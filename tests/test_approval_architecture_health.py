from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from desk.adoption import health, load_usage
from desk.approval import ApprovalError, compile_scope, load_all, problems
from desk.architecture import design
from desk.classify import classify

from .conftest import TODAY, make


def _by(portfolio):  # type: ignore[no-untyped-def]
    return {u.id: (u, c) for c in portfolio for u in c.use_cases}


def test_approvals_compile_into_scope(portfolio) -> None:  # type: ignore[no-untyped-def]
    apr = load_all()
    for uid, a in apr.items():
        u, c = _by(portfolio)[uid]
        s = compile_scope(a, classify(u, c), TODAY)
        assert set(s.tools) == set(a.tools)
    s = compile_scope(apr["lws-wohngeld-auskunft"], classify(*_by(portfolio)["lws-wohngeld-auskunft"]), TODAY)
    assert s.pseudonymise and s.ceiling_rank == 0 and "individual_eligibility" in s.forbidden


def test_expired_approval_refuses_to_compile(portfolio) -> None:  # type: ignore[no-untyped-def]
    a = load_all()["lws-wohngeld-auskunft"]
    with pytest.raises(ApprovalError, match="expired"):
        compile_scope(a, classify(*_by(portfolio)["lws-wohngeld-auskunft"]), date(2027, 5, 1))


def test_changed_discovery_answers_invalidate_the_approval(portfolio) -> None:  # type: ignore[no-untyped-def]
    a = load_all()["lws-wohngeld-auskunft"]
    u, c = _by(portfolio)["lws-wohngeld-auskunft"]
    grown = replace(u, decision_role="materially_influences")
    issues = problems(a, classify(grown, c), TODAY)
    assert any("discovery answers changed" in i for i in issues)
    assert any("now classifies as high_risk" in i for i in issues)


def test_target_that_cannot_take_the_data_is_refused(portfolio) -> None:  # type: ignore[no-untyped-def]
    a = replace(load_all()["lws-wohngeld-auskunft"], target="chatgpt_enterprise_eu")
    assert any("does not accept" in i for i in problems(a, classify(*_by(portfolio)["lws-wohngeld-auskunft"]), TODAY))


def test_citizen_channel_architecture_hands_individual_cases_over(portfolio) -> None:  # type: ignore[no-untyped-def]
    arch = design(classify(*_by(portfolio)["lws-wohngeld-auskunft"]))
    layers = {c.layer for c in arch.components}
    assert {"channel", "model", "data", "identity", "security", "privacy", "governance", "evaluation"} <= layers
    assert any("hand over" in d.choice.lower() for d in arch.decisions)
    assert any("pseudonymised" in c.choice for c in arch.components)
    assert "Caseworker queue" in arch.mermaid


def test_high_risk_architecture_keeps_people_deciding(portfolio) -> None:  # type: ignore[no-untyped-def]
    arch = design(classify(*_by(portfolio)["lws-wohngeld-vorpruefung"]))
    assert "Art. 14" in arch.oversight
    assert any("six months" in c.choice for c in arch.components)


def test_planned_target_architecture_starts_on_synthetic_data() -> None:
    c = make({"pattern": "records_summary", "data": ["personal", "social"]})
    arch = design(classify(c.use_cases[0], c))
    assert any("synthetic" in d.choice for d in arch.decisions)


def test_health_flags_decline_and_missing_champions(portfolio) -> None:  # type: ignore[no-untyped-def]
    apr = load_all()
    hs = {c.id: health(c, load_usage(c.id), apr, TODAY) for c in portfolio}
    assert hs["bafm"].band in ("watch", "at_risk")
    kinds = {a["kind"] for a in hs["bafm"].alerts}
    assert {"declining", "no_champion"} <= kinds
    assert hs["lws"].band == "healthy"
    assert any(a["kind"] == "aged_blocker" for a in hs["stmv"].alerts)
    assert all(a["handoff"] for h in hs.values() for a in h.alerts)


def test_expiring_approval_is_an_alert(portfolio) -> None:  # type: ignore[no-untyped-def]
    c = next(c for c in portfolio if c.id == "lws")
    h = health(c, load_usage("lws"), load_all(), date(2027, 4, 1))
    assert any(a["kind"] == "approval_expiring" for a in h.alerts)
