"""The bench clerk who reads the verdict back before anyone signs it.

Gemini decides. This module checks, with no model in the loop:

* every fact cites an id that exists on the file, in policy, or in a tool
  result from this hearing; facts that cite nothing real are struck;
* held and released transactions are real, disjoint, and agree with the
  disposition, and the amounts are counted here rather than by the model;
* the customer note obeys FC-02 and FC-09: no jargon, no tipping off;
* a document that gives the reader instructions blocks a clear (FC-70),
  whether the desk's pattern finds it or the Sentinel quotes it; a Sentinel
  quote counts only if it is found word for word in the document it names;
* a document added to the file cannot clear it unless a model screened it;
* a tool refusal for out-of-scope data is reported as a tamper signal.
"""

from __future__ import annotations

import re
import unicodedata
from copy import deepcopy

from quorum.cases import actionable
from quorum.policy import BY_ID as POLICY_IDS

# FC-02 and FC-09: words a customer note must never carry.
_BANNED = (
    (re.compile(r"\btypolog\w*", re.I), "typology"),
    (re.compile(r"\bSARs?\b"), "SAR"),
    (re.compile(r"\bSTRs?\b"), "STR"),
    (re.compile(r"\bmule\w*", re.I), "mule"),
    (re.compile(r"\bsuspicio\w*", re.I), "suspicious"),
    (re.compile(r"\blaunder\w*", re.I), "laundering"),
    (re.compile(r"\bsanction\w*", re.I), "sanctions"),
    (re.compile(r"\bwatch\s*list\w*", re.I), "watch list"),
    (re.compile(r"\bAML\b"), "AML"),
    (re.compile(r"\bfraudster\w*", re.I), "fraudster"),
    (re.compile(r"\bflagged\b", re.I), "flagged"),
)

# FC-70: phrases that address a reader instead of describing a payment.
_INSTRUCTION = re.compile(
    r"(ignore (all |any |the )?(previous|prior|above) instructions|disregard (the )?(above|previous)|"
    r"(approve|release|clear) (this|the) (payment|invoice|transfer|file)|mark (this|the) (file|case|alert) as|"
    r"you are an? (ai|assistant|model|language model)|as an ai|system prompt|note to (the )?(reviewer|ai|system|model)|"
    r"automated (review|system)s? (should|must)|do not (flag|escalate|hold))",
    re.I,
)

_HOLDING = {"hold", "escalate"}

# A quote this short could be found in almost any document, so finding it proves nothing.
_MIN_QUOTE = 8
_STRAIGHT = str.maketrans({"\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'", "\u2013": "-", "\u2014": "-"})
# Models wrap a quote in quotation marks or end it with a full stop the document may not have there.
_EDGES = " \"'.,;:!?\u3002\u3001\u300c\u300d\u2026"
_MARKS = "\"'\u201c\u201d\u2018\u2019\u300c\u300d"


def lint_note(message: str) -> list[str]:
    """Banned words found in a customer note, in the order FC-02 lists them."""
    return [label for pattern, label in _BANNED if pattern.search(message or "")]


def scan_documents(documents: list[dict]) -> list[dict]:
    """Documents whose text reads as instructions to the reviewer."""
    found = []
    for doc in documents:
        match = _INSTRUCTION.search(doc.get("detail", ""))
        if match:
            found.append({"id": doc["id"], "phrase": match.group(0)})
    return found


def _plain(text: str) -> str:
    """Text as a quote is compared: NFKC, case folded, quotation marks straightened, spaces collapsed."""
    return " ".join(unicodedata.normalize("NFKC", text or "").casefold().translate(_STRAIGHT).split())


def check_quotes(quotes: list[dict], documents: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split the Sentinel's quotes into those found in the document they name and those struck."""
    texts = {doc["id"]: _plain(doc.get("detail", "")) for doc in documents}
    found, struck = [], []
    for item in quotes:
        doc_id = (item.get("document_id") or "").strip()
        quote = _plain(item.get("quote", "")).strip(_EDGES)
        if len(quote.replace(" ", "")) < _MIN_QUOTE:
            struck.append({"id": doc_id, "quote": item.get("quote", ""), "reason": "too short to prove anything"})
        elif quote not in texts.get(doc_id, ""):
            struck.append({"id": doc_id, "quote": item.get("quote", ""),
                           "reason": "not in that document" if doc_id in texts else "no such document"})
        else:
            found.append({"id": doc_id, "phrase": item["quote"].strip().strip(_MARKS).strip()})
    return found, struck


def _planted(quoted: list[dict], scanned: list[dict]) -> list[dict]:
    """One entry per document that reads as an instruction, with what caught it."""
    planted: dict[str, dict] = {}
    for by, items in (("the Sentinel", quoted), ("the pattern", scanned)):
        for item in items:
            entry = planted.setdefault(item["id"], {"id": item["id"], "phrase": item["phrase"], "by": []})
            if by not in entry["by"]:
                entry["by"].append(by)
    return sorted(planted.values(), key=lambda entry: entry["id"])


def _normalise(ref: str, alert_id: str) -> str:
    ref = ref.strip().strip("[]()")
    if ref.startswith(f"{alert_id}:"):
        ref = ref.split(":", 1)[1]
    if re.fullmatch(r"t\d+", ref, re.I):
        ref = ref.upper()
    return ref


def valid_refs(alert: dict, documents: list[dict], evidence: dict[str, dict]) -> set[str]:
    refs = {row["id"] for row in alert["transactions"]}
    refs |= {doc["id"] for doc in documents}
    refs |= set(POLICY_IDS)
    refs |= set(evidence)
    refs |= set(alert.get("links", []))
    # A file the Ledger found paying the same account is evidence too.
    for item in evidence.values():
        refs |= set(item.get("summary", {}).get("open_files_paying_this_account", []))
    return refs


def _money(rows: list[dict]) -> str:
    by_currency: dict[str, float] = {}
    for row in rows:
        by_currency[row["currency"]] = by_currency.get(row["currency"], 0) + row["amount"]
    return ", ".join(f"{currency} {amount:,.0f}" for currency, amount in by_currency.items())


def check_facts(facts: list[dict], allowed: set[str], alert_id: str) -> tuple[list[dict], list[dict]]:
    """Split facts into those with at least one real ref and those struck."""
    kept, struck = [], []
    for fact in facts or []:
        refs = [_normalise(ref, alert_id) for ref in fact.get("refs", [])]
        good = [ref for ref in refs if ref in allowed]
        bad = [ref for ref in refs if ref not in allowed]
        if good:
            kept.append({"claim": fact.get("claim", ""), "refs": good, "unknown_refs": bad})
        else:
            struck.append({"claim": fact.get("claim", ""), "refs": refs, "reason": "cites nothing on the file" if refs else "cites no evidence"})
    return kept, struck


def verify(
    alert: dict,
    verdict: dict,
    *,
    documents: list[dict],
    evidence: dict[str, dict],
    tamper_flags: list[str] | None = None,
    scope_attempts: list[dict] | None = None,
    quotes: list[dict] | None = None,
) -> dict:
    """Return the verdict as it may be signed, plus every check and what it changed.

    `quotes` is what the Sentinel reported, or None when no model screened the documents.
    """
    out = deepcopy(verdict)
    checks: list[dict] = []
    allowed = valid_refs(alert, documents, evidence)

    kept, struck = check_facts(out.get("facts", []), allowed, alert["id"])
    out["facts"] = kept
    checks.append({
        "id": "citations",
        "label": "Every fact cites the file",
        "status": "pass" if not struck else "fixed",
        "detail": f"{len(kept)} facts stand" + (f", {len(struck)} struck" if struck else ""),
    })
    cited_policy = any(ref in POLICY_IDS for fact in kept for ref in fact["refs"])
    cited_record = any(ref not in POLICY_IDS for fact in kept for ref in fact["refs"])
    checks.append({
        "id": "grounds",
        "label": "Rests on a record and a policy",
        "status": "pass" if cited_policy and cited_record else "fail",
        "detail": ("policy and record both cited" if cited_policy and cited_record
                   else "missing a policy citation" if cited_record else "missing a record citation"),
    })

    # Money: the model chooses transactions, the code counts them.
    open_rows = actionable(alert)
    open_ids = {row["id"] for row in open_rows}
    held = [_normalise(ref, alert["id"]) for ref in out.get("held_txn_ids", [])]
    released = [_normalise(ref, alert["id"]) for ref in out.get("released_txn_ids", [])]
    unknown = sorted({ref for ref in held + released if ref not in open_ids})
    held = [ref for ref in dict.fromkeys(held) if ref in open_ids]
    released = [ref for ref in dict.fromkeys(released) if ref in open_ids and ref not in held]
    disposition = out.get("disposition")
    fixes = []
    if unknown:
        fixes.append(f"dropped ids not open on the file: {', '.join(unknown)}")
    if disposition == "clear":
        if held:
            fixes.append("a clear holds nothing")
        held, released = [], [row["id"] for row in open_rows]
    elif disposition in _HOLDING:
        missing = [row["id"] for row in open_rows if row["id"] not in held and row["id"] not in released]
        if missing:
            held.extend(missing)
            fixes.append(f"held unassigned {', '.join(missing)}")
    elif disposition == "split":
        missing = [row["id"] for row in open_rows if row["id"] not in held and row["id"] not in released]
        if missing:
            held.extend(missing)
            fixes.append(f"held unassigned {', '.join(missing)}")
        if not held or not released:
            fixes.append("a split needs both a held and a released part")
    by_id = {row["id"]: row for row in open_rows}
    out["held_txn_ids"] = held
    out["released_txn_ids"] = released
    out["held_amount"] = _money([by_id[ref] for ref in held])
    out["released_amount"] = _money([by_id[ref] for ref in released])
    split_broken = disposition == "split" and (not held or not released)
    checks.append({
        "id": "money",
        "label": "Held and released add up",
        "status": "fail" if split_broken else "fixed" if fixes else "pass",
        "detail": "; ".join(fixes) or f"held {out['held_amount'] or 'nothing'}, released {out['released_amount'] or 'nothing'}",
    })

    if out.get("false_positive") and disposition != "clear":
        out["false_positive"] = False
        checks.append({"id": "false_positive", "label": "False positive only on a clear", "status": "fixed",
                       "detail": "a held file is not a false positive"})
    if disposition == "clear" and out.get("sar_draft"):
        out["sar_draft"] = ""
        checks.append({"id": "sar", "label": "No report on a clear", "status": "fixed", "detail": "draft removed"})
    elif disposition == "escalate" and not (out.get("sar_draft") or "").strip():
        checks.append({"id": "sar", "label": "Escalation carries a draft", "status": "fail", "detail": "no draft for the reporting officer"})
    else:
        checks.append({"id": "sar", "label": "Report matches the disposition", "status": "pass",
                       "detail": "draft attached" if disposition == "escalate" else "no report needed"})

    overturned = None
    scanned = scan_documents(documents)
    quoted, unproven = check_quotes(quotes or [], documents)
    planted = _planted(quoted, scanned)
    planted_ids = [item["id"] for item in planted]
    # Anyone at the desk can add an upload; a file's own documents are fixed and were written with it.
    # An upload is where wording nobody foresaw arrives, so a model must have screened it before the
    # file can clear. The pattern alone is not enough.
    unscreened = [doc["id"] for doc in documents if doc.get("uploaded") and doc["id"] not in planted_ids] if quotes is None else []
    flagged = sorted(set(tamper_flags or []) | set(planted_ids) | set(unscreened))
    # Only what actually blocks the file is named here; the Archivist's other flags (an altered photo,
    # say) are for the officer to read, not the reason to hold.
    reasons = []
    if planted_ids:
        reasons.append(f"{', '.join(planted_ids)} {'read' if len(planted_ids) > 1 else 'reads'} as an instruction to the desk")
    if unscreened:
        many = len(unscreened) > 1
        reasons.append(f"{', '.join(unscreened)} {'were' if many else 'was'} added to the file and no model screened {'them' if many else 'it'}")
    if scope_attempts:
        reasons.append(f"a seat asked for {', '.join(sorted({item['asked'] for item in scope_attempts}))}, which is outside this file")
    how = [f"{item['id']} caught by {' and '.join(item['by'])}" for item in planted]
    if unproven:
        how.append(f"{len(unproven)} Sentinel {'quote' if len(unproven) == 1 else 'quotes'} not found in the document named, ignored")
    if quotes is None:
        how.append("the Sentinel did not sit, so only the pattern read the documents")
    if reasons and disposition in {"clear", "split"}:
        reason = " and ".join(reasons) + " (FC-70)"
        out["disposition"] = "hold"
        out["held_txn_ids"] = [row["id"] for row in open_rows]
        out["released_txn_ids"] = []
        out["held_amount"] = _money(open_rows)
        out["released_amount"] = ""
        out["false_positive"] = False
        # The model's note described the payment it meant to release; the customer must hear what actually happened.
        out["customer_message"] = safe_note(alert, "hold")
        # The typology and next step described the release; the rationale stays as the Magistrate wrote it.
        out["typology"] = ("Instruction planted in a document (FC-70)" if planted
                           else "Added document not screened (FC-70)" if unscreened
                           else "Tool request outside the file (FC-70)")
        out["next_step"] = (f"Keep {out['held_amount'] or 'the payment'} held. An officer reads "
                            f"{', '.join(flagged) or 'the tool log'} and confirms the payment with the customer "
                            "on their registered number before anything is released.")
        overturned = {"from": disposition, "to": "hold", "reason": reason}
        # The money check counted the model's release; the record must not say so beside a hold.
        money_check = next(check for check in checks if check["id"] == "money")
        money_check["detail"] = f"held {out['held_amount'] or 'nothing'}, released nothing once overturned"
        detail = f"{disposition} overturned to hold: {reason}"
    elif reasons:
        detail = f"{' and '.join(reasons)}; the {disposition} keeps the money held"
    elif tamper_flags:
        detail = f"no document addresses the reviewer; the Archivist's flags on {', '.join(sorted(set(tamper_flags)))} are for the officer"
    else:
        detail = "no document addresses the reviewer"
    checks.append({
        "id": "fc70",
        "label": "No instruction in a document decides the file",
        "status": "fixed" if reasons else "pass",
        "detail": "; ".join([detail, *how]),
    })
    # Linted after FC-70, which may have rewritten the note.
    banned = lint_note(out.get("customer_message", ""))
    checks.append({
        "id": "fc02",
        "label": "Customer note follows FC-02 and FC-09",
        "status": "pass" if not banned else "fail",
        "detail": "plain and discreet" if not banned else f"uses {', '.join(banned)}",
    })

    if scope_attempts:
        checks.append({"id": "scope", "label": "Tools stayed on this file", "status": "fail",
                       "detail": "refused: " + ", ".join(sorted({item["asked"] for item in scope_attempts}))})

    penalty = 0.08 * len(struck) + (0.1 if planted else 0)
    confidence = max(0.3, min(0.99, float(out.get("confidence", 0.5)) - penalty))
    out["confidence"] = round(confidence, 2)
    return {
        "verdict": out,
        "checks": checks,
        "struck": struck,
        "tamper": planted,
        "unscreened": unscreened,
        "unproven": unproven,
        "lint": banned,
        "overturned": overturned,
        "passed": all(item["status"] != "fail" for item in checks),
    }


_TEMPLATES = {
    "clear": "Your payment{party} has been released after a routine check. Nothing more is needed. If you have questions, call the number on the back of your card.",
    "hold": "We have paused your payment{party} while a person on our team checks it. Harbourline will never ask you to move money to a safe account or to keep anything from us. Please call the number on the back of your card.",
    "escalate": "We have paused your payment{party} while a person on our team reviews it. You do not need to do anything now. Please call the number on the back of your card if you would like to speak to someone.",
    "split": "Part of your payment run has been released. We are holding the rest while a person on our team checks it. Please call your relationship manager or the number on the back of your card.",
}


def safe_note(alert: dict, disposition: str) -> str:
    """A note that always passes FC-02 and states nothing the file does not."""
    rows = actionable(alert)
    outs = sorted({row["counterparty"] for row in rows if row["direction"] == "out"})
    ins = sorted({row["counterparty"] for row in rows if row["direction"] == "in"})
    party = f" to {outs[0]}" if len(outs) == 1 and not ins else f" from {ins[0]}" if len(ins) == 1 and not outs else ""
    return _TEMPLATES.get(disposition, _TEMPLATES["hold"]).format(party=party)
