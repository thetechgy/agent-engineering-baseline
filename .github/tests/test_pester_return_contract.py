"""Frozen candidate source and task-owned control contracts; no inference."""
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.github/scripts'))
from evaluation_tasks import load
from evaluation_campaign import purpose
import skill_evidence as evidence
import skill_reports as reports

BASE = ROOT / '.github/evals/pester-return-contract'

class ReturnContract(unittest.TestCase):
    def test_snapshots_and_frozen_inputs(self):
        frozen = reports.read_json(BASE / 'freeze.json')
        for member, digest in frozen['files'].items():
            raw = (ROOT / member).read_bytes()
            if member == '.github/scripts/evaluation_tasks.py':
                # Project out only additive metadata interfaces and registrations.
                # Every other byte, including all frozen Pester task code, must
                # still match the original manifest. New hook bytes are bound by
                # the source-successor profiles and their launch regressions.
                classes = {n.name:n for n in ast.parse(raw).body if isinstance(n, ast.ClassDef)}
                added = []
                for owner, names in {
                    'Task': {'launch_context', 'validate_launch_context', 'public_policy_fields'},
                    'GhFixture': {'fixture_control', 'validate_result', 'launch_context', 'validate_launch_context'},
                }.items():
                    nodes = [n for n in classes[owner].body if isinstance(n, ast.FunctionDef) and n.name in names]
                    self.assertEqual({n.name for n in nodes}, names)
                    added.extend(nodes)
                lines = raw.splitlines(keepends=True)
                for node in sorted(added, key=lambda n:n.lineno, reverse=True):
                    self.assertEqual(lines[node.end_lineno].strip(), b'')
                    del lines[node.lineno - 1:node.end_lineno + 1]
                # The new task registration is additive and cannot affect a Pester selector.
                loader = next(n for n in ast.parse(raw).body if isinstance(n, ast.FunctionDef) and n.name == 'load')
                hooks = []
                for condition, expected in {
                    "definition.get('adapter') == 'batch-summary-static-templates'":
                        "if definition.get('adapter') == 'batch-summary-static-templates':\n"
                        "        from pester_static_templates_task import StaticTemplateBatchSummary\n"
                        "        adapters['batch-summary-static-templates'] = StaticTemplateBatchSummary",
                    "definition.get('adapter') == 'gh-permission'":
                        "if definition.get('adapter') == 'gh-permission':\n"
                        "        from gh_permission_task import GhPermission\n"
                        "        adapters['gh-permission'] = GhPermission",
                    "definition.get('type') == 'case-observation'":
                        "if definition.get('type') == 'case-observation':\n"
                        "        from case_observation import CaseObservation\n"
                        "        require(path in (ROOT / '.github/evals/campaigns/case-observation.json',\n"
                        "                         ROOT / '.github/evals/campaigns/case-observation-1710.json',\n"
                        "                         ROOT / '.github/evals/campaigns/case-observation-1720.json'),\n"
                        "                'Unregistered observation')\n"
                        "        return CaseObservation(definition, path.relative_to(ROOT).as_posix())",
                    "definition.get('type') == 'judge-only'":
                        "if definition.get('type') == 'judge-only':\n"
                        "        from judge_calibration_inputs import load as load_judges\n"
                        "        return load_judges(path, definition)",
                }.items():
                    matched = [n for n in loader.body if isinstance(n, ast.If)
                        and ast.get_source_segment(raw.decode(), n.test) == condition]
                    self.assertEqual(len(matched), 1)
                    self.assertEqual(ast.get_source_segment(raw.decode(), matched[0]), expected)
                    hooks.extend(matched)
                for node in sorted(hooks, key=lambda n:n.lineno, reverse=True):
                    del lines[node.lineno - 1:node.end_lineno]
                raw = b''.join(lines)
                # Project only the shared extension hook. Task registrations
                # can change without adding exclusions to this frozen hash.
                extension = (
                    b"    from evaluation_registration import family_for_definition, registered_file\n"
                    b"    member = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else None\n"
                    b"    family = family_for_definition(ROOT, member)\n"
                    b"    adapter = definition.get('adapter')\n"
                    b"    require(adapter in adapters if family is None else adapter == family.adapter and definition.get('skill') == family.skill,\n"
                    b"            'Unsupported task adapter')\n"
                )
                extension_dispatch = (
                    b"    if family is None:\n"
                    b"        return adapters[adapter](definition, member)\n"
                    b"    module = registered_file(ROOT, path.with_name('task.py'))\n"
                    b"    implementation = runpy.run_path(str(module))[family.class_name]\n"
                    b"    require(isinstance(implementation, type) and issubclass(implementation, Task), 'Invalid task adapter class')\n"
                    b"    return implementation(definition, member)\n"
                )
                projections = {
                    b'import runpy\n': b'',
                    extension: b"    require(definition.get('adapter') in adapters, 'Unsupported task adapter')\n",
                    b"(path.is_relative_to(ROOT / '.github/evals/campaigns') or family is not None)":
                        b"path.is_relative_to(ROOT / '.github/evals/campaigns')",
                    extension_dispatch: b"    return adapters[definition['adapter']](definition, path.relative_to(ROOT).as_posix())\n",
                }
                for hook, previous in projections.items():
                    self.assertEqual(raw.count(hook), 1)
                    raw = raw.replace(hook, previous)
                for default in (b'    trusted_launch_metadata = False\n', b'    trusted_launch_metadata = True\n',
                                b'    diagnostic_observation = False\n'):
                    self.assertEqual(raw.count(default), 1)
                    raw = raw.replace(default, b'')
            self.assertEqual(hashlib.sha256(raw).hexdigest(), digest, member)
        current = BASE / 'variants/current/powershell-pester-6'
        candidate = BASE / 'variants/candidate/powershell-pester-6'
        self.assertEqual({p.relative_to(current).as_posix(): p.read_bytes() for p in reports.regular_tree(current)},
                         {p.relative_to(ROOT / '.apm/skills/powershell-pester-6').as_posix(): p.read_bytes() for p in reports.regular_tree(ROOT / '.apm/skills/powershell-pester-6')})
        for path in reports.regular_tree(current):
            if path.name != 'SKILL.md': self.assertEqual(path.read_bytes(), (candidate / path.relative_to(current)).read_bytes())
        for case in ('development', 'transfer'):
            definitions=[]
            version='v3' if case=='transfer' else 'v1'
            for variant in ('current', 'candidate'):
                task=load(ROOT / ('.github/evals/campaigns/pester-return-'+case+'-'+variant+'-'+version+'-sol62.json'))
                definitions.append(task.definition)
                self.assertFalse(task.diagnostic_observation)
                self.assertEqual(task.public_policy_fields(), {})
                # The generic hooks add validation, not task metadata or a new
                # Pester execution policy. Both frozen arms retain empty metadata.
                for present in (True, False):
                    self.assertIsNone(task.launch_context(ROOT, ROOT/'unused', present, {}))
                    self.assertEqual(task.validate_launch_context(ROOT, None, present, {}), {})
                    with self.assertRaises(ValueError):task.launch_context(ROOT, ROOT/'unused', present, {'AEB_UNREVIEWED':'1'})
                    with self.assertRaises(ValueError):task.validate_launch_context(ROOT, {'unreviewed':True}, present, {})

                controls=load(ROOT / ('.github/evals/campaigns/pester-return-'+case+'-'+variant+'-controls-'+version+'-sol62.json'))
                for mode in ('oracle','probe'):
                    selected=purpose(controls,mode)
                    profile,_,_=evidence.custom_contract('powershell-pester-6',purpose=selected)
                    self.assertEqual(profile['skill_source']['digest'],evidence.skill_content(ROOT/task.definition['source'])['digest'])
                    inputs = evidence.custom_input_identities(ROOT, 'powershell-pester-6', purpose=selected)
                    self.assertTrue(all(profile[key] == inputs[key] for key in ('grader_digest', 'fixture_digest')))
                from evaluation_campaign_protocol import protocol
                self.assertEqual(protocol(task)['attempt_slots'],6)
            self.assertEqual(definitions[0]['candidate'],definitions[1]['candidate'])
            self.assertEqual(definitions[0]['runtime_profile'],definitions[1]['runtime_profile'])
            self.assertEqual(definitions[0]['trials'],3)
        self.assertEqual(frozen['proposed_attempts'],24)
        transfer=load(ROOT/'.github/evals/campaigns/pester-return-transfer-candidate-controls-v3.json')
        for scenario in ('completed','task-failure','invalid'):
            for position in range(1,7):
                self.assertIn(transfer.fixture_control(scenario,{'position':position}),transfer.controls())


    def test_selected_source_identity_and_tampered_binding(self):
        import copy
        from evaluation_evidence import selected_source, selected_identity
        for variant in ('current','candidate'):
            task=load(ROOT / ('.github/evals/campaigns/pester-return-development-'+variant+'-controls-v1.json'))
            profile,_,_=evidence.custom_contract('powershell-pester-6',purpose=purpose(task,'oracle'))
            original=evidence.source('powershell-pester-6','local','thetechgy/agent-engineering-baseline',
                                     '9f81a66b343f340b681759db8c7c38a4e9e016c5','.apm/skills/powershell-pester-6')
            selected=selected_identity(ROOT,profile,original)
            self.assertEqual(selected['source_path'],task.definition['source'])
            self.assertEqual(selected['content']['digest'],profile['skill_source']['digest'])
            self.assertEqual(original['source_path'],'.apm/skills/powershell-pester-6')
            wrong=copy.deepcopy(profile);wrong['skill_source']['digest']='sha256:'+'0'*64
            with self.assertRaisesRegex(ValueError,'Unregistered campaign skill source'):
                selected_source(ROOT,wrong)

    @unittest.skipUnless(os.environ.get('PESTER_EFFECTIVENESS_LOCAL_SEMANTICS')=='1','Optional pinned local semantics')
    def test_transfer_controls_through_existing_runner_and_grader(self):
        from test_codex_effectiveness import local_semantic_fixture, prospective_grader
        manifest=subprocess.check_output([os.environ.get('CI_PWSH','pwsh'),'-NoProfile','-Command',
            '(Get-Module -ListAvailable Pester | Where-Object Version -EQ 6.2.0 | Select-Object -First 1).Path'],text=True).strip()
        self.assertTrue(manifest)
        task=load(ROOT/'.github/evals/campaigns/pester-return-transfer-candidate-v3.json')
        grader=prospective_grader();rows=[]
        for control in task.controls():
            result=local_semantic_fixture(task.payload(control),task.files(),manifest)
            status,details=grader.assess(result[0],result[1:],reports.read_json(task.input_directory().parent/'profile.json')['minimum_tests'])
            task.check(control,True,dict(classification=status,**details),{})
            if control=='good-loop':
                self.assertEqual(details['tests_executed'],1)
                self.assertEqual(details['mutants_detected'],5)
                self.assertEqual(grader.assess(result[0],result[1:],5),('invalid',{'code':'nonexecuting'}))
            from unittest.mock import patch
            with tempfile.TemporaryDirectory() as directory:
                target=Path(directory)
                reports.write_json(target/'entry.json',{'id':'pester-transfer-'+control,'grading_mode':'custom_only'})
                with patch.dict(os.environ,{'HARBOR_REWARD_JSON':str(target/'reward.json')}):
                    grader.emit(target,status,details)
                reward=reports.read_json(target/'custom_reward.json')
                sidecar=reports.read_json(target/'skill_evaluator_reward.json')
                self.assertEqual(reward['details']['outcome']['classification'],status)
                if status=='invalid':
                    self.assertNotIn('custom_metrics',reward)
                    self.assertEqual(sidecar['evaluation_status'],'failed')
                else:
                    self.assertEqual(reward['custom_metrics']['pester_test_quality'],float(status=='passed'))
            if control=='overrestricted': self.assertEqual(details['reference_pass'],0)
            rows.append(dict(control=control,classification=status,details=details,runs=result))
        target=os.environ.get('PESTER_RETURN_EVIDENCE')
        if target: reports.write_json(Path(target)/'transfer-controls.json',rows)
