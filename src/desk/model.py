"""The portfolio: customers (public bodies) and their AI use cases, as discovery records them.

Field names follow the discovery questionnaire in docs/DISCOVERY.md. Unknown fields are rejected,
so a typo in a portfolio file fails loudly instead of silently changing a classification.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from desk import settings

DECISION_ROLES = (
    "information",  # informs people, no decision about an individual
    "procedural",  # Art. 6(3)(a)
    "improves_completed_human_work",  # Art. 6(3)(b)
    "pattern_detection",  # Art. 6(3)(c)
    "preparatory",  # Art. 6(3)(d)
    "materially_influences",  # a person decides, but the output shapes the outcome
    "decides",  # the system decides
)
USERS = ("staff", "public", "both")


class PortfolioError(ValueError):
    pass


def _build(cls: type, raw: dict[str, Any], where: str) -> Any:
    names = {f.name for f in fields(cls)}
    unknown = set(raw) - names
    if unknown:
        raise PortfolioError(f"{where}: unknown fields {sorted(unknown)}")
    return cls(**raw)


@dataclass(frozen=True)
class Blocker:
    text: str
    since: date
    owner: str


@dataclass(frozen=True)
class StaffCouncil:
    weekday: int = 2  # sessions on the first <weekday> of the month (0 = Monday)
    skip_months: tuple[int, ...] = (8,)
    decision_weeks: int = 2  # after the session, until the decision is on paper
    framework_agreement: bool = False  # an AI framework agreement already covers new tools


@dataclass(frozen=True)
class UseCase:
    id: str
    customer: str
    title: str
    pattern: str
    mission: str
    stage: str
    owner: str
    users: str
    data: tuple[str, ...]
    decision_role: str = "information"
    purpose_area: str = "none"
    mission_weight: str = "normal"
    staff_users: int = 0
    cases_per_year: int = 0
    minutes_per_case: float = 0.0
    profiling: bool = False
    prohibited: tuple[str, ...] = ()
    publishes_public_interest_text: bool = False
    editorial_review: bool = False
    automated_decision: bool = False
    per_user_logging: bool = True
    large_scale: bool = False
    vulnerable_subjects: bool = False
    matching_datasets: bool = False
    systematic_monitoring: bool = False
    contract_value_eur: int = 0
    target_preference: str = ""
    pov: str = ""
    done: tuple[str, ...] = ()  # gates already passed
    decision_criteria: tuple[str, ...] = ()
    success_measures: tuple[str, ...] = ()
    blockers: tuple[Blocker, ...] = ()

    def __post_init__(self) -> None:
        where = f"use case {self.id}"
        p = settings.portfolio()
        if self.stage not in p["stages"]:
            raise PortfolioError(f"{where}: unknown stage {self.stage!r}")
        if self.pattern not in p["patterns"]:
            raise PortfolioError(f"{where}: unknown pattern {self.pattern!r}")
        if self.users not in USERS:
            raise PortfolioError(f"{where}: users must be one of {USERS}")
        if self.decision_role not in DECISION_ROLES:
            raise PortfolioError(f"{where}: decision_role must be one of {DECISION_ROLES}")
        act = settings.ai_act()
        if self.purpose_area != "none" and self.purpose_area not in act["annex_iii"]:
            raise PortfolioError(f"{where}: unknown purpose_area {self.purpose_area!r}")
        for pr in self.prohibited:
            if pr not in act["prohibited"]:
                raise PortfolioError(f"{where}: unknown prohibited practice {pr!r}")
        classes = settings.targets()["data_classes"]
        for d in self.data:
            if d not in classes:
                raise PortfolioError(f"{where}: unknown data class {d!r}")
        for g in self.done:
            if g not in settings.gates()["gates"]:
                raise PortfolioError(f"{where}: unknown gate in done: {g!r}")
        if self.mission_weight not in p["priority"]["mission_weight"]:
            raise PortfolioError(f"{where}: unknown mission_weight {self.mission_weight!r}")

    @property
    def staff_facing(self) -> bool:
        return self.users in ("staff", "both")

    @property
    def citizen_facing(self) -> bool:
        return self.users in ("public", "both")

    @property
    def hours_per_year(self) -> float:
        return self.cases_per_year * self.minutes_per_case / 60.0


@dataclass(frozen=True)
class Customer:
    id: str
    name: str
    level: str  # bund | land | kommune
    land: str  # bund | by | ... (decides the staff representation statute)
    buyer: str  # central_government | other (procurement threshold)
    mission_priorities: tuple[str, ...]
    reviewers: dict[str, int]
    staff_council: StaffCouncil = field(default_factory=StaffCouncil)
    blackouts: tuple[tuple[date, date], ...] = ()
    contracts: tuple[str, ...] = ()  # hosting targets already under contract
    framework_agreement: bool = False  # a call-off framework for AI services exists
    hosting_policy: dict[str, list[str]] = field(default_factory=dict)  # data class -> allowed targets
    seats: int = 0
    champions: dict[str, str] = field(default_factory=dict)  # department -> role of the champion
    stakeholders: tuple[str, ...] = ()
    use_cases: tuple[UseCase, ...] = ()


def _date(v: Any) -> date:
    return v if isinstance(v, date) else date.fromisoformat(str(v))


def _use_case(raw: dict[str, Any], customer: str) -> UseCase:
    raw = dict(raw)
    raw["customer"] = customer
    for k in ("data", "prohibited", "decision_criteria", "success_measures", "done"):
        if k in raw:
            raw[k] = tuple(raw[k])
    raw["blockers"] = tuple(
        _build(Blocker, {**b, "since": _date(b["since"])}, f"blocker of {raw.get('id')}")
        for b in raw.get("blockers", []) or []
    )
    return _build(UseCase, raw, f"use case {raw.get('id')}")


def customer_from(raw: dict[str, Any]) -> Customer:
    raw = dict(raw)
    cid = raw["id"]
    raw["use_cases"] = tuple(_use_case(u, cid) for u in raw.get("use_cases", []) or [])
    if "staff_council" in raw:
        sc = dict(raw["staff_council"])
        if "skip_months" in sc:
            sc["skip_months"] = tuple(sc["skip_months"])
        raw["staff_council"] = _build(StaffCouncil, sc, f"{cid} staff_council")
    raw["blackouts"] = tuple((_date(b[0]), _date(b[1])) for b in raw.get("blackouts", []) or [])
    for k in ("mission_priorities", "contracts", "stakeholders"):
        if k in raw:
            raw[k] = tuple(raw[k])
    c: Customer = _build(Customer, raw, f"customer {cid}")
    if c.level not in ("bund", "land", "kommune"):
        raise PortfolioError(f"customer {cid}: level must be bund, land or kommune")
    if c.buyer not in ("central_government", "other"):
        raise PortfolioError(f"customer {cid}: buyer must be central_government or other")
    roles = settings.gates()["roles"]
    for role in c.reviewers:
        if role not in roles:
            raise PortfolioError(f"customer {cid}: unknown reviewer role {role!r}")
    return c


def raw_portfolio(directory: Path | None = None) -> list[dict[str, Any]]:
    d = directory or settings.DATA_DIR / "portfolio"
    return [yaml.safe_load(f.read_text(encoding="utf-8")) for f in sorted(d.glob("*.yaml"))]


def load_portfolio(directory: Path | None = None) -> list[Customer]:
    out = [customer_from(r) for r in raw_portfolio(directory)]
    check_unique(out)
    return out


def check_unique(out: list[Customer]) -> None:
    ids = [u.id for c in out for u in c.use_cases]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise PortfolioError(f"duplicate use case ids: {sorted(dupes)}")
