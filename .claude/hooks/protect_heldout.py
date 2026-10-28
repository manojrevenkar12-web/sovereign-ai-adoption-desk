#!/usr/bin/env python3
"""Refuse edits to blind sets and to pinned first runs (PreToolUse hook for Edit/Write)."""

import json
import sys

data = json.load(sys.stdin)
path = str(data.get("tool_input", {}).get("file_path", ""))
if "/heldout/" in path and not path.endswith(("WRITING_CASES.md", "WRITING_POV.md", "/STATUS")):
    print("Blind sets are written by someone who has not seen the code. Do not edit them.", file=sys.stderr)
    sys.exit(2)
if "/reports/heldout/" in path and path.endswith("first_run.json"):
    print("First runs are pinned and never rewritten.", file=sys.stderr)
    sys.exit(2)
