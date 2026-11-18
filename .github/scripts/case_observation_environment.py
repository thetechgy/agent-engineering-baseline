"""Host-owned workspace witness inside the protected Codex lifecycle."""
import asyncio
import hashlib
import json
import os
import re
from pathlib import Path

from codex_pilot_environment import PilotEnvironment
from skill_evidence import read_bytes
from skill_reports import regular_tree, write_json

SCANNER = Path(__file__).with_name("case_workspace.py")
MAX_RECORD = 512 * 1024


class ObservationEnvironment(PilotEnvironment):
    async def _operator(self, *argv, payload=b""):
        proc = await asyncio.create_subprocess_exec(
            "docker", *argv, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env=self._trusted_compose_client_environment(excluded_names=set(),
                                                         excluded_values=self._pilot_secrets))
        try:
            async with asyncio.timeout(12):
                proc.stdin.write(payload)
                await proc.stdin.drain()
                proc.stdin.close()
                chunks = bytearray()
                while chunk := await proc.stdout.read(65536):
                    chunks.extend(chunk)
                    if len(chunks) > MAX_RECORD:
                        raise ValueError("Workspace observation size limit")
                if await proc.wait():
                    raise ValueError("Workspace observation unavailable")
                return bytes(chunks)
        finally:
            if proc.returncode is None:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
                async with asyncio.timeout(3):
                    await proc.communicate()

    async def _idle(self, container):
        # Compare identities as well as commands. Do not retain process argv.
        raw = await self._operator("top", container, "-eo", "pid,stat,args")
        idle = set()
        for row in raw.decode().splitlines()[1:]:
            pid, state, command = row.strip().split(None, 2)
            if state.startswith("Z"):
                continue
            if not pid.isdecimal() or command not in ("sh -c sleep infinity", "sleep infinity"):
                return None
            idle.add((pid, command))
        if not idle or len(idle) > 2:
            return None
        return idle

    async def _scan(self, container, baseline):
        # Direct exec of the image interpreter. Isolated mode ignores the task's
        # Python environment, site packages and current directory.
        value = await self._operator("exec", "-i", "--user", "agent", "--workdir", "/",
                                     container, "/usr/local/bin/python3", "-I", "-S",
                                     "-c", read_bytes(SCANNER, limit=16384).decode(),
                                     payload=json.dumps(baseline).encode())
        return json.loads(value)

    async def start_observation(self, container):
        if not re.fullmatch("[a-f0-9]{64}", container):
            raise ValueError("Invalid workload container")
        self._case_container = container
        self._case_idle = await self._idle(container)
        if not self._case_idle:
            raise ValueError("Staged workspace is busy")
        self._case_baseline = (await self._scan(container, None))["baseline"]
        inputs = Path(self.environment_dir) / "input"
        expected = {p.relative_to(inputs).as_posix(): hashlib.sha256(read_bytes(p)).hexdigest()
                    for p in regular_tree(inputs)} if inputs.exists() else {}
        observed = {name.removeprefix("input/"): item["sha256"] for name, item in self._case_baseline.items()
                    if name.startswith("input/") and item["type"] == "file"}
        if expected != observed:
            raise ValueError("Container inputs differ from staged case")
        self._case_input_count = len(observed)
        if await self._idle(container) != self._case_idle:
            raise ValueError("Staged workspace changed during capture")

    async def before_agent_disposal(self, final):
        # Always write incomplete first. Cancellation or a failed scan must
        # never leave an empty changes list that looks like a successful scan.
        dest = Path(self.trial_paths.trial_dir) / "operator/workspace-observation.json"
        write_json(dest, {"status": "incomplete", "reason": "collection_interrupted"})
        try:
            cid = self._case_container
            if cid != final["agent_id"]:
                raise ValueError("Container identity changed")
            async with asyncio.timeout(10):
                while await self._idle(cid) != self._case_idle:
                    await asyncio.sleep(.1)
            baseline = self._case_baseline
            result = await self._scan(cid, baseline)
            if await self._idle(cid) != self._case_idle:
                raise ValueError("Workload started during collection")
            if getattr(self, "interrupt_observation", False):
                raise InterruptedError("Qualification interruption before publication")
            from base64 import b64decode
            from skillevaluator.utils.redaction import is_sensitive_key, redact_printable_text
            from skillevaluator.tier3.harbor.secure_docker_environment import _redact
            rows = result["changes"]
            def clean(value):
                return _redact(redact_printable_text(value), self._pilot_secrets, include_short=True)
            for row in rows:
                parts = Path(row["path"]).parts
                protected = any(is_sensitive_key(p) or p.startswith(".env") or p in
                                (".ssh", ".aws", ".gnupg", ".git", ".netrc", ".npmrc", ".pypirc")
                                or p.endswith((".key", ".pem", ".p12", ".pfx")) for p in parts)
                if protected or clean(row["path"]) != row["path"]:
                    raise ValueError("Protected path")
                if "data" in row:
                    content = b64decode(row.pop("data"), validate=True)
                    if hashlib.sha256(content).hexdigest() != row["sha256"]:
                        raise ValueError("Content receipt mismatch")
                    text = content.decode()
                    if any(ord(ch) < 32 and ch not in "\r\n\t" for ch in text):
                        raise ValueError("Unsupported binary change")
                    row["text"] = clean(text)
                    row["redacted"] = row["text"] != text
            ready = dest.with_suffix(".ready")
            write_json(ready, {"status": "complete", "root": "/workspace", "changes": rows,
                               "baseline_input_files": self._case_input_count,
                               "baseline_sha256": hashlib.sha256(json.dumps(baseline, sort_keys=True).encode()).hexdigest()})
            os.replace(ready, dest)
        except (AttributeError, KeyError, OSError, TimeoutError, ValueError) as error:
            write_json(dest, {"status": "incomplete", "reason": type(error).__name__})
