#!/usr/bin/env bash
set -euo pipefail
umask 077
root="$RUNNER_TEMP/direct-qualification"
experiment="$GITHUB_WORKSPACE/investigations/direct-mode-qualification"
mkdir -p "$root/evidence" "$root/codex/bin" "$root/home"
git clone -q https://github.com/NVIDIA/SkillEvaluator.git "$root/evaluator"
git -C "$root/evaluator" checkout -q d9fa4b4041b31f417f02ed145999ecf1f0c11fcd
uv sync --project "$root/evaluator" --python 3.13.15 --frozen --no-dev --extra tier3
uv pip install --python "$root/evaluator/.venv/bin/python" --no-deps "$experiment"
python="$root/evaluator/.venv/bin/python"
curl -fsSL --proto '=https' --proto-redir '=https' https://github.com/openai/codex/releases/download/rust-v0.166.0/codex-x86_64-unknown-linux-musl.tar.gz -o "$root/codex.tar.gz"
printf '%s  %s\n' a0bf572d2f93f056c6712a6da348e96078dc84f3885fd7be67807ef389cb3978 "$root/codex.tar.gz" | sha256sum -c
tar -xzf "$root/codex.tar.gz" -C "$root/codex/bin"
mv "$root/codex/bin/codex-x86_64-unknown-linux-musl" "$root/codex/bin/codex"
chmod 0555 "$root/codex/bin/codex"
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
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
export SKILL_EVAL_LLM_PROVIDER=openai-compatible SKILL_EVAL_LLM_MODEL=gpt-5.6-sol
export SKILL_EVAL_LLM_API_KEY=offline-sentinel-not-a-real-key SKILL_EVAL_LLM_BASE_URL=http://127.0.0.1:8991/v1
unset OPENAI_API_KEY ANTHROPIC_API_KEY
for profile in positive denied; do
  export SKILLEVALUATOR_OUTPUT_PROVENANCE_KEY_FILE="$root/$profile.key"
  timeout --signal=INT --kill-after=30s 600 "$root/evaluator/.venv/bin/skillevaluator" tier3 evaluate "$root/source/gh" \
    --agents codex --agent-model codex=gpt-5.6-sol --env-mode aeb-direct --ek "profile=$profile" \
    --grading-mode custom_only --skill-workspace-mode group --n-attempts 1 --no-stop-on-pass \
    --n-concurrent 1 --max-agents 1 --harbor-keep-jobs --results-dir "$root/evidence/$profile" \
    > "$root/evidence/$profile.log" 2>&1 || { tail -60 "$root/evidence/$profile.log"; exit 1; }
done
"$python" "$experiment/check_results.py" "$root/evidence"
