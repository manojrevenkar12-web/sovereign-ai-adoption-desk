"""The rules in docs/RULES.md, one behaviour per test."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from desk.classify import classify
from desk.model import PortfolioError

from .conftest import make


def cl(uc: dict, **customer):  # type: ignore[no-untyped-def]
    c = make(uc, **customer)
    return classify(c.use_cases[0], c)


def test_prohibited_practice_stops_the_use_case() -> None:
    r = cl(
        {"prohibited": ["emotion_recognition_workplace"], "data": ["personal"], "decision_role": "pattern_detection"}
    )
    assert r.ai_act_class == "prohibited"
    assert ("prohibited", r.stops[0][1]) == r.stops[0]
    assert r.ai_act_basis == "Art. 5(1)(f)"


def test_materially_influencing_benefits_decision_is_high_risk_with_fria() -> None:
    r = cl(
        {
            "pattern": "eligibility_assessment",
            "purpose_area": "public_benefits",
            "decision_role": "materially_influences",
            "data": ["personal", "social"],
        }
    )
    assert r.ai_act_class == "high_risk"
    assert r.ai_act_basis == "Annex III(5)(a)"
    assert r.fria_required
    assert "provider_own_name" in r.roles
    assert any(d.article == "Art. 43" for d in r.duties)
    assert all(
        d.applies_from is not None and d.applies_from.isoformat() == "2027-12-02"
        for d in r.duties
        if d.article in ("Art. 43", "Art. 27")
    )


def test_procedural_role_is_not_high_risk_and_must_be_documented() -> None:
    r = cl(
        {
            "pattern": "form_extraction",
            "purpose_area": "public_benefits",
            "decision_role": "procedural",
            "data": ["personal"],
        }
    )
    assert r.ai_act_class == "not_high_risk"
    assert r.derogation == "procedural"
    assert {d.article for d in r.duties} >= {"Art. 6(4)", "Art. 49(2)"}
    assert r.facts["derogation"] and not r.fria_required


def test_profiling_rules_out_every_derogation() -> None:
    r = cl(
        {
            "pattern": "eligibility_assessment",
            "purpose_area": "employment",
            "decision_role": "preparatory",
            "profiling": True,
            "data": ["personal"],
        }
    )
    assert r.ai_act_class == "high_risk"
    assert r.derogation is None


def test_informing_system_in_an_annex_area_is_outside_it() -> None:
    r = cl(
        {
            "pattern": "enquiry_answering",
            "users": "public",
            "purpose_area": "public_benefits",
            "decision_role": "information",
            "data": ["public", "personal"],
        }
    )
    assert r.ai_act_class == "transparency"
    assert r.transparency == ("interacts_with_public",)


def test_informing_system_stays_inside_the_elections_area() -> None:
    r = cl(
        {
            "pattern": "enquiry_answering",
            "users": "public",
            "purpose_area": "elections",
            "decision_role": "information",
            "data": ["public"],
        }
    )
    assert r.ai_act_class == "high_risk"


def test_published_text_needs_disclosure_unless_editorially_reviewed() -> None:
    a = cl({"pattern": "records_summary", "data": ["public"], "publishes_public_interest_text": True})
    b = cl(
        {
            "pattern": "records_summary",
            "data": ["public"],
            "publishes_public_interest_text": True,
            "editorial_review": True,
        }
    )
    assert a.ai_act_class == "transparency" and a.transparency == ("publishes_public_interest_text",)
    assert b.ai_act_class == "minimal" and b.transparency == ()


@pytest.mark.parametrize(
    ("extra", "dpia"),
    [
        ({}, False),  # innovative technology alone
        ({"large_scale": True}, True),  # two criteria
        ({"data": ["personal", "social"]}, True),  # sensitive + innovative
        ({"data": ["internal"]}, False),  # no personal data, nothing counts
    ],
)
def test_dpia_counts_wp248_criteria(extra: dict, dpia: bool) -> None:  # type: ignore[type-arg]
    r = cl({"data": ["personal"], **extra})
    assert r.dpia_required is dpia


def test_art_35_3_case_needs_dpia_regardless_of_count() -> None:
    r = cl(
        {
            "data": ["personal"],
            "automated_decision": True,
            "profiling": True,
            "pattern": "eligibility_assessment",
            "decision_role": "decides",
        }
    )
    assert "automated_decision_legal_effect_with_profiling" in r.dpia_mandatory
    assert r.facts["automated_decision"]


def test_staff_council_statute_follows_the_land_and_logging() -> None:
    assert cl({"users": "staff"}, land="by").staff_council_statute == "Art. 75a Abs. 1 Nr. 1 BayPVG"
    assert cl({"users": "staff"}, land="bund", level="bund").staff_council_statute == "§ 80 Abs. 1 Nr. 21 BPersVG"
    assert cl({"users": "staff", "per_user_logging": False}).staff_council_statute is None
    assert cl({"users": "public", "pattern": "enquiry_answering", "data": ["public"]}).staff_council_statute is None


@pytest.mark.parametrize(
    ("buyer", "value", "route"),
    [
        ("central_government", 139_999, "national"),
        ("central_government", 140_000, "eu_procedure"),
        ("other", 215_999, "national"),
        ("other", 216_000, "eu_procedure"),
    ],
)
def test_procurement_threshold_boundaries(buyer: str, value: int, route: str) -> None:
    r = cl({"pattern": "form_extraction", "data": ["personal"], "contract_value_eur": value}, buyer=buyer)
    assert r.procurement_route == route


def test_contract_or_framework_shortens_procurement() -> None:
    assert (
        cl({"pattern": "form_extraction", "contract_value_eur": 900_000}, contracts=["openai_api_eu"]).procurement_route
        is None
    )
    assert (
        cl({"pattern": "form_extraction", "contract_value_eur": 900_000}, framework_agreement=True).procurement_route
        == "framework_call_off"
    )


def test_social_data_only_fits_the_planned_sovereign_target() -> None:
    r = cl({"pattern": "records_summary", "data": ["personal", "social"]})
    assert r.hosting.allowed == ("openai_for_germany",)
    assert r.hosting.chosen_status == "planned"
    assert r.facts["target_planned"] and not r.stops


def test_hosting_policy_can_leave_nothing() -> None:
    r = cl({"pattern": "form_extraction", "data": ["personal"]}, hosting_policy={"personal": ["chatgpt_enterprise_eu"]})
    assert r.hosting.chosen is None
    assert [k for k, _ in r.stops] == ["no_target"]


def test_classified_data_is_stopped() -> None:
    r = cl({"data": ["vs_nfd"]})
    assert [k for k, _ in r.stops] == ["classified"]


def test_codex_cannot_take_tax_data() -> None:
    r = cl({"pattern": "code_modernisation", "data": ["internal", "tax"]})
    assert r.hosting.chosen is None


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(PortfolioError):
        make({"decison_role": "information"})


def test_fictional_portfolio_classifies_as_designed(portfolio) -> None:  # type: ignore[no-untyped-def]
    got = {u.id: classify(u, c).ai_act_class for c in portfolio for u in c.use_cases}
    assert got["bafm-hotline-stimmung"] == "prohibited"
    assert got["lws-wohngeld-vorpruefung"] == "high_risk"
    assert got["bafm-bewerberauswahl"] == "high_risk"
    assert got["lws-vollstaendigkeit"] == "not_high_risk"
    assert got["lws-wohngeld-auskunft"] == "transparency"


def test_rules_never_ask_a_model() -> None:
    """Models read, rules decide: the deciding modules import no model client."""
    for mod in ("classify", "schedule", "priority", "architecture", "approval", "adoption"):
        tree = ast.parse(Path(f"src/desk/{mod}.py").read_text())
        names = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import | ast.ImportFrom) for a in n.names} | {
            n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
        }
        assert not any(x.startswith(("openai", "agents", "desk.pov")) for x in names), mod
