"""The documents a proof of value may answer from, split into citable passages, with search.

Search is BM25 over sentences with German-aware matching: light suffix stripping, and compound
matching by prefix ("Wohngeldstelle" matches "Wohngeld"), so a citizen's wording finds the office's.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import yaml

from desk import settings

STOP = set(
    [
        "der",
        "die",
        "das",
        "den",
        "dem",
        "des",
        "ein",
        "eine",
        "einer",
        "eines",
        "einem",
        "einen",
        "und",
        "oder",
        "aber",
        "auch",
        "als",
        "am",
        "an",
        "auf",
        "aus",
        "bei",
        "bis",
        "durch",
        "für",
        "fur",
        "gegen",
        "im",
        "in",
        "ist",
        "sind",
        "war",
        "wird",
        "werden",
        "wurde",
        "kann",
        "können",
        "konnen",
        "muss",
        "müssen",
        "mussen",
        "soll",
        "sollen",
        "mit",
        "nach",
        "nicht",
        "noch",
        "nur",
        "ob",
        "ohne",
        "so",
        "über",
        "uber",
        "um",
        "unter",
        "von",
        "vor",
        "wie",
        "wo",
        "zu",
        "zum",
        "zur",
        "es",
        "er",
        "sie",
        "ich",
        "mein",
        "meine",
        "meinen",
        "meiner",
        "mir",
        "mich",
        "wir",
        "uns",
        "ihr",
        "ihre",
        "ihren",
        "ihrem",
        "sein",
        "seine",
        "seinen",
        "was",
        "wer",
        "wann",
        "welche",
        "welcher",
        "welches",
        "wenn",
        "dann",
        "denn",
        "da",
        "dass",
        "daß",
        "sich",
        "selbst",
        "schon",
        "sehr",
        "mehr",
        "viel",
        "gibt",
        "habe",
        "hat",
        "haben",
        "hatte",
        "bitte",
        "danke",
        "hallo",
        "guten",
        "tag",
        "frage",
        "fragen",
        "gerne",
        "man",
        "mal",
        "etwa",
        "ja",
        "nein",
        "lassen",
        "lasse",
        "gehen",
        "geht",
        "machen",
        "macht",
        "tun",
        "gibt",
        "geben",
        "gab",
        "alle",
        "alles",
        "jede",
        "jeder",
        "jedes",
        "dies",
        "diese",
        "dieser",
        "dieses",
        "hier",
        "dort",
        "bereits",
        "immer",
        "wieder",
        "eigentlich",
        "genau",
        "einfach",
        "überhaupt",
        "uberhaupt",
        "wohl",
        "doch",
        "also",
        "wirklich",
        "bekannt",
    ]
)
SUFFIXES = ("ungen", "ung", "en", "er", "es", "et", "e", "n", "s")


def norm(token: str) -> str:
    t = token.lower().replace("ß", "ss")
    for s in SUFFIXES:
        if len(t) > len(s) + 3 and t.endswith(s):
            return t[: -len(s)]
    return t


def tokens(text: str) -> list[str]:
    return [norm(t) for t in re.findall(r"[A-Za-zÄÖÜäöüß0-9]+", text) if t.lower() not in STOP and len(t) > 1]


@dataclass(frozen=True)
class Passage:
    id: str  # DOC#n
    doc: str
    title: str
    text: str
    classification: str
    unit: str


@dataclass(frozen=True)
class Document:
    id: str
    title: str
    classification: str
    unit: str
    date: str
    passages: tuple[Passage, ...]


def _split(body: str) -> list[str]:
    out: list[str] = []
    for para in body.strip().split("\n"):
        para = para.strip()
        if not para:
            continue
        pieces = [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-ZÄÖÜ])", para) if s.strip()]
        for piece in pieces:
            # "am 1. September" is not a sentence end
            if out and re.search(r"(?:^|\s)\d{1,2}\.$", out[-1]):
                out[-1] = f"{out[-1]} {piece}"
            else:
                out.append(piece)
    return out


@cache
def load(name: str) -> tuple[Document, ...]:
    d: Path = settings.DATA_DIR / "corpus" / name
    docs = []
    for f in sorted(d.glob("*.md")):
        _, front, body = f.read_text(encoding="utf-8").split("---", 2)
        meta = yaml.safe_load(front)
        sentences = _split(body)
        passages = tuple(
            Passage(f"{meta['id']}#{i + 1}", meta["id"], meta["title"], s, meta["classification"], meta.get("unit", ""))
            for i, s in enumerate(sentences)
        )
        docs.append(
            Document(
                meta["id"],
                meta["title"],
                meta["classification"],
                meta.get("unit", ""),
                str(meta.get("date", "")),
                passages,
            )
        )
    return tuple(docs)


def _match(q: str, d: str) -> bool:
    """Same word, or one is a compound or inflection of the other ("abgleicht" ~ "Datenabgleich")."""
    if q == d:
        return True
    if min(len(q), len(d)) >= 5 and (d.startswith(q) or q.startswith(d)):
        return True
    if len(q) >= 6 and q[: max(5, len(q) - 2)] in d:
        return True
    return len(d) >= 6 and d[: max(5, len(d) - 2)] in q


class Index:
    def __init__(self, docs: tuple[Document, ...]):
        self.passages = [p for d in docs for p in d.passages]
        self.docs = {d.id: d for d in docs}
        self.toks = [tokens(p.title + " " + p.text) for p in self.passages]
        self.avg = sum(len(t) for t in self.toks) / max(1, len(self.toks))
        self.vocab = {t for ts in self.toks for t in ts}
        self.doc_toks = {d.id: tokens(d.title + " " + " ".join(p.text for p in d.passages)) for d in docs}

    def _expand(self, query: str) -> dict[str, set[str]]:
        syn = settings.load("pov").get("synonyms", {}) or {}
        qt = list(dict.fromkeys(tokens(query)))
        qt += [x for q in list(qt) for x in syn.get(q, []) if x not in qt]
        return {q: {v for v in self.vocab if _match(q, v)} for q in qt}

    def _bm25(self, expanded: dict[str, set[str]], toks: list[list[str]], avg: float) -> list[float]:
        n = len(toks)
        df = {q: sum(1 for ts in toks if e & set(ts)) for q, e in expanded.items()}
        out = []
        for ts in toks:
            c = Counter(ts)
            s = 0.0
            for q, e in expanded.items():
                tf = sum(c[v] for v in e)
                if tf:
                    idf = math.log(1 + (n - df[q] + 0.5) / (df[q] + 0.5))
                    s += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * len(ts) / avg))
            out.append(s)
        return out

    def search(self, query: str, k: int = 4, max_rank: int = 99) -> list[tuple[Passage, float]]:
        """Passages scored by their own BM25 plus half their document's, so context counts."""
        expanded = self._expand(query)
        pass_scores = self._bm25(expanded, self.toks, self.avg)
        doc_ids = list(self.docs)
        doc_toks = [self.doc_toks[d] for d in doc_ids]
        doc_avg = sum(len(t) for t in doc_toks) / max(1, len(doc_toks))
        doc_score = dict(zip(doc_ids, self._bm25(expanded, doc_toks, doc_avg), strict=True))
        scores = []
        for p, ps in zip(self.passages, pass_scores, strict=True):
            if settings.class_rank(p.classification) > max_rank or ps <= 0:
                continue
            scores.append((p, ps + 0.5 * doc_score[p.doc]))
        scores.sort(key=lambda x: -x[1])
        return scores[:k]

    def coverage(self, query: str, doc_ids: set[str]) -> float:
        texts = [p.text + " " + p.title for p in self.passages if p.doc in doc_ids]
        return coverage(query, texts)


def question_part(text: str) -> str:
    """The sentences that ask something; citizens often explain their situation first."""
    qs = [s for s in re.split(r"(?<=[?.!])\s+", text) if s.strip().endswith("?")]
    return " ".join(qs) if qs else text


def coverage(query: str, texts: list[str]) -> float:
    """Share of the question's content words found in the texts (inflections, compounds and synonyms count)."""
    syn = settings.load("pov").get("synonyms", {}) or {}
    qt = list(dict.fromkeys(tokens(question_part(query))))
    if not qt:
        return 0.0
    have = {t for x in texts for t in tokens(x)}
    hit = 0
    for q in qt:
        alts = [q, *syn.get(q, [])]
        if any(_match(a, h) for a in alts for h in have):
            hit += 1
    return hit / len(qt)


@cache
def index(name: str) -> Index:
    return Index(load(name))


QUANTITY = re.compile(
    r"\b(?:wie\s+viele?|wie\s+hoch|welche[rs]?\s+anteil|wie\s+lange|wie\s+oft|in\s+welcher\s+höhe)\b", re.I
)
NUMBER = re.compile(
    r"\d|\b(?:ein|eine|zwei|drei|vier|fünf|sechs|sieben|acht|neun|zehn|elf|zwölf|hundert|tausend|million\w*|monat\w*|woche\w*|jahr\w*)\b",
    re.I,
)
INTERROGATIVE = re.compile(
    r"(?i:\b(?:wie\s+viele?|wie\s+hoch(?:\s+(?:ist|sind|war|waren))?|welche[rs]?\s+anteil)\b"
    r"(?:\s+(?:ist|sind|war|waren|wird|werden|wurde|wurden|hat|haben|der|die|das|den|dem|des|anteil|art))*)\s+([A-ZÄÖÜ][\wäöüß-]+)",
)


def focus_missing(question: str, texts: list[str]) -> str | None:
    """Why the passages cannot answer the specific thing asked, or None.

    A question for a quantity needs a number in the passages, and the noun it counts
    ("Wie hoch sind die *Gesamtkosten*", "Wie viele *Beschwerden*") must appear in them.
    """
    q = question_part(question)
    joined = " ".join(texts)
    if QUANTITY.search(q) and not NUMBER.search(joined):
        return "asks for a quantity the passages do not state"
    m = INTERROGATIVE.search(q)
    if m:
        focus = norm(m.group(1))
        have = set(tokens(joined))
        if focus not in STOP and not any(_match(focus, h) for h in have):
            return f"asks about {m.group(1)!r}, which the passages do not mention"
    return None
