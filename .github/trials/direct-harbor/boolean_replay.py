"""Credential-free policy qualification and exact-byte replay of attempts eight/nine."""
import hashlib,json,os,shutil,subprocess,sys,uuid
from datetime import datetime,timezone,timedelta
from pathlib import Path
import admission_validation,boolean_checks,prepared,retrospective
from image_contents import DockerOperations,inspect_image
from handoff import no_credentials
import run as trial

HERE=Path(__file__).parent;SUPPORT=retrospective.SUPPORT
BASE='direct-harbor-verifier:templates-v2';IMAGE='direct-harbor-verifier:assertions-v3'
read=retrospective.read;digest=prepared.digest

def window(config):
    start=datetime.fromisoformat(config['window']['started_at'].replace('Z','+00:00'))
    end=datetime.fromisoformat(config['window']['deadline'].replace('Z','+00:00'))
    assert end-start==timedelta(minutes=90) and start<=datetime.now(timezone.utc)<end,'Qualification window expired'

def load_base(config,root,ops):
    source=config['prepared_source'];bundle=root/'base'
    artifact=prepared.download_artifact(source,bundle,members={'manifest.json','verifier.tar'},limit=2*1024**3)
    assert digest(bundle/'manifest.json')==source['manifest_sha256']
    manifest=read(bundle/'manifest.json')
    assert manifest['passed'] and manifest['policy_version']==2 and manifest['commit']==source['commit'] and int(manifest['run_id'])==source['run_id']
    assert manifest['corrected_image_id']==source['image_id']
    assert digest(bundle/'verifier.tar')==manifest['image_archive']['sha256'] and (bundle/'verifier.tar').stat().st_size==manifest['image_archive']['size']
    original=config['original_attempt_commit']
    for relative,item in manifest['policy_inputs'].items():
        assert hashlib.sha256(subprocess.check_output(['git','show',original+':'+relative])).hexdigest()==item['corrected']
    for relative,sha in manifest['unchanged_correctness_inputs'].items():
        assert digest(trial.ROOT/relative)==sha
        assert hashlib.sha256(subprocess.check_output(['git','show',original+':'+relative])).hexdigest()==sha
    ops.run('load_verified_base',['docker','image','load','--input',str(bundle/'verifier.tar')],timeout=240)
    assert prepared.image_id(BASE)==source['image_id']
    expected={}
    for target,relative in [('Runner.ps1','.github/evals/powershell-pester-6/support/Runner.ps1'),('case/profile.json','.github/evals/powershell-pester-6/support/cases/pester-002/profile.json'),('verifier/grader.py','.github/evals/powershell-pester-6/evals/grader.py')]:
        b=subprocess.check_output(['git','show',original+':'+relative]);expected[target]={'sha256':hashlib.sha256(b).hexdigest(),'size':len(b)}
    contents=inspect_image(BASE,'/tests',expected,root/'public/base-contents.json',exact=False)
    return {'source':source,'artifact':artifact,'manifest_sha256':digest(bundle/'manifest.json'),'manifest':manifest,'contents':contents}

def layer(config,root,ops):
    context=root/'layer';context.mkdir();identities={}
    for filename in ('Runner.ps1',):shutil.copyfile(SUPPORT/filename,context/filename)
    shutil.copyfile(SUPPORT/'cases/pester-002/profile.json',context/'profile.json')
    for case in ('pester-001','pester-002','pester-003','pester-004'):
        path=SUPPORT/'cases'/case/'profile.json';old=json.loads(subprocess.check_output(['git','show',config['original_attempt_commit']+':'+path.relative_to(trial.ROOT).as_posix()]));new=read(path)
        assert old=={**new,'admission_policy_version':2},'Only profile version may change'
        (context/'profiles'/case).mkdir(parents=True);shutil.copyfile(path,context/'profiles'/case/'profile.json')
    for filename in ('boolean_checks.py','trace_verifier.py'):shutil.copyfile(HERE/filename,context/filename)
    (context/'Dockerfile').write_text('FROM '+BASE+'\nCOPY Runner.ps1 /tests/Runner.ps1\nCOPY profile.json /tests/case/profile.json\nCOPY profiles/ /tests/template-profiles/\nCOPY boolean_checks.py trace_verifier.py /tests/\n')
    before=json.loads(ops.run('base_layers',['docker','inspect',BASE]))[0]['RootFS']['Layers']
    ops.run('build_verifier_only',['docker','build','--network=none','--pull=false','--progress=plain','-t',IMAGE,str(context)],timeout=240)
    after=json.loads(ops.run('corrected_layers',['docker','inspect',IMAGE]))[0]['RootFS']['Layers'];assert after[:len(before)]==before
    for path in [SUPPORT/'Runner.ps1',SUPPORT/'EXECUTION-PROFILE.md',*[p for p in (SUPPORT/'cases').glob('*/profile.json')]]:
        relative=path.relative_to(trial.ROOT).as_posix();old=subprocess.check_output(['git','show',config['original_attempt_commit']+':'+relative]);identities[relative]={'original':hashlib.sha256(old).hexdigest(),'corrected':digest(path)}
    expected={target:{'size':(context/name).stat().st_size,'sha256':digest(context/name)} for target,name in [('Runner.ps1','Runner.ps1'),('case/profile.json','profile.json'),('trace_verifier.py','trace_verifier.py'),('boolean_checks.py','boolean_checks.py')]}
    proof=inspect_image(IMAGE,'/tests',expected,root/'public/corrected-contents.json',exact=False)
    return {'image_id':prepared.image_id(IMAGE),'build_inputs':prepared.files(context),'policy_inputs':identities,'base_layers_unchanged':True,'contents':proof}

def parsers(root,ops):
    results={}
    for label,args in [('boolean',['/tests/boolean_checks.py','/opt/microsoft/powershell/7/pwsh','/tests/Runner.ps1','/tests/case/profile.json']),('template',['/tests/template_checks.py','/opt/microsoft/powershell/7/pwsh','/tests/Runner.ps1','/tests/template-profiles','/tests/admission-fixtures']),('existing',['/tests/admission_checks.py','--pwsh','/opt/microsoft/powershell/7/pwsh','--runner','/tests/Runner.ps1','--profile','/tests/case/profile.json','--fixtures','/tests/admission-fixtures','--extended'])]:
        name='policy-parser-'+uuid.uuid4().hex
        try:
            program="import runpy,sys;sys.argv=sys.argv[1:]\ntry:runpy.run_path(sys.argv[0],run_name='__main__')\nexcept SystemExit:pass"
            raw=ops.run(label+'_parser',['docker','run','--name',name,'--network','none','--read-only','--tmpfs','/tmp:rw,nosuid,nodev,size=128m','--cap-drop','ALL','--security-opt','no-new-privileges:true','--cpus','2','--memory','2g','--pids-limit','256','--entrypoint','python3',IMAGE,'-I','-c',program,*args],timeout=180)
            results[label]=json.loads(raw);trial.write(root/'public'/(label+'-parser.json'),results[label]);assert results[label]['passed'] and results[label]['candidate_execution'] is False
        finally:ops.run(label+'_remove',['docker','rm','--force',name],cleanup=True)
    trial.write(root/'public/parser-controls.json',results);return results

def completed(record):
    assert record['complete'] and record['container_removed'] and record['submission_unchanged'],record
    assert record['evaluation_status']=='complete' and record['outcome']['classification'] in ('passed','failed'),record
    native=record['native_runs'];assert native['admission']['status']=='admitted' and len(native['runs'])==3
    assert all(r['result']['status']=='executed' and r['result']['version']=='6.2.0' and r['result']['powershell_version']=='7.6.9' for r in native['runs'])
    record['variant_outcomes']=[{'variant':r['variant'],'reference_passed':r['result']['failed']==0 if i==0 else None,'mutant_detected':(r['result']['failed']>0 and r['result']['assertion_failures']==r['result']['failed']) if i else None} for i,r in enumerate(native['runs'])]


def qualify(root,ops):
    results=[]
    for label,expressions,failed in [('boolean_correct',boolean_checks.PASS,0),('boolean_wrong',boolean_checks.FAIL,len(boolean_checks.FAIL))]:
        path=root/(label+'.Tests.ps1');path.write_text(boolean_checks.suite(expressions))
        row=retrospective.grade(IMAGE,path,root,label,trace=True);completed(row)
        assert row['outcome']['reference_pass']==int(failed==0)
        for item in row['native_runs']['runs']:
            r=item['result'];assert r['total']==len(expressions) and r['failed']==failed and r['assertion_failures']==failed
        row.update(control=label,expected_failed_tests=failed,passed=True);results.append(row);trial.write(root/'public/native-controls.json',results)
    admission_validation.IMAGE=IMAGE
    for kind in ('good','weak','unsupported','runner_error','templates'):
        row=admission_validation.control(root,kind);results.append(row);trial.write(root/'public/native-controls.json',results);assert row['passed']
    return results

def main(root,report):
    no_credentials();config=read(HERE/'boolean-replay.json');window(config);launch=read(HERE/'launch.json')
    assert launch['phase']=='boolean' and launch['paid_attempts_used']==9 and launch['paid_attempts_reserved']==0 and launch['allocation']['state']=='closed' and launch['paid_execution_enabled'] is False and launch['scheduling_stopped'] is True
    assert os.environ['GITHUB_REPOSITORY']==prepared.REPOSITORY and os.environ['GITHUB_REF']==prepared.BRANCH and os.environ['GITHUB_EVENT_NAME']=='push' and os.environ['GITHUB_RUN_ATTEMPT']=='1'
    root.mkdir(parents=True,exist_ok=False);ops=DockerOperations(root/'public/operations.json')
    evidence={'kind':'retrospective_boolean_policy_v3_pair','passed':False,'commit':os.environ['GITHUB_SHA'],'run_id':os.environ['GITHUB_RUN_ID'],'window':config['window'],'policy_version':3,'inference':False,'model_judge':False,'new_reservations':0,'campaign_attempts':9,'recovery_attempts':4,'original_attempt_commit':config['original_attempt_commit'],'original_live_run':42295570341,'submissions':{},'controls':[],'replays':{},'post_output_policy_change':True,'qualification_basis':config['qualification_basis'],'qualification_history':config.get('qualification_history',[])}
    try:
        evidence['stage']='download_and_verify'
        candidates={}
        for arm,source in config['submissions'].items():candidates[arm],evidence['submissions'][arm]=retrospective.download_submission({'submission':source},root/arm)
        evidence['base']=load_base(config,root,ops)
        evidence['stage']='original_absent_rejection'
        original=retrospective.grade(BASE,candidates['absent'],root,'original-absent');evidence['original_absent']=original
        assert original['complete'] and original['outcome']=={'classification':'unsupported','code':'admission','admission_rule':'assertion_parameter','admission_diagnostic':{'ast_kind':'CommandAst','line':70,'column':33}}
        window(config);evidence['stage']='verifier_layer'
        evidence['corrected']=layer(config,root,ops);assert evidence['corrected']['image_id']!=config['prepared_source']['image_id']
        evidence['stage']='independent_admission_and_native_controls'
        evidence['parser_controls']=parsers(root,ops);evidence['controls']=qualify(root,ops)
        for arm in ('current','absent'):
            window(config);evidence['stage']='replay_'+arm
            row=retrospective.grade(IMAGE,candidates[arm],root,'corrected-'+arm,trace=True);evidence['replays'][arm]=row;completed(row)
        evidence['stage']='disposal_and_retention'
        evidence['remaining_containers']={tag:ops.run('disposal_audit',['docker','ps','--all','--filter','ancestor='+tag,'--quiet']).decode().split() for tag in (BASE,IMAGE)}
        assert not any(evidence['remaining_containers'].values());evidence['container_disposal_verified']=True
        export=root/'corrected-verifier';export.mkdir();archive=export/'verifier.tar'
        ops.run('retain_corrected_verifier',['docker','image','save','--output',str(archive),IMAGE],timeout=180)
        evidence['created_at']=datetime.now(timezone.utc).isoformat();evidence['expires_at']=(datetime.now(timezone.utc)+timedelta(days=7)).isoformat()
        evidence['image_archive']={'sha256':digest(archive),'size':archive.stat().st_size,'retention_days':7}
        evidence['agent_images_built']=0;evidence['dependency_installs']=0;evidence['snapshot_downloads']=0
        evidence['historical_agent_documentation_unchanged']=True;evidence['future_agent_inputs_require_new_matching_manifests']=True
        evidence['passed']=True;evidence['stage']='qualified';trial.write(export/'manifest.json',evidence)
    except Exception as exc:
        from diagnostics import sanitize
        evidence['failure']={'type':type(exc).__name__,'message':sanitize(str(exc))}
    finally:
        trial.write(root/'public/boolean-replay.json',evidence)
        shutil.copytree(HERE/'results',report);data=read(report/'results.json');data['retrospective_pair']=evidence
        data['summary']='This separate retrospective pass changes admission after inspecting the outputs. Original live results and historical agent documentation are preserved; no model requests, judges, reservations or paid attempts occurred.'
        data['decision']='Credential-free retrospective pair qualification '+('passed' if evidence['passed'] else 'failed')+'. Original live grades remain unchanged; inspect the separate retrospective comparison.'
        trial.write(report/'retrospective-pair.json',evidence);trial.report(report,data)
    print(json.dumps({'passed':evidence['passed'],'stage':evidence['stage'],'outcomes':{k:v.get('outcome') for k,v in evidence['replays'].items()},'failure':evidence.get('failure')}));return 0 if evidence['passed'] else 1

if __name__=='__main__':raise SystemExit(main(*(Path(x).resolve() for x in sys.argv[1:3])))
