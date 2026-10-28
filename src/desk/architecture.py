"""A reference architecture per use case, chosen by rules from its pattern and classification.

The output is what an AI architect brings to a customer's CIO, CISO and data protection officer:
one component per layer with the reason for the choice and the alternative that was rejected, the
decisions that carry a trade-off, and a diagram. Nothing here is decided by a model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from desk import settings
from desk.classify import Classification, channel_of

LAYERS = (
    "channel",
    "model",
    "data",
    "identity",
    "security",
    "privacy",
    "governance",
    "evaluation",
    "operations",
)


@dataclass(frozen=True)
class Component:
    layer: str
    choice: str
    why: str
    rejected: str | None = None


@dataclass(frozen=True)
class Decision:
    question: str
    choice: str
    trade_off: str


@dataclass(frozen=True)
class Architecture:
    use_case: str
    components: tuple[Component, ...]
    decisions: tuple[Decision, ...]
    oversight: str
    mermaid: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "useCase": self.use_case,
            "oversight": self.oversight,
            "components": [
                {"layer": c.layer, "choice": c.choice, "why": c.why, "rejected": c.rejected} for c in self.components
            ],
            "decisions": [
                {"question": d.question, "choice": d.choice, "tradeOff": d.trade_off} for d in self.decisions
            ],
            "mermaid": self.mermaid,
        }


CHANNELS = {
    "staff_assistant": (
        "ChatGPT Enterprise workspace: a project or custom GPT for the team",
        "Staff already work in the workspace; no application to build, operate or accredit.",
        "A custom web application (more to build and accredit for the same capability)",
    ),
    "citizen_channel": (
        "Chat on the authority's portal, built with the Agents SDK on the Responses API",
        "Citizens need no account; the authority controls the disclosure, the sources and the handover.",
        "A public custom GPT (citizens would need a ChatGPT account and the authority loses the handover)",
    ),
    "agent_workflow": (
        "Agents SDK workflow embedded in the team's tool, reaching records through MCP",
        "Multi-step work (search, draft, route for co-signature) with tools the approval can list one by one.",
        "A chat assistant with broad connectors (cannot restrict tools per approval)",
    ),
    "api_application": (
        "Service on the Responses API with structured outputs, called by the specialist procedure",
        "Results land as fields in the procedure the caseworker already uses, with a schema the procedure validates.",
        "Copy and paste between a chat window and the procedure (no audit trail, no validation)",
    ),
    "codex": (
        "Codex in the ChatGPT Enterprise workspace against the procedure's repositories",
        "Engineers keep their review process; Codex proposes changes as pull requests with tests.",
        "An external contractor rewrite (slower, knowledge leaves with the contractor)",
    ),
}

OVERSIGHT = {
    "citizen_channel": "Handover: any question about an individual case goes to a caseworker; the assistant never assesses it.",
    "agent_workflow": "A person reviews and signs every draft before it leaves the unit.",
    "api_application": "The caseworker sees the result next to the source and decides; nothing is applied automatically.",
    "staff_assistant": "Staff remain responsible for what they use; the assistant has no write access.",
    "codex": "Every change is a pull request reviewed by an engineer and gated by tests.",
}


def design(cl: Classification) -> Architecture:
    uc = cl.use_case
    t = settings.targets()
    pat = settings.portfolio()["patterns"][uc.pattern]
    channel = channel_of(uc)
    comps: list[Component] = []
    decisions: list[Decision] = []

    choice, why, rejected = CHANNELS[channel]
    comps.append(Component("channel", choice, why, rejected))

    if cl.hosting.chosen:
        tgt = t["targets"][cl.hosting.chosen]
        why_m = "; ".join(tgt["facts"][:2])
        others = [x for x in cl.hosting.allowed if x != cl.hosting.chosen]
        comps.append(
            Component(
                "model",
                f"{tgt['title']} ({cl.hosting.chosen})",
                why_m,
                f"{', '.join(others)} (also allowed)" if others else None,
            )
        )
        if tgt["status"] != "available":
            decisions.append(
                Decision(
                    "Start before the sovereign target is available?",
                    "Run the proof of value now on synthetic and public data on openai_api_eu; move to "
                    f"{cl.hosting.chosen} for the pilot with real data.",
                    "Evidence arrives months earlier; the switch of target needs a short re-evaluation on the blind set.",
                )
            )
        elif len(cl.hosting.allowed) > 1:
            decisions.append(
                Decision(
                    "Which hosting target?",
                    cl.hosting.chosen,
                    "Chosen for availability and existing contracts; "
                    f"{', '.join(others)} would also accept this data and stays the fallback.",
                )
            )
    else:
        comps.append(Component("model", "None: no target accepts this data", "See the stop reasons."))

    personal = cl.facts.get("personal_data", False)
    if channel == "citizen_channel":
        comps.append(
            Component(
                "data",
                "Retrieval over the authority's approved guidance only, through an MCP server with read-only tools",
                "Answers can only come from texts the authority has published; each answer cites them.",
                "Open web search (unapproved sources, no control over what is said)",
            )
        )
    elif channel in ("agent_workflow", "api_application"):
        comps.append(
            Component(
                "data",
                "MCP server in front of the records system: read-only tools, classification ceiling enforced on the server",
                "The approval lists the tools; documents above the approved classification never leave the server.",
                "Bulk export of records into a vector store (copies data, loses the access rules)",
            )
        )
    elif channel == "codex":
        comps.append(
            Component(
                "data",
                "Repository access through the workspace's GitLab/GitHub integration",
                "Codex sees code and tests, not production data.",
            )
        )
    else:
        comps.append(
            Component(
                "data",
                "Workspace connectors limited to approved sites and libraries",
                "Only sources the data owner approved are searchable.",
            )
        )

    if uc.staff_facing:
        comps.append(
            Component(
                "identity",
                "SSO with the customer's identity provider (OIDC/SAML), SCIM provisioning from the directory",
                "Joiners and leavers follow the directory; group membership decides workspace access.",
                "Local accounts (orphaned access when staff leave)",
            )
        )
    if uc.citizen_facing:
        comps.append(
            Component(
                "identity",
                "No login for general questions; case-specific questions handed to a channel with BundID/BayernID",
                "Keeps the AI channel free of identified case data, which keeps it out of Annex III(5)(a).",
            )
        )
    if channel in ("agent_workflow", "api_application", "citizen_channel"):
        comps.append(
            Component(
                "security",
                "Approval compiled into the agent: tool allowlist, data-class ceiling, oversight mode, expiry",
                "What was approved is what runs; anything outside it is refused at runtime and logged.",
                "A policy document next to an unrestricted agent (approval and runtime drift apart)",
            )
        )
    comps.append(
        Component(
            "security",
            "Retrieved text is data, never instructions; tool outputs cannot add tools or raise the ceiling",
            "Limits prompt injection through documents and enquiries.",
        )
    )
    if cl.ai_act_class == "high_risk":
        comps.append(
            Component(
                "security", "Event logs kept at least six months, tamper-evident", "Art. 12 and Art. 26(6) AI Act."
            )
        )

    if personal and channel != "staff_assistant":
        comps.append(
            Component(
                "privacy",
                "Personal identifiers pseudonymised before any model call and restored only in the reply",
                "Names, IBANs, tax IDs and addresses never reach the model; zero data retention on the API project.",
                "Refusing all input with personal data (citizens include it anyway)",
            )
        )
        decisions.append(
            Decision(
                "Pseudonymise or refuse personal data in requests?",
                "Pseudonymise",
                "Citizens and staff include identifiers anyway; refusing breaks the service, pseudonymising keeps it "
                "working while the model sees placeholders. Detection can miss free-form identifiers, so the DPIA "
                "keeps that residual risk.",
            )
        )
    elif personal:
        comps.append(
            Component(
                "privacy",
                "Workspace data residency in the EU, no training on business data",
                "Personal data stays under the workspace's DPA and retention settings.",
            )
        )

    oversight = OVERSIGHT[channel]
    if cl.ai_act_class == "high_risk":
        oversight = "A competent caseworker decides every case and can override the system (Art. 14, Art. 26(2))."
    comps.append(Component("governance", oversight, "Defines who is accountable for each output."))
    comps.append(
        Component(
            "governance",
            "Versioned approval record with an expiry; re-approval when scope, model or target changes",
            "Approvals cover a scope, not a product forever.",
        )
    )
    comps.append(
        Component(
            "evaluation",
            f"Blind evaluation set written before the build; metrics: {', '.join(pat['metrics'])}",
            "The proof of value is judged on cases nobody tuned the system to.",
        )
    )
    comps.append(
        Component(
            "operations",
            "Adoption from the workspace's usage export; agent runs traced; drift in metrics reopens the approval",
            "Value is tracked after go-live, not assumed.",
        )
    )

    if channel == "citizen_channel":
        decisions.append(
            Decision(
                "Answer questions about a person's own case?",
                "No: hand over to a caseworker",
                "Fewer questions answered automatically, but the system stays an information service instead of an "
                "Annex III(5)(a) eligibility system with conformity assessment, FRIA and registration.",
            )
        )
    if channel == "agent_workflow":
        decisions.append(
            Decision(
                "Include classified documents?",
                "No: the server withholds documents above the ceiling and the draft says one was withheld",
                "The unit handles those parts by hand, but no VS-NfD content ever reaches a model.",
            )
        )
    if cl.derogation:
        decisions.append(
            Decision(
                "Keep the system preparatory or let it decide?",
                "Preparatory/procedural only",
                f"Stays outside high-risk under Art. 6(3) ({cl.derogation}); if the role grows to influencing outcomes "
                "the classification must be redone.",
            )
        )

    return Architecture(uc.id, tuple(comps), tuple(decisions), oversight, _mermaid(cl, channel))


def _mermaid(cl: Classification, channel: str) -> str:
    uc = cl.use_case
    who = "Citizens" if uc.users == "public" else ("Staff and citizens" if uc.users == "both" else "Staff")
    target = cl.hosting.chosen or "no target"
    lines = [
        "flowchart LR",
        f'  U["{who}"] --> C["{CHANNELS[channel][0].split(":")[0]}"]',
    ]
    if uc.staff_facing:
        lines.append('  IDP["Identity provider (SSO, SCIM)"] -.-> C')
    if channel in ("agent_workflow", "api_application", "citizen_channel"):
        lines += [
            '  C --> G["Approved scope: tools, ceiling, oversight"]',
            '  G --> A["Agent (Agents SDK)"]',
            f'  A --> M["Model on {target}"]',
            '  A --> T["MCP server (read-only tools)"]',
            '  T --> S["Source system"]',
        ]
        if cl.facts.get("personal_data"):
            lines.append('  G --> P["Pseudonymiser"] --> A')
    else:
        lines.append(f'  C --> M["Model on {target}"]')
    if uc.citizen_facing:
        lines.append('  A -->|individual case| H["Caseworker queue"]')
    lines.append('  M -.-> L["Audit log and traces"]')
    return "\n".join(lines)
