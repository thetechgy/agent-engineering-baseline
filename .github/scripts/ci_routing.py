"""Credential-free CI impact selection and final-result admission.

Use the complete local Git graph, not the path-filter/PR-files API limits. Unknown
inputs select all maintained checks; malformed plans never produce a passing gate.
"""
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess

JOBS = {'contracts': 'ci-contracts', 'quality': 'skill-quality',
        'pester': 'pester-eval-feasibility', 'deadline': 'native-deadline',
        'admission': 'pester-admission'}
FLAGS = tuple(JOBS)
STATIC_QUALIFICATION = '.github/scripts/qualify_static_evaluator.py'
ROOT = Path(__file__).resolve().parents[2]
PESTER = {'contracts', 'pester', 'deadline', 'admission'}
GH = {'contracts', 'quality'}
WORKFLOWS = {
    'current-evaluator.yml': {'contracts'},
    'cli-observation-comparison.yml': {'contracts'},  # Explicit diagnostic mode.
    'native-deadline.yml': {'contracts', 'deadline'},
    'pester-admission-qualification.yml': {'contracts', 'admission'},
    'codex-pilot.yml': {'contracts', 'deadline'},  # Pilot preparation binds its workflow bytes.
    'codex-1691-qualification.yml': {'contracts'},  # Own PR trigger.
    # Full experiment preparation / migration remain operator-dispatched.
    'evaluation-campaign.yml': {'contracts'},
    'pester-return-qualification.yml': {'contracts'},
    'dependency-freshness.yml': {'contracts'},
    'update-baseline.yml': {'contracts'},
    'benchmark-skills.yml': {'contracts', 'quality'},
    'publish-skill-report.yml': {'contracts', 'quality'},
    'orchestrate-skill-evaluations.yml': {'contracts'},
}


def select(paths, *, complete=True):
    selected = set()
    if not complete or not paths:
        return dict.fromkeys(FLAGS, True)
    for path in paths:
        parts = PurePosixPath(path).parts
        if not path or path.startswith('/') or '..' in parts or any(ord(c) < 32 for c in path):
            return dict.fromkeys(FLAGS, True)
        # Skill Markdown and supporting files are executable evaluation inputs.
        if path.startswith('.apm/skills/'):
            selected.update(('contracts', 'quality'))
            skill = parts[2] if len(parts) > 2 else ''
            if skill == 'powershell-pester-6':
                selected.update(PESTER)
        elif path == '.github/tests/test_ci_routing.py':
            # The planner executes this entire stdlib suite on every PR.
            continue
        elif path == 'README.md':
            # The maintained external-action allowlist contract reads this file.
            selected.add('contracts')
        elif path.startswith(('docs/',)) or path in ('CONTRIBUTING.md', 'LICENSE',
                '.github/evals/EVALUATION-PLAN.md', '.github/evals/CI-ROUTING.md'):
            continue
        elif len(parts) == 3 and parts[:2] == ('.github', 'workflows') and parts[-1] in WORKFLOWS:
            selected.update(WORKFLOWS[parts[-1]])
        elif path.startswith('.github/evals/gh/') or path.startswith('.github/scripts/gh_'):
            selected.update(GH)
        elif path.startswith('.github/evals/pester-admission-v1/') or path in (
                '.github/evals/campaigns/pester-admission-controls-v2.json',
                '.github/evals/campaigns/pester-transfer-original-v1.json',
                '.github/evals/campaigns/pester-transfer-retrospective-v1.json'):
            selected.update(('contracts', 'admission'))
        elif path in ('.github/scripts/qualify_native_deadline.py', '.github/tests/test_native_deadline.py'):
            selected.update(('contracts', 'deadline'))
        elif path in ('.github/tests/test_ci_routing_profiles.py', '.github/tests/test_campaign_authentication.py',
                      '.github/evals/campaigns/codex-1691.json', '.github/evals/campaigns/gh-codex-1691.json',
                      '.github/evals/codex-execution-1691.json'):
            # The isolated 0.169.1 fixture workflow owns the three profile/definition paths.
            selected.add('contracts')
        elif path.startswith(('.github/evals/powershell-pester-6/', '.github/evals/pester-')):
            selected.update(PESTER)
        elif path.startswith('.github/evals/judge-calibration-090/') or path in (
                '.github/scripts/judge_transport_090.py', '.github/scripts/qualify_standard_judges.py',
                '.github/scripts/qualify_benchmark_evidence.py', '.github/tests/test_standard_judges.py'):
            # Qualification-only leaves; no production task/runtime or scoring consumer.
            selected.add('contracts')
        elif path.startswith('.github/scripts/qualify_scanner') or path in (STATIC_QUALIFICATION,
                '.github/scripts/skill_review.py', '.github/scripts/skill_report_reviews.py',
                '.github/scripts/skill_pages.py', '.github/scripts/skill_history.py',
                '.github/scripts/skill_orchestration.py'):
            selected.update(('contracts', 'quality'))
        elif path in ('.github/scripts/dependency_freshness.py', '.github/tests/test_dependency_freshness.py',
                      '.github/dependabot.yml', '.github/workflows/dependency-freshness.yml'):
            selected.add('contracts')
        else:
            # Deployment, locks, images, graders, fixtures, adapters, shared
            # reporting/policy and workflows have transitive consumers. Default
            # broad until a narrower dependency boundary has been demonstrated.
            selected.update(FLAGS)
    return {flag: flag in selected for flag in FLAGS}


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, stderr=subprocess.DEVNULL)


def changes(event, event_name):
    """Return both sides of renames as delete/add, with no API pagination cap."""
    if event_name != 'pull_request':
        return [], False, 'full-main-validation'
    try:
        base = event['pull_request']['base']['sha']
        head = event['pull_request']['head']['sha']
        if not all(isinstance(s, str) and re.fullmatch('[0-9a-f]{40}', s) for s in (base, head)):
            raise ValueError('invalid comparison')
        ancestor = git('merge-base', base, head).decode().strip()
        raw = git('diff', '--name-only', '--no-renames', '-z', ancestor, head, '--')
        if len(raw) > 16 * 1024 * 1024 or (raw and not raw.endswith(b'\0')):
            raise ValueError('incomplete comparison')
        paths = raw.decode('utf-8').split('\0')[:-1]
        return paths, True, 'complete-git-three-dot-diff'
    except (KeyError, TypeError, ValueError, UnicodeError, subprocess.CalledProcessError):
        return [], False, 'comparison-unavailable-select-all'


def gate(needs):
    plan = needs.get('plan', {})
    if plan.get('result') != 'success':
        raise ValueError('Selection/planning did not succeed')
    outputs = plan.get('outputs', {})
    if any(outputs.get(flag) not in ('true', 'false') for flag in FLAGS):
        raise ValueError('Incomplete or malformed selection outputs')
    expected = {'linux': True, 'windows-powershell': True}
    expected.update({job: outputs[flag] == 'true' for flag, job in JOBS.items()})
    failures = []
    rows = []
    for job, selected in expected.items():
        result = needs.get(job, {}).get('result', 'missing')
        required = 'success' if selected else 'skipped'
        rows.append(f'| {job} | {"selected" if selected else "not selected"} | {result} |')
        if result != required:
            failures.append(f'{job}: expected {required}, received {result}')
    summary = '| Check | Selection | Result |\n| --- | --- | --- |\n' + '\n'.join(rows) + '\n'
    if failures:
        raise ValueError(summary + '\n' + '\n'.join(failures))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('plan', 'gate'))
    args = parser.parse_args()
    if args.command == 'plan':
        try:
            event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
        except (KeyError, OSError, ValueError):
            event = {}
        event_name = os.environ.get('GITHUB_EVENT_NAME', '')
        paths, complete, reason = changes(event, event_name)
        selected = select(paths, complete=complete)
        selected['static_candidate'] = event_name == 'pull_request' and complete and STATIC_QUALIFICATION in paths
        if event_name == 'push':
            # Preserve main's production producer population and downstream chains.
            selected.update(dict.fromkeys(('deadline', 'admission'), False))
        # Only constant output names and literal booleans cross the job boundary.
        output = ''.join(f'{key}={str(value).lower()}\n' for key, value in selected.items())
        with open(os.environ['GITHUB_OUTPUT'], 'a') as stream:
            stream.write(output)
        summary = f'CI comparison: {reason}; {len(paths)} paths.\n\n' + output
    else:
        try:
            summary = gate(json.loads(os.environ['CI_NEEDS']))
        except (KeyError, TypeError, ValueError) as error:
            summary = str(error)
            if os.environ.get('GITHUB_STEP_SUMMARY'):
                with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as stream:
                    stream.write(summary + '\n')
            raise SystemExit(summary)
    print(summary)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as stream:
            stream.write(summary + '\n')


if __name__ == '__main__':
    main()
