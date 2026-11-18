"""Case selection and bounded workspace evidence on real local files."""
import base64
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from case_observation import CONFIG, selected
from case_workspace import MAX_FILE, compare


class CaseObservationTests(unittest.TestCase):
    def test_original_ids_resolve_without_runtime_or_credentials(self):
        self.assertEqual(selected("podman", "4")[1]["files"], [])
        self.assertEqual(selected("gh", "gh-014")[1]["id"], "gh-014")
        for skill, case in (("podman", "404"), ("../podman", "4"), ("gh", "4")):
            with self.assertRaises(ValueError):
                selected(skill, case)

    def test_missing_oversized_and_linked_members_cannot_attest_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(OSError):
                compare(root / "missing", {})
            workspace = root / "task"
            workspace.mkdir()
            baseline = compare(workspace, None)["baseline"]
            self.assertEqual(compare(workspace, baseline), {"changes": []})
            config = workspace / "traefik.yaml"
            config.write_text(CONFIG)
            row, = compare(workspace, baseline)["changes"]
            self.assertEqual((row["path"], row["change"], base64.b64decode(row["data"]).decode()),
                             ("traefik.yaml", "added", CONFIG))
            config.write_bytes(bytes(MAX_FILE + 1))
            with self.assertRaises(ValueError):
                compare(workspace, baseline)
            config.unlink()
            config.symlink_to(root / "private")
            with self.assertRaises(ValueError):
                compare(workspace, baseline)

    def test_successors_change_only_producer_identity(self):
        registry = json.loads((SCRIPTS.parent / "evals/custom-metrics.json").read_bytes())
        profiles = registry["profiles"]
        previous = {k.replace("-source-v27-", "-source-v28-"): k for k in profiles if "-source-v27-" in k}
        previous.update({"pester-effectiveness-v31": "pester-effectiveness-v30",
                         "pester-cli-pilot-retained-v19": "pester-cli-pilot-retained-v18"})
        for new, old in previous.items():
            successor = profiles.pop(new)
            predecessor = profiles[old]
            self.assertNotEqual(successor["runtime_digest"], predecessor["runtime_digest"])
            successor.update(id=old, runtime_digest=predecessor["runtime_digest"])
            if "adapter_sha256" in successor.get("campaign", {}):
                successor["campaign"]["adapter_sha256"] = predecessor["campaign"]["adapter_sha256"]
            self.assertEqual(successor, predecessor)
        self.assertEqual(hashlib.sha256((json.dumps(registry, indent=2) + "\n").encode()).hexdigest(),
                         "f59f8715f00cf22035f1a32c4bc0d1f4f53bdbea6668e902942e9144ae0a887a")
