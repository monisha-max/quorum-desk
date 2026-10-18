"""What each seat is shown. Separation of duties is enforced here, by omission.

The Clerk sees the alert. The Ledger sees payments and counterparties, never
document text. The Archivist sees only the customer and the question; it reads
documents through its own tool. The Sentinel sees the document texts and
nothing else, and what it reports goes to the verifier, not the bench. The
advocates and the Magistrate see the findings and the evidence board, which
carries tool results, not raw documents.
"""

from __future__ import annotations

import json

from quorum.cases import actionable


def _dump(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=1)


def _payments(alert: dict) -> list[dict]:
    return [
        {key: row.get(key) for key in ("id", "ts", "direction", "amount", "currency", "counterparty", "account", "narrative")}
        | {"state": row.get("state", "pending")}
        for row in alert["transactions"]
    ]


def _customer(alert: dict) -> dict:
    keep = ("id", "name", "segment", "age", "city", "tenure_years", "occupation", "language")
    return {key: alert["customer"].get(key) for key in keep}


def clerk(alert: dict, documents: list[dict]) -> str:
    return "\n".join([
        f"ALERT {alert['id']} opened {alert['opened']} ({alert['urgency']})",
        f"Product: {alert['product']}. Rule that fired: {alert['rule']}.",
        f"Monitoring summary: {alert['summary']}",
        "Customer:", _dump(_customer(alert)),
        "Transactions:", _dump(_payments(alert)),
        "Documents on file (ids and kinds only): " + ", ".join(f"{doc['id']} ({doc['kind']})" for doc in documents),
    ])


def _question(clerk_out: dict) -> str:
    return f"The clerk's question: {clerk_out.get('question', '')}\nWatch for: {'; '.join(clerk_out.get('watch_for', []))}"


def ledger(alert: dict, clerk_out: dict) -> str:
    return "\n".join([
        f"FILE {alert['id']}. Customer id {alert['customer']['id']} ({alert['customer']['segment']}). Rule: {alert['rule']}.",
        _question(clerk_out),
        "Transactions:", _dump(_payments(alert)),
        "Counterparties:", _dump(alert["counterparties"]),
        "Linked files: " + (", ".join(alert.get("links", [])) or "none"),
    ])


def archivist(alert: dict, clerk_out: dict) -> str:
    return "\n".join([
        f"FILE {alert['id']}. Rule: {alert['rule']}.",
        _question(clerk_out),
        "Customer:", _dump(_customer(alert)),
        "Call read_file to see the documents.",
    ])


def statute(alert: dict, clerk_out: dict) -> str:
    return "\n".join([
        f"FILE {alert['id']}. Product: {alert['product']}. Rule: {alert['rule']}.",
        f"Clerk's summary: {clerk_out.get('summary', '')}",
        _question(clerk_out),
        f"Customer age: {alert['customer'].get('age') or 'not a person'}. Segment: {alert['customer']['segment']}.",
    ])


def sentinel(alert: dict, documents: list[dict]) -> str:
    lines = [f"FILE {alert['id']}. {len(documents)} documents, each between its own markers."]
    for doc in documents:
        lines += [f"[{doc['id']} begins; kind: {doc['kind']}]", doc.get("detail", ""), f"[{doc['id']} ends]"]
    return "\n".join(lines)


def board(evidence: dict[str, dict]) -> list[dict]:
    """The evidence board: every tool result this hearing produced, by ref."""
    items = []
    for ref, item in sorted(evidence.items()):
        if item.get("tool") == "read_file" and not ref.startswith("file:"):
            continue
        items.append({"ref": ref, "tool": item.get("tool"), "summary": item.get("summary", {})})
    return items


def _findings(seats: dict[str, dict]) -> dict:
    keep = {}
    for name in ("ledger", "archivist", "statute"):
        out = seats.get(name, {}).get("out") or {}
        keep[name] = {key: out.get(key) for key in ("finding", "facts", "leans", "tamper_flags", "policy_ids") if key in out}
    return keep


def _open(alert: dict) -> list[dict]:
    return [{key: row[key] for key in ("id", "direction", "amount", "currency", "counterparty", "account")} for row in actionable(alert)]


def advocate(alert: dict, seats: dict[str, dict], evidence_board: list[dict]) -> str:
    return "\n".join([
        f"FILE {alert['id']}. Rule: {alert['rule']}. Customer: {alert['customer']['name']}, {alert['customer']['segment']}, age {alert['customer'].get('age') or 'n/a'}.",
        f"Clerk: {seats['clerk']['out'].get('summary', '')} {seats['clerk']['out'].get('question', '')}",
        "Open transactions the desk can still hold or release:", _dump(_open(alert)),
        "Seat findings:", _dump(_findings(seats)),
        "Evidence board (tool results by ref):", _dump(evidence_board),
    ])


def rebuttal(alert: dict, side: str, seats: dict[str, dict]) -> str:
    other = "counsel" if side == "prosecutor" else "prosecutor"
    return "\n".join([
        f"FILE {alert['id']}. Rule: {alert['rule']}.",
        f"Your opening ({side}):", _dump(seats[side]["out"]),
        f"The other side's opening ({other}):", _dump(seats[other]["out"]),
    ])


def magistrate(alert: dict, seats: dict[str, dict], evidence_board: list[dict], contested: bool) -> str:
    lines = [
        advocate(alert, seats, evidence_board),
        "Prosecutor's opening:", _dump(seats["prosecutor"]["out"]),
        "Counsel's opening:", _dump(seats["counsel"]["out"]),
    ]
    if contested:
        for name in ("prosecutor_rebuttal", "counsel_rebuttal"):
            if name in seats:
                lines += [f"{name.replace('_', ' ').capitalize()}:", _dump(seats[name]["out"])]
    else:
        lines.append("Both sides opened on the same position; there were no rebuttals.")
    return "\n".join(lines)


def liaison(alert: dict, verdict: dict, rewrite: list[str]) -> str:
    customer = alert["customer"]
    lines = [
        f"FILE {alert['id']}.",
        f"Customer: {customer['name']}, age {customer.get('age') or 'n/a'}, preferred language {customer.get('language', 'en')}.",
        f"Disposition: {verdict['disposition']}.",
        "Approved English note:", verdict.get("customer_message", ""),
    ]
    if rewrite:
        lines.append(f"The approved note used words FC-02 forbids ({', '.join(rewrite)}). Rewrite it without them, keeping its facts.")
    return "\n".join(lines)
