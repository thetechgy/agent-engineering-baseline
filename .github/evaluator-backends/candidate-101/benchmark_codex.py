"""Codex adapter for the SkillEvaluator 1.0.1 benchmark candidate."""

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shlex

from skillevaluator.tier3.harbor.installed_agents import SkillEvaluatorCodex
from skillevaluator.tier3_environments import EnvironmentBackendSpec


def backend_spec():
    return EnvironmentBackendSpec(
        import_path="skillevaluator.tier3.harbor.secure_docker_environment:SkillEvaluatorSecureDockerEnvironment",
        agent_import_paths={"codex": "aeb_gh_fixture.benchmark_codex:BenchmarkCodex"},
        supports_docker_compose=True,
    )


NATIVE_SESSION_LOGS = "codex-native"
CODEX_MODEL = "gpt-6.2-sol"
CODEX_VERSION = "0.171.0"
CATALOG = Path(__file__).with_name("codex-catalog") / "models.json"
CATALOG_SHA256 = "fd533349d25b61d61028a80f4a8c2c5388895490d7116bc39e2e407b6c972095"
REMOTE_CATALOG_DIR = "/opt/aeb-benchmark-codex"
REMOTE_CATALOG = REMOTE_CATALOG_DIR + "/models.json"


class BenchmarkCodex(SkillEvaluatorCodex):
    _exec_completed = False

    async def exec_as_agent(self, environment, command, *args, **kwargs):
        logs = self.environment_logs_dir
        original = shlex.quote((logs / "sessions").as_posix())
        native_logs = shlex.quote((logs / NATIVE_SESSION_LOGS).as_posix())
        native = shlex.quote((logs / NATIVE_SESSION_LOGS / "sessions").as_posix())

        # Harbor 0.25.0 replaces its entire destination. SkillEvaluator
        # projects an empty skill directory inside that destination, which
        # the trial user cannot remove. Preserve it and redirect the exact
        # save and resume fragments to a sibling directory.
        save = (
            f"mkdir -p {logs.as_posix()}\n"
            'if [ -d "$CODEX_HOME/sessions" ]; then\n'
            f"  rm -rf {original}\n"
            f'  cp -R "$CODEX_HOME/sessions" {original}\n'
            "fi"
        )
        if command == save:
            command = f"test ! -L {native_logs} && mkdir -p -- {native_logs} || exit 1\n" + save.replace(original, native)
        elif self._resume or self._load:
            resume = (
                f"\nif [ ! -d {original} ]; then\n"
                '  echo "Cannot resume Codex: no previous session logs found" >&2\n'
                "  exit 1\n"
                "fi\n"
                'rm -rf "$CODEX_HOME/sessions"\n'
                f'cp -R {original} "$CODEX_HOME/sessions"'
            )
            if command.endswith(resume):
                command = command.removesuffix(resume) + resume.replace(original, native)
        return await super().exec_as_agent(environment, command, *args, **kwargs)

    def _get_session_dir(self, logs_dir=None):
        logs = self.logs_dir if logs_dir is None else logs_dir
        if logs == self.logs_dir:
            # Streamed session snapshots have Harbor's ordinary layout and a
            # separate temporary root. Only the mounted execution uses ours.
            logs = logs / NATIVE_SESSION_LOGS
            if logs.is_symlink() or (logs / "sessions").is_symlink():
                return None
        return super()._get_session_dir(logs)

    def _convert_events_to_trajectory(self, sessions):
        trajectory = super()._convert_events_to_trajectory(sessions)
        if trajectory is not None and not self._exec_completed:
            return trajectory.model_copy(update={"final_metrics": None})
        return trajectory

    def build_cli_flags(self):
        catalog = shlex.quote("model_catalog_json=" + json.dumps(REMOTE_CATALOG))
        return super().build_cli_flags() + " --disable code_mode -c " + catalog

    async def install_catalog(self, environment):
        if self._resolved_model_name() != CODEX_MODEL or self._version != CODEX_VERSION:
            raise RuntimeError("Unexpected model or CLI for the reviewed direct-tool catalog")
        if CATALOG.is_symlink() or hashlib.sha256(CATALOG.read_bytes()).hexdigest() != CATALOG_SHA256:
            raise RuntimeError("Codex model catalog differs from its reviewed bytes")

        created = await self.exec_as_root(environment, command=(
            f'test "$(find /opt -maxdepth 0 -type d -uid 0 ! -perm /022 -print)" = /opt '
            f'&& mkdir -m 0755 -- {REMOTE_CATALOG_DIR}'
        ))
        if created.return_code != 0:
            raise RuntimeError("Could not create a protected Codex catalog directory")
        await environment.upload_file(CATALOG, REMOTE_CATALOG)
        checked = await self.exec_as_root(environment, command=(
            f'test -f {REMOTE_CATALOG} && test ! -L {REMOTE_CATALOG} '
            f'&& chown 0:0 -- {REMOTE_CATALOG} && chmod 0444 -- {REMOTE_CATALOG} '
            f'&& printf "%s  %s\n" {CATALOG_SHA256} {REMOTE_CATALOG} | sha256sum --check --strict'
        ))
        if checked.return_code != 0:
            raise RuntimeError("Could not verify the protected Codex catalog")

    async def run(self, instruction, environment, context):
        self._exec_completed = False
        await self.install_catalog(environment)
        created = await self.exec_as_agent(
            environment,
            command='home=$(getent passwd "$(id -u)" | cut -d: -f6) && '
                    'test -n "$home" && umask 077 && mktemp -d -- "$home/.codex-benchmark.XXXXXXXX"',
        )
        target = (created.stdout or "").strip()
        if created.return_code or not re.fullmatch(r"/home/agent/\.codex-benchmark\.[A-Za-z0-9]{8}", target):
            raise RuntimeError("Could not allocate isolated agent-owned Codex home")
        self._REMOTE_CODEX_HOME = PurePosixPath(target)
        await super().run(instruction, environment, context)
        self._exec_completed = True
