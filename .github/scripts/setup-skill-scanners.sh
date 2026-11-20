#!/usr/bin/env bash
# Shared pinned scanners; the caller selects and verifies the evaluator owner.
# Sourced only by setup-skillevaluator.sh after its confinement and uv checks.
install_skill_scanners() {
  local tool_root=$1 evaluator_bin=$2 repository_root=$3
  # Every Semgrep artifact must match a reviewed hash; nothing is resolved at run time.
  uv venv --quiet --python 3.13 --managed-python "$tool_root/semgrep"
  uv pip sync --quiet --python "$tool_root/semgrep/bin/python" --require-hashes --only-binary :all: \
    "$repository_root/.github/requirements/semgrep.txt"
  ln -s "$tool_root/semgrep/bin/semgrep" "$tool_root/bin/semgrep"
  skillspector_revision=e2674da339b0bddc6e565d059c0577c6d9cd25da # v2.13.6
  git init --quiet "$tool_root/skillspector"
  git -C "$tool_root/skillspector" fetch --quiet --depth=1 \
    https://github.com/NVIDIA/SkillSpector.git "$skillspector_revision"
  git -C "$tool_root/skillspector" checkout --quiet --detach FETCH_HEAD
  test "$(git -C "$tool_root/skillspector" rev-parse HEAD)" = "$skillspector_revision"
  # Scanner-owned compatible lock; evaluator and historical environments are untouched.
  skillspector_lock_sha256=5ab9adb9707d66ee786cf934509d6c8d7258fb7ce12ebbc6a5b74fee35733fd1
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
}
