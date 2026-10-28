"""Approval records, and the scope they compile into for the running agent.

An approval is what the customer's accountable people signed: which target, which model, which
data, which tools, which kind of human oversight, until when. Public bodies approve on paper and the
software then drifts; here the agent is built FROM the approval, refuses to start when the approval
is expired or no longer matches the use case, and the records server enforces the data ceiling on
its side with a token that carries the approval.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from desk import settings
from desk.classify import Classification
from desk.model import UseCase

OVERSIGHT_MODES = ("handover_on_individual_case", "human_signs_every_output")


class ApprovalError(RuntimeError):
    """The agent must not run: the approval does not cover what was asked."""


@dataclass(frozen=True)
class Approval:
    id: str
    use_case: str
    version: int
    approved_by: tuple[str, ...]
    approved_on: date
    valid_until: date
    classified_as: str  # AI Act class at the time of approval
    discovery_hash: str  # hash of the discovery answers the approval was based on
    target: str
    model: str
    request_classes: tuple[str, ...]  # data classes accepted in requests (personal ones pseudonymised)
    document_ceiling: str  # highest data class the tools may return
    tools: tuple[str, ...]
    oversight: str
    forbidden: tuple[str, ...]  # intents the agent must hand over instead of answering
    disclosure: str
    log_retention_days: int

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["approved_on"] = self.approved_on.isoformat()
        d["valid_until"] = self.valid_until.isoformat()
        return d


@dataclass(frozen=True)
class Scope:
    """What the agent is compiled from. Nothing outside it is reachable at runtime."""

    approval: str
    use_case: str
    target: str
    model: str
    tools: tuple[str, ...]
    ceiling_rank: int
    request_classes: tuple[str, ...]
    pseudonymise: bool
    oversight: str
    forbidden: tuple[str, ...]
    disclosure: str
    expires: date


def discovery_hash(uc: UseCase) -> str:
    """Hash of the answers that decide the classification. Editing them invalidates approvals."""
    keys = (
        "pattern",
        "users",
        "data",
        "decision_role",
        "purpose_area",
        "profiling",
        "prohibited",
        "publishes_public_interest_text",
        "editorial_review",
        "automated_decision",
        "per_user_logging",
        "large_scale",
        "vulnerable_subjects",
        "matching_datasets",
        "systematic_monitoring",
    )
    raw = {k: getattr(uc, k) for k in keys}
    return hashlib.sha256(json.dumps(raw, sort_keys=True, default=list).encode()).hexdigest()[:16]


def load(path: Path) -> Approval:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    for k in ("approved_by", "request_classes", "tools", "forbidden"):
        raw[k] = tuple(raw.get(k) or ())
    a = Approval(**raw)
    if a.oversight not in OVERSIGHT_MODES:
        raise ApprovalError(f"{a.id}: oversight must be one of {OVERSIGHT_MODES}")
    return a


def load_all(directory: Path | None = None) -> dict[str, Approval]:
    d = directory or settings.DATA_DIR / "approvals"
    out = {}
    for f in sorted(d.glob("*.yaml")):
        a = load(f)
        out[a.use_case] = a
    return out


def problems(a: Approval, cl: Classification, today: date) -> list[str]:
    """Why this approval does not (or no longer) cover the use case. Empty means it does."""
    out = []
    if today > a.valid_until:
        out.append(f"approval {a.id} expired on {a.valid_until.isoformat()}")
    if a.discovery_hash != discovery_hash(cl.use_case):
        out.append("the discovery answers changed after approval; the classification must be re-approved")
    if a.classified_as != cl.ai_act_class:
        out.append(f"approved as {a.classified_as}, but the use case now classifies as {cl.ai_act_class}")
    if a.target not in cl.hosting.allowed:
        out.append(f"target {a.target} does not accept the use case's data ({', '.join(cl.use_case.data)})")
    classes = settings.targets()["data_classes"]
    for d in a.request_classes:
        if d not in classes:
            out.append(f"unknown data class {d}")
    accepts = settings.targets()["targets"].get(a.target, {}).get("accepts", [])
    if a.document_ceiling not in accepts:
        out.append(f"document ceiling {a.document_ceiling} is above what {a.target} accepts")
    if cl.stopped:
        out.append("the use case is stopped: " + "; ".join(r for _, r in cl.stops))
    return out


def compile_scope(a: Approval, cl: Classification, today: date) -> Scope:
    issues = problems(a, cl, today)
    if issues:
        raise ApprovalError("; ".join(issues))
    personal = {"personal", "special", "social", "tax"}
    return Scope(
        approval=a.id,
        use_case=a.use_case,
        target=a.target,
        model=a.model,
        tools=a.tools,
        ceiling_rank=settings.class_rank(a.document_ceiling),
        request_classes=a.request_classes,
        pseudonymise=bool(personal & set(a.request_classes)),
        oversight=a.oversight,
        forbidden=a.forbidden,
        disclosure=a.disclosure,
        expires=a.valid_until,
    )
