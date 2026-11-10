"""Execute the literal candidate example with controlled implementations; no inference."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
EXAMPLE = Path(__file__).with_name('variants') / 'candidate/powershell-pester-6/SKILL.md'
text = EXAMPLE.read_text().split('# Contract: Test-LabelPresent', 1)[1].split('```', 1)[0]
example = '# Contract: Test-LabelPresent' + text
rows = []
for name, body, failures in (
    ('correct', "$Label -ne ''", 0),
    ('wrong-type', "[int]($Label -ne '')", 2),
    ('wrong-values', "$Label -eq ''", 2),
    ('empty-boundary', '$true', 1),
    ('nonempty-boundary', '$false', 1),
):
    with tempfile.TemporaryDirectory(prefix='pester-example-') as directory:
        path = Path(directory) / 'Example.Tests.ps1'
        path.write_text('BeforeAll { function Test-LabelPresent { param([string]$Label) ' + body + ' } }\n' + example)
        command = """$ErrorActionPreference='Stop';
if ($PSVersionTable.PSVersion.ToString() -cne '7.6.9') { throw 'runtime' };
Import-Module Pester -RequiredVersion 6.2.0 -ErrorAction Stop;
$c=New-PesterConfiguration; $c.Run.Path=$args[0]; $c.Run.PassThru=$true; $c.Output.Verbosity='None';
$r=Invoke-Pester -Configuration $c;
@{ Passed=$r.PassedCount; Failed=$r.FailedCount; Total=$r.TotalCount;
   Blocks=$r.FailedBlocksCount; Containers=$r.FailedContainersCount;
   Pester=(Get-Module Pester).Version.ToString(); PowerShell=$PSVersionTable.PSVersion.ToString() } | ConvertTo-Json -Compress
"""
        # -File avoids command-line quoting and PowerShell argument ambiguity.
        caller = Path(directory) / 'Run.ps1'
        caller.write_text(command)
        result = subprocess.run([os.environ.get('CI_PWSH','pwsh'),'-NoLogo','-NoProfile','-NonInteractive','-File',str(caller),str(path)],
                                capture_output=True,text=True,check=True,timeout=35)
        value=json.loads(result.stdout)
        assert (value['Failed'], value['Passed'], value['Total'], value['Blocks'], value['Containers']) == (failures,2-failures,2,0,0), (name,value)
        rows.append(dict(control=name,**value))
Path(sys.argv[1]).write_text(json.dumps(rows,indent=2)+'\n')
