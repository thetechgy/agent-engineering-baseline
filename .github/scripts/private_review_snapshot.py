"""Materialize the fixed private-review producer and validator."""
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


V2_PROFILE = "review-101-v2"
V2_REVISION = "86899d9356c94cead240ec14d8592b53db556b89"
V2_OVERLAY = evidence.ROOT / ".github/evals/retained/private-review-101-v2-overlay.zip"
V2_DIGEST = "sha256:73c2dc9059c0b8830a21f611b70fbff00d14ddca8272999c570e743414e9d2eb"

V3_PROFILE = "review-101-v3"
V3_REVISION = "cbfec6eec2dfce00b2234624a62cf88e88014780"
V3_OVERLAY = evidence.ROOT / ".github/evals/retained/private-review-101-v3-overlay.zip"
V3_DIGEST = "sha256:9e28a852608b8249d390c4521c58653a05695d66ee173a96f0906caf549fba60"

V4_PROFILE = "review-101-v4"
V4_REVISION = "af379d06d08d621910a1abe2cce1bb04e12a72c8"
V4_OVERLAY = evidence.ROOT / ".github/evals/retained/private-review-101-v4-overlay.zip"
V4_DIGEST = "sha256:4d2dfd9e49bfc1d253d25621cf8a38023469fbaabd4b1ac16299b47d8476eafe"

V5_PROFILE = "review-101-v5"
V5_REVISION = "f2d5d766ce5149dcc80dc851e64895c442d4e912"
V5_OVERLAY = evidence.ROOT / ".github/evals/retained/private-review-101-v5-overlay.zip"
V5_DIGEST = "sha256:21ac911579c5f4ccfb3d11f3db1bf2b1e5fc748a44e5f64650d1fa06659e206a"
V121_PROFILE = "review-121-v1"
V121_OVERLAY = evidence.ROOT / ".github/evals/retained/private-review-121-v1-overlay.zip"
V121_MANIFEST = evidence.ROOT / ".github/evals/retained/private-review-121-v1.json"
V121_V2_PROFILE = "review-121-v2"
V121_V2_OVERLAY = evidence.ROOT / ".github/evals/retained/private-review-121-v2-overlay.zip"
V121_V2_MANIFEST = evidence.ROOT / ".github/evals/retained/private-review-121-v2.json"
ACTIVE_PROFILE = "review-121-v3"
ACTIVE_OVERLAY = evidence.ROOT / ".github/evals/retained/private-review-121-v3-overlay.zip"
ACTIVE_MANIFEST = evidence.ROOT / ".github/evals/retained/private-review-121-v3.json"
RELEASE_PROFILES = (PROFILE, V2_PROFILE, V3_PROFILE, V4_PROFILE, V5_PROFILE,
                    V121_PROFILE, V121_V2_PROFILE, ACTIVE_PROFILE)


def release_overlays():
    return (
        (V121_PROFILE, V121_OVERLAY, V121_MANIFEST),
        (V121_V2_PROFILE, V121_V2_OVERLAY, V121_V2_MANIFEST),
        (ACTIVE_PROFILE, ACTIVE_OVERLAY, ACTIVE_MANIFEST),
    )


def read_manifest(path):
    manifest = evidence.parse_json(evidence.read_bytes(path, limit=4096))
    fields = ("revision", "digest", "members")
    has_reporting_patch = path in (V121_V2_MANIFEST, ACTIVE_MANIFEST)
    if has_reporting_patch:
        fields += ("reporting_patch_sha256",)
    evidence.closed(manifest, fields)
    if has_reporting_patch:
        evidence.sha(manifest["reporting_patch_sha256"])
    evidence.revision(manifest["revision"])
    evidence.sha(manifest["digest"])
    evidence.require(type(manifest["members"]) is int and 0 < manifest["members"] <= 100,
                     "Unexpected active validator overlay size")
    return manifest


def identity(profile):
    """Return the fixed producer source and execution identity for a release profile."""
    evidence.require(profile in RELEASE_PROFILES, "Unsupported validator profile")
    for version, _, manifest_path in release_overlays():
        if profile == version:
            return read_manifest(manifest_path)["revision"], (
                "skillevaluator-1.2.1-private-review-frozen-" + profile.rsplit("-", 1)[1])
    sources = {
        PROFILE: REVISION, V2_PROFILE: V2_REVISION, V3_PROFILE: V3_REVISION,
        V4_PROFILE: V4_REVISION, V5_PROFILE: V5_REVISION,
    }
    return sources[profile], "skillevaluator-1.0.1-private-review-frozen-" + profile.rsplit("-", 1)[1]


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
    overlays = ((V2_OVERLAY, V2_DIGEST, 10), (V3_OVERLAY, V3_DIGEST, 12),
                (V4_OVERLAY, V4_DIGEST, 12), (V5_OVERLAY, V5_DIGEST, 8))
    for source, digest, count in overlays[:RELEASE_PROFILES.index(profile)]:
        contents.update(snapshot_members(source, digest, count))
    if profile in (V121_PROFILE, V121_V2_PROFILE, ACTIVE_PROFILE):
        for version, archive, manifest_path in release_overlays():
            manifest = read_manifest(manifest_path)
            contents.update(snapshot_members(archive, manifest["digest"], manifest["members"]))
            if version == profile:
                break
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
