"""The technical account plan for one customer, as Markdown, from the materialised customer view.

It is what the architect and the Account Director take into the quarterly review: mission
priorities, the use-case portfolio with its path to production, decisions needed from the
customer, specialist engagements with owners, risks, and expansion based on proven patterns.
"""

from __future__ import annotations

from typing import Any

from desk import settings

CLASS_LABEL = {
    "prohibited": "Prohibited (Art. 5)",
    "high_risk": "High-risk",
    "not_high_risk": "Not high-risk (Art. 6(3))",
    "transparency": "Transparency duties",
    "minimal": "Minimal",
}


def _when(path: dict[str, Any] | None) -> str:
    if not path:
        return "—"
    if path.get("goLive"):
        return path["goLive"]
    if path.get("waitingFor"):
        return f"ready {path['readyBy']}, waits for {path['waitingFor']}"
    return "—"


def render(view: dict[str, Any], proven_patterns: set[str] | None = None) -> str:
    c, h = view["customer"], view["health"]
    plans = sorted(view["plans"], key=lambda d: (d.get("rank") or 999, d["useCase"]["id"]))
    patterns = settings.portfolio()["patterns"]
    out = [f"# Technical account plan: {c['name']}", ""]
    out += [
        f"Plan computed for the week starting {view['planStart']}. Account health **{h['score']}** ({h['band'].replace('_', ' ')})."
    ]
    out += ["", "## Mission priorities", ""]
    out += [f"- {m}" for m in c.get("mission_priorities", [])]

    out += [
        "",
        "## Use-case portfolio",
        "",
        "| # | Use case | Stage | AI Act | Go-live | Value (h/yr) |",
        "|---|---|---|---|---|---|",
    ]
    for d in plans:
        u, cl, p = d["useCase"], d["classification"], d.get("priority")
        stop = ", ".join(s["stop"] for s in cl["stops"])
        when = f"stopped: {stop}" if stop else _when(d.get("path"))
        if u["stage"] in ("production", "adopted"):
            when = "in production"
        value = f"{p['hoursSavedPerYear']:,} ({p['valueBasis']})" if p else "—"
        out.append(
            f"| {d.get('rank') or '—'} | {u['title']} | {u['stage'].replace('_', ' ')} | "
            f"{CLASS_LABEL[cl['aiAct']['class']]} | {when} | {value} |"
        )

    out += ["", "## Decisions needed from the customer", ""]
    n = 0
    for d in plans:
        path = d.get("path") or {}
        for g in path.get("gates", []):
            if g["done"] or g["gate"] in ("pov", "pilot", "go_live"):
                continue
            if g["gate"] in path.get("critical", []):
                n += 1
                out.append(
                    f"- **{d['useCase']['title']}**: {g['title']} by {g['end']} "
                    f"(critical path{'; waits for capacity' if g['wait'] == 'capacity' else ''})"
                    + (f" — {g['source']}" if g.get("source") else "")
                )
    if not n:
        out.append("- None on a critical path this quarter.")

    out += ["", "## Where the plan loses time", ""]
    if view["bottlenecks"]:
        for b in view["bottlenecks"]:
            who = "OpenAI Deployment Engineering (portfolio)" if b["customer"] == "portfolio" else b["role"]
            out.append(f"- {who}: {b['waitedWeeks']} weeks of critical-path waiting")
    else:
        out.append("- No reviewer is a bottleneck.")
    if view["levers"]:
        out += ["", "Levers, priced by recomputing the plan:", ""]
        out += [
            f"- {lv['lever']}: {lv['weeksSaved']} weeks earlier across {len(lv['useCases'])} use case(s)"
            for lv in view["levers"][:5]
        ]

    out += ["", "## Engagements and handoffs", ""]
    alerts = h["alerts"]
    if alerts:
        out += [f"- {a['handoff']}: {a['text']} (due {a['due']})" for a in alerts]
    else:
        out.append("- No intervention needed.")

    out += ["", "## Expansion", ""]
    here = {d["useCase"]["pattern"] for d in plans}
    proven = (proven_patterns or set()) - here
    if proven:
        out += [
            f"- {patterns[p]['title']}: proven elsewhere in the portfolio, not yet discussed here."
            for p in sorted(proven)
        ]
    else:
        out.append("- No proven pattern missing from this customer's portfolio.")
    out += [
        "",
        "_Values marked projected use the pattern's assumed time saving until a proof of value measures it._",
        "",
    ]
    return "\n".join(out)
