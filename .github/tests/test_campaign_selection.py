"""No-network identities exercise the actual future artifact/receipt boundary."""
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'.github/scripts'))
import evaluation_campaign_protocol as protocol
import evaluation_campaign_selection as selected
from codex_pilot_dispatch import REPO_ID, LIMIT
import skill_reports as reports

CAMPAIGNS = [f'pester-return-{case}-{variant}-{version}'
             for case,version in [('development','v1'),('transfer','v3')]
             for variant in ('current','candidate')]


class SelectionContracts(unittest.TestCase):
    def metadata(self, task, producer_index=1):
        producer = selected.registration(task)['producers'][producer_index]
        repo = {'id': REPO_ID, 'full_name': protocol.REPO}
        run = {'id':7000001, 'repository':repo, 'head_repository':repo, 'head_sha':protocol.revision(),
               'path':producer['workflow'], 'event':'pull_request', 'status':'completed', 'conclusion':'success', 'run_attempt':1}
        artifact = {'id':7000002, 'workflow_run':{'id':run['id'], 'repository_id':REPO_ID,
                    'head_repository_id':REPO_ID, 'head_sha':run['head_sha']},
                    'name':producer['artifact']+'-1', 'expired':False, 'size_in_bytes':1, 'digest':'sha256:'+'b'*64,
                    'expires_at':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()}
        return artifact, run

    def archive(self, root, task, *, mutate=None, producer_index=1):
        artifact,run = self.metadata(task,producer_index)
        internal = selected.location(task,artifact,run)
        proposal = copy.deepcopy(protocol.frozen(task))
        ready = {'complete':True, 'inference':False, 'revision':protocol.revision(),
                 'protocol_digest':proposal['protocol_digest'], 'authorized_live_attempts':0}
        proof = {**ready, 'scenarios':{name:{} for name in protocol.SCENARIOS}}
        files = {'frozen-proposal.json':proposal, 'preparation.json':ready, 'scheduler-qualification.json':proof}
        if mutate: mutate(files)
        archive = root/'fixture.zip'
        with zipfile.ZipFile(archive,'w') as bundle:
            for name,value in files.items(): bundle.writestr(internal+'/'+name,json.dumps(value))
            bundle.writestr(str(Path(internal).parent/'scenarios/complete/evidence/marker.json'),'{}')
        artifact.update(size_in_bytes=archive.stat().st_size,digest='sha256:'+hashlib.sha256(archive.read_bytes()).hexdigest())
        return archive,artifact,run

    def test_selection_rejects_shell_and_path_inputs_and_preserves_frozen_order(self):
        for bad in ('../boolean-effectiveness-v1', '/etc/passwd', '$(false)', 'pester-return-transfer-current-v2', 'unknown'):
            with self.assertRaises(ValueError): selected.selected_task(bad)
        for identity in CAMPAIGNS:
            task=selected.selected_task(identity)
            self.assertEqual(protocol.protocol(task)['id'],identity)
            self.assertEqual([row['variant'] for row in protocol.frozen(task)['schedule']],
                             [task.definition['variants'][0]['id'],'absent','absent',task.definition['variants'][0]['id'],task.definition['variants'][0]['id'],'absent'])
            self.assertIn('/'+('candidate' if '-candidate-' in identity else 'current')+'/',task.definition['source'])

    def test_all_four_admit_both_registered_layouts_to_the_same_live_consumer_path(self):
        for identity in CAMPAIGNS:
            task=selected.selected_task(identity)
            for index in (0,1):
                with self.subTest(identity=identity,producer=index), tempfile.TemporaryDirectory() as d:
                    root=Path(d);archive,artifact,run=self.archive(root,task,producer_index=index)
                    ref,internal=protocol.admit(archive,root/'downloaded',artifact,run,task)
                    self.assertEqual(ref,root/'downloaded/preparation/evidence')
                    self.assertTrue((ref.parent/'scenarios/complete/evidence/marker.json').is_file())
                    self.assertEqual(reports.read_json(ref/'frozen-proposal.json'),protocol.frozen(task))
                    self.assertEqual(internal,selected.location(task,artifact,run))

    def test_archive_and_preparation_mismatches_fail_before_receipt(self):
        task=selected.selected_task(CAMPAIGNS[0])
        mutations = [lambda f:f['frozen-proposal.json'].update(revision='0'*40),
                     lambda f:f['frozen-proposal.json'].update(protocol_digest='sha256:'+'0'*64),
                     lambda f:f['frozen-proposal.json']['definition'].update(id=CAMPAIGNS[1]),
                     lambda f:f['preparation.json'].update(complete=False),
                     lambda f:f['preparation.json'].update(authorized_live_attempts=6),
                     lambda f:f['scheduler-qualification.json'].update(scenarios={})]
        for mutate in mutations:
            with tempfile.TemporaryDirectory() as d:
                root=Path(d);archive,artifact,run=self.archive(root,task,mutate=mutate)
                with self.assertRaises(ValueError):protocol.admit(archive,root/'downloaded',artifact,run,task)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);archive,artifact,run=self.archive(root,task)
            with self.assertRaises(ValueError):protocol.admit(archive,root/'wrong-definition',artifact,run,selected.selected_task(CAMPAIGNS[1]))
            archive.write_bytes(archive.read_bytes()+b'corrupt')
            with self.assertRaisesRegex(ValueError,'digest mismatch'):protocol.admit(archive,root/'corrupt',artifact,run,task)

    def test_metadata_rejects_expired_wrong_producer_artifact_revision_and_attempt(self):
        task=selected.selected_task(CAMPAIGNS[0]);artifact,run=self.metadata(task)
        protocol.authenticate_metadata(artifact,run,protocol.revision(),REPO_ID,LIMIT,task=task)
        for key,value in [('expired',True),('expires_at','2000-01-01T00:00:00Z'),('name','pester-return-transfer-1'),('size_in_bytes',LIMIT+1)]:
            with self.assertRaises(ValueError):protocol.authenticate_metadata({**artifact,key:value},run,protocol.revision(),REPO_ID,LIMIT,task=task)
        for key,value in [('head_sha','0'*40),('path','.github/workflows/unreviewed.yml'),('conclusion','failure'),('run_attempt',2),('head_repository',{'id':1})]:
            with self.assertRaises(ValueError):protocol.authenticate_metadata(artifact,{**run,key:value},protocol.revision(),REPO_ID,LIMIT,task=task)

    def test_authenticate_uses_real_archive_admission_and_receipt_without_claiming_real_allocation(self):
        # APIs and archive transport are isolated fixtures. No actual dispatch,
        # allocation claim, protected environment or credential is contacted.
        import codex_pilot_dispatch as transport
        for identity in CAMPAIGNS:
            task=selected.selected_task(identity)
            with tempfile.TemporaryDirectory() as d:
                root=Path(d);archive,artifact,producer=self.archive(root,task)
                nonce='fixture_only_7000003'
                approval=f'campaign-{protocol.revision()}-{identity}-prep7000002-usd8-{nonce}'
                current={**producer,'id':7000003,'path':protocol.WORKFLOW,'display_title':'Evaluation campaign '+approval,
                         'run_attempt':1,'event':'workflow_dispatch'}
                def api(path):
                    return {'actions/runs/7000003':current, 'actions/runs/7000001':producer,
                            'actions/artifacts/7000002':artifact,
                            'actions/workflows/evaluation-campaign.yml/runs?event=workflow_dispatch&per_page=100&page=1':{'workflow_runs':[current]}}[path]
                original_run = protocol.subprocess.run
                def download(argv,**kwargs):
                    if argv[0] != 'gh': return original_run(argv,**kwargs)
                    self.assertEqual(argv,['gh','api',f'repos/{protocol.REPO}/actions/artifacts/7000002/zip'])
                    kwargs['stdout'].write(archive.read_bytes())
                env={'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':protocol.REPO,'GITHUB_EVENT_NAME':'workflow_dispatch',
                     'GITHUB_RUN_ATTEMPT':'1','GITHUB_RUN_ID':'7000003'}
                with patch.dict(os.environ,env), patch.object(transport,'api',side_effect=api), patch.object(protocol.subprocess,'run',side_effect=download):
                    reference=protocol.authenticate(root/'authentication',approval,task)
                    receipt=reports.read_json(reference/'dispatch-authentication.json')
                    protocol.validate_receipt(receipt,approval,task)
                    for key,value in [('definition',CAMPAIGNS[1]),('definition_digest','sha256:'+'0'*64),('selection_digest','sha256:'+'0'*64),
                                      ('revision','0'*40),('protocol_digest','sha256:'+'0'*64),('artifact','7000004'),('allocation','wrong'),('preparation_location','../evidence')]:
                        with self.assertRaises(ValueError):protocol.validate_receipt({**receipt,key:value},approval,task)
                    with self.assertRaises(ValueError):protocol.validate_receipt(receipt,approval+'other',task)
                    with patch.dict(os.environ,GITHUB_RUN_ATTEMPT='2'),self.assertRaises(ValueError):protocol.validate_receipt(receipt,approval,task)
                    protocol.first_dispatch([current],approval,str(current['id']))
                    with self.assertRaises(ValueError):protocol.first_dispatch([current,{**current,'id':7000004}],approval,'7000004')

    def test_workflow_uses_one_data_selection_for_all_four_boundaries(self):
        import yaml
        raw=(ROOT/'.github/workflows/evaluation-campaign.yml').read_text();workflow=yaml.safe_load(raw)
        for name in ('qualify','consume','authenticate','live'):
            commands='\n'.join(s.get('run','') for s in workflow['jobs'][name]['steps'])
            self.assertIn('--campaign "$CAMPAIGN_ID"',commands)
            self.assertNotIn('--definition .github/evals/campaigns/boolean-effectiveness-v1.json',commands)
        self.assertNotIn('${{ inputs.campaign }}',raw.split('run: |',1)[1])


if __name__=='__main__':unittest.main()
