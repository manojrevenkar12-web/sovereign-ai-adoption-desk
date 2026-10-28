"""Rules that decide before and after the model: forbidden intents, and statements the agent may never make.

These are deliberately plain regular expressions over German text, reviewed like code. The model is
never asked whether a question is about the person's own case; the rule decides and the model is
not called at all.
"""

from __future__ import annotations

import re

INTENTS: dict[str, list[str]] = {
    "individual_eligibility": [
        r"\b(?:habe|hätte|hab|haben|hätten)\s+(?:ich|wir)\b[^?.!]{0,40}\banspruch",
        r"\bsteht\s+(?:mir|uns)\b[^?.!]{0,40}\bzu\b",
        r"\b(?:bekomme|bekommen|kriege|kriegen|erhalte|erhalten)\s+(?:ich|wir)\b[^?.!]{0,40}\bwohngeld",
        r"\bwie\s*viel\b[^?.!]{0,40}\b(?:bekomme|bekommen|erhalte|erhalten|kriege)\s+(?:ich|wir)\b",
        r"\b(?:kann|könnte|können)\s+(?:ich|wir)\b[^?.!]{0,30}\bwohngeld\s+(?:bekommen|erhalten|beziehen|kriegen)",
        r"\b(?:bin|sind)\s+(?:ich|wir)\b[^?.!]{0,30}\b(?:berechtigt|anspruchsberechtigt)",
        r"\b(?:ich|wir)\s+(?:verdiene|verdienen|bekomme|bekommen|zahle|zahlen)\b[^?.!]{0,30}\d",
        r"\b(?:mein|meine|unser|unsere)\s+(?:einkommen|gehalt|rente|miete)\b[^?.!]{0,60}\b(?:reicht|zu hoch|zu niedrig|anspruch|wohngeld)",
        # someone else's case: "kann sie zusätzlich Wohngeld bekommen", "bekommt meine Mutter Wohngeld"
        r"\b(?:kann|könnte|bekommt|bekäme|erhält|hätte|hat)\s+(?:sie|er|meine?\s+\w+|mein\w*\s+\w+)\b[^?.!]{0,50}\bwohngeld",
        r"\b(?:berechne|berechnen|ausrechnen|rechne|rechnen)\w*\b[^?.!]{0,40}\bwohngeld",
        r"\bwohngeld\b[^?.!]{0,40}\b(?:berechnen|ausrechnen|ausgerechnet|berechnet)",
        r"\bverlier\w*\s+(?:ich|wir|er|sie)\b",
        r"\b(?:zählt|zählen|gehört|gehören)\s+(?:er|sie|mein\w*|unser\w*)\b[^?.!]{0,40}\bhaushalt",
    ],
    "individual_case_status": [
        r"\b(?:stand|status|bearbeitungsstand)\b[^?.!]{0,30}\b(?:meines|meinem|unseres|unserem|mein|unser)\b",
        r"\b(?:mein|meinen|meinem|unser|unseren)\s+(?:antrag|weiterleistungsantrag|bescheid)\b[^?.!]{0,60}\b(?:noch|immer|schon|wann|bearbeitet|eingegangen|angekommen|fertig|wo)\b",
        r"\bwann\s+(?:bekomme|erhalte|kommt)\b[^?.!]{0,30}\b(?:mein|meinen|den)\s+bescheid",
        r"\[AKTENZEICHEN_\d+\]",
        r"\baktenzeichen\s+(?:ist|lautet)\b",
        r"\bich\s+habe\s+(?:einen|ein|den|das|eine)\s+(?:brief|bescheid|schreiben|rückforderung|mahnung)\b",
        r"\bmuss\s+ich\b[^?.!]{0,40}\b(?:wirklich|tatsächlich)\b[^?.!]{0,20}\b(?:zahlen|zurückzahlen|bezahlen)",
        r"\b(?:wo|wann)\s+(?:bleibt|kommt)\s+(?:mein|meine|unser)\b",
    ],
    "legal_advice": [
        r"\bsoll(?:te)?\s+(?:ich|wir)\b[^?.!]{0,30}\b(?:widerspruch|klage|klagen)",
        r"\blohnt\s+sich\b[^?.!]{0,30}\b(?:widerspruch|klage)",
        r"\b(?:chancen|aussicht|erfolgsaussicht)\w*\b[^?.!]{0,40}\b(?:widerspruch|klage)",
        r"\b(?:widerspruch|klage)\b[^?.!]{0,40}\b(?:chancen|aussicht|erfolg)",
    ],
}

# Attempts to change the assistant's rules. Always handed over, whatever the approval says.
INJECTION = [
    r"\[\s*(?:system|admin|hinweis|system-hinweis|systemhinweis)\b",
    r"\bignorier\w*\b[^.!?]{0,30}\b(?:regeln|anweisungen|vorgaben|einschränkungen)",
    r"\bdu\s+bist\s+(?:jetzt|ab\s+sofort|nun|ab\s+jetzt)\b",
    r"\b(?:system\s*-?\s*prompt|deine\s+anweisungen|deine\s+instruktionen)\b",
    r"\bantworte\s+(?:nur|bitte\s+nur|einfach)\s+mit\s+(?:ja|nein)\b",
    r"\b(?:als\s+mitarbeiter\w*\s+verifiziert|entwicklermodus|developer\s+mode)\b",
]


def injection(text: str) -> bool:
    low = text.lower()
    return any(re.search(rx, low) for rx in INJECTION)


# Statements the enquiry agent must never make: they would assess an individual's case.
FORBIDDEN_STATEMENTS = [
    r"\bSie\s+haben\s+(?:einen\s+|keinen\s+|wahrscheinlich\s+|vermutlich\s+)?(?:Anspruch|kein\s+Recht)",
    r"\bIhnen\s+steht\b",
    r"\bSie\s+(?:erhalten|bekommen)\s+(?:voraussichtlich\s+|wahrscheinlich\s+|vermutlich\s+)?(?:etwa\s+|rund\s+|ca\.\s+)?\d",
    r"\bIhr\s+Wohngeld\s+(?:beträgt|wird|liegt)",
    r"\bSie\s+sind\s+(?:nicht\s+)?(?:anspruchs)?berechtigt",
    r"\bIhr\s+Antrag\s+(?:wird|ist|wurde)\s+(?:bewilligt|abgelehnt|genehmigt)",
]


def intent(text: str, forbidden: tuple[str, ...]) -> str | None:
    """The first forbidden intent the text expresses, or None."""
    low = text.lower()
    for name in forbidden:
        for rx in INTENTS.get(name, []):
            if re.search(rx, low if not rx.startswith(r"\[") else text):
                return name
    return None


def forbidden_statement(text: str) -> str | None:
    for rx in FORBIDDEN_STATEMENTS:
        m = re.search(rx, text)
        if m:
            return m.group(0)
    return None
