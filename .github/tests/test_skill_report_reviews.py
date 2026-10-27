"""Exact offline validator profiles and synthetic assessment/report attachments."""

import copy
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import skill_analysis as analysis
import skill_evidence as evidence
import skill_report as report
import skill_report_reviews as attachments
import test_skill_review as review_fixtures
from test_skill_review import judgment, CONFIG
from test_skill_analysis import write
from test_skill_report import Document

FIXTURE = Path(__file__).parent / 'fixtures/skill_report_reviews/historical-modules.zip'


def frozen_tooling(test, tooling, profile):
    """Restore the exact retained validator and data named by a profile."""
    scripts = tooling / '.github/scripts'; scripts.mkdir(parents=True)
    with zipfile.ZipFile(FIXTURE) as archive:
        for name, expected in zip(attachments.MODULES, attachments.PROFILES[profile][1]):
            raw = archive.read(expected + '.py')
            test.assertEqual(evidence.digest_bytes(raw), 'sha256:' + expected)
            (scripts / name).write_bytes(raw)
        if profile in attachments.REGISTRY_DIGESTS:
            digest = attachments.REGISTRY_DIGESTS[profile]
            asset = archive.read(digest + '.json')
            test.assertEqual(evidence.digest_bytes(asset), 'sha256:' + digest)
            registry = tooling / '.github/evals/custom-metrics.json'
            registry.parent.mkdir()
            registry.write_bytes(asset)
    return scripts


# Construct synthetic saved envelopes with the original public code, not a provider.
MAKE = r'''
import sys, json
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
import skill_review as r
p=json.loads(sys.stdin.buffer.read())
c=r.prepare([Path(x) for x in p['inputs']],Path(p['analysis']),p['skill'],p['record_id'],
    **{k:Path(p[k]) if p[k] else None for k in ('source','support','selection')})
v=r.make_review(p['judgment'],c,r.ModelConfig(**p['config']),
    r.Usage(preflight_input_tokens=1000,input_tokens=1000,output_tokens=500,total_tokens=1500))
d=Path(p['destination']);d.mkdir()
(d/'skill-review.json').write_bytes(r.evidence.encoded(v))
(d/'skill-review.md').write_bytes(r.render_review(v,c))
'''


class AttachmentTests(unittest.TestCase):
    bundle = review_fixtures.ReviewTests.bundle

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.clock = patch.object(evidence, 'utc_now', wraps=evidence.utc_now)
        self.clock.start(); self.addCleanup(self.clock.stop)

    def fixture(self, profile='current-v2', category=None, *, unmeasured=False):
        context = (review_fixtures.ReviewTests.gh_control(self) if unmeasured else
                   review_fixtures.ReviewTests.control(self))
        args = self.gh_args if unmeasured else self.args
        opts = dict(zip(args[::2], args[1::2]))
        # Every profile names frozen reviewed bytes, including the one named current-v2.
        # Presentation changes must not silently relabel the checkout as that validator.
        tooling = self.root / 'tooling'
        scripts = frozen_tooling(self, tooling, profile)
        body = judgment(context, category=category)
        if unmeasured:
            body['assessment'].update(tested_benefit='Not measured; configuration is not observed benefit.',
                tested_harm='Unknown without recorded outcomes.', interpretation='Retain the upstream skill; inspect evidence gaps.',
                uncertainty='Expected cases do not establish completed trials or successful execution.')
            for scope in (body['assessment'], *body['recommendations']):
                scope['sufficiency']['behavioral_scope'] = 'No measured trials supplied.'
            for recommendation in body['recommendations']:
                recommendation.update(scope='Request exact retained results from the overlay owner.',
                    expected_benefit='Establish what evidence is available before proposing changes.')
        request = {'inputs': [opts['--input']], 'analysis': opts['--analysis'], 'skill': opts['--skill'],
                   'record_id': opts['--record-id'], 'source': opts.get('--source'), 'support': opts.get('--support'),
                   'selection': opts.get('--selection'), 'judgment': body, 'config': CONFIG,
                   'destination': str(self.root / 'saved')}
        result = subprocess.run([sys.executable, '-I', '-B', '-c', MAKE, str(tooling / '.github/scripts')],
            input=evidence.encoded(request), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        saved = self.root / 'saved/skill-review.json'
        spec = {'schema_version': 1, 'profile': profile, 'tooling': str(tooling),
                'skill': request['skill'], 'record_id': request['record_id'], 'review': str(saved),
                'review_digest': evidence.digest_bytes(saved.read_bytes()),
                'markdown_digest': evidence.digest_bytes(saved.with_suffix('.md').read_bytes()),
                'inputs': request['inputs'], 'analysis': request['analysis'], 'source': request['source'],
                'support': request['support'], 'selection': request['selection'], 'assessments': []}
        self.path = self.root / 'attachment.json'; write(self.path, spec)
        self.spec = spec
        self.captured = analysis.capture_inputs([Path(opts['--input'])])
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
                self.assertEqual(item['report']['provenance']['implementation_digest'], evidence.identity(implementation))
                self.assertEqual(item['record_id'], self.spec['record_id'])
                output = report.render_report(self.result, self.captured, reviews=validated).decode()
                self.assertIn('Model interpretation', output)
                self.assertIn('No recommendations supplied', output)
                self.assertIn('not_quality_qualified', output)
                self.assertNotIn(str(self.root), output)

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

    def test_overview_exposes_proposed_action_and_separate_assessments(self):
        self.fixture('gh-89f46f0', category='investigate', unmeasured=True)
        self.supplied()
        self.supplied(verdict='Substantive pass; no numeric score assigned', scored=False, suffix='unscored')
        output = report.render_report(self.result, self.captured, reviews=self.load()).decode()
        overview = output.split('<section class="overview"', 1)[1].split('</section>', 1)[0]
        for value in ('Analyst conclusions and recommended actions', 'model interpretation',
                      'Request exact retained results from the overlay owner.', 'Independent AI assessment (supplied)',
                      'Synthetic ChatGPT assessor', '9 out of 10', 'Substantive pass; no numeric score assigned',
                      'Numeric score not assigned', 'Not quality qualified',
                      'Authenticated human approval is not established'):
            self.assertIn(value, overview)
        self.assertLess(output.index('Analyst conclusion:</strong>'), output.index('<h3>Behavioral run:'))
        self.assertIn('gh · analyst conclusions, proposed actions and citations', overview)

    def test_assessment_labels_scores_and_original_fields_match_overview_and_detail(self):
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
        overview = output.split('<section class="overview"', 1)[1].split('</section>', 1)[0]
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
        with patch.object(attachments.importlib.metadata, 'version', return_value='unreviewed'):
            with self.assertRaises(ValueError): self.load()
        self.spec['command'] = 'never execute descriptor commands'; write(self.path, self.spec)
        with self.assertRaises(ValueError): self.load()

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
        prefix = attachments.RUNNER.split('import skill_review as review')[0]
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
