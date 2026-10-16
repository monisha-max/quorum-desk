"""The ADK graph, run end to end with a fake Gemini that plays the authored seats."""

import asyncio

from fakes import FakeGemini
from google.adk.runners import InMemoryRunner
from google.genai import types

from quorum import config, standby, workflow
from quorum.cases import get_alert


def _hear(alert_id: str, fake: FakeGemini, mode: str = "gemini") -> dict:
    async def run():
        runner = InMemoryRunner(node=workflow.build(fake), app_name="quorum")
        session = await runner.session_service.create_session(app_name="quorum", user_id="t", state={"alert_id": alert_id, "mode": mode})
        message = types.Content(role="user", parts=[types.Part(text=alert_id)])
        async for _ in runner.run_async(user_id="t", session_id=session.id, new_message=message):
            pass
        return (await runner.session_service.get_session(app_name="quorum", user_id="t", session_id=session.id)).state

    return asyncio.run(run())


def _fake(**kw) -> FakeGemini:
    fake = FakeGemini(**{key: set(value) if key in {"fail", "stall"} else value for key, value in kw.items()})
    fake.calls = []
    return fake


def _sources(state: dict) -> dict[str, str]:
    return {name: state[f"seat:{name}"]["source"] for name in workflow.SEATS if f"seat:{name}" in state}


def test_contested_openings_go_to_rebuttal():
    fake = _fake()
    state = _hear("HL-4402", fake)
    assert state["route"] == "contested"
    assert {"prosecutor_rebuttal", "counsel_rebuttal"} <= set(fake.calls)
    assert set(_sources(state).values()) == {"gemini"}
    assert state["verified"]["passed"] and state["verified"]["verdict"]["disposition"] == "clear"


def test_agreed_openings_skip_rebuttal_and_english_skips_the_liaison_model():
    fake = _fake()
    state = _hear("HL-4429", fake)
    assert state["route"] == "agreed"
    assert "prosecutor_rebuttal" not in fake.calls and "liaison" not in fake.calls
    assert state["seat:liaison"]["source"] == "desk"
    assert "seat:prosecutor_rebuttal" not in state


def test_evidence_seats_see_only_their_own_tools():
    state = _hear("HL-4374", _fake())
    evidence = {key.split(":", 1)[1]: value["tool"] for key, value in state.items() if key.startswith("evidence:")}
    assert "fan_in:041-883921" in evidence and "FC-22" in evidence and "file:HL-4374" in evidence


def test_a_failed_seat_falls_back_alone():
    state = _hear("HL-4381", _fake(fail={"magistrate"}))
    sources = _sources(state)
    assert sources["magistrate"] == "standby"
    assert "429" in state["seat:magistrate"]["error"]
    assert all(source == "gemini" for name, source in sources.items() if name != "magistrate")
    assert state["verified"]["passed"]


def test_two_failures_put_the_rest_of_the_hearing_on_standby():
    fake = _fake(fail={"ledger", "archivist"})
    state = _hear("HL-4374", fake)
    sources = _sources(state)
    later = ("prosecutor", "counsel", "prosecutor_rebuttal", "counsel_rebuttal", "magistrate")
    assert all(sources[name] == "standby" for name in later)
    assert not set(later) & set(fake.calls)
    assert state["verified"]["passed"]


def test_a_stalled_seat_times_out(monkeypatch):
    monkeypatch.setattr(config, "SEAT_TIMEOUT_S", 0.3)
    state = _hear("HL-4429", _fake(stall={"counsel"}))
    assert state["seat:counsel"]["source"] == "standby"
    assert state["seat:counsel"]["error"].startswith("TimeoutError")
    assert state["seat:magistrate"]["source"] == "gemini"


def test_standby_mode_calls_no_model():
    fake = _fake()
    state = _hear("HL-4366", fake, mode="standby")
    assert fake.calls == []
    assert state["verified"]["verdict"]["disposition"] == "split"


def test_liaison_translates_for_a_nepali_speaker():
    state = _hear("HL-4402", _fake())
    assert state["seat:liaison"]["source"] == "gemini"
    assert state["seat:liaison"]["out"]["language"] == "ne"


def _own_note(alert_id: str) -> dict:
    """A live Magistrate writes its own note; the authored translation is not of it."""
    verdict = dict(standby.brief(get_alert(alert_id), "magistrate"))
    verdict["customer_message"] = "We have paused your payment while a person on our team checks it. Please call the number on the back of your card."
    return verdict


def test_a_failed_liaison_after_a_live_verdict_sends_the_approved_english():
    state = _hear("HL-4381", _fake(fail={"liaison"}, overrides={"magistrate": _own_note("HL-4381")}))
    liaison = state["seat:liaison"]
    assert liaison["source"] == "template"
    assert liaison["out"]["message"] == state["verified"]["verdict"]["customer_message"]


def test_the_authored_translation_is_used_only_for_the_note_it_translates():
    state = _hear("HL-4381", _fake(fail={"liaison"}))
    assert state["seat:liaison"]["source"] == "standby"


def test_a_failed_liaison_after_a_standby_verdict_uses_the_authored_translation():
    state = _hear("HL-4381", _fake(fail={"magistrate", "liaison"}))
    assert state["seat:liaison"]["source"] == "standby"
    assert state["seat:liaison"]["out"]["language"] == "tl"


def test_a_liaison_that_keeps_banned_words_is_replaced():
    fake = _fake(overrides={"magistrate": _own_note("HL-4381"),
                            "liaison": {"language": "tl", "message": "x", "english": "Your payment was flagged."}})
    state = _hear("HL-4381", fake)
    assert state["seat:liaison"]["source"] == "template"
    assert "flagged" in state["seat:liaison"]["error"]


def test_a_ledger_that_reaches_off_the_file_is_refused_and_reported():
    fake = _fake(tool_overrides={"ledger": [("counterparty_fan_in", {"account": "999-000000"})]})
    state = _hear("HL-4402", fake)
    assert "scope:counterparty_fan_in:999-000000" in state
    checks = {check["id"]: check["status"] for check in state["verified"]["checks"]}
    assert checks["scope"] == "fail"
    assert state["verified"]["verdict"]["disposition"] == "hold"
