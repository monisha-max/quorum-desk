"""Every test gets an empty docket in a temp dir, no uploads, and no real Gemini or Firestore."""

from __future__ import annotations

import pytest

from quorum import config, hearing, store, warehouse


class ToolContext:
    """The part of ADK's ToolContext the tools use."""

    def __init__(self, alert_id: str) -> None:
        self.state = {"alert_id": alert_id}

    def evidence(self) -> dict[str, dict]:
        return {key.split(":", 1)[1]: value for key, value in self.state.items() if key.startswith("evidence:")}


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    # A key in .env must never turn a test run into real model calls or real Firestore writes.
    monkeypatch.setattr(config, "gemini_mode", lambda: "none")
    monkeypatch.setattr(config, "USE_FIRESTORE", "off")
    monkeypatch.setattr(store, "BUNDLED", tmp_path / "bundled")
    monkeypatch.setattr(hearing, "_cooldown_until", 0.0)
    store.reset_local(tmp_path)
    warehouse.UPLOADED.clear()
    yield
    warehouse.UPLOADED.clear()


@pytest.fixture
def tool_context():
    return ToolContext
