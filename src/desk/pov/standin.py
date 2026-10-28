"""A deterministic stand-in for the model, so CI measures the whole agent pipeline for free.

It speaks the Responses item format through the Agents SDK `Model` interface: it calls the MCP
tools the agent was given and returns structured output that the agent's schema validates. Its
answers are extractive (whole retrieved sentences), so they show what retrieval, routing, scope
enforcement and verification do, not how well a frontier model writes. With OPENAI_API_KEY set
the same agents run on the model named in the approval instead.
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from typing import Any

from agents import Usage
from agents.items import ModelResponse
from agents.models.interface import Model
from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText

from desk import settings
from desk.pov.corpus import coverage, focus_missing

_cfg = settings.load("pov")["retrieval"]
ANSWER_FLOOR = float(_cfg["answer_floor"])
RELATIVE = float(_cfg["relative"])
MIN_COVERAGE = float(_cfg["min_coverage"])
QUESTION = re.compile(r"^\s*(\d{1,2})[.)]\s+(.+)$", re.M)


def _text_of(item: Any) -> str:
    c = item.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return " ".join(p.get("text", "") for p in c if isinstance(p, dict))
    return ""


def _output_text(o: Any) -> str:
    if isinstance(o, str):
        return o
    if isinstance(o, list):
        return "".join(p.get("text", "") for p in o if isinstance(p, dict))
    return str(o)


def _call(call_id: str, name: str, args: dict[str, Any]) -> ResponseFunctionToolCall:
    return ResponseFunctionToolCall(
        type="function_call",
        call_id=call_id,
        name=name,
        arguments=json.dumps(args, ensure_ascii=False),
        id=f"fc_{call_id}",
        status="completed",
    )


def _message(payload: dict[str, Any]) -> ResponseOutputMessage:
    return ResponseOutputMessage(
        id="msg_standin",
        type="message",
        role="assistant",
        status="completed",
        content=[ResponseOutputText(type="output_text", text=json.dumps(payload, ensure_ascii=False), annotations=[])],
    )


def _pick(question: str, passages: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Passages that answer the question, or none if the best ones do not cover what was asked."""
    if not passages or passages[0]["score"] < ANSWER_FLOOR:
        return []
    top = passages[0]["score"]
    chosen = [p for p in passages if p["score"] >= RELATIVE * top][:limit]
    texts = [p["title"] + " " + p["text"] for p in chosen]
    if coverage(question, texts) < MIN_COVERAGE or focus_missing(question, texts):
        return []
    return chosen


class StandInModel(Model):
    def __init__(self, kind: str):
        self.kind = kind  # "wohngeld" | "kleine_anfrage"

    async def get_response(
        self,
        system_instructions,
        input,
        model_settings,
        tools,
        output_schema,
        handoffs,  # type: ignore[no-untyped-def]
        tracing,
        *,
        previous_response_id,
        conversation_id,
        prompt,
    ) -> ModelResponse:
        items = input if isinstance(input, list) else [{"role": "user", "content": input}]
        user = next((_text_of(i) for i in reversed(items) if isinstance(i, dict) and i.get("role") == "user"), "")
        outputs = {
            i["call_id"]: _output_text(i["output"])
            for i in items
            if isinstance(i, dict) and i.get("type") == "function_call_output"
        }
        names = {t.name for t in tools}
        out = self._wohngeld(user, outputs, names) if self.kind == "wohngeld" else self._anfrage(user, outputs, names)
        return ModelResponse(output=out, usage=Usage(), response_id=None)

    def _wohngeld(self, user: str, outputs: dict[str, str], tools: set[str]) -> list[Any]:
        if "search" not in outputs:
            return [_call("search", "search_guidance", {"query": user})]
        if "handover" in outputs:
            return [
                _message(
                    {
                        "action": "handover",
                        "statements": [],
                        "handover_reason": "Die Hinweise beantworten diese Frage nicht sicher.",
                    }
                )
            ]
        try:
            passages = json.loads(outputs["search"]).get("passages", [])
        except json.JSONDecodeError:
            passages = []
        chosen = _pick(user, passages, 3)
        if not chosen:
            if "create_handover" in tools:
                return [_call("handover", "create_handover", {"reason": "no_guidance", "topic": user[:120]})]
            return [_message({"action": "handover", "statements": [], "handover_reason": "no_guidance"})]
        return [
            _message(
                {
                    "action": "answer",
                    "statements": [{"text": p["text"], "citations": [p["id"]]} for p in chosen],
                    "handover_reason": None,
                }
            )
        ]

    def _anfrage(self, user: str, outputs: dict[str, str], tools: set[str]) -> list[Any]:
        questions = [(int(n), q.strip()) for n, q in QUESTION.findall(user)]
        if not questions:
            questions = [(1, user.strip())]
        if not outputs:
            return [_call(f"q{n}", "search_records", {"query": q}) for n, q in questions]
        answers, units = [], []
        for n, q in questions:
            try:
                res = json.loads(outputs.get(f"q{n}", "{}"))
            except json.JSONDecodeError:
                res = {}
            chosen = _pick(q, res.get("passages", []), 2)
            if chosen:
                answers.append(
                    {
                        "question": n,
                        "status": "answered",
                        "statements": [{"text": p["text"], "citations": [p["id"]]} for p in chosen],
                    }
                )
                units += [p.get("unit", "") for p in chosen]
            elif res.get("withheld_documents"):
                answers.append({"question": n, "status": "withheld", "statements": []})
            else:
                answers.append({"question": n, "status": "no_record", "statements": []})
        return [_message({"answers": answers, "co_sign_units": sorted({u for u in units if u})})]

    def stream_response(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        raise NotImplementedError("the stand-in does not stream")
