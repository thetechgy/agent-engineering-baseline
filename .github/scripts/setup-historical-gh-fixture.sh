#!/usr/bin/env bash
# Acquire the authored Git evidence for the frozen gh replay tests.
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)
revision=5bdc85e358d2ee0e13327cc8809701cba924dab8
dataset=.github/evals/gh/evals/evals.json
digest=7da7fa863ddc768c34bb423b4667cfe43e8d714697c4e217e4a27d789028f598
export GIT_NO_REPLACE_OBJECTS=1
if ! git -C "$root" cat-file -e "$revision^{commit}" 2>/dev/null; then
  # The squash merge left this reviewed fixture commit outside branch history.
  git -C "$root" fetch --no-tags --no-write-fetch-head \
    https://github.com/thetechgy/agent-engineering-baseline.git "$revision"
fi
test "$(git -C "$root" cat-file -t "$revision")" = commit
git -C "$root" cat-file blob "$revision:$dataset" | sha256sum --check --strict --status <(printf '%s  -\n' "$digest")
