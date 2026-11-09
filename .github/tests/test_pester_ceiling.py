"""Exploratory candidate controls through existing task, grader and reward APIs."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from test_codex_effectiveness import ROOT, local_semantic_fixture, prospective_grader
import pester_evaluations as tasks
import skill_reports as reports

CANDIDATE = ROOT / '.github/evals/pester-ceiling'


class Candidate(unittest.TestCase):
    def test_original_task_wording_and_frozen_population_are_preserved(self):
        definition = reports.read_json(CANDIDATE / 'candidate.json')
        original = next(e for e in tasks.dataset(ROOT) if e['id'] == definition['source_case'])
        self.assertEqual((CANDIDATE / definition['prompt']).read_text(), original['prompt'] + '\n')
        self.assertNotIn(definition['id'], {e['id'] for e in tasks.dataset(ROOT)})
        self.assertEqual(set(definition['extra_mutants']), {'integer-result'})

    @unittest.skipUnless(os.environ.get('PESTER_EFFECTIVENESS_LOCAL_SEMANTICS') == '1',
                         'Optional pinned local Pester semantic check')
    def test_exploratory_controls_use_existing_grader_and_reward_sidecars(self):
        self.assertFalse(any(os.environ.get(k) for k in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'NVIDIA_API_KEY')))
        manifest = subprocess.check_output([os.environ.get('CI_PWSH', 'pwsh'), '-NoLogo', '-NoProfile', '-Command',
            '(Get-Module -ListAvailable Pester | Where-Object Version -EQ 6.2.0 | Select-Object -First 1).Path'],
            text=True).strip()
        self.assertTrue(manifest, 'Pinned Pester 6.2.0 required')
        definition = reports.read_json(CANDIDATE / 'candidate.json')
        grader = prospective_grader()
        with tempfile.TemporaryDirectory() as directory:
            scratch = Path(directory)
            bundle = tasks.stage(ROOT, scratch / 'bundle')
            task = bundle / 'evals/harbor' / definition['source_case']
            self.assertEqual((task / 'instruction.md').read_bytes(), (CANDIDATE / definition['prompt']).read_bytes())
            original = ROOT / tasks.OVERLAY / 'support/cases' / definition['source_case']
            for path in (original / 'input').iterdir():
                self.assertEqual((task / 'environment/input' / path.name).read_bytes(), path.read_bytes())
            files = {p.relative_to(task / 'tests/case').as_posix(): p.read_bytes()
                     for p in (task / 'tests/case').rglob('*') if p.is_file()}
            for name, source in definition['extra_mutants'].items():
                files[f'mutants/{name}.ps1'] = (CANDIDATE / source).read_bytes()
            variants = sorted(Path(k).stem for k in files if k.startswith('mutants/'))
            self.assertEqual(len(variants) + 1, grader.MAX_VARIANTS)
            evidence = Path(os.environ['PESTER_EFFECTIVENESS_EVIDENCE']) if os.environ.get('PESTER_EFFECTIVENESS_EVIDENCE') else scratch / 'evidence'
            evidence.mkdir(parents=True, exist_ok=False)
            reports.write_json(evidence / 'candidate.json', definition)
            for control in definition['controls']:
                with self.subTest(control=control['id']):
                    results = local_semantic_fixture((ROOT / control['file']).read_bytes(), files, manifest)
                    status, detail = grader.assess(results[0], results[1:])
                    target = evidence / control['id']
                    target.mkdir()
                    reports.write_json(target / 'entry.json', {
                        'id': definition['id'] + '-' + control['id'], 'grading_mode': 'custom_only'})
                    with patch.dict(os.environ, {'HARBOR_REWARD_JSON': str(target / 'reward.json')}):
                        grader.emit(target, status, detail)
                    reward = reports.read_json(target / 'custom_reward.json')
                    self.assertEqual(reward['details']['outcome'], {'classification': status, **detail})
                    self.assertEqual(status, control['outcome'], results)
                    if control['detections'] is not None:
                        self.assertEqual(detail['reference_pass'], 1)
                        self.assertEqual(dict(zip(variants, detail['variant_detections'])), control['detections'])
                    else:
                        self.assertNotIn('custom_metrics', reward)
                        self.assertEqual(reports.read_json(target / 'skill_evaluator_reward.json')['evaluation_status'], 'failed')
                    print(json.dumps({'exploratory_control': control['id'], 'outcome': status, **detail}))


if __name__ == '__main__':
    unittest.main()
