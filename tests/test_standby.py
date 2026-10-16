"""The standby hearing must be as well grounded as a live one: every authored fact resolves."""

import pytest

from quorum import standby, verifier
from quorum.cases import ALERTS

_SEATS = ("clerk", "ledger", "archivist", "statute", "prosecutor", "counsel", "prosecutor_rebuttal", "counsel_rebuttal", "magistrate")
_EXPECTED = {
    "HL-4374": ("escalate", "SGD 18,600", ""),
    "HL-4402": ("clear", "", "SGD 27,500"),
    "HL-4418": ("escalate", "SGD 47,800", ""),
    "HL-4390": ("hold", "USD 1,560,000", ""),
    "HL-4381": ("hold", "SGD 14,600", ""),
    "HL-4366": ("split", "SGD 3,200", "SGD 183,200"),
    "HL-4429": ("clear", "", "USD 12,000"),
    "HL-4437": ("escalate", "SGD 24,000", ""),
}


@pytest.mark.parametrize("alert", ALERTS, ids=lambda alert: alert["id"])
def test_every_authored_fact_cites_something_real(alert, tool_context):
    ctx = tool_context(alert["id"])
    standby.run_ledger(alert, ctx)
    standby.run_read_file(ctx)
    standby.run_statute(alert, ctx)
    allowed = verifier.valid_refs(alert, alert["documents"], ctx.evidence())
    for seat in _SEATS:
        brief = standby.brief(alert, seat, ctx.evidence())
        if brief and "facts" in brief:
            kept, struck = verifier.check_facts(brief["facts"], allowed, alert["id"])
            assert not struck, (seat, struck)
            assert not [ref for fact in kept for ref in fact["unknown_refs"]], seat


@pytest.mark.parametrize("alert", ALERTS, ids=lambda alert: alert["id"])
def test_every_standby_verdict_passes_the_verifier(alert, tool_context):
    ctx = tool_context(alert["id"])
    standby.run_ledger(alert, ctx)
    standby.run_read_file(ctx)
    standby.run_statute(alert, ctx)
    result = verifier.verify(alert, standby.brief(alert, "magistrate"), documents=alert["documents"], evidence=ctx.evidence(),
                             tamper_flags=standby.brief(alert, "archivist")["tamper_flags"])
    assert result["passed"], [check for check in result["checks"] if check["status"] == "fail"]
    assert all(check["status"] == "pass" for check in result["checks"]), result["checks"]
    verdict = result["verdict"]
    assert (verdict["disposition"], verdict["held_amount"], verdict["released_amount"]) == _EXPECTED[alert["id"]]


def test_standby_covers_every_outcome():
    assert {expected[0] for expected in _EXPECTED.values()} == {"clear", "hold", "escalate", "split"}


@pytest.mark.parametrize("alert", ALERTS, ids=lambda alert: alert["id"])
def test_authored_translations_keep_fc02(alert):
    note = standby.brief(alert, "liaison")
    if note:
        assert note["language"] == alert["customer"]["language"]
        assert verifier.lint_note(note["english"]) == []


def test_a_generated_alert_gets_a_cautious_hold():
    alert = dict(ALERTS[0], id="HL-9001")
    verdict = standby.brief(alert, "magistrate")
    assert verdict["disposition"] == "hold"
    assert verifier.lint_note(verdict["customer_message"]) == []
