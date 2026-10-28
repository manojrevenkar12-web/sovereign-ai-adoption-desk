"""Evaluation of the classifier and of the proofs of value, on dev sets and blind held-out sets.

Held-out sets live in heldout/<set>/ and were written from the guides in heldout/ by someone who had
not seen the code. Their first run is written to reports/heldout/<set>/first_run.json with the
sha256 of the set and is never rewritten; later runs go to latest.json, and a changed set is refused.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import yaml

from desk import settings
from desk.approval import compile_scope, load_all
from desk.classify import classify
from desk.model import customer_from, load_portfolio
from desk.pov import rules
from desk.pov.runtime import run_anfrage, run_enquiry

TODAY = date(2026, 10, 28)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("mcp").setLevel(logging.WARNING)
logging.getLogger("httpx2").setLevel(logging.WARNING)


# ---------------------------------------------------------------- classifier ("gates") sets


def _customer(raw: dict[str, Any], uc: dict[str, Any], i: int) -> Any:
    c = {
        "id": f"case-{i}",
        "name": "Case customer",
        "level": raw.get("level", "land"),
        "land": raw.get("land", "by"),
        "buyer": raw.get("buyer", "other"),
        "mission_priorities": [],
        "reviewers": {},
        "contracts": raw.get("contracts", []),
        "framework_agreement": bool(raw.get("framework_agreement", False)),
        "hosting_policy": raw.get("hosting_policy", {}) or {},
        "use_cases": [
            {
                "id": f"case-{i}-uc",
                "title": raw.get("title", "case"),
                "mission": "evaluation case",
                "stage": "qualified",
                "owner": "case",
                **uc,
            }
        ],
    }
    return customer_from(c)


def run_gates(path: Path) -> dict[str, Any]:
    cases = yaml.safe_load(path.read_text(encoding="utf-8"))["cases"]
    rows = []
    for i, case in enumerate(cases):
        c = _customer(case.get("customer", {}), case["use_case"], i)
        cl = classify(c.use_cases[0], c)
        want = case["expect"]
        got = {
            "ai_act_class": cl.ai_act_class,
            "derogation": cl.derogation,
            "transparency": sorted(cl.transparency),
            "dpia": cl.dpia_required,
            "fria": cl.fria_required,
            "staff_council": cl.staff_council_statute is not None,
            "procurement_route": cl.procurement_route,
            "hosting": cl.hosting.chosen,
            "stops": sorted(k for k, _ in cl.stops),
        }
        checks = {}
        for k, v in want.items():
            g = got.get(k)
            if isinstance(v, list):
                v = sorted(v)
            checks[k] = g == v
        rows.append(
            {
                "id": case["id"],
                "checks": checks,
                "got": {k: got[k] for k in want if k in got},
                "want": want,
                "all_right": all(checks.values()),
            }
        )
    n = len(rows)
    fields: dict[str, list[bool]] = {}
    for r in rows:
        for k, ok in r["checks"].items():
            fields.setdefault(k, []).append(ok)
    # The safety-critical misses: a prohibited or high-risk case classified as something lighter.
    under = [
        r["id"]
        for r in rows
        if r["want"].get("ai_act_class") in ("prohibited", "high_risk")
        and r["got"].get("ai_act_class") != r["want"]["ai_act_class"]
    ]
    return {
        "cases": n,
        "fully_right": sum(r["all_right"] for r in rows),
        "by_field": {k: {"right": sum(v), "of": len(v)} for k, v in sorted(fields.items())},
        "under_classified": under,
        "rows": rows,
    }


# ---------------------------------------------------------------- proof of value sets


def _scopes() -> dict[str, Any]:
    by = {u.id: (u, c) for c in load_portfolio() for u in c.use_cases}
    out = {}
    for uid, a in load_all().items():
        u, c = by[uid]
        out[uid] = compile_scope(a, classify(u, c), TODAY)
    return out


async def _enquiries(cases: list[dict[str, Any]], scope: Any) -> dict[str, Any]:
    rows = []
    for case in cases:
        r = await run_enquiry(case["message"], scope)
        d = r.as_dict()
        cited_docs = {c.split("#")[0] for s in r.statements for c in s["citations"]}
        bad = [s["text"] for s in r.statements if rules.forbidden_statement(s["text"])]
        rows.append(
            {
                "id": case["id"],
                "expect": case["expect"],
                "action": r.action,
                "decided_by": r.decided_by,
                "right_action": r.action == case["expect"],
                "source_hit": (
                    bool(cited_docs & set(case.get("sources", [])))
                    if r.action == "answer" and case["expect"] == "answer"
                    else None
                ),
                "eligibility_statements": len(bad),
                "identifiers_seen_by_model": d["identifiersSeenByModel"],
                "cited": sorted(cited_docs),
            }
        )
    answers_expected = [r for r in rows if r["expect"] == "answer"]
    handovers_expected = [r for r in rows if r["expect"] == "handover"]
    hits = [r for r in rows if r["source_hit"] is not None]
    return {
        "cases": len(rows),
        "right_action": sum(r["right_action"] for r in rows),
        "answered_when_expected": sum(r["action"] == "answer" for r in answers_expected),
        "answers_expected": len(answers_expected),
        "handed_over_when_expected": sum(r["action"] == "handover" for r in handovers_expected),
        "handovers_expected": len(handovers_expected),
        "answered_individual_case": sum(r["action"] == "answer" for r in handovers_expected),
        "source_hit": sum(bool(r["source_hit"]) for r in hits),
        "source_checked": len(hits),
        "eligibility_statements": sum(r["eligibility_statements"] for r in rows),
        "identifiers_seen_by_model": sum(r["identifiers_seen_by_model"] for r in rows),
        "rows": rows,
    }


async def _anfragen(items: list[dict[str, Any]], scope: Any) -> dict[str, Any]:
    rows = []
    for a in items:
        r = await run_anfrage(a["text"], scope)
        got = {x["question"]: x for x in r.answers}
        for q, want in a["expect"].items():
            g = got.get(int(q), {"status": "missing", "statements": []})
            cited = {c.split("#")[0] for s in g["statements"] for c in s["citations"]}
            rows.append(
                {
                    "id": f"{a['id']}.{q}",
                    "want": want["status"],
                    "got": g["status"],
                    "right_status": g["status"] == want["status"],
                    "source_hit": bool(cited & set(want.get("sources", [])))
                    if want["status"] == "answered" and g["status"] == "answered"
                    else None,
                    "cited": sorted(cited),
                }
            )
        rows.append({"id": f"{a['id']}.breaches", "ceiling_breaches": r.ceiling_breaches()})
    q = [r for r in rows if "right_status" in r]
    hits = [r for r in q if r["source_hit"] is not None]
    return {
        "anfragen": len(items),
        "questions": len(q),
        "right_status": sum(r["right_status"] for r in q),
        "source_hit": sum(bool(r["source_hit"]) for r in hits),
        "source_checked": len(hits),
        "ceiling_breaches": sum(len(r.get("ceiling_breaches", [])) for r in rows),
        "rows": rows,
    }


def run_pov(set_dir: Path) -> dict[str, Any]:
    scopes = _scopes()
    out: dict[str, Any] = {}
    enq = set_dir / "enquiries.yaml"
    anf = set_dir / "anfragen.yaml"
    if enq.exists():
        cases = yaml.safe_load(enq.read_text(encoding="utf-8"))["cases"]
        out["enquiries"] = asyncio.run(_enquiries(cases, scopes["lws-wohngeld-auskunft"]))
    if anf.exists():
        items = yaml.safe_load(anf.read_text(encoding="utf-8"))["anfragen"]
        out["anfragen"] = asyncio.run(_anfragen(items, scopes["stmv-kleine-anfragen"]))
    return out


# ---------------------------------------------------------------- headline, pinning


def headline(kind: str, r: dict[str, Any]) -> str:
    if kind == "gates":
        f = r["by_field"]
        cls = f.get("ai_act_class", {"right": 0, "of": 0})
        return (
            f"{r['cases']} use cases: AI Act class right {cls['right']}/{cls['of']}, every field right "
            f"{r['fully_right']}/{r['cases']}, prohibited or high-risk under-classified {len(r['under_classified'])}."
        )
    parts = []
    if "enquiries" in r:
        e = r["enquiries"]
        parts.append(
            f"{e['cases']} enquiries: right action {e['right_action']}/{e['cases']}, individual cases answered "
            f"{e['answered_individual_case']}, eligibility statements {e['eligibility_statements']}, identifiers "
            f"seen by the model {e['identifiers_seen_by_model']}, source hit {e['source_hit']}/{e['source_checked']}"
        )
    if "anfragen" in r:
        a = r["anfragen"]
        parts.append(
            f"{a['questions']} Anfrage questions: right status {a['right_status']}/{a['questions']}, source hit "
            f"{a['source_hit']}/{a['source_checked']}, classified passages to the model {a['ceiling_breaches']}"
        )
    return "; ".join(parts) + "."


def sha(set_dir: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(set_dir.glob("*.yaml")):
        h.update(f.name.encode())
        h.update(f.read_bytes())
    return h.hexdigest()


def evaluate(set_dir: Path) -> dict[str, Any]:
    kind = "gates" if (set_dir / "cases.yaml").exists() else "pov"
    r = run_gates(set_dir / "cases.yaml") if kind == "gates" else run_pov(set_dir)
    return {"kind": kind, "headline": headline(kind, r), **r}


def run_heldout(name: str, root: Path | None = None) -> dict[str, Any]:
    root = root or settings.ROOT
    set_dir = root / "heldout" / name
    out = root / "reports" / "heldout" / name
    out.mkdir(parents=True, exist_ok=True)
    report = evaluate(set_dir)
    digest = sha(set_dir)
    first = out / "first_run.json"
    if first.exists():
        if json.loads(first.read_text())["sha256"] != digest:
            raise SystemExit(f"{name}: the set changed after its first run")
        (out / "latest.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    else:
        status = (set_dir / "STATUS").read_text().strip()
        first.write_text(
            json.dumps(
                {
                    "set": name,
                    "status_at_first_run": status,
                    "sha256": digest,
                    "ran_at": datetime.now(UTC).isoformat(timespec="seconds"),
                    **report,
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n"
        )
    return report
