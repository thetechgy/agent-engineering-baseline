"""Offline tests of stable-only runtime acquisition through the CI entry point."""

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile


ROOT = Path(__file__).resolve().parents[2]

SPEC = importlib.util.spec_from_file_location(
    "ci_powershell", Path(__file__).resolve().parents[1] / "scripts/install_ci_powershell.py")
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)


def release(system="Linux", version="7.6.6"):
    name = (f"PowerShell-{version}-win-x64.zip" if system == "Windows"
            else f"powershell-{version}-linux-x64.tar.gz")
    return {"tag_name": f"v{version}", "draft": False, "prerelease": False,
            "assets": [{"name": asset, "browser_download_url": f"{runtime.RELEASE_BASE}v{version}/{asset}"}
                       for asset in (name, "hashes.sha256")]}


class CIPowerShellTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_selects_only_exact_official_assets_for_both_hosts(self):
        for system in ("Linux", "Windows"):
            version, name, urls = runtime.select_assets(release(system), system)
            self.assertEqual(version, "7.6.6")
            self.assertEqual(set(urls), {name, "hashes.sha256"})

    def test_rejects_prerelease_draft_and_malformed_metadata(self):
        for change in ({"prerelease": True}, {"draft": True}, {"tag_name": "v7.7.0-preview.1"},
                       {"tag_name": "v7.7.0-rc.1"}, {"tag_name": "v7.7.0-beta.1"},
                       {"tag_name": "v7.6.6\nCI_PWSH=other"}, {"prerelease": None}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                runtime.select_assets({**release(), **change}, "Linux")

    def test_rejects_missing_duplicate_or_relocated_assets(self):
        for mode in ("missing", "duplicate", "relocated"):
            data = release()
            if mode == "missing":
                data["assets"].pop()
            elif mode == "duplicate":
                data["assets"].append(data["assets"][0])
            else:
                data["assets"][0]["browser_download_url"] = "https://example.invalid/runtime"
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                runtime.select_assets(data, "Linux")

    def test_installs_and_executes_verified_linux_fixture_without_ambient_pwsh(self):
        executable, version = self.install_fixture()
        self.assertEqual(version, "7.6.6")
        self.assertEqual(executable, self.root / "installed/pwsh")
        self.assertEqual(subprocess.check_output([str(executable)], text=True).strip(), version)

    def install_fixture(self, *, reported="7.6.6", checksum="valid"):
        data = release()
        archive = self.root / "fixture.tar.gz"
        content = f"#!/bin/sh\nprintf '%s\\n' '{reported}'\n".encode()
        with tarfile.open(archive, "w:gz") as bundle:
            member = tarfile.TarInfo("pwsh")
            member.size = len(content)
            bundle.addfile(member, io.BytesIO(content))
        name = data["assets"][0]["name"]
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        sums = f"{digest}  {name}\n"
        if checksum == "wrong":
            sums = f"{'0' * 64}  {name}\n"
        elif checksum == "duplicate":
            sums *= 2
        elif checksum == "missing":
            sums = ""

        def download(url, destination):
            if url == runtime.RELEASE_API:
                destination.write_text(json.dumps(data))
            elif url.endswith("/hashes.sha256"):
                destination.write_text(sums)
            else:
                destination.write_bytes(archive.read_bytes())

        with patch.object(runtime, "download", side_effect=download), \
                patch.object(runtime.platform, "machine", return_value="x86_64"):
            return runtime.install(self.root / "installed", "Linux")

    def test_bad_hash_metadata_never_extracts_or_executes_runtime(self):
        for mode in ("wrong", "duplicate", "missing"):
            with self.subTest(mode=mode), patch.object(runtime, "extract_archive") as extract, \
                    patch.object(runtime.subprocess, "run") as run, self.assertRaises(ValueError):
                self.install_fixture(checksum=mode)
            extract.assert_not_called()
            run.assert_not_called()
            self.assertFalse((self.root / "installed").exists())

    def test_accepts_official_utf16_and_utf8_bom_checksum_files(self):
        archive = self.root / "runtime.zip"
        archive.write_bytes(b"verified archive fixture")
        sums = self.root / "hashes.sha256"
        digest = hashlib.sha256(archive.read_bytes()).hexdigest().upper()
        for encoding in ("utf-16", "utf-8-sig"):
            with self.subTest(encoding=encoding):
                sums.write_text(f"{digest}  {archive.name}\n", encoding=encoding)
                runtime.verify_archive(archive, sums)

    def test_runtime_version_mismatch_leaves_no_installed_runtime(self):
        with self.assertRaisesRegex(ValueError, "version does not match"):
            self.install_fixture(reported="7.7.0-preview.1")
        self.assertFalse((self.root / "installed").exists())

    def test_existing_destination_is_preserved_without_network_access(self):
        destination = self.root / "installed"
        destination.mkdir()
        sentinel = destination / "keep"
        sentinel.write_text("unrelated")
        with patch.object(runtime, "download") as download, self.assertRaises(ValueError):
            runtime.install(destination, "Linux")
        download.assert_not_called()
        self.assertEqual(sentinel.read_text(), "unrelated")

    def test_windows_zip_rejects_traversal_and_case_collisions(self):
        for names in (("../pwsh.exe",), ("C:/pwsh.exe",), ("pwsh.exe", "PWSH.EXE")):
            archive = self.root / "runtime.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                for name in names:
                    bundle.writestr(name, "untrusted")
            with self.subTest(names=names), self.assertRaises(ValueError):
                runtime.extract_archive(archive, self.root / "extracted", "Windows")
        self.assertFalse((self.root / "extracted").exists())

    def test_windows_zip_extracts_runtime_and_supporting_files(self):
        archive = self.root / "runtime.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("pwsh.exe", "fixture executable")
            bundle.writestr("Modules/fixture.psd1", "fixture module")
        destination = self.root / "extracted"
        runtime.extract_archive(archive, destination, "Windows")
        self.assertEqual((destination / "pwsh.exe").read_text(), "fixture executable")
        self.assertTrue((destination / "Modules/fixture.psd1").is_file())

    def test_platform_jobs_use_verified_runtime_and_latest_host_labels(self):
        import yaml
        workflow = Path(__file__).resolve().parents[1] / "workflows/validate.yml"
        jobs = yaml.safe_load(workflow.read_text())["jobs"]
        self.assertNotIn("macos", jobs)
        for name, host in (("linux", "ubuntu-latest"), ("windows-powershell", "windows-latest")):
            job = jobs[name]
            self.assertEqual(job["runs-on"], host)
            acquisition = next(i for i, step in enumerate(job["steps"])
                               if "install_ci_powershell.py" in step.get("run", ""))
            for index, step in enumerate(job["steps"]):
                if "Install-CIValidationModule" in step.get("run", "") or "Invoke-Validation.ps1" in step.get("run", ""):
                    self.assertGreater(index, acquisition)
                    self.assertIn("& $env:CI_PWSH", step["run"])
                self.assertNotEqual(step.get("shell"), "powershell")

    def test_validation_concurrency_only_supersedes_initial_runs_of_the_same_pr(self):
        import yaml
        workflow = yaml.safe_load((ROOT / ".github/workflows/validate.yml").read_text())
        triggers = workflow.get("on", workflow.get(True))
        self.assertEqual(triggers, {"push": {"branches": ["main"]}, "pull_request": None})
        self.assertEqual(workflow["concurrency"], {
            "group": "${{ github.workflow }}-${{ github.event_name == 'pull_request' && github.run_attempt == '1' && format('pr-{0}', github.event.pull_request.number) || github.run_id }}",
            "cancel-in-progress": "${{ github.event_name == 'pull_request' && github.run_attempt == '1' }}",
        })
        self.assertEqual(workflow["jobs"]["linux"]["name"], "Full validation (PowerShell 7 and Bash)")
        self.assertEqual(workflow["jobs"]["windows-powershell"]["name"], "Pester and analyzer (latest stable PowerShell)")

    def test_evaluator_recovery_uses_a_standalone_same_attempt_graph(self):
        import yaml
        workflow = yaml.safe_load((ROOT / ".github/workflows/current-evaluator.yml").read_text())
        self.assertEqual(set(workflow.get('on', workflow.get(True))), {'workflow_dispatch'})
        report = workflow['jobs']['report']
        self.assertEqual(set(report['needs']), {'cohorts', 'native-gh'})
        downloads = [step['with'] for step in report['steps']
                     if step.get('uses', '').startswith('actions/download-artifact@')]
        self.assertEqual(len(downloads), 3)
        for inputs in downloads:
            self.assertNotIn('run-id', inputs)
            self.assertIn('attempt-${{ github.run_attempt }}', inputs.get('pattern', inputs.get('name', '')))

    def test_release_benchmark_fixture_dispatch_is_explicit_and_credential_free(self):
        import yaml
        workflow = yaml.safe_load((ROOT / '.github/workflows/current-evaluator.yml').read_text())
        inputs = workflow.get('on', workflow.get(True))['workflow_dispatch']['inputs']
        self.assertFalse(inputs['benchmark-121-fixtures']['default'])
        self.assertFalse(inputs['benchmark-121-codex']['default'])
        self.assertFalse(inputs['benchmark-121-podman']['default'])
        self.assertFalse(inputs['benchmark-121-launcher']['default'])
        self.assertEqual(inputs['startup-owner']['options'], ['0.9.0', '1.2.1'])
        jobs = workflow['jobs']
        candidate = jobs['benchmark-121']
        self.assertEqual(candidate['if'], "github.event_name == 'workflow_dispatch'"
                         " && !inputs.benchmark-121-launcher"
                         " && (inputs.benchmark-121-fixtures || inputs.benchmark-121-codex || inputs.benchmark-121-podman)")
        for key in ('cohorts', 'native-gh', 'report', 'startup'):
            self.assertIn('!inputs.benchmark-121-fixtures', jobs[key]['if'])
            self.assertIn('!inputs.benchmark-121-codex', jobs[key]['if'])
            self.assertIn('!inputs.benchmark-121-podman', jobs[key]['if'])
            self.assertIn('!inputs.benchmark-121-launcher', jobs[key]['if'])
        self.assertEqual(candidate['strategy']['matrix']['suite'],
                         '''${{ fromJSON(inputs.benchmark-121-podman && '["podman"]' || inputs.benchmark-121-codex && '["codex"]' || '["gh", "pester"]') }}''')
        self.assertEqual(workflow['permissions'], {'contents': 'read'})
        self.assertNotIn('environment', candidate)
        self.assertNotIn('secrets.', yaml.safe_dump(candidate))
        steps = candidate['steps']
        self.assertFalse(steps[0]['with']['persist-credentials'])
        self.assertEqual(steps[0]['with']['ref'], '${{ github.sha }}')
        deterministic = next(step for step in steps if '--native "$FIXTURE_SUITE"' in step.get('run', ''))
        codex = next(step for step in steps if 'qualify_benchmark_codex.py' in step.get('run', ''))
        self.assertEqual(deterministic['if'], "matrix.suite == 'gh' || matrix.suite == 'pester'")
        self.assertIn('benchmark-121-gh-reporting.patch', deterministic['run'])
        self.assertEqual(codex['if'], "matrix.suite == 'codex'")
        podman = next(step for step in steps if 'qualify_benchmark_podman.py' in step.get('run', ''))
        publications = next(step for step in steps if 'qualify_benchmark_publication_101.py' in step.get('run', ''))
        self.assertEqual(podman['if'], "matrix.suite == 'podman'")
        self.assertEqual(publications['if'], "${{ !cancelled() && matrix.suite == 'podman' }}")
        self.assertIn('git archive "$GITHUB_SHA"', publications['run'])
        self.assertIn('benchmark-121-publication.patch', publications['run'])

    def test_selected_jobs_feed_an_always_running_gate_without_privileged_calls(self):
        import yaml
        workflow = yaml.safe_load((ROOT / '.github/workflows/validate.yml').read_text())
        jobs = workflow['jobs']
        gate = jobs['validation']
        self.assertEqual(gate['if'], 'always()')
        self.assertEqual(set(gate['needs']), set(jobs) - {'validation'})
        self.assertEqual(jobs['plan']['steps'][0]['with']['fetch-depth'], 0)
        self.assertTrue(any(step.get('working-directory') == '.github/tests'
                            and 'unittest test_ci_routing' in step.get('run', '')
                            for step in jobs['plan']['steps']))
        spec = importlib.util.spec_from_file_location('ci_routing', ROOT / '.github/scripts/ci_routing.py')
        ci_routing = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ci_routing)
        self.assertEqual(set(jobs['plan']['outputs']), {*ci_routing.FLAGS, 'static_candidate'})
        self.assertEqual(jobs['plan']['outputs']['static_candidate'], '${{ steps.impact.outputs.static_candidate }}')
        for flag, job in ci_routing.JOBS.items():
            self.assertIn(f"needs.plan.outputs.{flag} == 'true'", jobs[job]['if'])
        fixture = yaml.safe_load((ROOT / '.github/workflows/codex-1691-qualification.yml').read_text())
        fixture_paths = fixture.get('on', fixture.get(True))['pull_request']['paths']
        for path in ('.github/evals/campaigns/codex-1691.json', '.github/evals/campaigns/gh-codex-1691.json',
                     '.github/evals/codex-execution-1691.json', '.github/workflows/codex-1691-qualification.yml'):
            self.assertIn(path, fixture_paths)
            self.assertEqual({k for k, v in ci_routing.select([path]).items() if v}, {'contracts'})
        self.assertNotIn('needs', jobs['linux'])
        self.assertNotIn('if', jobs['linux'])
        self.assertNotIn('if', jobs['windows-powershell'])
        for job in jobs.values():
            if 'uses' in job:
                self.assertNotIn('secrets', job)
                self.assertIn("github.event_name == 'pull_request'", job['if'])
                called = yaml.safe_load((ROOT / job['uses'][2:]).read_text())
                triggers = called.get('on', called.get(True))
                self.assertIn('workflow_call', triggers)
                self.assertIn('workflow_dispatch', triggers)
                self.assertNotIn('pull_request', triggers)
        self.assertNotIn('current-evaluator', jobs)
        self.assertNotIn('codex-pilot', jobs)
        pilot = yaml.safe_load((ROOT / '.github/workflows/codex-pilot.yml').read_text())
        for name, job in pilot['jobs'].items():
            if job['permissions'].get('actions'):
                self.assertIn("github.event_name == 'workflow_dispatch'", job['if'])
                self.assertIn('github.run_attempt == 1', job['if'])
            elif name in ('prepare', 'consume', 'effectiveness', 'cohort-consume'):
                self.assertEqual(job['permissions'], {'contents': 'read'})
        for name in ('evaluation-campaign', 'pester-return-qualification'):
            called = yaml.safe_load((ROOT / f'.github/workflows/{name}.yml').read_text())
            self.assertEqual(set(called.get('on', called.get(True))), {'workflow_dispatch'})

    def test_all_validation_installers_and_consumers_use_the_shared_exact_version_contract(self):
        import yaml
        for name in ("validate", "update-baseline"):
            workflow = yaml.safe_load((ROOT / f".github/workflows/{name}.yml").read_text())
            self.assertEqual(workflow["env"]["PESTER_VERSION"], "6.2.0")
            self.assertEqual(workflow["env"]["PSSCRIPTANALYZER_VERSION"], "1.25.0")
            for job in workflow["jobs"].values():
                for step in job.get("steps", []):
                    source = step.get("run", "")
                    self.assertNotIn("Install-Module ", source)
                    if step.get("name") == "Install validation tools":
                        self.assertIn(". ./scripts/Install-CIValidationModule.ps1", source)
                        for module, variable in (("Pester", "PESTER_VERSION"), ("PSScriptAnalyzer", "PSSCRIPTANALYZER_VERSION")):
                            self.assertIn(f"Install-CIValidationModule -Name {module} -RequiredVersion $env:{variable}", source)
                    if "./scripts/Invoke-Validation.ps1" in source:
                        for module, variable in (("Pester", "PESTER_VERSION"), ("PSScriptAnalyzer", "PSSCRIPTANALYZER_VERSION")):
                            self.assertIn(f"Import-CIValidationModule -Name {module} -RequiredVersion $env:{variable}", source)

class FrozenRuntimeOwnership(unittest.TestCase):
    def test_weekly_refresh_uses_the_adopted_validation_runtime(self):
        import yaml
        workflow = yaml.safe_load((ROOT / '.github/workflows/update-baseline.yml').read_text())
        steps = workflow['jobs']['generate']['steps']
        acquire = next(step for step in steps if step['name'] == 'Acquire latest stable PowerShell')
        self.assertIn('install_ci_powershell.py', acquire['run'])
        self.assertIn('--github-env "$GITHUB_ENV"', acquire['run'])
        self.assertNotIn('--runtime frozen-pester', acquire['run'])
        for name in ('Install validation tools', 'Validate candidate update with reviewed CLI'):
            step = next(step for step in steps if step['name'] == name)
            self.assertLess(steps.index(acquire), steps.index(step))
            self.assertEqual(step['if'], acquire['if'])
            self.assertIn('& $env:CI_PWSH', step['run'])
            self.assertIn('if ($LASTEXITCODE -ne 0) { throw', step['run'])

    def test_only_frozen_grader_step_selects_pinned_runtime(self):
        import yaml
        steps=yaml.safe_load((ROOT/'.github/workflows/validate.yml').read_text())['jobs']['linux']['steps']
        latest=next(s for s in steps if s.get('name')=='Acquire latest stable PowerShell')
        self.assertNotIn('--runtime frozen-pester',latest['run'])
        pinned=next(s for s in steps if s.get('name')=='Acquire declared frozen-grader runtime')
        self.assertIn('--runtime frozen-pester',pinned['run'])
        self.assertIn('python3 -B ',pinned['run'])
        grader=next(s for s in steps if s.get('name')=='Check exploratory Pester candidate with the existing grader')
        self.assertEqual(grader['env']['CI_PWSH'],'${{ env.FROZEN_PWSH }}')
        self.assertEqual(grader['env']['PESTER_MANIFEST'],'${{ env.FROZEN_PESTER_MANIFEST }}')
        self.assertNotIn('FROZEN_PWSH',next(s for s in steps if s.get('name')=='Run full validation')['run'])

    def test_relocated_installer_fails_closed_on_changed_validation_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            destination=Path(directory)/'runtime'
            with patch('codex_pilot_contract.runtime_installer_bytes',return_value=b'def main(): pass\n'), self.assertRaisesRegex(ValueError,'validation contract changed'):
                runtime.install_frozen_pester(destination)
            self.assertFalse(destination.exists())

    def test_relocated_installer_preserves_an_existing_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            destination=Path(directory)/'runtime';destination.mkdir();(destination/'keep').write_text('unrelated')
            with self.assertRaisesRegex(ValueError,'must not exist'):
                runtime.install_frozen_pester(destination)
            self.assertEqual((destination/'keep').read_text(),'unrelated')
