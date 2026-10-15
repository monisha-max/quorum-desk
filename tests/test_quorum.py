from quorum.hearing import parse_json
from quorum.policy import search_policy
from quorum.warehouse import read_ledger


def test_parse_json_strips_fence():
    parsed = parse_json('```json\n{"disposition": "hold"}\n```')
    assert parsed["disposition"] == "hold"


def test_ledger_links_payroll_to_the_live_scam():
    ledger = read_ledger("HL-4366")
    assert ledger["linked_alerts"] == ["HL-4374"]
    assert ledger["features"]["new_or_unrelated_payees"] == ["Kelvin Ong"]


def test_seasonal_remittance_is_under_the_line():
    ledger = read_ledger("HL-4402")
    assert ledger["features"]["splits_just_under_sgd_10000"] == 3


def test_policy_search_finds_the_payroll_rule():
    hits = search_policy("payroll mule credit")
    ids = [item["id"] for item in hits["passages"]]
    assert "FC-40" in ids
