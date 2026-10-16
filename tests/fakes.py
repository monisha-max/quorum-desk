"""A stand-in for Gemini that plays each seat from the authored standby brief.

It behaves like the real model at the ADK boundary: it reads the seat from the
instruction and the file from the prompt, calls the seat's tools first, streams
a thought and the JSON answer in chunks, and can be told to fail or stall for
chosen seats.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncGenerator

from google.adk.models._capabilities import LlmCapabilities
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

from quorum import standby
from quorum.cases import get_alert

_SEAT = [
    ("You are the Clerk", "clerk"),
    ("You are the Ledger", "ledger"),
    ("You are the Archivist", "archivist"),
    ("You are the Statute", "statute"),
    ("You are the Prosecutor, answering", "prosecutor_rebuttal"),
    ("You are Counsel, answering", "counsel_rebuttal"),
    ("You are the Prosecutor", "prosecutor"),
    ("You are Counsel for the customer", "counsel"),
    ("You are the Magistrate", "magistrate"),
    ("You are the Liaison", "liaison"),
]


class ModelDown(Exception):
    """Carries a status code the way google-genai errors do."""

    def __init__(self, code: int = 429) -> None:
        super().__init__(f"{code} RESOURCE_EXHAUSTED")
        self.code = code


class FakeGemini(BaseLlm):
    model: str = "fake-gemini"
    fail: set[str] = set()
    stall: set[str] = set()
    overrides: dict[str, dict] = {}
    tool_overrides: dict[str, list] = {}
    calls: list[str] = []

    @property
    def capabilities(self) -> LlmCapabilities:
        return LlmCapabilities(output_schema_and_tools=True)

    def seat_of(self, req: LlmRequest) -> str:
        text = str(req.config.system_instruction or "")
        return next(seat for marker, seat in _SEAT if marker in text)

    async def generate_content_async(self, req: LlmRequest, stream: bool = False) -> AsyncGenerator[LlmResponse, None]:
        seat = self.seat_of(req)
        self.calls.append(seat)
        if seat in self.fail:
            raise ModelDown()
        if seat in self.stall:
            await asyncio.sleep(3600)
        prompt = "\n".join(part.text or "" for content in req.contents for part in content.parts or [] if content.role == "user")
        alert = get_alert(re.search(r"(?:ALERT|FILE) (HL-[\w-]+)", prompt).group(1))
        answered = any(part.function_response for content in req.contents for part in content.parts or [])
        calls = (self.tool_overrides.get(seat) or self._tool_calls(seat, alert)) if not answered else []
        if calls:
            yield LlmResponse(content=types.Content(role="model", parts=[
                types.Part(function_call=types.FunctionCall(id=f"call-{seat}-{i}", name=name, args=args))
                for i, (name, args) in enumerate(calls)
            ]))
            return
        out = self.overrides.get(seat) or standby.brief(alert, seat) or self._default(seat, alert)
        text = json.dumps(out, ensure_ascii=False)
        thought = f"Weighing the {seat} evidence on {alert['id']}."
        if stream:
            yield LlmResponse(content=types.Content(role="model", parts=[types.Part(text=thought, thought=True)]), partial=True)
            for start in range(0, len(text), 80):
                yield LlmResponse(content=types.Content(role="model", parts=[types.Part(text=text[start:start + 80])]), partial=True)
        yield LlmResponse(content=types.Content(role="model", parts=[types.Part(text=thought, thought=True), types.Part(text=text)]))

    @staticmethod
    def _tool_calls(seat: str, alert: dict) -> list[tuple[str, dict]]:
        if seat == "ledger":
            return standby.ledger_calls(alert)
        if seat == "archivist":
            return [("read_file", {})]
        if seat == "statute":
            return [("search_policy", {"query": standby.STANDBY.get(alert["id"], {}).get("policy_query", alert["rule"])})]
        return []

    @staticmethod
    def _default(seat: str, alert: dict) -> dict:
        if seat == "liaison":
            message = standby.brief(alert, "magistrate")["customer_message"]
            return {"language": "en", "message": message, "english": message}
        side = seat.removesuffix("_rebuttal")
        opening = standby.brief(alert, side)
        return {"position": opening["position"], "answer": "The opening stands.", "facts": opening["facts"], "moved": False}
