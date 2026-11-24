# Historical validator source fixture

`historical-modules.zip` contains eight unique, unmodified public Python source
modules from this repository at `1cffcf9947c265f126a3ceee75e5e35249bfd722`,
`89f46f026cdaaf001487cbcc1425204db29e8952`,
`3f47c9de4df362ae9977748ad6353227f403a9b8`, and
`a5392b0eda37485b131ffe416fcb9d6e5ee547d2`. Shared modules occur once,
under their raw SHA-256 filename. ZIP timestamps are fixed.

The production profile table independently pins every module digest. Tests read
only the required members, verify each raw digest before writing the temporary
layout, then exercise the original validators with entirely synthetic reports,
evidence, and assessments. The fixture contains no private pilot outputs, model
responses, credentials, or trajectories. It requires no Git history, network
fetch, patch application, or alternate validation engine. Original source is
covered by the repository's license.

Production does not load this fixture: historical callers must explicitly supply
a tooling snapshot matching the same reviewed hashes.

`retirement-parity.zip` contains 13 synthetic input and saved-output cases
from the ten original validators at `58cb9698543c546173501887254dc7989d2db396`.
The capture fixed the review timestamp at 2026-11-23 12:00 UTC. Its catalog
records expected admission and implementation digests for each case, plus
relative fixture paths. The snapshots above still identify the original
validators. The 1.0.1 tests restore the exact saved bytes and verify their
admission, then exercise substitutions across the authenticated inputs.

`retirement-pester-parity.zip` captures the custom-only Pester public bundle
and original `current-v4` attachment from the same base. The Pages and review
tests consume those validated public bytes without building a native result.
