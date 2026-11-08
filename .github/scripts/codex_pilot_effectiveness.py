"""Prospective Pester contract and controls for the existing pilot machinery.

No agent answers are inspected here. Legacy runners, fixtures and grades stay frozen.
"""
import hashlib
import shutil

from codex_pilot_contract import ROOT, PROFILE as RUNTIME, grader_bytes as retained_grader
from codex_pilot_iteration import runner_bytes

PROFILE_ID = 'pester-effectiveness-v1'
PURPOSE = 'skill_effectiveness'
CONTROL_PURPOSE = 'skill_effectiveness_control'
CASES = ('pester-001', 'pester-003', 'pester-004')
PRIMARY_CASES = CASES[1:]
DOCUMENT = '.github/evals/pester-effectiveness.md'
PROTOCOL = '.github/evals/pester-effectiveness.json'


def case_files(workspace, case):
    """Only prospective verifier fixtures change; public tasks stay identical."""
    root = workspace / '.github/evals/powershell-pester-6/support/cases' / case
    files = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*')
             if p.is_file() and p.relative_to(root).parts[0] != 'input'}
    if case == 'pester-003':
        reference = files['reference/Subject.ps1'].decode()
        anchor = '[pscustomobject] @{ Target = $Target; Healthy = [bool] (Test-ProbeConnection -Target $Target) }'
        assert reference.count(anchor) == 1
        for name, replacement in {
            'double': '$null = Test-ProbeConnection -Target $Target\n    ' + anchor,
            'echo': anchor.replace('Target = $Target;', "Target = 'localhost';"),
            'unhealthy': anchor.replace('[bool] (Test-ProbeConnection -Target $Target)',
                                        '[bool] ((Test-ProbeConnection -Target $Target) -or $true)'),
        }.items():
            files['mutants/' + name + '.ps1'] = reference.replace(anchor, replacement).encode()
    return files


def grader_bytes(workspace=ROOT):
    source = retained_grader(workspace).decode()
    # Six variants still fit the unchanged 220-second case deadline and worker limits.
    assert source.count('MAX_VARIANTS = 5') == 1
    source = source.replace('MAX_VARIANTS = 5', 'MAX_VARIANTS = 6')
    old = "killed = sum(m['failed'] > 0 and m['assertion_failures'] == m['failed'] for m in mutants)"
    assert source.count(old) == 1
    source = source.replace(old, "killed = sum(reference_pass and m['failed'] > 0 and m['assertion_failures'] == m['failed'] for m in mutants)")
    anchor = "        'tests_executed': reference['total'],"
    source = source.replace(anchor, anchor + "\n        'variant_detections': [int(reference_pass and m['failed'] > 0 and m['assertion_failures'] == m['failed']) for m in mutants],")
    return source.encode()


def fixtures(workspace=ROOT):
    """Expected outcomes and exact mutant signatures frozen before any live outputs."""
    support = workspace / '.github/evals/powershell-pester-6/support'
    rows = {}
    def add(case, name, payload, outcome, signature=None):
        rows[case + '-' + name] = {'case': case, 'payload': payload, 'outcome': outcome, 'signature': signature}
    def read(case, name):
        return (support / 'qualification' / case / (name + '.Tests.ps1')).read_bytes()
    for case, styles in {'pester-001': ('classic', 'standalone', 'data'),
                         'pester-003': ('external', 'module'),
                         'pester-004': ('discovery', 'inline', 'compact')}.items():
        for style in styles:
            payload = read(case, style)
            if case == 'pester-003' and style == 'module':
                # The historical module fixture omitted the returned Target contract.
                payload = payload.replace(b"(Get-EndpointStatus -Target 'service.invalid').Healthy | Should -Be $true",
                    b"$result = Get-EndpointStatus -Target 'service.invalid'\n            $result.Target | Should -Be 'service.invalid'\n            $result.Healthy | Should -Be $true")
                payload = payload.replace(b"(Get-EndpointStatus -Target 'backup.invalid').Healthy | Should -Be $false",
                    b"$result = Get-EndpointStatus -Target 'backup.invalid'\n            $result.Target | Should -Be 'backup.invalid'\n            $result.Healthy | Should -Be $false")
            add(case, style, payload, 'passed')
        add(case, 'weak', read(case, 'weak'), 'failed', [0] * (5 if case == 'pester-003' else 4 if case == 'pester-004' else 2))
    # Each boundary omission must miss exactly that mutant, regardless of test count.
    explicit = b"BeforeAll { . '/workspace/input/Subject.ps1' }\nDescribe 'port limits' { It 'checks supplied boundaries' {\n"
    boundaries = ((0, '$false', 'zero'), (1, '$true', 'lowest'), (65535, '$true', 'highest'), (65536, '$false', 'above'))
    for omitted in (None, 'zero', 'lowest', 'highest', 'above'):
        payload = explicit + ''.join(f'Test-PortAllowed -Port {port} | Should -Be {expected}\n' for port, expected, name in boundaries if name != omitted).encode() + b'} }\n'
        signature = [int(name != omitted) for name in ('above', 'highest', 'lowest', 'zero')]
        add('pester-004', 'explicit' if omitted is None else 'omit-' + omitted, payload,
            'passed' if omitted is None else 'failed', signature)
    # Missing-call and forwarding faults are not detected just by an unrelated failure.
    healthy = b"BeforeAll { Import-Module '/workspace/input/Probe.psm1' -Force }\nDescribe 'endpoint' { It 'checks a healthy request' {\nMock Test-ProbeConnection { $true } -ModuleName Probe\n$result = Get-EndpointStatus -Target 'service.invalid'\n$result.Target | Should -Be 'service.invalid'\n$result.Healthy | Should -Be $true\n"
    add('pester-003', 'healthy-output', healthy + b'} }\n', 'failed', [0, 0, 1, 0, 0])
    add('pester-003', 'healthy-calls', healthy + b"Should -Invoke -CommandName Test-ProbeConnection -ModuleName Probe -Times 1 -Exactly -ParameterFilter { $Target -eq 'service.invalid' }\n} }\n", 'failed', [1, 1, 1, 1, 0])
    add('pester-004', 'broken-discovery', (support / 'cases/pester-004/input/Existing.Tests.ps1').read_bytes(), 'invalid')
    add('pester-003', 'wrong-scope', b"BeforeAll { Import-Module '/workspace/input/Probe.psm1' -Force }; Describe 'scope' { It 'checks' { Mock Test-ProbeConnection { $true }; (Get-EndpointStatus -Target 'service.invalid').Healthy | Should -BeTrue } }", 'failed', [0]*5)
    for case in PRIMARY_CASES:
        good = next(row['payload'] for row in rows.values() if row['case'] == case and row['outcome'] == 'passed')
        add(case, 'failure', b"Describe 'actual failure' { It 'fails' { 1 | Should -Be 2 } }", 'failed', [0]*(5 if case == 'pester-003' else 4))
        add(case, 'missing', b'', 'invalid')
        add(case, 'unsupported', b"Describe x { It y { [System.IO.File]::ReadAllText('/tests/grader.py') } }", 'unsupported')
        add(case, 'timeout', b"Describe 'bounded' { It 'does not terminate' { for (;;) {} } }", 'timeout')
        add(case, 'missing-runtime', good, 'infrastructure_error')
    return rows


def schedule():
    """Twelve sequential, clean-container attempts; balanced first arm across cases."""
    rows = []
    for trial in range(1, 4):
        cases = PRIMARY_CASES if trial % 2 else tuple(reversed(PRIMARY_CASES))
        for case in cases:
            arms = ('with_skill', 'without_skill') if (trial + PRIMARY_CASES.index(case)) % 2 else ('without_skill', 'with_skill')
            start = len(rows)
            rows.extend({'position': start + offset + 1, 'case': case, 'trial': trial, 'arm': arm}
                        for offset, arm in enumerate(arms))
    return rows


def inputs(workspace=ROOT):
    paths = [PROTOCOL, DOCUMENT, '.github/scripts/codex_pilot_effectiveness.py']
    paths += [p.relative_to(workspace).as_posix() for p in sorted((workspace / '.github/evals/pester-confirmation-v1').rglob('*')) if p.is_file()]
    return [{'member': 'pilot/' + path, 'digest': 'sha256:' + hashlib.sha256((workspace / path).read_bytes()).hexdigest()} for path in paths]


def verify_arms(tasks, captured):
    """Full staged-byte comparison; the target directory is the sole arm difference."""
    by_key = {(r['arm'], r['case_id']): r for r in captured}
    for case in {row['case_id'] for row in captured}:
        left = by_key['with_skill', case]['members']
        right = by_key['without_skill', case]['members']
        prefix = 'environment/skills/powershell-pester-6/'
        assert {k: v for k, v in left.items() if not k.startswith(prefix)} == right, 'Matched-arm drift'
        assert any(k.startswith(prefix) for k in left), 'Missing skill deployment'
    # No oracle payload, grader, reference, mutant or retained submission enters agent images.
    for arm_tasks in tasks.values():
        for task in arm_tasks:
            assert not (task / 'solution').exists(), 'Oracle in prospective task'
            assert not any('verifier' in p.parts or 'mutants' in p.parts or 'reference' in p.parts
                           for p in (task / 'environment').rglob('*')), 'Protected material in agent context'
    return {'complete': True, 'only_difference': 'target skill directory including supporting files', 'cases': list(CASES)}


def prepare(root):
    """One credential-free case-to-report entry point; never delivers credentials."""
    import os
    import subprocess
    import codex_pilot as pilot
    import skill_evidence as evidence
    import skill_reports as reports
    import skill_report as report
    import evaluator_profiles as profiles
    if any(os.environ.get(k) for k in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'NVIDIA_API_KEY')):
        raise ValueError('Credential-free preparation received credentials')
    protocol = reports.read_json(ROOT / PROTOCOL)
    if (protocol['runtime_contract_sha256'] != hashlib.sha256((ROOT / '.github/evals/codex-pilot.json').read_bytes()).hexdigest()
            or protocol['evaluator_profile_sha256'] != hashlib.sha256((ROOT / '.github/evals/evaluator-candidate.json').read_bytes()).hexdigest()
            or protocol['authorized_live_attempts'] != 0 or protocol['proposed_attempts'] != len(schedule())):
        raise ValueError('Frozen protocol/runtime identity drift')
    artifact = root / 'evidence'
    staged = root / 'prospective'; staged.mkdir()
    bundle, tasks, captured = pilot.stage(staged, effectiveness=True)
    audit = verify_arms(tasks, captured)
    reports.write_json(staged / 'evidence/staging.json', captured)
    reports.write_json(staged / 'evidence/deployment-check.json', audit)
    reports.write_json(staged / 'evidence/source-identities.json', evidence.custom_input_identities(ROOT, RUNTIME['skill'], purpose=PURPOSE))
    # A second clean APM deployment must produce byte-identical task members.
    repeated = root / 'repeat'; repeated.mkdir()
    _, repeated_tasks, repeated_capture = pilot.stage(repeated, effectiveness=True)
    verify_arms(repeated_tasks, repeated_capture)
    if captured != repeated_capture:
        raise ValueError('Fresh prospective staging does not reproduce')
    controls = root / 'controls'; controls.mkdir()
    pilot.run(controls, controls=True, effectiveness=True)
    shutil.copytree(staged / 'evidence', artifact / 'prospective')
    shutil.copytree(controls / 'evidence', artifact / 'controls')
    # Reproduce through the same public evidence CLI path, without native originals.
    report.generate([artifact / 'controls/public'], artifact / 'controls/analysis/analysis.json', artifact / 'reproduced')
    original = artifact / 'controls/consolidated/report.html'
    reproduced = artifact / 'reproduced/report.html'
    if original.read_bytes() != reproduced.read_bytes():
        raise ValueError('Consolidated HTML does not reproduce')
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    rows = fixtures()
    reports.write_json(artifact / 'frozen-proposal.json', {
        'protocol': reports.read_json(ROOT / PROTOCOL), 'qualified_revision': revision,
        'profile': PROFILE_ID, 'runtime': RUNTIME, 'evaluator': profiles.CANDIDATE,
        'source_identities': evidence.custom_input_identities(ROOT, RUNTIME['skill'], purpose=PURPOSE),
        'deployment': reports.read_json(staged / 'workspace-profile.json'),
        'reserved_confirmation_source': reports.read_json(ROOT / '.github/evals/pester-confirmation-v1/manifest.json'),
        'schedule': schedule(), 'proposed_attempts': 12, 'authorized_live_attempts': 0,
        'control_expectations': {name: {k: v for k, v in row.items() if k != 'payload'} for name, row in rows.items()},
        'html_sha256': hashlib.sha256(original.read_bytes()).hexdigest(),
        'limitations': ['oracle submissions, not agent results', 'no effectiveness or generalization established',
                       'agent failures and verifier failures remain separate; unavailable quality is not zero',
                       'usage estimates are not actual billing']})
    reports.write_json(artifact / 'qualification.json', {'complete': True, 'inference': False,
        'profile': PROFILE_ID, 'revision': revision, 'fresh_staging_equal': True,
        'report_reproduced': True, 'control_trials': 2 * len(rows), 'proposed_live_attempts': 12,
        'authorized_live_attempts': 0})
