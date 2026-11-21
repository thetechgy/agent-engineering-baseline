# APM 0.37.0 qualification for #88 and #95

**Hold the shared 0.36.1 pin.** This draft carries the candidate so the existing Ubuntu and Windows checks can exercise it. The current bootstrap trust flags remain in use. The project MCP move and user MCP cleanup both need a resolution before rollout.

## Lock v4 and release verification

The [0.37.0 release](https://github.com/microsoft/apm/releases/tag/v0.37.0) changes the lock schema and package-level hash framing. It rejects manifest anchors. The candidate repeats the exact Microsoft Learn tool list in `tools` and `enabled_tools`, and permits isolated regeneration to publish the root MCP file and retire the old one. The reviewed Linux x86-64/ARM64 and Windows x86-64 archive hashes matched both GitHub release digests and Microsoft's checksum sidecars. The pins also bind the extracted executables.

| Owner | Lock use |
| --- | --- |
| Bash and PowerShell bootstrap | Native APM installs write the destination lock and compilation reads it. User scope owns `~/.apm/apm.lock.yaml` and repository scope owns `./apm.lock.yaml`. Scripts install, verify and invoke the version selected by `.apm-version`. |
| Weekly refresh and full validation | `update-baseline.yml` calls `scripts/apm_regeneration.py --mode refresh` on a scratch checkout and publishes generated changes to a reviewed branch. `Invoke-Validation.ps1` invokes frozen replay, compile, audit and pack dry-run with byte stability. `validate.yml` compares generated files and runs the native bootstrap lifecycle on Ubuntu and Windows. |
| Catalog, staging, orchestration and freshness | `skill_evidence.py`, `gh_evaluations.py`, `skill_orchestration.py` and `dependency_freshness.py` read the dependency and deployment ledgers for ownership, exact revisions and file hashes. Historical revision readers fetch the lock from their selected Git revision. The qualification and Pester paths exercise these contracts. |
| Installation checks | `bootstrap_lifecycle.py` reads native revisions and deployment hashes and deliberately writes contradictory fixture locks. The Microsoft Learn and code-reference Pester checks read the generated lock and native config. |

The isolated refresh preserved all seven resolved commits and every per-file digest, including all six msgraph executables. The regenerated v4 lock records the new package hashes and target list. The repo does not invoke `apm unpack` or `microsoft/apm-action`, so the release's known unpack rewrite does not require an action upgrade here.

## Weekly source regeneration

The one-time isolated refresh of the main checkout preserved the full skill graph.
The native lifecycle control for routine regeneration then refused a legitimate
authored instruction change. In a checkout without local deployment receipts,
0.37.0 kept the old generated Copilot instruction and exited 1. Retain 0.36.1
for the weekly updater until it can replace the previous, still-unedited
generated output while preserving a separately edited destination file.

## MCP migration on Ubuntu

These controls started with real APM 0.36.1 destinations in both scopes and ran 0.37.0 against the same local Git packages. The transitive fixture contained two self-defined HTTP entries. All fixture endpoints except the canonical Learn URL use reserved hostnames, and the test makes no requests to them.

| Control | Repository | User |
| --- | --- | --- |
| Unchanged Learn migration | Moved to root `.mcp.json`. Foreign entry remained in `.github/mcp.json`. | Stayed in `~/.copilot/mcp-config.json`. Foreign entry survived. |
| Edited Learn remains declared | Preserved the operator's entry in the retired file and added the package endpoint to the active root file with exit 0. | Preserved the edited endpoint with exit 0. |
| Remove declaration with an edited Copilot entry | Preserved the edited entry in the retired file. | Deleted the edited entry with exit 0. Foreign entry survived. |
| Drop blanket trust with an edited transitive Copilot entry | Preserved the edited entry in the retired file. Removed the unchanged transitive entry. | Deleted both the edited and unchanged entries with exit 0. Foreign entry survived. |

The generated Codex and Copilot entries both retain `microsoft_docs_search`, `microsoft_docs_fetch` and `microsoft_code_sample_search`. The upstream release notes say Claude Code also reads root `.mcp.json` and ignores `tools` allowlists. The repository move therefore changes the configuration boundary for operators using both clients. Preserve the current repository bootstrap and source-regeneration versions together. Preserve the user bootstrap version for destinations with edited Copilot settings until cleanup distinguishes operator contributions. Keep blanket transitive trust unchanged until scoped approval and lifecycle controls both pass.

## Roll back a migrated destination

Use the reviewed 0.36.1 bootstrap checkout at `12e0c54bf133bbbd9a3000b619d6deaf371c1403` and the pre-upgrade baseline ref. A binary downgrade alone fails on a v4 lock. Before restoring, save the current destination so you can reconcile any edits made since migration.

1. Restore the pre-upgrade destination manifest and v1 lock together, along with its APM ownership state, managed deployments and relevant Codex/Copilot config. In user scope this includes the pre-upgrade `~/.apm` state. In repository scope it includes the existing manifest and lock, modules, managed deployment paths, `.codex/config.toml` and `.github/mcp.json`.
2. Reverse the migration's changes to root `.mcp.json` from that same snapshot. Preserve entries and files owned by other clients or added since the snapshot.
3. Run the verified 0.36.1 bootstrap for the same destination scope and reviewed baseline ref. Verify the previous lock and deployed file hashes before using either client. For a checkout with the committed v4 lock, use a separate clean checkout of the prior revision.
4. If the only surviving lock is v4, keep the migrated destination and rebuild in a separate destination from known reviewed refs, carrying manually reviewed foreign settings over. This also applies to unrelated packages. Editing the version field does not restore the old hash framing or metadata.

The Ubuntu fixtures rejected the v4 lock with the 0.36.1 executable in both scopes and successfully reinstalled after restoring the pre-migration lock, manifest and affected MCP files.
