"""Authored briefs a seat falls back to when Gemini does not answer.

Judges should see a live Gemini hearing. These exist so a failed model call
still leaves a complete, honest docket, marked as standby wherever it shows.
A standby seat still runs its tools: the Ledger's queries execute and the
policy search runs, so every ref a standby brief cites is real evidence in the
hearing, and the verifier checks standby output by the same rules as Gemini's.

Numbers here are the ones the tools return on the seeded mart (synth.SEED).
tests/test_standby.py fails if a brief cites a figure the tools no longer give.
"""

from __future__ import annotations

from quorum import policy, warehouse
from quorum.cases import actionable
from quorum.verifier import safe_note


def _f(claim: str, *refs: str) -> dict:
    return {"claim": claim, "refs": list(refs)}


STANDBY: dict[str, dict] = {
    "HL-4374": {
        "ledger_calls": [
            ("customer_baseline", {"customer_id": "C-10021"}),
            ("counterparty_fan_in", {"account": "041-883921"}),
            ("beneficiary_history", {"customer_id": "C-10021", "account": "041-883921"}),
        ],
        "policy_query": "safe account push payment scam new payee collection account",
        "clerk": {
            "summary": "Priya Nair is sending SGD 18,600 in three transfers to a payee she has never paid, while on a call with an unknown number. The payee account is six days old.",
            "question": "Is Priya being scammed into paying a collection account, and how much can still be stopped?",
            "watch_for": ["who else has paid 041-883921", "what her own note says", "whether the funds have left Harbourline"],
        },
        "ledger": {
            "finding": "Account 041-883921 is six days old, took SGD 26,950 from four other customers in the last day, and sent all of it to Bitvault Exchange within an hour. Priya has never paid it, and tonight is 8.4 times her median month.",
            "facts": [
                _f("Four other Harbourline customers paid 041-883921 in the 24 hours before the alert, SGD 26,950 in total.", "fan_in:041-883921"),
                _f("Everything that arrived in 041-883921 left within an hour, to Bitvault Exchange, and the account now holds SGD 410.", "fan_in:041-883921"),
                _f("Priya has no earlier payment to 041-883921.", "history:041-883921"),
                _f("The three transfers total SGD 18,600 against a median month of SGD 2,208.", "baseline:C-10021", "T1", "T2", "T3"),
                _f("The same account is a new joiner on another customer's payroll file.", "fan_in:041-883921", "HL-4366"),
            ],
            "leans": "concerning",
        },
        "archivist": {
            "finding": "Priya's own payment note repeats a safe-account script and says she was told not to tell the bank. She was on a 23-minute call with a number not in her contacts while she paid.",
            "facts": [
                _f("Priya typed that she was told not to tell the bank and that this is the secure account.", "note-1"),
                _f("The payments were made during a 23-minute voice call from a number not in her contacts.", "dev-1"),
                _f("Her KYC shows no prior scam report and no change of address since 2021.", "kyc-1"),
            ],
            "leans": "concerning",
            "tamper_flags": [],
        },
        "statute": {
            "finding": "FC-22 governs: hold funds still in the bank, never accuse the customer, and file when the payee account is new or has taken money from other victims. FC-60 adds that 041-883921 is a collection account.",
            "facts": [
                _f("Hold funds still in Harbourline when a script tells the customer not to speak to the bank.", "FC-22"),
                _f("File a suspicious matter when the payee account opened within 30 days or already took funds from other victims.", "FC-22"),
                _f("An account paid by three or more unrelated customers in seven days that moves money out within an hour is a collection account.", "FC-60"),
            ],
            "leans": "concerning",
            "policy_ids": ["FC-22", "FC-60"],
        },
        "prosecutor": {
            "position": "escalate",
            "argument": "The payee account is six days old, four other customers paid it today, and every dollar left for a crypto exchange within the hour. Priya's own note carries the safe-account script. FC-22 requires a hold and a report on these facts.",
            "facts": [
                _f("Four other customers paid 041-883921 today and the money left within an hour.", "fan_in:041-883921"),
                _f("Priya was told not to tell the bank.", "note-1"),
                _f("FC-22 says file when the payee account is new or has taken other victims' funds.", "FC-22"),
            ],
            "concession": "Priya herself has six years of ordinary banking and is almost certainly the victim here.",
        },
        "counsel": {
            "position": "hold",
            "argument": "Priya is the victim, not a suspect, and the money is still inside Harbourline. Hold the three transfers and call her before anything else. A report should never read as an accusation of her.",
            "facts": [
                _f("Her banking is ordinary: a median month of SGD 2,208 and no night activity.", "baseline:C-10021"),
                _f("All three transfers are still pending.", "T1", "T2", "T3"),
            ],
            "concession": "Four other victims paying the same account today is exactly the case FC-22 says to report.",
        },
        "prosecutor_rebuttal": {
            "position": "escalate",
            "answer": "The report is about account 041-883921, not about Priya. Holding without reporting leaves the account open for the next customer.",
            "facts": [_f("The account is still taking money from other customers.", "fan_in:041-883921")],
            "moved": False,
        },
        "counsel_rebuttal": {
            "position": "escalate",
            "answer": "If the report names the collection account and records Priya as a victim, it protects her. I withdraw the objection.",
            "facts": [_f("FC-22 asks for a report on these facts.", "FC-22")],
            "moved": True,
        },
        "magistrate": {
            "disposition": "escalate",
            "typology": "Authorised push-payment scam into a collection account",
            "confidence": 0.93,
            "false_positive": False,
            "rationale": "All three transfers are still inside Harbourline and go to a six-day-old account that took SGD 26,950 from four other customers today and passed it to Bitvault Exchange within the hour. Priya's own note records the safe-account script while she was on a call with an unknown number. FC-22 requires a hold and a report, and the report concerns the payee account, with Priya recorded as a victim.",
            "facts": [
                _f("Four other customers paid 041-883921 in the last day and the money left within an hour.", "fan_in:041-883921"),
                _f("Priya was told not to tell the bank.", "note-1"),
                _f("She paid during a 23-minute call from an unknown number.", "dev-1"),
                _f("Hold the funds and file when the payee is new or has taken other victims' funds.", "FC-22"),
                _f("041-883921 meets the collection account test.", "FC-60", "fan_in:041-883921"),
            ],
            "held_txn_ids": ["T1", "T2", "T3"],
            "released_txn_ids": [],
            "customer_message": "We have paused your three transfers to Kelvin Ong. Harbourline will never ask you to move money to a safe account or to keep anything from us. If someone is on the phone with you now, please hang up. Then call the number on the back of your card and ask for the night desk.",
            "sar_draft": "On 15 Oct 2026 between 22:32 and 22:40 Harbourline customer Priya Nair (C-10021) attempted three transfers totalling SGD 18,600 to Kelvin Ong, account 041-883921, opened 9 Oct 2026. In the preceding 24 hours the account received SGD 26,950 from four other Harbourline customers and moved all of it to Bitvault Exchange within an hour. The customer's payment note records a safe-account script and she was on a call with an unknown number. The customer is recorded as a victim. Funds held. Linked file HL-4366 pays the same account as a new payroll joiner.",
            "next_step": "Call Priya on her registered number now, restrict outgoing payments on 041-883921, and link HL-4366.",
        },
    },
    "HL-4402": {
        "ledger_calls": [
            ("beneficiary_history", {"customer_id": "C-10388", "account": "KUB 0044192"}),
            ("peer_percentile", {"customer_id": "C-10388"}),
            ("customer_baseline", {"customer_id": "C-10388"}),
        ],
        "policy_query": "remittance splits threshold structuring family festival dashain",
        "clerk": {
            "summary": "Pemba Sherpa sent SGD 27,500 to his sister in Kathmandu in three transfers on consecutive days, each under the SGD 10,000 line. The narratives name Dashain and a surgery at Bir Hospital.",
            "question": "Is this structuring, or the seasonal family support his history already shows?",
            "watch_for": ["how long Anita Sherpa has been paid", "what October looks like for Nepal remitters", "whether his income and savings carry it"],
        },
        "ledger": {
            "finding": "Pemba has paid Anita Sherpa in 55 months since March 2022, typically SGD 800, and every October he sends more. Customers who send money to Nepal send 2.36 times their average month in October.",
            "facts": [
                _f("Anita Sherpa has been paid since 2022-03, in 55 months, typically SGD 800 a month.", "history:KUB 0044192"),
                _f("Each October he sent more: SGD 1,900, 2,000, 2,100 and 2,200.", "history:KUB 0044192"),
                _f("Customers who send money to Nepal send 2.36 times their average month in October.", "peers:C-10388"),
                _f("He held SGD 38,400 before these transfers, more than their SGD 27,500 total.", "baseline:C-10388"),
                _f("No other Harbourline customer pays this account.", "history:KUB 0044192"),
            ],
            "leans": "legitimate",
        },
        "archivist": {
            "finding": "His employer confirms a promotion to SGD 4,800 a month from September, and his KYC records Anita as a family beneficiary since 2022. Earlier Dashain transfers were larger than usual and completed.",
            "facts": [
                _f("Keong Construction promoted him to site supervisor at SGD 4,800 a month on 12 Sep 2026.", "emp-1"),
                _f("Anita Sherpa is a recorded family beneficiary since 2022, with larger Dashain transfers in 2024 and 2025.", "kyc-2"),
            ],
            "leans": "legitimate",
            "tamper_flags": [],
        },
        "statute": {
            "finding": "FC-14 says splits under a threshold are not structuring by themselves. Release when the beneficiary is long-standing, the narrative names a family event or medical bill, and income or savings carry the amount.",
            "facts": [
                _f("Release when the beneficiary has a multi-year history, the narrative names a family event or medical bill, and the customer can carry it.", "FC-14"),
                _f("Escalate when the beneficiary is new, the narrative is empty, or the splits have no seasonal explanation.", "FC-14"),
            ],
            "leans": "legitimate",
            "policy_ids": ["FC-14"],
        },
        "prosecutor": {
            "position": "hold",
            "argument": "Three transfers on three days, each just under SGD 10,000, is the textbook shape of structuring. SGD 27,500 is more than twelve times last October's SGD 2,200. The surgery is named in a narrative but no bill is on the file.",
            "facts": [
                _f("Three transfers of SGD 9,500, 9,200 and 8,800 on consecutive days.", "T1", "T2", "T3"),
                _f("Last October he sent SGD 2,200.", "history:KUB 0044192"),
            ],
            "concession": "The beneficiary, the festival and the savings all check out, which is what FC-14 asks for.",
        },
        "counsel": {
            "position": "clear",
            "argument": "Same sister for four and a half years, a Dashain spike every October that his peers share, and a hospital named in the narrative. A promotion and SGD 38,400 in savings carry the amount. FC-14 was written for exactly this file.",
            "facts": [
                _f("Paid in 55 months since March 2022.", "history:KUB 0044192"),
                _f("Nepal remitters send 2.36 times their average month in October.", "peers:C-10388"),
                _f("Salary rose to SGD 4,800 in September.", "emp-1"),
                _f("FC-14 releases on these facts.", "FC-14"),
            ],
            "concession": "This October is much larger than any October before it, and the surgery bill is not on the file.",
        },
        "prosecutor_rebuttal": {
            "position": "clear",
            "answer": "The size is explained by the surgery and the savings cover it, and every test in FC-14 is met. I withdraw the hold.",
            "facts": [_f("Savings of SGD 38,400 carry the SGD 27,500.", "baseline:C-10388"), _f("FC-14 test met.", "FC-14")],
            "moved": True,
        },
        "counsel_rebuttal": {
            "position": "clear",
            "answer": "A missing bill is a question for his next contact, not a reason to freeze money his sister needs for surgery during the festival.",
            "facts": [_f("The narrative names Bir Hospital.", "T1")],
            "moved": False,
        },
        "magistrate": {
            "disposition": "clear",
            "typology": "none",
            "confidence": 0.84,
            "false_positive": True,
            "rationale": "The rule fired on three splits under SGD 10,000, but the beneficiary is his sister, paid in 55 months since 2022, and every October he sends more, as do customers who remit to Nepal. His promotion to SGD 4,800 and SGD 38,400 in savings carry the SGD 27,500, and the narratives name Dashain and Bir Hospital. FC-14 says release on these facts.",
            "facts": [
                _f("Anita Sherpa has been paid since March 2022, more each October.", "history:KUB 0044192"),
                _f("Nepal remitters send 2.36 times their average month in October.", "peers:C-10388"),
                _f("Savings of SGD 38,400 before the transfers.", "baseline:C-10388"),
                _f("Promotion to SGD 4,800 a month.", "emp-1"),
                _f("Release when history, narrative and means all support the transfers.", "FC-14"),
            ],
            "held_txn_ids": [],
            "released_txn_ids": ["T1", "T2", "T3"],
            "customer_message": "Your three transfers to Anita Sherpa have been released. We checked them because they were larger and closer together than usual, and they match the Dashain support you have sent before. Nothing more is needed. If you have questions, call the number on the back of your card.",
            "sar_draft": "",
            "next_step": "Release all three transfers and note the Bir Hospital bill to ask for at his next branch visit.",
        },
        "liaison": {
            "language": "ne",
            "message": "अनिता शेर्पालाई पठाउनुभएका तपाईंका तीनवटा रकमान्तर अब पठाइएका छन्। यी रकम सामान्यभन्दा ठूला र नजिक-नजिक भएकाले हामीले जाँच गरेका थियौं, र यी तपाईंले पहिले दशैंमा पठाउनुभएको सहयोगसँग मेल खान्छन्। अब केही गर्नुपर्दैन। कुनै प्रश्न भए तपाईंको कार्डको पछाडि रहेको नम्बरमा फोन गर्नुहोस्।",
            "english": "Your three transfers to Anita Sherpa have been released. We checked them because they were larger and closer together than usual, and they match the Dashain support you have sent before. Nothing more is needed. If you have questions, call the number on the back of your card.",
        },
    },
    "HL-4418": {
        "ledger_calls": [
            ("customer_baseline", {"customer_id": "C-10544"}),
            ("counterparty_fan_in", {"account": "cash-4401"}),
            ("counterparty_fan_in", {"account": "SMB 2291"}),
            ("beneficiary_history", {"customer_id": "C-10544", "account": "SMB 2291"}),
        ],
        "policy_query": "romance scam pension elderly vulnerable new payee",
        "clerk": {
            "summary": "Meera Iyer, 67 and retired, sent SGD 47,800 of her savings in about an hour to a payee added yesterday, a Manila cash pickup and a Philippine e-wallet. She says an online friend is helping her invest.",
            "question": "Is Meera the victim of a romance investment scam, and how do we protect her without accusing her?",
            "watch_for": ["how new the payees are", "who else pays the cash pickup", "how she has been contacted"],
        },
        "ledger": {
            "finding": "SGD 47,800 is 27 times Meera's median month and most of her SGD 61,400 savings. Both new payee accounts are a day old, and two other customers paid the Manila cash pickup in the last day.",
            "facts": [
                _f("The three payments total SGD 47,800 against a median month of SGD 1,770.", "baseline:C-10544", "T2", "T3", "T4"),
                _f("She held SGD 61,400 before these payments.", "baseline:C-10544"),
                _f("Tondo Cash Pickup was opened a day before the alert and two other customers paid it SGD 17,700 in that day.", "fan_in:cash-4401"),
                _f("Jonathan Wei's account was opened a day before the alert.", "fan_in:SMB 2291"),
                _f("The only earlier movement with Jonathan Wei is SGD 500 he sent her, marked for the tickets my love.", "history:SMB 2291", "T1"),
            ],
            "leans": "concerning",
        },
        "archivist": {
            "finding": "Meera told the call centre that Jonathan is a friend she met online in August who is helping her invest, and she declined a branch appointment. In eleven years she has never had an investment payee.",
            "facts": [
                _f("She met Jonathan online in August and he is helping her invest; she did not want a branch appointment.", "call-1"),
                _f("Priority customer since 2015 with no previous investment payees and SGD 61,400 in savings.", "kyc-3"),
            ],
            "leans": "concerning",
            "tamper_flags": [],
        },
        "statute": {
            "finding": "FC-22 covers savings moving to new payees after a short online relationship and asks for a report when payee accounts are new. FC-05 requires a call back from a named person and allows a trusted contact to join.",
            "facts": [
                _f("Hold funds when a customer moves savings to a new payee after a short online relationship, and file when the payee is new.", "FC-22"),
                _f("Customers 65 or over get a named call back and may bring a trusted contact; never rush them.", "FC-05"),
            ],
            "leans": "concerning",
            "policy_ids": ["FC-22", "FC-05"],
        },
        "prosecutor": {
            "position": "escalate",
            "argument": "A 67-year-old moved most of her savings in an hour to accounts a day old, after a man she met online sent her SGD 500 for tickets. Two other customers paid the same Manila cash pickup the same day. FC-22 asks for a hold and a report.",
            "facts": [
                _f("Both new payees opened a day before the alert.", "fan_in:SMB 2291", "fan_in:cash-4401"),
                _f("Two other customers paid the cash pickup in the last day.", "fan_in:cash-4401"),
                _f("FC-22 asks for a report on new payee accounts.", "FC-22"),
            ],
            "concession": "Meera believes this is a real investment, and a report alone will not change her mind.",
        },
        "counsel": {
            "position": "hold",
            "argument": "Meera is the person being harmed here, and the first job is to keep her money and her trust. Hold everything and give her the call back FC-05 promises, with someone she trusts on the line. A report can follow once she has been heard.",
            "facts": [
                _f("She is 67 and has eleven years of steady banking.", "kyc-3", "baseline:C-10544"),
                _f("FC-05 asks for a named call back and a trusted contact.", "FC-05"),
            ],
            "concession": "Holding without a report leaves the cash pickup open to the next retiree.",
        },
        "prosecutor_rebuttal": {
            "position": "escalate",
            "answer": "The call back and the report are not alternatives. The report is about the payee accounts, and FC-05 governs how we speak to Meera.",
            "facts": [_f("FC-05 applies to how we contact her.", "FC-05")],
            "moved": False,
        },
        "counsel_rebuttal": {
            "position": "hold",
            "answer": "Then the report must say plainly that Meera is a victim, and nobody should call her until a named person who speaks her language is ready.",
            "facts": [_f("Never rush a vulnerable customer.", "FC-05")],
            "moved": False,
        },
        "magistrate": {
            "disposition": "escalate",
            "typology": "Romance investment scam",
            "confidence": 0.9,
            "false_positive": False,
            "rationale": "Meera moved SGD 47,800, 27 times her median month and most of her savings, to accounts opened a day before the alert, after a man she met online in August sent her SGD 500 for tickets. Two other customers paid the same Manila cash pickup that day. FC-22 requires a hold and a report on the payees, and FC-05 sets how we speak to her.",
            "facts": [
                _f("SGD 47,800 against a median month of SGD 1,770.", "baseline:C-10544"),
                _f("Two other customers paid Tondo Cash Pickup in the last day.", "fan_in:cash-4401"),
                _f("She met Jonathan online in August.", "call-1"),
                _f("Hold and file when savings move to new payees after an online relationship.", "FC-22"),
                _f("A named call back with a trusted contact.", "FC-05"),
            ],
            "held_txn_ids": ["T2", "T3", "T4"],
            "released_txn_ids": [],
            "customer_message": "We have paused three payments from your savings while a person on our team checks them. Harbourline will never ask you to move money to a safe account. A named member of our team would like to call you back, and you are welcome to have a family member or someone you trust join the call. You can also call the number on the back of your card.",
            "sar_draft": "On 15 Oct 2026 between 09:02 and 10:05 Harbourline customer Meera Iyer (C-10544), 67, attempted payments totalling SGD 47,800 to Jonathan Wei (SMB 2291), Tondo Cash Pickup (cash-4401) and QuickWallet PH (wallet-88). Both named accounts were opened on 14 Oct 2026. Tondo Cash Pickup received SGD 17,700 from two other Harbourline customers in the same day. Jonathan Wei sent the customer SGD 500 on 14 Oct marked for the tickets my love, and she told the call centre he is a friend met online in August helping her invest. The customer is recorded as a victim. Funds held.",
            "next_step": "Arrange a named call back to Meera with a trusted contact invited, and refer the three payee accounts to investigations.",
        },
    },
    "HL-4390": {
        "ledger_calls": [
            ("beneficiary_history", {"customer_id": "C-20017", "account": "Callao 30019"}),
            ("counterparty_fan_in", {"account": "Labuan 7712"}),
            ("beneficiary_history", {"customer_id": "C-20017", "account": "Labuan 7712"}),
            ("customer_baseline", {"customer_id": "C-20017"}),
        ],
        "policy_query": "trade invoice commodity price band aluminium bill lading",
        "clerk": {
            "summary": "Northspan Metals asked us to pay USD 1,560,000 for 400 tons of aluminium ingot at USD 3,900 a ton, against a desk band of USD 2,550 to 2,800. The payee is a new Labuan company and the beneficiary bank changed on this invoice.",
            "question": "Is INV-8841 over-invoiced to move value offshore, or a genuine trade with a new counterparty?",
            "watch_for": ["how the price compares with Northspan's earlier invoices", "how new the Labuan account is", "whether the bill of lading supports the quantity"],
        },
        "ledger": {
            "finding": "Northspan's six earlier invoices all went to Andes Refining in Callao, typically USD 786,750 and never more than USD 810,000. This one goes to a Labuan account opened 36 days ago that Northspan has never paid.",
            "facts": [
                _f("Six earlier payments went to Andes Refining since 2025-04, typically USD 786,750, the largest USD 810,000.", "history:Callao 30019"),
                _f("Labuan 7712 was opened 36 days before the alert and has never been paid by Northspan.", "fan_in:Labuan 7712", "history:Labuan 7712"),
                _f("The payment is twice Northspan's median month of USD 775,150.", "baseline:C-20017", "T1"),
            ],
            "leans": "concerning",
        },
        "archivist": {
            "finding": "The invoice prices ingot at USD 3,900 a ton, about 39 percent above the top of the desk band, and the beneficiary bank changed from Andes Refining's. The bill of lading weight of 398 tons is consistent with the 400 invoiced.",
            "facts": [
                _f("INV-8841 is USD 3,900 a ton and the beneficiary bank changed from the prior Andes invoices.", "inv-8841"),
                _f("The desk band this week is USD 2,550 to 2,800 a ton, and prior Northspan invoices were within 6 percent of it.", "band-1"),
                _f("The bill of lading shows 398 tons and a consignee incorporated on 3 Sep 2026.", "bl-19"),
            ],
            "leans": "concerning",
            "tamper_flags": [],
        },
        "statute": {
            "finding": "FC-31 requires a hold when the unit price is more than 15 percent from the desk band, or when the beneficiary bank changed and the counterparty is under 90 days old. Both tests are met; the weight test is not.",
            "facts": [
                _f("Hold when the unit price differs from the band by more than 15 percent.", "FC-31"),
                _f("Hold when the beneficiary or its bank changed and the counterparty was incorporated within 90 days.", "FC-31"),
            ],
            "leans": "concerning",
            "policy_ids": ["FC-31"],
        },
        "prosecutor": {
            "position": "escalate",
            "argument": "The price is 39 percent above the band, the money goes to a company six weeks old in Labuan, and the beneficiary bank changed on this invoice. That is the shape of value being moved offshore through an invoice. FC-31 is met twice over.",
            "facts": [
                _f("USD 3,900 a ton against a top of USD 2,800.", "inv-8841", "band-1"),
                _f("Consignee incorporated on 3 Sep 2026.", "bl-19"),
                _f("FC-31 hold tests met.", "FC-31"),
            ],
            "concession": "Northspan has seven years with us and six invoices that were all inside the band.",
        },
        "counsel": {
            "position": "hold",
            "argument": "Northspan has a clean seven-year history and six invoices that sat within 6 percent of the band. A new supplier and a price spike call for the sales contract and the bank change instruction, not a report on a long-standing customer. Hold and ask.",
            "facts": [
                _f("Prior invoices were within 6 percent of the band.", "band-1"),
                _f("Six earlier payments to Andes Refining were in a steady range.", "history:Callao 30019"),
                _f("FC-31 asks for a hold.", "FC-31"),
            ],
            "concession": "A 39 percent premium on a commodity with a public price is very hard to explain.",
        },
        "prosecutor_rebuttal": {
            "position": "escalate",
            "answer": "Asking Northspan for documents tells them exactly what we noticed. The facts already meet two red flags.",
            "facts": [_f("Both FC-31 tests are met.", "FC-31")],
            "moved": False,
        },
        "counsel_rebuttal": {
            "position": "hold",
            "answer": "FC-31 says hold, not file. Trade compliance can still file after the contract arrives if the premium stays unexplained.",
            "facts": [_f("FC-31 prescribes a hold.", "FC-31")],
            "moved": False,
        },
        "magistrate": {
            "disposition": "hold",
            "typology": "Possible trade over-invoicing",
            "confidence": 0.78,
            "false_positive": False,
            "rationale": "INV-8841 prices ingot about 39 percent above the desk band and pays a Labuan account opened 36 days ago, with the beneficiary bank changed from Andes Refining's. Northspan's six earlier invoices were steady and inside the band, so the change is the signal. FC-31 requires a hold; trade compliance should file if the contract does not explain the premium.",
            "facts": [
                _f("USD 3,900 a ton against a band of USD 2,550 to 2,800.", "inv-8841", "band-1"),
                _f("Labuan 7712 opened 36 days before the alert.", "fan_in:Labuan 7712"),
                _f("Earlier invoices went to Andes Refining, the largest USD 810,000.", "history:Callao 30019"),
                _f("Hold when the price or the beneficiary change tests are met.", "FC-31"),
            ],
            "held_txn_ids": ["T1"],
            "released_txn_ids": [],
            "customer_message": "We have paused payment of invoice INV-8841 to Kinabalu Commercials while our trade team reviews it. Please send your relationship manager the sales contract and the instruction for the new beneficiary bank. We will contact you once the review is complete.",
            "sar_draft": "",
            "next_step": "Request the sales contract and the beneficiary change instruction, and refer to trade compliance if the premium is unexplained.",
        },
    },
    "HL-4381": {
        "ledger_calls": [
            ("beneficiary_history", {"customer_id": "C-30112", "account": "INS-CLAIMS"}),
            ("customer_baseline", {"customer_id": "C-30112"}),
        ],
        "policy_query": "motor claim repair invoice photo prior claim",
        "clerk": {
            "summary": "Arun Dela Cruz claims SGD 14,600 under MC-22911 for a night collision in rain. Two garages sent the same invoice with consecutive numbers, the bumper was paid in March, and the photo shows afternoon light.",
            "question": "Should claim MC-22911 be paid, or referred to investigation?",
            "watch_for": ["the two repair invoices", "the March claim", "the scene photo against the stated time"],
        },
        "ledger": {
            "finding": "Arun was paid SGD 6,200 on an earlier claim in March 2026. His day-to-day banking is ordinary for a salaried customer.",
            "facts": [
                _f("One earlier claim payout of SGD 6,200 in 2026-03.", "history:INS-CLAIMS"),
                _f("His median month is SGD 1,910 and he has no night activity.", "baseline:C-30112"),
            ],
            "leans": "unclear",
        },
        "archivist": {
            "finding": "Two garages billed the same three lines for the same amount with invoice numbers one apart, and the March claim already paid for the same bumper. The scene photo shows short hard shadows on a dry road, not a night in rain.",
            "facts": [
                _f("Jurong Auto Works 55018 and Westlane Motors 55019 share the same lines and amounts.", "inv-a", "inv-b"),
                _f("MC-19002 paid SGD 6,200 for the same bumper on the same plate in March.", "prior"),
                _f("The photo's shadows and dry road are consistent with mid-afternoon, not 23:40 in rain.", "photo-1"),
            ],
            "leans": "concerning",
            "tamper_flags": ["inv-b", "photo-1"],
        },
        "statute": {
            "finding": "INS-07 refers a claim to investigation on twin invoices, a photo that contradicts the stated time, or overlap with a prior claim. All three are present. The customer message must not deny the claim and must name its number.",
            "facts": [
                _f("Refer on shared line items with near-sequential numbers, contradicted image circumstances, or overlapping prior damage.", "INS-07"),
                _f("Do not deny the claim in the customer message; say it is with a reviewer and name the claim number.", "INS-07"),
                _f("Hold the payout while it is investigated; a claim referral on its own is not a suspicious matter.", "INS-07"),
            ],
            "leans": "concerning",
            "policy_ids": ["INS-07"],
        },
        "prosecutor": {
            "position": "hold",
            "argument": "Every INS-07 trigger is present: twin invoices, a photo that contradicts the stated night, and a bumper we already paid for. The payout must not go out. Refer it to claims investigation.",
            "facts": [
                _f("Twin invoices one number apart.", "inv-a", "inv-b"),
                _f("Same bumper paid in March.", "prior"),
                _f("INS-07 refers on these facts.", "INS-07"),
            ],
            "concession": "The twin invoice may come from the garages rather than from Arun.",
        },
        "counsel": {
            "position": "hold",
            "argument": "The documents fail INS-07, but nothing yet shows Arun wrote them; garages sometimes duplicate quotes. Hold the payout and refer it, without telling him his claim is denied.",
            "facts": [
                _f("His banking is ordinary.", "baseline:C-30112"),
                _f("The customer message must not deny the claim.", "INS-07"),
            ],
            "concession": "The photo contradicting his own account of the night is hard to put on a garage.",
        },
        "magistrate": {
            "disposition": "hold",
            "typology": "Motor claim with duplicated invoices",
            "confidence": 0.82,
            "false_positive": False,
            "rationale": "Two garages billed identical lines with consecutive invoice numbers, the March claim already paid for the same bumper, and the scene photo shows afternoon light rather than a night in rain. INS-07 refers a claim to investigation on any one of these. The payout is held and the message names the claim without denying it.",
            "facts": [
                _f("Identical invoices 55018 and 55019.", "inv-a", "inv-b"),
                _f("Prior payout of SGD 6,200 for the same bumper.", "prior", "history:INS-CLAIMS"),
                _f("Photo contradicts the stated time of loss.", "photo-1"),
                _f("Refer to investigation and do not deny in the message.", "INS-07"),
            ],
            "held_txn_ids": ["T1"],
            "released_txn_ids": [],
            "customer_message": "Your claim MC-22911 is now with a reviewer on our claims team. A member of the team will contact you about the next steps. If you have questions, please call the number on your policy schedule and quote MC-22911.",
            "sar_draft": "",
            "next_step": "Refer MC-22911 to claims investigation with both invoices, the photo and MC-19002 attached.",
        },
        "liaison": {
            "language": "tl",
            "message": "Ang inyong claim na MC-22911 ay sinusuri na ngayon ng isang reviewer sa aming claims team. Makikipag-ugnayan sa inyo ang isang miyembro ng team tungkol sa susunod na hakbang. Kung may tanong kayo, tumawag sa numerong nakasulat sa inyong policy schedule at banggitin ang MC-22911.",
            "english": "Your claim MC-22911 is now with a reviewer on our claims team. A member of the team will contact you about the next steps. If you have questions, please call the number on your policy schedule and quote MC-22911.",
        },
    },
    "HL-4366": {
        "ledger_calls": [
            ("customer_baseline", {"customer_id": "C-20231"}),
            ("counterparty_fan_in", {"account": "041-883921"}),
            ("beneficiary_history", {"customer_id": "C-20231", "account": "041-883921"}),
        ],
        "policy_query": "payroll salary credit split collection account",
        "clerk": {
            "summary": "Lumen Studio's October payroll pays 41 known staff SGD 183,200 and one new joiner SGD 3,200. The new joiner's account is the one Priya Nair was told to pay tonight.",
            "question": "Can the payroll go out while the one credit to 041-883921 is held?",
            "watch_for": ["whether the 41 credits match last month", "what else 041-883921 has received", "who uploaded the file"],
        },
        "ledger": {
            "finding": "Lumen pays 41 staff about SGD 181,900 a month and this run is in line with that. The new credit goes to 041-883921, which four other customers paid today and which emptied into Bitvault Exchange within the hour.",
            "facts": [
                _f("Lumen's median month is SGD 181,900 across 41 payees, and this run is 1.0 times that.", "baseline:C-20231"),
                _f("041-883921 took SGD 26,950 from four other customers in the last day and passed it all on within an hour.", "fan_in:041-883921"),
                _f("Lumen has never paid 041-883921 before.", "history:041-883921"),
                _f("The account is also the payee in open file HL-4374.", "fan_in:041-883921", "HL-4374"),
            ],
            "leans": "concerning",
        },
        "archivist": {
            "finding": "41 of 42 rows match September's file; the new row names Kelvin Ong with a start date of today and no signed offer letter. The file was uploaded at 22:50 by a payroll admin login created yesterday, unlike earlier files.",
            "facts": [
                _f("41 of 42 account numbers match September; the new row is Kelvin Ong at 041-883921.", "pay-1"),
                _f("No offer letter, and the file was uploaded at 22:50 by an admin login created yesterday.", "hr-1"),
            ],
            "leans": "concerning",
            "tamper_flags": [],
        },
        "statute": {
            "finding": "FC-40 forbids holding a whole payroll for one tainted credit: release the credits that match the prior file and hold the match. FC-60 treats 041-883921 as a collection account to restrict and link.",
            "facts": [
                _f("Release credits matching the prior payroll, hold only the matched credit, and link the open scam.", "FC-40"),
                _f("Restrict a collection account and link every file that pays it.", "FC-60"),
            ],
            "leans": "concerning",
            "policy_ids": ["FC-40", "FC-60"],
        },
        "prosecutor": {
            "position": "hold",
            "argument": "A payroll admin login created yesterday uploaded this file at 22:50 and inserted a collection account. If that login is compromised, other rows may be wrong too. Hold the run until Lumen's finance manager confirms it.",
            "facts": [
                _f("Admin login created yesterday uploaded the file at 22:50.", "hr-1"),
                _f("041-883921 is a collection account.", "fan_in:041-883921"),
            ],
            "concession": "The other 41 rows match September's account numbers exactly.",
        },
        "counsel": {
            "position": "split",
            "argument": "Forty-one people are owed their salaries tonight, and every one of their account numbers matches September. FC-40 says release those and hold only the credit to the collection account. Lumen is a victim of whoever added that row.",
            "facts": [
                _f("41 rows match September.", "pay-1"),
                _f("FC-40 requires a split.", "FC-40"),
            ],
            "concession": "The new admin login means Lumen's own controls have been bypassed.",
        },
        "prosecutor_rebuttal": {
            "position": "split",
            "answer": "Since all 41 account numbers match September, the injected row is the only change. I accept the split, provided the login is suspended.",
            "facts": [_f("Only one row is new.", "pay-1"), _f("FC-40 split.", "FC-40")],
            "moved": True,
        },
        "counsel_rebuttal": {
            "position": "split",
            "answer": "Agreed on suspending the login; it protects Lumen as much as the bank.",
            "facts": [_f("Admin login created yesterday.", "hr-1")],
            "moved": False,
        },
        "magistrate": {
            "disposition": "split",
            "typology": "Payroll credit to a collection account",
            "confidence": 0.91,
            "false_positive": False,
            "rationale": "Forty-one credits match September's file and Lumen's usual monthly run, so they go out tonight. The one new credit pays 041-883921, the collection account in HL-4374, added by an admin login created yesterday. FC-40 requires releasing the matching credits and holding only the matched one.",
            "facts": [
                _f("41 of 42 rows match September.", "pay-1"),
                _f("This run is in line with Lumen's usual month.", "baseline:C-20231"),
                _f("041-883921 is a collection account.", "fan_in:041-883921", "FC-60"),
                _f("Release the matching credits and hold the match.", "FC-40"),
            ],
            "held_txn_ids": ["T2"],
            "released_txn_ids": ["T1"],
            "customer_message": "Your October payroll has been released, apart from one new credit of SGD 3,200 that we are holding while a person on our team checks it. Please call your relationship manager to confirm the new joiner and the payroll login that uploaded tonight's file.",
            "sar_draft": "",
            "next_step": "Release T1, hold T2, link HL-4374, and ask Lumen's finance manager to confirm or suspend the new payroll admin login.",
        },
    },
    "HL-4429": {
        "ledger_calls": [
            ("beneficiary_history", {"customer_id": "C-10902", "account": "DE89 3704 XXXX"}),
            ("customer_baseline", {"customer_id": "C-10902"}),
        ],
        "policy_query": "screening name match inbound wire false positive",
        "clerk": {
            "summary": "A USD 12,000 bonus from Larchfield Software to Alex Tan Wei Ming stopped at screening on a 91 percent name match. The listed man was born in 1959 and runs vessels; Alex was born in 1995 and is a product manager.",
            "question": "Is this the listed person, or a name match to discount under FC-51?",
            "watch_for": ["which identifiers differ", "how long Larchfield has paid him", "what the employer letter says"],
        },
        "ledger": {
            "finding": "Larchfield Software has credited Alex every month since September 2024, 25 credits of USD 7,400. The bonus comes from the same account.",
            "facts": [
                _f("Larchfield has paid Alex since 2024-09, 25 months at USD 7,400.", "history:DE89 3704 XXXX"),
                _f("The USD 12,000 comes from the same Larchfield account.", "T1", "history:DE89 3704 XXXX"),
            ],
            "leans": "legitimate",
        },
        "archivist": {
            "finding": "The listed person was born on 4 Feb 1959, is not Singaporean, and directs a vessel operator. Alex was born on 19 Jun 1995, is a verified Singapore citizen, and his employer announced this bonus on 1 Oct.",
            "facts": [
                _f("Listed entry: born 4 Feb 1959, not Singaporean, director of a vessel operator, matched on name only.", "scr-1"),
                _f("Alex: born 19 Jun 1995, Singapore citizen, NRIC verified 2022.", "kyc-4"),
                _f("Larchfield told us on 1 Oct that a USD 12,000 retention bonus would be paid on 15 Oct.", "emp-2"),
            ],
            "leans": "legitimate",
            "tamper_flags": [],
        },
        "statute": {
            "finding": "FC-51: a name match alone is not a hit; discount it when two or more identifiers differ and record them. FC-09 forbids telling the customer he matched a list.",
            "facts": [
                _f("Discount a match when two or more identifiers differ, record them, and release.", "FC-51"),
                _f("Never tell a customer that they matched a watch list.", "FC-09"),
            ],
            "leans": "legitimate",
            "policy_ids": ["FC-51", "FC-09"],
        },
        "prosecutor": {
            "position": "clear",
            "argument": "Date of birth, nationality and role all differ from the listed person, which is three identifiers where FC-51 needs two. The payer has credited him monthly for two years. I do not oppose release.",
            "facts": [
                _f("Three identifiers differ.", "scr-1", "kyc-4"),
                _f("FC-51 discount test met.", "FC-51"),
            ],
            "concession": "None of substance; the match rests on the name alone.",
        },
        "counsel": {
            "position": "clear",
            "argument": "Alex is a product manager receiving a bonus his employer announced in writing two weeks ago, from the account that pays his salary. The match is on name only. Release, and say nothing about screening.",
            "facts": [
                _f("Employer letter announces the bonus.", "emp-2"),
                _f("25 months of salary from the same payer.", "history:DE89 3704 XXXX"),
                _f("Do not tell him he matched a list.", "FC-09"),
            ],
            "concession": "The screening record must still carry the identifiers used to discount it.",
        },
        "magistrate": {
            "disposition": "clear",
            "typology": "none",
            "confidence": 0.95,
            "false_positive": True,
            "rationale": "The listed person was born in 1959, is not Singaporean and directs a vessel operator; Alex was born in 1995, is a verified Singapore citizen and is a product manager. FC-51 discounts a match when two identifiers differ, and three do. The payer has credited his salary for 25 months and announced this bonus in writing.",
            "facts": [
                _f("Date of birth, nationality and role differ from the listed entry.", "scr-1", "kyc-4"),
                _f("Larchfield has paid him since September 2024.", "history:DE89 3704 XXXX"),
                _f("The bonus was announced on 1 Oct.", "emp-2"),
                _f("Discount and release when two or more identifiers differ.", "FC-51"),
            ],
            "held_txn_ids": [],
            "released_txn_ids": ["T1"],
            "customer_message": "Your payment from Larchfield Software GmbH has been released after a routine check. Nothing more is needed. If you have questions, call the number on the back of your card.",
            "sar_draft": "",
            "next_step": "Release T1 and record date of birth, nationality and role as the identifiers that discount the match.",
        },
    },
    "HL-4437": {
        "ledger_calls": [
            ("customer_baseline", {"customer_id": "C-10077"}),
            ("counterparty_fan_in", {"account": "078-220014"}),
        ],
        "policy_query": "account takeover sim swap new device password reset elderly",
        "clerk": {
            "summary": "At 03:12 SGD 24,000 left Grace Lim's account for a payee added three minutes earlier, after a password reset from an unseen phone and a SIM swap. Grace is 72 and has never banked at night.",
            "question": "Is this an account takeover, and what must happen before Grace is contacted?",
            "watch_for": ["her usual hours", "the payee account's history", "which phone number is safe to call"],
        },
        "ledger": {
            "finding": "Across 202 transactions in thirteen months Grace has never banked between 22:00 and 06:00, and SGD 24,000 is 5.1 times her median month. Zenith Digital Trading's account is 11 days old and has passed SGD 46,300 from three other customers to Bitvault Exchange.",
            "facts": [
                _f("None of Grace's 202 transactions in thirteen months were between 22:00 and 06:00.", "baseline:C-10077"),
                _f("SGD 24,000 is 5.1 times her median month of SGD 4,703.", "baseline:C-10077", "T1"),
                _f("078-220014 was opened 11 days before the alert and three other customers paid it SGD 46,300.", "fan_in:078-220014"),
                _f("Everything it received left within an hour for Bitvault Exchange; it holds SGD 180.", "fan_in:078-220014"),
            ],
            "leans": "concerning",
        },
        "archivist": {
            "finding": "Her SIM was replaced at 01:58, the password was reset at 02:41 from a phone first seen tonight, and the payee was added at 03:09. Her own iPhone last signed in at 19:20 and she prefers Mandarin.",
            "facts": [
                _f("SIM replaced at 01:58; one-time passwords since went to the new SIM.", "tel-1"),
                _f("Password reset from a new Android at 02:41, payee added 03:09, transfer 03:12; her iPhone last signed in at 19:20.", "dev-2"),
                _f("No sign-ins between 22:00 and 06:00 since 2007; prefers Mandarin.", "kyc-5"),
            ],
            "leans": "concerning",
            "tamper_flags": [],
        },
        "statute": {
            "finding": "FC-27: a new device, a SIM change and a new payee inside 24 hours require holding outgoing payments, suspending digital access, and contacting the customer on the number held before the change. FC-60 applies to the payee account.",
            "facts": [
                _f("Hold payments, suspend digital access, and never contact the customer through the new SIM.", "FC-27"),
                _f("File a suspicious matter when the new payee's account was opened within 30 days or has received funds from other customers.", "FC-27"),
                _f("Restrict a collection account and link every file that pays it.", "FC-60"),
            ],
            "leans": "concerning",
            "policy_ids": ["FC-27", "FC-60"],
        },
        "prosecutor": {
            "position": "escalate",
            "argument": "SIM swap, a new device and a new payee inside 75 minutes, in the middle of the night, for a customer who has never banked after 22:00. The payee account has already emptied three other victims into a crypto exchange. Hold, lock and report.",
            "facts": [
                _f("SIM swap and new device before the payment.", "tel-1", "dev-2"),
                _f("Three other customers paid 078-220014.", "fan_in:078-220014"),
                _f("FC-27 applies.", "FC-27"),
            ],
            "concession": "Grace has done nothing wrong; she is asleep.",
        },
        "counsel": {
            "position": "escalate",
            "argument": "Nothing on this file is Grace. Hold the payment, lock the app, and reach her on the number we held before 01:58, in Mandarin. Reporting the payee account protects her and the next customer.",
            "facts": [
                _f("Her iPhone last signed in at 19:20.", "dev-2"),
                _f("Contact on the number held before the change.", "FC-27"),
            ],
            "concession": "None; the defence here is of Grace, and it agrees with the prosecution.",
        },
        "magistrate": {
            "disposition": "escalate",
            "typology": "Account takeover by SIM swap",
            "confidence": 0.96,
            "false_positive": False,
            "rationale": "A SIM swap at 01:58, a password reset from an unseen phone at 02:41 and a payee added at 03:09 fall well inside FC-27's 24 hours, for a customer with no night activity in 202 transactions. The payee account is 11 days old and has passed SGD 46,300 from three other customers to Bitvault Exchange. Hold the payment, suspend digital access, report the payee account, and reach Grace only on the number held before the swap.",
            "facts": [
                _f("SIM swap, new device and new payee inside 75 minutes.", "tel-1", "dev-2"),
                _f("No night activity in thirteen months.", "baseline:C-10077", "kyc-5"),
                _f("Payee account took SGD 46,300 from three other customers.", "fan_in:078-220014"),
                _f("Hold, suspend and call the old number.", "FC-27"),
                _f("Grace is 72; offer a named call back in Mandarin.", "FC-05"),
            ],
            "held_txn_ids": ["T1"],
            "released_txn_ids": [],
            "customer_message": "To protect your account, we have paused a payment of SGD 24,000 and locked online banking for now. We will call you on the phone number we held for you before tonight, and we can speak in Mandarin. Harbourline will never ask you for a one-time password. You are welcome to have a family member or someone you trust join the call.",
            "sar_draft": "On 16 Oct 2026 Harbourline customer Grace Lim (C-10077), 72, was subject to an account takeover: SIM replaced at 01:58, password reset from an unseen Android at 02:41, payee Zenith Digital Trading (078-220014) added at 03:09 and SGD 24,000 submitted at 03:12. The customer has no sign-ins between 22:00 and 06:00 since 2007. 078-220014 was opened on 5 Oct 2026, received SGD 46,300 from three other Harbourline customers, and moved it to Bitvault Exchange within an hour. The customer is recorded as a victim. Payment held and digital access suspended.",
            "next_step": "Suspend digital access, call Grace in Mandarin on the number held before 01:58, and restrict 078-220014.",
        },
        "liaison": {
            "language": "zh",
            "message": "为保护您的账户，我们已暂停一笔24,000新元的付款，并暂时锁定了网上银行。我们会通过今晚之前为您登记的电话号码与您联系，可以用华语沟通。Harbourline 绝不会向您索取一次性密码。如您愿意，可以请一位家人或您信任的人一起通话。",
            "english": "To protect your account, we have paused a payment of SGD 24,000 and locked online banking for now. We will call you on the phone number we held for you before tonight, and we can speak in Mandarin. Harbourline will never ask you for a one-time password. You are welcome to have a family member or someone you trust join the call.",
        },
    },
}

_TOOLS = {tool.__name__: tool for tool in warehouse.LEDGER_TOOLS}


def ledger_calls(alert: dict) -> list[tuple[str, dict]]:
    """The queries a standby Ledger runs. Generated alerts get the generic set."""
    authored = STANDBY.get(alert["id"])
    if authored:
        return authored["ledger_calls"]
    calls = [("customer_baseline", {"customer_id": alert["customer"]["id"]})]
    for account in sorted({row["account"] for row in actionable(alert) if row["direction"] == "out"}):
        calls.append(("counterparty_fan_in", {"account": account}))
    return calls


_REF = {
    "customer_baseline": lambda kw: f"baseline:{kw['customer_id']}",
    "counterparty_fan_in": lambda kw: f"fan_in:{kw['account']}",
    "beneficiary_history": lambda kw: f"history:{kw['account']}",
    "peer_percentile": lambda kw: f"peers:{kw['customer_id']}",
}


def run_ledger(alert: dict, tool_context, have: set[str] = frozenset()) -> list[dict]:
    """Run the standby Ledger's queries for real, so its refs exist. Skips refs already in `have`.

    Each call is returned as {name, args, result}, the shape of a model's tool call and its response.
    """
    return [
        {"name": name, "args": kwargs, "result": _TOOLS[name](**kwargs, tool_context=tool_context)}
        for name, kwargs in ledger_calls(alert)
        if _REF[name](kwargs) not in have
    ]


def run_statute(alert: dict, tool_context) -> dict:
    authored = STANDBY.get(alert["id"])
    query = authored["policy_query"] if authored else f"{alert['rule']} {alert['product']}"
    return {"name": "search_policy", "args": {"query": query}, "result": policy.search_policy(query, tool_context=tool_context)}


def run_read_file(tool_context) -> dict:
    return {"name": "read_file", "args": {}, "result": warehouse.read_file(tool_context)}


def brief(alert: dict, seat: str, evidence: dict[str, dict] | None = None) -> dict | None:
    """The authored output for one seat, or a generic one for generated alerts.

    Returns None when the authored hearing has no such seat: a rebuttal on a
    file the standby agreed on, or a liaison note for an English speaker.
    """
    authored = STANDBY.get(alert["id"])
    if authored:
        return authored.get(seat)
    return _generic(alert, seat, evidence or {})


def _generic(alert: dict, seat: str, evidence: dict[str, dict]) -> dict | None:
    """A cautious brief for a file nobody authored: hold it for a person."""
    open_ids = [row["id"] for row in actionable(alert)]
    baseline = evidence.get(f"baseline:{alert['customer']['id']}", {}).get("summary", {})
    fan_ins = [(ref, item["summary"]) for ref, item in evidence.items() if ref.startswith("fan_in:")]
    ledger_facts = []
    if baseline.get("alert_vs_median"):
        ledger_facts.append(_f(
            f"This file is {baseline['alert_vs_median']} times the customer's median month of {baseline['median_monthly_out']:,.0f}.",
            f"baseline:{alert['customer']['id']}",
        ))
    for ref, summary in fan_ins:
        ledger_facts.append(_f(
            f"{summary['other_customers_paying']} other customers paid {summary['account']} in the window.", ref,
        ))
    if not ledger_facts:
        ledger_facts.append(_f(alert["rule"], *open_ids[:1]))
    docs = [doc["id"] for doc in alert["documents"]]
    found = [p["id"] for p in policy.rank(f"{alert['rule']} {alert['product']}")] or ["FC-02"]
    hold = {
        "clerk": {"summary": alert["summary"], "question": f"Does '{alert['rule']}' reflect real risk on this file?",
                  "watch_for": ["the customer's usual pattern", "the payee's history"]},
        "ledger": {"finding": "Standby summary of the Ledger's queries.", "facts": ledger_facts, "leans": "unclear"},
        "archivist": {"finding": "Standby: the documents on the file were read but not weighed.",
                      "facts": [_f(f"The file holds {len(docs)} documents.", *docs)] if docs else ledger_facts[:1],
                      "leans": "unclear", "tamper_flags": []},
        "statute": {"finding": "Standby: the policies the search returned.", "facts": [_f(_title(pid), pid) for pid in found],
                    "leans": "unclear", "policy_ids": found},
        "prosecutor": {"position": "hold", "argument": "Without a reasoned hearing the cautious course is to hold for a person.",
                       "facts": ledger_facts[:2], "concession": "No seat has weighed the legitimate explanation."},
        "counsel": {"position": "hold", "argument": "A person should review this before the customer is affected further.",
                    "facts": ledger_facts[:1], "concession": "No seat has weighed the evidence against the customer."},
        "magistrate": {
            "disposition": "hold", "typology": "unreviewed", "confidence": 0.5, "false_positive": False,
            "rationale": "Gemini did not return a reasoned verdict for this file, so the desk holds it for a person. The facts below are the Ledger's queries, not a judgement.",
            "facts": ledger_facts + [_f(_title(found[0]), found[0])],
            "held_txn_ids": open_ids, "released_txn_ids": [],
            "customer_message": safe_note(alert, "hold"), "sar_draft": "",
            "next_step": "Review this file by hand; the hearing ran on standby.",
        },
    }
    return hold.get(seat)


def _title(policy_id: str) -> str:
    return policy.BY_ID[policy_id]["title"]
