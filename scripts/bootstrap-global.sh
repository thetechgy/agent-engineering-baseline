#!/usr/bin/env bash
set -euo pipefail

readonly GITHUB_MCP_NAME='github-mcp-server'
readonly GITHUB_MCP_URL='https://api.githubcopilot.com/mcp/'

usage() {
    cat <<'EOF'
Usage: scripts/bootstrap-global.sh [--dry-run]

Install the repository-approved APM CLI when needed, then use native APM
global install and compile operations to deploy this reviewed baseline.
EOF
}

die() { printf 'Error: %s\n' "$*" >&2; exit 1; }

lock_value() {
    local section=$1 subsection=$2 key=$3
    awk -v section="$section" -v subsection="$subsection" -v key="$key" '
        $0 == section ":" { in_section=1; next }
        in_section && $0 ~ "^  " subsection ":$" { in_subsection=1; next }
        in_section && in_subsection && $0 ~ "^    " key ":" {
            sub("^    " key ":[[:space:]]*", ""); gsub(/^\047|\047$/, ""); print; exit
        }
    ' "$cli_lock"
}

normalize_version() {
    printf '%s\n' "$1" | sed -nE 's/.*[^0-9]([0-9]+\.[0-9]+\.[0-9]+).*/\1/p'
}

compare_versions() {
    local left=$1 right=$2 pair
    local left_major left_minor left_patch right_major right_minor right_patch
    IFS=. read -r left_major left_minor left_patch <<< "$left"
    IFS=. read -r right_major right_minor right_patch <<< "$right"
    for pair in "$left_major:$right_major" "$left_minor:$right_minor" "$left_patch:$right_patch"; do
        if [ "${pair%%:*}" -lt "${pair#*:}" ]; then printf '%s\n' -1; return; fi
        if [ "${pair%%:*}" -gt "${pair#*:}" ]; then printf '%s\n' 1; return; fi
    done
    printf '%s\n' 0
}

verify_github_mcp() {
    command -v codex >/dev/null 2>&1 || return 0
    local state_file error_file
    state_file=$(mktemp "${TMPDIR:-/tmp}/apm-mcp-state.XXXXXX")
    error_file=$(mktemp "${TMPDIR:-/tmp}/apm-mcp-error.XXXXXX")
    if codex mcp get "$GITHUB_MCP_NAME" --json > "$state_file" 2> "$error_file"; then
        command -v jq >/dev/null 2>&1 || die "jq is required to validate the existing '$GITHUB_MCP_NAME' entry."
        jq -e --arg name "$GITHUB_MCP_NAME" --arg url "$GITHUB_MCP_URL" '
            . == {
              name: $name, enabled: true, disabled_reason: null,
              transport: {type: "streamable_http", url: $url,
                bearer_token_env_var: "GITHUB_TOKEN", http_headers: null,
                env_http_headers: null, http_headers_helper: null},
              enabled_tools: null, disabled_tools: null,
              startup_timeout_sec: null, tool_timeout_sec: null
            }
        ' "$state_file" >/dev/null ||
            die "Existing Codex MCP entry '$GITHUB_MCP_NAME' is customized; refusing to replace it."
    elif ! grep -F "No MCP server named '$GITHUB_MCP_NAME' found." "$error_file" >/dev/null; then
        die "Unable to inspect the existing Codex MCP entry '$GITHUB_MCP_NAME'."
    fi
    rm -f -- "$state_file" "$error_file"
}

dry_run=false
case "${1-}" in
    '') ;;
    --dry-run) dry_run=true ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
esac
[ "$#" -le 1 ] || { usage >&2; exit 2; }

script_dir=$(CDPATH='' cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
repo_root=$(CDPATH='' cd -- "$script_dir/.." && pwd -P)
cli_lock="$repo_root/apm-cli.lock.yml"
[ -f "$cli_lock" ] || die "Missing CLI lock: $cli_lock"
[ -f "$repo_root/apm.yml" ] || die "Missing APM manifest: $repo_root/apm.yml"
[ -f "$repo_root/apm.lock.yaml" ] || die "Missing APM dependency lock: $repo_root/apm.lock.yaml"

approved_version=$(awk '$1 == "version:" { print $2; exit }' "$cli_lock")
release_tag=$(awk '$1 == "tag:" { print $2; exit }' "$cli_lock")
installer_url=$(lock_value installers unix url)
installer_sha256=$(lock_value installers unix sha256)
case "$(uname -s):$(uname -m)" in
    Linux:x86_64|Linux:amd64) executable_platform=linux-x86_64 ;;
    Linux:aarch64|Linux:arm64) executable_platform=linux-arm64 ;;
    *) die 'This bootstrap supports the locked Linux x86_64/ARM64 builds; use Bootstrap-Global.ps1 on Windows.' ;;
esac
executable_sha256=$(lock_value artifacts "$executable_platform" executable_sha256)
archive_name=$(lock_value artifacts "$executable_platform" name)
archive_sha256=$(lock_value artifacts "$executable_platform" sha256)
if [ -z "$approved_version" ] || [ -z "$release_tag" ] || [ -z "$installer_url" ] ||
    [ -z "$installer_sha256" ] || [ -z "$archive_name" ] ||
    [ -z "$archive_sha256" ] || [ -z "$executable_sha256" ]; then
    die 'The APM CLI lock is incomplete.'
fi

action=install
installed_version=''
if command -v apm >/dev/null 2>&1; then
    installed_version=$(normalize_version "$(apm --version)")
    [ -n "$installed_version" ] || die 'Unable to parse the installed APM version.'
    comparison=$(compare_versions "$installed_version" "$approved_version")
    if [ "$comparison" -gt 0 ]; then
        die "Installed APM $installed_version is newer than reviewed baseline $approved_version; deployment stopped."
    elif [ "$comparison" -eq 0 ]; then action=none; else action=upgrade; fi
fi

verify_github_mcp

if [ "$dry_run" = true ]; then
    printf 'Dry run: APM CLI action: %s (approved version %s' "$action" "$approved_version"
    [ -z "$installed_version" ] || printf ', installed version %s' "$installed_version"
    printf ').\n'
    printf '%s\n' 'Dry run: would run apm install --global --frozen and apm compile --global.'
    printf '%s\n' 'Dry run: no files were downloaded or changed.'
    exit 0
fi

if [ "$action" != none ]; then
    command -v curl >/dev/null 2>&1 || die 'curl is required to install the approved APM CLI.'
    command -v sha256sum >/dev/null 2>&1 || die 'sha256sum is required to verify the APM installer.'
    installer_path=$(mktemp "${TMPDIR:-/tmp}/apm-install.XXXXXX")
    archive_path=$(mktemp "${TMPDIR:-/tmp}/apm-archive.XXXXXX")
    trap 'rm -f -- "$installer_path" "$archive_path"' EXIT HUP INT TERM
    curl --fail --location --silent --show-error --output "$installer_path" "$installer_url"
    printf '%s  %s\n' "$installer_sha256" "$installer_path" | sha256sum --check --status - ||
        die 'The downloaded APM installer does not match apm-cli.lock.yml.'
    curl --fail --location --silent --show-error --output "$archive_path" \
        "https://github.com/microsoft/apm/releases/download/$release_tag/$archive_name"
    printf '%s  %s\n' "$archive_sha256" "$archive_path" | sha256sum --check --status - ||
        die 'The downloaded APM release archive does not match apm-cli.lock.yml.'
    VERSION="v$approved_version" sh "$installer_path"
    hash -r
    rm -f -- "$installer_path" "$archive_path"
    trap - EXIT HUP INT TERM
    verified_version=$(normalize_version "$(apm --version)")
    [ "$verified_version" = "$approved_version" ] ||
        die "APM installation completed but version $approved_version is not active."
    command -v readlink >/dev/null 2>&1 || die 'readlink is required to verify the installed APM executable.'
    installed_executable=$(readlink -f "$(command -v apm)")
    printf '%s  %s\n' "$executable_sha256" "$installed_executable" | sha256sum --check --status - ||
        die 'The installed APM executable does not match apm-cli.lock.yml.'
fi

(
    cd "$repo_root"
    apm install --global --frozen
    apm compile --global --dry-run
    apm compile --global
)

printf 'Global APM baseline %s is ready.\n' "$approved_version"
printf '%s\n' 'Set GITHUB_TOKEN at runtime for the GitHub MCP server and start new agent sessions.'
