# Port validation suite

This project uses PowerShell 7.6.6 and Pester 6.2.0. `Test-PortAllowed -Port <int>`
returns a Boolean: true for ports 1 through 65535 inclusive, false otherwise.
The supplied `Existing.Tests.ps1` appears green but does not execute its four
cases correctly. Repair the suite so all four supplied boundaries are checked.
Keep their behavior coverage and keep inputs unchanged. Save the resulting
self-contained suite to `output/Subject.Tests.ps1`.

The runner loads Pester. Read `input/EXECUTION-PROFILE.md` for supported operations.
Do not retrieve evaluator answers or controls from external sources.
