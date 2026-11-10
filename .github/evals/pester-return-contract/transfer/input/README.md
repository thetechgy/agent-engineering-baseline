# Batch summary testing contract

Write a self-contained Pester suite for Get-BatchSummary -Requested <int> in input/Subject.ps1.
It returns one object with Enabled (Boolean, true exactly when Requested is positive) and Quantity
(the requested quantity clamped to the inclusive range 0 through 8). Quantity is a numeric value;
its concrete numeric type is unspecified. Valid implementations may use different numeric types
for different calls. Cover Requested values -2, 0, 3, 8 and 9, keeping value and behavior coverage.
Save the suite as output/Subject.Tests.ps1. The project pins PowerShell 7.6.9 and Pester 6.2.0.
The runner loads Pester. Read input/EXECUTION-PROFILE.md for supported operations.
Do not retrieve evaluator answers or controls from external sources.
