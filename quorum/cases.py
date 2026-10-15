"""Synthetic Harbourline files. Public, invented, and safe to show a judge.

Nothing here is a real customer. The shapes match the cases a night desk
actually argues: a live push-payment scam, a seasonal remittance that looks
like structuring, a mispriced metal invoice, a claim with twin invoices,
and a payroll that shares an account with the scam.
"""

from __future__ import annotations

ALERTS: list[dict] = [
    {
        "id": "HL-4374",
        "opened": "2026-10-15T22:41:00+08:00",
        "urgency": "live",
        "customer": {
            "name": "Priya Nair",
            "segment": "Everyday",
            "age": 34,
            "city": "Singapore",
            "tenure_years": 6,
            "occupation": "School administrator",
        },
        "product": "Payments",
        "amount": 18600,
        "currency": "SGD",
        "rule": "New payee, three transfers in nine minutes",
        "summary": (
            "Priya started a transfer while on a call. The payee account was "
            "opened six days ago and has already taken money from four other "
            "Harbourline customers today. A note she typed into the payment "
            "says she was told not to tell the bank."
        ),
        "transactions": [
            {"at": "22:32", "direction": "out", "amount": 200, "currency": "SGD", "counterparty": "Kelvin Ong", "account": "041-883921", "narrative": "test"},
            {"at": "22:36", "direction": "out", "amount": 8400, "currency": "SGD", "counterparty": "Kelvin Ong", "account": "041-883921", "narrative": "safe account do not reverse"},
            {"at": "22:40", "direction": "out", "amount": 10000, "currency": "SGD", "counterparty": "Kelvin Ong", "account": "041-883921", "narrative": "as instructed on the phone"},
        ],
        "history": [
            {"month": "2026-09", "typical_out": 2400, "new_payees": 0},
            {"month": "2026-08", "typical_out": 2100, "new_payees": 1},
        ],
        "counterparties": [
            {
                "name": "Kelvin Ong",
                "account": "041-883921",
                "opened_days_ago": 6,
                "relationship_on_file": "none",
                "other_customers_today": 4,
                "salary_credits": 0,
            }
        ],
        "documents": [
            {"id": "note-1", "kind": "payment note", "detail": "Customer typed: they said do not tell the bank, this is the secure account."},
            {"id": "kyc-1", "kind": "KYC", "detail": "Priya Nair, enhanced due diligence not required, address unchanged since 2021, no prior scam report."},
        ],
        "links": [],
    },
    {
        "id": "HL-4402",
        "opened": "2026-10-15T16:05:00+08:00",
        "urgency": "queue",
        "customer": {
            "name": "Pemba Sherpa",
            "segment": "Everyday",
            "age": 41,
            "city": "Singapore",
            "tenure_years": 9,
            "occupation": "Site supervisor, Keong Construction",
        },
        "product": "Remittance",
        "amount": 27500,
        "currency": "SGD",
        "rule": "Three credits just under the internal SGD 10,000 threshold",
        "summary": (
            "Pemba has sent about SGD 800 a month to his sister in Kathmandu "
            "for four years. This week he sent three larger transfers on "
            "consecutive days, each under SGD 10,000. The narratives mention "
            "Dashain and a surgery at Bir Hospital."
        ),
        "transactions": [
            {"at": "13 Oct", "direction": "out", "amount": 9500, "currency": "SGD", "counterparty": "Anita Sherpa", "account": "Nabil 0044192", "narrative": "Dashain and Anita surgery Bir Hospital"},
            {"at": "14 Oct", "direction": "out", "amount": 9200, "currency": "SGD", "counterparty": "Anita Sherpa", "account": "Nabil 0044192", "narrative": "hospital balance Bir"},
            {"at": "15 Oct", "direction": "out", "amount": 8800, "currency": "SGD", "counterparty": "Anita Sherpa", "account": "Nabil 0044192", "narrative": "Dashain family"},
        ],
        "history": [
            {"month": "2026-09", "typical_out": 800, "new_payees": 0},
            {"month": "2025-10", "typical_out": 2200, "new_payees": 0},
        ],
        "counterparties": [
            {
                "name": "Anita Sherpa",
                "account": "Nabil 0044192",
                "opened_days_ago": None,
                "relationship_on_file": "sister, beneficiary since March 2022",
                "other_customers_today": 0,
                "salary_credits": None,
            }
        ],
        "documents": [
            {"id": "emp-1", "kind": "employer letter", "detail": "Keong Construction, 12 Sep 2026: Pemba Sherpa promoted to site supervisor, monthly salary SGD 4,800."},
            {"id": "kyc-2", "kind": "KYC", "detail": "Sister Anita Sherpa recorded as family beneficiary since 2022. Prior Dashain transfers in Oct 2024 and Oct 2025 were larger than his monthly average and were completed."},
        ],
        "links": [],
    },
    {
        "id": "HL-4418",
        "opened": "2026-10-15T11:20:00+08:00",
        "urgency": "queue",
        "customer": {
            "name": "Meera Iyer",
            "segment": "Priority",
            "age": 67,
            "city": "Singapore",
            "tenure_years": 11,
            "occupation": "Retired teacher",
        },
        "product": "Savings",
        "amount": 48200,
        "currency": "SGD",
        "rule": "Pension customer, rapid outward to new payees",
        "summary": (
            "Meera's pension credit is SGD 3,200 a month. In two days she sent "
            "most of her savings to a payee she added yesterday, then onward "
            "toward a Manila cash outlet and a Philippine e-wallet. She told "
            "the call centre a friend is helping her invest."
        ),
        "transactions": [
            {"at": "14 Oct 19:10", "direction": "in", "amount": 500, "currency": "SGD", "counterparty": "Jonathan Wei", "account": "DBS 2291", "narrative": "for the tickets my love"},
            {"at": "15 Oct 09:02", "direction": "out", "amount": 19800, "currency": "SGD", "counterparty": "Jonathan Wei", "account": "DBS 2291", "narrative": "investment tranche"},
            {"at": "15 Oct 09:40", "direction": "out", "amount": 18400, "currency": "SGD", "counterparty": "M Lhuillier Manila", "account": "cash-4401", "narrative": "collection"},
            {"at": "15 Oct 10:05", "direction": "out", "amount": 9600, "currency": "SGD", "counterparty": "QuickWallet PH", "account": "wallet-88", "narrative": "top up"},
        ],
        "history": [
            {"month": "2026-09", "typical_out": 1900, "new_payees": 0},
            {"month": "2026-08", "typical_out": 1700, "new_payees": 0},
        ],
        "counterparties": [
            {"name": "Jonathan Wei", "account": "DBS 2291", "opened_days_ago": 1, "relationship_on_file": "none", "other_customers_today": 0, "salary_credits": None},
            {"name": "M Lhuillier Manila", "account": "cash-4401", "opened_days_ago": 1, "relationship_on_file": "none", "other_customers_today": 2, "salary_credits": None},
        ],
        "documents": [
            {"id": "call-1", "kind": "call note", "detail": "15 Oct 10:22. Meera said Jonathan is a friend she met online in August and he is helping her invest. She did not want a branch appointment."},
            {"id": "kyc-3", "kind": "KYC", "detail": "Priority customer since 2015. No previous investment payees. Savings balance before these payments was SGD 61,400."},
        ],
        "links": [],
    },
    {
        "id": "HL-4390",
        "opened": "2026-10-14T18:12:00+08:00",
        "urgency": "queue",
        "customer": {
            "name": "Northspan Metals Pte Ltd",
            "segment": "Trade",
            "age": None,
            "city": "Singapore",
            "tenure_years": 7,
            "occupation": "Non-ferrous metal trader",
        },
        "product": "Trade payment",
        "amount": 1240000,
        "currency": "USD",
        "rule": "Invoice unit price outside the commodity band",
        "summary": (
            "Northspan asked Harbourline to pay invoice INV-8841 for 400 metric "
            "tons of copper cathode at USD 1,240,000. The bank's commodity band "
            "for cathode this week is USD 1,800 to 2,100 per ton. The bill of "
            "lading shows 398 tons. The buyer was incorporated in Labuan 42 days "
            "ago, and the beneficiary bank changed on this invoice."
        ),
        "transactions": [
            {"at": "14 Oct", "direction": "out", "amount": 1240000, "currency": "USD", "counterparty": "Kinabalu Commercials", "account": "Labuan 7712", "narrative": "INV-8841 copper cathode 400 MT"},
        ],
        "history": [
            {"month": "2026-07", "typical_out": 810000, "new_payees": 0},
            {"month": "2026-04", "typical_out": 760000, "new_payees": 0},
        ],
        "counterparties": [
            {
                "name": "Kinabalu Commercials",
                "account": "Labuan 7712",
                "opened_days_ago": 42,
                "relationship_on_file": "first invoice",
                "other_customers_today": 0,
                "salary_credits": None,
            }
        ],
        "documents": [
            {"id": "inv-8841", "kind": "invoice", "detail": "INV-8841. 400 MT copper cathode. USD 1,240,000. Unit price USD 3,100 per MT. Beneficiary bank changed from the prior Andes Refining invoices."},
            {"id": "bl-19", "kind": "bill of lading", "detail": "BL-19. Weight 398 MT. Port of loading Callao. Consignee Kinabalu Commercials, Labuan, incorporated 3 Sep 2026."},
            {"id": "band-1", "kind": "market band", "detail": "Harbourline commodity desk, week of 13 Oct 2026: copper cathode USD 1,800 to 2,100 per MT. Prior six Northspan invoices were within 8 percent of the band."},
        ],
        "links": [],
    },
    {
        "id": "HL-4381",
        "opened": "2026-10-14T09:48:00+08:00",
        "urgency": "queue",
        "customer": {
            "name": "Arun Dela Cruz",
            "segment": "Insurance",
            "age": 38,
            "city": "Manila",
            "tenure_years": 3,
            "occupation": "Fleet coordinator",
        },
        "product": "Motor claim",
        "amount": 14600,
        "currency": "SGD",
        "rule": "Two workshops, overlapping damage, contradictory scene",
        "summary": (
            "Arun filed motor claim MC-22911 for a night collision on the PIE "
            "in heavy rain. Two garages submitted invoices with the same line "
            "items and numbers one apart. A March claim already covered the "
            "bumper. The photograph attached as the night scene has hard "
            "afternoon shadows."
        ),
        "transactions": [
            {"at": "claim", "direction": "out", "amount": 14600, "currency": "SGD", "counterparty": "Reserve for MC-22911", "account": "claims", "narrative": "requested settlement"},
        ],
        "history": [
            {"month": "2026-03", "typical_out": 6200, "new_payees": 0},
        ],
        "counterparties": [
            {"name": "Jurong Auto Works", "account": "inv 55018", "opened_days_ago": None, "relationship_on_file": "repairer", "other_customers_today": 0, "salary_credits": None},
            {"name": "Westlane Motors", "account": "inv 55019", "opened_days_ago": None, "relationship_on_file": "repairer", "other_customers_today": 1, "salary_credits": None},
        ],
        "documents": [
            {"id": "inv-a", "kind": "invoice", "detail": "Jurong Auto Works 55018: bumper, left lamp, labour. SGD 14,600."},
            {"id": "inv-b", "kind": "invoice", "detail": "Westlane Motors 55019: same three lines, same amounts, invoice number is the next integer."},
            {"id": "photo-1", "kind": "scene photo", "detail": "Described on the claim as 23:40 in rain. Assessor note: short hard shadows and a dry road, consistent with mid-afternoon."},
            {"id": "prior", "kind": "prior claim", "detail": "MC-19002 in March 2026 paid SGD 6,200 for the same bumper on the same plate."},
        ],
        "links": [],
    },
    {
        "id": "HL-4366",
        "opened": "2026-10-15T21:10:00+08:00",
        "urgency": "queue",
        "customer": {
            "name": "Lumen Studio Pte Ltd",
            "segment": "Business",
            "age": None,
            "city": "Singapore",
            "tenure_years": 5,
            "occupation": "Design studio, 42 staff",
        },
        "product": "Payroll",
        "amount": 186400,
        "currency": "SGD",
        "rule": "One new payroll credit matches an open scam beneficiary",
        "summary": (
            "Lumen's monthly payroll is 42 credits. Forty-one match last month "
            "within ordinary variance. One new joiner credit of SGD 3,200 goes "
            "to account 041-883921, the same account Priya Nair was told to use "
            "as a safe account in HL-4374."
        ),
        "transactions": [
            {"at": "21:05", "direction": "out", "amount": 183200, "currency": "SGD", "counterparty": "41 known staff", "account": "payroll file", "narrative": "October salaries, matches September file"},
            {"at": "21:05", "direction": "out", "amount": 3200, "currency": "SGD", "counterparty": "Kelvin Ong", "account": "041-883921", "narrative": "new joiner, added today"},
        ],
        "history": [
            {"month": "2026-09", "typical_out": 181900, "new_payees": 0},
        ],
        "counterparties": [
            {
                "name": "Kelvin Ong",
                "account": "041-883921",
                "opened_days_ago": 6,
                "relationship_on_file": "not on prior payroll",
                "other_customers_today": 4,
                "salary_credits": 0,
            }
        ],
        "documents": [
            {"id": "pay-1", "kind": "payroll file", "detail": "October file has 42 rows. 41 account numbers match September. The new row names Kelvin Ong, account 041-883921, SGD 3,200, start date today."},
            {"id": "hr-1", "kind": "HR email", "detail": "No signed offer letter is on the file for Kelvin Ong. The row was uploaded by a new payroll admin login created yesterday."},
        ],
        "links": ["HL-4374"],
    },
]


def all_alerts() -> list[dict]:
    return ALERTS


def get_alert(alert_id: str) -> dict | None:
    for alert in ALERTS:
        if alert["id"] == alert_id:
            return alert
    return None
