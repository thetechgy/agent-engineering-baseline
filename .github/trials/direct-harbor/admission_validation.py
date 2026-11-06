"""Fixed Docker validation of this diagnostic patch, not another paid trial."""
import json,os,shutil,subprocess,sys,uuid
from pathlib import Path
import run as trial
from live import admission_preflight,stage_admission_checks
from handoff import no_credentials

IMAGE='direct-harbor-verifier:admission'

def control(root,kind):
    name='admission-control-'+uuid.uuid4().hex
    output=root/'public'/kind;output.mkdir(parents=True)
    record={'control':kind,'kind':'credential_free_verifier_control','inference':False,'passed':False}
    script=r"""import os,shutil
from pathlib import Path
kind=os.environ['TRIAL_CONTROL']
Path('/logs/verifier').mkdir(parents=True,exist_ok=True)
if kind=='unsupported':
 Path('/workspace/output/Subject.Tests.ps1').write_text("Write-Output 'DIAGNOSTIC_CONTENT_MUST_NOT_LEAK'")
else:
 shutil.copyfile('/tests/admission-fixtures/'+('weak' if kind=='weak' else 'classic')+'.Tests.ps1','/workspace/output/Subject.Tests.ps1')
if kind=='runner_error':
 p=Path('/tests/Runner.ps1');s=p.read_text();marker='        $__peNodes = @('
 assert s.count(marker)==1
 p.write_text(s.replace(marker,"        throw 'PRIVATE_INTERNAL_FAILURE'\n"+marker,1))
os.execv('/bin/bash',['bash','/tests/test.sh'])
"""
    try:
        completed=subprocess.run(['docker','run','--name',name,'--network','none',
            '--security-opt','no-new-privileges:true','--cpus','2','--memory','2g','--pids-limit','256',
            '--env','TRIAL_CONTROL='+kind,'--env','PESTER_ADMISSION_DIAGNOSTICS=1',
            '--entrypoint','python3',IMAGE,'-I','-c',script],capture_output=True,timeout=260)
        record['process_exit']=completed.returncode
        # Retain only the grader's fixed metadata, never submissions or stdout.
        for filename in ('skill_evaluator_reward.json','reward.json'):
            subprocess.run(['docker','cp',name+':/logs/verifier/'+filename,str(output/filename)],check=True,capture_output=True,timeout=20)
        sidecar=json.loads((output/'skill_evaluator_reward.json').read_text());observed=sidecar['details']['outcome']
        record.update(outcome=observed,evaluation_status=sidecar['evaluation_status'])
        assert completed.returncode==0
        if kind in ('good','weak'):
            assert observed['classification']==('passed' if kind=='good' else 'failed')
            assert observed['reference_pass']==1 and observed['mutants_executed']==2
            assert observed['mutants_detected']==(2 if kind=='good' else 0)
        elif kind=='unsupported':
            assert observed['classification']=='unsupported' and observed['admission_rule']=='command_not_allowed'
            assert observed['admission_diagnostic']=={'ast_kind':'CommandAst','line':1,'column':1}
            assert sidecar['evaluation_status']=='failed'
        else:
            assert observed=={'classification':'infrastructure_error','code':'admission_runner'}
            assert sidecar['evaluation_status']=='failed'
        assert 'DIAGNOSTIC_CONTENT_MUST_NOT_LEAK' not in json.dumps(record)
        assert 'PRIVATE_INTERNAL_FAILURE' not in json.dumps(record)
        record['passed']=True
    except Exception as exc:
        record['failure_type']=type(exc).__name__
    finally:
        try:
            cleanup=subprocess.run(['docker','rm','--force',name],capture_output=True,timeout=20)
            record['container_removed']=cleanup.returncode==0 or b'No such container' in cleanup.stderr
        except (OSError,subprocess.TimeoutExpired):record['container_removed']=False
        record['passed']=record['passed'] and record['container_removed']
        trial.write(output/'control.json',record)
    print(json.dumps(record),flush=True)
    return record

def main(root,report):
    no_credentials();root.mkdir(parents=True,exist_ok=False)
    evidence={'kind':'credential_free_admission_validation','inference':False,'passed':False,
        'commit':os.environ.get('GITHUB_SHA'),'run_id':os.environ.get('GITHUB_RUN_ID'),
        'baseline_commit':'924a1e5b4ddb56c71cd032e68a6b9dc53c5ae01b',
        'policy_fingerprint':'03b6465e9395a6cc458daaa392de6d22fba30dd9eda10a9f355871039e8001e6','controls':[]}
    try:
        native,_=trial.stage(root/'stage',admission_diagnostics=True);task=native/'pester-002'
        stage_admission_checks(task)
        subprocess.run(['docker','build','--progress=plain','-t',IMAGE,str(task/'tests')],check=True,timeout=600)
        evidence['image_id']=subprocess.check_output(['docker','image','inspect','--format','{{.Id}}',IMAGE],text=True).strip()
        evidence['parser_preflight']=admission_preflight(IMAGE,root/'public/admission-preflight.json')
        evidence['controls']=[control(root,k) for k in ('good','weak','unsupported','runner_error')]
        evidence['passed']=all(c['passed'] for c in evidence['controls'])
    except Exception as exc:
        evidence['failure_type']=type(exc).__name__
    finally:
        data=None
        try:
            shutil.copytree(Path(__file__).with_name('results'),report)
            data=json.loads((report/'results.json').read_text());data['admission_validation']=evidence
            data['state']='credential_free_admission_diagnostics_verified' if evidence['passed'] else 'admission_validation_failed'
            data['decision']=('Credential-free admission validation passed. Fixed diagnostics reach the report and known-good/weak grades are unchanged. Historical live outcomes remain unchanged; no inference occurred.' if evidence['passed'] else 'Credential-free admission validation failed. Inspect the retained diagnostic evidence; do not infer grading success.')
            trial.report(report,data)
            html=(report/'report.html').read_text()
            if evidence['passed']:assert 'command_not_allowed (CommandAst at 1:1)' in html and 'admission_runner' in html
        except Exception as exc:
            evidence.update(passed=False,code='report_validation',failure_type=type(exc).__name__)
            (report/'report.html').unlink(missing_ok=True)
            if data is not None:
                data.update(state='admission_validation_failed',decision='Report validation failed; no successful diagnostic validation is claimed.')
                trial.write(report/'results.json',data)
        finally:
            trial.write(root/'public/admission-validation.json',evidence)
            trial.write(report/'admission-validation.json',evidence)
    return 0 if evidence['passed'] else 1

if __name__=='__main__':raise SystemExit(main(*(Path(x).resolve() for x in sys.argv[1:3])))
