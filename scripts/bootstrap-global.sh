#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: scripts/bootstrap-global.sh [--dry-run]

Install the pinned APM CLI when needed, then deploy this baseline with the
native APM global install and compile commands.
EOF
}

die() { printf 'Error: %s\n' "$*" >&2; exit 1; }

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
version_file="$repo_root/.apm-version"
checksums_file="$repo_root/.apm-installer-checksums"
[ -f "$version_file" ] || die "Missing APM version pin: $version_file"
[ -f "$checksums_file" ] || die "Missing APM installer checksums: $checksums_file"
[ -f "$repo_root/apm.yml" ] || die "Missing APM manifest: $repo_root/apm.yml"
[ -f "$repo_root/apm.lock.yaml" ] || die "Missing APM dependency lock: $repo_root/apm.lock.yaml"

approved_version=$(head -n 1 "$version_file" | tr -d '[:space:]')
printf '%s\n' "$approved_version" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$' ||
    die "The APM version pin is not a plain X.Y.Z version: $approved_version"

action=install
installed_version=''
if command -v apm >/dev/null 2>&1; then
    installed_version=$(normalize_version "$(apm --version)")
    [ -n "$installed_version" ] || die 'Unable to parse the installed APM version.'
    comparison=$(compare_versions "$installed_version" "$approved_version")
    if [ "$comparison" -gt 0 ]; then
        die "Installed APM $installed_version is newer than pinned baseline $approved_version; deployment stopped."
    elif [ "$comparison" -eq 0 ]; then action=none; else action=upgrade; fi
fi

if [ "$dry_run" = true ]; then
    printf 'Dry run: APM CLI action: %s (pinned version %s' "$action" "$approved_version"
    [ -z "$installed_version" ] || printf ', installed version %s' "$installed_version"
    printf ').\n'
    printf '%s\n' 'Dry run: would run apm install --global --frozen and apm compile --global.'
    printf '%s\n' 'Dry run: no files were downloaded or changed.'
    exit 0
fi

if [ "$action" != none ]; then
    command -v curl >/dev/null 2>&1 || die 'curl is required to install the pinned APM CLI.'
    command -v sha256sum >/dev/null 2>&1 || die 'sha256sum is required to verify the pinned APM installer.'
    expected_hash=$(awk '$2 == "install.sh" { print $1; exit }' "$checksums_file")
    printf '%s\n' "$expected_hash" | grep -Eq '^[0-9a-f]{64}$' ||
        die "The pinned install.sh checksum is not a SHA256 hex digest: $expected_hash"
    installer_path=$(mktemp "${TMPDIR:-/tmp}/apm-install.XXXXXX")
    trap 'rm -f -- "$installer_path"' EXIT HUP INT TERM
    curl --fail --location --silent --show-error --output "$installer_path" \
        "https://raw.githubusercontent.com/microsoft/apm/v$approved_version/install.sh"
    actual_hash=$(sha256sum "$installer_path" | awk '{ print $1 }')
    [ "$actual_hash" = "$expected_hash" ] ||
        die 'Downloaded install.sh does not match the pinned SHA256 checksum; refusing to execute it.'
    VERSION="v$approved_version" sh "$installer_path"
    rm -f -- "$installer_path"
    trap - EXIT HUP INT TERM
    hash -r
    if ! command -v apm >/dev/null 2>&1; then
        # The installer may target a directory missing from this shell's PATH.
        for candidate in "$HOME/.local/bin" /usr/local/bin; do
            if [ -x "$candidate/apm" ]; then
                PATH="$candidate:$PATH"
                export PATH
                break
            fi
        done
        hash -r
    fi
    command -v apm >/dev/null 2>&1 ||
        die 'APM installation completed but apm is not on PATH; add its install directory to PATH and rerun.'
    verified_version=$(normalize_version "$(apm --version)")
    [ "$verified_version" = "$approved_version" ] ||
        die "APM installation completed but version $approved_version is not active."
fi

(
    cd "$repo_root"
    apm install --global --frozen
    apm compile --global --dry-run
    apm compile --global
)

printf 'Global APM baseline %s is ready.\n' "$approved_version"
printf '%s\n' 'Set GITHUB_TOKEN at runtime for the GitHub MCP server and start new agent sessions.'
