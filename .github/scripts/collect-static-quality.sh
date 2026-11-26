#!/usr/bin/env bash
# Production static collection. Findings are advisory only after the separate
# catalog/projection gates validate complete native evidence and strict datasets.
set -euo pipefail
: "${SKILL_QUALITY_PYTHON:?}" "${SKILL_QUALITY_TOOLS:?}" "${RUNNER_TEMP:?}" "${GITHUB_WORKSPACE:?}"
case "$SKILL_QUALITY_PYTHON" in /*) ;; *) echo 'Absolute static interpreter required.' >&2; exit 1 ;; esac
repository_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)
"$SKILL_QUALITY_PYTHON" -B - "$repository_root" "$SKILL_QUALITY_TOOLS" <<'PYOWNER'
import sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / '.github/scripts'))
import skill_evidence as evidence
# Also supports the explicitly selected retained owner for rollback; neither
# missing metadata nor an interpreter/producer mismatch can fall back to PATH.
versions = evidence.read_json(Path(sys.argv[2]) / 'versions.json')
evidence.require(all(key in versions for key in ('python', 'skillevaluator', 'harbor',
    'evaluator_revision', 'scanners', 'scanner_runtime', 'skillspector_revision')), 'Missing static runtime provenance')
evidence.validate_runtime_versions(versions)
active_scanners = {
    '0.9.0': evidence.SCANNER_RUNTIME_NEXT,
    evidence.static_evaluator.VERSION: evidence.SCANNER_RUNTIME_STATIC_CANDIDATE,
}
evidence.require(versions['scanner_runtime'] == active_scanners.get(versions['skillevaluator']),
                 'Unsupported static scanner owner')
PYOWNER
evaluator_bin=$(dirname "$SKILL_QUALITY_PYTHON")
export PATH="$evaluator_bin:$SKILL_QUALITY_TOOLS/bin:$PATH"
export SKILLEVALUATOR_SKILLSPECTOR_PATH="$SKILL_QUALITY_TOOLS/bin/skillspector"
export SKILLEVALUATOR_GITLEAKS_PATH="$SKILL_QUALITY_TOOLS/bin/gitleaks"
export SKILLEVALUATOR_SEMGREP_PATH="$SKILL_QUALITY_TOOLS/bin/semgrep"
export SKILLEVALUATOR_BANDIT_PATH="$evaluator_bin/bandit"
export SKILLEVALUATOR_OUTPUT_PROVENANCE_KEY_FILE="$RUNNER_TEMP/static-quality-provenance.key"
report_root="$RUNNER_TEMP/skill-quality"
mkdir -p "$report_root/reports" "$report_root/datasets"
cp "$SKILL_QUALITY_TOOLS/versions.json" "$report_root/versions.json"
cp -r "$SKILL_QUALITY_TOOLS/dependencies" "$report_root/dependencies"
cd "$report_root"
status=0
"$SKILL_QUALITY_PYTHON" -B -c 'from skillevaluator.cli import cli; cli()' validate "$GITHUB_WORKSPACE/.apm/skills" \
  --external --tiers 1 --no-llm --no-dedup --continue-on-failure \
  --evaluated-source-repository "$GITHUB_REPOSITORY" \
  --evaluated-source-revision "$(git -C "$GITHUB_WORKSPACE" rev-parse HEAD)" \
  -r json,markdown,html -o "$report_root/reports" || status=$?
printf '%s\n' "$status" > "$report_root/catalog.exit"
for dataset in "$GITHUB_WORKSPACE"/.apm/skills/*/evals/evals.json; do
  if [ -L "$dataset" ]; then
    echo '::error::Linked evaluation dataset is not allowed.'
    exit 1
  fi
  [ -f "$dataset" ] || continue
  skill_dir="$(dirname "$(dirname "$dataset")")"
  skill="$(basename "$skill_dir")"
  status=0
  # Scanner overrides log initialization warnings to stdout. The strict JSON
  # command does not scan; remove overrides so its JSON remains machine-readable.
  env -u SKILLEVALUATOR_BANDIT_PATH -u SKILLEVALUATOR_SEMGREP_PATH -u SKILLEVALUATOR_SKILLSPECTOR_PATH \
    -u SKILLEVALUATOR_GITLEAKS_PATH \
    "$SKILL_QUALITY_PYTHON" -B -c 'from skillevaluator.cli import cli; cli()' tier3 validate "$skill_dir" --strict --json \
    > "$report_root/datasets/$skill.json" \
    2> "$report_root/datasets/$skill.stderr" || status=$?
  printf '%s\n' "$status" > "$report_root/datasets/$skill.exit"
done
