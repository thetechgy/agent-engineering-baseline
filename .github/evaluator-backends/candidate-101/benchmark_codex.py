"""Codex adapter for the SkillEvaluator 1.0.1 benchmark candidate."""

from pathlib import PurePosixPath
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
        return super().build_cli_flags() + " --disable code_mode"

    async def run(self, instruction, environment, context):
        self._exec_completed = False
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
