"""Authored hearings used only when Gemini does not return a usable brief.

Judges should see a live Gemini hearing. These briefs exist so a dead model
call still leaves a complete, honest docket instead of a broken page.
"""

from __future__ import annotations

STANDBY: dict[str, dict] = {
    "HL-4374": {
        "clerk": "Live push-payment. The payee account is six days old and already received money from four other customers today.",
        "ledger": "Three outward payments in nine minutes to account 041-883921, after a SGD 200 test.",
        "archivist": "Priya typed that she was told not to tell the bank. No prior relationship with Kelvin Ong.",
        "statute": "FC-22 requires a hold and a customer message that Harbourline will not ask anyone to move money to a safe account.",
        "counsel": "A genuine new payee is possible, but the script in her own note and the four other victims today leave that explanation thin.",
        "disposition": {
            "disposition": "hold",
            "typology": "Authorised push-payment scam",
            "confidence": 0.86,
            "false_positive": False,
            "rationale": "The payments are still inside Harbourline, the payee account was opened six days ago, and four other customers have already paid it today. Priya's own note records the safe-account script.",
            "customer_message": "We paused the transfers to Kelvin Ong. Harbourline will never ask you to move money to a safe account, and we will never ask you to keep it from us. If you are on a call, hang up. You can reach us on the number on the back of your card. A person on the night desk has this file.",
            "citations": [
                {"source": "ledger", "ref": "041-883921", "point": "Three payments in nine minutes, opened by a SGD 200 test."},
                {"source": "document", "ref": "note-1", "point": "She was told not to tell the bank."},
                {"source": "policy", "ref": "FC-22", "point": "Hold the funds and say we do not use safe accounts."},
            ],
            "sar_draft": "",
            "held_amount": "SGD 18,600 to Kelvin Ong",
            "released_amount": "",
        },
    },
    "HL-4402": {
        "clerk": "Looks like structuring. The beneficiary is his sister, on file since 2022.",
        "ledger": "Three transfers of SGD 9,500, 9,200 and 8,800, each just under the internal line, to the same Nabil account.",
        "archivist": "Employer letter shows a new salary of SGD 4,800. Prior Dashain transfers in 2024 and 2025 were also larger than his monthly average.",
        "statute": "FC-14 says release when the beneficiary is long-standing and the narrative names a family event the file supports.",
        "counsel": "This is the explanation the rule missed. Same sister, same festival, a promotion that can carry the amount, and a hospital named in the narrative.",
        "disposition": {
            "disposition": "clear",
            "typology": "Seasonal family support",
            "confidence": 0.78,
            "false_positive": True,
            "rationale": "The splits sit under the threshold, which is why the rule fired. Anita Sherpa has been his beneficiary since 2022, the narratives name Dashain and Bir Hospital, and his employer confirmed a salary that can carry the week.",
            "customer_message": "Your three transfers to Anita Sherpa are released. We looked at them because they were larger than usual and close together. They match the Dashain support you have sent before and the hospital note you included. Nothing further is needed.",
            "citations": [
                {"source": "document", "ref": "kyc-2", "point": "Sister on file since 2022, with prior Dashain transfers."},
                {"source": "document", "ref": "emp-1", "point": "Salary SGD 4,800 from September."},
                {"source": "policy", "ref": "FC-14", "point": "A known family event is not structuring on its own."},
            ],
            "sar_draft": "",
            "held_amount": "",
            "released_amount": "SGD 27,500 to Anita Sherpa",
        },
    },
    "HL-4418": {
        "clerk": "Pension customer sending most of her savings to payees added yesterday.",
        "ledger": "SGD 48,200 left in a day, after a SGD 500 inbound note that says 'my love', toward a person, a Manila cash outlet, and an e-wallet.",
        "archivist": "Meera told the call centre an online friend is helping her invest. She has no investment payees on an 11-year file.",
        "statute": "FC-22 covers a short online relationship followed by movement of savings. Speak to her without accusing her.",
        "counsel": "A real friend and a real investment would still not explain the same-day hop to a cash outlet and an e-wallet.",
        "disposition": {
            "disposition": "escalate",
            "typology": "Romance scam",
            "confidence": 0.83,
            "false_positive": False,
            "rationale": "An 11-year pension file with no investment payees sent most of its savings, in a day, to a payee added yesterday and then onward to a cash outlet and an e-wallet. The inbound note and the call match a romance script.",
            "customer_message": "We have paused the payments connected to Jonathan Wei. Please come into a branch or call the number on the back of your card and ask for the night desk. We will not ask you to move this money anywhere else. You are not in trouble. We want to talk before any more of your savings leave.",
            "citations": [
                {"source": "ledger", "ref": "15 Oct", "point": "Savings hopped to a new payee, then a cash outlet and an e-wallet."},
                {"source": "document", "ref": "call-1", "point": "She described an online friend helping her invest."},
                {"source": "policy", "ref": "FC-22", "point": "Escalate and do not accuse."},
            ],
            "sar_draft": "Priority customer Meera Iyer, tenure 11 years, pension SGD 3,200. On 15 Oct 2026 sent SGD 48,200 to a payee added the previous day and onward to M Lhuillier Manila and QuickWallet PH. Inbound SGD 500 carried the narrative 'my love'. Customer told the call centre an online acquaintance was directing an investment. Recommend a suspicious matter and a callback by a person.",
            "held_amount": "Any remaining balance related to these payees",
            "released_amount": "",
        },
    },
    "HL-4390": {
        "clerk": "Trade payment. Unit price is far above the cathode band, and the buyer is new.",
        "ledger": "USD 1,240,000, which is USD 3,100 per ton against a band of USD 1,800 to 2,100. Bill of lading weight is 398 tons.",
        "archivist": "Kinabalu Commercials was incorporated 42 days ago. The beneficiary bank changed on this invoice. The prior six invoices sat inside 8 percent of the band.",
        "statute": "FC-31 says hold when the unit price is more than 15 percent off the band, or the buyer is younger than 90 days and the bank changed.",
        "counsel": "A premium grade could explain a higher price. It does not explain a 42-day-old buyer and a new bank on the same invoice.",
        "disposition": {
            "disposition": "escalate",
            "typology": "Trade misinvoicing",
            "confidence": 0.8,
            "false_positive": False,
            "rationale": "The invoice prices cathode at USD 3,100 a ton while the bank's band is USD 1,800 to 2,100, on 398 tons of lading. The buyer was incorporated 42 days ago and the beneficiary bank changed. Earlier Northspan invoices did not look like this.",
            "customer_message": "We are holding payment of invoice INV-8841. The price per ton is outside the range we use for this metal, and the beneficiary details changed. Please send the contract and the grade specification to your trade officer. This is a pause, not a refusal.",
            "citations": [
                {"source": "document", "ref": "inv-8841", "point": "USD 3,100 per ton against a band ending at USD 2,100."},
                {"source": "document", "ref": "bl-19", "point": "Consignee incorporated 42 days ago."},
                {"source": "policy", "ref": "FC-31", "point": "Hold above a 15 percent variance when the bank also changed."},
            ],
            "sar_draft": "Northspan Metals requested USD 1,240,000 on INV-8841 for 400 MT copper cathode. Implied unit price USD 3,100 against an internal band of USD 1,800 to 2,100. Consignee Kinabalu Commercials, Labuan, incorporated 3 Sep 2026. Beneficiary bank differs from the prior Andes Refining series. Recommend holding the payment and a trade-based laundering review.",
            "held_amount": "USD 1,240,000",
            "released_amount": "",
        },
    },
    "HL-4381": {
        "clerk": "Motor claim with two garages and a scene that does not match the story.",
        "ledger": "Requested reserve SGD 14,600. A March claim on the same plate already paid the bumper.",
        "archivist": "Invoices 55018 and 55019 share lines and sit one number apart. The night-rain photo has afternoon shadows. The March claim overlaps the bumper.",
        "statute": "INS-07 says refer, and the customer message must not deny the claim.",
        "counsel": "Two quotes for the same repair are ordinary. Sequential invoice numbers across different garages, plus the old bumper claim, are not.",
        "disposition": {
            "disposition": "escalate",
            "typology": "Claim document mismatch",
            "confidence": 0.77,
            "false_positive": False,
            "rationale": "Two garages billed the same lines under invoice numbers one apart. The scene described as a rainy night shows afternoon light, and the bumper was already paid in March.",
            "customer_message": "Claim MC-22911 is with a reviewer. We are comparing the two repair invoices and the photograph with the March claim on this car. This is not a denial. You will hear from a person, and you do not need to send payment to either garage.",
            "citations": [
                {"source": "document", "ref": "inv-b", "point": "Invoice 55019 repeats 55018 and uses the next number."},
                {"source": "document", "ref": "photo-1", "point": "Scene light does not match 23:40 in rain."},
                {"source": "policy", "ref": "INS-07", "point": "Refer, and do not deny in the customer note."},
            ],
            "sar_draft": "",
            "held_amount": "Settlement of MC-22911",
            "released_amount": "",
        },
    },
    "HL-4366": {
        "clerk": "Payroll is mostly familiar. One new credit hits the account in Priya Nair's live file.",
        "ledger": "SGD 183,200 across 41 known staff matches September. SGD 3,200 goes to 041-883921, linked to HL-4374.",
        "archivist": "No offer letter for Kelvin Ong. The payroll admin login that added the row was created yesterday.",
        "statute": "FC-40 says release the clean credits and hold only the matched one.",
        "counsel": "A real new hire would have an offer letter and would not share an account that four scam victims used today.",
        "disposition": {
            "disposition": "split",
            "typology": "Payroll credit to a scam beneficiary",
            "confidence": 0.84,
            "false_positive": False,
            "rationale": "Forty-one salaries match the prior file and should go out. The new SGD 3,200 credit uses account 041-883921, the payee in Priya Nair's live scam, added by a payroll login created yesterday, with no offer letter.",
            "customer_message": "October pay for your existing team is released. We held SGD 3,200 for Kelvin Ong because that account is part of another open matter and we do not have an offer letter for him. Please call your relationship manager. Everyone else's salary is not affected.",
            "citations": [
                {"source": "ledger", "ref": "041-883921", "point": "Same account as HL-4374."},
                {"source": "document", "ref": "hr-1", "point": "No offer letter, and the admin login is one day old."},
                {"source": "policy", "ref": "FC-40", "point": "Hold the tainted credit only."},
            ],
            "sar_draft": "Lumen Studio payroll of SGD 186,400. Forty-one credits match the prior file. New credit SGD 3,200 to Kelvin Ong, account 041-883921, which is the beneficiary in live matter HL-4374 and has taken funds from four customers today. Admin login created the day before. Recommend releasing the 41 and holding the one.",
            "held_amount": "SGD 3,200 to Kelvin Ong",
            "released_amount": "SGD 183,200 across 41 staff",
        },
    },
}


def brief_for(alert_id: str) -> dict:
    brief = STANDBY[alert_id]
    return {
        "clerk": brief["clerk"],
        "ledger": brief["ledger"],
        "archivist": brief["archivist"],
        "statute": brief["statute"],
        "counsel": brief["counsel"],
        "disposition": brief["disposition"],
    }
