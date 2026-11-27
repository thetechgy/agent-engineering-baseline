"""Exact offline validator profiles and synthetic assessment/report attachments."""

import copy
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import skill_analysis as analysis
import skill_evidence as evidence
import skill_report as report
import skill_report_reviews as attachments
import test_skill_review as review_fixtures
from test_skill_analysis import write
from test_skill_report import Document

from review_snapshots import parity_archive, restore_parity_case

class AttachmentTests(unittest.TestCase):
    bundle = review_fixtures.ReviewTests.bundle

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.clock = patch.object(evidence, 'utc_now', wraps=evidence.utc_now)
        self.clock.start(); self.addCleanup(self.clock.stop)

    def fixture(self, profile='current-v4', category=None, *, unmeasured=False):
        key = '-'.join(part for part in (profile, category, 'unmeasured' if unmeasured else None) if part)
        with parity_archive() as archive:
            spec, self.path, _ = restore_parity_case(self, archive, self.root, key=key)
        self.spec = spec
        self.captured = analysis.capture_inputs([Path(name) for name in spec['inputs']])
        self.result = analysis.validate_analysis(None, self.captured)
        return spec

    def supplied(self, *, verdict='PASS', scored=True, suffix='one', kind='independent_ai'):
        source = {'report_hash': self.spec['review_digest'], 'verdict': verdict, 'score': 9, 'maximum': 10,
                  'dimensions': {name: {'score': s, 'rationale': 'Synthetic assessment rationale.'}
                                 for name, s in zip(('a', 'b', 'c', 'd', 'e'), (2, 1, 2, 2, 2))},
                  'limitations': 'Synthetic assessment; no authenticated human approval.',
                  'unselected_private_metadata': '/home/private-fixture/never-rendered'}
        doc = self.root / ('assessment-' + suffix + '.json'); write(doc, source)
        rubric = self.root / ('rubric-' + suffix + '.json')
        write(rubric, {'dimensions': dict.fromkeys(source['dimensions'], '0 to 2; supplied rubric')})
        row = {'author_kind': kind, 'attribution': 'Synthetic ChatGPT assessor',
               'document': {'path': str(doc), 'digest': evidence.digest_bytes(doc.read_bytes())},
               'report_digest_locator': ['report_hash'],
               'fields': {'verdict': ['verdict'], 'score': ['score'] if scored else None,
                          'maximum': ['maximum'] if scored else None, 'dimensions': ['dimensions'] if scored else None,
                          'limitations': ['limitations']},
               'narrative': None, 'rubric': {'path': str(rubric), 'digest': evidence.digest_bytes(rubric.read_bytes())},
               'rubric_locator': [], 'freeze': None}
        self.spec['assessments'].append(row); write(self.path, self.spec)
        return row

    def load(self):
        return attachments.load([self.path], self.captured)

    def test_active_validator_admits_current_static_scanner_provenance(self):
        import private_review_snapshot as snapshot
        import static_evaluator as static
        from test_skill_analysis import static_control

        record = static_control(states={'SECURITY': 'incomplete'})
        record['scanner_runtime'] = static.current_scanner_runtime(evidence.SCANNER_RUNTIME_STATIC_CANDIDATE)
        record['policy'] = evidence.make_policy(
            {key: static.VERSIONS[key] for key in ('evaluator_revision', 'harbor', 'python')},
            judge={'model': None, 'provider': None, 'enabled': False},
            provenance='runtime_recorded', published=static.VERSIONS['producer_profile'])
        scripts = snapshot.unpack(self.root / 'frozen', snapshot.ACTIVE_PROFILE)
        child = """
import json
import sys

sys.path.insert(0, sys.argv[1])
import skill_evidence as evidence

record = json.load(sys.stdin)
evidence.validate_public(record)
assert record['availability']['status'] == 'incomplete'
"""
        command = [attachments.validator_python(snapshot.ACTIVE_PROFILE), '-I', '-B', '-c', child, str(scripts)]
        result = subprocess.run(command, input=evidence.encoded(record), capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr.decode())

    def test_current_and_historical_production_validators(self):
        # A separate fixture root per profile keeps originals and guards unchanged.
        for profile in attachments.PROFILES:
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as directory:
                self.root = Path(directory)
                self.fixture(profile)
                validated = self.load()
                item = validated.items[0]
                hashes = attachments.PROFILES[profile][1]
                implementation = [[name, 'sha256:' + digest] for name, digest in zip(attachments.MODULES, hashes)]
                if profile in attachments.REGISTRY_DIGESTS:
                    implementation.append(['custom-metrics.json', 'sha256:' + attachments.REGISTRY_DIGESTS[profile]])
                implementation.extend([Path(member).name, 'sha256:' + digest]
                    for member, digest in attachments.SUPPORT_FILES.get(profile, {}).items())
                self.assertEqual(item['report']['provenance']['implementation_digest'], evidence.identity(implementation))
                self.assertEqual(item['record_id'], self.spec['record_id'])
                output = report.render_report(self.result, self.captured, reviews=validated).decode()
                self.assertIn('Model interpretation', output)
                self.assertIn('No recommendations supplied', output)
                self.assertIn('not_quality_qualified', output)
                self.assertNotIn(str(self.root), output)

    def test_release_snapshot_rejects_changed_archive_before_unpacking(self):
        import private_review_snapshot as snapshot

        for profile, member in ((snapshot.PROFILE, 'SNAPSHOT'), (snapshot.V2_PROFILE, 'V2_OVERLAY'),
                                (snapshot.V3_PROFILE, 'V3_OVERLAY'), (snapshot.V4_PROFILE, 'V4_OVERLAY'),
                                (snapshot.V5_PROFILE, 'V5_OVERLAY'),
                                (snapshot.V121_PROFILE, 'V121_OVERLAY'),
                                (snapshot.ACTIVE_PROFILE, 'ACTIVE_OVERLAY')):
            with self.subTest(profile=profile):
                changed = self.root / 'changed.zip'
                changed.write_bytes(getattr(snapshot, member).read_bytes() + b'changed')
                destination = self.root / 'unpacked'
                with patch.object(snapshot, member, changed):
                    with self.assertRaisesRegex(ValueError, 'Unreviewed private validator snapshot'):
                        snapshot.unpack(destination, profile)
                self.assertFalse(destination.exists())

    def test_release_review_cli_and_attachment_use_the_same_frozen_source(self):
        import json
        import shutil
        import private_review_snapshot as snapshot
        from private_review_snapshot import ACTIVE_PROFILE, PROFILE, V2_PROFILE, V3_PROFILE, V4_PROFILE, unpack

        cases = (('current-v5', False, ACTIVE_PROFILE), ('gh-89f46f0', False, ACTIVE_PROFILE),
                 (None, True, ACTIVE_PROFILE), ('current-v5', False, snapshot.V121_PROFILE),
                 ('current-v5', False, snapshot.V5_PROFILE),
                 ('current-v5', False, PROFILE), ('current-v5', False, V2_PROFILE),
                 ('current-v5', False, V3_PROFILE), ('current-v5', False, V4_PROFILE),
                 ('gh-89f46f0', False, V4_PROFILE), (None, True, V4_PROFILE))
        for key, pester, profile in cases:
            with self.subTest(fixture=key or 'pester', profile=profile), tempfile.TemporaryDirectory() as directory:
                base = Path(directory)
                with parity_archive(pester=pester) as archive:
                    spec, spec_path, _ = restore_parity_case(self, archive, base / 'inputs', key=key)
                scripts = unpack(base / 'frozen', profile)
                python = attachments.validator_python(profile)
                command = [python, '-B', str(evidence.ROOT / '.github/scripts/skill_review.py')]
                if profile != ACTIVE_PROFILE:
                    command = [python, '-I', '-B', '-c', snapshot.RUN_CLI, str(scripts), str(evidence.ROOT)]
                args = ['--analysis', spec['analysis'], '--skill', spec['skill'], '--record-id', spec['record_id']]
                for item in spec['inputs']:
                    args.extend(['--input', item])
                for member, flag in (('source', '--source'), ('support', '--support'), ('selection', '--source-selection')):
                    if spec[member] is not None:
                        args.extend([flag, spec[member]])
                env = {key: os.environ[key] for key in ('PATH', 'TMPDIR', 'LANG') if key in os.environ}
                env.update(HOME=str(base), PYTHON_DOTENV_DISABLED='1', LITELLM_LOCAL_MODEL_COST_MAP='True')
                planned = base / 'prepared'
                build = subprocess.run([*command, 'prepare', *args, '--output', str(planned)],
                    env=env, capture_output=True, text=True, timeout=45)
                self.assertEqual(build.returncode, 0, build.stderr)
                emitted = evidence.read_json(planned / 'review-context.json')
                # Build the synthetic judgment from the context emitted by its frozen owner.
                fixture_judgment = review_fixtures.judgment(SimpleNamespace(value=emitted))
                source = attachments.AUDIT_GUARD + """
sys.path.insert(0, sys.argv[1])
import skill_review as review
args = json.loads(sys.argv[2])
judgment, config = json.load(sys.stdin)
context = review.prepare([Path(p) for p in args['inputs']], Path(args['analysis']),
    args['skill'], args['record_id'],
    **{name: Path(args[name]) if args[name] is not None else None for name in ('source','support','selection')})
sample = review.make_review(judgment, context, review.ModelConfig(**config),
    review.Usage(preflight_input_tokens=100, input_tokens=100, output_tokens=25, total_tokens=125))
target = Path(sys.argv[3])
(target / 'skill-review.json').write_bytes(review.evidence.encoded(sample))
(target / 'skill-review.md').write_bytes(review.render_review(sample, context))
"""
                fixture = base / 'review'; fixture.mkdir()
                subprocess.run([python, '-I', '-B', '-c', source, str(scripts), json.dumps(spec), str(fixture)],
                               input=json.dumps([fixture_judgment, review_fixtures.CONFIG]),
                               env=env, text=True, check=True, timeout=45)
                save = fixture / 'skill-review.json'
                release_review = evidence.read_json(save)
                self.assertEqual(emitted['implementation_digest'], release_review['provenance']['implementation_digest'])
                self.assertEqual(release_review['provenance']['versions']['skillevaluator'],
                                 '1.2.1' if profile in (snapshot.V121_PROFILE, ACTIVE_PROFILE) else '1.0.1')
                self.assertEqual(subprocess.run([*command, 'validate', *args, '--review', str(save)],
                    env=env, capture_output=True, timeout=45).returncode, 0)
                if key == 'current-v5' and profile == ACTIVE_PROFILE:
                    forbidden = evidence.ROOT / ('.aeb-review-output-' + base.name)
                    try:
                        self.assertNotEqual(subprocess.run([*command, 'prepare', *args, '--output', str(forbidden)],
                            env=env, capture_output=True, timeout=45).returncode, 0)
                        self.assertFalse(forbidden.exists())
                    finally:
                        if forbidden.is_dir() and not forbidden.is_symlink():
                            shutil.rmtree(forbidden)
                spec.update(profile=profile, tooling=None, review=str(save),
                            review_digest=evidence.digest_bytes(save.read_bytes()),
                            markdown_digest=evidence.digest_bytes((fixture / 'skill-review.md').read_bytes()))
                write(spec_path, spec)
                captured = analysis.capture_inputs([Path(name) for name in spec['inputs']])
                item = attachments.load([spec_path], captured).items[0]
                expected_revision, expected_execution = snapshot.identity(profile)
                self.assertEqual(item['tooling_revision'], expected_revision)
                self.assertEqual(item['validator_execution'], expected_execution)
                spec['tooling'] = str(base / 'frozen')
                write(spec_path, spec)
                with self.assertRaisesRegex(ValueError, 'Tooling for this profile is fixed'):
                    attachments.load([spec_path], captured)

    def test_frozen_current_profile_rejects_changed_checkout_and_replays_on_release_host(self):
        self.fixture('current-v4')
        self.load()  # Exact retained validator bytes remain supported.
        tooling = self.spec['tooling']
        self.spec['tooling'] = None; write(self.path, self.spec)
        with self.assertRaisesRegex(ValueError, 'Unreviewed validator module'):
            self.load()
        # The original profile remains usable with its exact retained source.
        self.spec['tooling'] = tooling; write(self.path, self.spec)
        self.load()
        output_parent = tempfile.TemporaryDirectory(); self.addCleanup(output_parent.cleanup)
        output_root = Path(output_parent.name)
        command = [sys.executable, '-B',
                   str(evidence.ROOT / '.github/scripts/skill_report.py'),
                   '--input', self.spec['inputs'][0], '--analysis', self.spec['analysis'],
                   '--analyst-review', str(self.path), '--output', str(output_root / 'report-host')]
        child = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        self.assertEqual(child.returncode, 0, child.stderr.decode())
        self.assertTrue((output_root / 'report-host/report.html').is_file())

    def test_new_profile_requires_exact_supporting_code_and_data(self):
        self.fixture('current-v5')
        for member in attachments.SUPPORT_FILES['current-v5']:
            path = Path(self.spec['tooling']) / member
            original = path.read_bytes()
            path.write_bytes(original + b' ')
            with self.subTest(member=member), self.assertRaisesRegex(ValueError, 'supporting file'):
                self.load()
            path.write_bytes(original)
        self.load()

    def test_saved_profile_rejects_substituted_dependency_version(self):
        self.fixture('current-v5')
        saved = Path(self.spec['review'])
        value = evidence.read_json(saved)
        value['provenance']['versions']['pydantic'] = attachments.PREVIOUS_PINS['pydantic']
        write(saved, value)
        self.spec['review_digest'] = evidence.digest_bytes(saved.read_bytes())
        write(self.path, self.spec)
        with self.assertRaises(ValueError):
            self.load()

    def test_custom_profile_requires_exact_retained_metric_registry(self):
        self.fixture('custom-metrics-v2')
        self.load()
        registry = self.root / 'tooling/.github/evals/custom-metrics.json'
        registry.write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError, 'Unreviewed metric registry'):
            self.load()
        registry.unlink()
        with self.assertRaises((ValueError, FileNotFoundError)):
            self.load()

    def test_changed_checkout_cannot_substitute_for_frozen_current_profile(self):
        self.fixture('current-v2')
        self.load()  # Exact retained original modules remain supported.
        self.spec['tooling'] = None; write(self.path, self.spec)
        with self.assertRaisesRegex(ValueError, 'Unreviewed validator module'):
            self.load()

    def test_multiple_assessments_preserve_disagreement_and_unscored_result(self):
        self.fixture(category='investigate')
        self.supplied()
        self.supplied(verdict='Needs further investigation', scored=False, suffix='two', kind='human_supplied')
        validated = self.load()
        output = report.render_report(self.result, self.captured, reviews=validated).decode()
        for text in ('PASS', 'Needs further investigation', 'Numeric score not assigned', '9 out of 10',
                     'Independent AI assessment', 'Human assessment (supplied; unauthenticated)',
                     'No authenticated human approval', 'investigate'):
            self.assertIn(text, output)
        self.assertNotIn('never-rendered', output)
        self.assertEqual(len(validated.items[0]['assessments']), 2)
        self.spec['assessments'].reverse(); write(self.path, self.spec)
        self.assertEqual(report.render_report(self.result, self.captured, reviews=self.load()), output.encode())
        doc = Document(output)
        self.assertEqual(len(doc.ids), len(set(doc.ids)))
        self.assertTrue(all(href.startswith('#') and href[1:] in doc.ids for href in doc.links))

    def test_review_first_exposes_proposed_action_and_separate_assessments(self):
        self.fixture('gh-89f46f0', category='investigate', unmeasured=True)
        self.supplied()
        self.supplied(verdict='Substantive pass; no numeric score assigned', scored=False, suffix='unscored')
        output = report.render_report(self.result, self.captured, reviews=self.load()).decode()
        overview = output.split('<section aria-labelledby="important-findings"', 1)[1].split('</section>', 1)[0]
        for value in ('Analyst conclusions and recommended actions', 'model interpretation',
                      'Request exact retained results from the overlay owner.', 'Independent AI assessment (supplied)',
                      'Synthetic ChatGPT assessor', '9 out of 10', 'Substantive pass; no numeric score assigned',
                      'Numeric score not assigned', 'Not quality qualified',
                      'Authenticated human approval is not established'):
            self.assertIn(value, overview)
        self.assertLess(output.index('Analyst conclusion:</strong>'), output.index('<h3>Behavioral run:'))
        self.assertIn('gh · analyst conclusions, proposed actions and citations', overview)

    def test_assessment_labels_scores_and_original_fields_match_preview_and_detail(self):
        self.fixture(category='investigate')
        for kind in ('independent_ai', 'human_supplied', 'unknown'):
            row = self.supplied(verdict='pass_substantive_usefulness_demonstrated', kind=kind, suffix=kind)
            document = Path(row['document']['path'])
            value = evidence.read_json(document)
            value['limitations'] += ' Synthetic category: ' + kind + '.'
            write(document, value)
            row['document']['digest'] = evidence.digest_bytes(document.read_bytes())
        write(self.path, self.spec)
        self.supplied(verdict='Keep My_Unfamiliar verdict. <verbatim>', scored=False, suffix='freeform')
        validated = self.load()
        identities = (evidence.identity(self.result), evidence.identity(self.captured.records),
                      evidence.identity(validated.items))
        output = report.render_report(self.result, self.captured, reviews=validated).decode()
        overview = output.split('<section aria-labelledby="important-findings"', 1)[1].split('</section>', 1)[0]
        detail = output.split('Model interpretation · analyst report', 1)[1]
        for part in (overview, detail):
            for label in ('Independent AI assessment (supplied)', 'Human assessment (supplied; unauthenticated)',
                          'Assessment (author category unknown)', 'Substantive usefulness pass',
                          '9 out of 10', 'Numeric score not assigned',
                          'Keep My_Unfamiliar verdict. &lt;verbatim&gt;'):
                self.assertIn(label, part)
        self.assertIn('Not quality qualified', overview)
        self.assertIn('Analyst interpretation · Investigate', overview)
        self.assertIn('Proposed action · Investigate:', overview)
        self.assertIn('1 recommendation.', detail)
        self.assertIn('1 independently validated analyst report attached.', output)
        self.assertNotIn('1 recommendations', output)
        for supplied in validated.items[0]['assessments']:
            self.assertIn(report.disclosure('Original assessment fields', {k: supplied[k] for k in
                ('author_kind', 'attribution', 'verdict', 'score', 'maximum')}), output)
        self.assertIn('&quot;disposition&quot;: &quot;investigate&quot;', output)
        self.assertEqual(identities, (evidence.identity(self.result), evidence.identity(self.captured.records),
                                     evidence.identity(validated.items)))

    def test_recommendation_counts_preserve_supplied_prose(self):
        self.fixture(category='investigate')
        original = self.load().items[0]
        recommendation = original['report']['judgment']['recommendations'][0]
        for count in (0, 1, 2):
            with self.subTest(count=count):
                item = copy.deepcopy(original)
                item['report']['judgment']['recommendations'] = [copy.deepcopy(recommendation) for _ in range(count)]
                output = report.interpretation(item)
                self.assertIn(f'{count} ' + ('recommendation.' if count == 1 else 'recommendations.'), output)
                if count:
                    for key in ('scope', 'justification', 'expected_benefit'):
                        self.assertIn(report.text(recommendation[key]), output)

    def test_multiple_validated_analyst_reports_use_plural(self):
        parent = self.root
        descriptors = []; inputs = []
        for name, unmeasured in (('measured', False), ('unmeasured', True)):
            self.root = parent / name; self.root.mkdir()
            spec = self.fixture(unmeasured=unmeasured)
            descriptors.append(self.path)
            inputs.extend(Path(value) for value in spec['inputs'])
        captured = analysis.capture_inputs(inputs)
        result = analysis.validate_analysis(None, captured)
        validated = attachments.load(descriptors, captured)
        self.assertEqual(len(validated.items), 2)
        output = report.render_report(result, captured, reviews=validated).decode()
        self.assertIn('2 independently validated analyst reports attached.', output)

    def test_unmeasured_upstream_gh_interpretation_remains_investigation_only(self):
        self.fixture('gh-89f46f0', category='investigate', unmeasured=True)
        validated = self.load()
        value = validated.items[0]['report']
        self.assertEqual(value['provenance']['source_owner'], 'upstream')
        self.assertEqual(value['judgment']['assessment']['sufficiency']['conclusion'], 'investigation_only')
        output = report.render_report(self.result, self.captured, reviews=validated).decode()
        for text in ('Unmeasured', 'Source owner: upstream', 'Not measured', 'No measured trials supplied',
                     'overlay owner', 'Unknown / not supplied'):
            self.assertIn(text, output)
        self.assertFalse(any(row['category'] == 'modify_skill' for row in value['judgment']['recommendations']))

    def test_duplicate_selected_record_and_assessment_reject(self):
        self.fixture()
        with self.assertRaises(ValueError): attachments.load([self.path, self.path], self.captured)
        row = self.supplied()
        self.spec['assessments'].append(row); write(self.path, self.spec)
        with self.assertRaises(ValueError): self.load()

    def test_altered_json_or_markdown_reject_even_if_descriptor_hash_updated(self):
        self.fixture()
        saved = Path(self.spec['review']); raw = saved.read_bytes(); md = saved.with_suffix('.md')
        original = md.read_bytes()
        changed = evidence.parse_json(raw); changed['provenance']['context_digest'] = evidence.identity('altered')
        write(saved, changed); self.spec['review_digest'] = evidence.digest_bytes(saved.read_bytes()); write(self.path, self.spec)
        with self.assertRaises(ValueError): self.load()
        saved.write_bytes(raw); self.spec['review_digest'] = evidence.digest_bytes(raw)
        md.write_bytes(original + b'\nInjected assessment\n')
        self.spec['markdown_digest'] = evidence.digest_bytes(md.read_bytes()); write(self.path, self.spec)
        with self.assertRaises(ValueError): self.load()

    def test_tooling_hash_and_profile_cannot_authorize_code(self):
        self.fixture('podman-1cffcf9')
        scripts = Path(self.spec['tooling']) / '.github/scripts'
        marker = self.root / 'executed'
        (scripts / 'skill_review.py').write_text(
            f"from pathlib import Path\nPath({str(marker)!r}).write_text('Unreviewed module executed')\n"
            "raise RuntimeError('Never import altered module')\n")
        with self.assertRaisesRegex(ValueError, 'Unreviewed validator module'): self.load()
        self.assertFalse(marker.exists())
        self.spec['profile'] = 'arbitrary'; write(self.path, self.spec)
        with self.assertRaises(ValueError): self.load()

    def test_import_shadowing_and_environment_do_not_affect_temp_layout(self):
        self.fixture('gh-89f46f0')
        shadow = self.root / 'shadow'; shadow.mkdir()
        (shadow / 'skill_review.py').write_text("raise RuntimeError('Untrusted import')")
        (shadow / 'sitecustomize.py').write_text("raise RuntimeError('Untrusted site')")
        with patch.dict(os.environ, {'PYTHONPATH': str(shadow), 'OPENAI_API_KEY': 'must-not-be-forwarded'}):
            self.load()
        self.assertFalse(list(Path(self.spec['tooling']).rglob('__pycache__')))

    def test_missing_evidence_and_mismatched_record_or_skill_reject(self):
        self.fixture()
        original = copy.deepcopy(self.spec)
        for mutate in (lambda s: s.update(source=str(self.root / 'missing')),
                       lambda s: s.update(record_id=evidence.identity('other-record')),
                       lambda s: s.update(skill='gh')):
            self.spec = copy.deepcopy(original); mutate(self.spec); write(self.path, self.spec)
            with self.assertRaises((ValueError, OSError)): self.load()

    def test_forged_assessment_binding_approval_and_score_reject(self):
        self.fixture(); row = self.supplied()
        original = copy.deepcopy(self.spec)
        for mutate in (lambda r: r.update(authenticated_approval=True),
                       lambda r: r.update(author_kind='authenticated_human'),
                       lambda r: r.update(report_digest_locator=['verdict']),
                       lambda r: r['fields'].update(score=['maximum'])):
            self.spec = copy.deepcopy(original); mutate(self.spec['assessments'][0]); write(self.path, self.spec)
            with self.assertRaises(ValueError): self.load()

    def test_injection_is_inert_and_private_projection_rejects(self):
        self.fixture(); row = self.supplied(verdict='</pre><script>alert(1)</script><img src=x onerror=alert(2)>')
        validated = self.load()
        output = report.render_report(self.result, self.captured, reviews=validated).decode()
        doc = Document(output)
        self.assertEqual(sum(tag == 'script' for tag, _ in doc.elements), 1)
        self.assertFalse(any(tag == 'img' or any(k.startswith('on') for k in attrs) for tag, attrs in doc.elements))
        self.assertIn('&lt;script&gt;', output)
        self.spec['assessments'][0]['fields']['limitations'] = ['unselected_private_metadata']; write(self.path, self.spec)
        with self.assertRaises(ValueError): self.load()

    def test_changed_capture_projection_and_direct_unvalidated_input_reject(self):
        self.fixture(); validated = self.load()
        with self.assertRaises(ValueError): report.render_report(self.result, self.captured, reviews={})
        validated.items[0]['report']['judgment']['assessment']['uncertainty'] = 'Altered after validation'
        with self.assertRaises(ValueError): report.render_report(self.result, self.captured, reviews=validated)
        validated = self.load()
        Path(self.spec['review']).write_bytes(Path(self.spec['review']).read_bytes() + b' ')
        with self.assertRaises(ValueError): report.render_report(self.result, self.captured, reviews=validated)

    def test_final_reference_expiry_recheck_and_base_report(self):
        self.fixture(); validated = self.load()
        record = copy.deepcopy(self.captured.records[self.spec['record_id']])
        deadline = datetime(2026, 10, 19, 19, 11, 15, tzinfo=timezone.utc)
        identity = next(pair for pair, value in evidence.REVIEWED_REFERENCE_EXPIRY.items()
                        if datetime.fromisoformat(value) == deadline)
        pinned = dict(zip(('artifact_id', 'artifact_digest'), identity), provenance='reviewed_extract')
        expired = evidence.reference_expired
        # Route synthetic lifetime checks through the actual pinned expiry logic;
        # synthetic records never acquire reviewed provenance or modified pins.
        with patch.object(evidence, 'reference_expired', side_effect=lambda ref, now: expired(pinned, now)):
            with patch.object(evidence, 'utc_now', return_value=deadline - timedelta(seconds=1)):
                validated.check(self.captured)
            for instant in (deadline, deadline + timedelta(seconds=1)):
                with patch.object(evidence, 'utc_now', return_value=instant):
                    with self.assertRaises(ValueError): validated.check(self.captured)
            # Fresh, separate expired projection can still show historical scores.
            for ref in record['references']: ref['availability'] = 'expired'
            record['availability']['status'] = 'incomplete'
            record['availability']['reasons'] = sorted(set(record['availability']['reasons']) | {'reference_expired'})
            with patch.object(evidence, 'utc_now', return_value=deadline):
                fresh, saved, _ = self.bundle(record, 'current-availability')
                captured = analysis.capture_inputs([fresh])
                output = report.render_report(analysis.validate_analysis(None, captured), captured)
                self.assertIn(b'Original artifact references have expired', output)
                self.assertIn(b'0 independently validated analyst reports', output)

    def test_analyst_cannot_promote_quality_or_publication_metadata(self):
        self.fixture()
        saved = Path(self.spec['review']); original = evidence.read_json(saved)
        for key, value in (('quality_qualification', 'quality_qualified'), ('automated_publication_eligible', True)):
            altered = copy.deepcopy(original); altered['provenance'][key] = value
            write(saved, altered); self.spec['review_digest'] = evidence.digest_bytes(saved.read_bytes()); write(self.path, self.spec)
            with self.assertRaises(ValueError): self.load()

    def test_freeze_digest_context_and_time_are_consistency_only(self):
        self.fixture(); row = self.supplied()
        rubric = evidence.read_json(Path(row['rubric']['path']))
        provenance = evidence.read_json(Path(self.spec['review']))['provenance']
        freeze = self.root / 'freeze.json'
        value = {'rubric_digest': evidence.identity(rubric), 'context_digest': provenance['context_digest'],
                 'original_freeze_utc': (datetime.fromisoformat(provenance['timestamp']) - timedelta(seconds=1)).isoformat()}
        write(freeze, value)
        row['freeze'] = {'path': str(freeze), 'digest': evidence.digest_bytes(freeze.read_bytes())}; write(self.path, self.spec)
        output = report.render_report(self.result, self.captured, reviews=self.load())
        self.assertIn(b'not trusted timestamp attestation', output)
        write(freeze, {key: v for key, v in value.items() if key != 'original_freeze_utc'})
        row['freeze']['digest'] = evidence.digest_bytes(freeze.read_bytes()); write(self.path, self.spec)
        undated = report.render_report(self.result, self.captured, reviews=self.load())
        self.assertIn(b'Freeze time not supplied; time ordering is not established', undated)
        self.assertNotIn(b'time ordering are consistent', undated)
        self.assertNotIn(b'Recorded time ordering is consistent', undated)
        for key, change in (('rubric_digest', evidence.identity('different-rubric')),
                            ('context_digest', evidence.identity('different-context')),
                            ('original_freeze_utc', '2999-01-01T00:00:00+00:00')):
            altered = {**value, key: change}; write(freeze, altered)
            row['freeze']['digest'] = evidence.digest_bytes(freeze.read_bytes()); write(self.path, self.spec)
            with self.assertRaises(ValueError): self.load()

    def test_pinned_dependency_and_extra_descriptor_fields_reject(self):
        self.fixture()
        with patch.object(attachments.private_review_runtime.importlib.metadata, 'version', return_value='unreviewed'):
            with self.assertRaises(ValueError): self.load()
        self.spec['command'] = 'never execute descriptor commands'; write(self.path, self.spec)
        with self.assertRaises(ValueError): self.load()

    def test_historical_attachment_replays_without_legacy_interpreter(self):
        self.fixture('current-v2')
        with patch.dict(os.environ, {'SKILL_LEGACY_REVIEW_PYTHON': '', 'SKILL_PREVIOUS_REVIEW_PYTHON': '',
                                     'SKILL_REVIEW_PYTHON': ''}):
            self.assertEqual(self.load().items[0]['profile'], 'current-v2')

    def test_historical_runtime_alias_cannot_replace_release_host(self):
        self.fixture('current-v2')
        with patch.dict(os.environ, {'SKILL_LEGACY_REVIEW_PYTHON': '/unavailable/python'}):
            self.assertEqual(self.load().items[0]['validator_execution'], 'skillevaluator-1.0.1-private-review-offline-v1')

    def test_duplicate_json_keys_and_linked_documents_reject(self):
        self.fixture(); self.supplied()
        raw = self.path.read_bytes()
        self.path.write_bytes(raw.replace(b'"schema_version": 1', b'"schema_version": 1, "schema_version": 1'))
        with self.assertRaises(ValueError): self.load()
        self.path.write_bytes(raw)
        doc = Path(self.spec['assessments'][0]['document']['path'])
        moved = doc.with_suffix('.original'); doc.rename(moved); doc.symlink_to(moved)
        with self.assertRaises(ValueError): self.load()

    def test_attachment_change_during_render_removes_output(self):
        self.fixture(); row = self.supplied()
        output_parent = tempfile.TemporaryDirectory(); self.addCleanup(output_parent.cleanup)
        destination = Path(output_parent.name) / 'rejected'
        original = report.render_report
        def changed(*args, **kwargs):
            rendered = original(*args, **kwargs)
            doc = Path(row['document']['path']); doc.write_bytes(doc.read_bytes() + b' ')
            return rendered
        with patch.object(report, 'render_report', side_effect=changed):
            with self.assertRaises(ValueError):
                report.generate([Path(self.spec['inputs'][0])], Path(self.spec['analysis']), destination,
                                analyst_reviews=[self.path])
        self.assertFalse(destination.exists())

    def test_external_assessment_directory_protected_before_temporary_allocation(self):
        self.fixture(); row = self.supplied()
        other = tempfile.TemporaryDirectory(); self.addCleanup(other.cleanup)
        parent = Path(other.name)
        for key in ('document', 'rubric'):
            old = Path(row[key]['path']); moved = parent / old.name; old.rename(moved)
            row[key]['path'] = str(moved)
        write(self.path, self.spec)
        entries = sorted(parent.iterdir())
        with patch.dict(os.environ, {'TMPDIR': str(parent)}):
            with self.assertRaises(ValueError): self.load()
        self.assertEqual(sorted(parent.iterdir()), entries)
        with self.assertRaises(ValueError):
            report.generate([Path(self.spec['inputs'][0])], Path(self.spec['analysis']), parent / 'forbidden',
                            analyst_reviews=[self.path])
        self.assertEqual(sorted(parent.iterdir()), entries)

    def test_temporary_tooling_cleanup_after_success_and_validation_failure(self):
        self.fixture()
        original = evidence.write_outputs; reserved = []
        def observed(*args, **kwargs):
            path = original(*args, **kwargs)
            if len(args) == 1: reserved.append(path)
            return path
        with patch.object(evidence, 'write_outputs', side_effect=observed):
            self.load()
            md = Path(self.spec['review']).with_suffix('.md'); md.write_bytes(md.read_bytes() + b'changed')
            self.spec['markdown_digest'] = evidence.digest_bytes(md.read_bytes()); write(self.path, self.spec)
            with self.assertRaises(ValueError): self.load()
        self.assertEqual(len(reserved), 2)
        self.assertTrue(all(not path.exists() for path in reserved))

    def test_audit_guard_blocks_network_dns_and_process_spawning(self):
        prefix = attachments.AUDIT_GUARD
        actions = ["__import__('socket').socket()", "__import__('socket').getaddrinfo('example.invalid',443)",
                   "__import__('subprocess').run(['echo','forbidden'])", "__import__('os').system('echo forbidden')"]
        if hasattr(os, 'fork'): actions.append("__import__('os').fork()")
        for action in actions:
            with self.subTest(action=action):
                child = subprocess.run([sys.executable, '-I', '-B', '-c', prefix + '\n' + action, str(self.root)],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
                self.assertNotEqual(child.returncode, 0)
                self.assertIn(b'Offline validator operation rejected', child.stderr)

    def test_generate_cli_path_secure_output_and_no_partial_output(self):
        self.fixture(); self.supplied()
        output_parent = tempfile.TemporaryDirectory(); self.addCleanup(output_parent.cleanup)
        destination = Path(output_parent.name) / 'html'
        out = report.generate([Path(self.spec['inputs'][0])], Path(self.spec['analysis']), destination,
                              analyst_reviews=[self.path])
        self.assertEqual(out, destination)
        self.assertEqual(out.stat().st_mode & 0o777, 0o700)
        self.assertEqual((out / 'report.html').stat().st_mode & 0o777, 0o600)
        self.assertEqual(list(out.iterdir()), [out / 'report.html'])
        self.spec['review_digest'] = evidence.identity('corrupt'); write(self.path, self.spec)
        with self.assertRaises(ValueError):
            report.generate([Path(self.spec['inputs'][0])], Path(self.spec['analysis']), destination.parent / 'not-created',
                            analyst_reviews=[self.path])
        self.assertFalse((destination.parent / 'not-created').exists())

    def test_cli_attachment_and_bounded_rejection(self):
        self.fixture()
        output_parent = tempfile.TemporaryDirectory(); self.addCleanup(output_parent.cleanup)
        destination = Path(output_parent.name) / 'cli'
        command = [sys.executable, '-B', str(evidence.ROOT / '.github/scripts/skill_report.py'),
                   '--input', self.spec['inputs'][0], '--analysis', self.spec['analysis'],
                   '--analyst-review', str(self.path), '--output', str(destination)]
        child = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        self.assertEqual(child.returncode, 0, child.stderr.decode())
        self.assertTrue((destination / 'report.html').is_file())
        self.spec['profile'] = 'private-untrusted-profile'; write(self.path, self.spec)
        child = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        self.assertEqual(child.returncode, 1)
        self.assertEqual(child.stderr, b'Analyst report inputs rejected; no HTML report is ready. '
            b'Omit --analyst-review for a base report with valid current-availability inputs.\n')
        self.assertNotIn(b'private-untrusted-profile', child.stderr)


if __name__ == '__main__':
    unittest.main()
