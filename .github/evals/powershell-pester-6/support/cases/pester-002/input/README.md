# Retry delay contract

This project uses PowerShell 7.6.6 and Pester 6.2.0.

`Get-RetryDelay -Attempt <int> [-BaseMilliseconds <int>]` returns an integer
number of milliseconds. Attempts 1 through 4 return the base multiplied by
2 to the power of (attempt minus 1). The default base is 100; valid bases are
1 through 1000. Attempts outside 1 through 4 throw `ArgumentOutOfRangeException`.

Run from `/workspace`. Keep inputs unchanged and write only
`output/Subject.Tests.ps1`. The supplied runner loads the testing framework;
agent-written runners and claimed results are not grading evidence.
Read `input/EXECUTION-PROFILE.md` for supported operations. Do not retrieve
evaluator answers or controls from external sources.
