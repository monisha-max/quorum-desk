"""Harbourline policy excerpts the Statute seat is allowed to cite.

Production retrieval would be Vertex AI Search over the full policy library.
This corpus is the governed slice the prototype is permitted to quote.
"""

POLICIES = [
    {
        "id": "FC-14",
        "title": "Structuring versus seasonal family support",
        "text": (
            "Splits that sit just under a reporting threshold are not structuring "
            "by themselves. Release when the beneficiary has a multi-year history, "
            "the narrative names a known family event or medical bill, and the "
            "customer's income source can carry the amount. Escalate when the "
            "beneficiary is new, the narrative is empty, or the splits have no "
            "seasonal explanation."
        ),
    },
    {
        "id": "FC-22",
        "title": "Romance and authorised push-payment scams",
        "text": (
            "Hold funds still in the bank when a customer is moving savings to a "
            "new payee after a short online relationship, or when a script tells "
            "them not to speak to the bank. Never accuse the customer. The "
            "customer message must say Harbourline will not ask them to move money "
            "to a safe account, and must give the number on the back of the card. "
            "File a suspicious matter when the payee account was opened within "
            "30 days or has already received funds from other victims."
        ),
    },
    {
        "id": "FC-31",
        "title": "Trade misinvoicing",
        "text": (
            "Hold a trade payment when the invoice unit price differs from the "
            "observed market band for that commodity by more than 15 percent, "
            "or when the beneficiary or its bank changed on this invoice and the "
            "buyer was incorporated within 90 days. Weight on the bill of lading "
            "must be consistent with the invoiced quantity."
        ),
    },
    {
        "id": "INS-07",
        "title": "Claim document integrity",
        "text": (
            "Refer a claim to investigation when two repair invoices share line "
            "items and near-sequential numbers, when image circumstances contradict "
            "the stated time of loss, or when a prior claim overlaps the same "
            "damage. Do not deny the claim in the customer message. Say it is with "
            "a reviewer and name the claim number."
        ),
    },
    {
        "id": "FC-40",
        "title": "Payroll with one tainted credit",
        "text": (
            "Do not hold an entire payroll because one credit matches a mule or "
            "a scam beneficiary. Release the credits that match the prior payroll "
            "file. Hold only the matched credit and link the case to the open scam."
        ),
    },
    {
        "id": "FC-02",
        "title": "How to write to a customer",
        "text": (
            "Use plain sentences. Name the payment. Say what we did and why, "
            "without the words typology, SAR, mule, or suspicious. Offer a person. "
            "Do not invent a fact that is not in the file."
        ),
    },
]


def search_policy(query: str) -> dict:
    """Search Harbourline policy for passages relevant to a case question.

    Args:
        query: Words from the alert, such as remittance, invoice, scam, or payroll.

    Returns:
        The top matching policy passages the Statute seat may cite.
    """
    tokens = {t.lower() for t in query.replace("/", " ").split() if len(t) > 2}
    scored = []
    for policy in POLICIES:
        hay = f"{policy['title']} {policy['text']}".lower()
        score = sum(1 for token in tokens if token in hay)
        scored.append((score, policy))
    scored.sort(key=lambda item: item[0], reverse=True)
    hits = [policy for score, policy in scored if score > 0][:3]
    if not hits:
        hits = POLICIES[:2]
    return {"query": query, "passages": hits}
