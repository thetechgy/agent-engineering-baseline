#!/usr/bin/env bash
# One pinned setup contract for authentication and its clean-runner qualification.
set -euo pipefail
campaign=${1:?registered campaign required}
repository_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)
setup=$(python3 -B - "$repository_root" "$campaign" <<'PYSETUP'
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(sys.argv[1]) / '.github/scripts'))
from evaluation_campaign_selection import selected_task, owning_evaluator
import evaluator_profiles as profiles
owner = owning_evaluator(selected_task(sys.argv[2]))
choices = {profiles.NATIVE_1720['id']: 'native-benchmark-121', profiles.NEXT['id']: 'candidate-next', profiles.CANDIDATE['id']: 'candidate-current', profiles.ACCOUNTING['id']: 'candidate-accounting'}
if owner['id'] not in choices: raise ValueError('Unsupported authentication owning runtime')
print(choices[owner['id']])
PYSETUP
)
if [ "$setup" = native-benchmark-121 ]; then
  bash "$repository_root/.github/scripts/setup-static-evaluator.sh" "$setup"
else
  bash "$repository_root/.github/scripts/setup-skillevaluator.sh" "$setup"
fi
case "$setup" in
  native-benchmark-121) authentication_python="$RUNNER_TEMP/skill-native-benchmark-121/evaluator/.venv/bin/python" ;;
  candidate-next) authentication_python="$RUNNER_TEMP/next-evaluator/.venv/bin/python" ;;
  candidate-current) authentication_python="$RUNNER_TEMP/current-evaluator/.venv/bin/python" ;;
  candidate-accounting) authentication_python="$RUNNER_TEMP/accounting-evaluator/.venv/bin/python" ;;
esac
"$authentication_python" -B - "$repository_root" "$campaign" <<'PYVERIFY'
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(sys.argv[1]) / '.github/scripts'))
from evaluation_campaign_selection import selected_task, owning_evaluator
import evaluator_profiles as profiles
owner = owning_evaluator(selected_task(sys.argv[2]))
profiles.runtime(profiles.candidate_versions(owner), owning=True)
PYVERIFY
printf 'SKILL_AUTHENTICATION_PYTHON=%s\n' "$authentication_python" >> "$GITHUB_ENV"
printf 'SKILL_CURRENT_PYTHON=%s\n' "$authentication_python" >> "$GITHUB_ENV"
