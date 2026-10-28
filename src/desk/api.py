"""HTTP API behind the console, and the desk's own MCP server for ChatGPT and Codex.

Every request carries an OpenID Connect token; the customers it names become the row-level
security scope of the database transaction. Writes are architect-only, recorded as hash-chained
events in the same transaction, and followed by a replan of the portfolio.
"""

from __future__ import annotations

import json
import os
import time
from collections import Counter
from datetime import date
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from desk import account_plan, settings
from desk.approval import compile_scope
from desk.auth import Principal, Unauthorized, verify
from desk.classify import classify
from desk.model import customer_from
from desk.store import Store

STAGES: list[str] = settings.portfolio()["stages"]
METRICS: Counter[str] = Counter()


def today() -> date:
    v = os.environ.get("DESK_TODAY")
    return date.fromisoformat(v) if v else date.today()


class StageChange(BaseModel):
    stage: str
    note: str = ""


class GateChange(BaseModel):
    done: bool = True
    note: str = ""


class Ask(BaseModel):
    message: str


def principal(request: Request) -> Principal:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise HTTPException(401, "bearer token required", headers={"WWW-Authenticate": "Bearer"})
    try:
        return verify(header[7:])
    except Unauthorized as e:
        METRICS["auth_rejected"] += 1
        raise HTTPException(401, str(e), headers={"WWW-Authenticate": "Bearer"}) from e


def architect(p: Principal = Depends(principal)) -> Principal:
    if not p.can_write:
        raise HTTPException(403, "only the accountable architect can change the plan")
    return p


def create_app(store: Store | None = None) -> FastAPI:
    st = store or Store(os.environ["DESK_DATABASE_URL"])
    app = FastAPI(title="sovereign-ai-adoption-desk", version="0.1.0")
    origins = [o for o in os.environ.get("DESK_CORS_ORIGINS", "http://localhost:5173").split(",") if o]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])

    @app.middleware("http")
    async def count(request: Request, call_next: Any) -> Any:
        start = time.perf_counter()
        response = await call_next(request)
        METRICS[f"http_{response.status_code // 100}xx"] += 1
        METRICS["http_ms_total"] += int((time.perf_counter() - start) * 1000)
        return response

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz() -> dict[str, str]:
        with st.connect() as conn:
            conn.execute("SELECT 1")
        return {"status": "ready"}

    @app.get("/metrics", response_class=PlainTextResponse)
    def metrics() -> str:
        return "".join(f"desk_{k} {v}\n" for k, v in sorted(METRICS.items()))

    @app.get("/api/me")
    def me(p: Principal = Depends(principal)) -> dict[str, Any]:
        return {"subject": p.subject, "role": p.role, "customers": list(p.customers), "canWrite": p.can_write}

    @app.get("/api/portfolio")
    def portfolio(p: Principal = Depends(principal)) -> dict[str, Any]:
        return {**st.portfolio(list(p.customers)), "today": today().isoformat(), "role": p.role}

    @app.get("/api/use-cases/{uid}")
    def dossier(uid: str, p: Principal = Depends(principal)) -> dict[str, Any]:
        d = st.dossier(list(p.customers), uid)
        if d is None:
            raise HTTPException(404, "no such use case in your portfolio")
        return d

    @app.get("/api/customers/{cid}")
    def customer(cid: str, p: Principal = Depends(principal)) -> dict[str, Any]:
        v = st.customer_view(list(p.customers), cid)
        if v is None:
            raise HTTPException(404, "no such customer in your portfolio")
        return v

    @app.get("/api/customers/{cid}/plan.md", response_class=PlainTextResponse)
    def plan_md(cid: str, p: Principal = Depends(principal)) -> str:
        v = st.customer_view(list(p.customers), cid)
        if v is None:
            raise HTTPException(404, "no such customer in your portfolio")
        proven = set()
        for c in st.portfolio(list(p.customers))["customers"]:
            proven |= {u["pattern"] for u in c["useCases"] if u["stage"] in ("production", "adopted")}
        return account_plan.render(v, proven)

    @app.get("/api/customers/{cid}/events")
    def events(cid: str, p: Principal = Depends(principal)) -> dict[str, Any]:
        return st.events(list(p.customers), cid)

    def _replan() -> None:
        st.replan(today())
        METRICS["replans"] += 1

    @app.post("/api/use-cases/{uid}/stage")
    def change_stage(uid: str, body: StageChange, p: Principal = Depends(architect)) -> dict[str, Any]:
        d = st.dossier(list(p.customers), uid)
        if d is None:
            raise HTTPException(404, "no such use case in your portfolio")
        if body.stage not in STAGES:
            raise HTTPException(422, f"stage must be one of {STAGES}")
        current = d["useCase"]["stage"]
        reasons = transition_problems(d, current, body.stage)
        if reasons:
            raise HTTPException(409, {"message": "the use case cannot move", "reasons": reasons})
        st.update_use_case(list(p.customers), p.subject, uid, {"stage": body.stage}, "stage_changed")
        _replan()
        return st.dossier(list(p.customers), uid) or {}

    @app.post("/api/use-cases/{uid}/gates/{gate}")
    def change_gate(uid: str, gate: str, body: GateChange, p: Principal = Depends(architect)) -> dict[str, Any]:
        d = st.dossier(list(p.customers), uid)
        if d is None:
            raise HTTPException(404, "no such use case in your portfolio")
        gates = {g["gate"] for g in (d.get("path") or {}).get("gates", [])}
        if gate not in gates:
            raise HTTPException(422, f"{gate} is not a gate of this use case")
        done = [g for g in d["useCase"].get("done", []) if g != gate] + ([gate] if body.done else [])
        st.update_use_case(
            list(p.customers), p.subject, uid, {"done": done}, "gate_passed" if body.done else "gate_reopened"
        )
        _replan()
        return st.dossier(list(p.customers), uid) or {}

    @app.post("/api/use-cases/{uid}/pov")
    async def ask(uid: str, body: Ask, p: Principal = Depends(principal)) -> dict[str, Any]:
        from desk.approval import Approval
        from desk.pov.runtime import run_anfrage, run_enquiry

        if p.role == "customer":
            raise HTTPException(403, "proofs of value are run by the delivery team")
        d = st.dossier(list(p.customers), uid)
        if d is None:
            raise HTTPException(404, "no such use case in your portfolio")
        if not d.get("approval") or not d["useCase"].get("pov"):
            raise HTTPException(409, "this use case has no approved proof of value")
        if d["approval"]["problems"]:
            raise HTTPException(
                409, {"message": "the approval does not cover this run", "reasons": d["approval"]["problems"]}
            )
        u = d["useCase"]
        view = st.customer_view(list(p.customers), u["customer"])
        assert view is not None
        c = customer_from(
            {
                **view["customer"],
                "use_cases": [{k: v for k, v in u.items() if k != "customer"}],
            }
        )
        a = d["approval"]
        appr = Approval(
            **{
                **{k: v for k, v in a.items() if k != "problems"},
                **{k: tuple(a[k]) for k in ("approved_by", "request_classes", "tools", "forbidden")},
                "approved_on": date.fromisoformat(a["approved_on"]),
                "valid_until": date.fromisoformat(a["valid_until"]),
            }
        )
        scope = compile_scope(appr, classify(c.use_cases[0], c), today())
        if u["pov"] == "wohngeld":
            out = (await run_enquiry(body.message, scope)).as_dict()
        else:
            out = (await run_anfrage(body.message, scope)).as_dict()
        st.record_pov_run(
            list(p.customers),
            p.subject,
            u["customer"],
            uid,
            {
                "kind": u["pov"],
                "action": out.get("action", "draft"),
                "result": json.loads(json.dumps(out, default=str)),
            },
        )
        METRICS["pov_runs"] += 1
        return out

    from desk.desk_mcp import mount

    mount(app, st)
    return app


def transition_problems(d: dict[str, Any], current: str, target: str) -> list[str]:
    """What stops a stage change. Moving into production needs every gate passed and a valid approval."""
    out = []
    if d["classification"]["stops"] and target not in ("not_pursued", current):
        out.append("the use case is stopped: " + "; ".join(s["reason"] for s in d["classification"]["stops"]))
    order = [s for s in STAGES if s != "not_pursued"]
    if (
        target != "not_pursued"
        and current in order
        and target in order
        and order.index(target) > order.index(current) + 1
    ):
        out.append(f"move one stage at a time ({current} → {order[order.index(current) + 1]})")
    if target in ("production", "adopted") and current not in ("production",):
        open_gates = [
            g["title"] for g in (d.get("path") or {}).get("gates", []) if not g["done"] and g["gate"] != "go_live"
        ]
        if open_gates:
            out.append("gates still open: " + ", ".join(open_gates))
        appr = d.get("approval")
        if appr is None:
            out.append("no approval record covers production")
        elif appr["problems"]:
            out += appr["problems"]
    return out
