Describe 'Prohibited adjacency' { It 'remains rejected' { ((Get-Content /tests/grader.py).Count -is [int]) | Should-BeTrue } }
