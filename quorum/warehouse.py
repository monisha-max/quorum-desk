"""The same features a BigQuery mart would hand the Ledger seat.

sql/features.sql is the warehouse query. This module is the prototype mart:
it runs that logic in process so a demo does not depend on a loaded dataset.
"""

from __future__ import annotations

from quorum.cases import get_alert

EXTRA_DOCUMENTS: dict[str, list[dict]] = {}


def read_ledger(alert_id: str) -> dict:
    """Read the transaction mart for one alert, including derived features.

    Args:
        alert_id: Harbourline alert id, for example HL-4374.

    Returns:
        Payments, counterparties, and the features used in the hearing.
    """
    alert = get_alert(alert_id)
    if alert is None:
        return {"error": f"No alert {alert_id}"}
    payments = alert["transactions"]
    amounts = [row["amount"] for row in payments]
    new_payees = [
        party["name"]
        for party in alert["counterparties"]
        if party.get("relationship_on_file") in {None, "none", "first invoice", "not on prior payroll"}
    ]
    just_under = [
        row for row in payments
        if row["currency"] == "SGD" and 8000 <= row["amount"] < 10000
    ]
    return {
        "alert_id": alert_id,
        "customer": alert["customer"]["name"],
        "product": alert["product"],
        "currency": alert["currency"],
        "payments": payments,
        "payment_count": len(payments),
        "total_amount": sum(amounts),
        "history": alert["history"],
        "counterparties": alert["counterparties"],
        "linked_alerts": alert["links"],
        "features": {
            "new_or_unrelated_payees": new_payees,
            "splits_just_under_sgd_10000": len(just_under),
            "live_window": alert["urgency"] == "live",
        },
    }


def read_file(alert_id: str) -> dict:
    """Read KYC notes and documents on the alert, plus anything the officer added.

    Args:
        alert_id: Harbourline alert id.

    Returns:
        The customer profile and the document list.
    """
    alert = get_alert(alert_id)
    if alert is None:
        return {"error": f"No alert {alert_id}"}
    documents = list(alert["documents"])
    for item in EXTRA_DOCUMENTS.get(alert_id, []):
        documents.append(item)
    return {
        "alert_id": alert_id,
        "customer": alert["customer"],
        "summary": alert["summary"],
        "documents": documents,
        "links": alert["links"],
    }
