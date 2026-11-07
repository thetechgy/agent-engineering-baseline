"""Pilot-only adaptation of the pinned secure Docker transport; no host mounts.

Harbor's public import_path selects this class. Network policy and lifecycle are
inherited. The two compatibility changes use container-local logs (Harbor's
non-mounted collector) and stdin environment delivery as the target user, avoiding
CAP_CHOWN. Private transport helpers are pinned by the pilot input manifest.
"""
from skillevaluator.tier3.harbor.secure_docker_environment import (
    SkillEvaluatorSecureDockerEnvironment, _host_handoff_environment,
    _render_environment_script, _eligible_secret_values,
    _sensitive_environment_values, _credential_uri_environment_values,
    _collision_safe_redaction_marker,
)


class PilotEnvironment(SkillEvaluatorSecureDockerEnvironment):
    def __init__(self, *args, **kwargs):
        mounts = kwargs.pop('mounts', ())
        if any(str(m['target']) not in ('/logs/agent', '/logs/verifier', '/logs/artifacts') for m in mounts):
            raise ValueError('Unexpected pilot mount')
        self._pilot_agent = any(str(m['target']) == '/logs/agent' for m in mounts)
        super().__init__(*args, mounts=[] if self._pilot_agent else mounts, **kwargs)

    @property
    def capabilities(self):
        return super().capabilities.model_copy(update={'mounted': False}) if self._pilot_agent else super().capabilities

    async def exec(self, command, cwd=None, env=None, timeout_sec=None, user=None):
        if not self._pilot_agent:
            return await super().exec(command, cwd=cwd, env=env, timeout_sec=timeout_sec, user=user)
        user = self._resolve_user(user)
        merged = self._merge_env(env)
        if not merged:
            return await super().exec(command, cwd=cwd, timeout_sec=timeout_sec, user=user)
        merged = _host_handoff_environment(merged)
        secrets = set(_eligible_secret_values(merged.values()))
        secrets.update(_sensitive_environment_values(merged))
        secrets.update(_credential_uri_environment_values(merged))
        if secrets:
            _collision_safe_redaction_marker(secrets, include_short=True)
        argv = ['exec', '-T']
        if cwd or self.task_env_config.workdir:
            argv += ['-w', cwd or self.task_env_config.workdir]
        if user is not None:
            argv += ['-u', str(user)]
        argv += ['main', 'sh', '-s']
        return await self._run_docker_compose_command(
            argv, check=False, timeout_sec=timeout_sec,
            stdin_data=(_render_environment_script(merged) + '\n' + command + '\n').encode(),
            additional_secret_values=secrets, exact_secret_values=secrets,
            on_output=self._output_callback(), stop_main_on_interrupt=True)
