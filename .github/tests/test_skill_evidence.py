"""Offline inventory, pinned native ingestion, and public-boundary regressions."""

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import skill_evidence as evidence

REPO = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / 'fixtures/skill_evidence'


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(evidence.encoded(data))


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def native(self):
        target = self.root / 'native'
        shutil.copytree(FIXTURES / 'podman-native', target)
        # Mutated cases test ordinary native artifacts, independently of the reviewed extract.
        (target / 'extract-manifest.json').unlink()
        return target

    def data(self):
        return evidence.normalize_behavioral(FIXTURES / 'podman-native', 'podman')

    def repo(self):
        root = self.root / 'repo'
        root.mkdir()
        self.local(root, 'alpha')
        return root

    def local(self, root, name, dataset=False):
        path = root / '.apm/skills' / name
        path.mkdir(parents=True, exist_ok=True)
        (path / 'SKILL.md').write_text(f'---\nname: {name}\ndescription: Synthetic fixture\n---\n')
        if dataset:
            self.dataset(path, name)
        return path

    def dataset(self, root, name):
        write(root / 'evals/evals.json', {'skill_name': name, 'evals': [
            {'id': 1, 'prompt': 'Synthetic fixture', 'expected_output': 'Synthetic outcome'}]})

    def imported(self, root, name='beta'):
        deployed = root / '.agents/skills' / name
        deployed.mkdir(parents=True)
        (deployed / 'SKILL.md').write_text(f'---\nname: {name}\ndescription: Synthetic imported fixture\n---\n')
        member = (deployed / 'SKILL.md').relative_to(root).as_posix()
        sha = evidence.digest_bytes((deployed / 'SKILL.md').read_bytes())
        owner = 'example/skills/skills/' + name
        lock = {'dependencies': [{'name': name, 'repo_url': 'example/skills', 'virtual_path': 'skills/' + name,
                 'resolved_commit': 'a' * 40, 'deployed_file_hashes': {member: sha}}],
                'deployments': [{'value': member, 'target': 'codex', 'active_owner': owner, 'owners': [owner], 'content_hash': sha}]}
        (root / 'apm.lock.yaml').write_text(yaml.safe_dump(lock))
        self.dataset(root / '.github/evals' / name, name)
        return lock

    def mutate(self, root, suffix, fn):
        path = next(p for p in root.rglob('*.json') if p.as_posix().endswith(suffix))
        data = evidence.read_json(path); fn(data); write(path, data)
        return path

    def test_current_discovery(self):
        inv = evidence.inventory()
        self.assertEqual(sum(r['source']['owner'] == 'local' for r in inv['skills']), 6)
        self.assertEqual(sum(r['suite'] is not None for r in inv['skills']), 2)
        gh = next(r for r in inv['skills'] if r['source']['skill_id'] == 'gh')
        self.assertEqual(gh['source']['repository'], 'cli/cli')
        self.assertEqual(len(gh['suite']['case_ids']), 24)
        self.assertEqual(gh['measurement']['status'], 'unavailable')

    def test_future_source_and_suite(self):
        root = self.repo(); self.local(root, 'future', True)
        rows = evidence.inventory(root)['skills']
        self.assertEqual([r['source']['skill_id'] for r in rows], ['alpha', 'future'])
        self.assertEqual(rows[0]['behavioral_status'], 'not_configured')
        self.assertEqual(rows[1]['suite']['case_ids'], ['1'])

    def test_imported_owner_and_local_replacement(self):
        root = self.repo(); self.imported(root)
        before = next(r for r in evidence.inventory(root)['skills'] if r['source']['skill_id'] == 'beta')
        historical = evidence.evidence('beta', 'behavioral', ['1'], before['source'])
        frozen = evidence.encoded(historical)
        self.local(root, 'beta')
        with self.assertRaises(ValueError):
            evidence.inventory(root)
        (root / 'apm.lock.yaml').write_text(yaml.safe_dump({'dependencies': [], 'deployments': []}))
        after = next(r for r in evidence.inventory(root)['skills'] if r['source']['skill_id'] == 'beta')
        self.assertEqual(before['source']['skill_id'], after['source']['skill_id'])
        self.assertEqual(after['source']['owner'], 'local')
        self.assertEqual(after['suite']['owner'], 'overlay')
        evidence.project(historical)
        self.assertEqual(frozen, evidence.encoded(historical))
        self.assertEqual(historical['source']['owner'], 'upstream')

    def test_conflicting_datasets(self):
        root = self.repo(); path = self.local(root, 'alpha', True)
        self.dataset(root / '.github/evals/alpha', 'alpha')
        with self.assertRaises(ValueError):
            evidence.inventory(root)
        shutil.rmtree(root / '.github')
        write(path / 'evals/evals.jsonl', {})
        with self.assertRaises(ValueError):
            evidence.inventory(root)

    def test_ambiguous_owner_and_deployment_drift(self):
        for mutation in ('owner', 'hash', 'deployment', 'revision'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                root = Path(temp); self.local(root, 'alpha'); lock = self.imported(root)
                if mutation == 'owner':
                    lock['dependencies'].append(copy.deepcopy(lock['dependencies'][0]))
                elif mutation == 'hash':
                    next((root / '.agents').rglob('SKILL.md')).write_text('Drift')
                elif mutation == 'deployment':
                    lock['deployments'][0]['owners'].append('other/owner')
                else:
                    lock['dependencies'][0]['resolved_commit'] = 'bad'
                (root / 'apm.lock.yaml').write_text(yaml.safe_dump(lock))
                with self.assertRaises(ValueError):
                    evidence.inventory(root)

    def test_unsafe_source_trees(self):
        for kind in ('link', 'hardlink', 'fifo'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp:
                root = Path(temp); path = self.local(root, 'alpha')
                target = path / 'unsafe'
                if kind == 'link': target.symlink_to(path / 'SKILL.md')
                elif kind == 'hardlink': os.link(path / 'SKILL.md', target)
                else: os.mkfifo(target)
                with self.assertRaises(ValueError):
                    evidence.inventory(root)

    def test_malformed_metadata_and_case_collisions(self):
        root = self.repo(); path = root / '.apm/skills/alpha'
        (path / 'SKILL.md').write_text('---\nname: beta\ndescription: Fixture\n---\n')
        with self.assertRaises(ValueError): evidence.inventory(root)
        self.local(root, 'alpha', True)
        for invalid in ([1, '1'], ['Case', 'case'], ['../escape'], [True]):
            with self.subTest(invalid=invalid):
                write(path / 'evals/evals.json', {'skill_name': 'alpha', 'evals': [
                    {'id': i, 'prompt': 'Synthetic', 'expected_output': 'Synthetic'} for i in invalid]})
                with self.assertRaises(ValueError): evidence.inventory(root)

    def test_escaping_fixture_reference(self):
        root = self.repo(); path = root / '.apm/skills/alpha'
        self.dataset(path, 'alpha')
        self.mutate(root, '/evals/evals.json', lambda d: d['evals'][0].update(files=['../outside']))
        with self.assertRaises(ValueError): evidence.inventory(root)

    def test_exact_podman_observations(self):
        data = self.data()
        self.assertEqual([r['value'] for r in data['metrics']], [0.1207, 0.7730, 0.9600, 0.6937])
        self.assertEqual(len(data['observations']), 20)
        self.assertEqual({o['case_id'] for o in data['observations'] if o['arm'] == 'with_skill'},
                         {o['case_id'] for o in data['observations'] if o['arm'] == 'without_skill'})
        self.assertEqual([a['rubric']['passed_cases'] for a in data['arms']], [10, 8])
        self.assertEqual([o['score'] for o in data['observations'] if o['case_id'] == '2'], [0.6896, 0.7242])
        self.assertEqual(data['dataset']['staged_digest'], 'sha256:cecc0bcea480a3c197e1b4c527009958ada3be67eb0205325f6c16123f9355fe')
        self.assertEqual(data['policy']['patch_digest'], 'sha256:d48af476c19f06d94297e2e143f4643c74580abbcd631a599fe7b296244f3962')
        self.assertNotEqual(data['policy']['patch_digest'], evidence.digest_bytes((REPO / evidence.reports.PATCH).read_bytes()))
        # A shallow CI checkout need not contain the historical Git objects.
        if data['source']['content']['digest'] is None:
            self.assertEqual(data['source']['content']['provenance'], 'unknown')
            self.assertIn('source_unavailable', data['availability']['reasons'])
        else:
            self.assertEqual(data['source']['content']['provenance'], 'reconstructed_from_declared_revision')
            self.assertEqual(data['availability']['status'], 'complete')
        evidence.validate_public(evidence.project(data))

    def test_no_invented_gh_model_run(self):
        data = evidence.read_json(FIXTURES / 'gh-no-model.json'); evidence.validate_evidence(data)
        self.assertEqual(len(data['dataset']['case_ids']), 24)
        self.assertIsNone(data['run_id']); self.assertEqual(data['observations'], [])
        self.assertEqual(data['availability'], {'status': 'unavailable', 'reasons': ['results_not_supplied'], 'provenance': 'unknown'})
        self.assertEqual(data['arms'][0]['condition']['competing_skills'][0]['revision'], '143a3d976b3c1603cc8932984d5e1f28501cb5fc')
        for arm in data['arms']:
            self.assertIsNone(arm['coverage']['recorded_attempts'])
        data['arms'][0]['coverage']['recorded_attempts'] = 24
        with self.assertRaises(ValueError): evidence.project(data)

    def test_stable_identity_and_order(self):
        first = self.data(); self.assertEqual(evidence.encoded(first), evidence.encoded(self.data()))
        root = self.native()
        summaries = list(root.rglob('summary.json'))
        for p in summaries:
            data = evidence.read_json(p); data['pass_at_k']['cases'] = dict(reversed(list(data['pass_at_k']['cases'].items())))
            write(p, data)
        second = evidence.normalize_behavioral(root, 'podman')
        self.assertEqual([o['id'] for o in first['observations']], [o['id'] for o in second['observations']])
        self.assertEqual([o['native_id'] for o in first['observations']], [o['native_id'] for o in second['observations']])

    def test_policy_and_condition_identities_are_independent(self):
        data = evidence.read_json(FIXTURES / 'gh-no-model.json')
        target = data['source']['content']['digest']; dataset = data['dataset']['authored_digest']
        original = data['arms'][0]['condition']
        for key, value in [('instruction_digest', 'sha256:' + 'a'*64), ('build_digest', 'sha256:' + 'b'*64), ('fixture_digest', 'sha256:' + 'c'*64)]:
            cond = copy.deepcopy(original); cond[key] = value
            cond['id'] = evidence.identity({k:v for k,v in cond.items() if k != 'id'}); evidence.validate_condition(cond)
            self.assertNotEqual(cond['id'], original['id'])
        cond = copy.deepcopy(original); cond['execution']['base_image_mode'] = 'disabled'
        cond['id'] = evidence.identity({k:v for k,v in cond.items() if k != 'id'}); self.assertNotEqual(cond['id'], original['id'])
        cond = copy.deepcopy(original); cond['competing_skills'][0]['revision'] = 'c'*40
        cond['id'] = evidence.identity({k:v for k,v in cond.items() if k != 'id'}); self.assertNotEqual(cond['id'], original['id'])
        policy = copy.deepcopy(data['policy']); policy['fields']['competing_revision'] = 'c'*40
        policy['id'] = evidence.identity({k:policy[k] for k in ('fields','patch_digest','metric_set','judge','attempts')})
        evidence.validate_policy(policy); self.assertNotEqual(policy['id'], data['policy']['id'])
        self.assertEqual(target, data['source']['content']['digest']); self.assertEqual(dataset, data['dataset']['authored_digest'])

    def test_expired_references_cannot_promote(self):
        data = self.data(); data['references'][0]['availability'] = 'expired'
        with self.assertRaises(ValueError): evidence.project(data)
        data['availability'].update(status='incomplete', reasons=['reference_expired'])
        evidence.project(data)
        with self.assertRaises(ValueError): evidence.verify_reference(self.root, data['references'][0])

    def test_retained_member_verification(self):
        root = self.native(); path = root / 'versions.json'
        ref = evidence.reference(root, path, 'fixture', ('skillevaluator',))
        self.assertEqual(evidence.verify_reference(root, ref), '0.3.0')
        ref['locator'] = ['missing']; ref['id'] = evidence.identity({k:ref[k] for k in ('artifact_id','member','locator','digest')})
        with self.assertRaises(ValueError): evidence.verify_reference(root, ref)
        path.write_text('{}')
        with self.assertRaises(ValueError): evidence.verify_reference(root, ref)

    def test_exact_source_and_staging_boundary(self):
        root = self.repo(); path = self.local(root, 'alpha', True)
        (path / 'references').mkdir(); (path / 'references/a.md').write_text('Synthetic source')
        src = evidence.source('alpha', 'local', contents=evidence.skill_content(path))
        evidence.verify_source_snapshot(path, src)
        self.assertNotIn('evals/evals.json', [r['member'] for r in src['content']['manifest']])
        (path / 'references/a.md').write_text('Changed')
        with self.assertRaises(ValueError): evidence.verify_source_snapshot(path, src)
        self.assertEqual(evidence.historical_content(REPO, 'f'*40, '.apm/skills/podman')['provenance'], 'unknown')

    def test_missing_details_stay_incomplete(self):
        root = self.native(); p = next(root.rglob('*/trials/*/result.json')); p.unlink()
        data = evidence.normalize_behavioral(root, 'podman')
        self.assertEqual(data['availability']['status'], 'incomplete')
        self.assertIn('case_details_missing', data['availability']['reasons'])
        data['availability'] = {'status':'complete', 'reasons':[], 'provenance':'runtime_recorded'}
        with self.assertRaises(ValueError): evidence.project(data)

    def test_missing_summary_never_invents_zero_trials(self):
        root = self.native(); next(root.rglob('summary.json')).unlink()
        data = evidence.normalize_behavioral(root, 'podman')
        self.assertIn('metadata_missing', data['availability']['reasons'])
        self.assertTrue(any(arm['coverage']['recorded_attempts'] is None for arm in data['arms']))
        self.assertEqual(len(data['observations']), 20)
        evidence.project(data)

    def test_duplicate_trials_rejected(self):
        root = self.native(); path = next(root.rglob('*/trials/*/result.json'))
        shutil.copytree(path.parent, path.parent.with_name('duplicate'))
        with self.assertRaises(ValueError): evidence.normalize_behavioral(root, 'podman')

    def test_unscored_native_trial_keeps_identity(self):
        root = self.native(); run = next((root/'results/podman').iterdir())
        path = next((run/'codex/with-skill/trials').glob('*/result.json'))
        record = evidence.read_json(path); trial = record['trial_name']
        reward = evidence.read_json(path.parent/'reward.json'); case = reward['entry_id']
        record['verifier_result'] = None; record['exception_info'] = {'diagnostic': 'discarded'}
        write(path, record); (path.parent/'reward.json').unlink()
        summary_path = run/'codex/with-skill/summary.json'; summary = evidence.read_json(summary_path)
        prior = summary['pass_at_k']['cases'][case]['attempts'][0]
        prior.update(score=None, passed=None)
        summary['scored_attempts'] = 9; summary['execution_status'] = 'incomplete'
        summary['pass_at_k']['passed_cases'] -= 1
        write(summary_path, summary)
        result_path = run/'result.json'; result = evidence.read_json(result_path)
        result.update(report_status='incomplete', execution_status='incomplete')
        result['agents']['codex']['conditions']['with_skill'].update(scored_attempts=9, execution_status='incomplete')
        write(result_path, result)
        data = evidence.normalize_behavioral(root, 'podman')
        obs = next(o for o in data['observations'] if o['native_trial'] == trial)
        self.assertIsNone(obs['score']); self.assertEqual(obs['native_id'], record['id'])
        self.assertEqual(data['arms'][0]['coverage']['unscored_attempts'], 1)
        self.assertEqual(data['availability']['status'], 'incomplete')
        evidence.project(data)

    def test_confirmation_native_attempts(self):
        root = self.native(); run = next((root/'results/podman').iterdir())
        config_path = run/'run_config.json'; config = evidence.read_json(config_path)
        config['harbor']['n_attempts'] = 3; write(config_path, config)
        result_path = run/'result.json'; result = evidence.read_json(result_path)
        result['run_config'] = config
        for arm in ('with_skill', 'without_skill'):
            result['agents']['codex']['conditions'][arm].update(expected_attempts=30, scored_attempts=30)
            base = run/'codex'/arm.replace('_','-')
            summary_path = base/'summary.json'; summary = evidence.read_json(summary_path)
            summary.update(expected_attempts=30, scored_attempts=30, num_trials=30)
            summary['pass_at_k']['k'] = 3
            for case, row in summary['pass_at_k']['cases'].items():
                original = row['attempts'][0]; original_trial = base/'trials'/original['trial']
                for ordinal in (2,3):
                    new_trial = original['trial'] + '-attempt' + str(ordinal)
                    target = base/'trials'/new_trial; shutil.copytree(original_trial, target)
                    trial_result = evidence.read_json(target/'result.json')
                    trial_result.update(id=trial_result['id']+'-'+str(ordinal), trial_name=new_trial)
                    write(target/'result.json', trial_result)
                    reward = evidence.read_json(target/'reward.json'); reward['trial_id'] = new_trial
                    write(target/'reward.json', reward)
                    row['attempts'].append({**original, 'attempt':ordinal, 'trial':new_trial})
            write(summary_path, summary)
        write(result_path, result)
        attempts = evidence.read_json(run/'attempt_policy.json'); attempts['max_attempts'] = 3
        write(run/'attempt_policy.json', attempts)
        prov = evidence.read_json(root/'provenance.json'); prov['mode'] = 'confirmation'; write(root/'provenance.json', prov)
        data = evidence.normalize_behavioral(root, 'podman')
        self.assertEqual(len(data['observations']), 60)
        self.assertEqual({o['attempt'] for o in data['observations']}, {1,2,3})
        self.assertEqual(data['policy']['attempts']['mode'], 'confirmation')
        evidence.project(data)

    def test_contradictory_recovery_rejected(self):
        root = self.native(); write(root / 'provenance.json', {'schema_version':1,'status':'incomplete','diagnostic_only':True})
        with self.assertRaises(ValueError): evidence.normalize_behavioral(root, 'podman')
        self.mutate(root, '/podman/' + next((root/'results/podman').iterdir()).name + '/result.json', lambda d: d.update(report_status='incomplete', diagnostic_only=True))
        data = evidence.normalize_behavioral(root, 'podman')
        self.assertEqual(data['availability']['status'], 'incomplete')

    def test_missing_historical_metadata(self):
        root = self.native(); (root/'provenance.json').unlink(); (root/'versions.json').unlink()
        data = evidence.normalize_behavioral(root, 'podman')
        self.assertEqual(len(data['observations']), 20)
        self.assertIn('metadata_missing', data['availability']['reasons'])
        self.assertIsNone(data['policy']['fields']['evaluator_revision'])

    def test_failed_gate_preserved(self):
        data = self.data(); obs = data['observations'][0]
        obs['deterministic_gate'] = 0
        obs['deterministic_scores'] = {k:0 if k in ('authorization','gate') else 1 for k in evidence.GATE_FIELDS}
        self.assertEqual(evidence.project(data)['observations'][0]['score'], obs['score'])
        self.assertEqual(evidence.project(data)['observations'][0]['deterministic_gate'], 0)

    def test_static_native_contract_and_diagnostic_exclusion(self):
        data = evidence.normalize_static(FIXTURES/'static-synthetic', 'podman')
        self.assertEqual(data['availability']['status'], 'incomplete')
        self.assertEqual(data['availability']['provenance'], 'synthetic')
        self.assertEqual(data['scans'][0]['severity_counts']['high'], 1)
        self.assertEqual(data['findings'][0]['member'], 'SKILL.md')
        report = evidence.encoded(evidence.project(data)).decode()
        self.assertNotIn('Synthetic diagnostic', report)
        self.assertEqual(data['metrics'], [])
        data['availability'].update(status='complete', reasons=[])
        with self.assertRaises(ValueError): evidence.project(data)

    def test_unknown_keys_rejected_at_every_object(self):
        # Mutate every nested object, including records within arrays.
        base = self.data()
        def paths(value, prefix=()):
            if type(value) is dict:
                yield prefix
                for key, child in value.items(): yield from paths(child, prefix+(key,))
            elif type(value) is list:
                for index, child in enumerate(value): yield from paths(child, prefix+(index,))
        for path in list(paths(base)):
            with self.subTest(path=path):
                data = copy.deepcopy(base); value = data
                for key in path: value = value[key]
                value['injected_prompt'] = 'private content'
                with self.assertRaises(ValueError): evidence.project(data)
        public = evidence.project(base)
        for path in list(paths(public)):
            data = copy.deepcopy(public); value = data
            for key in path: value = value[key]
            value['html'] = '<script>'
            with self.assertRaises(ValueError): evidence.validate_public(data)
        for base in (evidence.normalize_static(FIXTURES/'static-synthetic', 'podman'),
                     evidence.read_json(FIXTURES/'gh-no-model.json')):
            for path in list(paths(base)):
                data = copy.deepcopy(base); value = data
                for key in path: value = value[key]
                value['commentary'] = 'not public'
                with self.assertRaises(ValueError): evidence.project(data)

    def test_actual_public_serialized_limit(self):
        data = evidence.read_json(FIXTURES/'gh-no-model.json')
        prototype = self.data()['references'][0]
        for index in range(2500):
            ref = copy.deepcopy(prototype); ref['member'] = 'members/' + str(index) + '.json'
            ref['id'] = evidence.identity({k:ref[k] for k in ('artifact_id','member','locator','digest')})
            data['references'].append(ref)
        evidence.validate_evidence(data)
        self.assertGreater(len(evidence.encoded(data)), evidence.PUBLIC_LIMIT)
        with self.assertRaises(ValueError): evidence.project(data)

    def test_ambiguous_yaml_metadata(self):
        root = self.repo()
        (root/'apm.lock.yaml').write_text('dependencies: []\ndependencies: []\ndeployments: []\n')
        with self.assertRaises(ValueError): evidence.inventory(root)
        (root/'apm.lock.yaml').unlink()
        (root/'.apm/skills/alpha/SKILL.md').write_text('---\nname: alpha\nname: beta\ndescription: Fixture\n---\n')
        with self.assertRaises(ValueError): evidence.inventory(root)

    def test_extract_manifest_tamper_and_missing_git_objects(self):
        root = self.root/'extract'; shutil.copytree(FIXTURES/'podman-native', root)
        self.mutate(root, '/versions.json', lambda d:d.update(python='3.13.99'))
        with self.assertRaises(ValueError): evidence.normalize_behavioral(root, 'podman')
        root = self.native()
        data = evidence.normalize_behavioral(root, 'podman', workspace=self.root)
        self.assertIsNone(data['source']['content']['digest'])
        self.assertIn('source_unavailable', data['availability']['reasons'])
        self.assertEqual(len(data['observations']), 20)
        data['availability'].update(status='complete', reasons=[])
        with self.assertRaises(ValueError): evidence.project(data)

    def test_native_prose_cannot_enter_projection(self):
        root = self.native()
        self.mutate(root, '/result.json', lambda d:d.update(transcript='DO-NOT-PUBLISH', metadata={'prompt':'DO-NOT-PUBLISH'}))
        report = evidence.encoded(evidence.project(evidence.normalize_behavioral(root, 'podman')))
        self.assertNotIn(b'DO-NOT-PUBLISH', report)
        with self.assertRaises(ValueError): evidence.project(evidence.read_json(next(root.rglob('result.json'))))

    def test_numeric_and_denominator_failures(self):
        for invalid in (True, float('nan'), float('inf'), 1.1):
            data = self.data(); data['metrics'][1]['value'] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(ValueError): evidence.project(data)
        data = self.data(); data['arms'][0]['coverage']['expected_attempts'] = 9
        with self.assertRaises(ValueError): evidence.project(data)
        data = self.data(); data['arms'][0]['rubric']['passed_cases'] = 11
        with self.assertRaises(ValueError): evidence.project(data)

    def test_json_limits_duplicate_keys_and_depth(self):
        path = self.root/'input.json'
        for value in ('{"a":1,"a":2}', '{"x":NaN}', '['*34+'0'+']'*34):
            path.write_text(value)
            with self.assertRaises(ValueError): evidence.read_json(path)
        path.write_bytes(b' '* (evidence.JSON_LIMIT+1))
        with self.assertRaises(ValueError): evidence.read_json(path)
        data = self.data(); data['observations'] *= 501
        with self.assertRaises(ValueError): evidence.project(data)
        data = self.data(); data['dataset']['case_ids'] = [str(i) for i in range(1001)]
        with self.assertRaises(ValueError): evidence.project(data)

    def test_reference_escape_and_public_size(self):
        for member in ('../escape','/absolute','C:\\private','safe/../escape','a//b'):
            data = self.data(); data['references'][0]['member'] = member
            with self.subTest(member=member), self.assertRaises(ValueError): evidence.project(data)
        data = self.data(); data['observations'][0]['references'] = ['sha256:'+'f'*64]
        with self.assertRaises(ValueError): evidence.project(data)
        # Enforce the serialized boundary independently of row-count limits.
        import unittest.mock
        with unittest.mock.patch.object(evidence, 'PUBLIC_LIMIT', 100):
            with self.assertRaises(ValueError): evidence.project(self.data())

    def test_linked_input_components(self):
        root = self.native(); alias = self.root/'alias'; alias.symlink_to(root, target_is_directory=True)
        with self.assertRaises(ValueError): evidence.normalize_behavioral(alias, 'podman')
        p = root/'versions.json'; os.link(p, self.root/'hardlinked')
        with self.assertRaises(ValueError): evidence.normalize_behavioral(root, 'podman')

    def test_ambiguous_run_requires_selection(self):
        root = self.native(); base = root/'results/podman'; run = next(base.iterdir())
        shutil.copytree(run, base/'second-run')
        with self.assertRaises(ValueError): evidence.normalize_behavioral(root, 'podman')
        data = evidence.normalize_behavioral(root, 'podman', run.name)
        self.assertEqual(data['run_id'], run.name)
        (base/'latest').symlink_to(run, target_is_directory=True)
        with self.assertRaises(ValueError): evidence.normalize_behavioral(root, 'podman', run.name)

    def test_cli_and_unchanged_inputs(self):
        root = self.native()
        before = {p.relative_to(root):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
        commands = [['inventory'], ['normalize','--kind','behavioral','--skill','podman','--input',str(root)],
                    ['normalize','--kind','static','--skill','podman','--input',str(FIXTURES/'static-synthetic')],
                    ['project','--input',str(FIXTURES/'gh-no-model.json')]]
        for command in commands:
            result = subprocess.run([sys.executable,str(REPO/'.github/scripts/skill_evidence.py'),*command], capture_output=True,text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            output = Path(result.stdout.strip()); self.addCleanup(shutil.rmtree, output)
            self.assertFalse(output.is_relative_to(REPO)); self.assertTrue(output.is_dir())
            for p in output.glob('*.json'):
                self.assertEqual(p.read_bytes(), evidence.encoded(evidence.read_json(p)))
        after = {p.relative_to(root):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_rejected_destinations(self):
        values = {'public-report.json': evidence.project(self.data())}
        for path in (REPO/'new-output', self.root, self.root/'missing/child', self.root/'../escape'):
            with self.subTest(path=path), self.assertRaises(ValueError): evidence.write_outputs(values, path)
        alias = self.root/'alias'; alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError): evidence.write_outputs(values, alias/'new')
        destination = self.root/'new'; evidence.write_outputs(values, destination)
        with self.assertRaises(ValueError): evidence.write_outputs(values, destination)


if __name__ == '__main__':
    unittest.main()
