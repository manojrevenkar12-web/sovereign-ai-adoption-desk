#!/usr/bin/env bash
# Run a command; on failure, turn its error lines into GitHub annotations so reviewers see them first.
set -o pipefail
log=$(mktemp)
"$@" 2>&1 | tee "$log"
status=${PIPESTATUS[0]}
if [ "$status" -ne 0 ]; then
  grep -E "FAILED|Error|error|✘|failed|AssertionError" "$log" | head -20 | while IFS= read -r line; do
    echo "::error::$(echo "$line" | cut -c1-300)"
  done
  echo "::error::last lines: $(tail -5 "$log" | tr '\n' ' ' | cut -c1-600)"
fi
exit "$status"
