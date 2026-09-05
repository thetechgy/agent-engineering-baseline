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
        @($script:LearnCopilot.mcpServers.PSObject.Properties.Name) | Should-BeCollection @('microsoft-learn')
        $server = $script:LearnCopilot.mcpServers.'microsoft-learn'
        $server.url | Should-Be 'https://learn.microsoft.com/api/mcp'
        $server.type | Should-Be 'http'
        @($server.PSObject.Properties.Name) |
            Should-BeCollection @('url', 'type', 'tools', 'id', 'enabled_tools')
    }

    It 'exposes exactly the reviewed tools through Copilot native and passthrough lists' {
        $script:LearnCopilot.mcpServers.'microsoft-learn'.tools | Should-BeCollection $script:LearnExpectedTools
        $script:LearnCopilot.mcpServers.'microsoft-learn'.enabled_tools | Should-BeCollection $script:LearnExpectedTools
    }

    It 'configures only the official unauthenticated remote server for Codex CLI' {
        $tables = @([regex]::Matches($script:LearnCodex, '(?m)^\[([^\r\n]+)\]\r?$') |
            ForEach-Object { $_.Groups[1].Value })
        $tables | Should-BeCollection @('mcp_servers.microsoft-learn')
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

    It 'records the named Microsoft Learn endpoint in the native lockfile' {
        $servers = [regex]::Match($script:LearnLockfile, '(?ms)^mcp_servers:\r?\n(.*?)(?=^[a-z_]+:|\z)')
        $servers.Success | Should-BeTrue
        $servers.Groups[1].Value.Trim() | Should-Be '- microsoft-learn'
        $configs = [regex]::Match($script:LearnLockfile, '(?ms)^mcp_configs:\r?\n(.*?)(?=^[a-z_]+:|\z)')
        $configs.Success | Should-BeTrue
        $configs.Groups[1].Value | Should-MatchString '(?m)^  microsoft-learn:\r?$'
        $configs.Groups[1].Value | Should-MatchString '(?m)^    name: microsoft-learn\r?$'
        $configs.Groups[1].Value | Should-MatchString '(?m)^    registry: false\r?$'
        $configs.Groups[1].Value | Should-MatchString '(?m)^    transport: http\r?$'
        $configs.Groups[1].Value | Should-MatchString '(?m)^    url: https://learn\.microsoft\.com/api/mcp\r?$'
    }

    It 'restricts locked MCP target ownership to Codex CLI and Copilot CLI' {
        $targets = [regex]::Match($script:LearnLockfile, '(?ms)^mcp_target_servers:\r?\n(.*?)(?=^[a-z_]+:|\z)')
        $targets.Success | Should-BeTrue
        $names = @([regex]::Matches($targets.Groups[1].Value, '(?m)^  ([a-z]+):\r?$') |
            ForEach-Object { $_.Groups[1].Value })
        $names | Should-BeCollection @('codex', 'copilot')
        $servers = @([regex]::Matches($targets.Groups[1].Value, '(?m)^  - ([^\r\n]+)\r?$') |
            ForEach-Object { $_.Groups[1].Value })
        $servers | Should-BeCollection @('microsoft-learn', 'microsoft-learn')
    }
}
