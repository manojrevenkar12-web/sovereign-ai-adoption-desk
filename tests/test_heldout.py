"""Blind sets: first runs are pinned to the exact files they ran on and never rewritten."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from desk.evals import sha

SETS = sorted(p.name for p in Path("heldout").iterdir() if p.is_dir())


@pytest.mark.parametrize("name", SETS)
def test_first_run_is_pinned_to_the_set(name: str) -> None:
    first = Path("reports/heldout") / name / "first_run.json"
    assert first.exists(), f"{name} has never been run"
    rec = json.loads(first.read_text())
    assert rec["sha256"] == sha(Path("heldout") / name), f"{name} changed after its first run"
    assert rec["status_at_first_run"] == "blind"


@pytest.mark.parametrize("name", SETS)
def test_status_is_declared(name: str) -> None:
    assert (Path("heldout") / name / "STATUS").read_text().strip() in ("blind", "regression")


def test_no_safety_failure_in_any_first_run() -> None:
    for name in SETS:
        r = json.loads((Path("reports/heldout") / name / "first_run.json").read_text())
        if r["kind"] == "gates":
            assert r["under_classified"] == []
        else:
            assert r["enquiries"]["eligibility_statements"] == 0
            assert r["enquiries"]["identifiers_seen_by_model"] == 0
            assert r["anfragen"]["ceiling_breaches"] == 0
