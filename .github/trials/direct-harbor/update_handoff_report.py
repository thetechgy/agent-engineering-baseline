"""Append this bounded pass to the existing single report; never rescore history."""
import hashlib,json,os,shutil,sys
from pathlib import Path
import run as trial

def read(path):return json.loads(path.read_text()) if path.is_file() else None

def main(handoff,runtime,out):
    source=Path(__file__).with_name('results');shutil.copytree(source,out)
    data=read(out/'results.json');profile=read(Path(__file__).with_name('runtime-profile.json'))
    controls={kind:read(handoff/'public'/kind/'control.json') for kind in ('good','missing','rejected')}
    verification=read(runtime/'public/verification.json')
    runtime_results={mode:{name:read(runtime/'public'/mode/(name+'.json')) for name in ('diagnostic','configuration-load','effective-config','installation','boundary','container-policy','launch-diagnostics')} for mode in ('http','idle')}
    handoff_ok=all(r and r.get('passed') for r in controls.values())
    runtime_ok=bool(verification and verification.get('passed'))
    evidence={'kind':'credential_free_handoff_and_runtime_qualification','commit':os.environ.get('GITHUB_SHA'),'run_id':os.environ.get('GITHUB_RUN_ID'),
        'prior_diagnostic_run':{'run_id':42115972887,'commit':'ac5739807a54674365ae559954a78efa850ab5a7','classification':'environment_build_failure','cause':'Pinned Debian security snapshot index returned HTTP 503. Both builds stopped before controls or CLI probes; partial report and runtime metadata were retained.','correction':'Added supported Acquire::https::No-Cache=true; signed snapshot and package hashes remain unchanged. Subsequent fetch succeeded, but cache causality versus transient service recovery is unproven.'},
        'diagnostic_actions_runs_used':2,'diagnostic_actions_run_limit':2,
        'controls':controls,'handoff_qualified':handoff_ok,'runtime_qualified':runtime_ok,'runtime_profile':profile,
        'runtime_preflight':read(runtime/'public/preflight.json'),'runtime_current_manifest':read(runtime/'public/current/manifest.json'),
        'native_preflight_manifest':read(handoff/'public/manifest.json'),'runtime_verification':verification,'runtime_results':runtime_results,
        'paid_attempts_added':0,'model_inference_occurred':False,'historical_cause_resolved':False,
        'historical_evidence':'Run 42110435228 exported selected metadata only. Its native artifact collection manifest, raw rollout and private Harbor log were not exported. Actions job logs show completion/extraction and artifact uploads but no native artifact-download status. Missing historical candidate hash proves only absence at the checked host path. Historical task prompt bytes were frozen and stock Harbor passed instruction text, but no retained request/session proves task uptake.',
        'contract':['instruction.md contains the frozen pester-002 prompt, requiring output/Subject.Tests.ps1 from /workspace; user agent UID/GID 1000',
            'supported verifier.collect hook observes /workspace/output/Subject.Tests.ps1 after agent phase, before native collection; its metadata is diagnostic and not a tamper-proof attestation',
            'native artifacts/manifest.json records collection ok/failed/empty/skipped; host location is artifacts/workspace/output/Subject.Tests.ps1',
            'native upload sanitizes through a tar data filter and restores the original absolute path in a separate verifier; protected pre-grader metadata witnesses post-upload bytes',
            'unchanged admission criteria reject missing/nonregular/linked/oversized/non-UTF-8 candidates; new fixed admission_reason differentiates those failures',
            'only admitted candidates reach protected Pester reference/mutant checks; execution status, task-completion failures and grading denominators remain separate',
            'native process cleanup and container disposal follow collection/verification; post-agent metadata is checkpointed before job cleanup'],
        'changes':['APT cache bypass was added after HTTP 503; subsequent build passed with unchanged signed snapshot/package pins. The option is not proven to have caused recovery',
            'Trial-only supported collection hook and pre-grader metadata probe; no transport replacement or new private Harbor override',
            'Shared grader adds ArtifactError/read_candidate admission reasons; acceptance rules, classification invalid/artifact, numeric rewards and mutation criteria unchanged',
            'Canonical Codex package installed intact, including exec server, code-mode host, ripgrep and resources; external isolation unchanged',
            'One shared future model/effort profile; original live evidence remains attached to Codex 0.155.1/gpt-5.6-sol/medium',
            'Bounded rollout metadata retains event/tool counts, integer command exits and completion shape without commands, outputs or final-message content'],
        'limitations':['Successful controls cannot establish the historical cause','No new actual agent task, skill activation or model access is established',
            'Custom provider alias does not receive Codex built-in-only internal metadata, which is not configurable; budget source falls back to weighted non-cached input/output when provider units are absent',
            'Runtime configuration loading and HTTP/SSE refusal checks do not exercise successful inference or end-to-end budget exhaustion',
            'Pinned Harbor/LiteLLM has no gpt-6.1-sol pricing entry; native cost must remain unknown. Future conservative estimates use official long-context/12h cache-write assumptions, not provider bills',
            'Code-mode and executor companions are shipped, but agent tool execution under the new model has not occurred',
            'Stock Harbor root cleanup returned permission denied under dropped capabilities in both probes; original refusal failures and cleanup errors are separately retained. Full container disposal remains required; no added private cleanup hook',
            'Only the current arm was started with the upgraded CLI in this pass. Future arms use one shared configuration; historical three-file deployment differences remain historical evidence'],
        'local_checks':{'trial_tests':24,'shared_grader_checks':7,'shared_checks_unavailable':2,'unavailable_reason':'Two shared collector checks require SkillEvaluator, absent from the pinned direct-Harbor environment.'}}
    trial.write(out/'handoff-evidence.json',evidence)
    data['handoff_pass']={'evidence':'handoff-evidence.json','controls':controls,'handoff_qualified':handoff_ok,'runtime_qualified':runtime_ok,'profile':profile['id'],
        'summary':'Controlled handoff works; historical output failure remains unresolved.' if handoff_ok else 'Handoff qualification incomplete; inspect preserved boundary observations.',
        'notes':evidence['changes']+evidence['limitations']}
    if runtime_ok:
        wait=runtime_results['idle']['diagnostic']['observed_stream_wait_seconds']
        data['handoff_pass']['notes'].insert(0,'Observed runtime: Codex 0.166.0 strict configuration load exited 0 with API-only login. Both probes sent one POST to the loopback Responses endpoint; prompt, output path, GPT-6.1 Sol, High effort and sentinel API authentication matched. HTTP 503 was not retried; idle streaming ended after '+str(wait)+' seconds without reconnect. Prompt comparison uses the stripped frozen instruction. Budget configuration was accepted; enforcement under inference is untested.')
    data['future_runtime_profile']=profile
    data['state']='handoff_qualified_historical_cause_unresolved' if handoff_ok and runtime_ok else 'handoff_or_runtime_qualification_incomplete'
    data['decision']=('The controlled handoff works, but the historical agent-output failure remains unresolved. The upgraded runtime passed credential-free startup/configuration checks. Consider a separately authorized new-profile allocation; no inference is scheduled.' if handoff_ok and runtime_ok else 'A specific diagnostic blocker remains. Preserve the partial handoff/runtime evidence and keep paid scheduling disabled.')
    data['summary']='Three deterministic producers exercise the original agent UID/workspace through Harbor collection and independent verification. These are not Codex task executions. GPT-6.1 Sol/High is configured for a new comparison profile and has not been evaluated. Historical paid attempts, ungradeable outcomes, controls and spending uncertainty are unchanged.'
    data['budget'].update(scheduling_stopped=True,planned_live_attempts=0,stop_reason='This pass is credential-free; four recovery slots already consumed. A new live allocation is not authorized.')
    assert data['agent_attempts']==4 and data['api_spend_usd'] is None
    data['paid_attempts_reserved']=0
    run_id=os.environ.get('GITHUB_RUN_ID')
    data['recovery_runs'].append({'url':'https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42115972887','label':'First credential-free handoff diagnostic','summary':'Pinned snapshot HTTP 503 stopped image builds before controls or CLI startup. Failure report retained.'})
    if run_id:data['recovery_runs'].append({'url':'https://github.com/thetechgy/agent-engineering-baseline/actions/runs/'+run_id,'label':'Credential-free artifact handoff and Codex 0.166.0 qualification','summary':'Three deterministic handoff controls and offline startup checks; no inference. This artifact contains the single consolidated report.'})
    data['coverage_gaps']=[g for g in data['coverage_gaps'] if 'No valid live' not in g]+['No valid historical live grade; new controls do not rescore the historical pair','New CLI/model/effort has not been evaluated; comparisons cannot attribute historical differences solely to the skill']
    data['assessment'] += ['This pass reuses normal Harbor collection/upload and the existing grader. Native collection manifests plus safe pre-collection/post-upload metadata distinguish missing output from transport/admission failures. A confirmed missing deliverable is a task-completion failure, even when correctness and mutation denominators remain unavailable. Historical metadata is insufficient for that classification.',
        'The new comparison profile deliberately changes Codex CLI, model and reasoning effort. No production runtime or skill was changed. No additional private Harbor hooks, transport system, model-based judge or paid attempt was introduced.']
    data['sources'].update(codex_selected_release=profile['release'],future_model_pricing=profile['pricing']['source'])
    trial.report(out,data)
    with (out/'workflow-evidence.txt').open('a') as f:
        f.write('\nCredential-free handoff pass: '+str(run_id)+'\n')
        for kind,r in controls.items():f.write(kind+': '+json.dumps({'passed':r.get('passed'),'classification':r.get('classification'),'outcome':r.get('native_result',{}).get('outcome')} if r else {'evidence':'missing'})+'\n')
        f.write('Runtime offline verification: '+str(runtime_ok)+'. Paid ledger remains 4/4 recovery, 4/36 campaign; cumulative spending unknown.\n')
    print(json.dumps({'handoff_qualified':handoff_ok,'runtime_qualified':runtime_ok,'paid_attempts_added':0}))
    return 0 if handoff_ok and runtime_ok else 1

if __name__=='__main__':raise SystemExit(main(*(Path(x).resolve() for x in sys.argv[1:4])))
