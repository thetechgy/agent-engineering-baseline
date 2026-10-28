#!/usr/bin/env bash
set -euo pipefail
umask 077
root="$RUNNER_TEMP/native-qualification"
source_root="$GITHUB_WORKSPACE/investigations/native-codex-qualification"
mkdir -p "$root/evidence" "$root/context" "$root/home"
curl --fail --location --silent --show-error --proto '=https' --proto-redir '=https' https://github.com/openai/codex/releases/download/rust-v0.164.0/codex-package-x86_64-unknown-linux-musl.tar.gz -o "$root/codex.tar.gz"
printf '%s  %s\n' 3ec55053109608d5038f7e50750f7d25f768dfd740fef071aa710e2559b63aac "$root/codex.tar.gz" | sha256sum -c
mkdir "$root/context/codex"
tar -xzf "$root/codex.tar.gz" -C "$root/context/codex"
cp "$source_root/"{Dockerfile,Base.Dockerfile} "$root/context/"
cp -r "$source_root/aeb_native_qualification/helpers" "$root/context/helpers"
docker build -q -t aeb-native-base:164 -f "$root/context/Base.Dockerfile" "$root/context"
docker build -q -t aeb-native-qualification:164 "$root/context"
for item in candidate:d9fa4b4041b31f417f02ed145999ecf1f0c11fcd released:5320d9329c36ecc72bc94c4f58cc813d6b54224b; do
  label=${item%%:*}
  revision=${item#*:}
  git init --quiet "$root/$label"
  git -C "$root/$label" fetch --quiet --depth=1 https://github.com/NVIDIA/SkillEvaluator.git "$revision"
  git -C "$root/$label" checkout --quiet --detach FETCH_HEAD
  test "$(git -C "$root/$label" rev-parse HEAD)" = "$revision"
  uv sync --project "$root/$label" --python 3.13.15 --frozen --no-dev --extra tier3
  git -C "$root/$label" diff --exit-code -- uv.lock pyproject.toml
  sha256sum "$root/$label/uv.lock" > "$root/evidence/$label-lock.sha256"
done
uv pip install --python "$root/candidate/.venv/bin/python" --no-deps "$source_root" "$GITHUB_WORKSPACE/investigations/skill-evaluation-architecture"
# From this point, only explicit local fixture provider configuration is available to probes.
env -i PATH="$PATH" HOME="$root/home" DOCKER_CONFIG="$DOCKER_CONFIG" PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1 "$root/candidate/.venv/bin/python" "$source_root/provider_gate.py" > "$root/evidence/provider-functions.json"
set +e
env -i PATH="$PATH" HOME="$root/home" DOCKER_CONFIG="$DOCKER_CONFIG" PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1 "$root/candidate/.venv/bin/python" "$source_root/producer_gate.py" --out "$root/evidence/producer"
producer_status=$?
set -e
printf '{"producer_exit":%s}\n' "$producer_status" > "$root/evidence/outcomes.json"
python3 - "$root/evidence" <<'LIMITS'
import pathlib,sys
root=pathlib.Path(sys.argv[1]);files=[p for p in root.rglob('*') if p.is_file()]
assert len(files)<1024 and sum(p.stat().st_size for p in files)<16*1024*1024
assert not any(p.is_symlink() for p in root.rglob('*'))
LIMITS
test "$producer_status" = 0
