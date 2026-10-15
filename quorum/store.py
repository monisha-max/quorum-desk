"""Dockets live in Firestore. A file copy keeps the desk up if Firestore is down."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

_LOCK = threading.Lock()
_MEMORY: dict[str, dict] = {}
_CLIENT = None
_MODE = "starting"
_COLLECTION = "quorum_hearings"
_PATH = Path(__file__).resolve().parents[1] / "data" / "hearings.json"


def mode() -> str:
    return _MODE


def init() -> str:
    global _CLIENT, _MODE
    project = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCLOUD_PROJECT")
    try:
        from google.cloud import firestore

        client = firestore.Client(project=project) if project else firestore.Client()
        list(client.collection(_COLLECTION).limit(1).stream())
        _CLIENT = client
        _MODE = "firestore"
    except Exception:
        _CLIENT = None
        _MODE = "file"
        _load_file()
    return _MODE


def _load_file() -> None:
    if not _PATH.exists():
        return
    try:
        saved = json.loads(_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return
    if isinstance(saved, dict):
        _MEMORY.update(saved)


def _flush_file() -> None:
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    _PATH.write_text(json.dumps(_MEMORY))


def save_hearing(hearing: dict) -> None:
    with _LOCK:
        if _CLIENT is not None:
            _CLIENT.collection(_COLLECTION).document(hearing["id"]).set(hearing)
            return
        _MEMORY[hearing["id"]] = hearing
        _flush_file()


def get_hearing(hearing_id: str) -> dict | None:
    with _LOCK:
        if _CLIENT is not None:
            snap = _CLIENT.collection(_COLLECTION).document(hearing_id).get()
            return snap.to_dict() if snap.exists else None
        return _MEMORY.get(hearing_id)


def list_hearings() -> list[dict]:
    with _LOCK:
        if _CLIENT is not None:
            return [snap.to_dict() for snap in _CLIENT.collection(_COLLECTION).stream()]
        return list(_MEMORY.values())
