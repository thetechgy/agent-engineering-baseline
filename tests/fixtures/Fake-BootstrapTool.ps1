[CmdletBinding()]
param(
    [Parameter(Mandatory, Position = 0)]
    [ValidateSet('apm', 'codex')]
    [string]$Tool,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ToolArgument
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$homePath = $env:FAKE_HOME
if ([string]::IsNullOrWhiteSpace($homePath)) {
    throw 'FAKE_HOME must be set.'
}

Add-Content -LiteralPath (Join-Path $homePath '.fake-command.log') `
    -Value ("{0} {1}" -f $Tool, ($ToolArgument -join ' '))

function Write-DefaultMcpState {
    $json = @'
{
  "name": "github-mcp-server",
  "enabled": true,
  "disabled_reason": null,
  "transport": {
    "type": "streamable_http",
    "url": "https://api.githubcopilot.com/mcp/",
    "bearer_token_env_var": "GITHUB_TOKEN",
    "http_headers": null,
    "env_http_headers": null,
    "http_headers_helper": null
  },
  "enabled_tools": null,
  "disabled_tools": null,
  "startup_timeout_sec": null,
  "tool_timeout_sec": null
}
'@
    Set-Content -LiteralPath (Join-Path $homePath '.fake-github-mcp.json') -Value $json -Encoding UTF8
}

if ($Tool -ceq 'codex') {
    $statePath = Join-Path $homePath '.fake-github-mcp.json'
    if ($ToolArgument.Count -ge 2 -and
        $ToolArgument[0] -ceq 'mcp' -and
        $ToolArgument[1] -ceq 'get') {
        if ($env:FAKE_CODEX_FAIL_GET -ceq '1') {
            [Console]::Error.WriteLine('Error: unable to inspect Codex MCP configuration.')
            exit 30
        }
        if (Test-Path -LiteralPath $statePath -PathType Leaf) {
            Get-Content -LiteralPath $statePath -Raw
            exit 0
        }
        [Console]::Error.WriteLine("Error: No MCP server named 'github-mcp-server' found.")
        exit 1
    }

    if ($ToolArgument.Count -ge 2 -and
        $ToolArgument[0] -ceq 'mcp' -and
        $ToolArgument[1] -ceq 'remove') {
        if ($env:FAKE_CODEX_FAIL_REMOVE -ceq '1') {
            exit 31
        }
        Remove-Item -LiteralPath $statePath -Force -ErrorAction SilentlyContinue
        $configPath = Join-Path $homePath '.codex/config.toml'
        if (Test-Path -LiteralPath $configPath -PathType Leaf) {
            $output = [System.Collections.Generic.List[string]]::new()
            $skipping = $false
            foreach ($line in [System.IO.File]::ReadAllLines($configPath)) {
                if ($line -ceq '[mcp_servers.github-mcp-server]') {
                    $skipping = $true
                    continue
                }
                if ($skipping -and $line -match '^\[') {
                    $skipping = $false
                }
                if (-not $skipping) {
                    $output.Add($line)
                }
            }
            [System.IO.File]::WriteAllLines($configPath, $output)
        }
        exit 0
    }
    exit 32
}

if ($ToolArgument.Count -gt 0 -and $ToolArgument[0] -ceq '--version') {
    $version = if ([string]::IsNullOrWhiteSpace($env:FAKE_APM_VERSION)) {
        '0.28.0'
    }
    else {
        $env:FAKE_APM_VERSION
    }
    Write-Output "APM $version"
    exit 0
}

if ($ToolArgument.Count -gt 0 -and $ToolArgument[0] -ceq 'install') {
    if ($env:FAKE_APM_FAIL_STAGE -ceq 'install') {
        exit 41
    }

    foreach ($skillName in @('code-simplification', 'dependabot', 'git-commit', 'github-actions-hardening', 'msgraph')) {
        $skillPath = Join-Path $homePath ".agents/skills/$skillName"
        $null = New-Item -ItemType Directory -Path $skillPath -Force
        Set-Content -LiteralPath (Join-Path $skillPath 'SKILL.md') -Value "installed $skillName"
    }
    $modulePath = Join-Path $homePath '.apm/apm_modules/fake'
    $null = New-Item -ItemType Directory -Path $modulePath -Force
    Set-Content -LiteralPath (Join-Path $modulePath 'state') -Value 'installed'
    Set-Content -LiteralPath (Join-Path $homePath '.apm/config.json') -Value '{"installed":true}'
    if ($env:FAKE_APM_REINTRODUCE_COPILOT_MCP -ceq '1') {
        $copilotDirectory = Join-Path $homePath '.copilot'
        $null = New-Item -ItemType Directory -Path $copilotDirectory -Force
        $copilotJson = @'
{
  "mcpServers": {
    "github-\u006dcp-server": {
      "type": "http",
      "url": "https://api.githubcopilot.com/mcp/",
      "tools": ["*"],
      "id": "",
      "headers": {},
      "bearer_token_env_var": "GITHUB_TOKEN"
    }
  }
}
'@
        Set-Content -LiteralPath (Join-Path $copilotDirectory 'mcp-config.json') `
            -Value $copilotJson -Encoding UTF8
    }
    exit 0
}

if ($ToolArgument.Count -gt 0 -and $ToolArgument[0] -ceq 'compile') {
    $target = $null
    $outputPath = $null
    $dryRun = $false
    for ($index = 1; $index -lt $ToolArgument.Count; $index++) {
        switch ($ToolArgument[$index]) {
            '--target' {
                $index++
                $target = $ToolArgument[$index]
            }
            '--output' {
                $index++
                $outputPath = $ToolArgument[$index]
            }
            '--dry-run' {
                $dryRun = $true
            }
        }
    }

    $stage = if ($dryRun) { "compile-dry-$target" } else { "compile-write-$target" }
    if ($env:FAKE_APM_FAIL_STAGE -ceq $stage) {
        exit 42
    }
    if (-not $dryRun) {
        $null = New-Item -ItemType Directory -Path (Split-Path -Parent $outputPath) -Force
        Set-Content -LiteralPath $outputPath -Value @(
            '# AGENTS.md'
            '<!-- Generated by APM CLI from .apm/ primitives -->'
            $target
        )
    }
    exit 0
}

exit 43
