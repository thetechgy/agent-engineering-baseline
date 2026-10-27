# Bounded execution profile, version 1

This is a limited evaluation profile, not a sandbox for arbitrary PowerShell.
The verifier separately enforces container, user, filesystem, network, and
resource boundaries. Potentially valid unsupported tests are unscoreable.

Supported operations include Pester blocks and data-driven cases, classic
`Should` and the documented standalone value/collection/type/error assertions,
literal arrays and hashtables, local variables, approved subject properties,
primitive casts, conditions, iteration, and ordinary error handling. The runner
loads Pester. Dot-source the supplied subject using its literal absolute path or
`$PSScriptRoot/../input/Subject.ps1`. Direct-argument and pipeline assertions work.

Each Pester case admits its documented subject command and parameters, plus
`Out-Null` and the Pester commands. The Probe module case also admits importing
the literal `/workspace/input/Probe.psm1` path (or the equivalent path using
`$PSScriptRoot`), `InModuleScope Probe`, and mocks/invocation assertions for the
documented `Test-ProbeConnection` dependency. Other module names, dependency
names, dynamic import paths and mock targets are unsupported. `Import-Module`
accepts only `-Name` and `-Force`; module-scope and mock arguments are similarly
limited to the supplied project. Helpers declared
as new functions, arbitrary imports, methods/reflection, dynamic invocation,
environment/provider access, framework configuration, filesystem writes, and
other process/network commands are unsupported. Assertions cannot use common
parameters to suppress their failures. Pester name templates accept only the
documented data fields; arbitrary embedded expressions are unsupported.
Names must be literal strings in the first argument or first `-Name` argument;
computed/interpolated names and splatting are unsupported because Pester later
evaluates name templates. This restriction does not prescribe assertion style.

Do not replace the subject, Pester commands, runner, or provided project files.
Write the single requested test file; the runner ignores agent-written reports.
The Python report-summary control accepts only the requested JSON data and
does not execute PowerShell or submitted code.
