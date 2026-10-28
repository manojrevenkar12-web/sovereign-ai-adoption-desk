"""Structured outputs of the proof-of-value agents. Every statement carries its citations."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Statement(BaseModel):
    text: str = Field(description="One sentence in German, taken from or paraphrasing the cited passages only.")
    citations: list[str] = Field(description="Passage ids such as WG-03#2 that support the sentence.")


class EnquiryReply(BaseModel):
    action: Literal["answer", "handover"]
    statements: list[Statement]
    handover_reason: str | None = Field(description="Why a person must take over; null when answering.")


class DraftAnswer(BaseModel):
    question: int
    status: Literal["answered", "no_record", "withheld"]
    statements: list[Statement]


class AnfrageDraft(BaseModel):
    answers: list[DraftAnswer]
    co_sign_units: list[str] = Field(description="Units whose records were cited and who must co-sign.")
