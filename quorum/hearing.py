"""Convene a hearing: run the workflow, stream it to the desk, seal the record.

Modes, and what the desk tells the officer about each:

* live: Gemini sits every seat. A seat that fails or stalls falls back to its
  standby brief alone, and the record says which seats did.
* standby: no model calls. Authored briefs, over tool results that are run for
  real against the warehouse, so every citation still resolves.
* replay: a recorded, fully live Gemini hearing on the same file, streamed
  with its original timing and labelled as a replay of that hearing.
* auto: live if Gemini is configured and has not just run out of quota; else
  replay if this file has a recording and nothing was uploaded since; else
  standby.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import secrets
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from google.adk.agents.run_config import RunConfig, StreamingMode, ToolThreadPoolConfig
from google.adk.models.base_llm import BaseLlm
from google.adk.runners import InMemoryRunner
from google.genai import types

from quorum import agents, config, store, warehouse, workflow
from quorum.cases import get_alert

Emit = Callable[[dict], Awaitable[None]]
MODES = ("auto", "live", "standby", "replay")

# The prose field of each seat's answer, streamed to the desk as the model writes it.
PROSE = {
    "clerk": "summary", "ledger": "finding", "archivist": "finding", "statute": "finding",
    "sentinel": "finding", "prosecutor": "argument", "counsel": "argument", "prosecutor_rebuttal": "answer",
    "counsel_rebuttal": "answer", "magistrate": "rationale", "liaison": "message",
}
# Which seats sit when a node finishes.
_NEXT = {
    "open": ["clerk"],
    "clerk": list(workflow.EVIDENCE_SEATS),
    "brief": list(workflow.ADVOCATES),
    "rebuttals": ["magistrate"],
    "verify": ["liaison"],
}
_ROWS_STREAMED = 12
_QUOTA_COOLDOWN_S = 90.0
_REPLAY_MAX_GAP_S = 2.0
_cooldown_until = 0.0


class Unavailable(Exception):
    """The mode asked for cannot run on this desk right now."""

    def __init__(self, message: str, status: int) -> None:
        super().__init__(message)
        self.status = status


def new_id(alert_id: str) -> str:
    return f"{alert_id}-{datetime.now(timezone.utc):%Y%m%d%H%M%S}-{secrets.token_hex(2)}"


def cooling() -> float:
    """Seconds left before auto mode tries Gemini again after a quota failure."""
    return max(0.0, _cooldown_until - time.monotonic())


def _replayable(alert_id: str) -> dict | None:
    # A recording heard the file as it was; a document uploaded since would be ignored.
    if warehouse.UPLOADED.get(alert_id):
        return None
    return store.get_recording(alert_id)


def choose_mode(alert_id: str, requested: str = "auto", *, model: BaseLlm | None = None) -> tuple[str, dict | None]:
    gemini = model is not None or config.gemini_mode() != "none"
    if requested == "live":
        if not gemini:
            raise Unavailable("Gemini is not configured on this desk.", 409)
        return "live", None
    if requested == "standby":
        return "standby", None
    recording = _replayable(alert_id)
    if requested == "replay":
        if recording is None:
            raise Unavailable("This file has no recorded live hearing to replay.", 404)
        return "replay", recording
    if gemini and not cooling():
        return "live", None
    return ("replay", recording) if recording else ("standby", None)


# ---- streaming helpers -------------------------------------------------------


_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", '"': '"', "\\": "\\", "/": "/"}


def prose_so_far(buffer: str, field: str) -> str:
    """The value of `field` in a JSON object that is still being written."""
    match = re.search(rf'"{field}"\s*:\s*"', buffer)
    if not match:
        return ""
    out, i = [], match.end()
    while i < len(buffer):
        char = buffer[i]
        if char == '"':
            break
        if char != "\\":
            out.append(char)
            i += 1
            continue
        if i + 1 >= len(buffer):
            break
        code = buffer[i + 1]
        if code != "u":
            out.append(_ESCAPES.get(code, code))
            i += 2
            continue
        if i + 6 > len(buffer):
            break
        point = int(buffer[i + 2:i + 6], 16)
        if 0xD800 <= point < 0xDC00:
            if i + 12 > len(buffer):
                break
            low = int(buffer[i + 8:i + 12], 16)
            point = 0x10000 + ((point - 0xD800) << 10) + (low - 0xDC00)
            i += 6
        out.append(chr(point))
        i += 6
    return "".join(out)


def _trim(result) -> dict:
    """A tool result small enough to stream; the full rows stay in the warehouse."""
    if not isinstance(result, dict):
        return {"value": result}
    out = dict(result)
    rows = out.get("rows")
    if isinstance(rows, list) and len(rows) > _ROWS_STREAMED:
        out["rows"] = rows[:_ROWS_STREAMED]
        out["rows_total"] = len(rows)
    return out


class _Seat:
    """What has streamed for one seat in its current model turn."""

    def __init__(self) -> None:
        self.thought = ""
        self.text = ""
        self.sent = 0


# ---- the hearing ---------------------------------------------------------------


class Hearing:
    def __init__(self, alert: dict, mode: str, emit: Emit, hearing_id: str) -> None:
        self.alert = alert
        self.mode = mode
        self.emit = emit
        self.id = hearing_id
        self.started = time.perf_counter()
        self.created_at = store.now()
        self.events: list[dict] = []
        self.streams: dict[str, _Seat] = {}
        self.calls: set[str] = set()
        self.tokens: dict[str, dict[str, int]] = {}

    async def send(self, event: dict) -> None:
        event = {"t": round((time.perf_counter() - self.started) * 1000), **event}
        self.events.append(event)
        await self.emit(event)

    async def sitting(self, seats: list[str]) -> None:
        if seats:
            await self.send({"type": "sitting", "seats": seats})

    def models(self) -> dict[str, str | None]:
        return {seat: agents.model_name(seat) if self.mode == "live" else None for seat in workflow.SEATS}

    async def convened(self, **extra) -> None:
        await self.send({
            "type": "convened", "hearing_id": self.id, "alert_id": self.alert["id"], "mode": self.mode,
            "at": self.created_at, "models": self.models(), "engine": warehouse.engine_name(),
            "store": store.mode(), **extra,
        })

    # ---- ADK events -> desk events

    async def on_agent_event(self, seat: str, ev) -> None:
        stream = self.streams.setdefault(seat, _Seat())
        parts = ev.content.parts if ev.content and ev.content.parts else []
        if ev.partial:
            for part in parts:
                if part.text and part.thought:
                    stream.thought += part.text
                    await self.send({"type": "thought", "seat": seat, "text": part.text})
                elif part.text:
                    stream.text += part.text
                    await self.draft(seat, stream)
            return
        thought = "".join(part.text for part in parts if part.text and part.thought)
        if thought and not stream.thought:
            # A model that did not stream still shows its reasoning, once.
            await self.send({"type": "thought", "seat": seat, "text": thought})
        text = "".join(part.text for part in parts if part.text and not part.thought)
        if text and not stream.text:
            stream.text = text
            await self.draft(seat, stream)
        for part in parts:
            call = part.function_call
            key = call and (call.id or f"{seat}:{call.name}:{json.dumps(dict(call.args or {}), sort_keys=True)}")
            if call and key not in self.calls:
                self.calls.add(key)
                await self.send({"type": "tool_call", "seat": seat, "id": call.id, "name": call.name, "args": dict(call.args or {})})
            response = part.function_response
            if response:
                await self.send({"type": "tool_result", "seat": seat, "id": response.id, "name": response.name,
                                 "result": _trim(response.response)})
        usage = ev.usage_metadata
        if usage:
            counts = self.tokens.setdefault(seat, {"prompt": 0, "output": 0, "thinking": 0})
            counts["prompt"] += usage.prompt_token_count or 0
            counts["output"] += usage.candidates_token_count or 0
            counts["thinking"] += usage.thoughts_token_count or 0
        self.streams[seat] = _Seat()

    async def draft(self, seat: str, stream: _Seat) -> None:
        prose = prose_so_far(stream.text, PROSE.get(seat, ""))
        if len(prose) > stream.sent:
            await self.send({"type": "draft", "seat": seat, "append": prose[stream.sent:]})
            stream.sent = len(prose)

    async def on_node_output(self, name: str, output) -> None:
        if name == "open":
            await self.send({"type": "open", **output})
        elif name in workflow.SEATS:
            for i, tool in enumerate(output.get("tools") or []):
                call_id = f"{name}-standby-{i}"
                await self.send({"type": "tool_call", "seat": name, "id": call_id, "name": tool["name"], "args": tool["args"]})
                await self.send({"type": "tool_result", "seat": name, "id": call_id, "name": tool["name"],
                                 "result": _trim(tool["result"])})
            await self.send({"type": "seat", **{key: value for key, value in output.items() if key != "tools"}})
        elif name == "brief":
            await self.send({"type": "board", "board": output["board"]})
        elif name == "bench":
            await self.send({"type": "route", **output})
            await self.sitting(list(workflow.REBUTTALS) if output["route"] == "contested" else ["magistrate"])
            return
        elif name == "verify":
            await self.send({"type": "verified", **output})
        await self.sitting(_NEXT.get(name, []))

    # ---- sealing

    def record(self, state: dict, replay_of: str | None = None) -> dict:
        seats = {name: state[f"seat:{name}"] for name in workflow.SEATS if f"seat:{name}" in state}
        verified = state["verified"]
        sources = {name: seat["source"] for name, seat in seats.items()}
        return {
            "id": self.id,
            "alert_id": self.alert["id"],
            "mode": self.mode,
            "replay_of": replay_of,
            "created_at": self.created_at,
            "sealed_at": store.now(),
            "ms": round((time.perf_counter() - self.started) * 1000),
            "route": state.get("route"),
            "board": state.get("board", []),
            "seats": seats,
            "sources": sources,
            "verified": verified,
            "tokens": self.tokens,
            "engine": warehouse.engine_name(),
            "uploads": [doc["id"] for doc in warehouse.UPLOADED.get(self.alert["id"], [])],
            "status": "sealed",
            "decision": None,
        }

    async def seal(self, record: dict) -> dict:
        verdict = record["verified"]["verdict"]
        body = {
            "mode": record["mode"],
            "replay_of": record["replay_of"],
            "disposition": verdict["disposition"],
            "held": verdict.get("held_amount", ""),
            "released": verdict.get("released_amount", ""),
            "passed": record["verified"]["passed"],
            "checks": {check["id"]: check["status"] for check in record["verified"]["checks"]},
            "sources": record["sources"],
            "verdict_sha256": hashlib.sha256(store.canonical(verdict).encode()).hexdigest(),
        }
        entry = await asyncio.to_thread(store.append_audit, "hearing", self.id, self.alert["id"], body)
        record["audit"] = {"seq": entry["seq"], "hash": entry["hash"]}
        await asyncio.to_thread(store.save_hearing, record)
        await self.send({"type": "sealed", "hearing_id": self.id, "audit": record["audit"], "ms": record["ms"],
                         "disposition": verdict["disposition"], "passed": record["verified"]["passed"]})
        return record


def _run_config() -> RunConfig:
    # Sync tools (warehouse queries) run on a pool so one slow query does not stall every stream.
    return RunConfig(streaming_mode=StreamingMode.SSE, tool_thread_pool_config=ToolThreadPoolConfig(max_workers=8))


_RUNNER: InMemoryRunner | None = None


def _runner(model: BaseLlm | None) -> InMemoryRunner:
    """One runner for the desk; tests with a fake model get their own."""
    global _RUNNER
    if model is not None:
        return InMemoryRunner(node=workflow.build(model), app_name="quorum")
    if _RUNNER is None:
        _RUNNER = InMemoryRunner(node=workflow.build(), app_name="quorum")
    return _RUNNER


async def _hear(hearing: Hearing, model: BaseLlm | None) -> dict:
    global _cooldown_until
    alert = hearing.alert
    runner = _runner(model)
    await hearing.convened()
    session = await runner.session_service.create_session(
        app_name="quorum", user_id="desk",
        state={"alert_id": alert["id"], "hearing_id": hearing.id, "mode": "gemini" if hearing.mode == "live" else "standby"},
    )
    message = types.Content(role="user", parts=[types.Part(text=f"Hear {alert['id']}.")])
    try:
        async for ev in runner.run_async(user_id="desk", session_id=session.id, new_message=message, run_config=_run_config()):
            names = [segment.split("@")[0] for segment in (ev.node_info.path if ev.node_info else "").split("/") if segment]
            if len(names) >= 3 and names[1] in workflow.SEATS:
                await hearing.on_agent_event(names[1], ev)
            elif len(names) == 2 and ev.output is not None:
                await hearing.on_node_output(names[1], ev.output)
        state = (await runner.session_service.get_session(app_name="quorum", user_id="desk", session_id=session.id)).state
    finally:
        await runner.session_service.delete_session(app_name="quorum", user_id="desk", session_id=session.id)
    if "verified" not in state:
        raise RuntimeError("the hearing ended without a verdict")
    record = hearing.record(state)
    quota = sum(1 for seat in record["seats"].values() if seat.get("error") and ("429" in seat["error"] or "RESOURCE_EXHAUSTED" in seat["error"]))
    if quota >= 2:
        _cooldown_until = time.monotonic() + _QUOTA_COOLDOWN_S
    record = await hearing.seal(record)
    live = all(source in {"gemini", "desk"} for source in record["sources"].values())
    if hearing.mode == "live" and live and not record["uploads"] and model is None:
        await asyncio.to_thread(store.save_recording, alert["id"], {
            "alert_id": alert["id"], "hearing_id": hearing.id, "recorded_at": record["sealed_at"],
            "models": hearing.models(), "events": hearing.events, "record": record,
        })
    return record


async def _replay(hearing: Hearing, recording: dict) -> dict:
    original = recording["record"]
    await hearing.convened(replay_of=recording["hearing_id"], recorded_at=recording["recorded_at"],
                           recorded_models=recording["models"])
    last = 0
    for event in recording["events"]:
        if event["type"] in {"convened", "sealed"}:
            continue
        gap = min(_REPLAY_MAX_GAP_S, max(0.0, (event["t"] - last) / 1000))
        last = event["t"]
        if gap:
            await asyncio.sleep(gap)
        await hearing.send({key: value for key, value in event.items() if key != "t"})
    state = {f"seat:{name}": seat for name, seat in original["seats"].items()}
    state.update(verified=original["verified"], route=original["route"], board=original["board"])
    record = hearing.record(state, replay_of=recording["hearing_id"])
    record["tokens"] = original.get("tokens", {})
    return await hearing.seal(record)


async def convene(alert_id: str, emit: Emit, *, requested: str = "auto", model: BaseLlm | None = None,
                  hearing_id: str | None = None) -> dict | None:
    """Run one hearing to its seal. Emits a terminal sealed or error event either way."""
    alert = get_alert(alert_id)
    if alert is None:
        raise Unavailable(f"No file {alert_id}.", 404)
    mode, recording = await asyncio.to_thread(choose_mode, alert_id, requested, model=model)
    hearing = Hearing(alert, mode, emit, hearing_id or new_id(alert_id))
    try:
        if mode == "replay":
            return await _replay(hearing, recording)
        return await _hear(hearing, model)
    except Exception as exc:  # noqa: BLE001 - the desk must hear why a hearing stopped
        await hearing.send({"type": "error", "hearing_id": hearing.id, "message": f"{type(exc).__name__}: {str(exc)[:200]}"})
        raise
