#!/usr/bin/env bash
# No-network tests for scripts/bootstrap.sh.
#
# Each case runs the bootstrap in a sandbox: a temp HOME, a PATH that exposes
# only a stub `apm` (and stub `curl` for the install path), and a private pin
# file. The stubs record every invocation so assertions inspect exactly which
# native commands the bootstrap would run.
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
BOOTSTRAP="$REPO_ROOT/scripts/bootstrap.sh"
FAILURES=0
CASES=0

sandbox() {
    SANDBOX="$(mktemp -d -t bootstrap-test-XXXXXX)"
    mkdir -p "$SANDBOX/bin" "$SANDBOX/repo/scripts" "$SANDBOX/home" "$SANDBOX/work"
    cp "$BOOTSTRAP" "$SANDBOX/repo/scripts/bootstrap.sh"
    printf '%s\n' "${1:-0.29.0}" > "$SANDBOX/repo/.apm-version"
    CALL_LOG="$SANDBOX/calls.log"
    : > "$CALL_LOG"
}

# Stub apm: records arguments, reports the version in $SANDBOX/apm-version,
# and applies $SANDBOX/apm-version-after-self-update on self-update.
write_apm_stub() {
    printf '%s\n' "$1" > "$SANDBOX/apm-version"
    cat > "$SANDBOX/bin/apm" <<STUB
#!/usr/bin/env bash
sandbox='$SANDBOX'
printf 'apm %s\n' "\$*" >> "\$sandbox/calls.log"
printf 'VERSION_ENV=%s\n' "\${VERSION:-}" >> "\$sandbox/calls.log"
case "\$1" in
    --version)
        printf 'Agent Package Manager (APM) CLI version %s (test)\n' "\$(cat "\$sandbox/apm-version")"
        ;;
    self-update)
        if [ -f "\$sandbox/self-update-fails" ]; then exit 1; fi
        if [ -f "\$sandbox/apm-version-after-self-update" ]; then
            cp "\$sandbox/apm-version-after-self-update" "\$sandbox/apm-version"
        fi
        ;;
esac
exit 0
STUB
    chmod +x "$SANDBOX/bin/apm"
}

# Stub curl: records the URL and writes a fake installer that records its
# environment and drops a working apm stub into APM_INSTALL_DIR.
write_curl_stub() {
    cat > "$SANDBOX/bin/curl" <<STUB
#!/usr/bin/env bash
sandbox='$SANDBOX'
out=''
url=''
while [ \$# -gt 0 ]; do
    case "\$1" in
        --output) out="\$2"; shift ;;
        http*|file*) url="\$1" ;;
    esac
    shift
done
printf 'curl %s\n' "\$url" >> "\$sandbox/calls.log"
cat > "\$out" <<'INSTALLER'
#!/bin/sh
printf 'installer VERSION=%s APM_INSTALL_DIR=%s\n' "\${VERSION:-}" "\${APM_INSTALL_DIR:-}" >> "SANDBOX_PATH/calls.log"
mkdir -p "\$APM_INSTALL_DIR"
cp "SANDBOX_PATH/installed-apm" "\$APM_INSTALL_DIR/apm"
chmod +x "\$APM_INSTALL_DIR/apm"
INSTALLER
sed -i "s|SANDBOX_PATH|\$sandbox|g" "\$out"
STUB
    chmod +x "$SANDBOX/bin/curl"
}

run_bootstrap() {
    set +e
    OUTPUT="$(
        cd "$SANDBOX/work" && \
        env -i HOME="$SANDBOX/home" PATH="$SANDBOX/bin:/usr/bin:/bin" \
            bash "$SANDBOX/repo/scripts/bootstrap.sh" "$@" 2>&1
    )"
    STATUS=$?
    set -e
}

assert() {
    local label=$1; shift
    CASES=$((CASES + 1))
    if "$@"; then
        printf 'ok   - %s\n' "$label"
    else
        printf 'FAIL - %s\n' "$label"
        printf '       status=%s\n' "${STATUS:-?}"
        printf '%s\n' "$OUTPUT" | sed 's/^/       out: /'
        sed 's/^/       log: /' "$CALL_LOG"
        FAILURES=$((FAILURES + 1))
    fi
}

# Invoked indirectly through assert, which ShellCheck cannot see.
# shellcheck disable=SC2317
log_has() { grep -Fq "$1" "$CALL_LOG"; }
# shellcheck disable=SC2317
log_lacks() { ! grep -Fq "$1" "$CALL_LOG"; }
# shellcheck disable=SC2317
out_has() { printf '%s' "$OUTPUT" | grep -Fq "$1"; }

echo '# pin parsing'
sandbox 'not-a-version'
write_apm_stub '0.29.0'
run_bootstrap
assert 'invalid pin fails' test "$STATUS" -ne 0
assert 'invalid pin reported' out_has 'must contain a semantic version'

sandbox
rm "$SANDBOX/repo/.apm-version"
write_apm_stub '0.29.0'
run_bootstrap
assert 'missing pin file fails' test "$STATUS" -ne 0

echo '# CLI missing: installs pinned version via official installer'
sandbox '0.29.0'
write_curl_stub
cat > "$SANDBOX/installed-apm" <<STUB
#!/usr/bin/env bash
printf 'apm %s\n' "\$*" >> '$SANDBOX/calls.log'
[ "\$1" = '--version' ] && echo 'Agent Package Manager (APM) CLI version 0.29.0 (test)'
exit 0
STUB
run_bootstrap --dry-run
assert 'dry-run without CLI succeeds' test "$STATUS" -eq 0
assert 'dry-run does not download' log_lacks 'curl'
run_bootstrap
assert 'install succeeds' test "$STATUS" -eq 0
assert 'installer fetched at pinned tag' log_has 'curl https://raw.githubusercontent.com/microsoft/apm/v0.29.0/install.sh'
assert 'installer ran pinned with user dir' log_has "installer VERSION=v0.29.0 APM_INSTALL_DIR=$SANDBOX/home/.local/bin"
assert 'baseline installed globally' log_has 'apm install --global thetechgy/agent-engineering-baseline#main'
assert 'root contexts compiled' log_has 'apm compile --global'

echo '# CLI older: native self-update pinned upgrade'
sandbox '0.29.0'
write_apm_stub '0.28.0'
printf '0.29.0\n' > "$SANDBOX/apm-version-after-self-update"
run_bootstrap
assert 'upgrade succeeds' test "$STATUS" -eq 0
assert 'self-update invoked' log_has 'apm self-update'
assert 'self-update saw pinned VERSION' log_has 'VERSION_ENV=v0.29.0'
assert 'no installer download' log_lacks 'curl'

echo '# CLI older: self-update failure surfaces'
sandbox '0.29.0'
write_apm_stub '0.28.0'
touch "$SANDBOX/self-update-fails"
run_bootstrap
assert 'self-update failure fails run' test "$STATUS" -ne 0
assert 'remediation message shown' out_has 'apm self-update failed'

echo '# CLI older: version asserted after upgrade'
sandbox '0.29.0'
write_apm_stub '0.28.0' # stays 0.28.0 after self-update
run_bootstrap
assert 'stale version after upgrade fails' test "$STATUS" -ne 0
assert 'mismatch reported' out_has 'expected v0.29.0'

echo '# CLI equal: no-op'
sandbox '0.29.0'
write_apm_stub '0.29.0'
run_bootstrap
assert 'equal pin succeeds' test "$STATUS" -eq 0
assert 'no self-update' log_lacks 'self-update'
assert 'no installer download' log_lacks 'curl'

echo '# CLI newer: warn and continue'
sandbox '0.29.0'
write_apm_stub '0.30.0'
run_bootstrap
assert 'newer CLI succeeds' test "$STATUS" -eq 0
assert 'newer CLI warns' out_has 'newer than the pinned'
assert 'still deploys' log_has 'apm install --global'

echo '# repo mode: native project install'
sandbox '0.29.0'
write_apm_stub '0.29.0'
run_bootstrap --repo
assert 'repo mode succeeds' test "$STATUS" -eq 0
assert 'project install invoked' log_has 'apm install --target codex,copilot thetechgy/agent-engineering-baseline#main'
assert 'project compile invoked' log_has 'apm compile'
assert 'no global install' log_lacks 'install --global'

echo '# package ref override'
sandbox '0.29.0'
write_apm_stub '0.29.0'
set +e
OUTPUT="$(
    cd "$SANDBOX/work" && \
    env -i HOME="$SANDBOX/home" PATH="$SANDBOX/bin:/usr/bin:/bin" \
        BASELINE_PACKAGE_REF='local/pkg' \
        bash "$SANDBOX/repo/scripts/bootstrap.sh" 2>&1
)"
STATUS=$?
set -e
assert 'override ref used' log_has 'apm install --global local/pkg'

echo '# dry-run never mutates'
sandbox '0.29.0'
write_apm_stub '0.28.0'
printf '0.29.0\n' > "$SANDBOX/apm-version-after-self-update"
run_bootstrap --dry-run
assert 'dry-run succeeds' test "$STATUS" -eq 0
assert 'dry-run skips self-update' log_lacks 'apm self-update'
assert 'dry-run skips install' log_lacks 'apm install'
assert 'dry-run skips compile' log_lacks 'apm compile'

echo '# invalid arguments'
sandbox '0.29.0'
write_apm_stub '0.29.0'
run_bootstrap --bogus
assert 'unknown flag fails' test "$STATUS" -ne 0

printf '\n%d cases, %d failures\n' "$CASES" "$FAILURES"
exit "$((FAILURES > 0 ? 1 : 0))"
