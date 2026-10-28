"""Configuration loading. Everything a reviewer may want to change lives in config/*.yaml."""

from __future__ import annotations

import os
from functools import cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = Path(os.environ.get("DESK_CONFIG", ROOT / "config"))
DATA_DIR = Path(os.environ.get("DESK_DATA", ROOT / "data"))


@cache
def load(name: str) -> dict[str, Any]:
    """Load config/<name>.yaml once per process."""
    with (CONFIG_DIR / f"{name}.yaml").open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def ai_act() -> dict[str, Any]:
    return load("ai_act")


def law() -> dict[str, Any]:
    return load("german_law")


def targets() -> dict[str, Any]:
    return load("targets")


def gates() -> dict[str, Any]:
    return load("gates")


def portfolio() -> dict[str, Any]:
    return load("portfolio")


def health() -> dict[str, Any]:
    return load("health")


def class_rank(data_class: str) -> int:
    return int(targets()["data_classes"][data_class]["rank"])
