# Scheduling window tests

Use PowerShell 7.6.9 and Pester 6.2.0. Test-WindowAllowed -Slot <int> returns
true for slots 8 through 32 inclusive and false otherwise. The existing suite
appears green but does not execute its four supplied boundaries. Repair it so
slots 7, 8, 32 and 33 are all checked. Keep input files unchanged and save the
self-contained suite as output/Subject.Tests.ps1. The supplied runner loads Pester.
Read input/EXECUTION-PROFILE.md for supported operations.
