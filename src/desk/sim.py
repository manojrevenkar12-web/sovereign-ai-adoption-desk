"""Fictional weekly usage exports for the fictional customers (deterministic, seeded).

Shapes, not secrets: STMV is broad and healthy except one department without a champion; BAFM
declines after its programme champion's team lost interest; LWS grows during its pilot.
"""

from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

from desk import settings

WEEKS = 26
FIRST = date(2026, 5, 4)

PROFILES: dict[str, dict[str, tuple[int, float, float, float]]] = {
    # department: (seats, start activation, end activation, messages per active user)
    "stmv": {
        "Zentralabteilung": (380, 0.48, 0.66, 31),
        "Digitales": (260, 0.62, 0.78, 44),
        "Haushalt": (220, 0.40, 0.58, 22),
        "Recht": (340, 0.22, 0.19, 9),
    },
    "bafm": {
        "Programme": (150, 0.55, 0.30, 18),
        "Prüfung": (90, 0.35, 0.20, 12),
        "Personal": (60, 0.45, 0.47, 20),
    },
    "lws": {
        "Wohngeld": (110, 0.15, 0.52, 19),
        "Bürgerservice": (40, 0.20, 0.61, 27),
    },
}


def generate(directory: Path | None = None, seed: int = 7) -> list[Path]:
    d = directory or settings.DATA_DIR / "usage"
    d.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(seed)
    out = []
    for cid, deps in PROFILES.items():
        path = d / f"{cid}.csv"
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(
                [
                    "week",
                    "department",
                    "seats",
                    "weekly_active_users",
                    "messages",
                    "gpt_messages",
                    "projects_active",
                    "connector_calls",
                ]
            )
            for i in range(WEEKS):
                week = FIRST + timedelta(weeks=i)
                t = i / (WEEKS - 1)
                for dep, (seats, a0, a1, mpu) in deps.items():
                    # declines happen late: the last third carries most of a fall
                    shape = t if a1 >= a0 else min(1.0, max(0.0, (t - 0.55) / 0.45))
                    act = max(0.0, a0 + (a1 - a0) * shape + rnd.uniform(-0.03, 0.03))
                    if week.month == 8:
                        act *= 0.8  # summer holidays
                    wau = round(seats * act)
                    msgs = round(wau * mpu * rnd.uniform(0.85, 1.15))
                    w.writerow(
                        [
                            week.isoformat(),
                            dep,
                            seats,
                            wau,
                            msgs,
                            round(msgs * 0.22),
                            round(wau * 0.15),
                            round(msgs * 0.05),
                        ]
                    )
        out.append(path)
    return out


if __name__ == "__main__":
    for p in generate():
        print(p)
