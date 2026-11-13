"""Read-only native verifier observations; no alternate grader or reward writer."""
import hashlib
import json
from pathlib import Path
import shlex
import subprocess

from codex_pilot_environment import PilotEnvironment


class ObservedVerifierEnvironment(PilotEnvironment):
    async def exec(self, command, cwd=None, env=None, timeout_sec=None, user=None):
        if self._pilot_agent:
            return await super().exec(command, cwd=cwd, env=env, timeout_sec=timeout_sec, user=user)
        # The existing public exec boundary also covers chmod/setup calls. Observe
        # every call, so there is no command-name or fixture-specific dispatch.
        before = await self._identity_observation('before', command)
        try:
            return await super().exec(command, cwd=cwd, env=env, timeout_sec=timeout_sec, user=user)
        finally:
            after = await self._identity_observation('after', command)
            target = Path(self.trial_paths.trial_dir) / 'operator/verifier-identity.jsonl'
            target.parent.mkdir(exist_ok=True)
            with target.open('a') as stream:
                stream.write(json.dumps({'before': before, 'after': after}) + '\n')

    async def _identity_observation(self, stage, command):
        code = '''import hashlib,json,os
from pathlib import Path
files={}
total=0
for base in ('/tests','/logs/verifier'):
 for p in sorted(Path(base).rglob('*')):
  if p.is_file() and not p.is_symlink():
   s=p.stat()
   if s.st_size > 1048576: continue
   total += s.st_size
   if len(files)>=256 or total>8388608: raise ValueError('Diagnostic evidence budget')
   raw=p.read_bytes()
   files[str(p)]={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'mtime_ns':s.st_mtime_ns,'inode':s.st_ino}
   if p.name in ('entry.json','skill_evaluator_reward.json','custom_reward.json'):
    files[str(p)]['json']=json.loads(raw)
print(json.dumps({'cwd':os.getcwd(),'uid':os.getuid(),'tests_env':os.environ.get('HARBOR_TESTS_DIR'),'files':files}))'''
        result = await super().exec(command='python3 -c ' + shlex.quote(code), user='root', timeout_sec=30)
        if result.return_code:
            raise ValueError('Verifier identity observation unavailable')
        ps = await self._run_docker_compose_command(['ps', '-q', 'main'])
        identifier = ps.stdout.strip()
        inspected = json.loads(subprocess.check_output(['docker', 'inspect', identifier], text=True, timeout=30))[0]
        return {'stage': stage, 'command': command, 'command_sha256': hashlib.sha256(command.encode()).hexdigest(),
                'container_id': identifier, 'image_id': inspected['Image'],
                'mounts': [{'source_sha256': hashlib.sha256(m['Source'].encode()).hexdigest(),
                            'source_is_current_trial': Path(m['Source']).is_relative_to(self.trial_paths.trial_dir),
                            'destination': m['Destination']} for m in inspected['Mounts']],
                'observation': json.loads(result.stdout)}
