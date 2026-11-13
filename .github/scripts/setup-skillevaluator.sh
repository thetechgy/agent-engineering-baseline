#!/usr/bin/env bash
# CI-only tools. Nothing is installed into an APM source or deployment tree.
set -euo pipefail
umask 077

kind=${1:?usage: setup-skillevaluator.sh quality|benchmark|reporting|candidate}
case "$kind" in quality|benchmark|reporting|candidate|candidate-current) ;; *) exit 2 ;; esac
: "${RUNNER_TEMP:?}" "${GITHUB_WORKSPACE:?}" "${GITHUB_ENV:?}" "${GITHUB_PATH:?}"
repository_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)
tool_root="$RUNNER_TEMP/skill-evaluation-tools"
case "$(realpath -m "$tool_root")/" in
  "$(realpath "$GITHUB_WORKSPACE")/"*|"$repository_root/"*) echo 'Tools must be outside the checkout.' >&2; exit 1 ;;
esac
mkdir -p "$tool_root/bin" "$tool_root/dependencies"
chmod 700 "$tool_root"
# The immutable return-contract workflow retains its original reviewed uv.
# Both supported compilers consume the same verified frozen Python catalog.
if [ "$kind" = candidate-current ] && [ "$(uv --version | awk '{print $2}')" = '0.13.7' ]; then
  :
else
test "$(uv --version | awk '{print $2}')" = '0.13.8'
fi
export UV_CACHE_DIR="$tool_root/uv-cache"
export UV_PYTHON_INSTALL_DIR="$tool_root/python"
export XDG_CACHE_HOME="$tool_root/cache"
export XDG_STATE_HOME="$tool_root/state"

# uv's managed-build catalog can change without changing a Python version.
# Preserve the reviewed 0.13.7 download identities for frozen evaluator recipes.
if [ "$kind" = candidate ] || [ "$kind" = candidate-current ]; then
  frozen_python_catalog="$tool_root/frozen-python-downloads.json"
  curl --fail --location --silent --show-error --proto '=https' --proto-redir '=https' \
    --output "$frozen_python_catalog" \
    https://raw.githubusercontent.com/astral-sh/uv/316c827e058c16b71d5c507a20729c2995a7bcce/crates/uv-python-managed/download-metadata.json
  printf '%s  %s\n' 81372e1cbff3dd87a786674ef00e01b3743638e3d8e58117d73e32a8e11eae05 "$frozen_python_catalog" | sha256sum --check --strict
  export UV_PYTHON_DOWNLOADS_JSON_URL="$frozen_python_catalog"
fi

# Current opt-in replacement. Historical recipes below retain their original bytes.
if [ "$kind" = candidate-current ]; then
  current_root="$RUNNER_TEMP/current-evaluator"
  export UV_PYTHON_INSTALL_DIR="$current_root/python"
  git init --quiet "$current_root"
  git -C "$current_root" fetch --quiet --depth=1 https://github.com/NVIDIA/SkillEvaluator.git 8149356e4476a1497fb334727f13f699c6fa6ba5
  git -C "$current_root" checkout --quiet --detach FETCH_HEAD
  test "$(git -C "$current_root" rev-parse HEAD)" = 8149356e4476a1497fb334727f13f699c6fa6ba5
  cp "$repository_root/.github/locks/evaluator-candidate.lock" "$current_root/uv.lock"
  printf '%s  %s\n' 4873fe654fa944e9806709ae8730a44936eca91d257645710c4524acc7964c5e "$current_root/uv.lock" | sha256sum --check --strict
  git -C "$current_root" apply --check "$repository_root/.github/patches/skillevaluator-v0.8.0-evidence.patch"
  git -C "$current_root" apply "$repository_root/.github/patches/skillevaluator-v0.8.0-evidence.patch"
  uv sync --project "$current_root" --python 3.14.10 --managed-python --frozen --no-dev --extra tier3
  "$current_root/.venv/bin/python" "$repository_root/.github/evaluator-backends/build_wheel.py" "$current_root/backend-wheel"
  uv pip install --python "$current_root/.venv/bin/python" --no-deps --no-index --link-mode copy --require-hashes --only-binary :all: \
    --requirement "$current_root/backend-wheel/requirements.txt"
  uv pip check --python "$current_root/.venv/bin/python"
  printf 'SKILL_CURRENT_PYTHON=%s/.venv/bin/python\nSKILL_CURRENT_SOURCE=%s\n' "$current_root" "$current_root" >> "$GITHUB_ENV"
  exit 0
fi

# Qualification owns a separate pristine source/lock and installed local wheel.
# Production and both historical/current review environments retain their pins.
if [ "$kind" = candidate ]; then
  candidate_revision=f878f99a9cd4a85dd04043feb43e5bd6a777f64b # v0.7.2
  candidate_root="$RUNNER_TEMP/candidate-evaluation-tools"
  export UV_PYTHON_INSTALL_DIR="$candidate_root/python"
  git init --quiet "$candidate_root/evaluator"
  git -C "$candidate_root/evaluator" fetch --quiet --depth=1 \
    https://github.com/NVIDIA/SkillEvaluator.git "$candidate_revision"
  git -C "$candidate_root/evaluator" checkout --quiet --detach FETCH_HEAD
  test "$(git -C "$candidate_root/evaluator" rev-parse HEAD)" = "$candidate_revision"
  uv sync --project "$candidate_root/evaluator" --python 3.13 --managed-python \
    --frozen --no-dev --extra tier3
  candidate_python="$candidate_root/evaluator/.venv/bin/python"
  "$candidate_python" "$repository_root/.github/evaluator-backends/build_wheel.py" "$candidate_root/wheel"
  "$candidate_python" "$repository_root/.github/evaluator-backends/build_wheel.py" "$candidate_root/wheel-repeat"
  cmp "$candidate_root/wheel/aeb_gh_fixture-1.0.0-py3-none-any.whl" \
    "$candidate_root/wheel-repeat/aeb_gh_fixture-1.0.0-py3-none-any.whl"
  uv pip install --python "$candidate_python" --no-deps --no-index --link-mode copy --require-hashes --only-binary :all: \
    --requirement "$candidate_root/wheel/requirements.txt"
  uv pip check --python "$candidate_python"
  git -C "$candidate_root/evaluator" diff --exit-code
  {
    printf 'SKILL_CANDIDATE_PYTHON=%s\n' "$candidate_python"
    printf 'SKILL_CANDIDATE_SOURCE=%s/evaluator\n' "$candidate_root"
  } >> "$GITHUB_ENV"
  exit 0
fi

evaluator_revision=ac0a04905100acdafc6c95829311a9739c340ff6 # v0.3.0
git init --quiet "$tool_root/evaluator"
git -C "$tool_root/evaluator" fetch --quiet --depth=1 \
  https://github.com/NVIDIA/SkillEvaluator.git "$evaluator_revision"
git -C "$tool_root/evaluator" checkout --quiet --detach FETCH_HEAD
test "$(git -C "$tool_root/evaluator" rev-parse HEAD)" = "$evaluator_revision"
if [ "$kind" = quality ]; then
  # Preserve pristine adapter bytes for credential-free before/after qualification.
  cp "$tool_root/evaluator/src/skillevaluator/validators/security.py" "$tool_root/security-original.py"
  compatibility_patch="$repository_root/.github/patches/skillevaluator-v0.3.0-skillspector-caveats.patch"
  printf '%s  %s\n' 09ab5d1440f355224935b9498ea3c2a68395d656997932ab525771287cb802bc "$compatibility_patch" | sha256sum --check --strict
  git -C "$tool_root/evaluator" apply --check "$compatibility_patch"
  git -C "$tool_root/evaluator" apply "$compatibility_patch"
fi
if [ "$kind" = benchmark ]; then
  patch="$repository_root/.github/patches/skillevaluator-v0.3.0-pin-codex.patch"
  git -C "$tool_root/evaluator" apply --check "$patch"
  git -C "$tool_root/evaluator" apply "$patch"
fi
uv sync --project "$tool_root/evaluator" --python 3.13 --managed-python \
  --frozen --no-dev --extra security --extra tier3
evaluator_bin="$tool_root/evaluator/.venv/bin"
"$evaluator_bin/python" -c 'import sys; assert sys.version_info[:2] == (3, 13)'
"$evaluator_bin/skillevaluator" --version
git -C "$tool_root/evaluator" diff --exit-code -- uv.lock pyproject.toml

# Current reviews have their own reviewed lock; historical validators and all
# evaluator/benchmark commands retain the original upstream environment.
git -C "$tool_root/evaluator" worktree add --quiet --detach "$tool_root/review" "$evaluator_revision"
review_patch="$repository_root/.github/patches/skillevaluator-v0.3.0-review-runtime.patch"
git -C "$tool_root/review" apply --check "$review_patch"
git -C "$tool_root/review" apply "$review_patch"
review_lock_sha256=029846ad359472e0f2bf2df96de430f5aca0fcf2c242949ceab8289013a532ec
printf '%s  %s\n' "$review_lock_sha256" "$tool_root/review/uv.lock" | sha256sum --check --strict
git -C "$tool_root/review" diff --exit-code -- pyproject.toml
uv sync --project "$tool_root/review" --python 3.13 --managed-python \
  --frozen --no-dev --extra security --extra tier3
review_bin="$tool_root/review/.venv/bin"
uv pip check --python "$review_bin/python"
printf '%s  %s\n' "$review_lock_sha256" "$tool_root/review/uv.lock" | sha256sum --check --strict
uv pip list --python "$review_bin/python" --format json > "$tool_root/dependencies/review.json"
"$review_bin/python" - <<'PYREVIEW' > "$tool_root/review-versions.json"
import importlib.metadata, json, sys
expected = {'openai': '2.54.0', 'pydantic': '2.14.3', 'pydantic-core': '2.50.4',
            'typing-inspection': '0.4.5', 'skillevaluator': '0.3.0', 'harbor': '0.13.2'}
actual = {name: importlib.metadata.version(name) for name in expected}
assert sys.version_info[:2] == (3, 13) and actual == expected
print(json.dumps(actual, indent=2))
PYREVIEW

# Frozen current-v3/v4 attachments keep their original review dependency set.
git -C "$tool_root/evaluator" worktree add --quiet --detach "$tool_root/review-previous" "$evaluator_revision"
git -C "$tool_root/review-previous" apply --check "$repository_root/.github/patches/skillevaluator-v0.3.0-review-runtime-v1.patch"
git -C "$tool_root/review-previous" apply "$repository_root/.github/patches/skillevaluator-v0.3.0-review-runtime-v1.patch"
previous_review_lock_sha256=99e40a0c414b500dba410fe1e6e687f48e4c10209397997732392ffd472520c4
printf '%s  %s\n' "$previous_review_lock_sha256" "$tool_root/review-previous/uv.lock" | sha256sum --check --strict
uv sync --project "$tool_root/review-previous" --python 3.13 --managed-python \
  --frozen --no-dev --extra security --extra tier3
uv pip check --python "$tool_root/review-previous/.venv/bin/python"
printf '%s  %s\n' "$previous_review_lock_sha256" "$tool_root/review-previous/uv.lock" | sha256sum --check --strict

if [ "$kind" = quality ]; then
  # Every Semgrep artifact must match a reviewed hash; nothing is resolved at run time.
  uv venv --quiet --python 3.13 --managed-python "$tool_root/semgrep"
  uv pip sync --quiet --python "$tool_root/semgrep/bin/python" --require-hashes --only-binary :all: \
    "$repository_root/.github/requirements/semgrep.txt"
  ln -s "$tool_root/semgrep/bin/semgrep" "$tool_root/bin/semgrep"
  skillspector_revision=54824463814a0be01360792523ec7245a69190fc # v2.13.4
  git init --quiet "$tool_root/skillspector"
  git -C "$tool_root/skillspector" fetch --quiet --depth=1 \
    https://github.com/NVIDIA/SkillSpector.git "$skillspector_revision"
  git -C "$tool_root/skillspector" checkout --quiet --detach FETCH_HEAD
  test "$(git -C "$tool_root/skillspector" rev-parse HEAD)" = "$skillspector_revision"
  # Scanner-owned compatible lock; evaluator and historical environments are untouched.
  skillspector_lock_sha256=3352c462434ed1d906069b710bfba8b352c255139a0c5718f4edb6ad4051be2b
  printf '%s  %s\n' "$skillspector_lock_sha256" "$repository_root/.github/locks/skillspector.lock" | sha256sum --check --strict
  cp "$repository_root/.github/locks/skillspector.lock" "$tool_root/skillspector/uv.lock"
  uv sync --project "$tool_root/skillspector" --python 3.13 --managed-python --frozen --no-dev
  uv pip check --python "$tool_root/skillspector/.venv/bin/python"
  uv pip check --python "$tool_root/semgrep/bin/python"
  printf '%s  %s\n' "$skillspector_lock_sha256" "$tool_root/skillspector/uv.lock" | sha256sum --check --strict
  git -C "$tool_root/skillspector" diff --exit-code -- pyproject.toml
  ln -s "$tool_root/skillspector/.venv/bin/skillspector" "$tool_root/bin/skillspector"
  curl --fail --location --silent --show-error --proto '=https' --proto-redir '=https' \
    --output "$tool_root/gitleaks.tar.gz" \
    https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_linux_x64.tar.gz
  # Official v8.30.1 release checksum; reviewed alongside the release asset.
  printf '%s  %s\n' 551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb \
    "$tool_root/gitleaks.tar.gz" | sha256sum --check --strict
  tar -xzf "$tool_root/gitleaks.tar.gz" -C "$tool_root/bin" gitleaks
  "$tool_root/bin/semgrep" --version
  "$tool_root/bin/skillspector" --version
  "$tool_root/bin/gitleaks" version
  "$evaluator_bin/bandit" --version
  "$evaluator_bin/pip-audit" --version
  uv pip list --python "$tool_root/semgrep/bin/python" --format json > "$tool_root/dependencies/semgrep.json"
  uv pip list --python "$tool_root/skillspector/.venv/bin/python" --format json > "$tool_root/dependencies/skillspector.json"
fi
uv pip list --python "$evaluator_bin/python" --format json > "$tool_root/dependencies/evaluator.json"

printf '%s\n' "$evaluator_bin" "$tool_root/bin" >> "$GITHUB_PATH"
{
  printf 'SKILL_EVALUATION_KIND=%s\n' "$kind"
  printf 'SKILL_EVALUATOR_PYTHON=%s/python\n' "$evaluator_bin"
  printf 'SKILL_LEGACY_REVIEW_PYTHON=%s/python\n' "$evaluator_bin"
  printf 'SKILL_PREVIOUS_REVIEW_PYTHON=%s/review-previous/.venv/bin/python\n' "$tool_root"
  printf 'SKILL_REVIEW_PYTHON=%s/python\n' "$review_bin"
  printf 'XDG_CACHE_HOME=%s\nXDG_STATE_HOME=%s\n' "$XDG_CACHE_HOME" "$XDG_STATE_HOME"
  printf 'SKILLEVALUATOR_OUTPUT_PROVENANCE_KEY_FILE=%s/provenance.key\n' "$tool_root"
} >> "$GITHUB_ENV"
"$evaluator_bin/python" - "$tool_root" "$kind" "${skillspector_revision:-}" "$repository_root" <<'PY' > "$tool_root/versions.json"
import hashlib, importlib.metadata, json, platform, subprocess, sys
from pathlib import Path
root = Path(sys.argv[1])
versions = {
    "python": platform.python_version(),
    "skillevaluator": importlib.metadata.version("skillevaluator"),
    "harbor": importlib.metadata.version("harbor"),
    "evaluator_revision": "ac0a04905100acdafc6c95829311a9739c340ff6",
}
if sys.argv[2] == "benchmark":
    versions["docker_compose"] = subprocess.check_output(
        ["docker", "compose", "version", "--short"], text=True).strip()
if sys.argv[2] == "quality":
    versions["scanners"] = {name: next(package["version"] for package in
        json.loads((root / "dependencies" / f"{name}.json").read_text()) if package["name"] == name)
        for name in ("semgrep", "skillspector")}
    versions["scanners"].update({name: importlib.metadata.version(name) for name in ("bandit", "pip-audit")})
    versions["scanners"]["gitleaks"] = subprocess.check_output([root / "bin/gitleaks", "version"], text=True).strip()
    versions["skillspector_revision"] = sys.argv[3]
    versions["scanner_runtime"] = {
        "versions": versions["scanners"], "skillspector_revision": sys.argv[3],
        "adapter_patch": "sha256:" + hashlib.sha256((Path(sys.argv[4]) / ".github/patches/skillevaluator-v0.3.0-skillspector-caveats.patch").read_bytes()).hexdigest(),
        "skillspector_lock": "sha256:" + hashlib.sha256((root / "skillspector/uv.lock").read_bytes()).hexdigest(),
        "semgrep_lock": "sha256:" + hashlib.sha256((Path(sys.argv[4]) / ".github/requirements/semgrep.txt").read_bytes()).hexdigest(),
    }
print(json.dumps(versions, indent=2))
PY
