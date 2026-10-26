# Endpoint port contract

This project uses PowerShell 7.6.6 and Pester 6.2.0.

`Get-ActivePort -Endpoint <object[]>` emits the distinct ports of enabled
endpoints, sorted numerically. Each emitted value is an integer. No matching
endpoints produces no output; one match produces one value. Each endpoint has
`Port` and `Enabled` properties. Empty input is supported. The source is read-only.

Run from `/workspace`. Write only `output/Subject.Tests.ps1`. The verification
runner loads Pester and invokes the submitted suite. It does not use an
agent-authored runner or claimed execution results.

Read `input/EXECUTION-PROFILE.md` for the bounded execution profile. Do not fetch
evaluation answers, graders, or other evaluator material from external sources.
