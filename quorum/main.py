"""Quorum desk. Cloud Run serves this. Firestore keeps the docket."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from quorum import hearing as hearing_mod
from quorum import store
from quorum.cases import all_alerts, get_alert

app = FastAPI(title="Quorum", version="1.0.0")
FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
_TASKS: set[asyncio.Task] = set()


class ConveneBody(BaseModel):
    alert_id: str = Field(min_length=4, max_length=32)


class DecisionBody(BaseModel):
    action: str
    disposition: str
    note: str = ""


@app.on_event("startup")
def _startup() -> None:
    hearing_mod.configure_gemini()
    store.init()


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "store": store.mode(),
        "model": os.environ.get("QUORUM_MODEL", "gemini-2.5-flash"),
        "project": os.environ.get("GOOGLE_CLOUD_PROJECT", ""),
        "gemini": "enterprise" if os.environ.get("GOOGLE_GENAI_USE_ENTERPRISE", "").lower() in {"1", "true"} else "api-key" if os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY") else "unconfigured",
    }


@app.get("/api/alerts")
def alerts() -> dict:
    hearings = store.list_hearings()
    latest: dict[str, dict] = {}
    for item in hearings:
        current = latest.get(item["alert_id"])
        stamp = item.get("created_at") or item["id"]
        if current is None or stamp > (current.get("created_at") or current["id"]):
            latest[item["alert_id"]] = item
    rows = []
    for alert in all_alerts():
        filed = latest.get(alert["id"])
        rows.append({
            "id": alert["id"],
            "customer": alert["customer"]["name"],
            "city": alert["customer"]["city"],
            "product": alert["product"],
            "amount": alert["amount"],
            "currency": alert["currency"],
            "rule": alert["rule"],
            "urgency": alert["urgency"],
            "opened": alert["opened"],
            "summary": alert["summary"],
            "hearing_status": None if filed is None else filed["status"],
            "disposition": None if filed is None or not filed.get("disposition") else filed["disposition"].get("disposition"),
            "customer_message": None if filed is None or not filed.get("disposition") else filed["disposition"].get("customer_message"),
            "decision": None if filed is None else filed.get("decision"),
        })
    return {"alerts": rows}


@app.get("/api/alerts/{alert_id}")
def alert_detail(alert_id: str) -> dict:
    alert = get_alert(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="No file with that id.")
    hearings = [item for item in store.list_hearings() if item["alert_id"] == alert_id]
    hearings.sort(key=lambda item: item.get("created_at") or item["id"], reverse=True)
    return {"alert": alert, "hearings": hearings}


@app.get("/api/portfolio")
def portfolio() -> dict:
    hearings = [item for item in store.list_hearings() if item.get("decision")]
    cleared = 0
    escalated = 0
    for item in hearings:
        decision = item["decision"]["disposition"]
        if decision == "clear":
            cleared += 1
        elif decision in {"escalate", "hold", "split"}:
            escalated += 1
    return {
        "filed": len(hearings),
        "cleared": cleared,
        "kept": escalated,
    }


@app.post("/api/hearings")
async def convene(body: ConveneBody) -> StreamingResponse:
    if get_alert(body.alert_id) is None:
        raise HTTPException(status_code=404, detail="No file with that id.")
    record = hearing_mod.new_hearing(body.alert_id)
    queue: asyncio.Queue = asyncio.Queue()

    async def emit(event: dict) -> None:
        current = store.get_hearing(record["id"]) or record
        current.setdefault("events", []).append(event)
        if event.get("type") == "disposition":
            current["disposition"] = event["disposition"]
            current["engine"] = event.get("engine")
            current["status"] = "ready"
        store.save_hearing(current)
        await queue.put(event)

    async def produce() -> None:
        try:
            result = await hearing_mod.convene(body.alert_id, emit, record["id"])
            current = store.get_hearing(record["id"]) or record
            current.update({
                "status": "ready",
                "engine": result["engine"],
                "disposition": result["disposition"],
                "seats": result["seats"],
            })
            store.save_hearing(current)
        except Exception as exc:  # noqa: BLE001
            await emit({"type": "error", "message": str(exc)[:240]})
            current = store.get_hearing(record["id"]) or record
            current["status"] = "failed"
            store.save_hearing(current)
        finally:
            await queue.put(None)

    task = asyncio.create_task(produce())
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)

    async def stream():
        yield _frame({"type": "started", "hearing_id": record["id"], "alert_id": body.alert_id})
        while True:
            event = await queue.get()
            if event is None:
                break
            yield _frame(event)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/hearings/{hearing_id}")
def get_one(hearing_id: str) -> dict:
    found = store.get_hearing(hearing_id)
    if found is None:
        raise HTTPException(status_code=404, detail="That hearing is not on the docket.")
    return found


@app.post("/api/hearings/{hearing_id}/decision")
def decide(hearing_id: str, body: DecisionBody) -> dict:
    found = store.get_hearing(hearing_id)
    if found is None:
        raise HTTPException(status_code=404, detail="That hearing is not on the docket.")
    if body.disposition not in {"clear", "hold", "escalate", "split"}:
        raise HTTPException(status_code=400, detail="Disposition must be clear, hold, escalate, or split.")
    if body.action not in {"file", "override"}:
        raise HTTPException(status_code=400, detail="Action must be file or override.")
    found["decision"] = {
        "action": body.action,
        "disposition": body.disposition,
        "note": body.note.strip(),
        "officer": "Amina Rahman, night desk",
        "at": datetime.now(timezone.utc).isoformat(),
    }
    store.save_hearing(found)
    return found


def _frame(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND / "index.html")


app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
