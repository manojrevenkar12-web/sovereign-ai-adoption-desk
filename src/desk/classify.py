"""What the law asks of a use case, decided by rules over the discovery answers.

Models never decide this. Each finding names the article it rests on and the reason in plain
words, so a customer's counsel can check the reasoning instead of trusting a score.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from desk import settings
from desk.model import Customer, UseCase

PERSONAL = ("personal", "special", "social", "tax")
SENSITIVE = ("special", "social", "tax")
DEROGATION_ROLES = ("procedural", "improves_completed_human_work", "pattern_detection", "preparatory")
# Areas where a purely informing system can still fall under Annex III.
INFORMING_STAYS_IN = ("biometrics", "elections")


@dataclass(frozen=True)
class Duty:
    kind: str  # ai_act | gdpr | secrecy | staff | accessibility | procurement
    article: str
    text: str
    applies_from: date | None = None


@dataclass(frozen=True)
class Hosting:
    allowed: tuple[str, ...]
    chosen: str | None
    chosen_status: str | None
    under_contract: bool


@dataclass(frozen=True)
class Classification:
    use_case: UseCase
    ai_act_class: str  # prohibited | high_risk | not_high_risk | transparency | minimal
    ai_act_basis: str
    roles: tuple[str, ...]
    derogation: str | None
    transparency: tuple[str, ...]
    dpia_required: bool
    dpia_criteria: tuple[str, ...]
    dpia_mandatory: tuple[str, ...]
    fria_required: bool
    staff_council_statute: str | None
    accessibility_statute: str | None
    procurement_route: str | None
    hosting: Hosting
    stops: tuple[tuple[str, str], ...]
    duties: tuple[Duty, ...]
    reasons: tuple[str, ...]
    facts: dict[str, bool] = field(default_factory=dict)

    @property
    def stopped(self) -> bool:
        return bool(self.stops)

    def as_dict(self) -> dict[str, Any]:
        return {
            "useCase": self.use_case.id,
            "aiAct": {
                "class": self.ai_act_class,
                "basis": self.ai_act_basis,
                "roles": list(self.roles),
                "derogation": self.derogation,
                "transparency": list(self.transparency),
            },
            "gdpr": {
                "dpiaRequired": self.dpia_required,
                "dpiaCriteria": list(self.dpia_criteria),
                "dpiaMandatory": list(self.dpia_mandatory),
            },
            "friaRequired": self.fria_required,
            "staffCouncil": self.staff_council_statute,
            "accessibility": self.accessibility_statute,
            "procurementRoute": self.procurement_route,
            "hosting": {
                "allowed": list(self.hosting.allowed),
                "chosen": self.hosting.chosen,
                "status": self.hosting.chosen_status,
                "underContract": self.hosting.under_contract,
            },
            "stops": [{"stop": k, "reason": r} for k, r in self.stops],
            "duties": [
                {
                    "kind": d.kind,
                    "article": d.article,
                    "text": d.text,
                    "appliesFrom": d.applies_from.isoformat() if d.applies_from else None,
                }
                for d in self.duties
            ],
            "reasons": list(self.reasons),
            "facts": dict(self.facts),
        }


def _d(s: Any) -> date:
    return s if isinstance(s, date) else date.fromisoformat(str(s))


def channel_of(uc: UseCase) -> str:
    return str(settings.portfolio()["patterns"][uc.pattern]["channel"])


def _ai_act(uc: UseCase, reasons: list[str], duties: list[Duty]) -> tuple[str, str, str | None, tuple[str, ...]]:
    act = settings.ai_act()
    dates = act["dates"]
    if uc.prohibited:
        for p in uc.prohibited:
            item = act["prohibited"][p]
            duties.append(Duty("ai_act", item["article"], item["text"], _d(dates["prohibitions"])))
            reasons.append(f"Prohibited practice: {item['text']} ({item['article']}).")
        first = act["prohibited"][uc.prohibited[0]]["article"]
        return "prohibited", first, None, ()

    klass, basis, derogation = "minimal", "Not listed in Annex III and no transparency duty", None
    if uc.purpose_area != "none":
        area = act["annex_iii"][uc.purpose_area]
        if uc.decision_role == "information" and uc.purpose_area not in INFORMING_STAYS_IN:
            reasons.append(
                f"The use case touches {area['point']} but only informs: it does not evaluate, decide or "
                "steer an outcome for a person, so its intended purpose is outside that point."
            )
        elif uc.decision_role in DEROGATION_ROLES and not uc.profiling:
            der = act["derogations"][uc.decision_role]
            klass, basis, derogation = "not_high_risk", f"{area['point']}, {der['article']}", uc.decision_role
            reasons.append(
                f"{area['point']} applies, but the system {der['text'][0].lower()}{der['text'][1:]} "
                f"({der['article']}); it is not high-risk provided it poses no significant risk of harm."
            )
            for dd in act["derogation_duties"]:
                duties.append(Duty("ai_act", dd["article"], dd["text"], _d(dates["high_risk_annex_iii"])))
        else:
            klass, basis = "high_risk", area["point"]
            if uc.profiling and uc.decision_role in DEROGATION_ROLES:
                why = "it profiles natural persons, which rules out every Art. 6(3) derogation"
            elif uc.decision_role == "information":
                why = "an informing system stays within this area"
            else:
                why = (
                    f"its output {'decides' if uc.decision_role == 'decides' else 'materially influences'} the outcome"
                )
            reasons.append(f"High-risk under {area['point']}: {area['text']} Here {why}.")

    transparency: list[str] = []
    if uc.citizen_facing:
        t = act["transparency"]["interacts_with_public"]
        transparency.append("interacts_with_public")
        duties.append(Duty("ai_act", t["article"], t["text"], _d(dates["transparency"])))
        reasons.append(f"Citizens talk to it directly, so they must be told it is an AI system ({t['article']}).")
    if uc.publishes_public_interest_text:
        t = act["transparency"]["publishes_public_interest_text"]
        if uc.editorial_review:
            reasons.append(
                f"It drafts text published to the public, but a person reviews it and holds editorial "
                f"responsibility, so the {t['article']} disclosure does not apply."
            )
        else:
            transparency.append("publishes_public_interest_text")
            duties.append(Duty("ai_act", t["article"], t["text"], _d(dates["transparency"])))
            reasons.append(f"Text it generates is published unreviewed, so it must be disclosed ({t['article']}).")
    if klass == "minimal" and transparency:
        klass, basis = "transparency", ", ".join(act["transparency"][k]["article"] for k in transparency)
    return klass, basis, derogation, tuple(transparency)


def _roles(uc: UseCase, klass: str) -> tuple[str, ...]:
    channel = channel_of(uc)
    roles = ["deployer"]
    if channel != "staff_assistant":
        roles.insert(0, "provider_own_name")
    elif klass == "high_risk":
        roles.insert(0, "provider_by_repurposing")
    return tuple(roles)


def _hosting(uc: UseCase, c: Customer) -> Hosting:
    t = settings.targets()
    channel = channel_of(uc)
    allowed = []
    for name, tgt in t["targets"].items():
        if channel not in tgt["suits"]:
            continue
        if not set(uc.data) <= set(tgt["accepts"]):
            continue
        if any(name not in c.hosting_policy.get(d, [name]) for d in uc.data):
            continue
        allowed.append(name)
    if not allowed:
        return Hosting((), None, None, False)

    def rank(name: str) -> tuple[int, int, int]:
        tgt = t["targets"][name]
        return (
            0 if name == uc.target_preference else 1,
            0 if tgt["status"] == "available" else 1,
            0 if name in c.contracts else 1,
        )

    chosen = sorted(allowed, key=rank)[0]
    return Hosting(tuple(allowed), chosen, t["targets"][chosen]["status"], chosen in c.contracts)


def classify(uc: UseCase, c: Customer) -> Classification:
    act, law = settings.ai_act(), settings.law()
    reasons: list[str] = []
    duties: list[Duty] = []
    stops: list[tuple[str, str]] = []
    stop_text = settings.gates()["stops"]

    klass, basis, derogation, transparency = _ai_act(uc, reasons, duties)
    if klass == "prohibited":
        stops.append(("prohibited", stop_text["prohibited"]))
    roles = _roles(uc, klass)
    for r in roles:
        if r != "deployer" and (klass in ("high_risk", "transparency") or r == "provider_by_repurposing"):
            reasons.append(act["roles"][r]["text"] + f" ({act['roles'][r]['article']})")
    hr_from = _d(act["dates"]["high_risk_annex_iii"])
    if klass == "high_risk":
        if any(r.startswith("provider") for r in roles):
            duties += [Duty("ai_act", x["article"], x["text"], hr_from) for x in act["high_risk_provider_duties"]]
        duties += [Duty("ai_act", x["article"], x["text"], hr_from) for x in act["high_risk_deployer_duties"]]
    if klass != "prohibited":
        duties += [Duty("ai_act", x["article"], x["text"], _d(act["dates"]["prohibitions"])) for x in act["always"]]
    # Art. 27: bodies governed by public law deploying a high-risk system (Annex III point 2 excluded).
    fria = klass == "high_risk" and uc.purpose_area != "critical_infrastructure"

    personal = any(d in PERSONAL for d in uc.data)
    sensitive = any(d in SENSITIVE for d in uc.data)
    crit: list[str] = []
    mandatory: list[str] = []
    if personal:
        if uc.profiling or uc.decision_role in ("materially_influences", "decides", "pattern_detection"):
            crit.append("evaluation_or_scoring")
        if uc.automated_decision:
            crit.append("automated_decision_legal_effect")
        if uc.systematic_monitoring:
            crit.append("systematic_monitoring")
        if sensitive:
            crit.append("sensitive_data")
        if uc.large_scale:
            crit.append("large_scale")
        if uc.matching_datasets:
            crit.append("matching_datasets")
        if uc.vulnerable_subjects:
            crit.append("vulnerable_subjects")
        crit.append("innovative_technology")
        if uc.automated_decision and uc.profiling:
            mandatory.append("automated_decision_legal_effect_with_profiling")
        if uc.large_scale and "special" in uc.data:
            mandatory.append("large_scale_sensitive")
    dpia_cfg = law["dpia"]
    dpia = personal and (len(crit) >= int(dpia_cfg["threshold"]) or bool(mandatory))
    if personal:
        lb = law["legal_basis"]
        level_basis = lb["by_level"].get(c.land)
        duties.append(Duty("gdpr", lb["article"] + (f"; {level_basis}" if level_basis else ""), lb["text"]))
    if dpia:
        names = ", ".join(dpia_cfg["criteria"][k]["text"].rstrip(".").lower() for k in crit)
        reasons.append(
            f"A DPIA is needed: {len(crit)} WP 248 criteria apply ({names})"
            + (f" and Art. 35(3) names it directly ({', '.join(mandatory)})" if mandatory else "")
            + "."
        )
        duties.append(Duty("gdpr", dpia_cfg["article"], "Data protection impact assessment before processing starts."))
    elif personal:
        reasons.append(f"No DPIA by the WP 248 rule of thumb: only {len(crit)} criterion applies ({', '.join(crit)}).")

    automated = uc.automated_decision or (uc.decision_role == "decides" and personal)
    if automated:
        ad = law["automated_decision"]
        duties.append(Duty("gdpr", ad["article"], ad["text"]))
        reasons.append("The system would decide without a person, which needs an explicit legal basis (§ 35a VwVfG).")

    if "social" in uc.data:
        s = law["secrecy"]["social_data"]
        duties.append(Duty("secrecy", s["article"], s["text"]))
    if "tax" in uc.data:
        s = law["secrecy"]["tax_secrecy"]
        duties.append(Duty("secrecy", s["article"], s["text"]))
    never = settings.targets()["never_routed"]
    if any(d in never for d in uc.data):
        s = law["secrecy"]["classified"]
        duties.append(Duty("secrecy", s["article"], s["text"]))
        stops.append(("classified", stop_text["classified"]))

    staff_statute = None
    if uc.staff_facing and uc.per_user_logging:
        sc = law["staff_council"]
        staff_statute = sc.get(c.land, sc["default"])["statute"]
        duties.append(
            Duty(
                "staff",
                staff_statute,
                "Co-determination: per-user logs make the tool objectively able to monitor staff.",
            )
        )
        reasons.append(
            f"Staff use it and their use is logged per person, so the staff council co-determines ({staff_statute})."
        )
    acc_statute = None
    if uc.citizen_facing:
        acc = law["accessibility"]
        acc_statute = acc.get(c.land, acc["default"])
        duties.append(Duty("accessibility", acc_statute, "The citizen channel must meet the accessibility standard."))

    hosting = _hosting(uc, c)
    if not stops and hosting.chosen is None:
        stops.append(("no_target", stop_text["no_target"]))
    if hosting.chosen and hosting.chosen_status != "available":
        reasons.append(
            f"Only {', '.join(hosting.allowed)} accepts this data; {hosting.chosen} is {hosting.chosen_status}, "
            "so go-live waits for it."
        )

    route = None
    if hosting.chosen and not hosting.under_contract:
        proc = law["procurement"]
        threshold = proc["thresholds_eur"][c.buyer]
        if c.framework_agreement:
            route = "framework_call_off"
        elif uc.contract_value_eur >= threshold:
            route = "eu_procedure"
        else:
            route = "national"
        duties.append(Duty("procurement", proc["source"], proc["routes"][route]["title"]))

    facts = {
        "always": True,
        "personal_data": personal,
        "dpia_required": dpia,
        "fria_required": fria,
        "automated_decision": automated,
        "derogation": derogation is not None,
        "social_data": "social" in uc.data,
        "tax_data": "tax" in uc.data,
        "staff_council_required": staff_statute is not None,
        "new_contract": route is not None,
        "citizen_facing": uc.citizen_facing,
        "high_risk": klass == "high_risk",
        "target_planned": bool(hosting.chosen and hosting.chosen_status != "available"),
    }
    return Classification(
        use_case=uc,
        ai_act_class=klass,
        ai_act_basis=basis,
        roles=roles,
        derogation=derogation,
        transparency=transparency,
        dpia_required=dpia,
        dpia_criteria=tuple(crit),
        dpia_mandatory=tuple(mandatory),
        fria_required=fria,
        staff_council_statute=staff_statute,
        accessibility_statute=acc_statute,
        procurement_route=route,
        hosting=hosting,
        stops=tuple(stops),
        duties=tuple(duties),
        reasons=tuple(reasons),
        facts=facts,
    )
