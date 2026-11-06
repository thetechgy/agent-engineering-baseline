"""Candidate-only gh recipe; preserve every existing runtime/profile recipe."""

import gh_evaluations as gh


def stage(workspace, destination, selected=None):
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
    grader.write_bytes(grader_source(grader.read_bytes()))
    return bundle


def grader_source(source):
    """The sole reviewed candidate verifier import-path transformation."""
    old = 'native_path = Path(os.environ.get("HARBOR_TESTS_DIR", "/tests")) / "eval.py"'
    new = ('native_path = Path(os.environ.get("HARBOR_TESTS_DIR", "/tests")) / "skill_evaluator/eval.py"\n'
           '    import sys\n    sys.path.insert(0, str(native_path.parent))')
    text = source.decode()
    if text.count(old) != 1:
        raise ValueError("Unreviewed gh native verifier loading contract")
    return text.replace(old, new).encode()
