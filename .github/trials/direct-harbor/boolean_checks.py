"""Independent Pester 6.2.0 semantics fixtures, not derived from either candidate."""
import json,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from admission_checks import inspect

# Expected results come from pinned classic BeTrueOrFalse and standalone Boolean
# assertion implementations. Each expression is its own test to observe failures.
PASS = [
 '$true | Should -BeTrue', '$false | Should -BeFalse',
 '$false | Should -Not -BeTrue', '$true | Should -Not -BeFalse',
 '$false | Should -BeTrue -Not', '$true | Should -BeFalse -Not',
 '1 | Should -BeTrue', '0 | Should -BeFalse', '$null | Should -BeFalse',
 "'false' | Should -BeTrue", 'Should -ActualValue 1 -BeTrue',
 '$true | sHoUlD -bEtRuE', '$false | Should -bEfAlSe',
 '$true | Should-BeTrue', '$false | Should-BeFalse',
 'Should-BeTrue -Actual $true', 'Should-BeFalse -Actual $false',
 "{ throw 'bounded failure' } | Should-Throw -ExceptionMessage 'bounded*'",
]
FAIL = [
 '$false | Should -BeTrue', '$true | Should -BeFalse',
 '$true | Should -Not -BeTrue', '$false | Should -Not -BeFalse',
 '1 | Should-BeTrue', '0 | Should-BeFalse', '$null | Should-BeFalse',
 '$false | Should-BeTrue', '$true | Should-BeFalse',
 "{ throw 'bounded failure' } | Should-Throw -ExceptionMessage 'different*'",
]

def suite(expressions):
    return "Describe 'Independent assertion semantics' {\n"+''.join(" It 'assertion "+str(i)+"' { "+s+" }\n" for i,s in enumerate(expressions,1))+"}\n"

def checks(pwsh,runner,profile):
    cases=[('positive_forms',suite(PASS),'admitted',None),('wrong_assertions_are_admitted',suite(FAIL),'admitted',None)]
    for style in ('Should -BeTrue','Should-BeTrue'):
        for parameter in ('ErrorAction SilentlyContinue','ErrorAction Continue','EA Ignore','ErrorVariable errors','WarningAction Ignore'):
            cases.append((style+' '+parameter,'$false | '+style+' -'+parameter,'unsupported','assertion_parameter'))
    for label,source,rule in [
        ('dynamic',"& 'Should' -BeTrue",'invocation_operator'),
        ('arbitrary_command','Get-Content /tests/case/profile.json','command_not_allowed'),
        ('protected_write',"Set-Content /tests/Runner.ps1 'replacement'",'command_not_allowed'),
        ('unsafe_member','$value.GetType | Should-BeTrue','member_access'),
        ('suppression_preference',"$ErrorActionPreference = 'SilentlyContinue'",'variable_name'),
        ('pester_preference',"$PesterPreference = @{}",'variable_name'),
    ]:cases.append((label,source,'unsupported',rule))
    rows=[]
    with tempfile.TemporaryDirectory(prefix='boolean-admission-') as scratch:
        for index,(name,source,status,rule) in enumerate(cases):
            candidate=Path(scratch)/(str(index)+'.Tests.ps1');candidate.write_text(source)
            result=inspect(pwsh,runner,profile,candidate,details=True)
            rows.append({'control':name,'expected_status':status,'expected_rule':rule,'observed':result,'passed':result.get('status')==status and result.get('admission_rule')==rule})
    return {'passed':all(x['passed'] for x in rows),'candidate_execution':False,'controls':rows}

if __name__=='__main__':
    result=checks(*[Path(x) for x in sys.argv[1:4]])
    print(json.dumps(result));raise SystemExit(0 if result['passed'] else 1)
