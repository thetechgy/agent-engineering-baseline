#!/usr/bin/env python3
"""Build the backend wheel with only stdlib and reproducible source inputs."""

import base64
import csv
import hashlib
import io
from pathlib import Path
import sys
import zipfile


def build(destination):
    root = Path(__file__).resolve().parent
    metadata = "aeb_gh_fixture-1.0.0.dist-info"
    contents = {"aeb_gh_fixture/" + p.name: p.read_bytes() for p in sorted((root / "aeb_gh_fixture").glob("*.py"))}
    contents.update({
        metadata + "/METADATA": b"Metadata-Version: 2.1\nName: aeb-gh-fixture\nVersion: 1.0.0\nRequires-Python: >=3.13,<3.15\n",
        metadata + "/WHEEL": b"Wheel-Version: 1.0\nGenerator: aeb-stdlib-1\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        metadata + "/entry_points.txt": b"[skillevaluator.env_modes]\naeb-gh-fixture = aeb_gh_fixture:backend_spec\n",
    })
    record = io.StringIO(newline="")
    writer = csv.writer(record, lineterminator="\n")
    for name, raw in sorted(contents.items()):
        writer.writerow([name, "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).decode().rstrip("="), len(raw)])
    writer.writerow([metadata + "/RECORD", "", ""])
    contents[metadata + "/RECORD"] = record.getvalue().encode()
    destination.mkdir(parents=True, exist_ok=True)
    wheel = destination / "aeb_gh_fixture-1.0.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "x", compression=zipfile.ZIP_STORED) as bundle:
        for name, raw in sorted(contents.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, raw)
    requirements = destination / "requirements.txt"
    requirements.write_text(wheel.absolute().as_uri() + " --hash=sha256:" + hashlib.sha256(wheel.read_bytes()).hexdigest() + "\n")
    return wheel


if __name__ == "__main__":
    print(build(Path(sys.argv[1])))
