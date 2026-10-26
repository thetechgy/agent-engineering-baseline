"""Verifier-owned Pester pilot grader; fixed codes, never raw test diagnostics."""

import ctypes
import json
import os
from pathlib import Path
import resource
import signal
import stat
import subprocess
import sys
import tempfile


PROTECTED_MARKER = 'PESTER_VERIFIER_ONLY_GRADER_B951'
RUN_SECONDS = 30
REAP_SECONDS = 5
CASE_SECONDS = 220
MAX_VARIANTS = 5
WORKER_UID = 53001
LIMIT = 64 * 1024
FILE_BYTES = 64 * 1024 * 1024
OUTPUT_BYTES = 1024 * 1024
UNSCORED = {'invalid', 'unsupported', 'timeout', 'infrastructure_error'}


def regular_bytes(path, limit=LIMIT):
    """Do not follow candidate links, including linked parent directories."""
    path = Path(path)
    for parent in (path, *path.parents):
        info = parent.lstat()
        if stat.S_ISLNK(info.st_mode):
            raise ValueError('artifact')
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
        raise ValueError('artifact')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
            raise ValueError('artifact')
        data = os.read(fd, limit + 1)
        if len(data) > limit:
            raise ValueError('artifact')
        return data
    finally:
        os.close(fd)


def worker_limits():
    """Bound files without preventing CoreCLR startup and Pester execution."""
    resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
    resource.setrlimit(resource.RLIMIT_NPROC, (128, 128))
    resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
    resource.setrlimit(resource.RLIMIT_FSIZE, (FILE_BYTES, FILE_BYTES))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def worker_identity():
    """Fixed privilege drop, not an agent-accessible privileged helper."""
    worker_limits()
    if ctypes.CDLL(None, use_errno=True).prctl(38, 1, 0, 0, 0) != 0:
        raise RuntimeError('privilege')
    os.setgroups([])
    os.setgid(WORKER_UID)
    os.setuid(WORKER_UID)


def check_environment():
    if os.geteuid() != 0 or not Path('/.dockerenv').is_file():
        raise RuntimeError('environment')
    if {p.name for p in Path('/sys/class/net').iterdir()} != {'lo'}:
        raise RuntimeError('network')
    status = Path('/proc/self/status').read_text()
    if 'Seccomp:\t2' not in status:
        raise RuntimeError('seccomp')
    memory = Path('/sys/fs/cgroup/memory.max').read_text().strip()
    quota, period = Path('/sys/fs/cgroup/cpu.max').read_text().split()
    if memory == 'max' or int(memory) > 2 * 1024**3 or quota == 'max' or int(quota) / int(period) > 2:
        raise RuntimeError('resources')
    if Path('/var/run/docker.sock').exists() or Path('/run/podman/podman.sock').exists():
        raise RuntimeError('mount')


def read_result(stream):
    """Require one bounded complete JSON object, never a truncated prefix."""
    stream.seek(0)
    data = stream.read(OUTPUT_BYTES + 1)
    if len(data) > OUTPUT_BYTES:
        return {'status': 'invalid', 'code': 'output_budget'}
    try:
        result = json.loads(data)
    except (ValueError, UnicodeError):
        return {'status': 'invalid', 'code': 'protocol'}
    return result if type(result) is dict else {'status': 'invalid', 'code': 'protocol'}


def invoke(candidate, profile, *, admission=False):
    argv = ['/opt/microsoft/powershell/7/pwsh', '-NoLogo', '-NoProfile', '-NonInteractive',
            '-File', '/opt/pester-runtime/Runner.ps1', '-Candidate', str(candidate),
            '-Profile', str(profile), '-RequireIsolation']
    if admission:
        argv.append('-AdmissionOnly')
    with tempfile.TemporaryDirectory(prefix='pester-worker-', dir='/tmp') as temporary:
        scratch = Path(temporary)
        scratch.chmod(0o700)
        os.chown(scratch, WORKER_UID, WORKER_UID)
        environment = {'PATH': '/opt/microsoft/powershell/7:/usr/bin:/bin', 'HOME': str(scratch),
                       'TMPDIR': str(scratch), 'PSModulePath': '/opt/pester/Modules',
                       'DOTNET_EnableDiagnostics': '0', 'POWERSHELL_TELEMETRY_OPTOUT': '1'}
        # Regular files plus RLIMIT_FSIZE bound output before parent reads it.
        with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            process = subprocess.Popen(argv, cwd='/workspace', env=environment,
                                       stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                       preexec_fn=worker_identity, start_new_session=True)
            try:
                process.wait(timeout=15 if admission else RUN_SECONDS)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=REAP_SECONDS)
                return {'status': 'timeout', 'code': 'deadline'}
            finally:
                # The admitted language has no process creation. Kill any
                # unexpected descendants too, before another variant starts.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=REAP_SECONDS)
            if process.returncode in (-signal.SIGXCPU, -signal.SIGKILL):
                return {'status': 'timeout', 'code': 'process_budget'}
            if process.returncode == -signal.SIGXFSZ:
                return {'status': 'invalid', 'code': 'output_budget'}
            if process.returncode:
                # The fixed runner catches candidate failures. Nonzero process
                # termination is an unqualified runtime, not candidate quality.
                stderr.seek(0)
                diagnostic = stderr.read(1024 * 1024)
                kind = next((label for label, pattern in (
                    ('permission', b'Permission denied'), ('coreclr', b'Failed to create CoreCLR'),
                    ('memory', b'Out of memory'), ('memory', b'Cannot allocate memory'),
                    ('dependency', b'Unable to load shared library'),
                ) if pattern in diagnostic), 'unclassified')
                return {'status': 'infrastructure_error', 'code': 'worker_' + kind,
                        'process_exit': process.returncode}
            return read_result(stdout)


def executed(result, minimum):
    keys = ('total', 'passed', 'failed', 'skipped', 'not_run', 'inconclusive',
            'failed_blocks', 'failed_containers', 'assertion_failures')
    return (result.get('status') == 'executed' and result.get('version') == '6.2.0'
            and result.get('powershell_version') == '7.6.6'
            and all(type(result.get(k)) is int and result[k] >= 0 for k in keys)
            and result['total'] >= minimum and result['total'] == result['passed'] + result['failed']
            and all(result[k] == 0 for k in ('skipped', 'not_run', 'inconclusive', 'failed_blocks', 'failed_containers')))


def assess(reference, mutants, minimum=1):
    """Pure classification of the fixed real-runner protocol, not a PS emulator."""
    for result in [reference, *mutants]:
        if result.get('status') in UNSCORED:
            return result['status'], {'code': result.get('code', 'runner')}
        if not executed(result, minimum):
            return 'invalid', {'code': 'nonexecuting'}
    reference_pass = reference['passed'] == reference['total'] and reference['failed'] == 0
    killed = sum(m['failed'] > 0 and m['assertion_failures'] == m['failed'] for m in mutants)
    return ('passed' if reference_pass and killed == len(mutants) else 'failed'), {
        'code': 'evaluated', 'reference_pass': int(reference_pass),
        'mutants_detected': killed, 'mutants_executed': len(mutants),
        'tests_executed': reference['total'],
        'pester_version': reference['version'], 'powershell_version': reference['powershell_version'],
    }


def prepare(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    os.chown(path, 0, 0)
    path.chmod(0o444)


def grade(tests):
    check_environment()
    # Harbor initially chmods its log directory; close that host mount to the child.
    logs = Path('/logs/verifier')
    os.chown(logs, 0, 0)
    logs.chmod(0o700)
    tests.chmod(0o700)
    profile = json.loads(regular_bytes(tests / 'case/profile.json'))
    try:
        candidate = regular_bytes(Path('/workspace/output/Subject.Tests.ps1'))
        candidate.decode('utf-8')
    except (FileNotFoundError, ValueError, UnicodeError):
        return 'invalid', {'code': 'artifact'}
    output = Path('/workspace/output/Subject.Tests.ps1')
    prepare(output, candidate)
    # Upload is finished, and the producer container is stopped. Replace the
    # artifact directory with verifier-owned immutable execution inputs.
    output.parent.chmod(0o755)
    os.chown(output.parent, 0, 0)
    runtime = Path('/opt/pester-runtime')
    runtime.mkdir(exist_ok=True)
    runtime.chmod(0o755)
    prepare(runtime / 'Runner.ps1', regular_bytes(tests / 'Runner.ps1'))
    prepare(runtime / 'profile.json', regular_bytes(tests / 'case/profile.json'))
    admission = invoke(output, runtime / 'profile.json', admission=True)
    if admission.get('status') != 'admitted':
        details = {'code': admission.get('code', 'admission')}
        if type(admission.get('process_exit')) is int:
            details['process_exit'] = admission['process_exit']
        return admission.get('status', 'infrastructure_error'), details
    variants = [tests / 'case/reference/Subject.ps1', *sorted((tests / 'case/mutants').glob('*.ps1'))]
    if not 2 <= len(variants) <= MAX_VARIANTS:
        raise RuntimeError('variants')
    runs = []
    for variant in variants:
        prepare(Path('/workspace/input/Subject.ps1'), regular_bytes(variant))
        runs.append(invoke(output, runtime / 'profile.json'))
    return assess(runs[0], runs[1:], profile['minimum_tests'])


def emit(tests, status, details):
    # All details are fixed classifications or integers, never source/actual values.
    if status not in UNSCORED | {'passed', 'failed'}:
        status, details = 'infrastructure_error', {'code': 'classification'}
    target = Path(os.environ.get('HARBOR_REWARD_JSON', '/logs/verifier/reward.json'))
    target.parent.mkdir(parents=True, exist_ok=True)
    entry = {}
    try:
        entry = json.loads(regular_bytes(tests / 'entry.json'))
        entry_id = entry['id']
    except Exception:
        status, details, entry_id = 'infrastructure_error', {'code': 'entry'}, 'unknown'
    reward = {'overall': float(status == 'passed'), 'entry_id': entry_id,
              'details': {'outcome': {'classification': status, **details}}}
    sidecar = {'evaluation_status': 'failed' if status in UNSCORED else 'complete',
               'entry_id': entry_id, 'has_skill': entry.get('has_skill'),
               'custom_details': reward['details']}
    if status in UNSCORED:
        sidecar['evaluation_errors'] = {'applicability': 'Unscoreable pilot trial: ' + status}
    else:
        reward['custom_metrics'] = {'pester_reference_pass': float(details['reference_pass']),
                                    'pester_mutation_detection': details['mutants_detected'] / details['mutants_executed'],
                                    'pester_test_quality': reward['overall']}
    target.write_text(json.dumps(reward))
    temporary = target.parent / 'pilot-sidecar.tmp'
    temporary.write_text(json.dumps(sidecar))
    os.replace(temporary, target.parent / 'skill_evaluator_reward.json')


def main():
    tests = Path(os.environ.get('HARBOR_TESTS_DIR', '/tests'))
    # Pre-arm the existing native unscoreable carrier before parsing or child
    # execution. An interrupted/killed grader cannot leave a scoreable zero.
    log = Path(os.environ.get('HARBOR_REWARD_JSON', '/logs/verifier/reward.json')).parent
    log.mkdir(parents=True, exist_ok=True)
    log_state = log.stat()
    (log / 'skill_evaluator_reward.json').write_text(json.dumps({
        'evaluation_status': 'failed', 'evaluation_errors': {'execution': 'Pilot verifier incomplete'},
        'custom_details': {'outcome': {'classification': 'infrastructure_error', 'code': 'incomplete'}}}))
    status, details = 'infrastructure_error', {'code': 'verifier'}
    try:
        def expired(_number, _frame):
            raise TimeoutError('case budget')
        signal.signal(signal.SIGALRM, expired)
        signal.alarm(CASE_SECONDS)
        status, details = grade(tests)
    except TimeoutError:
        status, details = 'timeout', {'code': 'case_budget'}
    except (ValueError, UnicodeError):
        status, details = 'invalid', {'code': 'artifact'}
    except Exception:
        pass
    finally:
        signal.alarm(0)
        # This directory is Harbor's host bind mount. Restore its original host
        # ownership/access after all workers are dead so native collection can
        # read rewards; keep it root-only throughout candidate execution.
        os.chown(log, log_state.st_uid, log_state.st_gid)
        log.chmod(stat.S_IMODE(log_state.st_mode))
    emit(tests, status, details)


if __name__ == '__main__':
    sys.excepthook = lambda *_args: None
    main()
