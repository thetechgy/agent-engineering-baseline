BeforeAll {
    $repositoryRoot = Split-Path -Parent $PSScriptRoot
    $script:LearnExpectedTools = @(
        'microsoft_docs_search'
        'microsoft_docs_fetch'
        'microsoft_code_sample_search'
    )
    $script:LearnCopilot = Get-Content -LiteralPath (Join-Path $repositoryRoot '.github/mcp.json') -Raw |
        ConvertFrom-Json -ErrorAction Stop
    $script:LearnCodex = Get-Content -LiteralPath (Join-Path $repositoryRoot '.codex/config.toml') -Raw
    $script:LearnLockfile = Get-Content -LiteralPath (Join-Path $repositoryRoot 'apm.lock.yaml') -Raw
}

Describe 'Microsoft Learn generated MCP configuration' {
    It 'configures only the official unauthenticated remote server for Copilot CLI' {
        @($script:LearnCopilot.mcpServers.PSObject.Properties.Name) | Should-BeCollection @('mcp')
        $server = $script:LearnCopilot.mcpServers.mcp
        $server.url | Should-Be 'https://learn.microsoft.com/api/mcp'
        $server.type | Should-Be 'http'
        @($server.PSObject.Properties.Name) |
            Should-BeCollection @('url', 'type', 'tools', 'id', 'enabled_tools')
    }

    It 'exposes exactly the reviewed tools through Copilot native and passthrough lists' {
        $script:LearnCopilot.mcpServers.mcp.tools | Should-BeCollection $script:LearnExpectedTools
        $script:LearnCopilot.mcpServers.mcp.enabled_tools | Should-BeCollection $script:LearnExpectedTools
    }

    It 'configures only the official unauthenticated remote server for Codex CLI' {
        $tables = @([regex]::Matches($script:LearnCodex, '(?m)^\[([^\r\n]+)\]\r?$') |
            ForEach-Object { $_.Groups[1].Value })
        $tables | Should-BeCollection @('mcp_servers.mcp')
        $script:LearnCodex | Should-MatchString '(?m)^url = "https://learn\.microsoft\.com/api/mcp"\r?$'
        $keys = @([regex]::Matches($script:LearnCodex, '(?m)^([a-z_]+)\s*=') |
            ForEach-Object { $_.Groups[1].Value })
        $keys | Should-BeCollection @('url', 'id', 'enabled_tools')
    }

    It 'exposes exactly the reviewed tools through the Codex native allowlist' {
        # APM's generated string-only TOML array also uses valid JSON syntax.
        $allowlist = [regex]::Match($script:LearnCodex, '(?m)^enabled_tools = (\[[^\r\n]*\])\r?$')
        $allowlist.Success | Should-BeTrue
        # Pass -Actual: Windows PowerShell 5.1 ConvertFrom-Json emits the array as
        # one pipeline object, which Should-BeCollection would treat as one item.
        $allowlistTools = ConvertFrom-Json -InputObject $allowlist.Groups[1].Value -ErrorAction Stop
        Should-BeCollection -Actual $allowlistTools -Expected $script:LearnExpectedTools
    }

    It 'records the Microsoft Learn registry dependency in the native lockfile' {
        $servers = [regex]::Match($script:LearnLockfile, '(?ms)^mcp_servers:\r?\n(.*?)(?=^[a-z_]+:|\z)')
        $servers.Success | Should-BeTrue
        $servers.Groups[1].Value.Trim() | Should-Be '- microsoftdocs/mcp'
    }

    It 'restricts locked MCP target ownership to Codex CLI and Copilot CLI' {
        $targets = [regex]::Match($script:LearnLockfile, '(?ms)^mcp_target_servers:\r?\n(.*?)(?=^[a-z_]+:|\z)')
        $targets.Success | Should-BeTrue
        $names = @([regex]::Matches($targets.Groups[1].Value, '(?m)^  ([a-z]+):\r?$') |
            ForEach-Object { $_.Groups[1].Value })
        $names | Should-BeCollection @('codex', 'copilot')
        $servers = @([regex]::Matches($targets.Groups[1].Value, '(?m)^  - ([^\r\n]+)\r?$') |
            ForEach-Object { $_.Groups[1].Value })
        $servers | Should-BeCollection @('microsoftdocs/mcp', 'microsoftdocs/mcp')
    }
}
