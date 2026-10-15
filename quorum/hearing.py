"""Run one hearing. Evidence seats sit in parallel. Counsel, then magistrate."""

from __future__ import annotations

import asyncio
import json
import os
import re
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from google.adk.runners import InMemoryRunner
from google.genai import types

from quorum import agents, store
from quorum.cases import get_alert
from quorum.standby import brief_for

Emit = Callable[[dict[str, Any]], Awaitable[None]]

_SEAT_ORDER = ("clerk", "ledger", "archivist", "statute", "counsel", "magistrate")
_GEMINI_DOWN = False


def _fatal(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(
        token in text
        for token in (
            "default credentials",
            "unauthenticated",
            "permission denied",
            "api key",
        )
    )


def configure_gemini() -> None:
    """Point ADK at Gemini Enterprise on Vertex when a project is set."""
    if os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"):
        return
    project = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCLOUD_PROJECT")
    if project:
        os.environ.setdefault("GOOGLE_GENAI_USE_ENTERPRISE", "true")
        os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project)
        os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "us-central1")


def parse_json(text: str) -> dict:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end < start:
        raise ValueError("model did not return JSON")
    return json.loads(cleaned[start : end + 1])


def _builders():
    return {
        "clerk": agents.clerk,
        "ledger": agents.ledger,
        "archivist": agents.archivist,
        "statute": agents.statute,
        "counsel": agents.counsel,
        "magistrate": agents.magistrate,
    }


async def _run_seat(name: str, prompt: str, emit: Emit) -> str:
    runner = InMemoryRunner(agent=_builders()[name](), app_name="quorum")
    session_id = str(uuid.uuid4())
    await runner.session_service.create_session(
        app_name="quorum",
        user_id="officer",
        session_id=session_id,
    )
    message = types.Content(role="user", parts=[types.Part(text=prompt)])
    final = ""
    async for event in runner.run_async(
        user_id="officer",
        session_id=session_id,
        new_message=message,
    ):
        content = getattr(event, "content", None)
        if not content:
            continue
        for part in content.parts or []:
            call = getattr(part, "function_call", None)
            if call and getattr(call, "name", None):
                await emit({"type": "tool", "seat": name, "tool": call.name})
            text = getattr(part, "text", None)
            if text and not getattr(event, "partial", False):
                final = text
    if not final:
        raise RuntimeError(f"{name} returned nothing")
    return final


async def _seat(name: str, prompt: str, emit: Emit, fallback: str | dict) -> Any:
    global _GEMINI_DOWN
    await emit({"type": "seat", "seat": name, "state": "speaking"})
    parsed: Any = None
    engine = "gemini"
    last_error = ""
    for _ in range(0 if _GEMINI_DOWN else 2):
        try:
            raw = await asyncio.wait_for(_run_seat(name, prompt, emit), timeout=90)
            parsed = parse_json(raw) if name == "magistrate" else raw
            if name == "magistrate" and parsed.get("disposition") not in {
                "clear",
                "hold",
                "escalate",
                "split",
            }:
                raise ValueError("disposition missing")
            break
        except Exception as exc:  # noqa: BLE001 — a dead seat must not kill the hearing
            last_error = str(exc)
            parsed = None
            if _fatal(exc):
                _GEMINI_DOWN = True
                break
    if parsed is None:
        engine = "standby"
        parsed = fallback
        await emit({"type": "seat_fallback", "seat": name, "detail": last_error[:180]})
    summary = _summary(name, parsed)
    await emit({"type": "seat", "seat": name, "state": "done", "summary": summary, "engine": engine})
    return parsed, engine


def _summary(name: str, parsed: Any) -> str:
    if isinstance(parsed, str):
        try:
            parsed = parse_json(parsed)
        except ValueError:
            return parsed[:360]
    if name == "magistrate":
        return parsed.get("rationale", "")
    for key in ("summary", "finding", "argument", "question"):
        if isinstance(parsed, dict) and parsed.get(key):
            return str(parsed[key])
    return json.dumps(parsed)[:360]


def _file_prompt(alert: dict) -> str:
    return (
        f"Alert {alert['id']}. Customer {alert['customer']['name']}. "
        f"Rule that fired: {alert['rule']}. Summary: {alert['summary']}"
    )


async def convene(alert_id: str, emit: Emit, hearing_id: str) -> dict:
    global _GEMINI_DOWN
    _GEMINI_DOWN = False
    configure_gemini()
    alert = get_alert(alert_id)
    if alert is None:
        raise KeyError(alert_id)
    standby = brief_for(alert_id)
    engines: list[str] = []

    clerk, clerk_engine = await _seat("clerk", _file_prompt(alert), emit, standby["clerk"])
    engines.append(clerk_engine)

    await emit({"type": "seat", "seat": "ledger", "state": "speaking"})
    await emit({"type": "seat", "seat": "archivist", "state": "speaking"})
    await emit({"type": "seat", "seat": "statute", "state": "speaking"})

    async def one(name: str, prompt: str, fallback: str):
        return await _seat_quiet(name, prompt, emit, fallback)

    ledger, archivist, statute = await asyncio.gather(
        one("ledger", f"Read the ledger for {alert_id}. {_file_prompt(alert)}", standby["ledger"]),
        one("archivist", f"Read the file for {alert_id}. {_file_prompt(alert)}", standby["archivist"]),
        one("statute", f"Find policy for {alert_id}. {alert['rule']}. {alert['summary']}", standby["statute"]),
    )
    engines.extend([ledger[1], archivist[1], statute[1]])

    notes = (
        f"File {alert_id}.\nClerk: {_summary('clerk', clerk)}\n"
        f"Ledger: {_summary('ledger', ledger[0])}\n"
        f"Archivist: {_summary('archivist', archivist[0])}\n"
        f"Statute: {_summary('statute', statute[0])}"
    )
    counsel, counsel_engine = await _seat(
        "counsel",
        "Argue the legitimate explanation.\n" + notes,
        emit,
        standby["counsel"],
    )
    engines.append(counsel_engine)
    magistrate, magistrate_engine = await _seat(
        "magistrate",
        notes + f"\nCounsel: {_summary('counsel', counsel)}\nWrite the disposition.",
        emit,
        standby["disposition"],
    )
    engines.append(magistrate_engine)
    engine = "gemini" if all(item == "gemini" for item in engines) else "mixed"
    if all(item == "standby" for item in engines):
        engine = "standby"
    disposition = magistrate if isinstance(magistrate, dict) else standby["disposition"]
    record = {
        "id": hearing_id,
        "alert_id": alert_id,
        "status": "ready",
        "engine": engine,
        "disposition": disposition,
        "seats": {
            "clerk": _summary("clerk", clerk),
            "ledger": _summary("ledger", ledger[0]),
            "archivist": _summary("archivist", archivist[0]),
            "statute": _summary("statute", statute[0]),
            "counsel": _summary("counsel", counsel),
            "magistrate": disposition.get("rationale", ""),
        },
    }
    await emit({"type": "disposition", "disposition": disposition, "engine": engine, "hearing_id": hearing_id})
    return record


async def _seat_quiet(name: str, prompt: str, emit: Emit, fallback: str):
    """Parallel seats already announced themselves. Avoid a second 'speaking' flash."""
    global _GEMINI_DOWN
    engine = "gemini"
    parsed: Any = None
    last_error = ""
    for _ in range(0 if _GEMINI_DOWN else 2):
        try:
            raw = await asyncio.wait_for(_run_seat(name, prompt, emit), timeout=90)
            parsed = raw
            break
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            parsed = None
            if _fatal(exc):
                _GEMINI_DOWN = True
                break
    if parsed is None:
        engine = "standby"
        parsed = fallback
        await emit({"type": "seat_fallback", "seat": name, "detail": last_error[:180]})
    await emit({
        "type": "seat",
        "seat": name,
        "state": "done",
        "summary": _summary(name, parsed),
        "engine": engine,
    })
    return parsed, engine


def new_hearing(alert_id: str) -> dict:
    from datetime import datetime, timezone

    hearing_id = uuid.uuid4().hex[:12]
    hearing = {
        "id": hearing_id,
        "alert_id": alert_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "hearing",
        "engine": None,
        "events": [],
        "disposition": None,
        "seats": {},
        "decision": None,
    }
    store.save_hearing(hearing)
    return hearing
