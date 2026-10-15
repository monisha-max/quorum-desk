"""Six ADK agents. One desk. Gemini sits in every seat that speaks."""

from __future__ import annotations

import os

from google.adk.agents.llm_agent import Agent
from google.genai import types

from quorum.policy import search_policy
from quorum.warehouse import read_file, read_ledger

MODEL = os.environ.get("QUORUM_MODEL", "gemini-2.5-flash")

_JSON = (
    "Use only the tool results and the file in the message. "
    "If a fact is not there, say it is not in the file. "
    "Return one JSON object and no other text."
)


def _agent(name: str, description: str, instruction: str, tools: list) -> Agent:
    return Agent(
        name=name,
        model=MODEL,
        description=description,
        instruction=instruction,
        tools=tools,
        generate_content_config=types.GenerateContentConfig(temperature=0.2),
    )


def clerk() -> Agent:
    return _agent(
        "clerk",
        "Opens a Harbourline alert and says what the fight is about.",
        "You are the clerk of a financial-crime hearing. Call read_file first. "
        "Then return JSON with keys summary and question. summary is two sentences. "
        "question is the single issue the other seats must answer. " + _JSON,
        [read_file],
    )


def ledger() -> Agent:
    return _agent(
        "ledger",
        "Reads payments and says what moved.",
        "You are the ledger seat. Call read_ledger. Return JSON with keys "
        "finding and figures. finding is two sentences on what moved, to whom, "
        "and how that compares with history. figures is a short list of amounts "
        "copied from the tool. " + _JSON,
        [read_ledger],
    )


def archivist() -> Agent:
    return _agent(
        "archivist",
        "Reads KYC and documents, including notes an officer just added.",
        "You are the archivist. Call read_file. Return JSON with keys finding "
        "and documents. finding is two sentences. documents is a list of the "
        "ids you actually used. " + _JSON,
        [read_file],
    )


def statute() -> Agent:
    return _agent(
        "statute",
        "Retrieves the Harbourline policy passage that governs this file.",
        "You are the statute seat. Call search_policy with a short query drawn "
        "from the file. Return JSON with keys policy_ids and finding. Cite only "
        "ids the tool returned. finding says what the passage tells the desk to do. "
        + _JSON,
        [search_policy],
    )


def counsel() -> Agent:
    return _agent(
        "counsel",
        "Argues the legitimate explanation, against escalation.",
        "You speak for the customer. You are not a cheerleader for the bank. "
        "Read the seat notes in the message. Return JSON with keys argument and "
        "weakness. argument is the best honest reason this could be legitimate. "
        "weakness is the fact that still troubles you. Do not invent documents. "
        + _JSON,
        [],
    )


def magistrate() -> Agent:
    return _agent(
        "magistrate",
        "Writes the disposition, the customer note, and a SAR only when one is earned.",
        """You are the magistrate. You decide. The seats have already spoken.
Return JSON with these keys:
disposition: one of clear, hold, escalate, split
typology: short name
confidence: number from 0 to 1
false_positive: true only when the rule fired and the activity is legitimate
rationale: three sentences for the officer, citing the file
customer_message: plain language for the customer, no jargon, no accusation
citations: list of objects with source, ref, and point
sar_draft: a short suspicious-matter draft when disposition is escalate, otherwise an empty string
held_amount: what stays, or an empty string
released_amount: what goes, or an empty string
clear means release. hold means pause and talk to the customer. escalate means a person must file. split means release the clean part and hold the tainted part.
""" + _JSON,
        [],
    )
