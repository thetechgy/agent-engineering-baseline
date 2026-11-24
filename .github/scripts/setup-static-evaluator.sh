#!/usr/bin/env bash
# Install the released evaluator for static quality or public data processing.
set -euo pipefail
umask 077

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)
kind=${1:-quality-static}
case "$kind" in
  quality-next) exec bash "$root/.github/scripts/setup-skillevaluator.sh" quality-next ;;
  quality-static|data-host) ;;
  *) exit 2 ;;
esac
: "${RUNNER_TEMP:?}" "${GITHUB_WORKSPACE:?}" "${GITHUB_ENV:?}"
tools="$RUNNER_TEMP/skill-evaluation-tools"
if [ "$kind" = data-host ]; then tools="$RUNNER_TEMP/skill-data-host"; fi
case "$(realpath -m "$tools")/" in
  "$(realpath "$GITHUB_WORKSPACE")/"*|"$root/"*) echo 'Tools must be outside the checkout.' >&2; exit 1 ;;
esac
mkdir -m 700 "$tools"
test "$(uv --version | awk '{print $2}')" = '0.13.9'
export UV_CACHE_DIR="$tools/uv-cache"
export UV_PYTHON_INSTALL_DIR="$tools/python"
export XDG_CACHE_HOME="$tools/cache"
export XDG_STATE_HOME="$tools/state"

# Static collection also requires the native CLI's strict dataset and scanner extras.
pins=$(PYTHONPATH="$root/.github/scripts" python3 -B -c '
import static_evaluator as owner
print(owner.REVISION, owner.LOCK, owner.VERSIONS["python"])
')
read -r revision lock python_version <<< "$pins"
evaluator="$tools/evaluator"
git init --quiet "$evaluator"
git -C "$evaluator" fetch --quiet --depth=1 https://github.com/NVIDIA/SkillEvaluator.git "$revision"
git -C "$evaluator" checkout --quiet --detach FETCH_HEAD
test "$(git -C "$evaluator" rev-parse HEAD)" = "$revision"
printf '%s  %s\n' "$lock" "$evaluator/uv.lock" | sha256sum --check --strict
extras=()
if [ "$kind" = quality-static ]; then extras=(--extra security --extra tier3); fi
uv sync --project "$evaluator" --python "$python_version" --managed-python --frozen --no-dev "${extras[@]}"
python="$evaluator/.venv/bin/python"
uv pip check --python "$python"
if [ "$kind" = data-host ]; then
  PYTHONPATH="$root/.github/scripts" "$python" -B -c 'import static_evaluator; static_evaluator.validate_install()'
  "$evaluator/.venv/bin/skillevaluator" --version
  printf 'SKILL_DATA_PYTHON=%s\n' "$python" >> "$GITHUB_ENV"
  exit 0
fi

mkdir "$tools/bin" "$tools/dependencies"
# shellcheck source-path=SCRIPTDIR
# shellcheck source=setup-skill-scanners.sh
source "$root/.github/scripts/setup-skill-scanners.sh"
install_skill_scanners "$tools" "$evaluator/.venv/bin" "$root"
uv pip list --python "$python" --format json > "$tools/dependencies/evaluator.json"
"$python" -B "$root/.github/scripts/static_quality_ci.py" versions --tools "$tools"

printf 'SKILL_QUALITY_PYTHON=%s\nSKILL_QUALITY_TOOLS=%s\nXDG_CACHE_HOME=%s\nXDG_STATE_HOME=%s\n' \
  "$python" "$tools" "$XDG_CACHE_HOME" "$XDG_STATE_HOME" >> "$GITHUB_ENV"
