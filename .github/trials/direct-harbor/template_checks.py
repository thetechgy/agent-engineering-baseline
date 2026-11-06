"""Small public-contract parser controls; candidates are parsed, never executed here."""
import json,subprocess,sys,tempfile
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent))
from admission_checks import inspect

# Expectations come from the public parameter contracts, existing fixture fields,
# Pester 6.2.0 It.ps1 Name/ForEach/TestCases binding, and the bounded execution profile.
FIELDS={
    'pester-001':['Port','Enabled','Count','Length','Name','Expected','Items','Endpoint'],
    'pester-002':['Count','Length','Name','Attempt','Base','Expected','BaseMilliseconds'],
    'pester-003':['Count','Length','Name','Target','Healthy'],
    'pester-004':['Count','Length','Name','Port','Expected'],
}

def checks(pwsh,runner,profiles,fixtures):
    rows=[]
    cases=[]
    for case,fields in FIELDS.items():
        name=' '.join('<'+field+'>' for field in fields)
        data='; '.join(field+' = 1' for field in fields)
        cases.append((case,case+'_public_fields',"It '"+name+"' -ForEach @(@{ "+data+" }) {}",'admitted',None))
    for label,source in [
        ('positional_foreach',"It 'base <basemilliseconds>' -ForEach @(@{BaseMilliseconds=37}) {}"),
        ('named_testcases',"It -Name 'base <BASEMILLISECONDS>' -TestCases @(@{BaseMilliseconds=37}) {}"),
        ('named_colon',"It -Name:'legacy <Base> <Expected>' -ForEach @(@{Base=37;Expected=37}) {}"),
        ('current_item',"It '<_>' -ForEach @(1,2) {}"),
        ('legacy_member',"$value.Base | Should-Be 37"),
        ('native_contract_fixture',(fixtures/'templates.Tests.ps1').read_text()),
    ]:cases.append(('pester-002',label,source,'admitted',None))
    for label,source,rule in [
        ('arithmetic',"It '<BaseMilliseconds + 1>' {}",'block_name_template'),
        ('subexpression',"It '<$(Get-Content /tests/private)>' {}",'block_name_template'),
        ('method',"It '<BaseMilliseconds.ToString()>' {}",'block_name_template'),
        ('template_member',"It '<BaseMilliseconds.Length>' {}",'block_name_template'),
        ('unknown_field',"It '<OtherField>' {}",'block_name_template'),
        ('reserved',"It '<ExecutionContext>' {}",'block_name_template'),
        ('reserved_case',"It '<hOsT>' {}",'block_name_template'),
        ('internal',"It '<__peRun>' {}",'block_name_template'),
        ('script_root',"It '<PSScriptRoot>' {}",'block_name_template'),
        ('scoped',"It '<env:PATH>' {}",'block_name_template'),
        ('new_field_not_member',"$value.BaseMilliseconds | Should-Be 37",'member_access'),
    ]:cases.append(('pester-002',label,source,'unsupported',rule))
    cases.append(('pester-001','endpoint_not_member','$value.Endpoint | Should-Be 1','unsupported','member_access'))
    with tempfile.TemporaryDirectory(prefix='template-admission-') as scratch:
        for case,label,source,status,rule in cases:
            candidate=Path(scratch)/(label+'.Tests.ps1');candidate.write_text(source)
            result=inspect(pwsh,runner,profiles/case/'profile.json',candidate,details=True)
            rows.append({'control':label,'case':case,'expected_status':status,'expected_rule':rule,
                         'observed':result,'passed':result.get('status')==status and result.get('admission_rule')==rule})
    return {'kind':'template_policy_v2_contract_checks','candidate_execution':False,'inference':False,
            'passed':all(r['passed'] for r in rows),'controls':rows}

if __name__=='__main__':
    result=checks(*[Path(x) for x in sys.argv[1:5]])
    print(json.dumps(result));raise SystemExit(0 if result['passed'] else 1)
