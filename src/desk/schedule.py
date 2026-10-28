"""The path to production for a whole portfolio, under the reviewers' real capacity.

Each use case's gates form a dependency graph (config/gates.yaml). Gates are placed week by week in
priority order: a gate starts when its dependencies are done AND its reviewer has a free slot. A
customer's data protection officer reviewing three DPIAs at once is the usual reason a pilot slips,
and an architect who plans each use case on its own never sees it. The staff council decides only in
its sessions; blackout weeks (Christmas) stop customer reviewers but not the calendar.

Levers (what-if): merge the FRIA into the DPIA (Art. 27(4) AI Act), add reviewer capacity, use a
framework call-off. The desk recomputes the portfolio with each lever and reports the weeks saved.
"""

from __future__ import annotations

import calendar
from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from typing import Any

from desk import settings
from desk.classify import Classification
from desk.model import Customer, UseCase

FINISHED_STAGES = ("production", "adopted", "not_pursued")


@dataclass(frozen=True)
class Levers:
    integrate_fria: frozenset[str] = frozenset()  # use case ids
    extra_capacity: tuple[tuple[str, str, int], ...] = ()  # (customer or "*", role, +n)
    framework_call_off: frozenset[str] = frozenset()  # customer ids

    def capacity_delta(self, customer: str, role: str) -> int:
        return sum(n for c, r, n in self.extra_capacity if r == role and c in (customer, "*"))


@dataclass
class GateSlot:
    gate: str
    title: str
    role: str
    start: int  # week index
    end: int  # week index, exclusive
    ready: int  # week the dependencies allowed
    wait: str | None  # capacity | session | None
    deps: tuple[str, ...]
    done: bool = False
    source: str | None = None


@dataclass
class Path:
    use_case: str
    customer: str
    gates: list[GateSlot]
    go_live: int | None  # None while waiting for something without a date (a planned target)
    waiting_for: str | None
    ready: int = 0  # week every gate is passed; equals go_live unless waiting_for is set
    critical: list[str] = field(default_factory=list)

    def slot(self, gate: str) -> GateSlot | None:
        return next((g for g in self.gates if g.gate == gate), None)


@dataclass
class PortfolioPlan:
    start: date
    paths: dict[str, Path]
    waits: dict[tuple[str, str], int]  # (customer, role) -> weeks critical-path gates waited for that role

    def date_of(self, week: int) -> date:
        return self.start + timedelta(weeks=week)

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"start": self.start.isoformat(), "useCases": {}, "bottlenecks": []}
        for uid, p in self.paths.items():
            out["useCases"][uid] = {
                "goLive": self.date_of(p.go_live).isoformat() if p.go_live is not None else None,
                "goLiveWeek": p.go_live,
                "readyBy": self.date_of(p.ready).isoformat(),
                "readyWeek": p.ready,
                "waitingFor": p.waiting_for,
                "critical": p.critical,
                "gates": [
                    {
                        "gate": g.gate,
                        "title": g.title,
                        "role": g.role,
                        "start": self.date_of(g.start).isoformat(),
                        "end": (self.date_of(g.end) - timedelta(days=3)).isoformat()
                        if g.end > g.start
                        else self.date_of(g.start).isoformat(),
                        "startWeek": g.start,
                        "endWeek": g.end,
                        "waitedWeeks": g.start - g.ready,
                        "wait": g.wait,
                        "deps": list(g.deps),
                        "done": g.done,
                        "source": g.source,
                    }
                    for g in p.gates
                ],
            }
        for (cust, role), weeks in sorted(self.waits.items(), key=lambda x: -x[1]):
            if weeks > 0:
                out["bottlenecks"].append({"customer": cust, "role": role, "waitedWeeks": weeks})
        return out


def monday_on_or_after(d: date) -> date:
    return d + timedelta(days=(7 - d.weekday()) % 7)


def _sessions(c: Customer, start: date, weeks: int) -> list[int]:
    """Week indices of the staff council's sessions: the first <weekday> of each month."""
    sc = c.staff_council
    out = []
    y, m = start.year, start.month
    end = start + timedelta(weeks=weeks)
    while date(y, m, 1) <= end:
        if m not in sc.skip_months:
            first = date(y, m, 1)
            day = first + timedelta(days=(sc.weekday - first.weekday()) % 7)
            if day >= start:
                out.append((day - start).days // 7)
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out


def _blackout_weeks(c: Customer, start: date, weeks: int) -> set[int]:
    out: set[int] = set()
    for a, b in c.blackouts:
        for w in range(weeks):
            ws = start + timedelta(weeks=w)
            we = ws + timedelta(days=4)
            if ws <= b and we >= a:
                out.add(w)
    return out


def applicable_gates(cl: Classification, levers: Levers) -> dict[str, dict[str, Any]]:
    """The gates this use case must pass, with dependencies on non-applicable gates removed."""
    cfg = settings.gates()["gates"]
    facts = cl.facts
    out = {gid: dict(g) for gid, g in cfg.items() if facts.get(g["when"], False)}
    if cl.use_case.id in levers.integrate_fria and "fria" in out and "dpia" in out:
        extra = int(out["fria"].get("integrated_extra_weeks", 2))
        out["dpia"]["weeks"] = int(out["dpia"]["weeks"]) + extra
        out["dpia"]["title"] = "Integrated DPIA and fundamental rights impact assessment"
        out["dpia"]["source"] = "Art. 35 GDPR; Art. 27(4) AI Act"
        del out["fria"]
        for g in out.values():
            g["depends_on"] = ["dpia" if d == "fria" else d for d in g.get("depends_on", [])]
    for g in out.values():
        g["depends_on"] = list(dict.fromkeys(d for d in g.get("depends_on", []) if d in out))
    return out


def _order(gates: dict[str, dict[str, Any]]) -> list[str]:
    seen: list[str] = []
    temp: set[str] = set()

    def visit(g: str) -> None:
        if g in seen:
            return
        if g in temp:
            raise ValueError(f"cycle in gates at {g}")
        temp.add(g)
        for d in gates[g]["depends_on"]:
            visit(d)
        temp.discard(g)
        seen.append(g)

    for g in gates:
        visit(g)
    return seen


def _weeks_for(gid: str, g: dict[str, Any], cl: Classification, c: Customer, levers: Levers) -> int:
    if g["weeks"] == "route":
        route = cl.procurement_route
        if c.id in levers.framework_call_off:
            route = "framework_call_off"
        return int(settings.law()["procurement"]["routes"][route]["weeks"])
    if gid == "staff_council" and c.staff_council.framework_agreement:
        return 1
    return int(g["weeks"])


def plan_portfolio(
    customers: list[Customer],
    classifications: dict[str, Classification],
    order: list[str],
    start: date,
    levers: Levers | None = None,
    unconstrained: bool = False,
) -> PortfolioPlan:
    """Place every gate of every open use case, in `order` (highest priority first)."""
    levers = levers or Levers()
    cfg = settings.portfolio()["planning"]
    horizon = int(cfg["horizon_weeks"]) * 2
    gate_cfg = settings.gates()
    by_id: dict[str, tuple[UseCase, Customer]] = {u.id: (u, c) for c in customers for u in c.use_cases}
    usage: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0] * horizon)
    waits: dict[tuple[str, str], int] = defaultdict(int)
    blackouts = {c.id: _blackout_weeks(c, start, horizon) for c in customers}
    sessions = {c.id: _sessions(c, start, horizon) for c in customers}
    paths: dict[str, Path] = {}

    def capacity(c: Customer, role: str) -> int:
        if unconstrained:
            return 10**6
        if gate_cfg["roles"][role]["scope"] == "portfolio":
            base = int(cfg["deployment_eng_capacity"])
            return base + levers.capacity_delta("*", role)
        return int(c.reviewers.get(role, cfg["default_capacity"])) + levers.capacity_delta(c.id, role)

    for uid in order:
        uc, c = by_id[uid]
        cl = classifications[uid]
        if cl.stopped or uc.stage in FINISHED_STAGES:
            continue
        gates = applicable_gates(cl, levers)
        slots: dict[str, GateSlot] = {}
        for gid in _order(gates):
            g = gates[gid]
            deps = tuple(g["depends_on"])
            ready = max((slots[d].end for d in deps), default=0)
            source = g.get("source")
            if source in ("staff_council", "accessibility"):
                source = cl.staff_council_statute if source == "staff_council" else cl.accessibility_statute
            if gid in uc.done:
                slots[gid] = GateSlot(gid, g["title"], g["role"], ready, ready, ready, None, deps, True, source)
                continue
            weeks = _weeks_for(gid, g, cl, c, levers)
            role = g["role"]
            scope_key = "*" if gate_cfg["roles"][role]["scope"] == "portfolio" else c.id
            if role == "staff_council":
                prep_end = ready + weeks
                if c.staff_council.framework_agreement or unconstrained:
                    end, wait = prep_end, None
                else:
                    session = next(s for s in sessions[c.id] if s >= prep_end)
                    end = session + c.staff_council.decision_weeks
                    wait = "session" if session > prep_end else None
                slots[gid] = GateSlot(gid, g["title"], role, ready, end, ready, wait, deps, False, source)
                continue
            if weeks == 0:
                slots[gid] = GateSlot(gid, g["title"], role, ready, ready, ready, None, deps, False, source)
                continue
            cap = capacity(c, role)
            pauses = blackouts[c.id] if scope_key != "*" else set()
            s = ready
            while True:
                weeks_used: list[int] = []
                w = s
                while len(weeks_used) < weeks and w < horizon:
                    if w not in pauses:
                        if usage[(scope_key, role)][w] >= cap:
                            break
                        weeks_used.append(w)
                    w += 1
                if len(weeks_used) == weeks:
                    break
                s += 1
                if s >= horizon:
                    raise RuntimeError(f"{uid}/{gid}: no capacity within the horizon")
            for w in weeks_used:
                usage[(scope_key, role)][w] += 1
            slots[gid] = GateSlot(
                gid,
                g["title"],
                role,
                s,
                weeks_used[-1] + 1,
                ready,
                "capacity" if s > ready else None,
                deps,
                False,
                source,
            )
        path = Path(uid, c.id, list(slots.values()), None, None)
        path.ready = slots["go_live"].end
        path.go_live = path.ready
        if cl.facts.get("target_planned"):
            path.waiting_for = f"{cl.hosting.chosen} availability (planned)"
            path.go_live = None
        path.critical = _critical(slots)
        for gid in path.critical:
            cs = slots[gid]
            if cs.wait == "capacity":
                scope = "portfolio" if gate_cfg["roles"][cs.role]["scope"] == "portfolio" else c.id
                waits[(scope, cs.role)] += cs.start - cs.ready
        paths[uid] = path
    return PortfolioPlan(start, paths, dict(waits))


def _critical(slots: dict[str, GateSlot]) -> list[str]:
    """Walk back from go-live through the dependency that finished last."""
    out = []
    cur: GateSlot | None = slots["go_live"]
    while cur is not None:
        out.append(cur.gate)
        if not cur.deps:
            break
        last = max(cur.deps, key=lambda d: (slots[d].end, slots[d].end - slots[d].start))
        cur = slots[last]
    return list(reversed(out))


def session_dates(c: Customer, start: date, count: int = 6) -> list[date]:
    return [start + timedelta(weeks=w) for w in _sessions(c, start, 60)][:count]


def month_name(d: date) -> str:
    return f"{calendar.month_abbr[d.month]} {d.year}"


def with_lever(levers: Levers, **kw: Any) -> Levers:
    return replace(levers, **kw)
