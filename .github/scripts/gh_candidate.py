"""Candidate-only gh recipe; preserve every existing runtime/profile recipe."""

import gh_evaluations as gh


def stage(workspace, destination, selected=None, *, fixture=False):
    bundle = gh.stage(workspace, destination, selected)
    for task in (bundle / "evals/harbor").iterdir():
        if not task.is_dir():
            continue
        config = task / "task.toml"
        # Producer recipe change before native validation; guards remain active.
        text = config.read_text()
        expected = '[environment.healthcheck]\ncommand = "python3 -I /opt/gh-eval/setup.py --start"\ninterval_sec = 1.0\nretries = 1\n'
        if not text.endswith(expected):
            raise ValueError("Unreviewed gh task initialization recipe")
        config.write_text(text.removesuffix(expected))
    grader = bundle / "evals/grader.py"
    grader.write_bytes(grader_source(grader.read_bytes(), fixture=fixture))
    return bundle


def grader_source(source, *, fixture=False):
    """The sole reviewed candidate verifier import-path transformation."""
    old = 'native_path = Path(os.environ.get("HARBOR_TESTS_DIR", "/tests")) / "eval.py"'
    new = ('native_path = Path(os.environ.get("HARBOR_TESTS_DIR", "/tests")) / "skill_evaluator/eval.py"\n'
           '    import sys\n    sys.path.insert(0, str(native_path.parent))')
    text = source.decode()
    if text.count(old) != 1:
        raise ValueError("Unreviewed gh native verifier loading contract")
    text = text.replace(old, new)
    if fixture:
        # Fixture-only custom scoring preserves the existing deterministic gate.
        # No standard metric or judge is produced by this verifier entry point.
        old = '    target.write_text(json.dumps(reward) + "\\n")'
        new = r'''    metrics = reward['custom_metrics']
    status = ('passed' if metrics['gh_gate'] else 'failed') if metrics['gh_evidence'] else (
        'unsupported' if any(call.get('normalization_status') for call in calls) else 'unknown')
    measured = status in ('passed', 'failed')
    sidecar = {'entry_id': entry['id'], 'has_skill': entry['has_skill'],
        'evaluation_status': 'complete' if measured else 'failed',
        'custom_metrics': metrics if measured else {},
        'custom_details': {'outcome': {'classification': status, 'code': 'evaluated' if measured else status}},
        'raw_custom_metrics': metrics, 'overall': float(status == 'passed')}
    if not measured: sidecar['evaluation_errors'] = {'evidence': status}
    target.with_name('skill_evaluator_reward.json').write_text(json.dumps(sidecar))
    target.with_name('custom_reward.json').write_text(json.dumps(sidecar))
    target.write_text(json.dumps({'overall': sidecar['overall'], **sidecar['custom_metrics']}) + "\n")'''
        if text.count(old) != 1:
            raise ValueError('Unreviewed gh fixture reward contract')
        text = text.replace(old, new)
    return text.encode()
