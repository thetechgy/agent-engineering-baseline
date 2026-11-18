BeforeAll { . '/workspace/input/Subject.ps1' }

Describe 'Deliberate dependence on the frozen return type' {
    It 'requires Int64 for Requested=3' {
        $actual = Get-BatchSummary -Requested 3
        Should-HaveType -Actual $actual.Quantity -Expected ([long])
    }
}
