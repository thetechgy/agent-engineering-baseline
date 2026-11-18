#!/usr/bin/env python3
"""Stage and qualify the transfer v2 native verifier without inference."""

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / '.github/scripts'))
sys.path.insert(0, str(HERE.parent / 'diagnostics'))
from evaluation_tasks import load
from quantity_replay_evidence import PUBLICATION_MEMBER, submission_roster
from replay_quantity import AMEND, SUBSTITUTE, digest, subjects

VERSION = 'pester-transfer-batch-v2'
TRANSFER = HERE.parent / 'transfer'
HISTORICAL = ROOT / 'docs/evaluations/pester-transfer-decision/diagnostics/quantity-int128.json'
REFERENCE = 'tests/case/reference/Subject.ps1'
EXTRA_REFERENCE = 'tests/case/reference/Quantity.Int128.ps1'


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Frozen native grader anchor drift')
    return source.replace(old, new, 1)


def native_members():
    """Create the v2 native members from the frozen transfer v6 staging contract."""
    definition = ROOT / '.github/evals/campaigns/pester-return-transfer-current-v6.json'
    task = load(definition)
    members = task.expected_members(task.definition['source_case'], 'without_skill')
    original = members[REFERENCE]
    members[EXTRA_REFERENCE] = replace_once(original, AMEND, SUBSTITUTE)

    grader = members['tests/verifier/grader.py'].decode()
    grader = replace_once(grader, 'MAX_VARIANTS = 6', 'MAX_VARIANTS = 7')
    # Recognize native Podman as well as Docker. The root, seccomp, cgroup,
    # network and socket checks still run before any submitted code.
    grader = replace_once(grader, "not Path('/.dockerenv').is_file()",
                          "not (Path('/.dockerenv').is_file() or Path('/run/.containerenv').is_file())")
    grader = replace_once(grader, """    variants = [tests / 'case/reference/Subject.ps1', *sorted((tests / 'case/mutants').glob('*.ps1'))]
    if not 2 <= len(variants) <= MAX_VARIANTS:
""", """    references = [tests / 'case/reference/Subject.ps1', tests / 'case/reference/Quantity.Int128.ps1']
    variants = [*references, *sorted((tests / 'case/mutants').glob('*.ps1'))]
    if len(variants) != MAX_VARIANTS:
""")
    grader = replace_once(grader, "return assess(runs[0], runs[1:], profile['minimum_tests'])",
                          "return assess_valid_references(runs[:2], runs[2:], profile['minimum_tests'])")
    grader = replace_once(grader, "    numeric = {'overall': float(status == 'passed')}",
                          "    details = {**details, 'grader_version': GRADER_VERSION}\n"
                          "    numeric = {'overall': float(status == 'passed')}")
    grader = replace_once(grader, "\nif __name__ == '__main__':",
                          '\n' + (HERE / 'grade_references.py').read_text() + "\n\nif __name__ == '__main__':")
    members['tests/verifier/grader.py'] = grader.encode()
    members['tests/entry.json'] = (json.dumps({'id': VERSION, 'grading_mode': 'custom_only'}, indent=2) + '\n').encode()
    return members


# The test entry point runs as the verifier. Its standard worker privilege drop
# runs each admitted submission as a distinct UID in a network-disabled container.
LAUNCH = """
set -eu
cp -R /staged/tests/. /tests/
mkdir -p /workspace/input /workspace/output
cp /staged/Subject.Tests.ps1 /workspace/output/
mkdir -p /logs/verifier
/bin/sh /tests/test.sh
/usr/bin/python3 -I -c 'import json, pathlib; root = pathlib.Path("/logs/verifier"); print(json.dumps({
"handoff": json.loads((root / "pilot-verified-submission.json").read_bytes()),
"reward": json.loads((root / "custom_reward.json").read_bytes()),
"sidecar": json.loads((root / "skill_evaluator_reward.json").read_bytes())}))'
"""


def run_native(image, runtime, staged):
    argv = [
        'podman', 'run', '--rm', '--pull=never', '--timeout=245', '--network=none', '--http-proxy=false',
        '--memory=2g', '--cpus=2', '--read-only', '--security-opt=no-new-privileges', '--user=0',
        '--cap-drop=ALL', '--cap-add=CHOWN,SETUID,SETGID,DAC_OVERRIDE,KILL',
        '--tmpfs=/tests:rw,nodev,nosuid,mode=0755', '--tmpfs=/workspace:rw,nodev,nosuid,mode=0755',
        '--tmpfs=/logs:rw,nodev,nosuid,mode=0755', '--tmpfs=/opt/pester-runtime:rw,nodev,nosuid,mode=0755',
        '--tmpfs=/tmp:rw,nodev,nosuid,mode=1777',
        '--mount', f'type=bind,src={staged},target=/staged,ro',
        '--mount', f'type=bind,src={runtime / "powershell"},target=/opt/microsoft/powershell/7,ro',
        '--mount', f'type=bind,src={runtime / "Modules"},target=/opt/pester/Modules,ro',
        '--entrypoint=/bin/sh', image, '-c', LAUNCH,
    ]
    try:
        result = subprocess.run(argv, capture_output=True, timeout=255, check=True)
        val = json.loads(result.stdout)
        if type(val) is not dict:
            raise ValueError('native output')
        return val
    except subprocess.CalledProcessError as error:
        return {'error': 'native_verifier_exit', 'exit_code': error.returncode}
    except subprocess.TimeoutExpired:
        return {'error': 'native_deadline'}
    except (ValueError, UnicodeError):
        return {'error': 'invalid_native_receipt'}


def grade_row(image, runtime, members, identity, payload):
    with tempfile.TemporaryDirectory(prefix='transfer-grader-v2-') as directory:
        staged = Path(directory)
        for member, content in members.items():
            if member.startswith('tests/'):
                path = staged / member
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
        (staged / 'Subject.Tests.ps1').write_bytes(payload)
        result = run_native(image, runtime, staged)
    row = {'id': identity, 'sha256': digest(payload), 'native': result}
    if not all(type(result.get(key)) is dict for key in ('handoff', 'reward', 'sidecar')):
        return {**row, 'outcome': 'unmeasured'}
    if (result['handoff'] != {'sha256': digest(payload).removeprefix('sha256:'), 'bytes': len(payload)}
            or result['sidecar']['details'] != result['reward']['details']
            or result['sidecar']['entry_id'] != VERSION or result['reward']['entry_id'] != VERSION):
        raise ValueError('Native handoff or reward identity mismatch')
    status = result['sidecar']['details']['outcome']['classification']
    if status not in ('passed', 'failed') or result['sidecar']['evaluation_status'] != 'complete':
        if 'custom_metrics' in result['reward']:
            raise ValueError('Unmeasured native trial acquired metrics')
        return {**row, 'outcome': 'unmeasured'}
    details = result['reward']['details']['outcome']
    if (details['grader_version'] != VERSION or details['powershell_version'] != '7.6.9'
            or details['pester_version'] != '6.2.0' or details['mutants_executed'] != 5):
        raise ValueError('Native grader/runtime/population mismatch')
    return {**row, 'outcome': status}


def qualify(image, runtime):
    members = native_members()
    history_raw = HISTORICAL.read_bytes()
    history = json.loads(history_raw)
    if (history['provenance']['fixtures'] != {'reference': digest(members[REFERENCE]),
                                             'variation': digest(members[EXTRA_REFERENCE])}
            or {row['id']: row['observed'] for row in history['checks']} != {
                'return-boundary': 'verified', 'permissive-suite': 'accepted', 'restrictive-suite': 'rejected'}):
        raise ValueError('Historical fixture/control binding mismatch')
    historical_controls = history['provenance']['control_runs']
    # The prior permissive probe used method calls outside the admission policy.
    # Use the admitted, frozen static-template control for the native positive.
    permissive = (TRANSFER / 'controls/static-template.Tests.ps1').read_bytes()
    restrictive = (HERE.parent / 'diagnostics/RestrictQuantity.Tests.ps1').read_bytes()
    historical_accept = (HERE.parent / 'diagnostics/AcceptQuantity.Tests.ps1').read_bytes()
    if (digest(restrictive) != historical_controls['restrictive-suite']['sha256']
            or digest(historical_accept) != historical_controls['permissive-suite']['sha256']):
        raise ValueError('Control changed since diagnostic replay')
    publication = (ROOT / PUBLICATION_MEMBER).read_bytes()
    retained = list(subjects(submission_roster(json.loads(publication))))
    history_rows = history['observations']
    if (history['provenance']['publication_sha256'] != digest(publication)
            or len(history_rows) != len(retained)
            or {row['id']: (row['arm'], row['sha256']) for row in history_rows} != {
                identity: (arm, suite_digest) for identity, arm, suite_digest, _ in retained}):
        raise ValueError('Historical submission population mismatch')
    controls = [grade_row(image, runtime, members, 'contract-correct', permissive),
                grade_row(image, runtime, members, 'type-restrictive', restrictive)]
    missing = {path: payload for path, payload in members.items() if path != EXTRA_REFERENCE}
    controls.append(grade_row(image, runtime, missing, 'missing-reference', permissive))
    observations = [dict(grade_row(image, runtime, members, identity, payload), arm=arm)
                    for identity, arm, _, payload in retained]
    return {
        'schema_version': 1, 'id': VERSION, 'historical_replay': digest(history_raw),
        'member_digests': {member: digest(raw) for member, raw in members.items()},
        'provenance': {
            'engine': 'rootless Podman', 'image_id': image,
            'powershell': digest((runtime / 'powershell/pwsh').read_bytes()),
            'pester_manifest': digest((runtime / 'Modules/Pester/6.2.0/Pester.psd1').read_bytes()),
        },
        'controls': controls, 'observations': observations,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--image', required=True, help='Existing local Linux image with frozen runtime dependencies')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    runtime = args.runtime.resolve(strict=True)
    output = args.output.resolve()
    if output.is_relative_to(ROOT) or output.exists():
        parser.error('Choose a new receipt path outside the checkout')
    rootless = subprocess.check_output(['podman', 'info', '--format', '{{.Host.Security.Rootless}}'], text=True)
    if rootless.strip() != 'true':
        parser.error('Qualification requires rootless Podman')
    image = subprocess.check_output(['podman', 'image', 'inspect', '--format', '{{.Id}}', '--', args.image],
                                    text=True).strip()
    if not re.fullmatch(r'(?:sha256:)?[0-9a-f]{64}', image):
        parser.error('Local image must resolve to a complete image ID')
    receipt = qualify(image, runtime)
    with output.open('x', encoding='utf-8') as handle:
        json.dump(receipt, handle, sort_keys=True, indent=2)
        handle.write('\n')


if __name__ == '__main__':
    main()
