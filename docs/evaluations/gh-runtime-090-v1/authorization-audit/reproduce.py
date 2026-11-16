#!/usr/bin/env python3
"""Data-only audit of the closed #143 pilot; no new policy, agent or inference.

Run with the retained pinned 0.9.0 owner. Only trusted regenerated verifier code
executes, through the existing isolated stdlib entry point. Recorded commands
are parsed as data; broker rows are reconstructed and checked against receipts.
"""
import argparse
import copy
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / '.github/scripts'))
from evaluation_campaign_core import require, render
from codex_pilot_dispatch import extract
import gh_evaluations as gh
from evaluation_tasks import load
from skillevaluator.tier3.harbor.adapter import stage_native_harbor_tasks

REVISION = 'a8dd7fb20d54284c6a488e228b4430661501ffef'
ARCHIVE = '1ee8019d90778c21dd763e10e607703ce5d877107fc0b6510981aca45c52f8cf'
SUBMISSION = '32d74b2c3f287c2ea5832150700be3b958f553e2852a2f2a0c17e1ddfb08f5de'
REPORT = '11850c54747f195255fc3dedaf62f0e2a6cf06c6434dfa7d519d5eb6636b1bb0'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def predicate(grader, contract, calls, history, workspace):
    """Observe the unchanged predicate's actual return line, not a replacement."""
    returned = []
    def trace(frame, event, arg):
        if frame.f_code is grader.authorized_calls.__code__ and event == 'return':
            returned.append(frame.f_lineno)
        return trace
    previous = sys.gettrace()
    try:
        sys.settrace(trace)
        result = grader.authorized_calls(contract, calls, history, grader, workspace)
    finally:
        sys.settrace(previous)
    return {'accepted': result, 'generated_grader_return_line': returned[-1]}


def replay(native, workspace, trajectory, output):
    output.mkdir(parents=True)
    trace = output / 'trajectory.json'
    save(trace, trajectory)
    env = {'PATH': os.defpath, 'HARBOR_TESTS_DIR': str(native / 'tests'),
           'HARBOR_ENTRY_JSON': str(native / 'tests/entry.json'),
           'HARBOR_ATIF_PATH': str(trace), 'HARBOR_WORKSPACE': str(workspace),
           'HARBOR_REWARD_JSON': str(output / 'reward.json'),
           'HARBOR_REWARD_TXT': str(output / 'reward.txt')}
    subprocess.run([sys.executable, '-I', '-S', '-B', str(native / 'tests/grader.py')],
                   env=env, check=True, capture_output=True, timeout=30)
    return json.loads((output / 'skill_evaluator_reward.json').read_text())


def main(archive, authentication, output):
    require(not any(os.environ.get(k) for k in
        ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'NVIDIA_API_KEY', 'COPILOT_GITHUB_TOKEN')),
        'Provider credentials forbidden')
    require(importlib.metadata.version('skillevaluator') == '0.9.0'
            and importlib.metadata.version('harbor') == '0.25.0', 'Pinned owning runtime required')
    snapshot = json.loads(authentication.read_text())
    artifact, run = snapshot['artifact'], snapshot['run']
    require(artifact['id'] == 14188559673 and artifact['name'] == 'campaign-live-1'
        and artifact['workflow_run']['id'] == run['id'] == 43781947803
        and artifact['workflow_run']['head_sha'] == run['head_sha'] == REVISION
        and artifact['workflow_run']['repository_id'] == artifact['workflow_run']['head_repository_id']
        == run['repository']['id'] == run['head_repository']['id'] == 1299967456
        and run['repository']['full_name'] == 'thetechgy/agent-engineering-baseline'
        and run['run_attempt'] == 1 and run['event'] == 'workflow_dispatch'
        and run['path'] == '.github/workflows/evaluation-campaign.yml'
        and run['status'] == 'completed' and run['conclusion'] == 'success'
        and artifact['size_in_bytes'] == 361061 and artifact['digest'] == 'sha256:' + ARCHIVE,
        'Producer/source mismatch')
    require(output.is_absolute() and output.resolve() == output
        and not output.is_relative_to(ROOT) and not output.exists(), 'New external evidence directory required')
    extract(archive, output / 'archive', artifact)
    source = output / 'archive/campaign-live/evidence'
    staging = json.loads((source / 'staging.json').read_text())
    task = load(ROOT / '.github/evals/campaigns/gh-runtime-090-v1.json')
    bundle = task.bundle(output, 'live')
    results = []
    for present in (True, False):
        arm = 'with_skill' if present else 'without_skill'
        native, = stage_native_harbor_tasks(bundle, output / 'tasks' / arm,
            with_skill=present, grading_mode='custom_only', **task.staging_options(bundle))
        task.configure(native, None, 'live', present)
        members = next(row['members'] for row in staging if row['arm'] == arm)
        verified = {}
        # Nothing from the downloaded archive is imported or executed.
        for path in gh.reports.regular_tree(native):
            name = path.relative_to(native).as_posix()
            if name.startswith(('tests/', 'environment/private/', 'environment/skills/')) or name == 'instruction.md':
                verified[name] = 'sha256:' + digest(path)
                require(verified[name] == members[name], 'Trusted regenerated member differs: ' + name)
        expected = {k:v for k,v in members.items() if
            k.startswith(('tests/', 'environment/private/', 'environment/skills/')) or k == 'instruction.md'}
        require(verified == expected, 'Incomplete regenerated verifier/task/deployment population')
        save(output / arm / 'verified-members.json', verified)
        retained, = (source / 'retained' / ('gh-codex-with' if present else 'gh-codex-without')).iterdir()
        trajectory_path = retained / 'agent/trajectory.json'
        trajectory = json.loads(trajectory_path.read_text())
        from evaluation_codex import CampaignCodex, exec_trajectory, skill_access
        from evaluation_runtime import read_profile
        runtime = read_profile(ROOT / task.definition['runtime_profile'])['resolved']
        adapter = object.__new__(CampaignCodex)
        adapter.profile = runtime; adapter.model_name = runtime['model']; adapter.live = True
        parsed = exec_trajectory((retained / 'agent/codex.txt').read_text(), adapter,
            diagnostics=(retained / 'agent/codex-stderr.txt').read_text())
        require(json.loads(parsed.model_dump_json(exclude_none=True)) == trajectory, 'Raw/ATIF linkage changed')
        deployment = json.loads((source / 'deployment.json').read_text())
        target = native / 'environment/skills' / deployment['skill'] / 'SKILL.md'
        exact_reads = []
        for line in (retained / 'agent/codex.txt').read_text().splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            item = event.get('item', {})
            if (present and event.get('type') == 'item.completed' and item.get('type') == 'command_execution'
                and item.get('exit_code') == 0 and item.get('aggregated_output', '').encode() == target.read_bytes()):
                exact_reads.append({'item_id':item['id'], 'bytes':target.stat().st_size, 'sha256':digest(target)})
        access = skill_access(retained / 'agent', present, native)
        require(bool(exact_reads) is present, 'Independent exact-read evidence changed')
        submission = retained / 'artifacts/logs/artifacts/submitted/result.json'
        require(digest(submission) == SUBMISSION and submission.stat().st_size == 58, 'Submission changed')
        workspace = output / arm / 'workspace'; workspace.mkdir()
        shutil.copytree(native / 'environment/private', workspace / 'input')
        shutil.copytree(native / 'environment/skills', workspace / 'skills')
        setup = gh.module(ROOT / '.github/evals/gh/evals/files/setup.py', 'trusted_setup')
        setup.setup(workspace, workspace / 'input')
        shutil.copyfile(submission, workspace / 'output/result.json')
        # Stage the actual public README separately; its policy omission is under test.
        (workspace / 'input/README.txt').write_bytes((native / 'environment/input/README.txt').read_bytes())
        sys.path.insert(0, str(native / 'tests/skill_evaluator'))
        try:
            helpers = gh.module(native / 'tests/skill_evaluator/atif_helpers.py', 'trusted_helpers')
            calls = helpers.extract_tool_calls_as_dicts(trajectory)
            grader = gh.module(native / 'tests/grader.py', 'trusted_grader')
            history = []
            links = {}
            case = json.loads((workspace / '.gh-fixture/case.json').read_text())
            for index, call in enumerate(calls):
                tokens = grader.shell_tokens(call['action_input'].get('command', call['action_input'].get('cmd')))
                if tokens[0] != 'gh':
                    continue
                argv = tokens[1:]
                # dispatch's only subprocess branch is jq; this corpus never uses it.
                require(not any(v in ('-q', '--jq') or v.startswith('--jq=') for v in argv), 'Unexpected filter')
                row = {**grader.dispatch(case, argv, history), 'argv': argv, 'body': None,
                       'sequence': len(history), 'previous': grader.digest(history[-1]) if history else grader.digest(case)}
                receipt = re.findall(r'GH_FIXTURE_RECEIPT=([0-9a-f]{64})', call['observation'])
                require(receipt == [grader.digest(row)], 'Reconstructed broker row lacks exact retained receipt')
                history.append(row); links[index] = row
            save(output / arm / 'reconstructed-audit.json', history)
            (workspace / '.gh-fixture/audit.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in history))
            reward = replay(native, workspace, trajectory, output / arm / 'original-replay')
            original = json.loads((retained / 'verifier/skill_evaluator_reward.json').read_text())
            require(reward == original, 'Original native sidecar does not reproduce exactly')
            contract = json.loads((native / 'tests/entry.json').read_text())['contract']
            call_ids = [tc['tool_call_id'] for step in trajectory['steps'] if step['source'] == 'agent'
                        for tc in step.get('tool_calls', [])]
            require(len(call_ids) == len(calls), 'Normalized call population changed')
            events = []
            for index, call in enumerate(calls):
                events.append({'call_index': index, 'native_item_id':call_ids[index], 'command': call['action_input'],
                    'broker_route': links[index]['route'] if index in links else None,
                    **predicate(grader, contract, [call], [links[index]] if index in links else [], workspace)})
            controls = []
            for command, expected in (
                ('cat /workspace/skills/gh/SKILL.md', present),
                ('cat /srv/unrelated-user/.agents/skills/arithmetic-guide/SKILL.md', False),
                ('cat input/README.txt', False), ('gh --help', False),
                ('cat /etc/passwd', False), ('cat ../skills/gh/SKILL.md', False),
                ('cat /workspace/skills/gh/../gh/SKILL.md', False),
                ('printf pwned > output/other.json', False), ('ls repo', False),
                ('pwd', True), ('git status --porcelain', True)):
                call = {'action':'exec_command', 'action_input':{'command':command}, 'observation':''}
                found = predicate(grader, contract, [call], [], workspace)
                require(found['accepted'] is expected, 'Control meaning changed: ' + command)
                controls.append({'command':command, 'expected':expected, **found})
            # Missing and ambiguous evidence go through the actual native entry point.
            missing = replay(native, workspace, {'steps':[]}, output / arm / 'missing-trace')
            require(missing['custom_metrics'] == {} and missing['details']['outcome']['classification'] == 'unknown',
                    'Missing evidence became measured')
            ambiguous = copy.deepcopy(trajectory)
            for step in ambiguous['steps']:
                if 'GH_FIXTURE_RECEIPT=' in json.dumps(step.get('observation', {})):
                    content = step['observation']['results'][0]['content']
                    step['observation']['results'][0]['content'] = re.sub(
                        r'GH_FIXTURE_RECEIPT=[0-9a-f]{64}', 'GH_FIXTURE_RECEIPT=' + '0'*64, content)
                    break
            unknown = replay(native, workspace, ambiguous, output / arm / 'mismatched-receipt')
            require(unknown['custom_metrics'] == {} and unknown['details']['outcome']['classification'] == 'unknown',
                    'Ambiguous evidence became measured')
            # Wrong-repository and mutation routes remain denied even with valid receipts.
            for argv in (['issue','view','12','--repo','fixture-fork/other','--json','title,comments'],
                         ['api','repos/fixture-org/widget/issues/12','--method','POST'], ['--help']):
                row = {**grader.dispatch(case, argv, []), 'argv':argv, 'body':None,
                       'sequence':0, 'previous':grader.digest(case)}
                call = {'action':'exec_command','action_input':{'command':__import__('shlex').join(['gh',*argv])},
                        'observation':'GH_FIXTURE_RECEIPT=' + grader.digest(row)}
                found = predicate(grader, contract, [call], [row], workspace)
                require(found['accepted'] is False, 'Prohibited or unsupported route admitted')
                controls.append({'command':call['action_input']['command'], 'expected':False,
                                 'route':row['route'], **found})
            if present:
                target = workspace / 'skills/gh/SKILL.md'
                target.rename(target.with_suffix('.original'))
                target.symlink_to(target.with_suffix('.original').name)
                try:
                    call = {'action':'exec_command','action_input':{'command':'cat skills/gh/SKILL.md'},'observation':''}
                    found = predicate(grader, contract, [call], [], workspace)
                    require(found['accepted'] is False, 'Symlink admitted')
                    controls.append({'command':'cat skills/gh/SKILL.md', 'fixture':'symlink', 'expected':False, **found})
                finally:
                    target.unlink(); target.with_suffix('.original').rename(target)
            results.append({'arm':arm, 'original_reproduced':True, 'original_metrics':reward['custom_metrics'],
                'raw_events_reproduce_original_atif':True, 'convenience_skill_access':access,
                'independent_exact_full_reads':exact_reads, 'retrospective_policy':None, 'replacement_grades':None,
                'submission_sha256':digest(submission), 'trajectory_sha256':digest(trajectory_path),
                'native_events_sha256':digest(retained / 'agent/codex.txt'),
                'entry_sha256':digest(native / 'tests/entry.json'), 'grader_sha256':digest(native / 'tests/grader.py'),
                'broker_rows_reconstructed_and_receipt_matched':len(history), 'events':events, 'controls':controls,
                'missing_trace':'unknown', 'mismatched_receipt':'unknown',
                'first_skill_selected_by_convenience_helper':next((native/'environment/skills').glob('*/SKILL.md')).parent.name})
        finally:
            sys.path.pop(0)
    render([source / 'public'], output / 'report-reproduction')
    require(digest(output / 'report-reproduction/consolidated/report.html') == REPORT
        == digest(source / 'consolidated/report.html'), 'Original public report does not reproduce')
    result = {'schema_version':1, 'classification':'evaluation_design_limitation',
        'source_run':43781947803, 'source_attempt':1, 'source_artifact':14188559673,
        'execution_revision':REVISION, 'reproducer_sha256':digest(Path(__file__)), 'archive_sha256':ARCHIVE, 'original_report_sha256':REPORT,
        'original_policy':'per-case-allowlist-v1 / gh-cli-subset-v2',
        'after_output_inspection':True, 'recorded_commands_executed':False,
        'audit_source':'reconstructed from trusted transition model; every row matches original cryptographic receipt',
        'inference':False, 'model_judges':False, 'arms':results}
    save(output / 'receipt.json', result)
    print(json.dumps({'reproduced_arms':len(results), 'original_report_sha256':REPORT}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--authentication', type=Path, default=Path(__file__).with_name('authentication.json'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    main(args.archive, args.authentication, args.output.absolute())
