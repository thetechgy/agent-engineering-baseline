"""Actual authentication CLI coverage is mandatory in hosted preparation."""
import copy
import hashlib
import json
from importlib.metadata import version, PackageNotFoundError
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'.github/scripts'))
import campaign_authentication_qualification as qualification
import evaluation_campaign_protocol as protocol
from evaluation_campaign_selection import selected_task
import skill_reports as reports


class AuthenticationContracts(unittest.TestCase):
    def test_real_cli_and_receipt_artifact_round_trip_under_each_owning_runtime(self):
        try: owner = version('skillevaluator')
        except PackageNotFoundError: owner = None
        identities = {'0.9.0': 'gh-task-permission-v2', '0.8.0': 'boolean-effectiveness-v1'}
        if owner not in identities:
            self.skipTest('Pinned owning runtime required; hosted preparation runs the unskippable CLI qualifier')
        task = selected_task(identities[owner])
        with tempfile.TemporaryDirectory() as directory:
            proof = qualification.qualify(Path(directory)/'proof', task)
            qualification.validate(proof, task)
            self.assertEqual(set(proof['cases']), set(qualification.case_names(task)))
            self.assertFalse(proof['live_authority'])

    def test_registered_metadata_only_adapter_uses_the_same_setup_guard(self):
        task=selected_task('boolean-effectiveness-v1')
        with tempfile.TemporaryDirectory() as directory:
            qualification.run_case(Path(directory)/'positive', task, 'accepted')
            qualification.run_case(Path(directory)/'missing-owner', task, 'missing-dependency')

    def test_readiness_rejects_missing_incomplete_wrong_source_campaign_protocol_and_owner_proofs(self):
        task = selected_task('gh-task-permission-v2')
        valid = {**qualification.expected(task), 'complete': True, 'inference': False,
                 'cases': {name:'passed' for name in qualification.case_names(task)}}
        qualification.validate(valid, task)
        for key, value in [('complete', False), ('revision', '0'*40), ('campaign', 'gh-runtime-090-v1'),
                           ('protocol_digest', 'sha256:'+'0'*64), ('runtime', {}), ('cases', {}), ('live_authority', True)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                qualification.validate({**valid, key:value}, task)
        for key in valid:
            with self.assertRaises(ValueError): qualification.validate({k:v for k,v in valid.items() if k != key}, task)

    def test_source_successors_preserve_complete_pre_repair_registry(self):
        registry=json.loads((ROOT/'.github/evals/custom-metrics.json').read_text())
        registry['profiles']={k:v for k,v in registry['profiles'].items()
            if '-source-v24-' not in k and '-source-v28-' not in k and k not in ('pester-effectiveness-v31', 'pester-cli-pilot-retained-v19') and '-source-v27-' not in k and '-source-v26-' not in k and k not in ('pester-effectiveness-v30', 'pester-cli-pilot-retained-v18') and '-source-v25-' not in k and k != 'pester-effectiveness-v29'}
        added=[k for k in registry['profiles'] if any(f'-source-v{v}-' in k for v in (21,22,23))]
        self.assertEqual(len(added), 105)
        for key in added:
            number=next(v for v in (21,22,23) if f'-source-v{v}-' in key)
            previous=key.replace(f'-source-v{number}-', f'-source-v{number-1}-')
            new=registry['profiles'][key];old=registry['profiles'][previous]
            self.assertEqual({k:v for k,v in new.items() if k not in ('id','runtime_digest')},
                             {k:v for k,v in old.items() if k not in ('id','runtime_digest')})
            self.assertNotEqual(new['runtime_digest'],old['runtime_digest'])
        for key in added: del registry['profiles'][key]
        self.assertEqual(len(registry['profiles']),698)
        digest=hashlib.sha256(json.dumps(registry,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        self.assertEqual(digest, 'c94b40da0620cac5cd123fad4015eb0e60486e629ed6bb9210de02d895d095ce')

    def test_expired_authority_is_rejected_before_github_io(self):
        from datetime import datetime, timezone
        task=selected_task('gh-task-permission-v2')
        with patch.object(protocol, 'datetime') as clock:
            clock.now.return_value = datetime(2099,1,1,tzinfo=timezone.utc)
            clock.fromisoformat.side_effect = datetime.fromisoformat
            with self.assertRaisesRegex(ValueError, 'authorization expired'):
                protocol.allocation('not-an-allocation', task)

    def test_workflow_uses_identical_setup_and_pinned_interpreter_before_any_test(self):
        import yaml
        workflow=yaml.safe_load((ROOT/'.github/workflows/evaluation-campaign.yml').read_text())
        jobs=workflow['jobs'];steps=jobs['qualify']['steps']
        for job in ('qualify','authenticate'):
            commands='\n'.join(s.get('run','') for s in jobs[job]['steps'])
            self.assertIn('bash .github/scripts/setup-campaign-authentication.sh "$CAMPAIGN_ID"', commands)
        commands='\n'.join(s.get('run','') for s in jobs['authenticate']['steps'])
        self.assertIn('"$SKILL_AUTHENTICATION_PYTHON" -B .github/scripts/evaluation_campaign_selection.py authenticate',commands)
        self.assertNotIn('python3 -B .github/scripts/evaluation_campaign_selection.py authenticate', commands)
        qualifier=next(i for i,s in enumerate(steps) if 'campaign_authentication_qualification.py' in s.get('run',''))
        first_test=next(i for i,s in enumerate(steps) if 'unittest' in s.get('run',''))
        self.assertLess(qualifier, first_test)
        self.assertIn('--authentication-qualification', '\n'.join(s.get('run','') for s in steps))
        preparation_upload=next(s for s in steps if s.get('id')=='preparation-artifact')
        self.assertTrue(all(path.startswith('${{ runner.temp }}/reusable-evaluation/')
                            for path in preparation_upload['with']['path'].splitlines()))
        proof_upload=next(s for s in steps if s.get('name')=='Retain authentication qualification without authorization')
        self.assertEqual(proof_upload['with']['name'], 'campaign-authentication-qualification-${{ github.run_attempt }}')
        upload=next(s for s in jobs['authenticate']['steps'] if s.get('name')=='Retain authentication failure diagnosis without authorization')
        self.assertEqual(upload['if'], 'failure()')
        self.assertNotEqual(upload['with']['name'], 'campaign-authenticated-${{ github.run_attempt }}')


if __name__ == '__main__': unittest.main()
