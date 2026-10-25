"""Offline production-path contracts; upstream releases never drive expectations."""

import base64
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("dependency_freshness", ROOT / ".github/scripts/dependency_freshness.py")
fresh = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fresh)
REVISION = "a" * 40


def advisory(id="GHSA-abcd-1234-5678", package="uv", severity="high", affected="< 99.0.0", fixed="99.0.0"):
    return {"ghsa_id": id, "severity": severity, "summary": "Controlled security fixture", "withdrawn_at": None,
            "vulnerabilities": [{"package": {"ecosystem": "pip", "name": package},
                                 "vulnerable_version_range": affected, "first_patched_version": fixed}]}


class FixtureAPI(fresh.GitHub):
    """Fixed transport fixtures; the real collectors, pagination and publisher run."""

    def __init__(self, root=ROOT):
        super().__init__()
        definitions, rows, _ = fresh.inventory(root)
        self.definitions = {item["id"]: item for item in definitions}
        self.rows = {row["id"]: row for row in rows}
        self.by_repo = {item["repo"]: item for item in definitions}
        self.latest = {}
        self.notes = {}
        self.publisher = {}
        self.reviewed = {}
        self.affected = {}
        self.failures = {}
        self.calls = []
        self.issues = []
        self.comments = []
        self.mutations = []
        self.lose_response = None
        self.main_revision = REVISION
        self.tree_changed = False

    def request(self, path, *, public=False, method="GET", data=None):
        self.requests += 1
        self.calls.append((method, path, public))
        for prefix, failure in self.failures.items():
            if path.startswith(prefix):
                raise fresh.DiscoveryError(failure)
        location = urlsplit(path)
        arguments = parse_qs(location.query)
        parts = location.path.split("/")
        if method != "GET":
            self.mutations.append((method, path, copy.deepcopy(data)))
            if path == f"repos/{fresh.REPOSITORY}/issues":
                issue = dict(number=84, state="open", user={"login": fresh.BOT}, **data)
                self.issues.append(issue)
                result = copy.deepcopy(issue)
            elif path.endswith("/comments"):
                self.comments.append({"user": {"login": fresh.BOT}, **data})
                result = {"id": len(self.comments)}
            else:
                self.issues[0].update(data)
                result = copy.deepcopy(self.issues[0])
            if self.lose_response == method + ":" + path.rsplit("/", 1)[-1]:
                self.lose_response = None
                raise fresh.DiscoveryError("timeout")
            return result
        if path == f"repos/{fresh.REPOSITORY}":
            return {"default_branch": "main"}
        if path == f"repos/{fresh.REPOSITORY}/branches/main":
            return {"commit": {"sha": self.main_revision}}
        if location.path == f"repos/{fresh.REPOSITORY}/issues":
            return copy.deepcopy(self.issues)
        if location.path.endswith("/comments"):
            return copy.deepcopy(self.comments)
        if location.path == "advisories":
            identity = arguments["affects"][0]
            return copy.deepcopy(self.affected.get(identity, []) if "@" in identity else self.reviewed.get(identity, []))
        repo = "/".join(parts[1:3])
        item = self.by_repo.get(repo)
        if location.path.endswith("/security-advisories"):
            return copy.deepcopy(self.publisher.get(repo, []))
        if item and location.path.endswith("/releases/latest"):
            pin = self.rows[item["id"]]["pin"]
            version = self.latest.get(item["id"], pin["version"])
            return {"tag_name": item.get("tag_prefix", "v") + version, "draft": False, "prerelease": False,
                    "body": self.notes.get(item["id"], "Controlled ordinary release")}
        if item and "commits" in parts:
            pin = self.rows[item["id"]]["pin"]
            pinned_tag = item.get("tag_prefix", "v") + (pin["version"] or "")
            return {"sha": "b" * 40 if self.tree_changed and parts[-1] != pinned_tag else pin["revision"]}
        if location.path.endswith("/contents/uv.lock"):
            content = "\n".join('[[package]]\nname = "' + name + '"\nversion = "' + self.rows[name]["pin"]["version"] + '"'
                                for name in ("harbor", "openai", "pydantic"))
            return {"encoding": "base64", "content": base64.b64encode(content.encode()).decode()}
        if item and "contents" in parts:
            ref = arguments["ref"][0]
            changed = self.tree_changed and ref != self.rows[item["id"]]["pin"]["revision"]
            return [{"path": item["path"] + "/SKILL.md", "type": "file", "sha": ("b" if changed else "a") * 40}]
        raise AssertionError("Unexpected fixture request: " + path)


class FreshnessTests(unittest.TestCase):
    def collect(self, api=None, root=ROOT):
        return fresh.collect(root, api or FixtureAPI(root), REVISION)

    def find(self, report, id):
        return next(row for row in report["dependencies"] if row["id"] == id)

    def publish(self, report, api):
        with patch.dict(os.environ, {"GITHUB_REF": "refs/heads/main", "GITHUB_EVENT_NAME": "schedule"}):
            return fresh.publish(report, ROOT, api, REVISION)

    def scratch(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        for name in (fresh.CONFIG, "apm.yml", "apm.lock.yaml", ".apm-version", ".github/dependabot.yml"):
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        for directory in (".github/workflows", ".github/requirements", ".github/patches", ".github/scripts"):
            shutil.copytree(ROOT / directory, root / directory, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
        return root

    def test_actual_inventory_resolves_authoritative_pins_without_installing_or_importing_consumers(self):
        with patch.object(fresh.subprocess, "run", side_effect=AssertionError("execution forbidden")):
            _, rows, mechanisms = fresh.inventory(ROOT)
        self.assertFalse([r for r in rows if r["errors"]])
        self.assertEqual(mechanisms["dependabot_routine_ecosystems"], ["github-actions"])
        self.assertIn("not proof", mechanisms["dependabot_python_security_updates"])
        for id in ("harbor", "openai", "pydantic"):
            row = next(r for r in rows if r["id"] == id)
            self.assertEqual(row["policy"]["group"], "evaluation-runtime compatibility group")
            self.assertTrue(row["policy"]["hold"])

    def test_current_and_managed_not_checked_are_distinct_from_policy(self):
        report = self.collect()
        self.assertTrue(report["complete"])
        self.assertEqual(self.find(report, "uv")["freshness"], "current")
        self.assertEqual(self.find(report, "openai")["freshness"], "current")
        managed = self.find(report, "action-actions-checkout")
        self.assertEqual(managed["freshness"], "not_checked")
        self.assertIn("Dependabot routine", managed["policy"]["owner"])
        self.assertEqual(self.find(report, "apm")["freshness"], "current")
        fresh.validate_report(report, ROOT, REVISION)

    def test_patch_minor_major_and_multiple_updates_preserve_holds(self):
        api = FixtureAPI()
        for id in ("uv", "openai", "pydantic"):
            major, minor, patch_version = fresh.stable(api.rows[id]["pin"]["version"])
            api.latest[id] = {"uv": f"{major}.{minor}.{patch_version + 1}", "openai": f"{major + 1}.0.0",
                              "pydantic": f"{major}.{minor + 1}.0"}[id]
        report = self.collect(api)
        for id in api.latest:
            self.assertEqual(self.find(report, id)["freshness"], "update_available")
        self.assertTrue(self.find(report, "openai")["policy"]["hold"])
        self.assertTrue(report["complete"])
        self.assertFalse(fresh.risk_events(self.collect()))

    def test_prerelease_draft_malformed_and_ahead_are_unknown_not_current(self):
        for change in ({"prerelease": True}, {"draft": True}, {"tag_name": "0.99.0rc1"},
                       {"tag_name": "0.0.0"}, {"tag_name": "0.99.0\nINJECT=yes"}):
            api = FixtureAPI()
            original = api.request
            def request(path, **kwargs):
                result = original(path, **kwargs)
                return {**result, **change} if path == "repos/astral-sh/uv/releases/latest" else result
            api.request = request
            with self.subTest(change=change):
                report = self.collect(api)
                self.assertFalse(report["complete"])
                self.assertEqual(self.find(report, "uv")["freshness"], "unverified")
                self.assertEqual(self.find(report, "semgrep")["freshness"], "current")
                fresh.validate_report(report, ROOT, REVISION)

    def test_content_sha_holds_and_tag_commit_mismatch(self):
        api = FixtureAPI()
        api.tree_changed = True
        major, minor, patch_version = fresh.stable(api.rows["gh"]["pin"]["version"])
        api.latest["gh"] = f"{major}.{minor + 1}.{patch_version}"
        report = self.collect(api)
        self.assertEqual(self.find(report, "git-commit")["freshness"], "update_available")
        self.assertTrue(self.find(report, "git-commit")["policy"]["hold"])
        self.assertEqual(self.find(report, "gh")["freshness"], "update_available")
        self.assertFalse(fresh.risk_events(report), "Uninterpreted skill commits must not notify")
        api.failures["repos/NVIDIA/SkillEvaluator/commits/"] = "pin_tag_mismatch"
        report = self.collect(api)
        self.assertEqual(self.find(report, "skillevaluator")["freshness"], "unverified")

    def test_missing_contradictory_and_unsupported_pins_remain_visible(self):
        for kind in ("missing", "contradictory", "format", "duplicate"):
            root = self.scratch()
            source = root / ".github/requirements/rumdl.in"
            text = source.read_text()
            pin = fresh.extract(root, next(d for d in fresh.load_config(root) if d["id"] == "rumdl"))[0]["version"]
            replacement = {"missing": "", "contradictory": "99.0.0", "format": "latest", "duplicate": pin}[kind]
            source.write_text((text + f"rumdl=={pin}\n") if kind == "duplicate" else text.replace("rumdl==" + pin, "rumdl==" + replacement if replacement else ""))
            report = self.collect(FixtureAPI(root), root)
            self.assertEqual(self.find(report, "rumdl")["freshness"], "unverified")
            self.assertFalse(report["complete"])
            self.assertEqual(self.find(report, "uv")["freshness"], "current")
            fresh.validate_report(report, root, REVISION)

    def test_failed_api_timeout_rate_limit_and_advisory_failure_retain_successes(self):
        for failure in ("http_403", "http_429", "timeout", "invalid_metadata"):
            api = FixtureAPI()
            api.failures["repos/astral-sh/uv/releases/latest"] = failure
            api.failures["repos/rvben/rumdl/security-advisories"] = failure
            report = self.collect(api)
            self.assertFalse(report["complete"])
            self.assertEqual(self.find(report, "uv")["freshness"], "unverified")
            self.assertEqual(self.find(report, "semgrep")["freshness"], "current")
            rumdl = self.find(report, "rumdl")
            self.assertEqual(rumdl["freshness"], "current", "Version freshness is independent of failed advisory coverage")
            self.assertEqual(rumdl["security"]["status"], "partial")
            body = fresh.render(report, fresh.load_config(ROOT))
            self.assertIn("INCOMPLETE", body)
            self.assertIn(fresh.escape(failure), body)
            fresh.validate_report(report, ROOT, REVISION)

    def test_advisory_identity_version_evidence_and_source_severity_are_retained(self):
        api = FixtureAPI()
        current = api.rows["uv"]["pin"]["version"]
        source = advisory()
        api.publisher["astral-sh/uv"] = [source]
        api.reviewed["uv"] = [{**source, "severity": "critical"}, advisory(id="GHSA-aaaa-bbbb-cccc", affected="< 0.0.1")]
        api.affected["uv@" + current] = [{**source, "severity": "critical"}]
        report = self.collect(api)
        records = self.find(report, "uv")["security"]["advisories"]
        self.assertEqual({r["severity"] for r in records}, {"high", "critical"})
        self.assertEqual({r["applicability"] for r in records}, {"unknown", "confirmed_version_match", "not_matched"})
        confirmed = next(r for r in records if r["applicability"] == "confirmed_version_match")
        self.assertEqual(confirmed["packages"][0]["name"], "uv")
        self.assertIn("uv@" + current, confirmed["evidence"])
        self.assertIn("platform", confirmed["evidence"])
        fresh.validate_report(report, ROOT, REVISION)

    def test_modified_evaluator_match_is_potential_and_withdrawn_records_are_excluded(self):
        api = FixtureAPI()
        source = advisory(package="skillevaluator")
        api.reviewed["skillevaluator"] = [source, {**source, "withdrawn_at": "2026-01-01"}]
        api.affected["skillevaluator@" + api.rows["skillevaluator"]["pin"]["version"]] = [source]
        report = self.collect(api)
        records = self.find(report, "skillevaluator")["security"]["advisories"]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["applicability"], "potentially_affected")
        self.assertIn("Locally modified", records[0]["evidence"])

    def test_untrusted_notes_and_advisory_text_are_bounded_escaped_and_never_commands(self):
        api = FixtureAPI()
        api.latest["uv"] = "99.0.0"
        attack = 'Security: @everyone [click](javascript:alert(1)) <img src=x> | `$(touch /tmp/pwn)` ${{ secrets.TOKEN }}\x1b[31m\u202e'
        api.notes["uv"] = attack + "x" * 10000
        source = advisory()
        source["summary"] = attack
        api.publisher["astral-sh/uv"] = [source]
        with patch.object(fresh.subprocess, "run", side_effect=AssertionError("must not execute")):
            report = self.collect(api)
            body = fresh.render(report, fresh.load_config(ROOT))
        self.assertNotIn("@everyone", body)
        self.assertNotIn("<img", body)
        self.assertNotIn("[click](javascript:", body)
        self.assertNotIn("\x1b", body)
        self.assertNotIn("\u202e", body)
        self.assertLessEqual(len(self.find(report, "uv")["signals"][0]["text"]), 240)
        self.assertLess(len(body.encode()), fresh.MAX_BODY)

    def test_no_current_release_signal_notifications_and_ordinary_held_drift_is_quiet(self):
        api = FixtureAPI()
        api.notes["skillspector"] = "Security: already installed release fix"
        report = self.collect(api)
        self.assertFalse(fresh.risk_events(report))
        api.latest["pydantic"] = ".".join(str(v + (1 if i == 2 else 0)) for i, v in enumerate(fresh.stable(api.rows["pydantic"]["pin"]["version"])))
        self.assertFalse(fresh.risk_events(self.collect(api)))
        api.latest["uv"] = "99.0.0"
        events = fresh.risk_events(self.collect(api))
        api.latest["uv"] = "99.0.1"
        self.assertEqual(events, fresh.risk_events(self.collect(api)), "Routine patch drift must not repeat material alerts")

    def test_report_is_deterministic_and_frozen_sdk_lock_disagreement_is_visible(self):
        self.assertEqual(self.collect(), self.collect())
        report = self.collect()
        shifted = copy.deepcopy(report)
        shifted["source_revision"] = "b" * 40
        for result in shifted["dependencies"]:
            for source in result["sources"]:
                source["line"] += 10
        self.assertEqual(fresh.render(report, fresh.load_config(ROOT)), fresh.render(shifted, fresh.load_config(ROOT)),
                         "Unrelated commits and pin line-number shifts must not churn the issue")
        api = FixtureAPI()
        original = api.request
        def request(path, **kwargs):
            result = original(path, **kwargs)
            if "/contents/uv.lock" in path:
                result["content"] = base64.b64encode(b'[[package]]\nname="openai"\nversion="99.0.0"').decode()
            return result
        api.request = request
        report = self.collect(api)
        for id in ("harbor", "openai", "pydantic"):
            self.assertIn("release:frozen_lock_mismatch", self.find(report, id)["errors"])

    def test_failed_reviewed_lookup_retains_publisher_unknown_and_rejects_skipped_assessments(self):
        api = FixtureAPI()
        api.publisher["astral-sh/uv"] = [advisory(affected="unsupported custom range")]
        api.failures["advisories?ecosystem=pip&affects=uv"] = "http_429"
        report = self.collect(api)
        result = self.find(report, "uv")
        self.assertEqual(result["security"]["advisories"][0]["applicability"], "unknown")
        self.assertEqual(result["security"]["status"], "partial")
        self.assertFalse(report["complete"])
        fresh.validate_report(report, ROOT, REVISION)
        for field in ("upstream", "security"):
            candidate = self.collect()
            result = self.find(candidate, "uv")
            result[field]["status"] = "not_checked"
            if field == "upstream":
                result["freshness"] = "not_checked"
            with self.assertRaises(fresh.DiscoveryError):
                fresh.validate_report(candidate, ROOT, REVISION)

    def test_security_signal_deduplicates_against_advisory_and_substantive_breaking_changes_notify(self):
        api = FixtureAPI()
        api.latest["uv"] = "99.0.0"
        source = advisory()
        api.reviewed["uv"] = [source]
        api.affected["uv@" + api.rows["uv"]["pin"]["version"]] = [source]
        report = self.collect(api)
        before = fresh.risk_events(report)
        api.notes["uv"] = "### Security\n\nSame known fix described again"
        self.assertEqual(before, fresh.risk_events(self.collect(api)))
        first = fresh.signals("### BREAKING CHANGES\n\n- Removes interface A")
        second = fresh.signals("### BREAKING CHANGES\n\n- Removes interface B")
        self.assertNotEqual(first, second)

    def test_real_check_entrypoint_writes_partial_report_and_returns_failure(self):
        api = FixtureAPI()
        api.failures["repos/astral-sh/uv/releases/latest"] = "timeout"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result"
            with patch.object(fresh, "GitHub", return_value=api), patch.dict(os.environ, {"GITHUB_SHA": REVISION}), redirect_stdout(io.StringIO()):
                code = fresh.main(["check", "--output", str(output)])
            self.assertEqual(code, 1)
            report = json.loads((output / "report.json").read_text())
            self.assertFalse(report["complete"])
            self.assertEqual(self.find(report, "semgrep")["freshness"], "current")
            self.assertIn("INCOMPLETE", (output / "report.md").read_text())

    def test_single_issue_and_notification_are_idempotent_including_partial_reports(self):
        api = FixtureAPI()
        api.latest["uv"] = "99.0.0"
        report = self.collect(api)
        first = self.publish(report, api)
        self.assertEqual(first["issue"], 84)
        self.assertEqual(len(api.issues), 1)
        self.assertEqual(len(api.comments), 1)
        changes = len(api.mutations)
        second = self.publish(report, api)
        self.assertFalse(second["body_changed"])
        self.assertEqual(len(api.mutations), changes)
        api.failures["repos/astral-sh/uv/releases/latest"] = "timeout"
        partial = self.collect(api)
        self.publish(partial, api)
        self.assertIn("INCOMPLETE", api.issues[0]["body"])
        self.assertEqual(len(api.comments), 1)
        del api.failures["repos/astral-sh/uv/releases/latest"]
        self.publish(self.collect(api), api)
        self.assertEqual(len(api.comments), 1, "Recovery must not repeat previously identified risks")
        self.assertTrue(all(f"repos/{fresh.REPOSITORY}/issues" in path for _, path, _ in api.mutations))

    def test_uncertain_create_comment_and_body_writes_reconcile_without_duplicates(self):
        for failure in ("POST:issues", "POST:comments", "PATCH:84"):
            api = FixtureAPI()
            api.latest["uv"] = "99.0.0"
            report = self.collect(api)
            if failure == "PATCH:84":
                self.publish(self.collect(), api)
            api.lose_response = failure
            with self.assertRaises(fresh.DiscoveryError):
                self.publish(report, api)
            self.publish(report, api)
            self.assertEqual(len(api.issues), 1)
            self.assertEqual(len(api.comments), 1)
            self.assertEqual(api.issues[0]["body"], fresh.render(report, fresh.load_config(ROOT)))

    def test_duplicate_closed_foreign_issue_and_forged_notification_boundaries(self):
        report = self.collect()
        for kind in ("duplicate", "closed", "foreign"):
            api = FixtureAPI()
            issue = {"number": 84, "state": "closed" if kind == "closed" else "open", "user": {"login": fresh.BOT}, "body": fresh.ISSUE_MARKER}
            api.issues = [issue, copy.deepcopy(issue)] if kind == "duplicate" else [issue]
            if kind == "foreign":
                api.issues[0]["user"]["login"] = "someone-else"
                self.publish(report, api)
                self.assertEqual(len(api.issues), 2, "Foreign issue text is not a bot-owned tracking target")
            else:
                with self.assertRaises(fresh.DiscoveryError):
                    self.publish(report, api)
                self.assertFalse(api.mutations)

    def test_publisher_rejects_bad_artifact_revision_inventory_status_and_source_without_writes(self):
        report = self.collect()
        mutations = [lambda r: r.update(source_revision="b" * 40), lambda r: r.update(complete=False),
                     lambda r: r["dependencies"].pop(), lambda r: r["dependencies"][0]["pin"].update(value="injected"),
                     lambda r: r["dependencies"][0]["sources"][0].update(path="../../secret"),
                     lambda r: r["dependencies"][0].update(freshness="current")]
        for mutate in mutations:
            candidate = copy.deepcopy(report)
            mutate(candidate)
            api = FixtureAPI()
            with self.assertRaises(fresh.DiscoveryError):
                self.publish(candidate, api)
            self.assertFalse(api.calls, "Artifact rejection must precede API access")
        api = FixtureAPI()
        api.main_revision = "b" * 40
        with self.assertRaisesRegex(fresh.DiscoveryError, "superseded_snapshot"):
            self.publish(report, api)
        self.assertFalse(api.mutations)
        for event, ref in (("pull_request", "refs/heads/main"), ("workflow_dispatch", "refs/heads/feature")):
            api = FixtureAPI()
            with patch.dict(os.environ, {"GITHUB_REF": ref, "GITHUB_EVENT_NAME": event}), self.assertRaises(fresh.DiscoveryError):
                fresh.publish(report, ROOT, api, REVISION)
            self.assertFalse(api.mutations)

    def test_live_transport_bounds_credentials_redirects_and_http_errors(self):
        class Response:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def read(self, size):
                return b'{}'
        api = fresh.GitHub("secret-fixture-token")
        with patch.object(api.opener, "open", return_value=Response()) as opened:
            api.request("repos/astral-sh/uv/security-advisories", public=True)
            request = opened.call_args.args[0]
            self.assertIsNone(request.get_header("Authorization"))
            api.request("advisories?affects=uv")
            self.assertEqual(opened.call_args.args[0].get_header("Authorization"), "Bearer secret-fixture-token")
            api.request("advisories?affects=uv")
            self.assertEqual(opened.call_count, 2, "Duplicate lookups are cached within a run")
        with patch.object(api.opener, "open", side_effect=HTTPError(fresh.API, 429, "untrusted", {}, None)):
            with self.assertRaisesRegex(fresh.DiscoveryError, "^http_429$"):
                api.request("advisories?affects=other")
        with patch.object(api.opener, "open", side_effect=AssertionError("A failed lookup must not be polled again")):
            with self.assertRaisesRegex(fresh.DiscoveryError, "^http_429$"):
                api.request("advisories?affects=other")
        with self.assertRaisesRegex(fresh.DiscoveryError, "unsafe_redirect"):
            fresh.SameOrigin().redirect_request(None, None, 302, "", {}, "https://example.invalid/steal")
        for path in ("https://example.invalid", "//example.invalid", "/repos/other"):
            with self.assertRaises(fresh.DiscoveryError):
                api.request(path)
        with patch.object(api, "request", return_value=[{}] * 100), self.assertRaisesRegex(fresh.DiscoveryError, "pagination_limit"):
            api.pages("advisories")


class WorkflowTests(unittest.TestCase):
    def test_partial_failure_handoff_and_least_privilege_contract(self):
        import yaml  # Already supplied by the pinned repository test environment.
        path = ROOT / ".github/workflows/dependency-freshness.yml"
        workflow = yaml.safe_load(path.read_text())
        triggers = workflow.get("on", workflow.get(True))
        self.assertEqual(set(triggers), {"schedule", "workflow_dispatch"})
        self.assertEqual(triggers["schedule"], [{"cron": "43 13 * * *"}])
        self.assertEqual(workflow["permissions"], {})
        discover, publish = workflow["jobs"]["discover"], workflow["jobs"]["publish"]
        self.assertEqual(discover["permissions"], {"contents": "read"})
        self.assertEqual(publish["permissions"], {"contents": "read", "issues": "write"})
        collect = next(s for s in discover["steps"] if s.get("id") == "collect")
        artifact = next(s for s in discover["steps"] if s.get("id") == "artifact")
        self.assertNotIn("continue-on-error", collect)
        self.assertIn("always()", artifact["if"])
        self.assertEqual(discover["outputs"]["artifact_ready"], "${{ steps.artifact.outcome == 'success' }}")
        self.assertIn("always()", publish["if"])
        self.assertIn("!cancelled()", publish["if"])
        self.assertIn("artifact_ready == 'true'", publish["if"])
        self.assertIn("github.ref == 'refs/heads/main'", publish["if"])
        self.assertNotIn("success()", publish["if"])
        for job in (discover, publish):
            for step in job["steps"]:
                self.assertNotIn("${{", step.get("run", ""))
                if "uses" in step:
                    self.assertRegex(step["uses"], r"@[0-9a-f]{40}$")
                if step.get("uses", "").startswith("actions/checkout@"):
                    self.assertIs(step["with"]["persist-credentials"], False)
                    self.assertEqual(step["with"]["ref"], "${{ github.sha }}")
        self.assertFalse(any("setup-skillevaluator" in s.get("run", "") for s in publish["steps"]))


if __name__ == "__main__":
    unittest.main()
