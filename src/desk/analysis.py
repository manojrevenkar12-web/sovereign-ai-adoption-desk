"""One pass over the portfolio: classify, rank, plan under capacity, and price the levers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from desk.architecture import Architecture, design
from desk.classify import Classification, classify
from desk.model import Customer
from desk.priority import Priority, rank
from desk.schedule import Levers, PortfolioPlan, monday_on_or_after, plan_portfolio


@dataclass
class Analysis:
    customers: list[Customer]
    classifications: dict[str, Classification]
    priorities: list[Priority]
    plan: PortfolioPlan
    architectures: dict[str, Architecture]
    levers: list[dict[str, Any]]

    def customer(self, cid: str) -> Customer:
        return next(c for c in self.customers if c.id == cid)

    def priority(self, uid: str) -> Priority | None:
        return next((p for p in self.priorities if p.use_case == uid), None)


def _order(customers: list[Customer], priorities: list[Priority]) -> list[str]:
    ranked = [p.use_case for p in priorities]
    rest = [u.id for c in customers for u in c.use_cases if u.id not in ranked]
    return ranked + rest


def candidate_levers(
    customers: list[Customer], cls: dict[str, Classification], plan: PortfolioPlan
) -> list[tuple[str, Levers]]:
    """Levers worth pricing: one more reviewer wherever critical paths wait, a merged FRIA, framework call-offs."""
    from desk import settings

    roles = settings.gates()["roles"]
    names = {c.id: c.name for c in customers}
    out: list[tuple[str, Levers]] = []
    fria = frozenset(u for u, c in cls.items() if c.fria_required and c.dpia_required)
    if fria:
        out.append(("Run the FRIA as part of the DPIA (Art. 27(4) AI Act)", Levers(integrate_fria=fria)))
    for (cust, role), weeks in sorted(plan.waits.items()):
        if weeks <= 0:
            continue
        who = "across the portfolio" if cust == "portfolio" else f"at {names[cust]}"
        out.append(
            (
                f"One more {roles[role]['title']} {who}",
                Levers(extra_capacity=(("*" if cust == "portfolio" else cust, role, 1),)),
            )
        )
    for c in customers:
        if not c.framework_agreement and any(
            cl.procurement_route for cl in cls.values() if cl.use_case.customer == c.id
        ):
            out.append(
                (f"Call off from a framework agreement at {c.name}", Levers(framework_call_off=frozenset({c.id})))
            )
    return out


def analyse(
    customers: list[Customer],
    today: date,
    levers: Levers | None = None,
    measured_share: dict[str, float] | None = None,
    price_levers: bool = True,
) -> Analysis:
    start = monday_on_or_after(today)
    by_id = {u.id: (u, c) for c in customers for u in c.use_cases}
    cls = {uid: classify(u, c) for uid, (u, c) in by_id.items()}
    intrinsic_plan = plan_portfolio(customers, cls, list(by_id), start, levers, unconstrained=True)
    intrinsic: dict[str, int | None] = {uid: p.ready for uid, p in intrinsic_plan.paths.items()}
    priorities = rank(customers, cls, intrinsic, measured_share)
    order = _order(customers, priorities)
    plan = plan_portfolio(customers, cls, order, start, levers)
    archs = {uid: design(cl) for uid, cl in cls.items() if not cl.stopped}
    priced: list[dict[str, Any]] = []
    if price_levers:
        base = {uid: p.ready for uid, p in plan.paths.items()}
        for title, lever in candidate_levers(customers, cls, plan):
            alt = plan_portfolio(customers, cls, order, start, lever)
            gains = {uid: base[uid] - p.ready for uid, p in alt.paths.items() if base[uid] - p.ready > 0}
            if gains:
                priced.append({"lever": title, "weeksSaved": sum(gains.values()), "useCases": gains})
        priced.sort(key=lambda x: -x["weeksSaved"])
    return Analysis(customers, cls, priorities, plan, archs, priced)
