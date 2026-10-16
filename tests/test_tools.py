"""The Ledger, Archivist and Statute tools, against the synthetic warehouse."""

from quorum import warehouse
from quorum.cases import actionable, get_alert
from quorum.policy import search_policy


def test_mule_account_links_the_payroll_file_to_the_scam(tool_context):
    ctx = tool_context("HL-4366")
    summary = warehouse.counterparty_fan_in("041-883921", tool_context=ctx)["summary"]
    assert summary["holder"] == "Kelvin Ong"
    assert summary["opened_days_before_alert"] == 6
    assert summary["open_files_paying_this_account"] == ["HL-4374"]
    assert summary["left_within_an_hour_share"] == 1.0
    assert "fan_in:041-883921" in ctx.evidence()


def test_scam_victim_pays_the_same_fresh_account(tool_context):
    summary = warehouse.counterparty_fan_in("041-883921", tool_context=tool_context("HL-4374"))["summary"]
    assert "HL-4366" in summary["open_files_paying_this_account"]
    assert summary["balance_now"] == 410


def test_seasonal_remittance_is_split_under_the_line_and_seasonal(tool_context):
    rows = actionable(get_alert("HL-4402"))
    assert len(rows) == 3 and all(row["amount"] < 10_000 for row in rows)
    assert sum(row["amount"] for row in rows) == 27_500
    peers = warehouse.peer_percentile("C-10388", tool_context=tool_context("HL-4402"))["summary"]
    assert peers["of_which_this_alert"] == 27_500
    assert peers["this_month_vs_average_month"] < 3


def test_beneficiary_history_shows_years_of_payments(tool_context):
    summary = warehouse.beneficiary_history("C-10388", "KUB 0044192", tool_context=tool_context("HL-4402"))["summary"]
    assert summary["first_payment_month"] == "2022-03" and summary["months_with_payments"] == 55
    assert summary["months_customer_sends_more"] == {"10": [1900.0, 2000.0, 2100.0, 2200.0]}


def test_ledger_refuses_accounts_off_the_file(tool_context):
    ctx = tool_context("HL-4402")
    result = warehouse.counterparty_fan_in("999-000000", tool_context=ctx)
    assert result["error"] == "out_of_scope"
    assert "scope:counterparty_fan_in:999-000000" in ctx.state
    assert not ctx.evidence()


def test_tool_results_carry_the_sql_they_ran(tool_context):
    result = warehouse.customer_baseline("C-10021", tool_context=tool_context("HL-4374"))
    assert result["queries"] and all("SELECT" in query["sql"] for query in result["queries"])
    assert result["engine"] == "sqlite mirror"


def test_read_file_includes_uploads(tool_context):
    warehouse.UPLOADED["HL-4429"] = [{"id": "up-1", "kind": "invoice", "detail": "Invoice 77."}]
    ctx = tool_context("HL-4429")
    result = warehouse.read_file(tool_context=ctx)
    assert "up-1" in [doc["id"] for doc in result["documents"]]
    assert "up-1" in ctx.evidence()


def test_policy_search_finds_the_payroll_rule():
    ids = [item["id"] for item in search_policy("payroll mule credit")["passages"]]
    assert "FC-40" in ids
