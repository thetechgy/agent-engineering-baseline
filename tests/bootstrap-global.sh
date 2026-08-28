#!/usr/bin/env bash
set -euo pipefail

repo_root=$(CDPATH='' cd -- "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)
bootstrap="$repo_root/scripts/bootstrap-global.sh"
approved_version=$(head -n 1 "$repo_root/.apm-version" | tr -d '[:space:]')
older_version='0.0.1'
newer_version='999.999.999'
test_root=$(mktemp -d "${TMPDIR:-/tmp}/apm-bootstrap-tests.XXXXXX")
trap 'rm -rf -- "$test_root"' EXIT HUP INT TERM

fail() { printf 'not ok - %s\n' "$*" >&2; exit 1; }

write_fake_apm() {
    local path=$1 version=$2
    cat > "$path" <<EOF
#!/usr/bin/env bash
set -euo pipefail
printf 'apm %s\n' "\$*" >> "\$TEST_COMMAND_LOG"
if [ "\${1-}" = --version ]; then printf 'APM $version\n'; exit 0; fi
if [ "\${1-}" = install ] || [ "\${1-}" = compile ]; then exit 0; fi
exit 40
EOF
    chmod +x "$path"
}

make_apm() {
    mkdir -p "$case_bin"
    write_fake_apm "$case_bin/apm" "$1"
}

new_case() {
    case_root="$test_root/$1"
    case_bin="$case_root/bin"
    case_home="$case_root/home"
    case_tmp="$case_root/tmp"
    command_log="$case_root/commands.log"
    mkdir -p "$case_bin" "$case_home" "$case_tmp"
    : > "$command_log"
}

run_case() {
    HOME="$case_home" TMPDIR="$case_tmp" TEST_COMMAND_LOG="$command_log" \
        PATH="$case_bin:/usr/bin:/bin" "$bootstrap" "$@"
}

new_case missing
missing_output=$(run_case --dry-run)
grep -F 'APM CLI action: install' <<< "$missing_output" >/dev/null || fail 'missing APM action'
[ ! -s "$command_log" ] || fail 'missing dry run executed a native command'

new_case older
make_apm "$older_version"
older_output=$(run_case --dry-run)
grep -F 'APM CLI action: upgrade' <<< "$older_output" >/dev/null || fail 'older APM action'
! grep -F 'apm install' "$command_log" >/dev/null || fail 'older dry run deployed'

new_case matching
make_apm "$approved_version"
run_case >/dev/null
grep -F 'apm install --global --frozen' "$command_log" >/dev/null || fail 'native global install'
grep -F 'apm compile --global --dry-run' "$command_log" >/dev/null || fail 'native compile preview'
run_case >/dev/null
[ "$(grep -c 'apm install --global --frozen' "$command_log")" -eq 2 ] || fail 'idempotent rerun'

new_case newer
make_apm "$newer_version"
if run_case > "$case_root/out" 2> "$case_root/err"; then fail 'newer APM was accepted'; fi
grep -F 'newer than pinned baseline' "$case_root/err" >/dev/null || fail 'newer APM diagnostic'
! grep -F 'apm install' "$command_log" >/dev/null || fail 'newer APM deployed'

new_case download_failure
make_apm "$older_version"
cat > "$case_bin/curl" <<'EOF'
#!/usr/bin/env bash
exit 55
EOF
chmod +x "$case_bin/curl"
if run_case > "$case_root/out" 2> "$case_root/err"; then fail 'download failure was ignored'; fi
! grep -F 'apm install' "$command_log" >/dev/null || fail 'download failure deployed'

new_case fresh_install
# No apm on PATH; the fake installer deploys apm to ~/.local/bin, which is
# also absent from PATH, exercising the post-install PATH fallback.
write_fake_apm "$case_root/fake-apm" "$approved_version"
cat > "$case_root/installer.sh" <<EOF
#!/bin/sh
mkdir -p "\$HOME/.local/bin"
cp '$case_root/fake-apm' "\$HOME/.local/bin/apm"
chmod +x "\$HOME/.local/bin/apm"
EOF
cat > "$case_bin/curl" <<EOF
#!/usr/bin/env bash
set -euo pipefail
while [ "\$#" -gt 0 ]; do
    if [ "\$1" = --output ]; then cp '$case_root/installer.sh' "\$2"; exit 0; fi
    shift
done
exit 56
EOF
chmod +x "$case_bin/curl"
run_case >/dev/null
grep -F 'apm install --global --frozen' "$command_log" >/dev/null || fail 'fresh install did not deploy'
grep -F 'apm compile --global' "$command_log" >/dev/null || fail 'fresh install did not compile'

printf '%s\n' 'All native Bash bootstrap behavior tests passed.'
