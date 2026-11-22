# APM 0.37.0 bootstrap and rollback

Both bootstrap wrappers and the weekly updater read `.apm-version`. The repository Learn declaration targets Codex. APM
0.37.0 writes project Copilot servers to the file also read by Claude. User bootstrap installs the Copilot Learn
companion from the bootstrap checkout as an absolute local APM package. Keep that checkout at the same path for
subsequent user-scope installs. The companion has a distinct server ID so APM tracks both declarations. Both clients
use the three reviewed Learn tools.
[Tagged adapter](https://github.com/microsoft/apm/blob/v0.37.0/src/apm_cli/adapters/client/copilot_project.py).

## Reset an existing destination

1. Stop the clients. Make a restorable backup of the destination’s APM manifest, lock, modules, receipts, deployed
   instructions and skills, shared Codex and Copilot settings and the reviewed baseline ref. Include the retired
   project `.github/mcp.json` and any existing root `.mcp.json`. For user scope, include `~/.apm` and the affected
   client directories. For repository scope, include the matching receipt under `~/.apm/deployment-receipts/`.
   Save independently edited settings separately so you can compare them after uninstall.
2. From the original scope, use the verified **0.36.1** executable to run
   `apm uninstall thetechgy/agent-engineering-baseline`. Add `--global` for user scope. Check the surviving package
   commits, deployed files and independent client entries against the backup. Restore any independently owned entry
   removed by cleanup. Reconcile a conflicting server name before continuing.
3. Run the 0.37.0 bootstrap for that same scope. The wrapper verifies and replaces its managed CLI. Compare the
   destination lock and the seven imported skills with the reviewed release. Keep the backup until both clients have
   been checked.

## Lock v4 and release verification

The [0.37.0 release](https://github.com/microsoft/apm/releases/tag/v0.37.0) changes the lock schema and package-level
hash framing. It rejects manifest anchors. The manifest repeats the exact Microsoft Learn tool list in `tools` and
`enabled_tools`, and permits isolated regeneration to publish the root MCP file and retire the old one. The reviewed
Linux x86-64/ARM64 and Windows x86-64 archive hashes matched both GitHub release digests and Microsoft's checksum
sidecars. The pins also bind the extracted executables.

| Owner | Lock use |
| --- | --- |
| Bash and PowerShell bootstrap | Native APM installs write the destination lock and compilation reads it. User scope owns `~/.apm/apm.lock.yaml` and repository scope owns `./apm.lock.yaml`. Scripts install, verify and invoke the version selected by `.apm-version`. |
| Weekly refresh and full validation | `update-baseline.yml` calls `scripts/apm_regeneration.py --mode refresh` on a scratch checkout and publishes generated changes to a reviewed branch. `Invoke-Validation.ps1` invokes frozen replay, compile, audit and pack dry-run with byte stability. `validate.yml` compares generated files and runs the native bootstrap lifecycle on Ubuntu and Windows. |
| Catalog, staging, orchestration and freshness | `skill_evidence.py`, `gh_evaluations.py`, `skill_orchestration.py` and `dependency_freshness.py` read the dependency and deployment ledgers for ownership, exact revisions and file hashes. Historical revision readers fetch the lock from their selected Git revision. The qualification and Pester paths exercise these contracts. |
| Installation checks | `bootstrap_lifecycle.py` reads native revisions and deployment hashes and deliberately writes contradictory fixture locks. The Microsoft Learn and code-reference Pester checks read the generated lock and native config. |

The isolated refresh preserved all seven resolved commits and every per-file digest, including all six msgraph
executables. The regenerated v4 lock records the new package hashes and target list. The repo does not invoke
`apm unpack` or `microsoft/apm-action`, so the release's known unpack rewrite does not require an action upgrade here.

## Weekly source regeneration

The weekly updater uses the verified 0.37.0 CLI. A fresh checkout has no deployment receipt. Before calling APM,
`scripts/apm_regeneration.py --mode refresh` compares the modular Copilot instruction with its previous SHA-256 in
the native lock. When they match, it removes that copy from the scratch checkout so APM can render the edited
source. A second refresh preserves the resulting bytes. If the destination was separately edited, back it up and
reconcile it with the source before retrying. The failure leaves the caller’s file in place.

## Historical in-place MCP migration on Ubuntu

These controls started with real APM 0.36.1 destinations in both scopes and ran 0.37.0 against the same local Git
packages. The transitive fixture contained two self-defined HTTP entries. All fixture endpoints except the canonical
Learn URL use reserved hostnames, and the test makes no requests to them.

| Control | Repository | User |
| --- | --- | --- |
| Unchanged Learn migration | Moved to root `.mcp.json`. Foreign entry remained in `.github/mcp.json`. | Stayed in `~/.copilot/mcp-config.json`. Foreign entry survived. |
| Edited Learn remains declared | Preserved the operator's entry in the retired file and added the package endpoint to the active root file with exit 0. | Preserved the edited endpoint with exit 0. |
| Remove declaration with an edited Copilot entry | Preserved the edited entry in the retired file. | Deleted the edited entry with exit 0. Foreign entry survived. |
| Drop blanket trust with an edited transitive Copilot entry | Preserved the edited entry in the retired file. Removed the unchanged transitive entry. | Deleted both the edited and unchanged entries with exit 0. Foreign entry survived. |

The generated Codex and Copilot entries both retain `microsoft_docs_search`, `microsoft_docs_fetch` and
`microsoft_code_sample_search`. The upstream release notes say Claude Code also reads root `.mcp.json` and ignores
`tools` allowlists. The repository move therefore changes the configuration boundary for operators using both clients.
These results describe the former in-place migration. The scoped reset precedes deployment of the Codex-only project
declaration.

## Roll back a migrated destination

Use the reviewed 0.36.1 bootstrap checkout at `12e0c54bf133bbbd9a3000b619d6deaf371c1403` and the pre-upgrade baseline
ref. A binary downgrade alone fails on a v4 lock. Before restoring, save the current destination so you can reconcile
any edits made since migration.

1. Keep the existing project directory and, for user scope, the existing home and `~/.apm` directories in place.
   The receipt binds that directory’s filesystem identity. Restore the pre-upgrade manifest and v1 lock together,
   including the APM ownership state, managed deployments and relevant Codex/Copilot config. In user scope, restore the
   pre-upgrade `~/.apm` state. For repository scope, restore the existing manifest and lock, modules, the repository
   installation identity, its matching receipt under `~/.apm/deployment-receipts/`, managed deployment paths,
   `.codex/config.toml` and `.github/mcp.json`.
2. Reverse the migration's changes to root `.mcp.json` from that same snapshot. Preserve entries and files owned by
   other clients or added since the snapshot.
3. Run the verified 0.36.1 bootstrap for the same destination scope and reviewed baseline ref. Verify the previous lock
   and deployed file hashes before using either client. For a checkout with the committed v4 lock, use a separate clean
   checkout of the prior revision.
4. If the only surviving lock is v4, keep the migrated destination and rebuild in a separate destination from known
   reviewed refs, carrying manually reviewed foreign settings over. This also applies to unrelated packages. Editing
   the version field does not restore the old hash framing or metadata.

The Ubuntu and Windows bootstrap jobs exercise this reset and rollback at both scopes. Each fixture checks the
original lock, unrelated package and independently owned client settings after restoring its backup.
