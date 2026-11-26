#!/usr/bin/env bash
# Install the released evaluator for static quality, public data, or startup qualification.
set -euo pipefail
umask 077

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)
kind=${1:-quality-static}
case "$kind" in
  quality-next) exec bash "$root/.github/scripts/setup-skillevaluator.sh" quality-next ;;
  quality-static|scanner-contracts|data-host|native-startup|native-benchmark-candidate|native-benchmark-101|review-candidate|review-contracts) ;;
  *) exit 2 ;;
esac
: "${RUNNER_TEMP:?}" "${GITHUB_WORKSPACE:?}" "${GITHUB_ENV:?}"
tools="$RUNNER_TEMP/skill-evaluation-tools"
if [ "$kind" = data-host ]; then tools="$RUNNER_TEMP/skill-data-host"; fi
if [ "$kind" = scanner-contracts ]; then tools="$RUNNER_TEMP/skill-scanner-contracts"; fi
if [ "$kind" = native-startup ]; then tools="$RUNNER_TEMP/skill-native-startup"; fi
if [[ "$kind" == native-benchmark-* ]]; then tools="$RUNNER_TEMP/skill-$kind"; fi
if [[ "$kind" == review-* ]]; then tools="$RUNNER_TEMP/skill-$kind"; fi
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
if [[ "$kind" == review-* ]]; then
  pins=$(PYTHONPATH="$root/.github/scripts" python3 -B -c '
import private_review_runtime as owner
print(owner.PYTHON, owner.LOCK)
')
  read -r python_version overlay_digest <<< "$pins"
fi
evaluator="$tools/evaluator"
git init --quiet "$evaluator"
git -C "$evaluator" fetch --quiet --depth=1 https://github.com/NVIDIA/SkillEvaluator.git "$revision"
git -C "$evaluator" checkout --quiet --detach FETCH_HEAD
test "$(git -C "$evaluator" rev-parse HEAD)" = "$revision"
printf '%s  %s\n' "$lock" "$evaluator/uv.lock" | sha256sum --check --strict
extras=()
if [[ "$kind" == quality-static || "$kind" == scanner-contracts ]]; then extras=(--extra security --extra tier3); fi
if [[ "$kind" == native-startup || "$kind" == native-benchmark-* ]]; then extras=(--extra tier3); fi
uv sync --project "$evaluator" --python "$python_version" --managed-python --frozen --no-dev "${extras[@]}"
python="$evaluator/.venv/bin/python"
uv pip check --python "$python"
if [[ "$kind" == review-* ]]; then
  overlay="$root/.github/requirements/review-101.txt"
  printf '%s  %s\n' "$overlay_digest" "$overlay" | sha256sum --check --strict
  uv pip install --python "$python" --no-deps --only-binary :all: --require-hashes --requirement "$overlay"
  if [ "$kind" = review-contracts ]; then
    tests="$root/.github/requirements/review-tests-101.txt"
    printf '%s  %s\n' d481a93aba488792854fc18b9376d0eafeadc3e25320db8e18ac2c52a1d347d5 "$tests" | sha256sum --check --strict
    uv pip install --python "$python" --no-deps --only-binary :all: --require-hashes --requirement "$tests"
  fi
  uv pip check --python "$python"
  PYTHONPATH="$root/.github/scripts" "$python" -B -c 'import private_review_runtime; private_review_runtime.validate_install()'
  printf 'SKILL_REVIEW_CANDIDATE_PYTHON=%s\n' "$python" >> "$GITHUB_ENV"
  exit 0
fi
if [[ "$kind" == native-startup || "$kind" == native-benchmark-* ]]; then
  PYTHONPATH="$root/.github/scripts" "$python" -B -c 'import static_evaluator; static_evaluator.validate_install()'
  wheel_version=1.2.0
  wheel_kind=--release-startup
  wheel_digest=c76a4689f6b59b1b221e4b4fc8445869e9f1c923edbe995f2909cd9d227b1fb3
  python_export=SKILL_NATIVE_STARTUP_PYTHON
  if [[ "$kind" == native-benchmark-* ]]; then
    patch="$root/.github/patches/skillevaluator-v1.0.1-benchmark-request.patch"
    printf '%s  %s\n' 029ac12e32476d83b5a8555291b7c094be7df3262cd862396ddff1b453ec1821 "$patch" | sha256sum --check --strict
    git -C "$evaluator" apply --check "$patch"
    git -C "$evaluator" apply "$patch"
    wheel_version=1.3.2
    wheel_kind=--benchmark-candidate
    wheel_digest=0899cdc4c270d5fe817b256c099457551f6b273b65aaf5418da99ae5ff60052b
    python_export=SKILL_NATIVE_BENCHMARK_CANDIDATE_PYTHON
  fi
  if [ "$kind" = native-benchmark-101 ]; then
    staging_patch="$root/.github/patches/skillevaluator-v1.0.1-benchmark-staging.patch"
    printf '%s  %s\n' a997da90485a79696b83481e403359d4ad33cd40300986b499efc8c3cc70cbd6 "$staging_patch" | sha256sum --check --strict
    git -C "$evaluator" apply --check "$staging_patch"
    git -C "$evaluator" apply "$staging_patch"
    recovery_patch="$root/.github/patches/skillevaluator-v1.0.1-benchmark-recovery.patch"
    printf '%s  %s\n' 44a766ab7cb7bcf38bc0769fc8f87fc6edf20997363ec0341d252edc93dca0b5 "$recovery_patch" | sha256sum --check --strict
    git -C "$evaluator" apply --check "$recovery_patch"
    git -C "$evaluator" apply "$recovery_patch"
    evidence_patch="$root/.github/patches/skillevaluator-v1.0.1-benchmark-evidence.patch"
    printf '%s  %s\n' 45923e37bf4dd71b0c1b3c38390dd6c32c8f2ea234f9634cb04fbb0f48232c75 "$evidence_patch" | sha256sum --check --strict
    git -C "$evaluator" apply --check "$evidence_patch"
    git -C "$evaluator" apply "$evidence_patch"
    python_export=SKILL_NATIVE_BENCHMARK_PYTHON
  fi
  "$python" -IB "$root/.github/evaluator-backends/build_wheel.py" "$tools/backend-wheel" "$wheel_kind"
  printf '%s  %s\n' "$wheel_digest" "$tools/backend-wheel/aeb_gh_fixture-$wheel_version-py3-none-any.whl" | sha256sum --check --strict
  uv pip install --python "$python" --no-deps --no-index --link-mode copy --require-hashes --only-binary :all: \
    --requirement "$tools/backend-wheel/requirements.txt"
  uv pip check --python "$python"
  "$python" -IB -c 'from aeb_gh_fixture.backend import require_runtime; require_runtime()'
  if [ "$kind" = native-benchmark-101 ]; then
    "$python" -B "$root/.github/scripts/benchmark_native.py" verify-runtime
  fi
  printf '%s=%s\n' "$python_export" "$python" >> "$GITHUB_ENV"
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
if [ "$kind" = scanner-contracts ]; then
  patch="$root/.github/patches/skillevaluator-v1.0.1-scanner-contracts.patch"
  printf '%s  %s\n' d974793bb66d3629cb3b2d74a6cad2c1f21e8ee9f1787b256cc4b22eb1751c2b "$patch" | sha256sum --check --strict
  git -C "$evaluator" apply --check "$patch"
  git -C "$evaluator" apply "$patch"
  PYTHONPATH="$root/.github/scripts" "$python" -B -c 'import static_evaluator; static_evaluator.validate_install(scanner_contracts=True)'
  printf 'SKILL_SCANNER_CONTRACT_PYTHON=%s\nSKILL_SCANNER_CONTRACT_TOOLS=%s\n' "$python" "$tools" >> "$GITHUB_ENV"
  exit 0
fi
uv pip list --python "$python" --format json > "$tools/dependencies/evaluator.json"
"$python" -B "$root/.github/scripts/static_quality_ci.py" versions --tools "$tools"

printf 'SKILL_QUALITY_PYTHON=%s\nSKILL_QUALITY_TOOLS=%s\nXDG_CACHE_HOME=%s\nXDG_STATE_HOME=%s\n' \
  "$python" "$tools" "$XDG_CACHE_HOME" "$XDG_STATE_HOME" >> "$GITHUB_ENV"
