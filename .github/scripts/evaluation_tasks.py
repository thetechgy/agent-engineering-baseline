"""Task-owned definitions, staging transformations and qualification expectations.

The existing graders remain the authority. No scheduling or report renderer lives here.
"""
import copy
import hashlib
import json
from pathlib import Path
import shlex
import shutil

from evaluation_campaign_core import require
import skill_reports as reports

ROOT = Path(__file__).resolve().parents[2]


def load(path):
    definition = reports.read_json(path)
    adapters = {'boolean-contract': BooleanContract, 'gh-fixture': GhFixture}
    require(definition.get('adapter') in adapters, 'Unsupported task adapter')
    for key in ('id', 'skill', 'source_case'):
        require(__import__('re').fullmatch('[a-z0-9-]+', definition[key]), 'Invalid task identity')
    require(definition['authorized_live_attempts'] == 0, 'Campaign paid execution disabled')
    require(path.resolve() == path and path.is_relative_to(ROOT / '.github/evals/campaigns'), 'Unregistered definition path')
    variants = definition['variants']
    require(type(variants) is list and len(variants) >= 2 and len({v['id'] for v in variants}) == len(variants)
            and all(__import__('re').fullmatch('[a-z0-9-]+', v['id']) and type(v['present']) is bool for v in variants), 'Invalid campaign variants')
    require(type(definition['attempt_limit']) is int and 0 < definition['attempt_limit'] <= 1000
            and type(definition['stop_estimate_usd']) in (int,float) and 0 < definition['stop_estimate_usd'] < float('inf'), 'Invalid campaign limits')
    for key in ('source', 'candidate', 'runtime_profile', 'protocol', 'retrospective'):
        if key in definition:
            target = ROOT / definition[key]
            require(target.resolve() == target and target.is_relative_to(ROOT), 'Unsafe campaign input path')
    return adapters[definition['adapter']](definition, path.relative_to(ROOT).as_posix())


class Task:
    probe_origin = 'tool'
    native_file_edit_probe = False
    protected_paths = ()
    retained_members = ('test-stdout.txt', 'test-stderr.txt', 'skill_evaluator_reward.json')
    def __init__(self, definition, member):
        self.definition, self.member = definition, member

    def source_inputs(self, workspace):
        import skill_evidence as e
        paths = list(self.source_files)
        for directory in self.source_directories:
            paths.extend(p.relative_to(workspace).as_posix() for p in reports.regular_tree(workspace / directory)
                         if p.name not in ('audit.json','validation.json'))
        return [{'member': 'task/' + path, 'digest': e.digest_bytes(e.read_bytes(workspace / path))} for path in sorted(set(paths))]

    def staging_options(self, bundle):
        return {}

    def operator_environment(self, root, tasks):
        return {}

    def cases(self, mode):
        if mode == 'replay':
            require(self.definition.get('retrospective') == '.github/evals/codex-retrospective/42695478931/manifest.json','Unregistered retained source')
            return {self.definition['source_case']:'retained'}
        if mode in ('live', 'experiment-probe'):
            require('protocol' in self.definition, 'Qualification cannot enable inference')
            return {self.definition['source_case']: None}
        controls = self.controls()
        if mode == 'probe':
            controls = {k: controls[k] for k in self.probe_controls}
        return {self.definition['source_case'] + '-' + key: key for key in controls}

    def entries(self, mode):
        entry = self.entry()
        return [{**copy.deepcopy(entry), 'id': case} for case in self.cases(mode)]

    def bundle(self, root, mode):
        bundle = self.base_bundle(root)
        native = bundle / 'evals/harbor'
        original = native / self.definition['source_case']
        for case, control in self.cases(mode).items():
            target = native / case
            if target != original:
                shutil.copytree(original, target)
            config = target / 'task.toml'
            config.write_text(config.read_text().replace('entry_id = ' + json.dumps(original.name), 'entry_id = ' + json.dumps(case)))
        for path in native.iterdir():
            if path.is_dir() and path.name not in self.cases(mode):
                shutil.rmtree(path)
        reports.write_json(bundle / 'evals/evals.json', {'skill_name': self.definition['skill'], 'evals': self.entries(mode)})
        (native / 'dataset.toml').write_text('[dataset]\nname = "nvidia/credential-free-campaign"\n\n' +
            ''.join('[[tasks]]\nname = ' + json.dumps('nvidia/' + case) + '\n\n' for case in self.cases(mode)))
        return bundle

    def validate_members(self, members, case, arm):
        """Compare task-owned grader, prompt and fixtures after common checksum checks."""
        control = case.removeprefix(self.definition['source_case'] + '-')
        require(control in self.controls() or case == self.definition['source_case'] and ('protocol' in self.definition or 'retrospective' in self.definition), 'Unknown task control')
        expected = self.expected_members(case, arm)
        require(all(members.get(k) == 'sha256:' + hashlib.sha256(v).hexdigest() for k,v in expected.items()),
                'Task grader/prompt/fixture drift')
        if 'retrospective' in self.definition:
            require(members.get('solution/candidate') == 'sha256:' + hashlib.sha256(self.payload('retained')).hexdigest(),'Retained solution drift')
        prefix = 'environment/skills/' + self.definition['skill'] + '/'
        source = ROOT / self.definition['source']
        skill = {prefix + p.relative_to(source).as_posix(): 'sha256:' + hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in reports.regular_tree(source) if p.relative_to(source).parts[0] != 'evals'} if arm == 'with_skill' else {}
        require({k:v for k,v in members.items() if k.startswith(prefix)} == skill, 'Task skill deployment drift')
        require(not any(k.startswith('environment/') and any(part in ('reference','mutants','solution','verifier')
                        for part in Path(k).parts[1:]) for k in members), 'Protected material in agent image')


class BooleanContract(Task):
    native_file_edit_probe = True
    source_directories = ('.github/evals/powershell-pester-6', '.github/evals/pester-ceiling/candidate')
    source_files = ('.github/scripts/pester_evaluations.py', '.github/scripts/codex_pilot_effectiveness.py', '.github/evals/pester-ceiling/candidate.json')
    output = 'Subject.Tests.ps1'
    family = 'pester-effectiveness-v6'
    probe_controls = ('identity', 'value-only')
    environment = 'codex_pilot_environment:PilotEnvironment'

    def candidate(self):
        return reports.read_json(ROOT / self.definition['candidate'])

    def controls(self):
        return {row['id']: row for row in self.candidate()['controls']}

    def payload(self, control):
        if control == 'retained':
            require('retrospective' in self.definition,'Unregistered retained task')
            from codex_pilot_replay import campaign_payload
            return campaign_payload()
        if control == 'unsupported':
            from codex_pilot_effectiveness import fixtures
            return fixtures()['pester-004-unsupported']['payload']
        return (ROOT / self.controls()[control]['file']).read_bytes()

    def fixture_control(self, scenario, row):
        if scenario == 'invalid': return 'broken-discovery'
        if scenario == 'unsupported-grading': return 'unsupported'
        return 'value-only' if row['position'] % 3 == 0 else 'identity'

    def validate_result(self, outcome, metrics):
        detections = outcome.get('variant_detections')
        require(outcome.get('code') == 'evaluated' and outcome.get('reference_pass') in (0,1)
                and type(detections) is list and len(detections) == 5
                and all(type(v) is int and v in (0,1) for v in detections)
                and outcome.get('mutants_detected') == sum(detections)
                and {'pester_reference_pass','pester_mutation_detection','pester_test_quality'} <= set(metrics), 'Missing usable task evidence')
        reference = outcome['reference_pass']
        require(metrics['pester_reference_pass'] == reference
                and metrics['pester_mutation_detection'] == (sum(detections)/5 if reference else 0)
                and metrics['pester_test_quality'] == int(reference == 1 and all(detections))
                and (outcome['classification'] == 'passed') == (metrics['pester_test_quality'] == 1), 'Contradictory task evidence')

    def entry(self):
        import pester_evaluations as pester
        return next(row for row in pester.dataset(ROOT) if row['id'] == self.definition['source_case'])

    def files(self):
        from codex_pilot_effectiveness import case_files
        files = case_files(ROOT, self.definition['source_case'])
        parent = (ROOT / self.definition['candidate']).parent
        files.update({'mutants/' + k + '.ps1': (parent / v).read_bytes() for k,v in self.candidate()['extra_mutants'].items()})
        return files

    def base_bundle(self, root):
        import pester_evaluations as pester
        return pester.stage(ROOT, root / 'bundle' / self.definition['skill'])

    def expected_members(self, case, arm):
        from codex_pilot_effectiveness import grader_bytes, runner_bytes, execution_profile_bytes
        base = ROOT / '.github/evals/powershell-pester-6/support'
        result = {'instruction.md': (self.entry()['prompt'] + '\n').encode(),
            'tests/verifier/grader.py': grader_bytes(), 'tests/Runner.ps1': runner_bytes(),
            'tests/test.sh': (base / 'test.sh').read_bytes(),
            'tests/entry.json': (json.dumps({'id': case, 'grading_mode': 'custom_only'}, indent=2) + '\n').encode(),
            'environment/input/EXECUTION-PROFILE.md': execution_profile_bytes()}
        result.update({'tests/case/' + k:v for k,v in self.files().items()})
        result.update({'environment/input/' + p.name:p.read_bytes() for p in (base / 'cases' / self.definition['source_case'] / 'input').iterdir()})
        return result

    def configure(self, task, control, mode, present):
        from codex_pilot_contract import runtime_installer_bytes
        from codex_pilot_iteration import PATH_LINK
        for context in ('environment', 'tests'):
            (task / context / 'build/install-runtime.py').write_bytes(runtime_installer_bytes())
        shutil.rmtree(task / 'tests/case')
        for member, raw in self.expected_members(task.name, 'with_skill' if present else 'without_skill').items():
            target = task / member; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw)
        (task / 'tests/docker-compose.yaml').write_text('services:\n  main:\n    network_mode: none\n')
        with (task / 'environment/Dockerfile').open('a') as stream:
            stream.write(PATH_LINK)
        if mode in ('oracle','replay'):
            solution = task / 'solution'; solution.mkdir()
            (solution / 'candidate').write_bytes(self.payload(control))
            (solution / 'solve.sh').write_text('#!/bin/sh\nset -eu\ntest ! -e /tests\ncp /solution/candidate /workspace/output/' + self.output + '\n')

    def probe_commands(self, control, payload, present=True):
        return ['printf %s ' + payload + ' | base64 -d > /workspace/output/' + self.output]

    def check(self, control, present, outcome, metrics):
        expected = self.controls()[control]
        require(outcome['classification'] == expected['outcome'], 'Unexpected Boolean outcome: ' + control)
        if expected['detections'] is not None:
            names = sorted(Path(k).stem for k in self.files() if k.startswith('mutants/'))
            require(dict(zip(names, outcome['variant_detections'])) == expected['detections'], 'Boolean defect discrimination drift')


class GhFixture(Task):
    probe_origin = 'operator'
    protected_paths = ('/opt/gh-eval/state/case.json', '/opt/aeb-gh/approved.json')
    retained_members = (*Task.retained_members, 'gh-initialization.jsonl')
    source_directories = ('.github/evals/gh', '.github/evaluator-backends/aeb_gh_fixture')
    source_files = ('.github/scripts/gh_evaluations.py', '.github/scripts/gh_candidate.py', '.github/scripts/gh_oracle_validation.py')
    output = 'result.json'
    family = 'gh-native-oracle-v1'
    probe_controls = ('good', 'unauthorized')
    environment = 'evaluation_codex:CampaignGhEnvironment'

    def staging_options(self, bundle):
        return {'workspace_mode': 'group', 'workspace_skill_paths': [bundle.parent / 'github-actions-hardening']}

    def operator_environment(self, root, tasks):
        from aeb_gh_fixture.manifest import write_manifest
        return {'AEB_GH_MANIFEST': str(write_manifest(root / 'operator', [p for group in tasks.values() for p in group.values()],
            staged_roots=[root / 'tasks', root / 'bundle']))}

    def controls(self):
        return dict.fromkeys(self.definition['controls'])

    def original(self):
        import gh_evaluations as gh
        return gh.dataset(ROOT, [self.definition['source_case']])[0]

    def entry(self):
        import gh_evaluations as gh
        entry = gh.enriched(self.original())
        entry['contract']['allowed_reads'] = sorted(entry['contract']['allowed_reads'])
        return entry

    def payload(self, control):
        return json.dumps(self.entry()['contract']['expected']).encode()

    def commands(self, control):
        commands = copy.deepcopy(self.original()['contract']['good_commands'])
        if control == 'wrong-repo':
            commands[0] = [v.replace('fixture-org/widget', 'fixture-fork/other').replace('owner=fixture-org', 'owner=fixture-fork') for v in commands[0]]
        if control == 'unauthorized':
            commands.append(['api', 'repos/fixture-org/widget/issues/12', '--method', 'POST'])
        return commands

    def entries(self, mode):
        rows = super().entries(mode)
        for row in rows:
            old = 'cases/' + self.definition['source_case'] + '.json'
            new = 'cases/' + row['id'] + '.json'
            row['files'] = [value.replace(old, new) for value in row['files']]
            row['contract']['input_hashes'][new] = row['contract']['input_hashes'].pop(old)
        return rows

    def probe_commands(self, control, payload, present=True):
        return ['cat /workspace/skills/gh/SKILL.md' if present else 'pwd', *[shlex.join(['gh', *argv]) for argv in self.commands(control)],
            "printf '%s\\n' " + shlex.quote(json.dumps(self.entry()['contract']['expected'])) + ' > output/result.json']

    def base_bundle(self, root):
        import gh_candidate
        return gh_candidate.stage(ROOT, root / 'bundle/gh', [self.definition['source_case']], fixture=True)

    def grader(self):
        import gh_candidate
        base = ROOT / '.github/evals/gh/evals'
        source = (base / 'files/fixture.py').read_text().rsplit('\nif __name__ ==', 1)[0].encode() + b'\n' + (base / 'grader.py').read_bytes()
        return gh_candidate.grader_source(source, fixture=True)

    def expected_members(self, case, arm):
        result = {'instruction.md': (self.entry()['prompt'] + '\n').encode(),
            'tests/grader.py': self.grader(), 'tests/test.sh': b'#!/bin/sh\nset -eu\nexec python3 -I /tests/grader.py\n',
            'environment/input/README.txt': b'Public gh fixture transport. Use gh to obtain observations.\n'}
        base = ROOT / '.github/evals/gh/evals/files'
        for member in self.original()['files']:
            relative = Path(member).relative_to('evals/files').as_posix()
            target = relative.replace('cases/' + self.definition['source_case'] + '.json', 'cases/' + case + '.json')
            result['environment/private/' + target] = (base / relative).read_bytes()
        return result

    def configure(self, task, control, mode, present):
        from gh_oracle_validation import SOLUTION
        old = task / 'environment/private/cases' / (self.definition['source_case'] + '.json')
        old.rename(old.with_name(task.name + '.json'))
        (task / 'environment/input').mkdir(exist_ok=True)
        (task / 'environment/input/README.txt').write_bytes(b'Public gh fixture transport. Use gh to obtain observations.\n')
        with (task / 'environment/Dockerfile').open('a') as stream:
            stream.write('COPY input/ /workspace/input/\nRUN chmod -R a-w /workspace/input\n')
        # Custom-only native tasks retain the existing fixture/grader and trusted initializer.
        for member, raw in self.expected_members(task.name, 'with_skill' if present else 'without_skill').items():
            if member.startswith('tests/'):
                (task / member).write_bytes(raw)
        if mode == 'oracle':
            solution = task / 'solution'; solution.mkdir()
            reports.write_json(solution / 'candidate', {'expected_skill': 'gh', 'commands': self.commands(control),
                'expected': self.entry()['contract']['expected'], 'control': control})
            (solution / 'solve.py').write_text(SOLUTION)
            (solution / 'solve.sh').write_text('#!/bin/sh\nset -eu\npython3 -I /solution/solve.py\nmkdir -p /logs/artifacts/submitted\ncp /workspace/output/result.json /logs/artifacts/submitted/result.json\n')

    def check(self, control, present, outcome, metrics):
        expected = 'unsupported' if control == 'unsupported' else 'unknown' if control == 'missing-trace' else 'passed' if control == 'good' and present else 'failed'
        require(outcome['classification'] == expected, 'Unexpected gh classification: ' + control)
        if expected in ('passed','failed'):
            require(metrics['gh_task'] == (0 if control == 'wrong-repo' else 1), 'gh task correctness lost')
            require(metrics['gh_authorization'] == (0 if control in ('unauthorized','wrong-repo') else 1), 'gh authorization meaning lost')
        else:
            require(not metrics, 'Unavailable gh evidence acquired metrics')
