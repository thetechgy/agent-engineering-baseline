"""One bounded, credential-free replay through the existing isolated native verifier."""
import hashlib,json,os,shutil,subprocess,sys,uuid
from pathlib import Path
import admission_validation,prepared
import run as trial
from handoff import no_credentials

HERE=Path(__file__).parent
SUPPORT=trial.ROOT/'.github/evals/powershell-pester-6/support'
IMAGE='direct-harbor-verifier:templates-v2'
ORIGINAL='direct-harbor-verifier:live'

def read(path):return json.loads(path.read_text())
def call(args,**kwargs):return subprocess.run(args,check=True,timeout=kwargs.pop('timeout',120),**kwargs)
def digest(path):return prepared.digest(path)

def download_submission(config,root):
    source=config['submission']
    metadata=prepared.download_artifact(source,root,members={'metadata.json','Subject.Tests.ps1'},limit=128*1024,require_success=False)
    candidate=root/'Subject.Tests.ps1';record=read(root/'metadata.json')
    assert candidate.stat().st_size==source['file_size'] and digest(candidate)==source['file_sha256']
    assert record['identity']==source['identity'] and record['sha256']==source['file_sha256'] and record['size']==source['file_size']
    assert record['declared_output']=='/workspace/output/Subject.Tests.ps1' and record['kind']=='agent_submission'
    assert set(record['boundary_sha256'].values())=={source['file_sha256']}
    assert record['checks']=={'regular_single_link':True,'credential_scan':'passed','protected_content_scan':'passed'}
    candidate.chmod(0o444)
    return candidate,{'source':source,'artifact':{k:metadata[k] for k in ('id','digest','size_in_bytes','expires_at')},'download_verified':True,'metadata':record}

def load_original(config,root):
    source=config['prepared_source'];bundle=root/'original-bundle'
    metadata=prepared.download_artifact(source,bundle)
    original=root/'qualified-source'
    call(['git','worktree','add','--detach',str(original),source['commit']])
    who={'repository':prepared.REPOSITORY,'branch':prepared.BRANCH,'commit':source['commit'],
         'run_id':str(source['run_id']),'run_attempt':1,'allocation_id':None}
    # Verify using the producer's complete experiment inputs and original code.
    # The corrected experiment cannot and must not pass as the old experiment.
    program="import sys,json;from pathlib import Path;sys.path.insert(0,sys.argv[1]);import prepared;prepared.verify(Path(sys.argv[2]),sys.argv[3],json.loads(sys.argv[4]));print('Original experiment, archives and task members verified')"
    call([sys.executable,'-c',program,str(original/'.github/trials/direct-harbor'),str(bundle),source['manifest_sha256'],json.dumps(who)],cwd=original)
    manifest=read(bundle/'manifest.json')
    assert manifest['experiment']!=prepared.experiment(), 'Policy v2 must have a distinct experiment identity'
    call(['docker','image','load','--input',str(bundle/'images.tar')],timeout=240)
    assert {tag:prepared.image_id(tag) for tag in manifest['images']}==manifest['images']
    return manifest,{'source':source,'artifact':{k:metadata[k] for k in ('id','digest','size_in_bytes','expires_at')},'verified_against_original_checkout':True,'original_experiment_sha256':manifest['experiment']['sha256']}

def grade(image,candidate,root,label):
    """Candidate execution occurs only behind the unchanged grader worker boundary."""
    name='retrospective-'+uuid.uuid4().hex;output=root/'public'/label;output.mkdir(parents=True)
    record={'image':image,'image_id':prepared.image_id(image),'submission_sha256':digest(candidate),'inference':False,'complete':False}
    try:
        call(['docker','create','--name',name,'--network','none','--security-opt','no-new-privileges:true',
              '--cpus','2','--memory','2g','--pids-limit','256','--env','PESTER_ADMISSION_DIAGNOSTICS=1',
              '--entrypoint','/bin/bash',image,'/tests/test.sh'],capture_output=True)
        inspect=json.loads(subprocess.check_output(['docker','inspect',name]))[0]
        assert inspect['HostConfig']['NetworkMode']=='none' and not inspect['Mounts'] and not inspect['HostConfig']['Privileged']
        record['boundary']={'network':'none','host_mounts':False,'no_new_privileges':True,'cpus':2,'memory_mb':2048,'pids':256,
                            'worker_uid':53001,'worker_checks':'unchanged grader requires immutable inputs, dropped privileges/capabilities and inaccessible protected verifier files'}
        call(['docker','cp',str(candidate),name+':/workspace/output/Subject.Tests.ps1'])
        process=subprocess.run(['docker','start','--attach',name],capture_output=True,timeout=260)
        record['process_exit']=process.returncode
        for filename in ('skill_evaluator_reward.json','reward.json'):
            call(['docker','cp',name+':/logs/verifier/'+filename,str(output/filename)],capture_output=True)
        # Verify the executed candidate after collection without publishing another copy.
        returned=root/(label+'-returned.ps1')
        call(['docker','cp',name+':/workspace/output/Subject.Tests.ps1',str(returned)],capture_output=True)
        assert digest(returned)==record['submission_sha256']==digest(candidate)
        returned.unlink();record['submission_unchanged']=True
        sidecar=read(output/'skill_evaluator_reward.json')
        record.update(outcome=sidecar['details']['outcome'],evaluation_status=sidecar['evaluation_status'])
        assert process.returncode==0
        record['complete']=True
    except Exception as exc:
        record['failure_type']=type(exc).__name__
    finally:
        removal=subprocess.run(['docker','rm','--force',name],capture_output=True,timeout=30)
        record['container_removed']=removal.returncode==0 or b'No such container' in removal.stderr
        record['complete']=record['complete'] and record['container_removed']
        trial.write(output/'replay.json',record)
    return record

def policy_inputs(config,root):
    context=root/'layer';context.mkdir()
    paths=['.github/evals/powershell-pester-6/support/Runner.ps1',
           *['.github/evals/powershell-pester-6/support/cases/'+case+'/profile.json' for case in ('pester-001','pester-002','pester-003','pester-004')]]
    identities={}
    for relative in paths:
        original=subprocess.check_output(['git','show',config['original_attempt_commit']+':'+relative])
        current=(trial.ROOT/relative).read_bytes()
        identities[relative]={'original':hashlib.sha256(original).hexdigest(),'corrected':hashlib.sha256(current).hexdigest()}
        if relative.endswith('profile.json'):
            old=json.loads(original);new=json.loads(current)
            assert old=={k:v for k,v in new.items() if k not in ('template_fields','admission_policy_version')}, 'Non-template profile policy changed'
    # Correctness implementation and worker isolation must remain byte-identical.
    fixed=[trial.ROOT/'.github/evals/powershell-pester-6/evals/grader.py',SUPPORT/'test.sh',
           *[p for p in (SUPPORT/'cases').rglob('*') if p.is_file() and ('reference' in p.parts or 'mutants' in p.parts or p.suffix=='.ps1' and 'input' in p.parts)]]
    correctness={}
    for path in fixed:
        relative=path.relative_to(trial.ROOT).as_posix()
        old=subprocess.check_output(['git','show',config['original_attempt_commit']+':'+relative])
        assert old==path.read_bytes(), 'Correctness or isolation input changed'
        correctness[relative]=digest(path)
    shutil.copyfile(SUPPORT/'Runner.ps1',context/'Runner.ps1')
    shutil.copyfile(SUPPORT/'cases/pester-002/profile.json',context/'profile.json')
    shutil.copyfile(SUPPORT/'qualification/pester-002/templates.Tests.ps1',context/'templates.Tests.ps1')
    shutil.copyfile(HERE/'template_checks.py',context/'template_checks.py')
    for case in ('pester-001','pester-002','pester-003','pester-004'):
        (context/'profiles'/case).mkdir(parents=True)
        shutil.copyfile(SUPPORT/'cases'/case/'profile.json',context/'profiles'/case/'profile.json')
    (context/'Dockerfile').write_text('FROM '+ORIGINAL+'\nCOPY Runner.ps1 /tests/Runner.ps1\nCOPY profile.json /tests/case/profile.json\nCOPY templates.Tests.ps1 /tests/admission-fixtures/templates.Tests.ps1\nCOPY template_checks.py /tests/template_checks.py\nCOPY profiles/ /tests/template-profiles/\n')
    return context,identities,correctness

def parser_checks(root):
    name='template-parser-'+uuid.uuid4().hex
    result={'passed':False}
    try:
        p=subprocess.run(['docker','run','--name',name,'--network','none','--read-only','--tmpfs','/tmp:rw,nosuid,nodev,size=128m',
            '--cap-drop','ALL','--security-opt','no-new-privileges:true','--cpus','2','--memory','2g','--pids-limit','256',
            '--entrypoint','python3',IMAGE,'-I','/tests/template_checks.py','/opt/microsoft/powershell/7/pwsh',
            '/tests/Runner.ps1','/tests/template-profiles','/tests/admission-fixtures'],capture_output=True,timeout=150)
        assert len(p.stdout)<32768
        result=json.loads(p.stdout);assert result['candidate_execution'] is False and result['inference'] is False
        result['passed']=result['passed'] and p.returncode==0
    finally:
        cleanup=subprocess.run(['docker','rm','--force',name],capture_output=True,timeout=30)
        result['container_removed']=cleanup.returncode==0 or b'No such container' in cleanup.stderr
        result['passed']=result['passed'] and result['container_removed']
        trial.write(root/'public/template-controls.json',result)
    return result

def main(root,report):
    no_credentials();config=read(HERE/'retrospective.json');launch=read(HERE/'launch.json')
    assert launch['phase']=='retrospective' and launch['paid_attempts_used']==7 and launch['paid_attempts_reserved']==0 and launch['allocation']['state']=='closed'
    assert os.environ['GITHUB_REPOSITORY']==prepared.REPOSITORY and os.environ['GITHUB_REF']==prepared.BRANCH
    assert os.environ['GITHUB_EVENT_NAME']=='push' and os.environ['GITHUB_RUN_ATTEMPT']=='1'
    assert str(config['workflow_run_number'])==os.environ['GITHUB_RUN_NUMBER']
    assert config['limit']==2 and config['attempt'] in (1,2)
    assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==os.environ['GITHUB_SHA']
    root.mkdir(parents=True,exist_ok=False)
    evidence={'kind':'retrospective_template_policy_v2','attempt':config['attempt'],'limit':2,'passed':False,
        'commit':os.environ['GITHUB_SHA'],'run_id':os.environ['GITHUB_RUN_ID'],'inference':False,'model_judge':False,'new_reservations':0,
        'campaign_attempts':7,'recovery_attempts':4,'policy_version':2,'original_attempt_commit':config['original_attempt_commit'],'controls':[]}
    try:
        evidence['stage']='submission_download'
        candidate,evidence['submission']=download_submission(config,root/'submission')
        evidence['stage']='original_experiment_verification_and_load'
        manifest,evidence['original_preparation']=load_original(config,root)
        evidence['original_image_id']=manifest['images'][ORIGINAL]
        context,evidence['policy_inputs'],evidence['unchanged_correctness_inputs']=policy_inputs(config,root)
        for relative in ('Runner.ps1','case/profile.json'):
            key='.github/evals/powershell-pester-6/support/'+('Runner.ps1' if relative=='Runner.ps1' else 'cases/pester-002/profile.json')
            assert manifest['members']['tasks/current/tests/'+relative]['sha256']==evidence['policy_inputs'][key]['original']
        evidence['stage']='original_policy_replay'
        evidence['original_replay']=grade(ORIGINAL,candidate,root,'original-replay')
        expected={'classification':'unsupported','code':'admission','admission_rule':'block_name_template','admission_diagnostic':{'ast_kind':'CommandAst','column':9,'line':23}}
        assert evidence['original_replay']['complete'] and evidence['original_replay']['outcome']==expected
        evidence['stage']='corrected_verifier_layer_build'
        call(['docker','build','--network=none','--pull=false','--progress=plain','-t',IMAGE,str(context)],timeout=240)
        evidence['corrected_image_id']=prepared.image_id(IMAGE)
        assert evidence['corrected_image_id']!=evidence['original_image_id']
        evidence['corrected_experiment']=prepared.experiment()['sha256']
        evidence['stage']='parser_contract_controls'
        evidence['parser_controls']=parser_checks(root);assert evidence['parser_controls']['passed']
        evidence['stage']='native_regression_controls'
        admission_validation.IMAGE=IMAGE
        evidence['controls']=[admission_validation.control(root,kind) for kind in ('good','weak','unsupported','runner_error','templates')]
        assert all(c['passed'] for c in evidence['controls'])
        evidence['stage']='corrected_policy_replay'
        evidence['corrected_replay']=grade(IMAGE,candidate,root,'corrected-replay')
        replay=evidence['corrected_replay'];assert replay['complete']
        assert replay['evaluation_status']=='complete' and replay['outcome']['classification'] in ('passed','failed')
        assert replay['outcome']['powershell_version']=='7.6.9' and replay['outcome']['pester_version']=='6.2.0'
        assert replay['outcome']['mutants_executed']==2 and replay['submission_unchanged']
        evidence['remaining_containers']={tag:subprocess.check_output(['docker','ps','--all','--filter','ancestor='+tag,'--quiet'],text=True).split() for tag in (ORIGINAL,IMAGE)}
        assert not any(evidence['remaining_containers'].values())
        evidence['container_disposal_verified']=True
        evidence['stage']='corrected_image_retention'
        export=root/'corrected-verifier';export.mkdir()
        archive=export/'verifier.tar';call(['docker','image','save','--output',str(archive),IMAGE],timeout=180)
        evidence['image_archive']={'sha256':digest(archive),'size':archive.stat().st_size,'retention_days':7}
        evidence['build_inputs']=prepared.files(context)
        evidence['future_input_change']={'execution_profile_sha256':digest(SUPPORT/'EXECUTION-PROFILE.md'),'old_agent_documentation_retained_for_attempt_seven':True,
            'prior_full_image_bundle_compatible_with_corrected_experiment':False,'future_pair_requires_matching_agent_documentation_and_task_preparation':True}
        evidence['passed']=True
        evidence['stage']='qualified'
        trial.write(export/'manifest.json',evidence)
    except Exception as exc:
        from diagnostics import sanitize
        evidence['failure']={'type':type(exc).__name__,'message':sanitize(str(exc))}
    finally:
        trial.write(root/'public/retrospective.json',evidence)
        shutil.copytree(HERE/'results',report)
        data=read(report/'results.json');data['retrospective_evaluation']=evidence
        data['state']='retrospective_qualification_complete' if evidence['passed'] else 'retrospective_qualification_failed'
        data['decision']=('Credential-free retrospective grading is qualified. Inspect the separate native result below; the original attempt remains unsupported/unmeasured and skill benefit remains unmeasured.' if evidence['passed'] else 'Credential-free retrospective qualification failed. Preserve the original outcome; inspect the retained failure before another bounded correction.')
        trial.write(report/'retrospective-evaluation.json',evidence)
        trial.report(report,data)
    print(json.dumps({'passed':evidence['passed'],'original':evidence.get('original_replay',{}).get('outcome'),
        'retrospective':evidence.get('corrected_replay',{}).get('outcome'),'failure':evidence.get('failure'),'new_reservations':0}),flush=True)
    return 0 if evidence['passed'] else 1

if __name__=='__main__':raise SystemExit(main(*(Path(x).resolve() for x in sys.argv[1:3])))
