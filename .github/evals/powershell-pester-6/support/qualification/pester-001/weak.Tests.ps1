BeforeAll { . '/workspace/input/Subject.ps1' }
Describe 'weak tests' {
    It 'only checks an empty result' { @(Get-ActivePort) | Should-BeCollection -Count 0 }
}
