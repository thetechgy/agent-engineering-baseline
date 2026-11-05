"""Check the fixed offline reproduction and two refusal probes; never task grading."""
import json,sys
from datetime import datetime
from pathlib import Path
root=Path(sys.argv[1]);output=root/'public'
records={mode:json.loads((output/mode/'diagnostic.json').read_text()) for mode in ('historical','http','idle')}
checks={}
old=json.loads((output/'historical/launch-diagnostics.json').read_text())
checks['historical_reserved_id_reproduced']=bool(old['primary_failure'] and old['primary_failure']['stage']=='cli_startup' and 'reserved built-in provider IDs' in old['primary_failure']['stdout'])
for mode in ('http','idle'):
    record=records[mode]
    settings=json.loads((output/mode/'effective-config.json').read_text())
    provider=settings['model_providers'][settings['model_provider']]
    checks[mode+'_effective_alias']=settings['model_provider']=='trial_openai' and provider['base_url']=='http://127.0.0.1:8765/v1'
    requests=record.get('provider_observation',{}).get('requests',[])
    checks[mode+'_one_request']=len(requests)==1 and requests[0]['path']=='/v1/responses'
    checks[mode+'_real_startup']=record['rollout_present'] and record['result_extraction_succeeded'] and bool(requests)
    checks[mode+'_intentional_failure']=not record['launch_succeeded'] and record['native_result']['measured'] is False
    if mode=='idle' and requests:
        finished=datetime.fromisoformat(record['native_result']['timing']['agent_execution']['finished_at']).timestamp()
        elapsed=finished-requests[0]['at']
        checks['idle_60_second_deadline']=55<=elapsed<=70
        record['observed_stream_wait_seconds']=round(elapsed,3)
        (output/mode/'diagnostic.json').write_text(json.dumps(record,indent=2)+'\n')
value={'kind':'credential_free_diagnostic_verification','checks':checks,'passed':all(checks.values()),
       'paid_attempts_added':0,'task_outcome_measured':False}
(output/'verification.json').write_text(json.dumps(value,indent=2)+'\n')
print(json.dumps(value,indent=2))
raise SystemExit(0 if value['passed'] else 1)
