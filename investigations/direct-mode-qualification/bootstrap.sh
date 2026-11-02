#!/usr/bin/env bash
set -euo pipefail
umask 077
root="$RUNNER_TEMP/direct-qualification"
experiment="$GITHUB_WORKSPACE/investigations/direct-mode-qualification"
python3 "$experiment/test_gates.py"
mkdir -p "$root/evidence" "$root/codex/bin" "$root/home"
git clone -q https://github.com/NVIDIA/SkillEvaluator.git "$root/evaluator"
git -C "$root/evaluator" checkout -q d9fa4b4041b31f417f02ed145999ecf1f0c11fcd
python3 "$experiment/prepare_evaluator.py" "$root/evaluator" "$root/evidence"
uv sync --project "$root/evaluator" --python 3.13.15 --frozen --no-dev --extra tier3
uv pip install --python "$root/evaluator/.venv/bin/python" --no-deps "$experiment"
python="$root/evaluator/.venv/bin/python"
"$python" "$experiment/test_publication.py" "$root/evaluator" "$root/evidence"
curl -fsSL --proto '=https' --proto-redir '=https' https://github.com/openai/codex/releases/download/rust-v0.166.0/codex-x86_64-unknown-linux-musl.tar.gz -o "$root/codex.tar.gz"
printf '%s  %s\n' a0bf572d2f93f056c6712a6da348e96078dc84f3885fd7be67807ef389cb3978 "$root/codex.tar.gz" | sha256sum -c
tar -xzf "$root/codex.tar.gz" -C "$root/codex/bin"
mv "$root/codex/bin/codex-x86_64-unknown-linux-musl" "$root/codex/bin/codex"
chmod 0555 "$root/codex/bin/codex"
curl -fsSL --proto '=https' --proto-redir '=https' https://files.pythonhosted.org/packages/1e/5e/d4e9f1a599fb8e573b7b87160658329fbf28d19eac2718f51fc3def3aa5a/idna-3.18-py3-none-any.whl -o "$root/codex/idna-3.18-py3-none-any.whl"
printf '%s  %s\n' 7f952cbe720b688055e3f87de14f5c3e5fdaa8bc3928985c4077ca689de849a2 "$root/codex/idna-3.18-py3-none-any.whl" | sha256sum -c
git init -q "$root/codex-source"
git -C "$root/codex-source" fetch -q --depth=1 https://github.com/openai/codex.git 6ff1e1ca3b30fc8b914720681fcf5fe62e95f856
git -C "$root/codex-source" show FETCH_HEAD:codex-rs/models-manager/models.json > "$root/catalog.json"
"$python" - "$root" <<'CATALOG'
import hashlib,json,sys
from pathlib import Path
r=Path(sys.argv[1]);raw=(r/'catalog.json').read_bytes();c=json.loads(raw)
c['models']=[m for m in c['models'] if m['slug']=='gpt-5.6-sol']
assert len(c['models'])==1
c['models'][0]['tool_mode']='direct'
(r/'codex/direct-catalog.json').write_text(json.dumps(c))
(r/'evidence/identities.json').write_text(json.dumps({'model':'gpt-5.6-sol','catalog_original_sha256':hashlib.sha256(raw).hexdigest(),'catalog_direct_sha256':hashlib.sha256((r/'codex/direct-catalog.json').read_bytes()).hexdigest(),'codex_sha256':hashlib.sha256((r/'codex/bin/codex').read_bytes()).hexdigest(),'production_admission':False},indent=2))
CATALOG
"$python" "$experiment/stage.py" "$GITHUB_WORKSPACE" "$root"
timeout 300 docker build -t aeb-direct-gh:166 "$root/source/gh/evals/harbor/gh-010-partial/environment" > "$root/evidence/image-build.log" 2>&1 || { tail -100 "$root/evidence/image-build.log"; exit 1; }
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
export SKILL_EVAL_LLM_PROVIDER=openai-compatible SKILL_EVAL_LLM_MODEL=gpt-5.6-sol
export SKILL_EVAL_LLM_API_KEY=offline-sentinel-not-a-real-key SKILL_EVAL_LLM_BASE_URL=http://127.0.0.1:8991/v1
unset OPENAI_API_KEY ANTHROPIC_API_KEY
for profile in positive denied boundary; do
  export SKILLEVALUATOR_OUTPUT_PROVENANCE_KEY_FILE="$root/$profile.key"
  timeout --signal=INT --kill-after=30s 600 "$root/evaluator/.venv/bin/skillevaluator" tier3 evaluate "$root/source/gh" \
    --agents codex --agent-model codex=gpt-5.6-sol --env-mode aeb-direct --ek "profile=$profile" \
    --grading-mode custom_only --skill-workspace-mode group --n-attempts 1 --no-stop-on-pass \
    --n-concurrent 1 --max-agents 1 --harbor-keep-jobs --results-dir "$root/evidence/$profile" \
    > "$root/evidence/$profile.log" 2>&1 || { tail -60 "$root/evidence/$profile.log"; exit 1; }
done
"$python" "$experiment/check_results.py" "$root/evidence"

# This entry point has no live provider execution mode or credential input.
"$python" "$experiment/provider_preflight/test_relay.py"
timeout 120 docker build -f "$experiment/provider_preflight/Dockerfile" -t aeb-provider-preflight:166 "$experiment" > "$root/evidence/preflight-image-build.log" 2>&1 || { tail -60 "$root/evidence/preflight-image-build.log"; exit 1; }
timeout --signal=INT --kill-after=15s 240 "$python" "$experiment/provider_preflight/orchestrate.py" "$root/evidence/provider-preflight"
