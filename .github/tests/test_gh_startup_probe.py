"""Startup diagnostic delegation and primary-failure preservation; no Docker."""
import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.github/scripts'))


@unittest.skipUnless(importlib.util.find_spec('aeb_gh_fixture'), 'Owning native backend required')
class StartupProbe(unittest.TestCase):
    def test_observer_returns_original_result_and_bounds_sanitized_streams(self):
        from gh_initializer_validation import startup_observer
        from aeb_gh_fixture.backend import COMMAND
        result=SimpleNamespace(return_code=23,stdout='x'*5000,stderr='\x1b[31mfailed\x00\n')
        seen=[]
        class Parent:
            async def exec(self,*args,**kwargs):
                seen.append((args,kwargs));return result
        records=[];environment=startup_observer(Parent,records)()
        actual=asyncio.run(environment.exec(COMMAND,user='root',timeout_sec=28))
        self.assertIs(actual,result)
        self.assertEqual(seen,[((COMMAND,),{'user':'root','timeout_sec':28})])
        self.assertEqual(records,[{'operation':'initialize','status':'complete','returncode':23,
            'stdout':'x'*4096,'stderr':'failed\n','stdout_truncated':True,'stderr_truncated':False}])
        asyncio.run(environment.exec('private payload not retained',user='root'))
        self.assertEqual(len(records),1)

    def test_startup_failure_survives_failed_cleanup_with_pending_receipt(self):
        from gh_initializer_validation import startup_attempt
        primary=RuntimeError('initializer failed')
        cleanup=OSError('teardown failed')
        environment=SimpleNamespace(start=AsyncMock(side_effect=primary),stop=AsyncMock(side_effect=cleanup))
        states=[]
        def retain(value):states.append(dict(value))
        with self.assertRaises(RuntimeError) as raised:
            asyncio.run(startup_attempt(environment,inspect_image=lambda: {},cleanup_check=lambda:None,retain=retain))
        self.assertIs(raised.exception,primary)
        self.assertEqual(states[0]['cleanup'],'pending')
        self.assertEqual(states[-1]['primary_error'],'RuntimeError')
        self.assertEqual(states[-1]['cleanup_error'],'OSError')
        self.assertEqual(states[-1]['status'],'failed')
        environment.start.assert_awaited_once_with(False)
        environment.stop.assert_awaited_once_with(delete=True)

    def test_evidence_failure_cannot_skip_cleanup_or_replace_primary(self):
        from gh_initializer_validation import startup_attempt
        primary=RuntimeError('initializer failed')
        environment=SimpleNamespace(start=AsyncMock(side_effect=primary),stop=AsyncMock())
        def unavailable(_value):raise OSError('retention unavailable')
        with self.assertRaises(RuntimeError) as raised:
            asyncio.run(startup_attempt(environment,inspect_image=lambda:{},cleanup_check=lambda:None,retain=unavailable))
        self.assertIs(raised.exception,primary)
        environment.stop.assert_awaited_once_with(delete=True)

    def test_diagnostic_failure_retains_primary_and_still_cleans_environment(self):
        from gh_initializer_validation import startup_attempt
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'gh-initialization.jsonl'
            async def start(force):
                with path.open('a') as stream:stream.write(json.dumps({'status':'ready','broker':{'pid':123}})+'\n')
            error=RuntimeError('diagnostic failed');states=[]
            env=SimpleNamespace(start=start,stop=AsyncMock(),trial_paths=SimpleNamespace(trial_dir=root))
            with self.assertRaises(RuntimeError) as raised:
                asyncio.run(startup_attempt(env,inspect_image=lambda:{},cleanup_check=lambda:None,
                    retain=lambda row:states.append(dict(row)),diagnose=AsyncMock(side_effect=error)))
            self.assertIs(raised.exception,error)
            self.assertEqual(states[-1]['status'],'failed');self.assertEqual(states[-1]['cleanup'],'complete')
            env.stop.assert_awaited_once_with(delete=True)

    def test_repeated_startup_requires_exact_broker_identity_and_cleanup(self):
        from gh_initializer_validation import startup_attempt
        for drift in (False,True):
            with self.subTest(drift=drift),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);path=root/'gh-initialization.jsonl';calls=[]
                identity={'status':'ready','broker':{'pid':123,'start':'20'}}
                async def start(force):
                    calls.append(force)
                    value=dict(identity)
                    if drift and len(calls)==2:value['broker']={'pid':124,'start':'21'}
                    with path.open('a') as stream:stream.write(json.dumps(value)+'\n')
                env=SimpleNamespace(start=start,stop=AsyncMock(),trial_paths=SimpleNamespace(trial_dir=root))
                if drift:
                    with self.assertRaisesRegex(RuntimeError,'identity drift'):
                        asyncio.run(startup_attempt(env,inspect_image=lambda:{'image':'sha256:fixture'},cleanup_check=lambda:None,retain=lambda r:None))
                else:
                    result=asyncio.run(startup_attempt(env,inspect_image=lambda:{'image':'sha256:fixture'},cleanup_check=lambda:None,retain=lambda r:None))
                    self.assertTrue(result['repeated_identity_equal']);self.assertEqual(result['cleanup'],'complete')
                self.assertEqual(calls,[False,False]);env.stop.assert_awaited_once_with(delete=True)


if __name__=='__main__':unittest.main()
