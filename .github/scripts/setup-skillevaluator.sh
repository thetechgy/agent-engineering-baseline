#!/usr/bin/env bash
# CI-only tools. Nothing is installed into an APM source or deployment tree.
set -euo pipefail
umask 077

kind=${1:?usage: setup-skillevaluator.sh quality|benchmark}
case "$kind" in quality|benchmark) ;; *) exit 2 ;; esac
: "${RUNNER_TEMP:?}" "${GITHUB_WORKSPACE:?}" "${GITHUB_ENV:?}" "${GITHUB_PATH:?}"
tool_root="$RUNNER_TEMP/skill-evaluation-tools"
case "$(realpath -m "$tool_root")/" in
  "$(realpath "$GITHUB_WORKSPACE")/"*) echo 'Tools must be outside the checkout.' >&2; exit 1 ;;
esac
mkdir -p "$tool_root/bin" "$tool_root/dependencies"
chmod 700 "$tool_root"
test "$(uv --version | awk '{print $2}')" = '0.12.17'
export UV_CACHE_DIR="$tool_root/uv-cache"
export UV_PYTHON_INSTALL_DIR="$tool_root/python"
export XDG_CACHE_HOME="$tool_root/cache"
export XDG_STATE_HOME="$tool_root/state"

evaluator_revision=ac0a04905100acdafc6c95829311a9739c340ff6 # v0.3.0
git init --quiet "$tool_root/evaluator"
git -C "$tool_root/evaluator" fetch --quiet --depth=1 \
  https://github.com/NVIDIA/SkillEvaluator.git "$evaluator_revision"
git -C "$tool_root/evaluator" checkout --quiet --detach FETCH_HEAD
test "$(git -C "$tool_root/evaluator" rev-parse HEAD)" = "$evaluator_revision"
if [ "$kind" = benchmark ]; then
  patch="$GITHUB_WORKSPACE/.github/patches/skillevaluator-v0.3.0-pin-codex.patch"
  git -C "$tool_root/evaluator" apply --check "$patch"
  git -C "$tool_root/evaluator" apply "$patch"
fi
uv sync --project "$tool_root/evaluator" --python 3.13 --managed-python \
  --frozen --no-dev --extra security --extra tier3
evaluator_bin="$tool_root/evaluator/.venv/bin"
"$evaluator_bin/python" -c 'import sys; assert sys.version_info[:2] == (3, 13)'
"$evaluator_bin/skillevaluator" --version
git -C "$tool_root/evaluator" diff --exit-code -- uv.lock pyproject.toml

if [ "$kind" = quality ]; then
  # Every Semgrep artifact must match a reviewed hash; nothing is resolved at run time.
  uv venv --quiet --python 3.13 --managed-python "$tool_root/semgrep"
  uv pip sync --quiet --python "$tool_root/semgrep/bin/python" --require-hashes \
    "$GITHUB_WORKSPACE/.github/requirements/semgrep.txt"
  ln -s "$tool_root/semgrep/bin/semgrep" "$tool_root/bin/semgrep"
  skillspector_revision=69dcdfb74487d361ba4c811d088cfdea2ff3a9dc # v2.11.2
  git init --quiet "$tool_root/skillspector"
  git -C "$tool_root/skillspector" fetch --quiet --depth=1 \
    https://github.com/NVIDIA/SkillSpector.git "$skillspector_revision"
  git -C "$tool_root/skillspector" checkout --quiet --detach FETCH_HEAD
  test "$(git -C "$tool_root/skillspector" rev-parse HEAD)" = "$skillspector_revision"
  uv sync --project "$tool_root/skillspector" --python 3.13 --managed-python --frozen --no-dev
  git -C "$tool_root/skillspector" diff --exit-code -- uv.lock pyproject.toml
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
  printf 'SKILL_EVALUATOR_PYTHON=%s/python\n' "$evaluator_bin"
  printf 'XDG_CACHE_HOME=%s\nXDG_STATE_HOME=%s\n' "$XDG_CACHE_HOME" "$XDG_STATE_HOME"
  printf 'SKILLEVALUATOR_OUTPUT_PROVENANCE_KEY_FILE=%s/provenance.key\n' "$tool_root"
} >> "$GITHUB_ENV"
"$evaluator_bin/python" - "$tool_root" "$kind" <<'PY' > "$tool_root/versions.json"
import importlib.metadata, json, platform, subprocess, sys
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
    versions["skillspector_revision"] = "69dcdfb74487d361ba4c811d088cfdea2ff3a9dc"
print(json.dumps(versions, indent=2))
PY
