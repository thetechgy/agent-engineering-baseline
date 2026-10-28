#!/usr/bin/env bash
set -euo pipefail
umask 077
root="$RUNNER_TEMP/architecture-poc"
mkdir -p "$root/context" "$root/evidence"
curl --fail --location --silent --show-error --proto '=https' --proto-redir '=https' https://github.com/openai/codex/releases/download/rust-v0.164.0/codex-package-x86_64-unknown-linux-musl.tar.gz -o "$root/codex.tar.gz"
printf '%s  %s\n' 3ec55053109608d5038f7e50750f7d25f768dfd740fef071aa710e2559b63aac "$root/codex.tar.gz" | sha256sum -c
mkdir "$root/context/codex"
tar -xzf "$root/codex.tar.gz" -C "$root/context/codex"
cp investigations/skill-evaluation-architecture/{Dockerfile,native_probe.py,broker.py} "$root/context/"
docker build -q -t architecture-poc:164 "$root/context"
git clone --quiet https://github.com/NVIDIA/SkillEvaluator.git "$root/evaluator"
git -C "$root/evaluator" checkout --quiet d9fa4b4041b31f417f02ed145999ecf1f0c11fcd
uv sync --project "$root/evaluator" --python 3.13.15 --frozen --no-dev --extra tier3
git -C "$root/evaluator" diff --exit-code -- uv.lock pyproject.toml
"$root/evaluator/.venv/bin/python" investigations/skill-evaluation-architecture/harbor_gate.py "$root"
