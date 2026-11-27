#!/usr/bin/env bash
# Install the released evaluator for static quality, public data, or startup qualification.
set -euo pipefail
umask 077

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)
kind=${1:-quality-static}
case "$kind" in
  quality-next) exec bash "$root/.github/scripts/setup-skillevaluator.sh" quality-next ;;
  quality-static|quality-retained-101|scanner-contracts|data-host|native-startup|native-benchmark-candidate|native-benchmark-candidate-101|native-benchmark-101|native-benchmark-121|review-candidate|review-contracts|review-retained-101|review-retained-121) ;;
  *) exit 2 ;;
esac
: "${RUNNER_TEMP:?}" "${GITHUB_WORKSPACE:?}" "${GITHUB_ENV:?}"
tools="$RUNNER_TEMP/skill-evaluation-tools"
if [ "$kind" = quality-retained-101 ]; then tools="$RUNNER_TEMP/skill-quality-retained-101"; fi
if [ "$kind" = data-host ]; then tools="$RUNNER_TEMP/skill-data-host"; fi
if [ "$kind" = scanner-contracts ]; then tools="$RUNNER_TEMP/skill-scanner-contracts"; fi
if [ "$kind" = native-startup ]; then tools="$RUNNER_TEMP/skill-native-startup"; fi
if [[ "$kind" == native-benchmark-* ]]; then tools="$RUNNER_TEMP/skill-$kind"; fi
if [[ "$kind" == review-* ]]; then tools="$RUNNER_TEMP/skill-$kind"; fi
case "$(realpath -m "$tools")/" in
  "$(realpath "$GITHUB_WORKSPACE")/"*|"$root/"*) echo 'Tools must be outside the checkout.' >&2; exit 1 ;;
esac
mkdir -m 700 "$tools"
test "$(uv --version | awk '{print $2}')" = '0.13.10'
export UV_CACHE_DIR="$tools/uv-cache"
export UV_PYTHON_INSTALL_DIR="$tools/python"
export XDG_CACHE_HOME="$tools/cache"
export XDG_STATE_HOME="$tools/state"

# Static collection also requires the native CLI's strict dataset and scanner extras.
pins=$(PYTHONPATH="$root/.github/scripts" python3 -B -c '
import sys
import static_evaluator as owner
pins = owner.RETAINED if sys.argv[1].endswith("-101") else owner.VERSIONS
print(pins["evaluator_revision"], pins["lock_sha256"], pins["python"], pins["skillevaluator"])
' "$kind")
read -r revision lock python_version release_version <<< "$pins"
if [[ "$kind" == review-* ]]; then
  pins=$(PYTHONPATH="$root/.github/scripts" python3 -B -c '
import sys
import private_review_runtime as owner
retained = sys.argv[1].startswith("review-retained-")
print(owner.PYTHON, owner.RETAINED_LOCK if retained else owner.LOCK)
' "$kind")
  read -r python_version overlay_digest <<< "$pins"
fi
evaluator="$tools/evaluator"
git init --quiet "$evaluator"
git -C "$evaluator" fetch --quiet --depth=1 https://github.com/NVIDIA/SkillEvaluator.git "$revision"
git -C "$evaluator" checkout --quiet --detach FETCH_HEAD
test "$(git -C "$evaluator" rev-parse HEAD)" = "$revision"
printf '%s  %s\n' "$lock" "$evaluator/uv.lock" | sha256sum --check --strict
extras=()
if [[ "$kind" == quality-* || "$kind" == scanner-contracts ]]; then extras=(--extra security --extra tier3); fi
if [[ "$kind" == native-startup || "$kind" == native-benchmark-* ]]; then extras=(--extra tier3); fi
uv sync --project "$evaluator" --python "$python_version" --managed-python --frozen --no-dev "${extras[@]}"
python="$evaluator/.venv/bin/python"
uv pip check --python "$python"
if [[ "$kind" == review-* ]]; then
  overlay="$root/.github/requirements/review-121-v2.txt"
  profile=active
  case "$kind" in
    review-retained-101|review-retained-121) overlay="$root/.github/requirements/review-101.txt" ;;
  esac
  if [ "$kind" = review-retained-101 ]; then profile=review-101; fi
  if [ "$kind" = review-retained-121 ]; then profile=review-121-v1; fi
  printf '%s  %s\n' "$overlay_digest" "$overlay" | sha256sum --check --strict
  uv pip install --python "$python" --no-deps --only-binary :all: --require-hashes --requirement "$overlay"
  if [ "$kind" = review-contracts ]; then
    tests="$root/.github/requirements/review-tests-101.txt"
    printf '%s  %s\n' d481a93aba488792854fc18b9376d0eafeadc3e25320db8e18ac2c52a1d347d5 "$tests" | sha256sum --check --strict
    uv pip install --python "$python" --no-deps --only-binary :all: --require-hashes --requirement "$tests"
  fi
  uv pip check --python "$python"
  review_export=SKILL_REVIEW_CANDIDATE_PYTHON
  case "$kind" in
    review-retained-101) review_export=SKILL_REVIEW_RETAINED_PYTHON ;;
    review-retained-121) review_export=SKILL_REVIEW_RETAINED_121_PYTHON ;;
  esac
  PYTHONPATH="$root/.github/scripts" "$python" -B -c '
import sys
import private_review_runtime
private_review_runtime.validate_install(sys.argv[1])
' "$profile"
  printf '%s=%s\n' "$review_export" "$python" >> "$GITHUB_ENV"
  exit 0
fi
apply_evaluator_patch() {
  local name=$1 digest=$2 patch
  patch="$root/.github/patches/skillevaluator-v$release_version-$name.patch"
  printf '%s  %s\n' "$digest" "$patch" | sha256sum --check --strict
  git -C "$evaluator" apply --check "$patch"
  git -C "$evaluator" apply "$patch"
}

if [[ "$kind" == native-startup || "$kind" == native-benchmark-* ]]; then
  PYTHONPATH="$root/.github/scripts" "$python" -B -c '
import sys
import static_evaluator as owner
owner.validate_install(owner=owner.RETAINED if sys.argv[1] == "1.0.1" else owner.VERSIONS)
' "$release_version"
  python_export=SKILL_NATIVE_BENCHMARK_CANDIDATE_PYTHON
  if [ "$kind" = native-startup ]; then python_export=SKILL_NATIVE_STARTUP_PYTHON; fi
  if [ "$release_version" = 1.0.1 ]; then
    wheel_version=1.3.2
    wheel_kind=--benchmark-candidate
    wheel_digest=0899cdc4c270d5fe817b256c099457551f6b273b65aaf5418da99ae5ff60052b
    apply_evaluator_patch benchmark-request 029ac12e32476d83b5a8555291b7c094be7df3262cd862396ddff1b453ec1821
  else
    wheel_version=1.4.0
    wheel_kind=--benchmark-current
    wheel_digest=b1a6b0f86a5c7f7873146327a215687969d46bbadc54ee46c84c615518262ea7
    apply_evaluator_patch benchmark-request 18b217f7e88289911617f27a6ff5ba5638a73336f12509fdcf3caef4f9ce135f
  fi
  case "$kind" in
    native-benchmark-101)
      apply_evaluator_patch benchmark-staging a997da90485a79696b83481e403359d4ad33cd40300986b499efc8c3cc70cbd6
      apply_evaluator_patch benchmark-recovery 44a766ab7cb7bcf38bc0769fc8f87fc6edf20997363ec0341d252edc93dca0b5
      apply_evaluator_patch benchmark-evidence 45923e37bf4dd71b0c1b3c38390dd6c32c8f2ea234f9634cb04fbb0f48232c75
      python_export=SKILL_NATIVE_BENCHMARK_RETAINED_PYTHON ;;
    native-benchmark-121)
      apply_evaluator_patch benchmark-staging e763a97c0ed3b48f014aa30f0e39181f89b0151324a739a738eecc4fec435c3e
      apply_evaluator_patch benchmark-recovery 3360099d6c936ba5e67fdb485fc53210db7c8477152099daf41e3c86fee78bb6
      apply_evaluator_patch benchmark-evidence c3003dc7f50d93b8a786c0c1e11b325e6e518b06d6a6e4a823472a198be788fa
      python_export=SKILL_NATIVE_BENCHMARK_PYTHON ;;
  esac
  "$python" -IB "$root/.github/evaluator-backends/build_wheel.py" "$tools/backend-wheel" "$wheel_kind"
  printf '%s  %s\n' "$wheel_digest" "$tools/backend-wheel/aeb_gh_fixture-$wheel_version-py3-none-any.whl" | sha256sum --check --strict
  uv pip install --python "$python" --no-deps --no-index --link-mode copy --require-hashes --only-binary :all: \
    --requirement "$tools/backend-wheel/requirements.txt"
  uv pip check --python "$python"
  PYTHONPATH="$root/.github/scripts" "$python" -B -c '
import sys
from aeb_gh_fixture.backend import require_runtime
import benchmark_native as native
import evaluator_profiles as profiles
require_runtime()
kind, version = sys.argv[1:]
if kind == "native-benchmark-121":
    native.validate_runtime()
elif kind == "native-benchmark-101":
    profiles.validate_install(native.native_profile(owner=native.RETAINED_NATIVE_PRODUCER))
else:
    profiles.validate_install(profiles.by_version(version))
' "$kind" "$release_version"
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
if [ "$release_version" = 1.2.1 ]; then
  apply_evaluator_patch scanner-contracts 6873c37c0ca482b2222e2774700b6982302e74fccfb805192bd54b0447e860a9
fi
if [ "$kind" = scanner-contracts ]; then
  PYTHONPATH="$root/.github/scripts" "$python" -B -c 'import static_evaluator; static_evaluator.validate_install(scanner_contracts=True)'
  printf 'SKILL_SCANNER_CONTRACT_PYTHON=%s\nSKILL_SCANNER_CONTRACT_TOOLS=%s\n' "$python" "$tools" >> "$GITHUB_ENV"
  exit 0
fi
uv pip list --python "$python" --format json > "$tools/dependencies/evaluator.json"
"$python" -B "$root/.github/scripts/static_quality_ci.py" versions --tools "$tools"

printf 'SKILL_QUALITY_PYTHON=%s\nSKILL_QUALITY_TOOLS=%s\nXDG_CACHE_HOME=%s\nXDG_STATE_HOME=%s\n' \
  "$python" "$tools" "$XDG_CACHE_HOME" "$XDG_STATE_HOME" >> "$GITHUB_ENV"
