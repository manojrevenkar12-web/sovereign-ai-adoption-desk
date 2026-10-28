"""Account health: is the customer getting value, and what should happen this week if not.

Usage comes from the workspace's weekly usage export, normalised to the columns in
docs/USAGE_EXPORT.md. Delivery comes from the desk itself (aged blockers, expiring approvals). Every
alert names the team that executes the intervention; the architect stays accountable.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from desk import settings
from desk.approval import Approval
from desk.model import Customer


@dataclass(frozen=True)
class WeekRow:
    week: date
    department: str
    seats: int
    active: int
    messages: int


@dataclass
class Health:
    customer: str
    score: int
    band: str  # healthy | watch | at_risk
    components: dict[str, float | None]
    activation: float | None
    momentum: float | None
    departments: list[dict[str, Any]]
    trend: list[dict[str, Any]]
    alerts: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "customer": self.customer,
            "score": self.score,
            "band": self.band,
            "components": {k: (round(v, 3) if v is not None else None) for k, v in self.components.items()},
            "activation": round(self.activation, 3) if self.activation is not None else None,
            "momentum": round(self.momentum, 3) if self.momentum is not None else None,
            "departments": self.departments,
            "trend": self.trend,
            "alerts": self.alerts,
        }


def load_usage(customer: str, directory: Path | None = None) -> list[WeekRow]:
    path = (directory or settings.DATA_DIR / "usage") / f"{customer}.csv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [
            WeekRow(
                date.fromisoformat(r["week"]),
                r["department"],
                int(r["seats"]),
                int(r["weekly_active_users"]),
                int(r["messages"]),
            )
            for r in csv.DictReader(f)
        ]


def _clip(x: float) -> float:
    return max(0.0, min(1.0, x))


def health(c: Customer, rows: list[WeekRow], approvals: dict[str, Approval], today: date) -> Health:
    cfg = settings.health()
    win = int(cfg["window_weeks"])
    tgt = cfg["targets"]
    al = cfg["alerts"]
    weeks = sorted({r.week for r in rows if r.week <= today})
    alerts: list[dict[str, Any]] = []
    due = (today + timedelta(days=14)).isoformat()

    def act(ws: list[date], dep: str | None = None) -> float | None:
        sel = [r for r in rows if r.week in ws and (dep is None or r.department == dep)]
        seats = sum(r.seats for r in sel)
        return sum(r.active for r in sel) / seats if seats else None

    last, prev = weeks[-win:], weeks[-2 * win : -win]
    activation = act(last) if last else None
    before = act(prev) if prev else None
    momentum = (activation - before) / before if activation is not None and before else None
    by_dep: dict[str, list[WeekRow]] = defaultdict(list)
    for r in rows:
        if r.week in last:
            by_dep[r.department].append(r)
    departments: list[dict[str, Any]] = []
    for dep, rs in sorted(by_dep.items()):
        a = act(last, dep) or 0.0
        p = act(prev, dep)
        m = (a - p) / p if p else None
        active = sum(r.active for r in rs)
        departments.append(
            {
                "department": dep,
                "seats": rs[-1].seats,
                "activation": round(a, 3),
                "momentum": round(m, 3) if m is not None else None,
                "messagesPerActive": round(sum(r.messages for r in rs) / active, 1) if active else 0.0,
                "champion": c.champions.get(dep) or None,
            }
        )
    trend = []
    for w in weeks:
        sel = [r for r in rows if r.week == w]
        seats = sum(r.seats for r in sel)
        trend.append(
            {"week": w.isoformat(), "activation": round(sum(r.active for r in sel) / seats, 3) if seats else None}
        )

    comps: dict[str, float | None] = {}
    if activation is not None:
        comps["activation"] = _clip(activation / float(tgt["activation"]))
        floor = float(al["momentum_floor"])
        comps["momentum"] = _clip(((momentum or 0.0) - floor) / (float(tgt["momentum"]) - floor))
        comps["breadth"] = (
            (sum(d["activation"] >= float(tgt["department_active_share"]) for d in departments) / len(departments))
            if departments
            else 0.0
        )
        msgs = sum(r.messages for r in rows if r.week in last)
        active = sum(r.active for r in rows if r.week in last)
        comps["depth"] = _clip((msgs / active if active else 0) / float(tgt["depth_messages_per_active"]))
    else:
        comps.update({"activation": None, "momentum": None, "breadth": None, "depth": None})

    open_ucs = [u for u in c.use_cases if u.stage not in ("production", "adopted", "not_pursued")]
    aged = [(u, b) for u in open_ucs for b in u.blockers if (today - b.since).days >= 7 * int(al["blocker_age_weeks"])]
    comps["delivery"] = 1.0 - (len({u.id for u, _ in aged}) / len(open_ucs)) if open_ucs else 1.0

    weights = cfg["score_weights"]
    have = {k: v for k, v in comps.items() if v is not None}
    total_w = sum(weights[k] for k in have)
    score = round(100 * sum(weights[k] * v for k, v in have.items()) / total_w) if total_w else 0
    band = "healthy" if score >= cfg["bands"]["healthy"] else ("watch" if score >= cfg["bands"]["watch"] else "at_risk")

    h = cfg["handoffs"]
    if activation is not None and activation < float(al["activation_floor"]):
        alerts.append(
            {
                "kind": "low_activation",
                "severity": "high",
                "handoff": h["enablement"],
                "due": due,
                "text": f"Only {activation:.0%} of seats active in the last {win} weeks.",
            }
        )
    if momentum is not None and momentum < float(al["momentum_floor"]):
        alerts.append(
            {
                "kind": "declining",
                "severity": "high",
                "handoff": h["account_director"],
                "due": due,
                "text": f"Activation fell {abs(momentum):.0%} window over window; agree a recovery plan with the sponsor.",
            }
        )
    for d in departments:
        if d["momentum"] is not None and d["momentum"] < float(al["momentum_floor"]):
            alerts.append(
                {
                    "kind": "department_declining",
                    "severity": "medium",
                    "handoff": h["enablement"],
                    "due": due,
                    "department": d["department"],
                    "text": f"{d['department']}: activation down {abs(d['momentum']):.0%} to {d['activation']:.0%}.",
                }
            )
        if al.get("department_without_champion") and not d["champion"]:
            alerts.append(
                {
                    "kind": "no_champion",
                    "severity": "medium",
                    "handoff": h["enablement"],
                    "due": due,
                    "department": d["department"],
                    "text": f"{d['department']} has no named champion ({d['activation']:.0%} active).",
                }
            )
    for u, b in aged:
        weeks_old = (today - b.since).days // 7
        alerts.append(
            {
                "kind": "aged_blocker",
                "severity": "high" if weeks_old >= 8 else "medium",
                "handoff": h["account_director"] if b.owner == "account_director" else h["deployment_eng"],
                "due": due,
                "useCase": u.id,
                "text": f"{u.title}: '{b.text}' open for {weeks_old} weeks (owner: {b.owner}).",
            }
        )
    for u in c.use_cases:
        appr = approvals.get(u.id)
        if appr is None:
            continue
        days = (appr.valid_until - today).days
        if days < 0:
            alerts.append(
                {
                    "kind": "approval_expired",
                    "severity": "high",
                    "handoff": h["security"],
                    "due": due,
                    "useCase": u.id,
                    "text": f"Approval {appr.id} expired {-days} days ago; the agent will refuse to run.",
                }
            )
        elif days <= int(al["approval_expiry_days"]):
            alerts.append(
                {
                    "kind": "approval_expiring",
                    "severity": "medium",
                    "handoff": h["security"],
                    "due": due,
                    "useCase": u.id,
                    "text": f"Approval {appr.id} expires in {days} days; start re-approval.",
                }
            )
    order = {"high": 0, "medium": 1, "low": 2}
    alerts.sort(key=lambda x: order[x["severity"]])
    return Health(c.id, score, band, comps, activation, momentum, departments, trend, alerts)
