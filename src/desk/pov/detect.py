"""Personal identifiers in German administrative text, and reversible pseudonymisation.

Validated where a check digit exists (IBAN mod 97, Steuer-ID ISO 7064 MOD 11,10), pattern-based
otherwise. Placeholders replace values before any model call; the reply is restored afterwards.
Free-form identifiers can still slip through: the DPIA keeps that residual risk.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

STREET = r"[A-ZÄÖÜ][a-zäöüß\-]+(?:straße|strasse|str\.|weg|platz|allee|gasse|ring|damm)\s+\d+[a-z]?"


def iban_ok(s: str) -> bool:
    s = re.sub(r"\s", "", s).upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", s):
        return False
    n = "".join(str(int(ch, 36)) for ch in s[4:] + s[:4])
    return int(n) % 97 == 1


def steuer_id_ok(s: str) -> bool:
    d = re.sub(r"\D", "", s)
    if len(d) != 11 or d[0] == "0":
        return False
    counts = [d[:10].count(x) for x in set(d[:10])]
    if not (max(counts) in (2, 3) and len(set(d[:10])) in (8, 9)):
        return False
    product = 10
    for ch in d[:10]:
        total = (int(ch) + product) % 10
        if total == 0:
            total = 10
        product = (total * 2) % 11
    check = 11 - product
    return (0 if check == 10 else check) == int(d[10])


PATTERNS: list[tuple[str, re.Pattern[str], object]] = [
    ("IBAN", re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}(?:\s?[A-Z0-9]{1,3})?\b"), iban_ok),
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), None),
    ("AKTENZEICHEN", re.compile(r"\b(?:Az\.?\s*:?\s*)?[A-Z]{2,4}-\d{4}-\d{3,7}\b"), None),
    ("STEUER_ID", re.compile(r"\b\d{2}\s?\d{3}\s?\d{3}\s?\d{3}\b"), steuer_id_ok),
    ("SVNR", re.compile(r"\b\d{2}\s?\d{6}\s?[A-Z]\s?\d{3}\b"), None),
    ("TELEFON", re.compile(r"(?<![\w-])(?:\+49|0049|0)[\s/-]?\d{2,5}[\s/-]?\d{3,9}(?:[\s-]?\d{1,5})?(?![\w-])"), None),
    ("GEBURTSDATUM", re.compile(r"\b(?:geb(?:oren)?\.?\s*(?:am\s*)?)\d{1,2}\.\d{1,2}\.\d{2,4}\b", re.I), None),
    ("ADRESSE", re.compile(STREET), None),
    (
        "NAME",
        re.compile(
            r"(?:(?<=Herr )|(?<=Frau )|(?<=Herrn )|(?<=heiße )|(?<=heisse )|(?<=Name ist )|(?<=Name: ))"
            r"[A-ZÄÖÜ][a-zäöüß]+(?:[\s-][A-ZÄÖÜ][a-zäöüß]+)?"
        ),
        None,
    ),
]


@dataclass
class Pseudonymised:
    text: str
    mapping: dict[str, str] = field(default_factory=dict)  # placeholder -> original
    kinds: list[str] = field(default_factory=list)

    def restore(self, text: str) -> str:
        for ph, orig in self.mapping.items():
            text = text.replace(ph, orig)
        return text


def find(text: str) -> list[tuple[str, int, int, str]]:
    """(kind, start, end, value) for every identifier, longest first where they overlap."""
    hits: list[tuple[str, int, int, str]] = []
    for kind, rx, check in PATTERNS:
        for m in rx.finditer(text):
            if check is not None and not check(m.group(0)):  # type: ignore[operator]
                continue
            hits.append((kind, m.start(), m.end(), m.group(0)))
    hits.sort(key=lambda h: (h[1], -(h[2] - h[1])))
    out: list[tuple[str, int, int, str]] = []
    end = -1
    for h in hits:
        if h[1] >= end:
            out.append(h)
            end = h[2]
    return out


def pseudonymise(text: str) -> Pseudonymised:
    hits = find(text)
    counters: dict[str, int] = {}
    seen: dict[str, str] = {}
    out, last = [], 0
    p = Pseudonymised(text)
    for kind, s, e, value in hits:
        if value not in seen:
            counters[kind] = counters.get(kind, 0) + 1
            seen[value] = f"[{kind}_{counters[kind]}]"
            p.mapping[seen[value]] = value
            p.kinds.append(kind)
        out.append(text[last:s])
        out.append(seen[value])
        last = e
    out.append(text[last:])
    p.text = "".join(out)
    return p


def contains_identifier(text: str) -> list[str]:
    return [k for k, *_ in find(text)]
