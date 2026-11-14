"""Secure startup followed by trusted initialization, before Harbor agent setup."""

import asyncio
import importlib.metadata
import json
import os
import stat
import sys
from pathlib import Path

from skillevaluator.tier3.harbor.secure_docker_environment import SkillEvaluatorSecureDockerEnvironment
from . import MANIFEST_ENV
from .manifest import approve, payload_digest

COMMAND = "/usr/local/bin/python3 -I /opt/aeb-gh/initialize.py"
VERIFY_COMMAND = COMMAND + " --verify"


def require_runtime():
    """Only the two reviewed owning pairs; newer versions require qualification."""
    pair = (importlib.metadata.version("skillevaluator"), importlib.metadata.version("harbor"))
    python = tuple(sys.version_info[:3])
    if not ((pair == ("0.7.2", "0.24.0") and python[:2] == (3, 13))
            or (pair == ("0.8.0", "0.24.0") and python == (3, 14, 10))):
        raise RuntimeError("Unqualified gh backend owning runtime")


class TrustedGhEnvironment(SkillEvaluatorSecureDockerEnvironment):
    async def start(self, force_build):
        if not hasattr(self, "_aeb_start_lock"):
            self._aeb_start_lock = asyncio.Lock()
        async with self._aeb_start_lock:
            await self._start_locked(force_build)

    async def _start_locked(self, force_build):
        status = {"status": "infrastructure_error", "initializer": payload_digest()}
        # Host trial root is outside all agent mounts (agent logs are a child).
        target = self.trial_paths.trial_dir / "gh-initialization.jsonl"
        def record():
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
            with os.fdopen(fd, "a") as stream:
                info = os.fstat(stream.fileno())
                if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.geteuid()
                        or info.st_mode & 0o077 or info.st_size > 64 * 1024):
                    raise RuntimeError("Unsafe gh initialization evidence file")
                stream.write(json.dumps(status, sort_keys=True) + "\n")
        try:
            require_runtime()
            # Only the declared operator host variable can select the sealed manifest.
            row, manifest = approve(os.environ.get(MANIFEST_ENV, ""), self.environment_dir.parent)
            status.update(manifest=manifest, case=row["case"], arm=row["arm"], checksum=row["checksum"])
            repeated = getattr(self, "_aeb_ready", False)
            if getattr(self, "_aeb_failed", False):
                raise RuntimeError("Failed gh initialization requires a new trial")
            if repeated and force_build:
                raise RuntimeError("Refusing to rebuild an initialized gh trial")
            if not repeated:
                await super().start(force_build)
            async with asyncio.timeout(30):
                # Revalidate after startup; changed contexts cannot initialize.
                approve(os.environ.get(MANIFEST_ENV, ""), self.environment_dir.parent)
                created = await self.exec("/usr/bin/install -d -m 700 -o root -g root /opt/aeb-gh", user="root", timeout_sec=5)
                if created.return_code:
                    raise RuntimeError("Cannot create private initializer directory")
                await self.upload_file(Path(__file__).with_name("initialize.py"), "/opt/aeb-gh/initialize.py")
                # The fixed JSON payload has no executable/command fields.
                approval = self.trial_paths.trial_dir / "gh-approved.json"
                approval.write_text(json.dumps(row["private"], sort_keys=True))
                approval.chmod(0o600)
                await self.upload_file(approval, "/opt/aeb-gh/approved.json")
                owned = await self.exec("/usr/bin/chown -R root:root /opt/aeb-gh && /usr/bin/chmod 700 /opt/aeb-gh && /usr/bin/chmod 600 /opt/aeb-gh/*.py /opt/aeb-gh/*.json", user="root", timeout_sec=5)
                if owned.return_code:
                    raise RuntimeError("Cannot protect initializer payload")
                result = await self.exec(VERIFY_COMMAND if repeated else COMMAND, user="root", timeout_sec=28)
                if result.return_code or len(result.stdout or "") > 1024:
                    try:
                        diagnostic = json.loads((result.stdout or "")[:1024])
                        if (set(diagnostic) == {"status", "phase", "error"} and diagnostic["status"] == "infrastructure_error"
                                and diagnostic["phase"] in {"operator", "private_inputs", "resume", "spawn", "readiness"}
                                and diagnostic["error"] in {"RuntimeError", "ValueError", "OSError", "FileNotFoundError", "PermissionError", "TimeoutError", "ConnectionRefusedError", "ProcessLookupError", "JSONDecodeError", "Exception"}):
                            status["failure"] = diagnostic
                    except (ValueError, TypeError):
                        pass
                    raise RuntimeError("Trusted gh initialization failed")
                identity = json.loads(result.stdout)
                if (set(identity) != {"status", "pid", "start", "uid", "socket_inode"}
                        or identity["status"] != "ready" or type(identity["uid"]) is not int or identity["uid"] != 0
                        or type(identity["pid"]) is not int or identity["pid"] <= 0
                        or type(identity["socket_inode"]) is not int or identity["socket_inode"] <= 0
                        or type(identity["start"]) is not str or not identity["start"].isdecimal()):
                    raise RuntimeError("Invalid gh broker identity")
                if repeated and identity != self._aeb_broker_identity:
                    raise RuntimeError("Repeated startup changed the approved gh broker")
                self._aeb_broker_identity = identity
                self._aeb_ready = True
                status.update(status="ready", broker=identity)
        except BaseException as error:
            self._aeb_failed = True
            status["status"] = "cancelled" if isinstance(error, asyncio.CancelledError) else "infrastructure_error"
            record()
            raise
        record()
