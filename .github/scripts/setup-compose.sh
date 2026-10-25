#!/usr/bin/env bash
# CI-only Linux plugin; reviewed release bytes are checked before execution.
set -euo pipefail
umask 077

compose_version=5.6.1
compose_sha256=47737f4236e6d3ccea7291995203f8f018058783b4c3a9469119811a0b5db8c0
: "${RUNNER_TEMP:?}" "${GITHUB_WORKSPACE:?}"
temporary=$(realpath -e -- "$RUNNER_TEMP")
workspace=$(realpath -e -- "$GITHUB_WORKSPACE")
[[ "$temporary" = "$RUNNER_TEMP" && -d "$temporary" && -O "$temporary" ]]
[[ "$temporary" != *$'\n'* && "$temporary" != *$'\r'* ]]
case "$temporary/" in "$workspace/"*) echo 'Compose tools must be outside the checkout.' >&2; exit 1 ;; esac

case "${1:-install}" in
  cleanup)
    if [[ -n "${COMPOSE_PLUGIN_ROOT:-}" ]]; then
      [[ "$(dirname -- "$COMPOSE_PLUGIN_ROOT")" = "$temporary" ]]
      [[ "$(basename -- "$COMPOSE_PLUGIN_ROOT")" = compose-plugin.* ]]
      [[ ! -L "$COMPOSE_PLUGIN_ROOT" ]]
      if [[ -e "$COMPOSE_PLUGIN_ROOT" ]]; then
        [[ -d "$COMPOSE_PLUGIN_ROOT" && -O "$COMPOSE_PLUGIN_ROOT" ]]
        rm -rf -- "$COMPOSE_PLUGIN_ROOT"
      fi
    fi
    exit 0
    ;;
  install) ;;
  *) echo 'usage: setup-compose.sh [install|cleanup]' >&2; exit 2 ;;
esac

: "${GITHUB_ENV:?}"
[[ "$(uname -s)" = Linux && "$(uname -m)" = x86_64 ]]
[[ -f "$GITHUB_ENV" && ! -L "$GITHUB_ENV" ]]
plugin_root=$(mktemp -d "$temporary/compose-plugin.XXXXXXXX")
installed=false
cleanup() {
  if [[ "$installed" != true ]]; then
    rm -rf -- "$plugin_root"
  fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
mkdir "$plugin_root/cli-plugins"
binary="$plugin_root/cli-plugins/docker-compose"
curl --fail --location --silent --show-error --proto '=https' --proto-redir '=https' \
  "https://github.com/docker/compose/releases/download/v$compose_version/docker-compose-linux-x86_64" \
  --output "$binary"
printf '%s  %s\n' "$compose_sha256" "$binary" | sha256sum --check --strict
chmod 755 "$binary"
test "$("$binary" version --short)" = "$compose_version"
test "$(DOCKER_CONFIG="$plugin_root" docker compose version --short)" = "$compose_version"
printf 'DOCKER_CONFIG=%s\nCOMPOSE_PLUGIN_ROOT=%s\n' "$plugin_root" "$plugin_root" >> "$GITHUB_ENV"
installed=true
