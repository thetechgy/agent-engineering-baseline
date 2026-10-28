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
for label in candidate released; do
  uv pip freeze --python "$root/$label/.venv/bin/python" > "$root/evidence/$label-runtime.txt"
done
python3 - "$root/evidence/runtime-identities.json" <<'IDENTITIES'
import json,os,pathlib,platform,subprocess,sys
identity={"schema":"native-qualification-identities-v1","qualification":"not-production-qualified","policy":"native-submission-contract-v2","source":os.environ['GITHUB_SHA'],"run_id":os.environ['GITHUB_RUN_ID'],"run_attempt":os.environ['GITHUB_RUN_ATTEMPT'],"kernel":platform.release(),"python_host":platform.python_version(),"candidate_source":"d9fa4b4041b31f417f02ed145999ecf1f0c11fcd","released_source":"5320d9329c36ecc72bc94c4f58cc813d6b54224b","codex_source":"6aaac694803004a63c6f393d153c96d22521a6b9","codex_version":"0.164.0","codex_package_sha256":"3ec55053109608d5038f7e50750f7d25f768dfd740fef071aa710e2559b63aac","docker":json.loads(subprocess.check_output(['docker','version','--format','{{json .}}']))}
identity['images']= [subprocess.check_output(['docker','image','inspect',name,'--format','{{.Id}}']).decode().strip() for name in ['aeb-native-base:164','aeb-native-qualification:164']]
pathlib.Path(sys.argv[1]).write_text(json.dumps(identity,indent=2))
IDENTITIES
# From this point, only explicit local fixture provider configuration is available to probes.
env -i PATH="$PATH" HOME="$root/home" DOCKER_CONFIG="$DOCKER_CONFIG" PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1 "$root/candidate/.venv/bin/python" "$source_root/provider_gate.py" > "$root/evidence/provider-functions.json"
set +e
env -i PATH="$PATH" HOME="$root/home" DOCKER_CONFIG="$DOCKER_CONFIG" PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1 "$root/candidate/.venv/bin/python" "$source_root/producer_gate.py" --out "$root/evidence/producer"
producer_status=$?
if [ "$producer_status" = 0 ]; then
  env -i PATH="$PATH" HOME="$root/home" DOCKER_CONFIG="$DOCKER_CONFIG" PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1 "$root/candidate/.venv/bin/python" "$source_root/contract_gate.py" --out "$root/evidence/contract"
  contract_status=$?
else
  contract_status=125
fi
if [ "$producer_status" = 0 ]; then
  env -i PATH="$PATH" HOME="$root/home" DOCKER_CONFIG="$DOCKER_CONFIG" PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1 "$root/candidate/.venv/bin/python" "$source_root/cli_controls.py" "$root" "$GITHUB_WORKSPACE"
  cli_status=$?
else
  cli_status=125
fi
set -e
printf '{"producer_exit":%s,"cli_controls_exit":%s,"contract_exit":%s}\n' "$producer_status" "$cli_status" "$contract_status" > "$root/evidence/outcomes.json"
python3 - "$root/evidence" <<'LIMITS'
import pathlib,sys
root=pathlib.Path(sys.argv[1]);files=[p for p in root.rglob('*') if p.is_file()]
assert len(files)<1024 and sum(p.stat().st_size for p in files)<16*1024*1024
assert not any(p.is_symlink() for p in root.rglob('*'))
LIMITS
test "$producer_status" = 0 && test "$cli_status" = 0 && test "$contract_status" = 0
