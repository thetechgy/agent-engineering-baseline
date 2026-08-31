#!/usr/bin/env bash
# Offline fixture tests for scripts/bootstrap.sh on Linux and macOS.
set -euo pipefail

REPO_ROOT="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
readonly REPO_ROOT
readonly SOURCE_BOOTSTRAP="$REPO_ROOT/scripts/bootstrap.sh"
TEST_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/baseline-bootstrap-tests.XXXXXX")
readonly TEST_ROOT
trap 'rm -rf -- "$TEST_ROOT"' EXIT HUP INT TERM

CASES=0
FAILURES=0
STATUS=0
OUTPUT=''

digest() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{ print $1 }'
    else
        shasum -a 256 "$1" | awk '{ print $1 }'
    fi
}

record_result() {
    local label=$1 expected=$2
    CASES=$((CASES + 1))
    if [ "$expected" = success ] && [ "$STATUS" -eq 0 ]; then
        printf 'ok   - %s\n' "$label"
    elif [ "$expected" = failure ] && [ "$STATUS" -ne 0 ]; then
        printf 'ok   - %s\n' "$label"
    else
        printf 'FAIL - %s (status=%s)\n' "$label" "$STATUS"
        printf '%s\n' "$OUTPUT" | sed 's/^/       /'
        FAILURES=$((FAILURES + 1))
    fi
}

assert_true() {
    local label=$1
    shift
    CASES=$((CASES + 1))
    if "$@"; then
        printf 'ok   - %s\n' "$label"
    else
        printf 'FAIL - %s\n' "$label"
        printf '%s\n' "$OUTPUT" | sed 's/^/       /'
        FAILURES=$((FAILURES + 1))
    fi
}

# Invoked indirectly by assert_true.
# shellcheck disable=SC2317
out_has() { printf '%s\n' "$OUTPUT" | grep -Fq "$1"; }
# shellcheck disable=SC2317
file_has() { grep -Fq "$2" "$1"; }

assert_true 'mirror redirects are limited to reviewed protocols' \
    file_has "$SOURCE_BOOTSTRAP" "proto-redir '=https,file'"
assert_true 'public redirects remain HTTPS-only' \
    file_has "$SOURCE_BOOTSTRAP" "proto-redir '=https'"
assert_true 'dash-leading script paths are normalized portably' \
    file_has "$SOURCE_BOOTSTRAP" "SCRIPT_SOURCE=\"./\$SCRIPT_SOURCE\""
assert_true 'cleanup refuses non-absolute staging paths' \
    file_has "$SOURCE_BOOTSTRAP" 'refusing to clean non-absolute staging path'

new_case() {
    local name=$1
    unset CASE_INSTALL_DIR CASE_NO_FALLBACK CASE_PACKAGE_REF CASE_RELEASE_BASE
    CASE_ROOT="$TEST_ROOT/$name"
    CASE_HOME="$CASE_ROOT/home"
    CASE_REPO="$CASE_ROOT/repo"
    CASE_BIN="$CASE_ROOT/bin"
    CASE_TMP="$CASE_ROOT/tmp"
    CASE_INSTALL="$CASE_ROOT/install/bin"
    MIRROR_ROOT="$CASE_ROOT/mirror"
    CALL_LOG="$CASE_ROOT/apm-calls.log"
    HASH_LOG="$CASE_ROOT/hash-calls.log"
    AMBIENT_SENTINEL="$CASE_ROOT/ambient-executed"
    mkdir -p "$CASE_HOME" "$CASE_REPO/scripts" "$CASE_BIN" "$CASE_TMP" "$CASE_INSTALL"
    cp "$SOURCE_BOOTSTRAP" "$CASE_REPO/scripts/bootstrap.sh"
    cp "$REPO_ROOT/.apm-version" "$CASE_REPO/.apm-version"
    cp "$REPO_ROOT/.apm-checksums" "$CASE_REPO/.apm-checksums"
    : > "$CALL_LOG"
    : > "$HASH_LOG"

    cat > "$CASE_BIN/apm" <<EOF
#!/usr/bin/env bash
printf 'ambient executed\n' >> '$AMBIENT_SENTINEL'
exit 97
EOF
    chmod +x "$CASE_BIN/apm"
}

write_uname_stub() {
    local os=$1 arch=$2
    cat > "$CASE_BIN/uname" <<EOF
#!/usr/bin/env bash
case "\${1-}" in
    -s) printf '%s\n' '$os' ;;
    -m) printf '%s\n' '$arch' ;;
    *) exit 2 ;;
esac
EOF
    chmod +x "$CASE_BIN/uname"
}

write_hash_stubs() {
    local real_sha='' real_shasum=''
    real_sha=$(command -v sha256sum 2>/dev/null || true)
    real_shasum=$(command -v shasum 2>/dev/null || true)
    if [ -n "$real_sha" ]; then
        cat > "$CASE_BIN/sha256sum" <<EOF
#!/usr/bin/env bash
printf 'sha256sum %s\n' "\$*" >> '$HASH_LOG'
exec '$real_sha' "\$@"
EOF
        chmod +x "$CASE_BIN/sha256sum"
    fi
    if [ -n "$real_shasum" ]; then
        cat > "$CASE_BIN/shasum" <<EOF
#!/usr/bin/env bash
printf 'shasum %s\n' "\$*" >> '$HASH_LOG'
exec '$real_shasum' "\$@"
EOF
        chmod +x "$CASE_BIN/shasum"
    fi
}

replace_checksum() {
    local name=$1 checksum=$2 staged="$CASE_REPO/.apm-checksums.next"
    awk -v name="$name" -v checksum="$checksum" '
        $2 == name { $1 = checksum }
        { print $1 "  " $2 }
    ' "$CASE_REPO/.apm-checksums" > "$staged"
    mv "$staged" "$CASE_REPO/.apm-checksums"
}

make_fixture() {
    local os=$1 arch=$2 version=${3:-0.29.0}
    PLATFORM_OS=$(printf '%s' "$os" | tr '[:upper:]' '[:lower:]')
    [ "$PLATFORM_OS" != darwin ] || PLATFORM_OS=darwin
    case "$arch" in
        arm64|aarch64) PLATFORM_ARCH=arm64 ;;
        *) PLATFORM_ARCH=x86_64 ;;
    esac
    ARCHIVE_NAME="apm-$PLATFORM_OS-$PLATFORM_ARCH.tar.gz"
    ARCHIVE_ROOT="apm-$PLATFORM_OS-$PLATFORM_ARCH"
    FIXTURE_ROOT="$CASE_ROOT/fixture"
    BUNDLE_ROOT="$FIXTURE_ROOT/$ARCHIVE_ROOT"
    MIRROR_ROOT="$CASE_ROOT/mirror"
    mkdir -p "$BUNDLE_ROOT/_internal/indexes" "$MIRROR_ROOT/v$version"
    printf 'fixture index\n' > "$BUNDLE_ROOT/_internal/indexes/catalog.json"
    cat > "$BUNDLE_ROOT/apm" <<EOF
#!/usr/bin/env bash
printf '%s\n' "\$0 \$*" >> '$CALL_LOG'
if [ "\${1-}" = '--version' ]; then
    printf 'Agent Package Manager (APM) CLI version %s (fixture)\n' '$version'
fi
exit 0
EOF
    chmod +x "$BUNDLE_ROOT/apm"
    tar -czf "$MIRROR_ROOT/v$version/$ARCHIVE_NAME" -C "$FIXTURE_ROOT" "$ARCHIVE_ROOT"
    replace_checksum "$ARCHIVE_ROOT/apm" "$(digest "$BUNDLE_ROOT/apm")"
    replace_checksum "$ARCHIVE_NAME" "$(digest "$MIRROR_ROOT/v$version/$ARCHIVE_NAME")"
    write_uname_stub "$os" "$arch"
    write_hash_stubs
}

run_case() {
    local release_base=${CASE_RELEASE_BASE-"file://$MIRROR_ROOT"}
    local install_dir=${CASE_INSTALL_DIR-$CASE_INSTALL}
    set +e
    OUTPUT=$(
        env -i \
            HOME="$CASE_HOME" \
            PATH="$CASE_BIN:/usr/bin:/bin" \
            TMPDIR="$CASE_TMP" \
            APM_INSTALL_DIR="$install_dir" \
            APM_RELEASE_BASE_URL="$release_base" \
            APM_NO_DIRECT_FALLBACK="${CASE_NO_FALLBACK-}" \
            BASELINE_PACKAGE_REF="${CASE_PACKAGE_REF-}" \
            bash "$CASE_REPO/scripts/bootstrap.sh" "$@" 2>&1
    )
    STATUS=$?
    set -e
}

printf '# metadata and preview\n'
new_case invalid-pin
printf 'not-a-version\n' > "$CASE_REPO/.apm-version"
run_case --dry-run
record_result 'invalid pin fails' failure
assert_true 'invalid pin is diagnosed' out_has 'must contain a full APM version'

new_case missing-checksums
rm "$CASE_REPO/.apm-checksums"
run_case --dry-run
record_result 'missing checksum file fails' failure

for corruption in duplicate malformed extra missing; do
    new_case "checksums-$corruption"
    case "$corruption" in
        duplicate)
            sed -n '1p' "$CASE_REPO/.apm-checksums" > "$CASE_REPO/duplicate-entry"
            sed -n '1,9p' "$CASE_REPO/.apm-checksums" > "$CASE_REPO/.apm-checksums.next"
            sed -n '1p' "$CASE_REPO/duplicate-entry" >> "$CASE_REPO/.apm-checksums.next"
            mv "$CASE_REPO/.apm-checksums.next" "$CASE_REPO/.apm-checksums"
            ;;
        malformed)
            sed '1s/^[0-9a-f]/G/' "$CASE_REPO/.apm-checksums" > "$CASE_REPO/.apm-checksums.next"
            mv "$CASE_REPO/.apm-checksums.next" "$CASE_REPO/.apm-checksums"
            ;;
        extra)
            sed -n '1,9p' "$CASE_REPO/.apm-checksums" > "$CASE_REPO/.apm-checksums.next"
            printf '%064d  unexpected\n' 0 >> "$CASE_REPO/.apm-checksums.next"
            mv "$CASE_REPO/.apm-checksums.next" "$CASE_REPO/.apm-checksums"
            ;;
        missing)
            sed -n '1,9p' "$CASE_REPO/.apm-checksums" > "$CASE_REPO/.apm-checksums.next"
            mv "$CASE_REPO/.apm-checksums.next" "$CASE_REPO/.apm-checksums"
            ;;
    esac
    run_case --dry-run
    record_result "$corruption checksum metadata fails" failure
done

new_case preview
mkdir -p "$CASE_ROOT/no-mirror"
MIRROR_ROOT="$CASE_ROOT/no-mirror"
run_case --dry-run
record_result 'preview validates metadata without a release archive' success
assert_true 'preview creates no temporary directory' test -z "$(find "$CASE_TMP" -mindepth 1 -print -quit)"
assert_true 'preview creates no installation content' test -z "$(find "$CASE_ROOT/install" -mindepth 2 -print -quit)"
assert_true 'preview never executes ambient APM' test ! -e "$AMBIENT_SENTINEL"

printf '# platform mapping, verification, and native deployment\n'
for platform_case in 'Linux x86_64 sha256sum' 'Linux aarch64 sha256sum' 'Darwin x86_64 shasum' 'Darwin arm64 shasum'; do
    read -r platform_os platform_arch platform_hash <<EOF
$platform_case
EOF
    new_case "platform-$platform_os-$platform_arch"
    make_fixture "$platform_os" "$platform_arch"
    run_case --cli-only
    record_result "$platform_os/$platform_arch complete bundle acquisition succeeds" success
    assert_true "$platform_os/$platform_arch selects $ARCHIVE_NAME" out_has "$ARCHIVE_NAME"
    assert_true "$platform_os/$platform_arch uses $platform_hash" file_has "$HASH_LOG" "$platform_hash"
    assert_true "$platform_os/$platform_arch persists _internal" test -f "$CASE_ROOT/install/lib/apm/_internal/indexes/catalog.json"
    assert_true "$platform_os/$platform_arch writes ownership marker" file_has "$CASE_ROOT/install/lib/apm/.apm-installed" 'v0.29.0'
    assert_true "$platform_os/$platform_arch creates the managed symlink" test -L "$CASE_INSTALL/apm"
    assert_true "$platform_os/$platform_arch never runs ambient APM" test ! -e "$AMBIENT_SENTINEL"
done

new_case tilde-install-dir
make_fixture Linux x86_64
# The literal tilde is the behavior under test.
# shellcheck disable=SC2088
CASE_INSTALL_DIR='~/.reviewed/bin'
run_case --cli-only
record_result 'tilde install directory expands to HOME' success
assert_true 'tilde install directory uses the current user home' \
    test -L "$CASE_HOME/.reviewed/bin/apm"

new_case global-deploy
make_fixture Linux x86_64
run_case
record_result 'global deployment succeeds' success
assert_true 'global install trusts package launchers and uses full URL ref' \
    file_has "$CALL_LOG" 'install --global --trust-bin https://github.com/thetechgy/agent-engineering-baseline.git#main'
assert_true 'global compilation is native' file_has "$CALL_LOG" 'compile --global'

new_case repo-deploy
make_fixture Linux x86_64
run_case --repo
record_result 'repository deployment succeeds' success
assert_true 'repo install always passes targets and trust-bin' \
    file_has "$CALL_LOG" 'install --target codex,copilot --trust-bin https://github.com/thetechgy/agent-engineering-baseline.git#main'
assert_true 'repo compile always passes targets' file_has "$CALL_LOG" 'compile --target codex,copilot'

new_case package-override
make_fixture Linux x86_64
CASE_PACKAGE_REF='https://example.invalid/reviewed.git#release'
run_case --repo
record_result 'package reference override succeeds' success
assert_true 'package reference override is passed literally' file_has "$CALL_LOG" "$CASE_PACKAGE_REF"

new_case prerelease
printf '0.30.0rc2\n' > "$CASE_REPO/.apm-version"
make_fixture Linux x86_64 0.30.0rc2
run_case --cli-only
record_result 'full prerelease version is preserved' success
assert_true 'prerelease marker is exact' file_has "$CASE_ROOT/install/lib/apm/.apm-installed" 'v0.30.0rc2'

new_case shadowed-path
make_fixture Linux x86_64
run_case --cli-only
record_result 'shadowed PATH does not block verified acquisition' success
assert_true 'shadowing warning names the ambient command' out_has "$CASE_BIN/apm will still shadow"
assert_true 'shadowed ambient command is never executed' test ! -e "$AMBIENT_SENTINEL"

printf '# archive and mirror failures\n'
new_case no-mirror
make_fixture Linux x86_64
CASE_RELEASE_BASE=''
CASE_NO_FALLBACK=true
run_case --cli-only
record_result 'no-direct-fallback requires a configured mirror' failure
assert_true 'no-direct-fallback failure is explicit' out_has 'no APM_RELEASE_BASE_URL'

new_case credentialed-mirror
make_fixture Linux x86_64
CASE_RELEASE_BASE='https://user:secret@example.invalid/apm'
run_case --cli-only
record_result 'credentialed mirror URL is rejected' failure

new_case corrupt-archive
make_fixture Linux x86_64
printf 'not a tar archive\n' > "$MIRROR_ROOT/v0.29.0/$ARCHIVE_NAME"
replace_checksum "$ARCHIVE_NAME" "$(digest "$MIRROR_ROOT/v0.29.0/$ARCHIVE_NAME")"
run_case --cli-only
record_result 'digest-valid corrupt archive is rejected' failure

new_case corrupt-executable
make_fixture Linux x86_64
replace_checksum "$ARCHIVE_ROOT/apm" '0000000000000000000000000000000000000000000000000000000000000000'
run_case --cli-only
record_result 'executable digest mismatch is rejected before execution' failure
assert_true 'digest-mismatched executable never executes' test ! -s "$CALL_LOG"

new_case missing-internal
make_fixture Linux x86_64
rm -rf "$BUNDLE_ROOT/_internal"
tar -czf "$MIRROR_ROOT/v0.29.0/$ARCHIVE_NAME" -C "$FIXTURE_ROOT" "$ARCHIVE_ROOT"
replace_checksum "$ARCHIVE_NAME" "$(digest "$MIRROR_ROOT/v0.29.0/$ARCHIVE_NAME")"
run_case --cli-only
record_result 'bundle without _internal is rejected' failure

new_case wrong-root
make_fixture Linux x86_64
mv "$BUNDLE_ROOT" "$FIXTURE_ROOT/wrong-root"
tar -czf "$MIRROR_ROOT/v0.29.0/$ARCHIVE_NAME" -C "$FIXTURE_ROOT" wrong-root
replace_checksum "$ARCHIVE_NAME" "$(digest "$MIRROR_ROOT/v0.29.0/$ARCHIVE_NAME")"
run_case --cli-only
record_result 'archive with wrong root is rejected' failure

new_case linked-entry
make_fixture Linux x86_64
ln -s catalog.json "$BUNDLE_ROOT/_internal/indexes/linked.json"
tar -czf "$MIRROR_ROOT/v0.29.0/$ARCHIVE_NAME" -C "$FIXTURE_ROOT" "$ARCHIVE_ROOT"
replace_checksum "$ARCHIVE_NAME" "$(digest "$MIRROR_ROOT/v0.29.0/$ARCHIVE_NAME")"
run_case --cli-only
record_result 'archive link is rejected before extraction' failure

new_case duplicate-executable
make_fixture Linux x86_64
tar -czf "$MIRROR_ROOT/v0.29.0/$ARCHIVE_NAME" -C "$FIXTURE_ROOT" \
    "$ARCHIVE_ROOT/apm" "$ARCHIVE_ROOT/apm" "$ARCHIVE_ROOT/_internal"
replace_checksum "$ARCHIVE_NAME" "$(digest "$MIRROR_ROOT/v0.29.0/$ARCHIVE_NAME")"
run_case --cli-only
record_result 'duplicate executable member is rejected' failure

if tar --help 2>&1 | grep -q -- '--transform'; then
    new_case traversal
    make_fixture Linux x86_64
    tar -czf "$MIRROR_ROOT/v0.29.0/$ARCHIVE_NAME" --transform='s|^|../|' \
        -C "$FIXTURE_ROOT" "$ARCHIVE_ROOT"
    replace_checksum "$ARCHIVE_NAME" "$(digest "$MIRROR_ROOT/v0.29.0/$ARCHIVE_NAME")"
    run_case --cli-only
    record_result 'traversing archive name is rejected' failure
fi

printf '# ownership and rollback\n'
new_case unowned-bundle
make_fixture Linux x86_64
mkdir -p "$CASE_ROOT/install/lib/apm"
printf 'unrelated\n' > "$CASE_ROOT/install/lib/apm/keep"
run_case --cli-only
record_result 'unowned bundle target is not overwritten' failure
assert_true 'unowned bundle content is preserved' file_has "$CASE_ROOT/install/lib/apm/keep" 'unrelated'

new_case unrelated-command
make_fixture Linux x86_64
rm -rf "$CASE_ROOT/install/lib/apm"
printf 'unrelated command\n' > "$CASE_INSTALL/apm"
run_case --cli-only
record_result 'unrelated command is not overwritten' failure
assert_true 'unrelated command content is preserved' file_has "$CASE_INSTALL/apm" 'unrelated command'

new_case rollback
make_fixture Linux x86_64
mkdir -p "$CASE_ROOT/install/lib/apm/_internal"
printf 'v0.28.0\n' > "$CASE_ROOT/install/lib/apm/.apm-installed"
printf 'old bundle\n' > "$CASE_ROOT/install/lib/apm/_internal/old"
printf '#!/bin/sh\nexit 0\n' > "$CASE_ROOT/install/lib/apm/apm"
chmod +x "$CASE_ROOT/install/lib/apm/apm"
ln -s "$CASE_ROOT/install/lib/apm/apm" "$CASE_INSTALL/apm"
real_ln=$(command -v ln)
cat > "$CASE_BIN/ln" <<EOF
#!/usr/bin/env bash
if [ ! -f '$CASE_ROOT/ln-failed-once' ]; then
    : > '$CASE_ROOT/ln-failed-once'
    exit 73
fi
exec '$real_ln' "\$@"
EOF
chmod +x "$CASE_BIN/ln"
run_case --cli-only
record_result 'promotion failure is surfaced' failure
assert_true 'promotion rollback restores old bundle' file_has "$CASE_ROOT/install/lib/apm/_internal/old" 'old bundle'
assert_true 'promotion rollback restores managed symlink' test -L "$CASE_INSTALL/apm"

printf '\n%d cases, %d failures\n' "$CASES" "$FAILURES"
exit "$((FAILURES > 0 ? 1 : 0))"
