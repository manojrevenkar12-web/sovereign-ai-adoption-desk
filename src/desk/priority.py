"""Which use cases to push first: value, speed to production, reuse, and risk.

Value is hours saved per year. Before a proof of value measures it, the saving comes from the
pattern's assumed share (config/portfolio.yaml) and is labelled `projected`; afterwards from the
measured share, labelled `measured`. The two are never mixed silently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from desk import settings
from desk.classify import Classification
from desk.model import Customer


@dataclass(frozen=True)
class Priority:
    use_case: str
    score: float
    value_hours: float
    value_basis: str  # projected | measured
    speed_weeks: int | None
    reuse: int
    risk: float
    parts: dict[str, float]

    def as_dict(self) -> dict[str, Any]:
        return {
            "useCase": self.use_case,
            "score": round(self.score, 3),
            "hoursSavedPerYear": round(self.value_hours),
            "valueBasis": self.value_basis,
            "intrinsicWeeks": self.speed_weeks,
            "reuse": self.reuse,
            "risk": round(self.risk, 2),
            "parts": {k: round(v, 3) for k, v in self.parts.items()},
        }


def _scale(xs: dict[str, float]) -> dict[str, float]:
    if not xs:
        return {}
    lo, hi = min(xs.values()), max(xs.values())
    return {k: (v - lo) / (hi - lo) if hi > lo else 1.0 for k, v in xs.items()}


def rank(
    customers: list[Customer],
    classifications: dict[str, Classification],
    intrinsic_weeks: dict[str, int | None],
    measured_share: dict[str, float] | None = None,
) -> list[Priority]:
    """Score every open, unstopped use case; highest first."""
    cfg = settings.portfolio()
    pw = cfg["priority"]
    measured_share = measured_share or {}
    patterns_by_customer: dict[str, set[str]] = {}
    for c in customers:
        for u in c.use_cases:
            patterns_by_customer.setdefault(u.pattern, set()).add(c.id)
    value: dict[str, float] = {}
    basis: dict[str, str] = {}
    speed: dict[str, float] = {}
    reuse: dict[str, int] = {}
    risk: dict[str, float] = {}
    for c in customers:
        for u in c.use_cases:
            cl = classifications[u.id]
            if cl.stopped or u.stage in ("production", "adopted", "not_pursued"):
                continue
            share = measured_share.get(u.id)
            basis[u.id] = "measured" if share is not None else "projected"
            if share is None:
                share = float(cfg["patterns"][u.pattern]["time_saved_share"])
            value[u.id] = u.hours_per_year * share * float(pw["mission_weight"][u.mission_weight])
            weeks = intrinsic_weeks.get(u.id)
            speed[u.id] = 1.0 / (1.0 + (weeks if weeks is not None else 104) / 26.0)
            reuse[u.id] = len(patterns_by_customer[u.pattern]) - 1
            pts = pw["risk_points"]
            risk[u.id] = (
                (pts["high_risk"] if cl.ai_act_class == "high_risk" else 0)
                + (pts["derogation"] if cl.derogation else 0)
                + (pts["dpia"] if cl.dpia_required else 0)
                + (pts["automated_decision"] if cl.facts.get("automated_decision") else 0)
                + (pts["citizen_facing"] if u.citizen_facing else 0)
            )
    sv, ss, sr, sk = _scale(value), _scale(speed), _scale({k: float(v) for k, v in reuse.items()}), _scale(risk)
    out = []
    for uid in value:
        parts = {
            "value": sv[uid] * pw["w_value"],
            "speed": ss[uid] * pw["w_speed"],
            "reuse": sr[uid] * pw["w_reuse"],
            "risk": -sk[uid] * pw["w_risk"],
        }
        out.append(
            Priority(
                uid, sum(parts.values()), value[uid], basis[uid], intrinsic_weeks.get(uid), reuse[uid], risk[uid], parts
            )
        )
    return sorted(out, key=lambda p: (-p.score, p.use_case))
