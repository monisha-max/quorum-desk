"""A seeded synthetic Harbourline mart: customers, accounts, transactions.

Every run produces the same rows. About fifteen hundred background customers
give the Ledger seat a population to compare against, and the eight case files
are written into it with the history their documents describe: Pemba's four
years of remittances to his sister, the mule account taking money from four
other customers on the night Priya pays it, Grace never once banking after ten.

Timestamps are ISO strings in Singapore time. That keeps the Ledger SQL
identical on BigQuery and on the local SQLite mirror.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from functools import lru_cache

SGT = timezone(timedelta(hours=8))
SEED = 4374
START = datetime(2024, 10, 1, tzinfo=SGT)
AS_OF = datetime(2026, 10, 16, 6, 0, tzinfo=SGT)

CUSTOMER_FIELDS = ("customer_id", "name", "segment", "cohort", "age", "city", "tenure_years", "occupation", "monthly_income")
ACCOUNT_FIELDS = ("account_id", "holder_name", "bank", "opened", "customer_id", "kind", "balance")
TXN_FIELDS = (
    "txn_id", "ts", "customer_id", "account_id", "direction", "amount", "currency",
    "counterparty_name", "counterparty_account", "corridor", "channel", "narrative",
    "status", "alert_ref",
)

_FIRST = (
    "Wei Ling", "Jun Hao", "Mei Xin", "Kai Wen", "Siti", "Nurul", "Ahmad", "Farah", "Arjun",
    "Kavya", "Rohan", "Divya", "Marco", "Joy", "Paolo", "Rhea", "Hui Min", "Zhi Hao",
    "Aisyah", "Hafiz", "Ravi", "Anjali", "Daniel", "Grace", "Ethan", "Chloe", "Bikash",
    "Sunita", "Ramesh", "Sabina", "Liza", "Carlo", "Imran", "Yusof", "Shalini", "Vikram",
)
_LAST = (
    "Tan", "Lim", "Lee", "Ng", "Wong", "Goh", "Chua", "Ong", "Koh", "Teo", "Rahman",
    "Ismail", "Hassan", "Pillai", "Menon", "Raj", "Krishnan", "Reyes", "Santos", "Cruz",
    "Bautista", "Gurung", "Tamang", "Rai", "Thapa", "Shrestha", "Chen", "Ho", "Yeo",
)
_LOCAL_PAYEES = (
    ("Lion City Power", "UTIL-01"), ("Straits Telco", "UTIL-02"), ("Town Council", "UTIL-03"),
    ("Harbour Water", "UTIL-04"), ("Merlion Mobile", "UTIL-05"), ("Harbourline Cards", "CARD-00"),
)
_CORRIDOR_BANK = {
    "NP": ("Kathmandu Union Bank", "KUB"),
    "PH": ("Pasig Mutual Bank", "PMB"),
    "IN": ("Kaveri Rural Bank", "KRB"),
}
# Festival months when families send more home: Dashain, Christmas, Diwali.
_SPIKE_MONTH = {"NP": 10, "PH": 12, "IN": 11}

# (cohort, count, segment, corridor, income range)
_COHORTS = (
    ("salaried", 740, "Everyday", "SG", (3200, 9000)),
    ("np_remit", 150, "Everyday", "NP", (2600, 5200)),
    ("ph_remit", 160, "Everyday", "PH", (2200, 4800)),
    ("in_remit", 130, "Everyday", "IN", (3000, 7000)),
    ("retiree", 150, "Priority", "SG", (2400, 4200)),
    ("priority", 110, "Priority", "SG", (9000, 22000)),
    ("business", 50, "Business", "SG", (60000, 260000)),
    ("trader", 10, "Trade", "SG", (500000, 1500000)),
)


def _months(start: datetime, end: datetime):
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        yield year, month
        month += 1
        if month == 13:
            year, month = year + 1, 1


def _ts(year: int, month: int, day: int, hour: int, minute: int) -> str:
    return datetime(year, month, min(day, 28), hour, minute, tzinfo=SGT).isoformat()


class _Mart:
    def __init__(self) -> None:
        self.rng = random.Random(SEED)
        self.customers: list[dict] = []
        self.accounts: list[dict] = []
        self.txns: list[tuple] = []
        self.account_of: dict[str, str] = {}
        self._seq = 0
        self._acct_seq = 100000

    def account(self, holder: str, bank: str = "Harbourline", opened: str = "2018-01-01",
                customer_id: str | None = None, kind: str = "deposit", account_id: str | None = None,
                balance: float | None = None) -> str:
        if account_id is None:
            self._acct_seq += 7919
            account_id = f"0{self.rng.randint(10, 99)}-{self._acct_seq % 1000000:06d}"
        if customer_id and customer_id not in self.account_of:
            self.account_of[customer_id] = account_id
        self.accounts.append({
            "account_id": account_id, "holder_name": holder, "bank": bank, "opened": opened,
            "customer_id": customer_id, "kind": kind, "balance": balance,
        })
        return account_id

    def txn(self, ts: str, customer_id: str, account_id: str, direction: str, amount: float,
            counterparty: str, counterparty_account: str, narrative: str = "", currency: str = "SGD",
            corridor: str = "SG", channel: str = "mobile", status: str = "posted",
            alert_ref: str | None = None, txn_id: str | None = None) -> None:
        if txn_id is None:
            self._seq += 1
            txn_id = f"X{self._seq:07d}"
        self.txns.append((
            txn_id, ts, customer_id, account_id, direction, round(float(amount), 2), currency,
            counterparty, counterparty_account, corridor, channel, narrative, status, alert_ref,
        ))


def _name(rng: random.Random) -> str:
    return f"{rng.choice(_FIRST)} {rng.choice(_LAST)}"


def _background(m: _Mart) -> dict[str, list[str]]:
    rng = m.rng
    by_cohort: dict[str, list[str]] = {}
    serial = 11000
    for cohort, count, segment, corridor, (lo, hi) in _COHORTS:
        for _ in range(count):
            serial += 1
            cid = f"C-{serial}"
            tenure = rng.randint(1, 18)
            income = round(rng.uniform(lo, hi), -1)
            name = _name(rng) if segment not in {"Business", "Trade"} else f"{rng.choice(_LAST)} {rng.choice(('Studio', 'Logistics', 'Foods', 'Engineering', 'Trading', 'Clinic'))} Pte Ltd"
            m.customers.append({
                "customer_id": cid, "name": name, "segment": segment, "cohort": cohort,
                "age": None if segment in {"Business", "Trade"} else (rng.randint(62, 84) if cohort == "retiree" else rng.randint(22, 60)),
                "city": "Singapore", "tenure_years": tenure,
                "occupation": {"retiree": "Retired", "business": "SME", "trader": "Commodity trader"}.get(cohort, "Employee"),
                "monthly_income": income,
            })
            acct = m.account(name, customer_id=cid, opened=f"{2026 - tenure}-0{rng.randint(1, 9)}-1{rng.randint(0, 9)}",
                             balance=round(income * rng.uniform(1.5, 14), -1))
            by_cohort.setdefault(cohort, []).append(cid)
            _background_rows(m, cid, acct, cohort, corridor, income)
    return by_cohort


def _background_rows(m: _Mart, cid: str, acct: str, cohort: str, corridor: str, income: float) -> None:
    rng = m.rng
    payees = [(_name(rng), f"0{rng.randint(10, 99)}-{rng.randint(100000, 999999)}") for _ in range(rng.randint(2, 5))]
    utilities = rng.sample(_LOCAL_PAYEES, 3)
    beneficiary = None
    if corridor in _CORRIDOR_BANK:
        bank, code = _CORRIDOR_BANK[corridor]
        beneficiary = (_name(rng), f"{code} {rng.randint(1000000, 9999999)}")
        base_remit = round(income * rng.uniform(0.12, 0.3), -1)
    night_owl = cohort in {"salaried", "priority"} and rng.random() < 0.18
    day_lo, day_hi = (8, 20) if cohort == "retiree" else (7, 22)

    def hour() -> int:
        if night_owl and rng.random() < 0.06:
            return rng.choice((22, 23, 0, 1))
        return rng.randint(day_lo, day_hi)

    for year, month in _months(START, AS_OF):
        last_day = 15 if (year, month) == (AS_OF.year, AS_OF.month) else 28
        if cohort == "retiree":
            m.txn(_ts(year, month, 1, 9, 5), cid, acct, "in", income, "Pension credit", "PEN-00", "monthly pension", channel="giro")
        elif cohort == "business":
            for _ in range(rng.randint(3, 6)):
                m.txn(_ts(year, month, rng.randint(1, last_day), rng.randint(9, 18), rng.randint(0, 59)), cid, acct, "in",
                      round(income * rng.uniform(0.15, 0.4), -1), _name(rng) + " Pte Ltd", f"0{rng.randint(10, 99)}-{rng.randint(100000, 999999)}", "invoice receipt", channel="fast")
            if last_day == 28:
                m.txn(_ts(year, month, 25, 21, 0), cid, acct, "out", round(income * rng.uniform(0.5, 0.6), -1), "Payroll batch", "PAYROLL", "monthly salaries", channel="payroll")
            for _ in range(rng.randint(2, 4)):
                m.txn(_ts(year, month, rng.randint(1, last_day), rng.randint(9, 18), rng.randint(0, 59)), cid, acct, "out",
                      round(income * rng.uniform(0.03, 0.12), -1), rng.choice(payees)[0] + " Supplies", rng.choice(payees)[1], "supplier", channel="fast")
            continue
        elif cohort == "trader":
            if rng.random() < 0.35:
                m.txn(_ts(year, month, rng.randint(1, last_day), rng.randint(9, 17), rng.randint(0, 59)), cid, acct, "out",
                      round(income * rng.uniform(0.6, 1.2), -3), "Overseas supplier", f"SWIFT-{rng.randint(1000, 9999)}", "commodity invoice", currency="USD", corridor="XX", channel="trade")
            continue
        elif last_day == 28:
            m.txn(_ts(year, month, 26, 10, 0), cid, acct, "in", income, "Employer payroll", "PAY-00", "salary", channel="giro")
        for name, code in utilities:
            if rng.random() < 0.85:
                m.txn(_ts(year, month, rng.randint(2, last_day), hour(), rng.randint(0, 59)), cid, acct, "out",
                      round(rng.uniform(40, 260), 2), name, code, "bill")
        for _ in range(rng.randint(1, 4)):
            name, code = rng.choice(payees)
            m.txn(_ts(year, month, rng.randint(1, last_day), hour(), rng.randint(0, 59)), cid, acct, "out",
                  round(rng.uniform(30, income * 0.25), 2), name, code, rng.choice(("dinner", "rent share", "gift", "repay", "")))
        if rng.random() < 0.06:
            payees.append((_name(rng), f"0{rng.randint(10, 99)}-{rng.randint(100000, 999999)}"))
        if beneficiary and (last_day == 28 or month == _SPIKE_MONTH[corridor]):
            amount = base_remit
            if month == _SPIKE_MONTH[corridor]:
                amount = base_remit * rng.uniform(1.8, 3.6)
            pieces = 1 if amount < base_remit * 2 else rng.randint(1, 3)
            for i in range(pieces):
                m.txn(_ts(year, month, min(rng.randint(3, 14) + i, last_day), hour(), rng.randint(0, 59)), cid, acct, "out",
                      round(amount / pieces, -1), beneficiary[0], beneficiary[1], rng.choice(("family", "home", "support", "festival")),
                      corridor=corridor, channel="remit")


def _priya_and_the_mule(m: _Mart, victims: list[str]) -> None:
    priya = m.account("Priya Nair", customer_id="C-10021", opened="2020-08-14", account_id="015-220341", balance=31240)
    mother = ("Lakshmi Nair", "024-771903")
    for year, month in _months(START, AS_OF):
        last = 15 if (year, month) == (2026, 10) else 28
        if last == 28:
            m.txn(_ts(year, month, 26, 10, 0), "C-10021", priya, "in", 4300, "Northvale Primary School", "PAY-NVP", "salary", channel="giro")
        m.txn(_ts(year, month, 1, 9, 20), "C-10021", priya, "out", 1800, "Rahim Properties", "037-550218", "rent")
        m.txn(_ts(year, month, 4, 20, 10), "C-10021", priya, "out", 300, *mother, "for amma")
        m.txn(_ts(year, month, 7, 19, 45), "C-10021", priya, "out", round(80 + (month * 7) % 40, 2), "Lion City Power", "UTIL-01", "bill")
        if month in (3, 8, 12):
            m.txn(_ts(year, month, 12, 13, 5), "C-10021", priya, "out", 220, "Merlion Mobile", "UTIL-05", "bill")
    m.txn("2026-08-18T12:40:00+08:00", "C-10021", priya, "out", 160, "Kopi Corner Catering", "052-118604", "staff lunch")

    m.customers.append({"customer_id": "C-19044", "name": "Kelvin Ong", "segment": "Everyday", "cohort": "new",
                        "age": 24, "city": "Singapore", "tenure_years": 0, "occupation": "Not stated", "monthly_income": None})
    mule = m.account("Kelvin Ong", customer_id="C-19044", opened="2026-10-09", account_id="041-883921", balance=410)
    m.txn("2026-10-10T11:02:00+08:00", "C-19044", mule, "in", 50, "Cash deposit machine", "CDM-12", "", channel="cdm")
    exchange = ("Bitvault Exchange", "VASP-7731")
    hits = (("18:05", 4800, "secure account as advised"), ("19:40", 7250, "safe account"),
            ("20:15", 2900, "transfer per officer call"), ("21:52", 12000, "do not reverse"))
    for victim, (hhmm, amount, note) in zip(victims, hits):
        hh, mm = hhmm.split(":")
        m.txn(f"2026-10-15T{hhmm}:00+08:00", victim, m.account_of[victim], "out", amount, "Kelvin Ong", mule, note)
        m.txn(f"2026-10-15T{hhmm}:00+08:00", "C-19044", mule, "in", amount, "Harbourline customer", m.account_of[victim], note)
        out_minute = int(mm) + 7
        m.txn(f"2026-10-15T{int(hh) + out_minute // 60:02d}:{out_minute % 60:02d}:00+08:00", "C-19044", mule, "out",
              amount - 20, *exchange, "top up", channel="fast")
    for tid, hhmm, amount, note in (("T1", "22:32", 200, "test"), ("T2", "22:36", 8400, "safe account do not reverse"),
                                   ("T3", "22:40", 10000, "as instructed on the phone")):
        m.txn(f"2026-10-15T{hhmm}:00+08:00", "C-10021", priya, "out", amount, "Kelvin Ong", mule, note,
              status="pending", alert_ref=f"HL-4374:{tid}", txn_id=f"HL-4374:{tid}")


def _pemba(m: _Mart) -> None:
    acct = m.account("Pemba Sherpa", customer_id="C-10388", opened="2017-05-02", account_id="027-118204", balance=38400)
    sister = ("Anita Sherpa", "KUB 0044192")
    for year, month in _months(datetime(2022, 3, 1, tzinfo=SGT), AS_OF):
        if (year, month) >= (2024, 10):
            if (year, month) != (2026, 10):
                salary = 4800 if (year, month) >= (2026, 9) else 3900
                m.txn(_ts(year, month, 27, 10, 0), "C-10388", acct, "in", salary, "Keong Construction", "PAY-KC", "salary", channel="giro")
            m.txn(_ts(year, month, 3, 8, 40), "C-10388", acct, "out", 650, "Tamang Lodging", "063-220981", "room rent")
        if (year, month) == (2026, 10):
            continue
        amount = 800 + ((year * 12 + month) % 5 - 2) * 30
        if month == 10:
            amount = {2022: 1900, 2023: 2000, 2024: 2100, 2025: 2200}[year]
        m.txn(_ts(year, month, 6, 12, 15), "C-10388", acct, "out", amount, *sister,
              "Dashain" if month == 10 else "for family", corridor="NP", channel="remit")
    for tid, ts, amount, note in (("T1", "2026-10-13T12:10:00+08:00", 9500, "Dashain and Anita surgery Bir Hospital"),
                                  ("T2", "2026-10-14T12:22:00+08:00", 9200, "hospital balance Bir"),
                                  ("T3", "2026-10-15T15:58:00+08:00", 8800, "Dashain family")):
        m.txn(ts, "C-10388", acct, "out", amount, *sister, note, corridor="NP", channel="remit",
              status="pending", alert_ref=f"HL-4402:{tid}", txn_id=f"HL-4402:{tid}")


def _meera(m: _Mart, other_victims: list[str]) -> None:
    acct = m.account("Meera Iyer", customer_id="C-10544", opened="2015-02-11", account_id="033-604117", balance=61400)
    for year, month in _months(START, AS_OF):
        m.txn(_ts(year, month, 1, 9, 5), "C-10544", acct, "in", 3200, "Pension credit", "PEN-00", "monthly pension", channel="giro")
        if (year, month) == (2026, 10):
            break
        m.txn(_ts(year, month, 3, 10, 30), "C-10544", acct, "out", 900, "Iyer Household", "019-330417", "household")
        m.txn(_ts(year, month, 9, 11, 0), "C-10544", acct, "out", round(160 + month * 4, 2), "Lion City Power", "UTIL-01", "bill")
        m.txn(_ts(year, month, 15, 15, 20), "C-10544", acct, "out", 600 + (month % 3) * 100, "Kavya Iyer", "028-114590", "for the kids")
    m.txn("2026-10-14T19:10:00+08:00", "C-10544", acct, "in", 500, "Jonathan Wei", "SMB 2291", "for the tickets my love",
          channel="fast", alert_ref="HL-4418:T1", txn_id="HL-4418:T1")
    for tid, ts, amount, party, account, note in (
        ("T2", "2026-10-15T09:02:00+08:00", 19800, "Jonathan Wei", "SMB 2291", "investment tranche"),
        ("T3", "2026-10-15T09:40:00+08:00", 18400, "Tondo Cash Pickup", "cash-4401", "collection"),
        ("T4", "2026-10-15T10:05:00+08:00", 9600, "QuickWallet PH", "wallet-88", "top up"),
    ):
        m.txn(ts, "C-10544", acct, "out", amount, party, account, note, corridor="PH", status="pending",
              alert_ref=f"HL-4418:{tid}", txn_id=f"HL-4418:{tid}")
    for victim, ts, amount in zip(other_victims, ("2026-10-14T16:12:00+08:00", "2026-10-15T08:31:00+08:00"), (6500, 11200)):
        m.txn(ts, victim, m.account_of[victim], "out", amount, "Tondo Cash Pickup", "cash-4401", "collection", corridor="PH")


def _northspan(m: _Mart) -> None:
    acct = m.account("Northspan Metals Pte Ltd", customer_id="C-20017", opened="2019-06-03", account_id="088-400172", kind="trade", balance=2140000)
    prior = (("2025-04", "INV-8012", 300, 2610), ("2025-07", "INV-8107", 300, 2680), ("2025-10", "INV-8233", 290, 2590),
             ("2026-01", "INV-8390", 310, 2550), ("2026-04", "INV-8512", 290, 2620), ("2026-07", "INV-8701", 300, 2700))
    for month, inv, tons, price in prior:
        m.txn(f"{month}-09T11:20:00+08:00", "C-20017", acct, "out", tons * price, "Andes Refining SAC", "Callao 30019",
              f"{inv} P1020 aluminium ingot {tons} MT @ USD {price:,}", currency="USD", corridor="PE", channel="trade")
        m.txn(f"{month}-24T15:00:00+08:00", "C-20017", acct, "in", round(tons * price * 1.06, -2), "Selangor Extrusions Bhd",
              "MY-55120", f"onward sale of {inv}", currency="USD", corridor="MY", channel="trade")
    m.txn("2026-10-14T17:55:00+08:00", "C-20017", acct, "out", 1560000, "Kinabalu Commercials", "Labuan 7712",
          "INV-8841 aluminium ingot 400 MT", currency="USD", corridor="MY", channel="trade", status="pending",
          alert_ref="HL-4390:T1", txn_id="HL-4390:T1")


def _arun(m: _Mart) -> None:
    acct = m.account("Arun Dela Cruz", customer_id="C-30112", opened="2023-04-20", account_id="019-772510", balance=8900)
    for year, month in _months(START, AS_OF):
        if (year, month) != (2026, 10):
            m.txn(_ts(year, month, 26, 10, 0), "C-30112", acct, "in", 3600, "Pasir Fleet Services", "PAY-PFS", "salary", channel="giro")
        m.txn(_ts(year, month, 2, 9, 0), "C-30112", acct, "out", 210, "Harbourline General", "INS-MOTOR", "motor premium", channel="giro")
        m.txn(_ts(year, month, 1, 8, 30), "C-30112", acct, "out", 1350, "Woodlands Rooms", "044-918203", "rent")
        m.txn(_ts(year, month, 12, 19, 10), "C-30112", acct, "out", round(70 + month * 6, 2), "Straits Telco", "UTIL-02", "bill")
        m.txn(_ts(year, month, 18, 20, 40), "C-30112", acct, "out", 250, "Rosalinda Dela Cruz", "PMB 4410882", "for nanay", corridor="PH", channel="remit")
    m.txn("2026-03-19T14:10:00+08:00", "C-30112", acct, "in", 6200, "Harbourline General claims", "INS-CLAIMS",
          "MC-19002 settlement bumper", channel="giro")
    m.txn("2026-10-14T09:40:00+08:00", "C-30112", acct, "in", 14600, "Harbourline General claims", "INS-CLAIMS",
          "requested settlement MC-22911", status="pending", alert_ref="HL-4381:T1", txn_id="HL-4381:T1")


def _lumen(m: _Mart) -> None:
    acct = m.account("Lumen Studio Pte Ltd", customer_id="C-20231", opened="2021-01-18", account_id="090-310558", kind="business", balance=402000)
    rng = random.Random(SEED + 66)
    staff = [(_name(rng), f"0{rng.randint(10, 99)}-{rng.randint(100000, 999999)}", round(rng.uniform(3000, 6600), -1)) for _ in range(41)]
    scale = 181900 / sum(pay for _, _, pay in staff)
    staff = [(name, account, round(pay * scale, 2)) for name, account, pay in staff]
    for year, month in _months(START, AS_OF):
        for _ in range(4):
            m.txn(_ts(year, month, rng.randint(1, 15 if (year, month) == (2026, 10) else 28), 11, rng.randint(0, 59)), "C-20231", acct, "in",
                  round(rng.uniform(40000, 70000), -2), "Client receipt", f"CL-{rng.randint(100, 999)}", "design retainer", channel="fast")
        if (year, month) >= (2026, 10):
            continue
        headcount = 41 if (year, month) >= (2026, 3) else 38
        for name, account, pay in staff[:headcount]:
            m.txn(_ts(year, month, 25, 21, 5), "C-20231", acct, "out", pay, name, account, f"salary {year}-{month:02d}", channel="payroll")
    october = 183200 / sum(pay for _, _, pay in staff)
    for i, (name, account, pay) in enumerate(staff, 1):
        m.txn("2026-10-15T22:50:00+08:00", "C-20231", acct, "out", round(pay * october, 2), name, account, "salary 2026-10",
              channel="payroll", status="pending", alert_ref="HL-4366:T1", txn_id=f"HL-4366:T1.{i:02d}")
    m.txn("2026-10-15T22:50:00+08:00", "C-20231", acct, "out", 3200, "Kelvin Ong", "041-883921", "new joiner, added today",
          channel="payroll", status="pending", alert_ref="HL-4366:T2", txn_id="HL-4366:T2")


def _alex(m: _Mart, colleagues: list[str]) -> None:
    acct = m.account("Alex Tan Wei Ming", customer_id="C-10902", opened="2022-06-30", account_id="011-559203", balance=46800)
    employer = ("Larchfield Software GmbH", "DE89 3704 XXXX")
    for year, month in _months(datetime(2024, 9, 1, tzinfo=SGT), AS_OF):
        if (year, month) != (2026, 10):
            m.txn(_ts(year, month, 28, 16, 0), "C-10902", acct, "in", 7400, *employer, "Salary A Tan", currency="USD", corridor="DE", channel="swift")
        if (year, month) >= (2024, 10):
            m.txn(_ts(year, month, 2, 9, 30), "C-10902", acct, "out", 2400, "Tiong Bahru Residences", "045-330872", "rent")
            m.txn(_ts(year, month, 11, 20, 15), "C-10902", acct, "out", round(90 + month * 3, 2), "Straits Telco", "UTIL-02", "bill")
    for colleague in colleagues:
        for year, month in _months(datetime(2025, 3, 1, tzinfo=SGT), datetime(2026, 9, 1, tzinfo=SGT)):
            m.txn(_ts(year, month, 28, 16, 0), colleague, m.account_of[colleague], "in", 6900, *employer, "Salary", currency="USD", corridor="DE", channel="swift")
    m.txn("2026-10-15T14:22:00+08:00", "C-10902", acct, "in", 12000, *employer, "Q3 retention bonus A Tan", currency="USD",
          corridor="DE", channel="swift", status="pending", alert_ref="HL-4429:T1", txn_id="HL-4429:T1")


def _grace_and_the_takeover(m: _Mart, victims: list[str]) -> None:
    acct = m.account("Grace Lim", customer_id="C-10077", opened="2007-03-12", account_id="002-118830", balance=212600)
    rng = random.Random(SEED + 77)
    for year, month in _months(START, AS_OF):
        m.txn(_ts(year, month, 1, 9, 0), "C-10077", acct, "in", 2900, "Annuity payout", "ANN-04", "annuity", channel="giro")
        if month in (3, 9):
            m.txn(_ts(year, month, 20, 10, 0), "C-10077", acct, "in", 1850, "Dividend", "DIV-01", "dividend", channel="giro")
        last = 15 if (year, month) == (2026, 10) else 28
        for _ in range(rng.randint(12, 17)):
            party = rng.choice((("Lion City Power", "UTIL-01"), ("Lim Wen Hui", "017-442093"), ("Fairprice Online", "MER-77"),
                                ("Town Council", "UTIL-03"), ("Clinic Harmony", "MER-31"), ("Lim Jia Le", "031-882614")))
            m.txn(_ts(year, month, rng.randint(1, last), rng.randint(8, 20), rng.randint(0, 59)), "C-10077", acct, "out",
                  round(rng.uniform(25, 600), 2), *party, "")
    m.customers.append({"customer_id": "C-19102", "name": "Zenith Digital Trading", "segment": "Business", "cohort": "new",
                        "age": None, "city": "Singapore", "tenure_years": 0, "occupation": "Not stated", "monthly_income": None})
    mule = m.account("Zenith Digital Trading", customer_id="C-19102", opened="2026-10-05", account_id="078-220014", kind="business", balance=180)
    for victim, ts, amount in zip(victims, ("2026-10-08T02:20:00+08:00", "2026-10-11T03:05:00+08:00", "2026-10-13T01:47:00+08:00"),
                                  (9800, 15500, 21000)):
        m.txn(ts, victim, m.account_of[victim], "out", amount, "Zenith Digital Trading", mule, "invoice")
        m.txn(ts, "C-19102", mule, "in", amount, "Harbourline customer", m.account_of[victim], "invoice")
        out_ts = datetime.fromisoformat(ts) + timedelta(minutes=9)
        m.txn(out_ts.isoformat(), "C-19102", mule, "out", amount - 15, "Bitvault Exchange", "VASP-7731", "top up", channel="fast")
    m.txn("2026-10-16T03:12:00+08:00", "C-10077", acct, "out", 24000, "Zenith Digital Trading", mule, "invoice 2210",
          status="pending", alert_ref="HL-4437:T1", txn_id="HL-4437:T1")


_CASE_CUSTOMERS = (
    ("C-10021", "Priya Nair", "Everyday", "salaried", 34, 6, "School administrator", 4300),
    ("C-10388", "Pemba Sherpa", "Everyday", "np_remit", 41, 9, "Site supervisor", 4800),
    ("C-10544", "Meera Iyer", "Priority", "retiree", 67, 11, "Retired teacher", 3200),
    ("C-20017", "Northspan Metals Pte Ltd", "Trade", "trader", None, 7, "Non-ferrous metal trader", 900000),
    ("C-30112", "Arun Dela Cruz", "Everyday", "salaried", 38, 3, "Fleet coordinator", 3600),
    ("C-20231", "Lumen Studio Pte Ltd", "Business", "business", None, 5, "Design studio", 230000),
    ("C-10902", "Alex Tan Wei Ming", "Everyday", "salaried", 31, 4, "Product manager", 9900),
    ("C-10077", "Grace Lim", "Priority", "retiree", 72, 19, "Retired pharmacist", 2900),
)


@lru_cache(maxsize=1)
def build() -> dict[str, list]:
    """Generate the mart once per process. Same seed, same rows."""
    m = _Mart()
    by_cohort = _background(m)
    rng = random.Random(SEED + 1)
    salaried = by_cohort["salaried"]
    retirees = by_cohort["retiree"]
    for cid, name, segment, cohort, age, tenure, occupation, income in _CASE_CUSTOMERS:
        m.customers.append({"customer_id": cid, "name": name, "segment": segment, "cohort": cohort, "age": age,
                            "city": "Singapore", "tenure_years": tenure, "occupation": occupation, "monthly_income": income})
    _priya_and_the_mule(m, rng.sample(salaried, 4))
    _pemba(m)
    _meera(m, rng.sample(retirees, 2))
    _northspan(m)
    _arun(m)
    _lumen(m)
    _alex(m, rng.sample(salaried, 3))
    _grace_and_the_takeover(m, rng.sample(salaried + retirees, 3))
    for party, account, bank in (("Anita Sherpa", "KUB 0044192", "Kathmandu Union Bank"), ("Jonathan Wei", "SMB 2291", "Straits Mutual Bank"),
                                 ("Tondo Cash Pickup", "cash-4401", "cash agent, Manila"), ("QuickWallet PH", "wallet-88", "e-wallet, Philippines"),
                                 ("Kinabalu Commercials", "Labuan 7712", "Labuan offshore bank"), ("Andes Refining SAC", "Callao 30019", "Callao"),
                                 ("Larchfield Software GmbH", "DE89 3704 XXXX", "Berlin"), ("Bitvault Exchange", "VASP-7731", "virtual asset provider")):
        opened = {"Labuan 7712": "2026-09-08", "SMB 2291": "2026-10-14", "cash-4401": "2026-10-14"}.get(account)
        m.account(party, bank=bank, opened=opened, kind="external", account_id=account)
    m.txns.sort(key=lambda row: row[1])
    return {"customers": m.customers, "accounts": m.accounts, "transactions": m.txns}


def stats() -> dict[str, int]:
    mart = build()
    return {name: len(rows) for name, rows in mart.items()}
