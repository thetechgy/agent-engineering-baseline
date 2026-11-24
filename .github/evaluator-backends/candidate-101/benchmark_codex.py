"""Codex adapter for the SkillEvaluator 1.0.1 benchmark candidate."""

from pathlib import PurePosixPath
import re

from skillevaluator.tier3.harbor.installed_agents import SkillEvaluatorCodex
from skillevaluator.tier3_environments import EnvironmentBackendSpec


def backend_spec():
    return EnvironmentBackendSpec(
        import_path="skillevaluator.tier3.harbor.secure_docker_environment:SkillEvaluatorSecureDockerEnvironment",
        agent_import_paths={"codex": "aeb_gh_fixture.benchmark_codex:BenchmarkCodex"},
        supports_docker_compose=True,
    )


class BenchmarkCodex(SkillEvaluatorCodex):
    _exec_completed = False

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
