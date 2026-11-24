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


def unpack(destination):
    raw = evidence.read_bytes(SNAPSHOT, limit=2 * 1024 * 1024)
    evidence.require(evidence.digest_bytes(raw) == DIGEST, "Unreviewed private validator snapshot")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members = archive.infolist()
        evidence.require(len(members) == 490 and sum(m.file_size for m in members) <= 8 * 1024 * 1024,
                         "Private validator snapshot member limit")
        names = set()
        for member in members:
            path = PurePosixPath(member.filename)
            evidence.require(not path.is_absolute() and ".." not in path.parts
                             and path.as_posix() == member.filename and len(path.parts) >= 3
                             and path.parts[:2] in ((".github", "scripts"), (".github", "evals"))
                             and stat.S_ISREG(member.external_attr >> 16) and member.filename not in names,
                             "Invalid private validator member")
            names.add(member.filename)
            target = destination / member.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as output:
                output.write(archive.read(member))
    return destination / ".github/scripts"


RUN_CLI = r"""
from pathlib import Path
import runpy
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
runpy.run_path(entrypoint, run_name='__main__')
"""


def run_cli(arguments):
    """Run the same producer bytes used by the independent attachment checker."""
    import private_review_runtime

    private_review_runtime.validate_install()
    temporary = evidence.write_outputs({})
    try:
        scripts = unpack(temporary)
        child = subprocess.run([sys.executable, "-I", "-B", "-c", RUN_CLI, str(scripts),
                                str(evidence.ROOT), *arguments])
        return child.returncode
    finally:
        shutil.rmtree(temporary)
