#!/usr/bin/env bash
# Acquire the reviewed APM CLI bundle, then deploy the baseline with native APM.
set -euo pipefail

SCRIPT_SOURCE=${BASH_SOURCE[0]:-$0}
case "$SCRIPT_SOURCE" in
    /*|./*|../*) ;;
    *) SCRIPT_SOURCE="./$SCRIPT_SOURCE" ;;
esac
readonly SCRIPT_SOURCE
SCRIPT_DIR="$(CDPATH='' cd "$(dirname "$SCRIPT_SOURCE")" && pwd -P)"
readonly SCRIPT_DIR
REPOSITORY_ROOT="$(CDPATH='' cd "$SCRIPT_DIR/.." && pwd -P)"
readonly REPOSITORY_ROOT
readonly PIN_FILE="$REPOSITORY_ROOT/.apm-version"
readonly CHECKSUMS_FILE="$REPOSITORY_ROOT/.apm-checksums"
readonly DEFAULT_PACKAGE_REF='https://github.com/thetechgy/agent-engineering-baseline.git#main'

MODE='global'
DRY_RUN=false
CLI_ONLY=false
TEMP_ROOT=''
ORIGINAL_PATH=$PATH

usage() {
    cat <<'USAGE'
Usage: bootstrap.sh [--global | --repo] [--cli-only] [--dry-run]

  --global    Install the baseline at user scope. Default.
  --repo      Install the baseline into the current repository.
  --cli-only  Acquire the reviewed CLI without installing the baseline.
  --dry-run   Validate local pin/checksum metadata without making changes.

Environment:
  APM_INSTALL_DIR       CLI shim directory (default: ~/.local/bin).
  APM_RELEASE_BASE_URL  Authoritative HTTPS or file mirror base URL.
  APM_NO_DIRECT_FALLBACK
                        If truthy, require APM_RELEASE_BASE_URL.
  BASELINE_PACKAGE_REF  Package reference installed by native APM.
USAGE
}

log() { printf 'bootstrap: %s\n' "$*"; }
die() { printf 'bootstrap: error: %s\n' "$*" >&2; exit 1; }

cleanup() {
    if [ -n "$TEMP_ROOT" ] && [ -d "$TEMP_ROOT" ]; then
        case "$TEMP_ROOT" in
            /*) rm -rf "$TEMP_ROOT" ;;
            *) log "warning: refusing to clean non-absolute staging path: $TEMP_ROOT" ;;
        esac
    fi
}
trap cleanup EXIT HUP INT TERM

require_command() {
    command -v "$1" >/dev/null 2>&1 || die "required command is unavailable: $1"
}

is_truthy() {
    case "${1-}" in
        1|true|TRUE|True|yes|YES|Yes|on|ON|On) return 0 ;;
        *) return 1 ;;
    esac
}

read_pin() {
    if [ ! -f "$PIN_FILE" ] || [ -L "$PIN_FILE" ]; then
        die ".apm-version is missing or linked: $PIN_FILE"
    fi
    local line_count pin
    line_count=$(awk 'END { print NR }' "$PIN_FILE")
    [ "$line_count" -eq 1 ] || die '.apm-version must contain exactly one line.'
    pin=$(tr -d '\r\n' < "$PIN_FILE")
    printf '%s\n' "$pin" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+(a[0-9]+|b[0-9]+|rc[0-9]+)?$' ||
        die ".apm-version must contain a full APM version, got: '$pin'"
    printf '%s\n' "$pin"
}

validate_checksums() {
    if [ ! -f "$CHECKSUMS_FILE" ] || [ -L "$CHECKSUMS_FILE" ]; then
        die ".apm-checksums is missing or linked: $CHECKSUMS_FILE"
    fi
    local expected_names name
    expected_names='apm-darwin-arm64.tar.gz
apm-darwin-arm64/apm
apm-darwin-x86_64.tar.gz
apm-darwin-x86_64/apm
apm-linux-arm64.tar.gz
apm-linux-arm64/apm
apm-linux-x86_64.tar.gz
apm-linux-x86_64/apm
apm-windows-x86_64.zip
apm-windows-x86_64/apm.exe'

    awk '
        NF != 2 || length($1) != 64 || $1 !~ /^[0-9a-f]+$/ { exit 1 }
        END { if (NR != 10) exit 1 }
    ' "$CHECKSUMS_FILE" ||
        die '.apm-checksums must contain exactly ten lowercase SHA256/name entries.'

    while IFS= read -r name; do
        [ "$(awk -v expected="$name" '$2 == expected { count++ } END { print count + 0 }' "$CHECKSUMS_FILE")" -eq 1 ] ||
            die "Expected exactly one checksum for $name."
    done <<EOF
$expected_names
EOF
}

get_checksum() {
    awk -v expected="$1" '$2 == expected { print $1 }' "$CHECKSUMS_FILE"
}

select_platform() {
    local os machine
    os=$(uname -s)
    machine=$(uname -m)
    case "$machine" in
        x86_64|amd64) PLATFORM_ARCH='x86_64' ;;
        arm64|aarch64) PLATFORM_ARCH='arm64' ;;
        *) die "unsupported architecture: $machine" ;;
    esac
    case "$os" in
        Linux) PLATFORM_OS='linux'; HASH_COMMAND='sha256sum' ;;
        Darwin) PLATFORM_OS='darwin'; HASH_COMMAND='shasum' ;;
        *) die "unsupported operating system: $os" ;;
    esac
    ARCHIVE_NAME="apm-$PLATFORM_OS-$PLATFORM_ARCH.tar.gz"
    ARCHIVE_ROOT="apm-$PLATFORM_OS-$PLATFORM_ARCH"
    EXECUTABLE_MEMBER="$ARCHIVE_ROOT/apm"
}

sha256_file() {
    if [ "$HASH_COMMAND" = sha256sum ]; then
        sha256sum "$1" | awk '{ print $1 }'
    else
        shasum -a 256 "$1" | awk '{ print $1 }'
    fi
}

verify_file() {
    local path=$1 name=$2 expected actual
    if [ ! -f "$path" ] || [ -L "$path" ]; then
        die "$name is not a regular unlinked file."
    fi
    expected=$(get_checksum "$name")
    actual=$(sha256_file "$path")
    [ "$actual" = "$expected" ] || die "$name does not match its reviewed SHA256 digest."
}

validate_tar_archive() {
    local archive_path=$1 list_path="$TEMP_ROOT/archive.list" verbose_path="$TEMP_ROOT/archive.verbose"
    tar -tzf "$archive_path" > "$list_path" || die "unable to list $ARCHIVE_NAME."
    tar -tvzf "$archive_path" > "$verbose_path" || die "unable to inspect $ARCHIVE_NAME entry types."
    awk -v root="$ARCHIVE_ROOT" -v executable="$EXECUTABLE_MEMBER" '
        BEGIN { valid = 1; executable_count = 0; internal_file_count = 0 }
        {
            path = $0
            sub(/\r$/, "", path)
            if (path == executable) executable_count++
            if (path != root && path != root "/" && index(path, root "/") != 1) valid = 0
            if (path ~ /^\// || path ~ /(^|\/)\.\.($|\/)/) valid = 0
            if (index(path, root "/_internal/") == 1 && path !~ /\/$/) internal_file_count++
        }
        END { exit(valid && executable_count == 1 && internal_file_count > 0 ? 0 : 1) }
    ' "$list_path" || die "$ARCHIVE_NAME has an unexpected root, traversal, executable count, or missing _internal tree."
    awk 'substr($0, 1, 1) != "-" && substr($0, 1, 1) != "d" { exit 1 }' "$verbose_path" ||
        die "$ARCHIVE_NAME contains a link or unsupported entry type."
}

assert_plain_tree() {
    local path=$1 label=$2 linked unsupported
    if [ ! -d "$path" ] || [ -L "$path" ]; then
        die "$label is not an unlinked directory."
    fi
    linked=$(find "$path" -type l -print -quit)
    [ -z "$linked" ] || die "$label contains a symbolic link: $linked"
    unsupported=$(find "$path" ! -type d ! -type f -print -quit)
    [ -z "$unsupported" ] || die "$label contains an unsupported entry: $unsupported"
}

reported_version() {
    local executable=$1 banner version
    if ! banner=$("$executable" --version 2>&1); then
        die 'the staged APM executable failed its version postcondition.'
    fi
    version=$(printf '%s\n' "$banner" |
        grep -Eo '[0-9]+\.[0-9]+\.[0-9]+(a[0-9]+|b[0-9]+|rc[0-9]+)?' |
        head -n 1 || true)
    [ -n "$version" ] || die 'the staged APM executable did not report a full version.'
    printf '%s\n' "$version"
}

download_archive() {
    local destination=$1 base=${APM_RELEASE_BASE_URL-} url
    if [ -n "$base" ]; then
        case "$base" in
            *://*'@'*) die 'APM_RELEASE_BASE_URL must not contain credentials.' ;;
            https://*|file://*) ;;
            *) die 'APM_RELEASE_BASE_URL must use https:// or file://.' ;;
        esac
        url="${base%/}/v$PIN/$ARCHIVE_NAME"
    else
        is_truthy "${APM_NO_DIRECT_FALLBACK-}" &&
            die 'APM_NO_DIRECT_FALLBACK is truthy but no APM_RELEASE_BASE_URL is configured.'
        url="https://github.com/microsoft/apm/releases/download/v$PIN/$ARCHIVE_NAME"
    fi
    log "downloading $ARCHIVE_NAME"
    if [ -n "$base" ]; then
        curl --fail --location --silent --show-error --proto '=https,file' \
            --proto-redir '=https,file' --output "$destination" "$url"
    else
        curl --fail --location --silent --show-error --proto '=https' \
            --proto-redir '=https' --tlsv1.2 --output "$destination" "$url"
    fi
}

assert_safe_directory() {
    local path=$1 label=$2 current=$1
    case "$current" in
        /*) ;;
        *) die "$label is not an absolute directory path: $path" ;;
    esac
    while [ "$current" != / ]; do
        case "$current" in
            */) current=${current%/}; continue ;;
        esac
        if [ -L "$current" ]; then
            die "$label has a symlinked path component: $current"
        fi
        current=${current%/*}
        [ -n "$current" ] || current=/
    done
    if [ -e "$path" ] || [ -L "$path" ]; then
        if [ ! -d "$path" ] || [ -L "$path" ]; then
            die "$label is not a safe directory: $path"
        fi
    fi
}

promote_bundle() {
    local source_bundle=$1 install_parent bundle_parent bundle_path link_path
    local stage_path backup_path old_link_target='' had_bundle=false had_link=false failed=false
    install_parent=$(dirname "$INSTALL_DIR")
    bundle_parent="$install_parent/lib"
    bundle_path="$bundle_parent/apm"
    link_path="$INSTALL_DIR/apm"
    stage_path="$bundle_parent/.apm-stage-$$"
    backup_path="$bundle_parent/.apm-rollback-$$"

    assert_safe_directory "$install_parent" 'APM installation parent'
    assert_safe_directory "$INSTALL_DIR" 'APM shim directory'
    assert_safe_directory "$bundle_parent" 'APM bundle parent'
    mkdir -p "$INSTALL_DIR" "$bundle_parent"

    if [ -e "$bundle_path" ] || [ -L "$bundle_path" ]; then
        assert_plain_tree "$bundle_path" 'Existing managed APM bundle'
        if [ ! -f "$bundle_path/.apm-installed" ] || [ -L "$bundle_path/.apm-installed" ]; then
            die "refusing to replace an unowned APM bundle: $bundle_path"
        fi
        had_bundle=true
    fi
    if [ -e "$link_path" ] || [ -L "$link_path" ]; then
        [ -L "$link_path" ] || die "refusing to overwrite unrelated APM command: $link_path"
        old_link_target=$(readlink "$link_path")
        [ "$old_link_target" = "$bundle_path/apm" ] ||
            die "refusing to overwrite an unrelated APM symlink: $link_path"
        had_link=true
    fi
    if [ -e "$stage_path" ] || [ -L "$stage_path" ] ||
        [ -e "$backup_path" ] || [ -L "$backup_path" ]; then
        die 'a stale APM promotion path already exists.'
    fi

    mkdir "$stage_path"
    cp -R "$source_bundle/." "$stage_path/"
    chmod +x "$stage_path/apm"
    printf 'v%s\n' "$PIN" > "$stage_path/.apm-installed"
    assert_plain_tree "$stage_path" 'Staged persistent APM bundle'
    verify_file "$stage_path/apm" "$EXECUTABLE_MEMBER"

    if [ "$had_bundle" = true ] && ! mv "$bundle_path" "$backup_path"; then failed=true; fi
    if [ "$failed" = false ] && ! mv "$stage_path" "$bundle_path"; then failed=true; fi
    if [ "$failed" = false ] && [ "$had_link" = true ] && ! rm "$link_path"; then failed=true; fi
    if [ "$failed" = false ] && ! ln -s "$bundle_path/apm" "$link_path"; then failed=true; fi

    if [ "$failed" = true ]; then
        [ ! -L "$link_path" ] || rm -f "$link_path"
        if [ -d "$bundle_path" ] && { [ "$had_bundle" = false ] || [ -d "$backup_path" ]; }; then
            rm -rf "$bundle_path"
        fi
        if [ -d "$backup_path" ]; then mv "$backup_path" "$bundle_path" || true; fi
        if [ "$had_link" = true ] && [ ! -e "$link_path" ] && [ ! -L "$link_path" ]; then
            ln -s "$old_link_target" "$link_path" || true
        fi
        die 'APM bundle promotion failed; the prior managed installation was restored.'
    fi
    [ ! -d "$backup_path" ] || rm -rf "$backup_path"
    PROMOTED_APM="$bundle_path/apm"
    verify_file "$PROMOTED_APM" "$EXECUTABLE_MEMBER"
    [ "$(reported_version "$PROMOTED_APM")" = "$PIN" ] ||
        die "the promoted APM CLI does not report the pinned v$PIN."
}

acquire_cli() {
    local temp_parent=${TMPDIR:-/tmp}
    require_command awk
    require_command curl
    require_command find
    require_command grep
    require_command head
    require_command mktemp
    require_command tar
    require_command uname
    select_platform
    require_command "$HASH_COMMAND"

    case "$temp_parent" in
        /*|./*|../*) ;;
        *) temp_parent="./$temp_parent" ;;
    esac
    temp_parent=$(CDPATH='' cd "$temp_parent" && pwd -P) ||
        die "temporary directory is unavailable: ${TMPDIR:-/tmp}"
    TEMP_ROOT=$(mktemp -d "$temp_parent/apm-bootstrap.XXXXXX")
    local archive_path="$TEMP_ROOT/$ARCHIVE_NAME" extract_root="$TEMP_ROOT/extract"
    mkdir "$extract_root"
    download_archive "$archive_path"
    verify_file "$archive_path" "$ARCHIVE_NAME"
    validate_tar_archive "$archive_path"
    tar -xzf "$archive_path" -C "$extract_root"
    assert_plain_tree "$extract_root/$ARCHIVE_ROOT" 'Extracted APM bundle'
    [ -d "$extract_root/$ARCHIVE_ROOT/_internal" ] || die 'the extracted APM bundle is missing _internal.'
    verify_file "$extract_root/$EXECUTABLE_MEMBER" "$EXECUTABLE_MEMBER"
    chmod +x "$extract_root/$EXECUTABLE_MEMBER"
    [ "$(reported_version "$extract_root/$EXECUTABLE_MEMBER")" = "$PIN" ] ||
        die "the staged APM CLI does not report the pinned v$PIN."
    promote_bundle "$extract_root/$ARCHIVE_ROOT"
}

warn_if_shadowed() {
    local discovered
    discovered=$(PATH="$ORIGINAL_PATH" command -v apm 2>/dev/null || true)
    if [ -n "$discovered" ] && [ "$discovered" != "$INSTALL_DIR/apm" ]; then
        log "warning: $discovered will still shadow $INSTALL_DIR/apm in new shells until PATH is reordered."
    fi
}

run_apm() {
    verify_file "$PROMOTED_APM" "$EXECUTABLE_MEMBER"
    "$PROMOTED_APM" "$@"
}

deploy_baseline() {
    local package_ref=${BASELINE_PACKAGE_REF:-$DEFAULT_PACKAGE_REF}
    case "$MODE" in
        global)
            log "installing $package_ref at user scope"
            run_apm install --global --target codex,copilot --trust-bin --trust-transitive-mcp "$package_ref"
            log 'refreshing all user-scope branch-ref dependencies to their latest commits'
            run_apm update --global --yes --target codex,copilot
            run_apm compile --global
            ;;
        repo)
            log "installing $package_ref into $PWD"
            run_apm install --target codex,copilot --trust-bin --trust-transitive-mcp "$package_ref"
            log 'refreshing all repository branch-ref dependencies to their latest commits'
            run_apm update --yes --target codex,copilot
            run_apm compile --target codex,copilot
            ;;
    esac
}

main() {
    local mode_seen=false
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --global|--repo)
                [ "$mode_seen" = false ] || die 'choose exactly one deployment mode.'
                mode_seen=true
                [ "$1" = --global ] && MODE='global' || MODE='repo'
                ;;
            --cli-only) CLI_ONLY=true ;;
            --dry-run) DRY_RUN=true ;;
            -h|--help) usage; exit 0 ;;
            *) usage >&2; die "unknown argument: $1" ;;
        esac
        shift
    done

    PIN=$(read_pin)
    validate_checksums
    log "reviewed APM CLI version: v$PIN"
    if [ "$DRY_RUN" = true ]; then
        log '[dry-run] local pin/checksum metadata is valid; no other action was taken.'
        return
    fi

    INSTALL_DIR=${APM_INSTALL_DIR:-${HOME:?HOME must be set}/.local/bin}
    case "$INSTALL_DIR" in
        \~) INSTALL_DIR=${HOME:?HOME must be set} ;;
        \~/*) INSTALL_DIR="${HOME:?HOME must be set}/${INSTALL_DIR#\~/}" ;;
        \~*) die 'APM_INSTALL_DIR supports only the current-user ~ prefix.' ;;
    esac
    case "$INSTALL_DIR" in
        /*) ;;
        *) INSTALL_DIR="$PWD/$INSTALL_DIR" ;;
    esac
    acquire_cli
    PATH="$INSTALL_DIR:$PATH"
    export PATH
    warn_if_shadowed
    if [ "$CLI_ONLY" = false ]; then deploy_baseline; fi
    log "done; reviewed CLI: $PROMOTED_APM"
}

main "$@"
