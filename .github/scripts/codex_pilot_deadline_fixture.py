"""Credential-free controls only; never selected by production agent configuration."""
import asyncio
import json
import os
import shlex
import time
from evaluation_codex import CampaignCodex


class DeadlineCodex(CampaignCodex):
    def __init__(self, *args, deadline_fixture, **kwargs):
        assert os.environ.get('AEB_PILOT_PROBE') == '1' and not kwargs.get('live')
        assert deadline_fixture in ('emitted', 'empty', 'secondary', 'cancelled')
        self.deadline_fixture = deadline_fixture
        super().__init__(*args, **kwargs)

    async def run(self, instruction, environment, context):
        os.environ['AEB_PILOT_SCENARIO'] = 'native-empty' if self.deadline_fixture == 'empty' else 'native-deadline'
        if self.deadline_fixture == 'secondary':
            # A real failed stopped-container copy, not an exception substituted for execution.
            environment._deadline_copy_fault = True
        witness = None
        started = time.monotonic()
        source = """import hashlib,json
from pathlib import Path
p=Path('/workspace/output/Subject.Tests.ps1')
s=Path('/logs/agent/codex.txt')
e=Path('/logs/agent/codex-stderr.txt')
if p.is_file() and s.is_file() and e.is_file():
 events=[]
 for line in s.read_text().splitlines():
  try: events.append(json.loads(line))
  except ValueError: pass
 emitted=any(v.get('type')=='item.completed' and v.get('item',{}).get('type')=='command_execution' and 'native-deadline-evidence' in v['item'].get('aggregated_output','') for v in events)
 if emitted and 'native-deadline-stderr' in e.read_text():
  print(json.dumps({'events_emitted':True,'stderr_emitted':True,'submission_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'submission_bytes':p.stat().st_size}))
"""
        async def observe_emission():
            nonlocal witness
            while witness is None:
                try:
                    result = await environment.exec(command='python3 -c ' + shlex.quote(source), user='agent', timeout_sec=3)
                    if result.return_code == 0 and result.stdout:
                        witness = dict(json.loads(result.stdout), observed_elapsed_seconds=round(time.monotonic()-started,3))
                        return
                except Exception:
                    pass
                await asyncio.sleep(.25)
        observer = asyncio.create_task(observe_emission())
        try:
            return await super().run(instruction, environment, context)
        finally:
            observer.cancel()
            try: await observer
            except asyncio.CancelledError: pass
            target = self.logs_dir.parent / 'operator/pilot-runtime.json'
            if target.exists():
                audit = json.loads(target.read_text())
                audit['deadline_fixture_witness'] = witness
                target.write_text(json.dumps(audit, indent=2)+'\n')

    def fixture_commands(self, payload):
        return [f"printf %s {payload} | base64 -d > {self.output}; "
                "printf 'native-deadline-evidence\\n'; "
                "printf 'native-deadline-stderr OPENAI_API_KEY=fixture-redaction-sentinel\\n' >> /logs/agent/codex-stderr.txt; "
                "(sleep 100; touch /workspace/output/deadline-descendant-survived) &"]
