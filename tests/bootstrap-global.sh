#!/usr/bin/env bash
set -euo pipefail

repo_root=$(CDPATH='' cd -- "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)
bootstrap="$repo_root/scripts/bootstrap-global.sh"
test_root=$(mktemp -d "${TMPDIR:-/tmp}/native-apm-bootstrap.XXXXXX")
trap 'rm -rf -- "$test_root"' EXIT HUP INT TERM

fail() { printf 'not ok - %s\n' "$*" >&2; exit 1; }

make_apm() {
    local version=$1
    mkdir -p "$case_bin"
    cat > "$case_bin/apm" <<EOF
#!/usr/bin/env bash
set -euo pipefail
printf 'apm %s\n' "\$*" >> "\$TEST_COMMAND_LOG"
if [ "\${1-}" = --version ]; then printf 'APM $version\n'; exit 0; fi
if [ "\${1-}" = install ] || [ "\${1-}" = compile ]; then exit 0; fi
exit 40
EOF
    chmod +x "$case_bin/apm"
}

make_codex_absent() {
    cat > "$case_bin/codex" <<'EOF'
#!/usr/bin/env bash
printf "No MCP server named 'github-mcp-server' found.\n" >&2
exit 1
EOF
    chmod +x "$case_bin/codex"
}

new_case() {
    case_root="$test_root/$1"
    case_bin="$case_root/bin"
    case_home="$case_root/home"
    command_log="$case_root/commands.log"
    mkdir -p "$case_bin" "$case_home"
    : > "$command_log"
}

run_case() {
    HOME="$case_home" TEST_COMMAND_LOG="$command_log" PATH="$case_bin:/usr/bin:/bin" "$bootstrap" "$@"
}

new_case missing
missing_output=$(run_case --dry-run)
grep -F 'APM CLI action: install' <<< "$missing_output" >/dev/null || fail 'missing APM action'
[ ! -s "$command_log" ] || fail 'missing dry run executed a native command'

new_case older
make_apm 0.27.0
make_codex_absent
older_output=$(run_case --dry-run)
grep -F 'APM CLI action: upgrade' <<< "$older_output" >/dev/null || fail 'older APM action'
! grep -F 'apm install' "$command_log" >/dev/null || fail 'older dry run deployed'

new_case matching
make_apm 0.28.0
make_codex_absent
run_case >/dev/null
grep -F 'apm install --global --frozen' "$command_log" >/dev/null || fail 'native global install'
grep -F 'apm compile --global --dry-run' "$command_log" >/dev/null || fail 'native compile preview'
run_case >/dev/null
[ "$(grep -c 'apm install --global --frozen' "$command_log")" -eq 2 ] || fail 'idempotent rerun'

new_case newer
make_apm 0.29.0
make_codex_absent
if run_case > "$case_root/out" 2> "$case_root/err"; then fail 'newer APM was accepted'; fi
grep -F 'newer than reviewed baseline' "$case_root/err" >/dev/null || fail 'newer APM diagnostic'
! grep -F 'apm install' "$command_log" >/dev/null || fail 'newer APM deployed'

new_case download_failure
make_apm 0.27.0
make_codex_absent
cat > "$case_bin/curl" <<'EOF'
#!/usr/bin/env bash
exit 55
EOF
chmod +x "$case_bin/curl"
if run_case > "$case_root/out" 2> "$case_root/err"; then fail 'download failure was ignored'; fi
! grep -F 'apm install' "$command_log" >/dev/null || fail 'download failure deployed'

new_case checksum_failure
make_apm 0.27.0
make_codex_absent
cat > "$case_bin/curl" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
while [ "$#" -gt 0 ]; do
    if [ "$1" = --output ]; then printf 'tampered\n' > "$2"; exit 0; fi
    shift
done
exit 56
EOF
chmod +x "$case_bin/curl"
if run_case > "$case_root/out" 2> "$case_root/err"; then fail 'checksum failure was ignored'; fi
grep -F 'does not match apm-cli.lock.yml' "$case_root/err" >/dev/null || fail 'checksum diagnostic'
! grep -F 'apm install' "$command_log" >/dev/null || fail 'checksum failure deployed'

printf '%s\n' 'All native Bash bootstrap behavior tests passed.'
