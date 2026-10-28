from __future__ import annotations

import logging
import os
from datetime import date
from typing import Any

import pytest

from desk.model import Customer, customer_from, load_portfolio

TODAY = date(2026, 10, 28)

for noisy in ("httpx", "httpx2", "mcp"):
    logging.getLogger(noisy).setLevel(logging.WARNING)


def make(uc: dict[str, Any] | None = None, **customer: Any) -> Customer:
    """A one-use-case customer with sensible defaults, overridable per test."""
    base_uc = {
        "id": "uc",
        "title": "t",
        "pattern": "knowledge_assistant",
        "mission": "m",
        "stage": "qualified",
        "owner": "o",
        "users": "staff",
        "data": ["internal"],
    }
    raw = {
        "id": "c",
        "name": "Customer",
        "level": "land",
        "land": "by",
        "buyer": "other",
        "mission_priorities": [],
        "reviewers": {},
        "use_cases": [{**base_uc, **(uc or {})}],
        **customer,
    }
    return customer_from(raw)


@pytest.fixture(scope="session")
def portfolio() -> list[Customer]:
    return load_portfolio()


@pytest.fixture(scope="session")
def dsn() -> str:
    url = os.environ.get("DESK_TEST_DATABASE_URL")
    if not url:
        pytest.skip("DESK_TEST_DATABASE_URL not set")
    return url
