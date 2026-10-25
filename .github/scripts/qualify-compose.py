"""One-time, credential-free paired qualification; removed after evidence capture."""

import asyncio
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import uuid

import gh_container_validation as validation


async def main():
    candidate = os.environ["DOCKER_CONFIG"]
    root = Path(sys.argv[1])
    server = json.loads(validation.run("docker", "version", "--format", "{{json .Server}}").stdout)
    records = []
    try:
        for version, plugin in (("5.0.2", root / "baseline"), ("5.6.1", Path(candidate))):
            os.environ["DOCKER_CONFIG"] = str(plugin)
            assert validation.run("docker", "compose", "version", "--short").stdout.strip() == version
            case = root / version
            case.mkdir()
            try:
                record = await validation.compose_lifecycle(case, "compose-qualification-" + uuid.uuid4().hex[:12])
            except Exception as error:
                record = {"compose": version, "failure": str(error)}
            records.append(record)
            print(json.dumps(record), flush=True)
    finally:
        os.environ["DOCKER_CONFIG"] = candidate
    assert server == json.loads(validation.run("docker", "version", "--format", "{{json .Server}}").stdout)
    assert not any("failure" in record for record in records), "Paired lifecycle failure; preserve preceding evidence"
    assert records[0]["configuration"] == records[1]["configuration"]
    assert records[0]["task_context_digest"] == records[1]["task_context_digest"]
    # Execute the unchanged benchmark metadata producer against the discovered plugin.
    source = (validation.gh.ROOT / ".github/scripts/setup-skillevaluator.sh").read_text()
    producer = source.split("<<'PY' > \"$tool_root/versions.json\"\n", 1)[1].rsplit("\nPY", 1)[0]
    previous_argv = sys.argv
    output = io.StringIO()
    try:
        sys.argv = ["-", str(root), "benchmark", ""]
        with redirect_stdout(output):
            exec(compile(producer, "setup-benchmark-metadata", "exec"), {})
    finally:
        sys.argv = previous_argv
    validation.gh.reports.validate_benchmark_versions(json.loads(output.getvalue()))
    print(json.dumps({"paired_compose_qualification": "passed", "model_trials": 0,
                      "engine": server["Version"], "api": server["ApiVersion"],
                      "harbor": "0.13.2", "skillevaluator": "0.3.0"}), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
