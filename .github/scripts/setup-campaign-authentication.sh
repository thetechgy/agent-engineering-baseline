#!/usr/bin/env bash
# One pinned setup contract for authentication and its clean-runner qualification.
set -euo pipefail
campaign=${1:?registered campaign required}
repository_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)
setup=$(python3 -B - "$repository_root" "$campaign" <<'PYSETUP'
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(sys.argv[1]) / '.github/scripts'))
from evaluation_campaign_selection import selected_task
from evaluation_runtime import ROOT, evaluator, read_profile
import evaluator_profiles as profiles
owner = evaluator(read_profile(ROOT / selected_task(sys.argv[2]).definition['runtime_profile']))
choices = {profiles.NEXT['id']: 'candidate-next', profiles.CANDIDATE['id']: 'candidate-current'}
if owner['id'] not in choices: raise ValueError('Unsupported authentication owning runtime')
print(choices[owner['id']])
PYSETUP
)
bash "$repository_root/.github/scripts/setup-skillevaluator.sh" "$setup"
case "$setup" in
  candidate-next) authentication_python="$RUNNER_TEMP/next-evaluator/.venv/bin/python" ;;
  candidate-current) authentication_python="$RUNNER_TEMP/current-evaluator/.venv/bin/python" ;;
esac
"$authentication_python" -B - "$repository_root" "$campaign" <<'PYVERIFY'
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(sys.argv[1]) / '.github/scripts'))
from evaluation_campaign_selection import selected_task
from evaluation_runtime import ROOT, evaluator, read_profile
import evaluator_profiles as profiles
owner = evaluator(read_profile(ROOT / selected_task(sys.argv[2]).definition['runtime_profile']))
profiles.runtime(profiles.candidate_versions(owner), owning=True)
PYVERIFY
printf 'SKILL_AUTHENTICATION_PYTHON=%s\n' "$authentication_python" >> "$GITHUB_ENV"
