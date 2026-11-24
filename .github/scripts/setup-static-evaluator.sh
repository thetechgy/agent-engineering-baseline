#!/usr/bin/env bash
# Install the released evaluator for static quality, public data, or startup qualification.
set -euo pipefail
umask 077

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)
kind=${1:-quality-static}
case "$kind" in
  quality-next) exec bash "$root/.github/scripts/setup-skillevaluator.sh" quality-next ;;
  quality-static|data-host|native-startup) ;;
  *) exit 2 ;;
esac
: "${RUNNER_TEMP:?}" "${GITHUB_WORKSPACE:?}" "${GITHUB_ENV:?}"
tools="$RUNNER_TEMP/skill-evaluation-tools"
if [ "$kind" = data-host ]; then tools="$RUNNER_TEMP/skill-data-host"; fi
if [ "$kind" = native-startup ]; then tools="$RUNNER_TEMP/skill-native-startup"; fi
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
if [ "$kind" = native-startup ]; then extras=(--extra tier3); fi
uv sync --project "$evaluator" --python "$python_version" --managed-python --frozen --no-dev "${extras[@]}"
python="$evaluator/.venv/bin/python"
uv pip check --python "$python"
if [ "$kind" = native-startup ]; then
  PYTHONPATH="$root/.github/scripts" "$python" -B -c 'import static_evaluator; static_evaluator.validate_install()'
  "$python" -IB "$root/.github/evaluator-backends/build_wheel.py" "$tools/backend-wheel" --release-startup
  printf '%s  %s\n' c76a4689f6b59b1b221e4b4fc8445869e9f1c923edbe995f2909cd9d227b1fb3 \
    "$tools/backend-wheel/aeb_gh_fixture-1.2.0-py3-none-any.whl" | sha256sum --check --strict
  uv pip install --python "$python" --no-deps --no-index --link-mode copy --require-hashes --only-binary :all: \
    --requirement "$tools/backend-wheel/requirements.txt"
  uv pip check --python "$python"
  "$python" -IB -c 'from aeb_gh_fixture.backend import require_runtime; require_runtime()'
  printf 'SKILL_NATIVE_STARTUP_PYTHON=%s\n' "$python" >> "$GITHUB_ENV"
  exit 0
fi
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
