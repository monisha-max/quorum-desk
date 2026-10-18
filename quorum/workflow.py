"""The hearing as an ADK 2 workflow graph.

    open -> clerk -> (ledger | archivist | statute | sentinel) -> evidence -> brief
         -> (prosecutor | counsel) -> openings -> bench
    bench --contested--> (prosecutor_rebuttal | counsel_rebuttal) -> rebuttals -> magistrate
    bench --agreed-----> magistrate
    magistrate -> verify -> liaison

Seats in parentheses sit at the same time and see only their own brief. The
Sentinel sits with the evidence seats, but what it reports goes to the
verifier alone: no advocate and not the Magistrate reads it. Each
seat is a function node wrapping its LlmAgent. A seat that stalls, or is
refused mid-stream, is asked once more if it has time left; a seat that still
fails, or runs out of time, falls back to the authored standby for that seat
and the hearing goes on. After two such failures the remaining seats skip the
model. The bench routes
on whether the openings disagree; the verifier is code.
"""

from __future__ import annotations

import asyncio
import math
import time

from google.adk.agents.context import Context
from google.adk.events.event import Event
from google.adk.models.base_llm import BaseLlm
from google.adk.workflow import JoinNode, Workflow, node

from quorum import agents, config, prompts, standby, verifier, warehouse
from quorum.cases import actionable, get_alert

EVIDENCE_SEATS = ("ledger", "archivist", "statute", "sentinel")
ADVOCATES = ("prosecutor", "counsel")
REBUTTALS = ("prosecutor_rebuttal", "counsel_rebuttal")
SEATS = ("clerk", *EVIDENCE_SEATS, *ADVOCATES, *REBUTTALS, "magistrate", "liaison")

# After this many seats fail in one hearing, the rest go straight to standby
# instead of each waiting out the same outage.
_FAILURES_BEFORE_STANDBY = 2
# A seat the service refused, or that stalled, is heard once more if this much of its time is left.
_RETRY_MIN_S = 20.0
# A seat streams something every few seconds while it thinks and writes. One
# that goes this long without a chunk has stalled, and asked again it usually
# answers in seconds. The clock starts with the run, not the first chunk: the
# stalls seen on the bench were waits for a first chunk.
_SILENCE_S = 25.0
# When each seat of a sitting hearing last streamed, by hearing id. The hearing
# stamps it from the events it relays; a graph run with no hearing has no entry,
# so its seats wait out their whole timeout.
HEARD: dict[str, dict[str, float]] = {}
# Quota and server errors: worth asking again. Anything else would fail the same way.
_REFUSALS = frozenset({429, 500, 502, 503, 504})


def _alert(ctx: Context) -> dict:
    return get_alert(ctx.state.get("alert_id"))


def documents(alert: dict) -> list[dict]:
    return list(alert["documents"]) + list(warehouse.UPLOADED.get(alert["id"], []))


def evidence(ctx: Context) -> dict[str, dict]:
    return {key.split(":", 1)[1]: value for key, value in ctx.state.to_dict().items() if key.startswith("evidence:")}


def seats(ctx: Context) -> dict[str, dict]:
    return {key.split(":", 1)[1]: value for key, value in ctx.state.to_dict().items() if key.startswith("seat:")}


def _short(exc: BaseException) -> str:
    exc = getattr(exc, "error", None) or exc  # ADK wraps a failed child node; report what actually failed
    text = str(exc).strip().splitlines()[0] if str(exc).strip() else ""
    return f"{type(exc).__name__}: {text[:160]}" if text else type(exc).__name__


def _refused(exc: BaseException) -> bool:
    exc = getattr(exc, "error", None) or exc
    return getattr(exc, "code", None) in _REFUSALS or getattr(exc, "status_code", None) in _REFUSALS


class Stalled(TimeoutError):
    """The seat streamed nothing for _SILENCE_S."""


async def _sit(ctx: Context, seat: str, agent, node_input, timeout: float):
    """Run the seat's agent, and once more if it stalled or was refused mid-stream, with time to spare.

    The model chain fails over only on an error before a model's first chunk. A
    refusal after that, or a stream that stops, would otherwise send the seat
    straight to standby. A refusal before anything streamed has already been
    through the whole chain, and is not asked again.
    """
    deadline = time.perf_counter() + timeout
    heard = HEARD.get(ctx.state.get("hearing_id"))
    started = asyncio.get_running_loop().time()
    try:
        return await _run(ctx, seat, agent, node_input, timeout)
    except Exception as exc:  # noqa: BLE001 - re-raised unless it is worth one more try
        left = deadline - time.perf_counter()
        # A graph run with no hearing cannot tell whether the seat streamed, so it is asked again.
        streamed = heard is None or heard.get(seat, started) > started
        if not ((_refused(exc) and streamed) or isinstance(exc, Stalled)) or left < _RETRY_MIN_S or _on_standby(ctx):
            raise
    return await _run(ctx, seat, agent, node_input, left)


async def _run(ctx: Context, seat: str, agent, node_input, timeout: float):
    """One run of the seat's agent: TimeoutError after `timeout`, Stalled after _SILENCE_S without a chunk."""
    loop = asyncio.get_running_loop()
    heard = HEARD.get(ctx.state.get("hearing_id"))
    started = loop.time()
    run = asyncio.ensure_future(ctx.run_node(agent, node_input=node_input))
    try:
        while not run.done():
            now = loop.time()
            # A stamp from an earlier run of this seat does not count for this one.
            quiet_since = max(started, heard.get(seat, started)) if heard is not None else math.inf
            if now - started >= timeout:
                raise TimeoutError
            if now - quiet_since >= _SILENCE_S:
                raise Stalled(f"nothing streamed for {_SILENCE_S:.0f} s")
            await asyncio.wait({run}, timeout=min(started + timeout, quiet_since + _SILENCE_S) - now)
        return run.result()
    finally:
        if not run.done():
            run.cancel()
            # Wait for it to wind down without raising its error, but still raise if this seat is itself cancelled.
            await asyncio.wait({run})
            if not run.cancelled():
                run.exception()  # retrieved, so asyncio does not log it as never retrieved


class _Standby(Exception):
    """Raised to skip the model when the hearing is already on standby."""


def _on_standby(ctx: Context) -> bool:
    """True when the hearing was convened on standby or Gemini has already failed enough seats.

    Failures are counted from the seat records rather than a shared counter:
    seats that sit at the same time write state in parallel branches, and two
    increments of one key would merge into one.
    """
    failed = sum(1 for record in seats(ctx).values() if record.get("error"))
    return ctx.state.get("mode") == "standby" or failed >= _FAILURES_BEFORE_STANDBY


# ---- fallbacks: what a seat does when Gemini does not answer ---------------


async def _fallback(seat: str, alert: dict, ctx: Context) -> tuple[dict, list[dict]]:
    # Tools run off the event loop, as the agents' own tool calls do, so a slow
    # warehouse query stalls this seat and not every other hearing's stream.
    tools: list[dict] = []
    if seat == "ledger":
        tools = await asyncio.to_thread(standby.run_ledger, alert, ctx)
    elif seat == "archivist":
        tools = [await asyncio.to_thread(standby.run_read_file, ctx)]
    elif seat == "statute":
        tools = [await asyncio.to_thread(standby.run_statute, alert, ctx)]
    elif seat == "magistrate":
        # The authored verdict cites the authored Ledger's refs; make sure they exist.
        have = set(evidence(ctx))
        tools = await asyncio.to_thread(standby.run_ledger, alert, ctx, have)
        if f"file:{alert['id']}" not in have:
            tools.append(await asyncio.to_thread(standby.run_read_file, ctx))
    out = standby.brief(alert, seat, evidence(ctx))
    if out is None and seat == "sentinel":
        out = {"finding": "No model screened the documents on this hearing. The verifier still checks them against its pattern, "
                          "and will not clear a file whose added documents went unscreened.", "instructions": []}
    if out is None and seat in REBUTTALS:
        side = seat.removesuffix("_rebuttal")
        opening = seats(ctx).get(side, {}).get("out", {})
        out = {"position": opening.get("position", "hold"), "answer": "No rebuttal on standby; the opening stands.",
               "facts": opening.get("facts", []), "moved": False}
    return out, tools


# ---- seat nodes ----------------------------------------------------------


def _seat(name: str, agent, prompt) -> object:
    timeout = config.SEAT_TIMEOUT_S * (1.6 if name == "magistrate" else 1)

    @node(name=name, rerun_on_resume=True)
    async def run(ctx: Context, node_input):
        alert = _alert(ctx)
        started = time.perf_counter()
        error = None
        tools: list[dict] = []
        try:
            if _on_standby(ctx):
                raise _Standby("hearing is on standby")
            out = await _sit(ctx, name, agent, prompt(alert, ctx), timeout)
            if not isinstance(out, dict):
                raise ValueError("no structured output")
            source = "gemini"
        except Exception as exc:  # noqa: BLE001 - any model failure falls back to the standby brief
            if not isinstance(exc, _Standby):
                error = _short(exc)
            out, tools = await _fallback(name, alert, ctx)
            source = "standby"
        record = {
            "seat": name,
            "source": source,
            "model": agents.model_name(name) if source == "gemini" else None,
            "out": out,
            "error": error,
            "ms": round((time.perf_counter() - started) * 1000),
            "tools": tools,
        }
        ctx.state[f"seat:{name}"] = record
        return record

    return run


def _prompt(seat: str):
    def clerk(alert, ctx):
        return prompts.clerk(alert, documents(alert))

    def sentinel(alert, ctx):
        return prompts.sentinel(alert, documents(alert))

    def evidence_seat(alert, ctx):
        return getattr(prompts, seat)(alert, seats(ctx)["clerk"]["out"])

    def advocate(alert, ctx):
        return prompts.advocate(alert, seats(ctx), ctx.state.get("board", []))

    def rebuttal(alert, ctx):
        return prompts.rebuttal(alert, seat.removesuffix("_rebuttal"), seats(ctx))

    def magistrate(alert, ctx):
        return prompts.magistrate(alert, seats(ctx), ctx.state.get("board", []), ctx.state.get("route") == "contested")

    if seat == "clerk":
        return clerk
    if seat == "sentinel":
        return sentinel
    if seat in EVIDENCE_SEATS:
        return evidence_seat
    if seat in ADVOCATES:
        return advocate
    if seat in REBUTTALS:
        return rebuttal
    return magistrate


# ---- desk nodes (code, no model) -----------------------------------------


@node(name="open")
async def open_file(ctx: Context, node_input):
    alert = _alert(ctx)
    if alert is None:
        raise ValueError(f"no file {ctx.state.get('alert_id')!r}")
    return {"alert_id": alert["id"], "open": [row["id"] for row in actionable(alert)]}


@node(name="brief")
async def brief(ctx: Context, node_input):
    board = prompts.board(evidence(ctx))
    ctx.state["board"] = board
    return {"board": board}


@node(name="bench")
async def bench(ctx: Context, node_input):
    sat = seats(ctx)
    positions = {side: sat[side]["out"].get("position") for side in ADVOCATES}
    route = "agreed" if positions["prosecutor"] == positions["counsel"] else "contested"
    ctx.state["route"] = route
    yield Event(output={"route": route, "positions": positions}, route=route)


@node(name="verify")
async def verify(ctx: Context, node_input):
    alert = _alert(ctx)
    sat = seats(ctx)
    scope = [value for key, value in ctx.state.to_dict().items() if key.startswith("scope:")]
    sentinel = sat.get("sentinel", {})
    result = verifier.verify(
        alert,
        sat["magistrate"]["out"],
        documents=documents(alert),
        evidence=evidence(ctx),
        tamper_flags=(sat.get("archivist", {}).get("out") or {}).get("tamper_flags", []),
        scope_attempts=scope,
        # None, not an empty list, when no model screened the documents: the verifier fails closed on uploads.
        quotes=(sentinel.get("out") or {}).get("instructions", []) if sentinel.get("source") == "gemini" else None,
    )
    ctx.state["verified"] = result
    return result


def _liaison(agent) -> object:
    @node(name="liaison", rerun_on_resume=True)
    async def run(ctx: Context, node_input):
        alert = _alert(ctx)
        result = ctx.state["verified"]
        verdict = result["verdict"]
        language = alert["customer"].get("language", "en")
        started = time.perf_counter()
        source, error, out = "desk", None, None
        if language == "en" and not result["lint"]:
            out = {"language": "en", "message": verdict["customer_message"], "english": verdict["customer_message"]}
        else:
            try:
                if _on_standby(ctx):
                    raise _Standby("hearing is on standby")
                out = await _sit(ctx, "liaison", agent, prompts.liaison(alert, verdict, result["lint"]), config.SEAT_TIMEOUT_S)
                if not isinstance(out, dict):
                    raise ValueError("no structured output")
                if verifier.lint_note(out.get("english", "")):
                    raise ValueError(f"note still uses {', '.join(verifier.lint_note(out['english']))}")
                source = "gemini"
            except Exception as exc:  # noqa: BLE001 - fall back to an authored or template note
                if not isinstance(exc, _Standby):
                    error = _short(exc)
                out = None
                # The authored translation is of the authored note; use it only if that note is what the desk approved.
                authored_note = (standby.brief(alert, "magistrate") or {}).get("customer_message")
                authored = standby.brief(alert, "liaison") if verdict["customer_message"] == authored_note else None
                if authored and not result["lint"]:
                    out, source = authored, "standby"
                else:
                    note = verdict["customer_message"] if not result["lint"] else verifier.safe_note(alert, verdict["disposition"])
                    out, source = {"language": "en", "message": note, "english": note}, "template"
        if result["lint"]:
            verdict["customer_message"] = out["english"]
            for check in result["checks"]:
                if check["id"] == "fc02":
                    check.update(status="fixed", detail=f"rewritten without {', '.join(result['lint'])}")
            result["passed"] = all(check["status"] != "fail" for check in result["checks"])
            ctx.state["verified"] = result
        record = {"seat": "liaison", "source": source, "model": agents.model_name("liaison") if source == "gemini" else None,
                  "out": out, "error": error, "ms": round((time.perf_counter() - started) * 1000), "tools": []}
        ctx.state["seat:liaison"] = record
        return record

    return run


def build(model: BaseLlm | None = None) -> Workflow:
    """The hearing graph. Tests pass one fake model for every seat."""
    seat = {name: _seat(name, agents.build(name, model), _prompt(name)) for name in SEATS if name != "liaison"}
    liaison = _liaison(agents.build("liaison", model))
    evidence_join = JoinNode(name="evidence")
    openings = JoinNode(name="openings")
    rebuttals = JoinNode(name="rebuttals")
    return Workflow(
        name="hearing",
        edges=[
            ("START", open_file, seat["clerk"], tuple(seat[name] for name in EVIDENCE_SEATS), evidence_join, brief,
             tuple(seat[name] for name in ADVOCATES), openings, bench),
            (bench, {"contested": tuple(seat[name] for name in REBUTTALS), "agreed": seat["magistrate"]}),
            (tuple(seat[name] for name in REBUTTALS), rebuttals, seat["magistrate"]),
            (seat["magistrate"], verify, liaison),
        ],
    )
