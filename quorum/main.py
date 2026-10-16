"""Quorum desk. Cloud Run serves this; Firestore keeps the docket and the audit chain."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from collections import deque
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from quorum import agents, config, hearing, store, verifier, warehouse, workflow
from quorum.cases import all_alerts, get_alert

FRONTEND = config.ROOT / "frontend"
_KEEPALIVE_S = 15.0
_LIVE_KEEP_S = 600.0


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.configure_gemini()
    await asyncio.to_thread(store.init)
    await asyncio.to_thread(warehouse.warm)
    yield


app = FastAPI(title="Quorum", version="2.0.0", lifespan=lifespan)


# ---- live hearings: one producer, any number of followers ------------------


class Live:
    """A hearing's events so far. Followers can attach late and read from any index."""

    def __init__(self, alert_id: str) -> None:
        self.alert_id = alert_id
        self.events: list[dict] = []
        self.done = False
        self.finished_at = 0.0
        self.cond = asyncio.Condition()

    async def push(self, event: dict) -> None:
        async with self.cond:
            self.events.append(event)
            self.cond.notify_all()

    async def close(self) -> None:
        async with self.cond:
            self.done = True
            self.finished_at = time.monotonic()
            self.cond.notify_all()

    async def follow(self, start: int = 0):
        """Yield events from `start`; None now and then so the stream can send a keepalive."""
        index = start
        while True:
            # Never yield while holding the lock: a follower that stops reading must not stall the producer.
            async with self.cond:
                try:
                    await asyncio.wait_for(self.cond.wait_for(lambda: len(self.events) > index or self.done), _KEEPALIVE_S)
                except TimeoutError:
                    pass
                batch, done = self.events[index:], self.done
            if not batch and not done:
                yield None
                continue
            for event in batch:
                yield event
            index += len(batch)
            if done and index >= len(self.events):
                return


_LIVE: dict[str, Live] = {}
_TASKS: set[asyncio.Task] = set()
_ACTIVE = 0
_BY_IP: dict[str, deque[float]] = {}
_ALL: deque[float] = deque()


def _sweep() -> None:
    now = time.monotonic()
    for hearing_id in [key for key, live in _LIVE.items() if live.done and now - live.finished_at > _LIVE_KEEP_S]:
        del _LIVE[hearing_id]


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")


def _admit(request: Request) -> None:
    """Rate limits and the concurrency cap. Too many is expected, so 429, with when to retry."""
    now = time.monotonic()
    while _ALL and now - _ALL[0] > 60:
        _ALL.popleft()
    recent = _BY_IP.setdefault(_client_ip(request), deque())
    while recent and now - recent[0] > 60:
        recent.popleft()
    if _ACTIVE >= config.MAX_CONCURRENT_HEARINGS:
        raise HTTPException(429, "The bench is full. Try again in a moment.", headers={"Retry-After": "20"})
    if len(recent) >= config.HEARINGS_PER_IP_PER_MINUTE:
        raise HTTPException(429, "Too many hearings from this address in a minute.",
                            headers={"Retry-After": str(max(1, round(60 - (now - recent[0]))))})
    if len(_ALL) >= config.HEARINGS_PER_MINUTE:
        raise HTTPException(429, "The desk has heard its limit for this minute.",
                            headers={"Retry-After": str(max(1, round(60 - (now - _ALL[0]))))})
    recent.append(now)
    _ALL.append(now)


def _frame(event: dict | None) -> str:
    if event is None:
        return ": keepalive\n\n"
    return f"event: {event['type']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"


def _stream(live: Live, start: int = 0) -> StreamingResponse:
    async def frames():
        async for event in live.follow(start):
            yield _frame(event)

    return StreamingResponse(frames(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---- request bodies ------------------------------------------------------------


Disposition = Literal["clear", "hold", "escalate", "split"]


class HearBody(BaseModel):
    mode: Literal["auto", "live", "standby", "replay"] = "auto"


class DecisionBody(BaseModel):
    action: Literal["file", "override"]
    disposition: Disposition | None = None
    note: str = Field(default="", max_length=600)
    officer: str = Field(default="Duty officer", min_length=2, max_length=60)


class DocumentBody(BaseModel):
    kind: str = Field(min_length=2, max_length=40)
    detail: str = Field(min_length=4, max_length=4000)


# ---- reads -----------------------------------------------------------------


def _alert_or_404(alert_id: str) -> dict:
    alert = get_alert(alert_id)
    if alert is None:
        raise HTTPException(404, f"No file {alert_id}.")
    return alert


def _hearing_or_404(hearing_id: str) -> dict:
    found = store.get_hearing(hearing_id)
    if found is None:
        raise HTTPException(404, "That hearing is not on the docket.")
    return found


def _brief(record: dict) -> dict:
    verdict = record["verified"]["verdict"]
    return {
        "id": record["id"], "mode": record["mode"], "replay_of": record.get("replay_of"),
        "created_at": record["created_at"], "ms": record["ms"], "route": record["route"],
        "disposition": verdict["disposition"], "confidence": verdict.get("confidence"),
        "false_positive": verdict.get("false_positive", False), "passed": record["verified"]["passed"],
        "held": verdict.get("held_amount", ""), "released": verdict.get("released_amount", ""),
        "sources": record["sources"], "decision": record.get("decision"), "audit": record.get("audit"),
    }


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@app.get("/api/config")
def desk_config() -> dict:
    return {
        "gemini": config.gemini_mode(),
        "models": {seat: agents.model_name(seat) for seat in workflow.SEATS},
        "fallback_models": config.FALLBACK_MODELS,
        "thinking": config.THINKING,
        "engine": warehouse.engine_name(),
        "store": store.mode(),
        "cooling_s": round(hearing.cooling()),
        "recorded": sorted(store.recorded_alerts()),
        "limits": {"concurrent": config.MAX_CONCURRENT_HEARINGS, "per_ip_per_minute": config.HEARINGS_PER_IP_PER_MINUTE},
        "host": "cloud-run" if os.environ.get("K_SERVICE") else "local",
    }


@app.get("/api/alerts")
def alerts() -> dict:
    latest: dict[str, dict] = {}
    for record in store.list_hearings():
        latest.setdefault(record["alert_id"], record)
    rows = []
    for alert in all_alerts():
        record = latest.get(alert["id"])
        rows.append({
            "id": alert["id"], "customer": alert["customer"]["name"], "segment": alert["customer"]["segment"],
            "city": alert["customer"]["city"], "language": alert["customer"].get("language", "en"),
            "product": alert["product"], "amount": alert["amount"], "currency": alert["currency"],
            "rule": alert["rule"], "urgency": alert["urgency"], "opened": alert["opened"], "summary": alert["summary"],
            "uploads": len(warehouse.UPLOADED.get(alert["id"], [])),
            "latest": _brief(record) if record else None,
        })
    return {"alerts": rows}


@app.get("/api/alerts/{alert_id}")
def alert_detail(alert_id: str) -> dict:
    alert = _alert_or_404(alert_id)
    documents = workflow.documents(alert)
    return {
        "alert": alert,
        "documents": documents,
        "instructions": verifier.scan_documents(documents),
        "hearings": [_brief(record) for record in store.list_hearings(alert_id)],
        "recorded": store.get_recording(alert_id) is not None,
    }


@app.get("/api/hearings/{hearing_id}")
def hearing_detail(hearing_id: str) -> dict:
    live = _LIVE.get(hearing_id)
    if live and not live.done:
        return {"id": hearing_id, "alert_id": live.alert_id, "status": "sitting", "events": len(live.events)}
    return _hearing_or_404(hearing_id)


@app.get("/api/hearings/{hearing_id}/stream")
def hearing_stream(hearing_id: str, start: int = 0) -> StreamingResponse:
    """Re-attach to a hearing still sitting on this instance, from event `start`."""
    live = _LIVE.get(hearing_id)
    if live is None:
        raise HTTPException(404, "That hearing is not sitting here; read the sealed record instead.")
    return _stream(live, max(0, start))


@app.get("/api/audit")
def audit(limit: int = 300) -> dict:
    entries = store.audit(max(1, min(limit, 2000)))
    return {"entries": entries, "check": store.verify_chain(entries), "genesis": store.GENESIS}


@app.get("/api/metrics")
def metrics() -> dict:
    records = store.list_hearings(limit=1000)
    heard = [record for record in records if record["mode"] != "replay"]
    by_disposition: dict[str, int] = {}
    sources: dict[str, int] = {}
    held: dict[str, float] = {}
    released: dict[str, float] = {}
    struck = overturned = false_positives = 0
    for record in heard:
        struck += len(record["verified"].get("struck", []))
        overturned += bool(record["verified"].get("overturned"))
        for source in record["sources"].values():
            sources[source] = sources.get(source, 0) + 1
    # Outcomes and money come from each file's latest hearing, so hearing a file
    # again does not count its funds twice. Records are newest first.
    standing: dict[str, dict] = {}
    for record in heard:
        standing.setdefault(record["alert_id"], record)
    for record in standing.values():
        verdict = record["verified"]["verdict"]
        by_disposition[verdict["disposition"]] = by_disposition.get(verdict["disposition"], 0) + 1
        false_positives += bool(verdict.get("false_positive"))
        alert = get_alert(record["alert_id"])
        rows = {row["id"]: row for row in alert["transactions"]} if alert else {}
        for ids, totals in ((verdict.get("held_txn_ids", []), held), (verdict.get("released_txn_ids", []), released)):
            for txn_id in ids:
                if txn_id in rows:
                    totals[rows[txn_id]["currency"]] = totals.get(rows[txn_id]["currency"], 0) + rows[txn_id]["amount"]
    decided = [record["decision"] for record in records if record.get("decision")]
    # Standby and replay timings say nothing about how long Gemini takes.
    seconds = sorted(record["ms"] / 1000 for record in heard if record["mode"] == "live")
    return {
        "hearings": len(heard),
        "replays": len(records) - len(heard),
        "by_disposition": by_disposition,
        "false_positives_cleared": false_positives,
        "funds_held": held,
        "funds_released": released,
        "facts_struck": struck,
        "verdicts_overturned": overturned,
        "seat_sources": sources,
        "files_decided": len(standing),
        "median_live_seconds": seconds[len(seconds) // 2] if seconds else None,
        "decisions": len(decided),
        "officer_overrides": sum(1 for decision in decided if decision["action"] == "override"),
    }


# ---- writes ----------------------------------------------------------------


@app.post("/api/alerts/{alert_id}/hear")
async def hear(alert_id: str, request: Request, body: HearBody | None = None) -> StreamingResponse:
    global _ACTIVE
    _alert_or_404(alert_id)
    requested = (body or HearBody()).mode
    try:
        mode, _ = await asyncio.to_thread(hearing.choose_mode, alert_id, requested)
    except hearing.Unavailable as exc:
        raise HTTPException(exc.status, str(exc)) from exc
    _admit(request)
    _sweep()
    hearing_id = hearing.new_id(alert_id)
    live = _LIVE[hearing_id] = Live(alert_id)
    _ACTIVE += 1

    async def run() -> None:
        global _ACTIVE
        try:
            # The hearing runs to its seal even if the officer closes the tab.
            await hearing.convene(alert_id, live.push, requested=mode, hearing_id=hearing_id)
        except Exception as exc:  # noqa: BLE001 - every stream ends with sealed or error
            if not live.events or live.events[-1]["type"] != "error":
                await live.push({"type": "error", "hearing_id": hearing_id, "message": f"{type(exc).__name__}: {str(exc)[:200]}"})
        finally:
            _ACTIVE -= 1
            await live.close()

    task = asyncio.create_task(run())
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)
    response = _stream(live)
    response.headers["X-Hearing-Id"] = hearing_id
    return response


@app.post("/api/hearings/{hearing_id}/decision")
async def decide(hearing_id: str, body: DecisionBody) -> dict:
    record = await asyncio.to_thread(_hearing_or_404, hearing_id)
    if record.get("decision"):
        raise HTTPException(409, "This hearing has already been decided.")
    proposed = record["verified"]["verdict"]["disposition"]
    if body.action == "file":
        if body.disposition and body.disposition != proposed:
            raise HTTPException(422, "Filing keeps the Magistrate's disposition. Use override to change it.")
        disposition = proposed
    else:
        if not body.disposition or body.disposition == proposed:
            raise HTTPException(422, "An override needs a disposition different from the Magistrate's.")
        if len(body.note.strip()) < 12:
            raise HTTPException(422, "An override needs a note of at least a sentence saying why.")
        disposition = body.disposition
    decision = {"action": body.action, "disposition": disposition, "proposed": proposed,
                "note": body.note.strip(), "officer": body.officer.strip(), "at": store.now()}
    entry = await asyncio.to_thread(store.append_audit, "decision", hearing_id, record["alert_id"], decision)
    record["decision"] = {**decision, "audit": {"seq": entry["seq"], "hash": entry["hash"]}}
    await asyncio.to_thread(store.save_hearing, record)
    return record


@app.post("/api/alerts/{alert_id}/documents")
async def upload(alert_id: str, body: DocumentBody) -> dict:
    alert = _alert_or_404(alert_id)
    uploaded = warehouse.UPLOADED.setdefault(alert_id, [])
    if len(uploaded) >= config.UPLOADS_PER_FILE:
        raise HTTPException(409, f"This file already has {config.UPLOADS_PER_FILE} uploaded documents.")
    doc = {"id": f"up-{len(uploaded) + 1}", "kind": body.kind.strip(), "detail": body.detail.strip(), "uploaded": True}
    uploaded.append(doc)
    scan = verifier.scan_documents([doc])
    entry = await asyncio.to_thread(store.append_audit, "document", "", alert["id"], {
        "doc_id": doc["id"], "kind": doc["kind"], "detail_sha256": hashlib.sha256(doc["detail"].encode()).hexdigest(),
        "reads_as_instruction": bool(scan),
    })
    return {"document": doc, "reads_as_instruction": scan, "audit": {"seq": entry["seq"], "hash": entry["hash"]}}


@app.delete("/api/alerts/{alert_id}/documents")
async def clear_uploads(alert_id: str) -> dict:
    alert = _alert_or_404(alert_id)
    removed = [doc["id"] for doc in warehouse.UPLOADED.pop(alert_id, [])]
    if removed:
        await asyncio.to_thread(store.append_audit, "documents_removed", "", alert["id"], {"doc_ids": removed})
    return {"removed": removed}


# ---- the desk ----------------------------------------------------------------


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND / "index.html")


app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
