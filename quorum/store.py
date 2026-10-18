"""The docket. Firestore when it is reachable, a local file when it is not.

Three collections:

* hearings: one sealed record per hearing, with the officer's decision added later;
* audit: an append-only hash chain of everything the desk did. Each entry
  stores its body as the exact JSON string that was hashed, so anyone,
  including the browser, can recompute sha256(prev + "\\n" + body) and find a
  changed or missing entry without trusting this server's serialiser;
* recordings: the event stream of a fully live Gemini hearing, replayed, and
  labelled as a replay, when Gemini is out of quota.
"""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from quorum import config

GENESIS = "0" * 64
_HEARINGS = "quorum_hearings"
_AUDIT = "quorum_audit"
_HEAD = "quorum_audit_head"
_RECORDINGS = "quorum_recordings"
_DATA = config.ROOT / "data"
# Recordings that ship with the code, so a fresh instance can replay a real hearing.
BUNDLED = config.ROOT / "recordings"

_LOCK = threading.Lock()
_CLIENT = None
_MODE = "starting"
_LOCAL: dict[str, dict] = {"hearings": {}, "audit": {}, "recordings": {}}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def entry_hash(prev: str, body: str) -> str:
    return hashlib.sha256(f"{prev}\n{body}".encode()).hexdigest()


def mode() -> str:
    return _MODE


def init() -> str:
    """Connect to Firestore if allowed and reachable; otherwise load the local files."""
    global _CLIENT, _MODE
    wanted = config.USE_FIRESTORE.lower()
    if wanted not in {"0", "off", "false", "no"}:
        try:
            from google.cloud import firestore

            client = firestore.Client(project=config.PROJECT or None)
            list(client.collection(_HEARINGS).limit(1).stream(timeout=5))
            _CLIENT, _MODE = client, "firestore"
            return _MODE
        except Exception:  # noqa: BLE001 - no credentials, no database, or no network: keep the desk up
            if wanted in {"1", "on", "true", "yes"}:
                raise
    _CLIENT, _MODE = None, "file"
    for name in _LOCAL:
        path = _DATA / f"{name}.json"
        try:
            _LOCAL[name] = json.loads(path.read_text()) if path.exists() else {}
        except (OSError, json.JSONDecodeError):
            _LOCAL[name] = {}
    return _MODE


def _flush(name: str) -> None:
    _DATA.mkdir(parents=True, exist_ok=True)
    path = _DATA / f"{name}.json"
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(_LOCAL[name], ensure_ascii=False))
    temp.replace(path)


# ---- hearings ------------------------------------------------------------


def save_hearing(hearing: dict) -> None:
    if _CLIENT is not None:
        _CLIENT.collection(_HEARINGS).document(hearing["id"]).set(hearing)
        return
    with _LOCK:
        _LOCAL["hearings"][hearing["id"]] = hearing
        _flush("hearings")


def get_hearing(hearing_id: str) -> dict | None:
    if _CLIENT is not None:
        snap = _CLIENT.collection(_HEARINGS).document(hearing_id).get()
        return snap.to_dict() if snap.exists else None
    with _LOCK:
        return _LOCAL["hearings"].get(hearing_id)


def list_hearings(alert_id: str | None = None, limit: int = 200) -> list[dict]:
    """Newest first."""
    if _CLIENT is not None:
        from google.cloud import firestore

        query = _CLIENT.collection(_HEARINGS)
        if alert_id:
            # Firestore cannot filter on one field and sort on another without a composite
            # index, and the deploy creates none. One file's hearings are few, so sort here.
            rows = [snap.to_dict() for snap in query.where(filter=firestore.FieldFilter("alert_id", "==", alert_id)).stream()]
            return sorted(rows, key=lambda row: row["created_at"], reverse=True)[:limit]
        return [snap.to_dict() for snap in query.order_by("created_at", direction="DESCENDING").limit(limit).stream()]
    with _LOCK:
        rows = [row for row in _LOCAL["hearings"].values() if not alert_id or row["alert_id"] == alert_id]
    return sorted(rows, key=lambda row: row["created_at"], reverse=True)[:limit]


# ---- audit chain -----------------------------------------------------------


def _entry(seq: int, prev: str, kind: str, hearing_id: str, alert_id: str, body: dict) -> dict:
    text = canonical({"kind": kind, "hearing_id": hearing_id, "alert_id": alert_id, **body})
    return {"seq": seq, "at": now(), "kind": kind, "hearing_id": hearing_id, "alert_id": alert_id,
            "body": text, "prev": prev, "hash": entry_hash(prev, text)}


def append_audit(kind: str, hearing_id: str, alert_id: str, body: dict) -> dict:
    """Append one entry to the chain. Concurrent appends serialise on the chain head."""
    if _CLIENT is not None:
        from google.cloud import firestore

        head_ref = _CLIENT.collection(_HEAD).document("head")

        @firestore.transactional
        def append(transaction):
            snap = head_ref.get(transaction=transaction)
            head = snap.to_dict() if snap.exists else {"seq": 0, "hash": GENESIS}
            entry = _entry(head["seq"] + 1, head["hash"], kind, hearing_id, alert_id, body)
            transaction.set(_CLIENT.collection(_AUDIT).document(f"{entry['seq']:09d}"), entry)
            transaction.set(head_ref, {"seq": entry["seq"], "hash": entry["hash"]})
            return entry

        return append(_CLIENT.transaction())
    with _LOCK:
        chain = _LOCAL["audit"]
        last = chain[max(chain, key=int)] if chain else {"seq": 0, "hash": GENESIS}
        entry = _entry(last["seq"] + 1, last["hash"], kind, hearing_id, alert_id, body)
        chain[str(entry["seq"])] = entry
        _flush("audit")
        return entry


def audit(limit: int = 500) -> list[dict]:
    """The chain in order, oldest first, ending at the head."""
    if _CLIENT is not None:
        from google.cloud import firestore

        query = _CLIENT.collection(_AUDIT).order_by("seq", direction=firestore.Query.DESCENDING).limit(limit)
        return sorted((snap.to_dict() for snap in query.stream()), key=lambda entry: entry["seq"])
    with _LOCK:
        entries = sorted(_LOCAL["audit"].values(), key=lambda entry: entry["seq"])
    return entries[-limit:]


def verify_chain(entries: list[dict]) -> dict:
    """Recompute every hash. The browser runs the same check with SubtleCrypto."""
    prev = entries[0]["prev"] if entries else GENESIS
    for entry in entries:
        if entry["prev"] != prev or entry_hash(entry["prev"], entry["body"]) != entry["hash"]:
            return {"ok": False, "broken_at": entry["seq"], "checked": len(entries)}
        prev = entry["hash"]
    return {"ok": True, "broken_at": None, "checked": len(entries), "head": prev}


# ---- recordings ------------------------------------------------------------


def save_recording(alert_id: str, recording: dict) -> None:
    if _CLIENT is not None:
        # One string field: Firestore caps nesting and forbids arrays of arrays; a recording is opaque to queries anyway.
        _CLIENT.collection(_RECORDINGS).document(alert_id).set({"alert_id": alert_id, "json": canonical(recording)})
    with _LOCK:
        _LOCAL["recordings"][alert_id] = recording
        if _CLIENT is None:
            _flush("recordings")


def get_recording(alert_id: str) -> dict | None:
    with _LOCK:
        found = _LOCAL["recordings"].get(alert_id)
    if found:
        return found
    if _CLIENT is not None:
        snap = _CLIENT.collection(_RECORDINGS).document(alert_id).get()
        if snap.exists:
            return json.loads(snap.to_dict()["json"])
    path = BUNDLED / f"{alert_id}.json"
    if path.exists():
        return json.loads(path.read_text())
    return None


def recorded_alerts() -> set[str]:
    with _LOCK:
        found = set(_LOCAL["recordings"])
    if BUNDLED.exists():
        found |= {path.stem for path in BUNDLED.glob("HL-*.json")}
    if _CLIENT is not None:
        found |= {snap.id for snap in _CLIENT.collection(_RECORDINGS).select([]).stream()}
    return found


def reset_local(directory: Path | None = None) -> None:
    """Point the file store at a fresh directory. Tests only."""
    global _DATA, _CLIENT, _MODE
    _DATA = directory or _DATA
    _CLIENT, _MODE = None, "file"
    for name in _LOCAL:
        _LOCAL[name] = {}
