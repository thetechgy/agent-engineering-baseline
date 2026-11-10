"""Pilot-only adaptation of the pinned secure Docker transport; no host mounts.

Harbor's public import_path selects this class. Network policy and containment
remain inherited. Container-local logs, stdin environment delivery as the target
user, and bounded stopped-container retention avoid host mounts and CAP_CHOWN.
Private lifecycle helpers are pinned by the pilot input manifest.
"""
import asyncio
import hashlib
import io
import json
import os
import signal
import shutil
import tarfile
import time
from pathlib import Path

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
        self._pilot_interrupted = False
        self._pilot_evidence = None
        self._pilot_secrets = set()
        self._pilot_stages = []
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
        self._pilot_secrets.update(secrets)
        if secrets:
            _collision_safe_redaction_marker(secrets, include_short=True)
        argv = ['exec', '-T']
        if cwd or self.task_env_config.workdir:
            argv += ['-w', cwd or self.task_env_config.workdir]
        if user is not None:
            argv += ['-u', str(user)]
        argv += ['main', 'sh', '-s']
        # Use an actual asyncio deadline, like Harbor's agent deadline. The pinned
        # transport's own deadline otherwise raises an untyped RuntimeError.
        async with asyncio.timeout(timeout_sec or None):
            return await self._run_docker_compose_command(
                argv, check=False, timeout_sec=None,
                stdin_data=(_render_environment_script(merged) + '\n' + command + '\n').encode(),
                additional_secret_values=secrets, exact_secret_values=secrets,
                on_output=self._output_callback(), stop_main_on_interrupt=True)

    def retain_on_interrupt(self, output):
        if not output.startswith('/workspace/output/') or Path(output).parent.as_posix() != '/workspace/output':
            raise ValueError('Unapproved submission path')
        self._pilot_evidence = output

    def _stage(self, stage, **values):
        self._pilot_stages.append({'stage': stage, 'monotonic_seconds': round(time.monotonic(), 6), **values})
        target = Path(self.trial_paths.trial_dir) / 'operator/pilot-lifecycle.json'
        try:
            target.parent.mkdir(exist_ok=True)
            target.write_text(json.dumps({'stages': self._pilot_stages}, indent=2) + '\n')
        except OSError:
            pass  # Diagnostic storage must never prevent containment/disposal.

    async def _copy_stopped_file(self, container, source, limit):
        """Bound a single Docker cp tar in memory; never extract untrusted paths."""
        creation = asyncio.create_task(asyncio.create_subprocess_exec(
            shutil.which('docker'), 'cp', '--', container + ':' + source, '-',
            env=self._trusted_compose_client_environment(excluded_names=set(), excluded_values=self._pilot_secrets),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            start_new_session=True))
        try:
            process = await asyncio.shield(creation)
        except asyncio.CancelledError:
            from skillevaluator.tier3.harbor.secure_docker_environment import _await_task_uninterruptibly
            process = await _await_task_uninterruptibly(creation, preserve_cancellation=False)
            os.killpg(process.pid, signal.SIGKILL)
            await asyncio.wait_for(process.wait(), 5)
            raise
        try:
            async with asyncio.timeout(5):
                chunks = bytearray()
                while chunk := await process.stdout.read(65536):
                    chunks.extend(chunk)
                    if len(chunks) > limit + 65536:
                        raise ValueError('Evidence transfer size limit')
                if await process.wait():
                    raise ValueError('Evidence file unavailable')
            with tarfile.open(fileobj=io.BytesIO(chunks), mode='r:') as archive:
                members = archive.getmembers()
                if len(members) != 1 or not members[0].isfile() or members[0].size > limit:
                    raise ValueError('Unsafe evidence member')
                return archive.extractfile(members[0]).read(limit + 1)
        finally:
            if process.returncode is None:
                os.killpg(process.pid, signal.SIGKILL)
                await asyncio.wait_for(process.wait(), 5)

    async def _contain_main_container(self):
        """Pinned private hook: kill all work, copy allowlisted data, then Harbor disposes.

        No restart, exec, runtime home or host mount is needed. If stopping cannot
        be confirmed, fall back to the inherited forced removal before raising.
        """
        if not self._pilot_agent:
            return await super()._contain_main_container()
        self._pilot_interrupted = True
        self._stage('containment_started')
        try:
            snapshot = await self._stop_raw_service_containers('main', remove=False, require_existing=True)
        except BaseException:
            await super()._contain_main_container()
            raise
        self._stage('workload_stopped', container_ids=list(snapshot.all_identities))
        if not self._pilot_evidence:
            return
        # A failed copy must not escape into native cancellation or skip disposal.
        from skillevaluator.utils.redaction import redact_sensitive_text
        from skillevaluator.tier3.harbor.secure_docker_environment import _redact
        base = Path(self.trial_paths.trial_dir)
        files = [(name, '/logs/agent/' + name, 16*1024*1024) for name in ('codex.txt', 'codex-stderr.txt', 'probe.json')]
        files.append(('submission', self._pilot_evidence, 65536))
        for name, source, limit in files:
            try:
                if getattr(self, '_deadline_copy_fault', False) and name == 'codex-stderr.txt':
                    source = '/logs/agent/deliberately-absent-diagnostic'
                raw = await self._copy_stopped_file(snapshot.all_identities[0], source, limit)
                clean = _redact(redact_sensitive_text(raw.decode(errors='replace')), self._pilot_secrets, include_short=True)
                if name == 'submission':
                    receipt = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw),
                               'complete': False, 'source': 'stopped-container', 'container_id': snapshot.all_identities[0]}
                    target = base / 'operator/interrupted-submission' / Path(source).name
                    if clean.encode() != raw:
                        raise ValueError('Submission requires protected retention')
                    (base / 'operator/interrupted-submission.json').write_text(json.dumps(receipt) + '\n')
                    data = raw
                else:
                    target = base / 'agent' / name
                    data = clean.encode()
                target.parent.mkdir(parents=True, exist_ok=True)
                # Replace directory entries rather than following existing links.
                temporary = target.with_suffix('.retaining')
                with temporary.open('xb') as stream:
                    stream.write(data)
                os.replace(temporary, target)
                self._stage('evidence_retained', member=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
            except Exception as error:
                self._stage('collection_failed', member=name, error=type(error).__name__)

    async def download_dir(self, source_dir, target_dir):
        if self._pilot_agent and self._pilot_interrupted and str(source_dir) == '/logs/agent':
            return  # The stopped-container allowlist has already been retained.
        return await super().download_dir(source_dir, target_dir)

    async def stop(self, delete):
        if not self._pilot_agent:
            return await super().stop(delete)
        if self._pilot_interrupted:
            try:
                self._stage('disposal_started')
                async with asyncio.timeout(60):
                    await super().stop(delete)
                self._stage('disposal_complete')
            except BaseException as error:
                self._stage('cleanup_failed', error=type(error).__name__)
                raise
            return
        # Observe the real post-phase policy immediately before inherited disposal.
        # Cleanup runs even if the observation or delayed child probe fails.
        try:
            from codex_pilot_boundary import observe
            final = await observe(self)
            if os.environ.get('AEB_PILOT_PROBE') == '1' and os.environ.get('AEB_PILOT_SCENARIO', 'success') == 'success':
                result = await self.exec(user='agent', timeout_sec=60, command=(
                    'touch /tmp/pilot-after-agent; '
                    'for i in $(seq 1 55); do '
                    'if test -f /logs/agent/late-policy.json; then cat /logs/agent/late-policy.json; exit 0; fi; '
                    'sleep 1; done; exit 1'))
                if result.return_code:
                    raise ValueError('Post-agent CLI child network observation unavailable')
                late = json.loads(result.stdout)
                rows = late.get('network', [])
                if len(rows) != 3 or rows[0]['http_code'] != '401' or any(v['returncode'] not in (35, 52, 56, 97) for v in rows[1:]):
                    raise ValueError('Post-agent CLI child policy enforcement failed')
                final['late_cli_child'] = late
            target = Path(self.trial_paths.trial_dir) / 'operator/pilot-final-policy.json'
            target.write_text(json.dumps(final, indent=2) + '\n')
        finally:
            await super().stop(delete)
