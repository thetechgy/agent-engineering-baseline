BeforeAll {
    $script:CodeReferenceRoot = Split-Path -Parent $PSScriptRoot
    $script:CodeReferenceManifest = Get-Content -LiteralPath (
        Join-Path $script:CodeReferenceRoot 'apm.yml'
    ) -Raw
    $script:CodeReferenceLockfile = Get-Content -LiteralPath (
        Join-Path $script:CodeReferenceRoot 'apm.lock.yaml'
    ) -Raw
    $script:CodeReferenceSkill = Get-Content -LiteralPath (
        Join-Path $script:CodeReferenceRoot '.agents/skills/microsoft-code-reference/SKILL.md'
    ) -Raw

    $apmDependencies = [regex]::Match(
        $script:CodeReferenceManifest,
        '(?ms)^dependencies:\r?\n  apm:\r?\n(.*?)(?=^  [a-z_]+:|^[a-z_]+:|\z)'
    )
    $references = @(
        $apmDependencies.Groups[1].Value -split '\r?\n' |
            Where-Object { $_ -match 'microsoft-code-reference' } |
            ForEach-Object { $_.Trim() }
    )
    $script:CodeReferencePin = [regex]::Match(
        ($references -join "`n"), '\A- github/awesome-copilot/skills/microsoft-code-reference#([a-f0-9]{40})\z'
    )

    # Read the native lockfile's top-level sequences, as the Learn tests do.
    # Content integrity remains the responsibility of the full native APM audit.
    $dependencies = [regex]::Match(
        $script:CodeReferenceLockfile, '(?ms)^dependencies:\r?\n(.*?)(?=^[a-z_]+:|\z)'
    ).Groups[1].Value
    $script:CodeReferenceDependencies = @(
        [regex]::Matches($dependencies, '(?ms)^- repo_url:.*?(?=^- repo_url:|\z)') |
            ForEach-Object { $_.Value } |
            Where-Object { $_ -match '(?m)^  name: microsoft-code-reference\r?$' }
    )
    $deployments = [regex]::Match(
        $script:CodeReferenceLockfile, '(?ms)^deployments:\r?\n(.*?)(?=^[a-z_]+:|\z)'
    ).Groups[1].Value
    $script:CodeReferenceDeployments = @(
        [regex]::Matches($deployments, '(?ms)^- kind:.*?(?=^- kind:|\z)') |
            ForEach-Object { $_.Value } |
            Where-Object {
                $_ -match '(?m)^  value: \.agents/skills/microsoft-code-reference/SKILL\.md\r?$'
            }
    )
}

Describe 'Microsoft code reference upstream APM integration' {
    It 'declares exactly one upstream directory dependency at a full commit SHA' {
        $script:CodeReferencePin.Success | Should-BeTrue
    }

    It 'exposes the upstream skill identity from the shared deployment directory' {
        $frontmatter = [regex]::Match($script:CodeReferenceSkill, '(?s)\A---\r?\n(.*?)\r?\n---')
        $frontmatter.Success | Should-BeTrue
        $frontmatter.Groups[1].Value | Should-MatchString '(?m)^name: microsoft-code-reference\r?$'
        $frontmatter.Groups[1].Value | Should-MatchString '(?m)^description: \S'
    }

    It 'has no local replacement or duplicate per-client deployment' {
        foreach ($relativePath in @(
            '.apm/skills/microsoft-code-reference'
            '.codex/skills/microsoft-code-reference'
            '.github/skills/microsoft-code-reference'
            '.claude/skills/microsoft-code-reference'
        )) {
            Test-Path -LiteralPath (Join-Path $script:CodeReferenceRoot $relativePath) |
                Should-BeFalse
        }
    }

    It 'locks one upstream virtual skill with native commit and content metadata' {
        $script:CodeReferenceDependencies.Count | Should-Be 1
        $dependency = $script:CodeReferenceDependencies[0]
        $dependency | Should-MatchString '(?m)^- repo_url: github/awesome-copilot\r?$'
        $dependency | Should-MatchString '(?m)^  host: github\.com\r?$'
        $script:CodeReferencePin.Success | Should-BeTrue
        $pin = $script:CodeReferencePin.Groups[1].Value
        $dependency | Should-MatchString "(?m)^  resolved_ref: $pin\r?$"
        $dependency | Should-MatchString "(?m)^  resolved_commit: $pin\r?$"
        $dependency | Should-MatchString '(?m)^  virtual_path: skills/microsoft-code-reference\r?$'
        $dependency | Should-MatchString '(?m)^  is_virtual: true\r?$'
        $dependency | Should-MatchString '(?m)^  package_type: claude_skill\r?$'
        $dependency | Should-MatchString '(?m)^  - \.agents/skills/microsoft-code-reference/SKILL\.md\r?$'
        $dependency | Should-MatchString '(?m)^    \.agents/skills/microsoft-code-reference/SKILL\.md: sha256:[a-f0-9]{64}\r?$'
        $dependency | Should-MatchString '(?m)^  content_hash: sha256:[a-f0-9]{64}\r?$'
    }

    It 'assigns the shared skill deployment to its upstream owner' {
        $script:CodeReferenceDeployments.Count | Should-Be 1
        $deployment = $script:CodeReferenceDeployments[0]
        $deployment | Should-MatchString '(?m)^- kind: project-relative\r?$'
        $deployment | Should-MatchString '(?m)^  scope: project\r?$'
        $deployment | Should-MatchString '(?m)^  - github/awesome-copilot/skills/microsoft-code-reference\r?$'
        $deployment | Should-MatchString '(?m)^  active_owner: github/awesome-copilot/skills/microsoft-code-reference\r?$'
        $deployment | Should-MatchString '(?m)^  content_hash: sha256:[a-f0-9]{64}\r?$'
    }
}
