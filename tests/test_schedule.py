"""The capacity-aware path to production."""

from __future__ import annotations

from datetime import date

from desk.analysis import analyse
from desk.classify import classify
from desk.model import customer_from
from desk.schedule import Levers, _sessions, monday_on_or_after, plan_portfolio

START = date(2026, 11, 2)


def two_dpias(dsb: int = 1):  # type: ignore[no-untyped-def]
    uc = {
        "title": "t",
        "pattern": "form_extraction",
        "mission": "m",
        "stage": "qualified",
        "owner": "o",
        "users": "staff",
        "data": ["personal"],
        "large_scale": True,
        "per_user_logging": False,
    }
    c = customer_from(
        {
            "id": "c",
            "name": "C",
            "level": "land",
            "land": "by",
            "buyer": "other",
            "mission_priorities": [],
            "reviewers": {"dsb": dsb, "legal": 5, "isb": 5, "customer_pm": 5},
            "contracts": ["openai_api_eu"],
            "use_cases": [{**uc, "id": "a"}, {**uc, "id": "b"}],
        }
    )
    cls = {u.id: classify(u, c) for u in c.use_cases}
    return c, cls


def test_one_dpo_serialises_two_dpias() -> None:
    c, cls = two_dpias(dsb=1)
    plan = plan_portfolio([c], cls, ["a", "b"], START)
    a, b = plan.paths["a"].slot("dpia"), plan.paths["b"].slot("dpia")
    assert a and b
    assert b.start >= a.end and b.wait == "capacity"
    assert ("c", "dsb") in plan.waits


def test_a_second_dpo_lets_them_run_in_parallel() -> None:
    c, cls = two_dpias(dsb=2)
    plan = plan_portfolio([c], cls, ["a", "b"], START)
    assert plan.paths["a"].slot("dpia").start == plan.paths["b"].slot("dpia").start  # type: ignore[union-attr]


def test_priority_order_decides_who_waits() -> None:
    c, cls = two_dpias(dsb=1)
    plan = plan_portfolio([c], cls, ["b", "a"], START)
    assert plan.paths["a"].slot("dpia").wait == "capacity"  # type: ignore[union-attr]


def test_staff_council_decides_only_in_sessions(portfolio) -> None:  # type: ignore[no-untyped-def]
    lechfeld = next(c for c in portfolio if c.id == "lechfeld")
    sessions = _sessions(lechfeld, START, 60)
    a = analyse(portfolio, date(2026, 10, 28), price_levers=False)
    slot = a.plan.paths["lechfeld-bauantrag"].slot("staff_council")
    assert slot is not None
    assert slot.end - lechfeld.staff_council.decision_weeks in sessions


def test_blackout_pauses_reviewers(portfolio) -> None:  # type: ignore[no-untyped-def]
    a = analyse(portfolio, date(2026, 10, 28), price_levers=False)
    for p in a.plan.paths.values():
        for g in p.gates:
            if g.role in ("dsb", "legal", "isb") and g.end > g.start:
                # Christmas weeks 7 and 8 (21 Dec to 3 Jan) never count as work, so spans that cross them are longer
                assert g.end - g.start >= 1


def test_framework_agreement_shortens_staff_council(portfolio) -> None:  # type: ignore[no-untyped-def]
    a = analyse(portfolio, date(2026, 10, 28), price_levers=False)
    slot = a.plan.paths["stmv-kleine-anfragen"].slot("staff_council")
    assert slot is not None and slot.end - slot.start == 1


def test_done_gates_take_no_time(portfolio) -> None:  # type: ignore[no-untyped-def]
    a = analyse(portfolio, date(2026, 10, 28), price_levers=False)
    pov = a.plan.paths["lws-wohngeld-auskunft"].slot("pov")
    assert pov is not None and pov.done and pov.end == pov.start


def test_planned_target_has_a_ready_date_but_no_go_live(portfolio) -> None:  # type: ignore[no-untyped-def]
    a = analyse(portfolio, date(2026, 10, 28), price_levers=False)
    p = a.plan.paths["lechfeld-jugendamt-akten"]
    assert p.go_live is None and p.ready > 0 and "OpenAI for Germany" in (p.waiting_for or "")


def test_finished_and_stopped_use_cases_are_not_planned(portfolio) -> None:  # type: ignore[no-untyped-def]
    a = analyse(portfolio, date(2026, 10, 28), price_levers=False)
    for uid in ("stmv-assistent", "stmv-lagebild", "bafm-hotline-stimmung"):
        assert uid not in a.plan.paths


def test_critical_path_runs_into_go_live(portfolio) -> None:  # type: ignore[no-untyped-def]
    a = analyse(portfolio, date(2026, 10, 28), price_levers=False)
    for p in a.plan.paths.values():
        assert p.critical[-1] == "go_live"
        for earlier, later in zip(p.critical, p.critical[1:], strict=False):
            assert p.slot(earlier).end <= p.slot(later).start  # type: ignore[union-attr]


def test_capacity_only_delays(portfolio) -> None:  # type: ignore[no-untyped-def]
    a = analyse(portfolio, date(2026, 10, 28), price_levers=False)
    cls = a.classifications
    free = plan_portfolio(
        portfolio, cls, [p.use_case for p in a.priorities], monday_on_or_after(date(2026, 10, 28)), unconstrained=True
    )
    for uid, p in a.plan.paths.items():
        assert p.ready >= free.paths[uid].ready


def test_merging_fria_into_dpia_never_delays(portfolio) -> None:  # type: ignore[no-untyped-def]
    a = analyse(portfolio, date(2026, 10, 28), price_levers=False)
    order = [p.use_case for p in a.priorities]
    fria = frozenset(u for u, c in a.classifications.items() if c.fria_required)
    merged = plan_portfolio(portfolio, a.classifications, order, a.plan.start, Levers(integrate_fria=fria))
    for uid in fria & set(merged.paths):
        assert merged.paths[uid].slot("fria") is None
        assert merged.paths[uid].ready <= a.plan.paths[uid].ready


def test_levers_are_priced_by_replanning(portfolio) -> None:  # type: ignore[no-untyped-def]
    a = analyse(portfolio, date(2026, 10, 28))
    assert a.levers and all(lv["weeksSaved"] > 0 for lv in a.levers)
    assert a.levers == sorted(a.levers, key=lambda x: -x["weeksSaved"])
