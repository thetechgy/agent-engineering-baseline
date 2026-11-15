"""Consequential 0.9 adoption boundaries, exercised without credentials or judges."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.github/scripts'))


@unittest.skipUnless(os.environ.get('EVALUATOR_ADOPTION_CONTROLS') == '1', '0.9 owning runtime qualification')
class AdoptionTests(unittest.TestCase):
    def test_released_status_keeps_confirmed_failure_and_missing_coverage(self):
        import skill_reports as reports
        from skillevaluator.models import ValidationResult, Finding, Severity
        from skillevaluator.reporting.json_reporter import JSONReporter
        result = ValidationResult(validator_name='Security Scan')
        result.add_finding(Finding(category='SECURITY', severity=Severity.HIGH,
                                  check_name='known_violation', message='Controlled violation',
                                  file_path='SKILL.md', line_number=1))
        result.mark_scan_incomplete('skillspector')
        native = json.loads(JSONReporter(include_timestamp=False).render_all([result]))
        self.assertEqual(native['overall_status'], 'failed')
        self.assertEqual(native['incomplete_scans'], ['skillspector'])
        self.assertEqual(native['results'][0]['status'], 'failed')
        self.assertEqual(len(reports.released_static_results(native)), 1)
        for key, value in (('overall_status', 'incomplete'), ('overall_passed', True)):
            bad = copy.deepcopy(native); bad[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                reports.released_static_results(bad)
        bad = copy.deepcopy(native); bad['results'][0]['status'] = 'passed'
        with self.assertRaises(ValueError): reports.released_static_results(bad)
        # Exercise the repository's actual catalog and public projection boundaries.
        import skill_evidence as evidence
        import evaluator_profiles as profiles
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory) / 'work'
            skill = work / '.apm/skills/scanner-control'; skill.mkdir(parents=True)
            (skill / 'SKILL.md').write_text('---\nname: scanner-control\ndescription: Fixture.\n---\n')
            bundle = Path(directory) / 'native'
            destination = bundle / 'reports/scanner-control'; destination.mkdir(parents=True)
            filename = 'skillevaluator-output-20261114000000.json'
            native['skills'] = [{'name': 'scanner-control'}]
            reports.write_json(destination / filename, native)
            for suffix in ('.md', '.html'):
                (destination / Path(filename).with_suffix(suffix)).write_text('Controlled human report')
            reports.write_json(bundle / 'reports/catalog-summary.json', {'total': 1, 'failed': 1, 'skills': [
                {'name': 'scanner-control', 'passed': False, 'reason': 'validation failed', 'json_report': filename}]})
            (bundle / 'catalog.exit').write_text('1\n')
            reports.write_json(bundle / 'versions.json', dict(profiles.candidate_versions(profiles.NEXT),
                fixture='synthetic', scanner_runtime=evidence.SCANNER_RUNTIME_NEXT,
                scanners=evidence.SCANNER_RUNTIME_NEXT['versions'],
                skillspector_revision=evidence.SCANNER_RUNTIME_NEXT['skillspector_revision']))
            reports.catalog_report(work, bundle)
            captured = evidence.normalize_static(bundle, 'scanner-control', workspace=work)
            public = evidence.project(captured)
            self.assertEqual(public['availability']['status'], 'incomplete')
            self.assertTrue(any(row['scanner'] == 'SECURITY' and row['status'] == 'failed' for row in public['scans']))
            self.assertTrue(any(row['scanner'] == 'skillspector' and row['status'] == 'incomplete' for row in public['scans']))
            self.assertTrue(any(row['check'] == 'known_violation' for row in public['findings']))
            # Hand current public evidence to the existing publisher, then rebuild
            # with the retained host. Neither build normalizes or rescores records.
            import skill_pages as pages
            from test_skill_pages import bundle, prov
            site = Path(directory) / 'site'
            revision = pages.git(ROOT, 'rev-parse', 'HEAD')
            public['source'].update(repository=pages.REPOSITORY, revision=revision)
            bundle(site / 'report/current', extra=('scanner-control',))
            state = {'schema_version': 1, 'slots': {}, 'current': {'revision': revision,
                     'digest': pages.digest((site / 'report/current/inventory/inventory.json').read_bytes())}}
            pages.write(site, 'report/publication.json', pages.encoded(state))
            pages.admit(site, state, 'quality', prov(revision),
                        bundle(Path(directory) / 'public', [public]), ROOT)
            pages.write(site, 'report/publication.json', pages.encoded(state))
            pages.build(site)
            before = pages.tree(site)
            legacy = os.environ['SKILL_EVALUATOR_PYTHON']
            run = subprocess.run([legacy, '-B', str(ROOT / '.github/scripts/skill_pages.py'),
                                  'build', '--site', str(site)], capture_output=True, text=True, timeout=60)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(before, pages.tree(site))
            changed = copy.deepcopy(dict(captured)); changed['findings'] = []
            with self.assertRaises(ValueError): evidence.project(changed)
            forged = copy.deepcopy(dict(public))
            forged['policy'] = evidence.make_policy({'evaluator_revision': profiles.HISTORICAL_REVISION}, provenance='runtime_recorded')
            with self.assertRaisesRegex(ValueError, 'Scanner adapter and public producer differ'):
                evidence.validate_public(forged)

    def test_actual_native_verifier_and_unscored_collection_visibility(self):
        from unscored_security_controls import run_visibility
        run_visibility(self)
        from test_unscored_security import SecurityProjectionTests
        SecurityProjectionTests('test_actual_collector_handles_secondary_sidecar_failure_without_losing_known_finding').debug()


    def test_unlinked_multi_wrapper_secret_is_retained_once_without_attribution(self):
        from skillevaluator.tier3.eval_core.atif_helpers import extract_tool_calls_as_dicts
        from skillevaluator.tier3.eval_core.checks import check_security
        source = 'const r=await tools.exec_command({cmd:"pwd"}); text(r.output);'
        trajectory = {'steps': [{'source': 'agent', 'tool_calls': [
            {'function_name': 'exec', 'arguments': {'input': source}},
            {'function_name': 'exec', 'arguments': {'input': source}}],
            'observation': {'results': [{'content': 'Authorization: Bearer sk-' + 'abcdefgh12345678'}]}}]}
        calls = extract_tool_calls_as_dicts(trajectory)
        self.assertTrue(all(c['observation'] == '' for c in calls))
        self.assertTrue(all(c['observation_status'] == 'unobserved_inner_call' for c in calls))
        result = check_security(calls)
        findings = [f for f in result['findings'] if f['type'] == 'secret_exposure']
        self.assertEqual(len(findings), 1)
        self.assertNotIn('tool', findings[0])
        self.assertNotIn('target_skill_used_before', findings[0])

    def test_held_consumers_refuse_candidate_before_execution(self):
        import skill_evidence as evidence
        with self.assertRaisesRegex(ValueError, 'producer owning runtime'):
            evidence.normalize_behavioral(ROOT / '.github/tests/fixtures/skill_evidence/podman-native', 'podman')
        import evaluator_profiles as profiles
        import skill_reports as reports
        import skill_review
        import skill_report_reviews
        with self.assertRaises(ValueError):
            reports.validate_benchmark_versions(dict(profiles.candidate_versions(profiles.NEXT), docker_compose='5.7.1'))
        with self.assertRaises(ValueError):
            skill_review.versions()
        with self.assertRaisesRegex(ValueError, 'Pinned validator environment required'):
            skill_report_reviews.load([Path('not-opened.json')], None)

    @unittest.skipUnless(os.environ.get('EVALUATOR_ADOPTION_SCAN_OUTPUT'), 'requires retained native scanner assessment')
    def test_repository_dataset_revision_admitted_with_findings_visible(self):
        root = Path(os.environ['EVALUATOR_ADOPTION_SCAN_OUTPUT']) / 'repository-caveats'
        self.assertFalse((root / 'collection-gate.json').exists())
        datasets = root / 'after/native/datasets'
        expected = {p.parents[1].name for p in (ROOT / '.apm/skills').glob('*/evals/evals.json')}
        self.assertEqual({p.stem for p in datasets.glob('*.json')}, expected)
        for name in expected:
            self.assertEqual((datasets / (name + '.exit')).read_text().strip(), '0', name)
            self.assertTrue(all(row['status'] == 'ok' for row in json.loads(
                (datasets / (name + '.json')).read_text())), name)
        html = (root / 'report.html').read_text()
        for marker in ('reference_missing', 'complete_with_caveats', 'RA1'):
            self.assertIn(marker, html)

    def test_podman_outcome_revision_preserves_negative_case_and_rejection(self):
        import shutil
        import hashlib
        receipt = json.loads((ROOT / 'docs/evaluations/podman-dataset/receipt.json').read_text())
        current = (ROOT / '.apm/skills/podman/evals/evals.json').read_bytes()
        original = current.replace(receipt['revised_expected_output'].encode(),
                                   receipt['original_expected_output'].encode(), 1)
        self.assertEqual(hashlib.sha256(original).hexdigest(), receipt['original_sha256'])
        self.assertEqual(hashlib.sha256(current).hexdigest(), receipt['revised_sha256'])
        before, after = json.loads(original), json.loads(current)
        old_case = next(row for row in before['evals'] if row['id'] == 8)
        new_case = next(row for row in after['evals'] if row['id'] == 8)
        old_case['expected_output'] = new_case['expected_output']
        self.assertEqual(before, after)
        self.assertIsNone(new_case['expected_skill'])
        self.assertIs(new_case['should_trigger'], False)
        self.assertEqual(current, (ROOT / '.agents/skills/podman/evals/evals.json').read_bytes())
        with tempfile.TemporaryDirectory() as directory:
            skill = Path(directory) / 'podman'
            shutil.copytree(ROOT / '.apm/skills/podman', skill)
            for data, code in ((original, 1), (current, 0)):
                (skill / 'evals/evals.json').write_bytes(data)
                result = subprocess.run([sys.executable, '-B', '-c',
                    'from skillevaluator.cli import cli; cli()', 'tier3', 'validate',
                    str(skill), '--strict', '--json'], capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, code, result.stderr)
                warnings = [row for row in json.loads(result.stdout) if row['status'] != 'ok']
                if code:
                    self.assertEqual(len(warnings), 1)
                    self.assertEqual(warnings[0]['path'], 'entry 8')
                    self.assertIn("expected_output grades skill use ('podman skill')", warnings[0]['message'])
                else:
                    self.assertEqual(warnings, [])
