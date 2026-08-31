#!/usr/bin/env bash
# Bootstrap the agent engineering baseline with the native APM CLI.
#
# Ensures the pinned APM CLI version from .apm-version is installed (using
# the official upstream installer), upgrades an older CLI in place with
# `apm self-update`, then deploys the baseline package natively:
#
#   --global  apm install --global <ref> && apm compile --global
#   --repo    apm install --target codex,copilot <ref> && apm compile
#             (run from the target project)
#
# Everything else (skill deployment, instruction deployment, lockfiles,
# uninstall, updates) is native APM behavior. See README.md.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]:-$0}")" && pwd)"
PIN_FILE="$SCRIPT_DIR/../.apm-version"
PACKAGE_REF="${BASELINE_PACKAGE_REF:-thetechgy/agent-engineering-baseline#main}"
INSTALL_DIR="${APM_INSTALL_DIR:-$HOME/.local/bin}"
INSTALLER_URL_BASE="${APM_INSTALLER_URL_BASE:-https://raw.githubusercontent.com/microsoft/apm}"

MODE='global'
DRY_RUN=0

usage() {
    cat <<'USAGE'
Usage: bootstrap.sh [--global | --repo] [--dry-run]

  --global   Install the baseline machine-wide (user scope). Default.
  --repo     Install the baseline into the project at the current directory.
  --dry-run  Print the actions that would run without changing anything.

Environment:
  APM_INSTALL_DIR       Where to install the APM CLI when it is missing
                        (default: ~/.local/bin).
  BASELINE_PACKAGE_REF  Package reference to install
                        (default: thetechgy/agent-engineering-baseline#main).
USAGE
}

log() { printf 'bootstrap: %s\n' "$*"; }
die() { printf 'bootstrap: error: %s\n' "$*" >&2; exit 1; }

run() {
    if [ "$DRY_RUN" -eq 1 ]; then
        log "[dry-run] would run: $*"
        return 0
    fi
    "$@"
}

read_pin() {
    [ -f "$PIN_FILE" ] || die ".apm-version not found at $PIN_FILE"
    local pin
    pin="$(head -n 1 "$PIN_FILE" | tr -d '[:space:]')"
    printf '%s' "$pin" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$' \
        || die ".apm-version must contain a semantic version, got: '$pin'"
    printf '%s' "$pin"
}

installed_version() {
    apm --version 2>/dev/null | grep -Eo '[0-9]+\.[0-9]+\.[0-9]+' | head -n 1
}

# True when $1 is a strictly lower version than $2.
version_lt() {
    [ "$1" != "$2" ] && [ "$(printf '%s\n%s\n' "$1" "$2" | sort -V | head -n 1)" = "$1" ]
}

install_cli() {
    local pin=$1 installer
    log "APM CLI not found; installing v$pin to $INSTALL_DIR"
    if [ "$DRY_RUN" -eq 1 ]; then
        log "[dry-run] would download and run the official installer for v$pin"
        return 0
    fi
    installer="$(mktemp -t apm-install-XXXXXX.sh)"
    trap 'rm -f "$installer"' EXIT
    curl --fail --location --silent --show-error --proto '=https' --tlsv1.2 \
        --output "$installer" "$INSTALLER_URL_BASE/v$pin/install.sh"
    VERSION="v$pin" APM_INSTALL_DIR="$INSTALL_DIR" sh "$installer"
    rm -f "$installer"
    trap - EXIT
    hash -r 2>/dev/null || true
    if ! command -v apm >/dev/null 2>&1; then
        case ":$PATH:" in
            *":$INSTALL_DIR:"*) die "apm was installed to $INSTALL_DIR but is not runnable" ;;
            *)
                log "warning: $INSTALL_DIR is not on PATH; using it for this run only."
                log "         Add it to PATH permanently, e.g.: export PATH=\"$INSTALL_DIR:\$PATH\""
                PATH="$INSTALL_DIR:$PATH"
                ;;
        esac
    fi
}

ensure_cli() {
    local pin=$1 current
    if ! command -v apm >/dev/null 2>&1; then
        install_cli "$pin"
        return 0
    fi
    current="$(installed_version)"
    [ -n "$current" ] || die "could not determine the installed APM CLI version"
    if [ "$current" = "$pin" ]; then
        log "APM CLI v$current already matches the pin"
    elif version_lt "$current" "$pin"; then
        log "upgrading APM CLI v$current -> v$pin via apm self-update"
        if ! run env VERSION="v$pin" apm self-update; then
            die "apm self-update failed. If this CLI was installed via pip/brew or \
self-update is disabled by policy, upgrade it with that tool or remove it and re-run."
        fi
    else
        log "warning: installed APM CLI v$current is newer than the pinned v$pin; continuing"
        return 0
    fi
    if [ "$DRY_RUN" -eq 0 ]; then
        current="$(installed_version)"
        [ "$current" = "$pin" ] || die "APM CLI reports v$current after setup, expected v$pin"
    fi
}

deploy() {
    case "$MODE" in
        global)
            log "installing $PACKAGE_REF to user scope"
            run apm install --global "$PACKAGE_REF"
            log 'compiling user-scope root context files'
            run apm compile --global
            ;;
        repo)
            log "installing $PACKAGE_REF into the project at $PWD"
            log 'note: this updates the project'\''s apm.yml, lockfile, and compiled outputs'
            run apm install --target codex,copilot "$PACKAGE_REF"
            log 'compiling project outputs'
            run apm compile
            ;;
    esac
}

main() {
    while [ $# -gt 0 ]; do
        case "$1" in
            --global) MODE='global' ;;
            --repo) MODE='repo' ;;
            --dry-run) DRY_RUN=1 ;;
            -h|--help) usage; exit 0 ;;
            *) usage >&2; die "unknown argument: $1" ;;
        esac
        shift
    done
    local pin
    pin="$(read_pin)"
    log "pinned APM CLI version: v$pin (mode: $MODE)"
    ensure_cli "$pin"
    deploy
    log 'done'
}

main "$@"
