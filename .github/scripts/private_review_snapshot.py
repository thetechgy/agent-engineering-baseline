"""Materialize the fixed 1.0.1 private-review producer and validator."""
import io
from pathlib import PurePosixPath
import shutil
import stat
import subprocess
import sys
import zipfile

import skill_evidence as evidence

PROFILE = "review-101-v1"
REVISION = "c1d0f61d29e1a2dfad964a4406964ad068cd0a5b"
SNAPSHOT = evidence.ROOT / ".github/evals/retained/private-review-101.zip"
DIGEST = "sha256:376fe25f26672a98a878c6d946a7700a6f463d5ae6d0599fb2b8da7f05c5ba9d"


ACTIVE_PROFILE = "review-101-v2"
ACTIVE_REVISION = "86899d9356c94cead240ec14d8592b53db556b89"
ACTIVE_OVERLAY = evidence.ROOT / ".github/evals/retained/private-review-101-v2-overlay.zip"
ACTIVE_DIGEST = "sha256:73c2dc9059c0b8830a21f611b70fbff00d14ddca8272999c570e743414e9d2eb"


def identity(profile):
    """Return the fixed producer source and execution identity for a release profile."""
    evidence.require(profile in (PROFILE, ACTIVE_PROFILE), "Unsupported validator profile")
    if profile == PROFILE:
        return REVISION, "skillevaluator-1.0.1-private-review-frozen-v1"
    return ACTIVE_REVISION, "skillevaluator-1.0.1-private-review-frozen-v2"


def snapshot_members(source, digest, count):
    raw = evidence.read_bytes(source, limit=2 * 1024 * 1024)
    evidence.require(evidence.digest_bytes(raw) == digest, "Unreviewed private validator snapshot")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members = archive.infolist()
        evidence.require(len(members) == count and sum(m.file_size for m in members) <= 8 * 1024 * 1024,
                         "Private validator snapshot member limit")
        contents = {}
        for member in members:
            path = PurePosixPath(member.filename)
            evidence.require(not path.is_absolute() and ".." not in path.parts
                             and path.as_posix() == member.filename and len(path.parts) >= 3
                             and path.parts[:2] in ((".github", "scripts"), (".github", "evals"))
                             and stat.S_ISREG(member.external_attr >> 16) and path not in contents,
                             "Invalid private validator member")
            contents[path] = archive.read(member)
    return contents


def unpack(destination, profile=PROFILE):
    identity(profile)
    contents = snapshot_members(SNAPSHOT, DIGEST, 490)
    if profile == ACTIVE_PROFILE:
        contents.update(snapshot_members(ACTIVE_OVERLAY, ACTIVE_DIGEST, 10))
    for member, raw in contents.items():
        target = destination / member
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as output:
            output.write(raw)
    return destination / ".github/scripts"


RUN_CLI = r"""
from pathlib import Path
import sys

scripts, checkout, *arguments = sys.argv[1:]
sys.path.insert(0, scripts)
import skill_evidence
write_outputs = skill_evidence.write_outputs

def confined_write(values, destination=None, *, input_paths=(), **kwargs):
    return write_outputs(values, destination, workspace=Path(checkout),
                         input_paths=(Path(scripts).parents[1], *input_paths), **kwargs)

skill_evidence.write_outputs = confined_write
entrypoint = str(Path(scripts) / 'skill_review.py')
sys.argv[:] = [entrypoint, *arguments]
import skill_review as review
try:
    review.main()
except review.PrivateContractError as error:
    print(str(error), file=sys.stderr)
    raise SystemExit(1) from None
except Exception:
    print("Skill review rejected; no validated report is ready. Retry requires a new manual invocation.", file=sys.stderr)
    raise SystemExit(1) from None
"""


def run_cli(arguments):
    """Run the same producer bytes used by the independent attachment checker."""
    import private_review_runtime

    private_review_runtime.validate_install()
    temporary = evidence.write_outputs({})
    try:
        scripts = unpack(temporary, ACTIVE_PROFILE)
        child = subprocess.run([sys.executable, "-I", "-B", "-c", RUN_CLI, str(scripts),
                                str(evidence.ROOT), *arguments])
        return child.returncode
    finally:
        shutil.rmtree(temporary)
