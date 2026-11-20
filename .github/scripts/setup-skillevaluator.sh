#!/usr/bin/env bash
# CI-only tools. Nothing is installed into an APM source or deployment tree.
set -euo pipefail
umask 077

kind=${1:?usage: setup-skillevaluator.sh quality|quality-next|quality-candidate|benchmark|reporting|candidate-current|candidate-next|candidate-accounting}
case "$kind" in quality-next|quality-candidate|quality|benchmark|reporting|candidate-current|candidate-next|candidate-accounting) ;; *) exit 2 ;; esac
: "${RUNNER_TEMP:?}" "${GITHUB_WORKSPACE:?}" "${GITHUB_ENV:?}" "${GITHUB_PATH:?}"
repository_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)
tool_root="$RUNNER_TEMP/skill-evaluation-tools"
if [ "$kind" = quality-candidate ]; then tool_root="$RUNNER_TEMP/skill-static-candidate-tools"; fi
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
test "$(uv --version | awk '{print $2}')" = '0.13.9'
fi
export UV_CACHE_DIR="$tool_root/uv-cache"
export UV_PYTHON_INSTALL_DIR="$tool_root/python"
export XDG_CACHE_HOME="$tool_root/cache"
export XDG_STATE_HOME="$tool_root/state"

# uv's managed-build catalog can change without changing a Python version.
# Preserve the reviewed 0.13.7 download identities for the frozen 0.8.0 recipe.
if [ "$kind" = candidate-current ]; then
  frozen_python_catalog="$tool_root/frozen-python-downloads.json"
  curl --fail --location --silent --show-error --proto '=https' --proto-redir '=https' \
    --output "$frozen_python_catalog" \
    https://raw.githubusercontent.com/astral-sh/uv/316c827e058c16b71d5c507a20729c2995a7bcce/crates/uv-python-managed/download-metadata.json
  printf '%s  %s\n' 81372e1cbff3dd87a786674ef00e01b3743638e3d8e58117d73e32a8e11eae05 "$frozen_python_catalog" | sha256sum --check --strict
  export UV_PYTHON_DOWNLOADS_JSON_URL="$frozen_python_catalog"
fi

write_static_versions() {
  uv pip list --python "$1" --format json > "$tool_root/dependencies/evaluator.json"
  "$1" -B - "$repository_root" "$tool_root" "$2" <<'PYSTATIC' > "$tool_root/versions.json"
import json, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / '.github/scripts'))
import evaluator_profiles as profiles
import skill_evidence as evidence
import static_evaluator
root = Path(sys.argv[2])
if sys.argv[3] == 'candidate':
    runtime = evidence.SCANNER_RUNTIME_STATIC_CANDIDATE
    owner = static_evaluator.VERSIONS
else:
    runtime = evidence.SCANNER_RUNTIME_NEXT
    owner = profiles.candidate_versions(profiles.NEXT)
versions = dict(owner, scanners=runtime['versions'],
                skillspector_revision=runtime['skillspector_revision'], scanner_runtime=runtime)
for name in ('semgrep', 'skillspector', 'bandit', 'pip-audit'):
    owner = 'evaluator' if name in ('bandit', 'pip-audit') else name
    actual = next(p['version'] for p in json.loads((root / 'dependencies' / (owner + '.json')).read_text()) if p['name'] == name)
    assert actual == versions['scanners'][name], (name, actual)
assert subprocess.check_output([root / 'bin/gitleaks', 'version'], text=True).strip() == versions['scanners']['gitleaks']
assert evidence.digest_bytes((root / 'skillspector/uv.lock').read_bytes()) == versions['scanner_runtime']['skillspector_lock']
assert evidence.digest_bytes((Path(sys.argv[1]) / '.github/requirements/semgrep.txt').read_bytes()) == versions['scanner_runtime']['semgrep_lock']
evidence.validate_runtime_versions(versions)
print(json.dumps(versions, indent=2))
PYSTATIC
}

# Compare against the existing static installation with identical external scanners.
if [ "$kind" = quality-candidate ]; then
  : "${SKILL_QUALITY_PYTHON:?Install quality-next first}" "${SKILL_QUALITY_TOOLS:?Install quality-next first}"
  candidate_root="$tool_root/evaluator"
  mapfile -t pin < <("$SKILL_QUALITY_PYTHON" -B - "$repository_root" "$SKILL_QUALITY_TOOLS" <<'PYPIN'
import sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / '.github/scripts'))
import skill_evidence as evidence
import static_evaluator
baseline = evidence.read_json(Path(sys.argv[2]) / 'versions.json')
evidence.validate_runtime_versions(baseline)
evidence.require(baseline.get('scanner_runtime') == evidence.SCANNER_RUNTIME_NEXT,
                 'Install the current static baseline first')
print(static_evaluator.REVISION, static_evaluator.LOCK, static_evaluator.VERSIONS['python'], sep='\n')
PYPIN
  )
  test "${#pin[@]}" -eq 3
  git init --quiet "$candidate_root"
  git -C "$candidate_root" fetch --quiet --depth=1 https://github.com/NVIDIA/SkillEvaluator.git "${pin[0]}"
  git -C "$candidate_root" checkout --quiet --detach FETCH_HEAD
  test "$(git -C "$candidate_root" rev-parse HEAD)" = "${pin[0]}"
  printf '%s  %s\n' "${pin[1]}" "$candidate_root/uv.lock" | sha256sum --check --strict
  # The offline strict dataset command imports Tier 3 and its Harbor dependency.
  uv sync --project "$candidate_root" --python "${pin[2]}" --managed-python --frozen --no-dev --extra security --extra tier3
  uv pip check --python "$candidate_root/.venv/bin/python"
  ln -s "$SKILL_QUALITY_TOOLS/skillspector" "$tool_root/skillspector"
  for tool in gitleaks skillspector semgrep; do
    ln -s "$SKILL_QUALITY_TOOLS/bin/$tool" "$tool_root/bin/$tool"
  done
  cp "$SKILL_QUALITY_TOOLS/dependencies/"{skillspector,semgrep}.json "$tool_root/dependencies/"
  write_static_versions "$candidate_root/.venv/bin/python" candidate
  printf 'SKILL_STATIC_CANDIDATE_PYTHON=%s/.venv/bin/python\nSKILL_STATIC_CANDIDATE_TOOLS=%s\n' \
    "$candidate_root" "$tool_root" >> "$GITHUB_ENV"
  exit 0
fi

# Current opt-in replacement. Historical recipes below retain their original bytes.
if [ "$kind" = candidate-next ] || [ "$kind" = quality-next ] || [ "$kind" = candidate-accounting ]; then
  current_patch=skillevaluator-v0.9.0-evidence-v3.patch
  current_patch_sha=ca00768c1c2b054573743707473ed98964ed6bf910ad8bfac5accfd683860da4
  if [ "$kind" = candidate-accounting ]; then
    current_patch=skillevaluator-v0.9.0-accounting-v1.patch
    current_patch_sha=1018edc9d22bc1770625701f7611a62ffe41c38a08bdb720dcb0347610f6575a
  fi
  current_root="$RUNNER_TEMP/next-evaluator"
  if [ "$kind" = candidate-accounting ]; then current_root="$RUNNER_TEMP/accounting-evaluator"; fi
  export UV_PYTHON_INSTALL_DIR="$current_root/python"
  git init --quiet "$current_root"
  git -C "$current_root" fetch --quiet --depth=1 https://github.com/NVIDIA/SkillEvaluator.git b78d14618a694dec84bc9601468f8f711df5cab3
  git -C "$current_root" checkout --quiet --detach FETCH_HEAD
  test "$(git -C "$current_root" rev-parse HEAD)" = b78d14618a694dec84bc9601468f8f711df5cab3
  cp "$repository_root/.github/locks/evaluator-0.9.lock" "$current_root/uv.lock"
  printf '%s  %s\n' 05dd72bfd0bac5399ac19232ea847929e2b21df4a7ef2d2c65eefc4f72484dda "$current_root/uv.lock" | sha256sum --check --strict
  printf '%s  %s\n' "$current_patch_sha" "$repository_root/.github/patches/$current_patch" | sha256sum --check --strict
  git -C "$current_root" apply --check "$repository_root/.github/patches/$current_patch"
  git -C "$current_root" apply "$repository_root/.github/patches/$current_patch"
  extras=(--extra tier3)
  if [ "$kind" = quality-next ]; then extras+=(--extra security); fi
  uv sync --project "$current_root" --python 3.14.10 --managed-python --frozen --no-dev "${extras[@]}"
  "$current_root/.venv/bin/python" "$repository_root/.github/evaluator-backends/build_wheel.py" "$current_root/backend-wheel" --candidate-next
  printf '%s  %s\n' 070237e238326d49a63f348d405533d01bdc58c68295aea206095aee80ac5149 "$current_root/backend-wheel/aeb_gh_fixture-1.1.0-py3-none-any.whl" | sha256sum --check --strict
  uv pip install --python "$current_root/.venv/bin/python" --no-deps --no-index --link-mode copy --require-hashes --only-binary :all: \
    --requirement "$current_root/backend-wheel/requirements.txt"
  uv pip check --python "$current_root/.venv/bin/python"
  if [ "$kind" = candidate-accounting ]; then
    printf 'SKILL_ACCOUNTING_PYTHON=%s/.venv/bin/python\n' "$current_root" >> "$GITHUB_ENV"
    exit 0
  fi
  printf 'SKILL_NEXT_PYTHON=%s/.venv/bin/python\nSKILL_NEXT_SOURCE=%s\nSKILL_QUALIFICATION_PYTHON=%s/.venv/bin/python\n' "$current_root" "$current_root" "$current_root" >> "$GITHUB_ENV"
  if [ "$kind" = quality-next ]; then
    # No 0.3 evaluator or private review overlay is needed by static quality.
    # shellcheck source-path=SCRIPTDIR
    # shellcheck source=setup-skill-scanners.sh
    source "$repository_root/.github/scripts/setup-skill-scanners.sh"
    install_skill_scanners "$tool_root" "$current_root/.venv/bin" "$repository_root"
    write_static_versions "$current_root/.venv/bin/python" next
    printf 'SKILL_QUALITY_PYTHON=%s/.venv/bin/python\nSKILL_QUALITY_TOOLS=%s\n' "$current_root" "$tool_root" >> "$GITHUB_ENV"
    printf 'XDG_CACHE_HOME=%s\nXDG_STATE_HOME=%s\nSKILLEVALUATOR_OUTPUT_PROVENANCE_KEY_FILE=%s/static-quality-provenance.key\n' \
      "$XDG_CACHE_HOME" "$XDG_STATE_HOME" "$RUNNER_TEMP" >> "$GITHUB_ENV"
  fi
  exit 0
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
  printf 'SKILL_CURRENT_PYTHON=%s/.venv/bin/python\nSKILL_CURRENT_SOURCE=%s\nSKILL_QUALIFICATION_PYTHON=%s/.venv/bin/python\n' "$current_root" "$current_root" "$current_root" >> "$GITHUB_ENV"
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
  # Keep the upstream evaluator lock and interpreter available for offline replay.
  benchmark_root="$tool_root/benchmark"
  benchmark_lock_sha256=860d39d65694902b88abae1e8fc6cf85da67d2e861847d566bba0981d826b458
  git -C "$tool_root/evaluator" worktree add --quiet --detach "$benchmark_root" "$evaluator_revision"
  for patch in skillevaluator-v0.3.0-pin-codex.patch skillevaluator-v0.3.0-benchmark-lock.patch; do
    git -C "$benchmark_root" apply --check "$repository_root/.github/patches/$patch"
    git -C "$benchmark_root" apply "$repository_root/.github/patches/$patch"
  done
  printf '%s  %s\n' "$benchmark_lock_sha256" "$benchmark_root/uv.lock" | sha256sum --check --strict
  uv sync --project "$benchmark_root" --python 3.13 --managed-python \
    --frozen --no-dev --extra security --extra tier3
  uv pip check --python "$benchmark_root/.venv/bin/python"
  printf '%s  %s\n' "$benchmark_lock_sha256" "$benchmark_root/uv.lock" | sha256sum --check --strict
  git -C "$benchmark_root" diff --exit-code -- pyproject.toml
  "$benchmark_root/.venv/bin/python" -c 'from importlib.metadata import version; assert version("certifi") == "2026.10.23"'
fi
uv sync --project "$tool_root/evaluator" --python 3.13 --managed-python \
  --frozen --no-dev --extra security --extra tier3
legacy_evaluator_bin="$tool_root/evaluator/.venv/bin"
evaluator_bin="$legacy_evaluator_bin"
if [ "$kind" = benchmark ]; then evaluator_bin="$benchmark_root/.venv/bin"; fi
"$evaluator_bin/python" -c 'import sys; assert sys.version_info[:2] == (3, 13)'
"$evaluator_bin/skillevaluator" --version
git -C "$tool_root/evaluator" diff --exit-code -- uv.lock pyproject.toml

# Current and historical private review overlays keep their respective locks.
git -C "$tool_root/evaluator" worktree add --quiet --detach "$tool_root/review" "$evaluator_revision"
review_patch="$repository_root/.github/patches/skillevaluator-v0.3.0-review-runtime.patch"
git -C "$tool_root/review" apply --check "$review_patch"
git -C "$tool_root/review" apply "$review_patch"
review_lock_sha256=4df95f60d91da22824193c00fbfaa51acdc9f910a6a09c0b3856c5188eb25b6e
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
expected = {'certifi': '2026.10.23', 'openai': '2.54.0', 'pydantic': '2.14.3', 'pydantic-core': '2.50.4',
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
  # shellcheck source-path=SCRIPTDIR
  # shellcheck source=setup-skill-scanners.sh
  source "$repository_root/.github/scripts/setup-skill-scanners.sh"
  install_skill_scanners "$tool_root" "$evaluator_bin" "$repository_root"
fi
uv pip list --python "$evaluator_bin/python" --format json > "$tool_root/dependencies/evaluator.json"

printf '%s\n' "$evaluator_bin" "$tool_root/bin" >> "$GITHUB_PATH"
{
  printf 'SKILL_EVALUATION_KIND=%s\n' "$kind"
  printf 'SKILL_EVALUATOR_PYTHON=%s/python\n' "$evaluator_bin"
  printf 'SKILL_LEGACY_REVIEW_PYTHON=%s/python\n' "$legacy_evaluator_bin"
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
    versions["lock_sha256"] = hashlib.sha256((root / "benchmark/uv.lock").read_bytes()).hexdigest()
    versions["certifi"] = importlib.metadata.version("certifi")
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
