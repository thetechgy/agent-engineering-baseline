#!/usr/bin/env bash
# Offline fixture tests for scripts/bootstrap.sh on Linux and macOS.
set -euo pipefail

REPO_ROOT="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
readonly REPO_ROOT
readonly SOURCE_BOOTSTRAP="$REPO_ROOT/scripts/bootstrap.sh"
TEST_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/baseline-bootstrap-tests.XXXXXX")
TEST_ROOT=$(CDPATH='' cd -- "$TEST_ROOT" && pwd -P)
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
out_lacks() { ! out_has "$1"; }
# shellcheck disable=SC2317
file_has() { grep -Fq "$2" "$1"; }
# The generation directory currently activated through the managed symlink.
active_release() { dirname "$(readlink "$CASE_INSTALL/apm")"; }

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
    unset CASE_INSTALL_DIR CASE_NO_FALLBACK CASE_PACKAGE_REF CASE_RELEASE_BASE CASE_ACTOR
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
    # Match the synthetic archives, independently of the production release pin.
    printf '0.29.0\n' > "$CASE_REPO/.apm-version"
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
printf '%s VERSION=%s\n' "\$0 \$*" "\${VERSION-unset}" >> '$CALL_LOG'
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
            APM_TEST_ACTOR="${CASE_ACTOR-}" \
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
    assert_true "$platform_os/$platform_arch persists _internal" test -f "$(active_release)/_internal/indexes/catalog.json"
    assert_true "$platform_os/$platform_arch writes ownership marker" file_has "$(active_release)/.apm-installed" 'v0.29.0'
    assert_true "$platform_os/$platform_arch installs a versioned generation" test -d "$CASE_ROOT/install/lib/apm/releases/v0.29.0-"*
    assert_true "$platform_os/$platform_arch reports the activated command and generation" out_has "done; reviewed CLI: $CASE_INSTALL/apm -> $(active_release)/apm"
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
assert_true 'global install pins targets, trusts launchers and MCP, and uses full URL ref' \
    file_has "$CALL_LOG" 'install --global --target codex,copilot --trust-bin --trust-transitive-mcp https://github.com/thetechgy/agent-engineering-baseline.git#main'
assert_true 'global rerun refreshes locked refs natively' \
    file_has "$CALL_LOG" 'update --global --yes --target codex,copilot'
assert_true 'global refresh log covers all user-scope branch-ref dependencies' \
    out_has 'refreshing all user-scope branch-ref dependencies to their latest commits'
assert_true 'global compilation is native' file_has "$CALL_LOG" 'compile --global'
assert_true 'deployment commands pin VERSION so APM skips its self-update nudge' \
    test "$(grep -Ec ' (install|update|compile) .*VERSION=0\.29\.0$' "$CALL_LOG")" -eq 3
assert_true 'no deployment command runs without the pinned VERSION' \
    test "$(grep -Ec ' (install|update|compile) .*VERSION=unset$' "$CALL_LOG")" -eq 0

new_case repo-deploy
make_fixture Linux x86_64
run_case --repo
record_result 'repository deployment succeeds' success
assert_true 'repo install always passes targets and launcher/MCP trust' \
    file_has "$CALL_LOG" 'install --target codex,copilot --trust-bin --trust-transitive-mcp https://github.com/thetechgy/agent-engineering-baseline.git#main'
assert_true 'repo re-runs refresh locked refs natively' \
    file_has "$CALL_LOG" 'update --yes --target codex,copilot'
assert_true 'repo refresh log covers all repository branch-ref dependencies' \
    out_has 'refreshing all repository branch-ref dependencies to their latest commits'
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
assert_true 'prerelease marker is exact' file_has "$(active_release)/.apm-installed" 'v0.30.0rc2'
assert_true 'prerelease generation name keeps the full version' test -d "$CASE_ROOT/install/lib/apm/releases/v0.30.0rc2-"*

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
assert_true 'credentialed mirror rejection is diagnosed' out_has 'must not contain credentials'

new_case corrupt-archive
make_fixture Linux x86_64
printf 'not a tar archive\n' > "$MIRROR_ROOT/v0.29.0/$ARCHIVE_NAME"
replace_checksum "$ARCHIVE_NAME" "$(digest "$MIRROR_ROOT/v0.29.0/$ARCHIVE_NAME")"
run_case --cli-only
record_result 'digest-valid corrupt archive is rejected' failure
assert_true 'corrupt archive reaches layout inspection' out_has "unable to list $ARCHIVE_NAME"

new_case corrupt-executable
make_fixture Linux x86_64
replace_checksum "$ARCHIVE_ROOT/apm" '0000000000000000000000000000000000000000000000000000000000000000'
run_case --cli-only
record_result 'executable digest mismatch is rejected before execution' failure
assert_true 'executable checksum rejection is diagnosed' \
    out_has "$ARCHIVE_ROOT/apm does not match its reviewed SHA256 digest"
assert_true 'digest-mismatched executable never executes' test ! -s "$CALL_LOG"

new_case missing-reported-version
make_fixture Linux x86_64
printf '#!/usr/bin/env bash\nexit 0\n' > "$BUNDLE_ROOT/apm"
chmod +x "$BUNDLE_ROOT/apm"
tar -czf "$MIRROR_ROOT/v0.29.0/$ARCHIVE_NAME" -C "$FIXTURE_ROOT" "$ARCHIVE_ROOT"
replace_checksum "$ARCHIVE_ROOT/apm" "$(digest "$BUNDLE_ROOT/apm")"
replace_checksum "$ARCHIVE_NAME" "$(digest "$MIRROR_ROOT/v0.29.0/$ARCHIVE_NAME")"
run_case --cli-only
record_result 'executable without a full version is rejected' failure
assert_true 'missing version uses the reviewed diagnostic' \
    out_has 'did not report a full version'
assert_true 'missing staged version is not misreported as a mismatch' out_lacks 'does not report the pinned'

new_case staged-execution-failure
make_fixture Linux x86_64
printf '#!/bin/sh\nexit 73\n' > "$BUNDLE_ROOT/apm"
tar -czf "$MIRROR_ROOT/v0.29.0/$ARCHIVE_NAME" -C "$FIXTURE_ROOT" "$ARCHIVE_ROOT"
replace_checksum "$ARCHIVE_ROOT/apm" "$(digest "$BUNDLE_ROOT/apm")"
replace_checksum "$ARCHIVE_NAME" "$(digest "$MIRROR_ROOT/v0.29.0/$ARCHIVE_NAME")"
run_case --cli-only
record_result 'staged execution failure is surfaced' failure
assert_true 'staged execution failure uses a phase-neutral diagnostic' out_has 'the APM executable failed its version postcondition'
assert_true 'staged execution failure is not misreported as a mismatch' out_lacks 'does not report the pinned'

new_case missing-internal
make_fixture Linux x86_64
rm -rf "$BUNDLE_ROOT/_internal"
tar -czf "$MIRROR_ROOT/v0.29.0/$ARCHIVE_NAME" -C "$FIXTURE_ROOT" "$ARCHIVE_ROOT"
replace_checksum "$ARCHIVE_NAME" "$(digest "$MIRROR_ROOT/v0.29.0/$ARCHIVE_NAME")"
run_case --cli-only
record_result 'bundle without _internal is rejected' failure
assert_true 'missing internal tree reaches layout validation' out_has 'missing _internal tree'

new_case wrong-root
make_fixture Linux x86_64
mv "$BUNDLE_ROOT" "$FIXTURE_ROOT/wrong-root"
tar -czf "$MIRROR_ROOT/v0.29.0/$ARCHIVE_NAME" -C "$FIXTURE_ROOT" wrong-root
replace_checksum "$ARCHIVE_NAME" "$(digest "$MIRROR_ROOT/v0.29.0/$ARCHIVE_NAME")"
run_case --cli-only
record_result 'archive with wrong root is rejected' failure
assert_true 'wrong root reaches layout validation' out_has 'unexpected root'

new_case linked-entry
make_fixture Linux x86_64
ln -s catalog.json "$BUNDLE_ROOT/_internal/indexes/linked.json"
tar -czf "$MIRROR_ROOT/v0.29.0/$ARCHIVE_NAME" -C "$FIXTURE_ROOT" "$ARCHIVE_ROOT"
replace_checksum "$ARCHIVE_NAME" "$(digest "$MIRROR_ROOT/v0.29.0/$ARCHIVE_NAME")"
run_case --cli-only
record_result 'archive link is rejected before extraction' failure
assert_true 'archive link reaches entry type validation' out_has 'contains a link or unsupported entry type'

new_case duplicate-executable
make_fixture Linux x86_64
tar -czf "$MIRROR_ROOT/v0.29.0/$ARCHIVE_NAME" -C "$FIXTURE_ROOT" \
    "$ARCHIVE_ROOT/apm" "$ARCHIVE_ROOT/apm" "$ARCHIVE_ROOT/_internal"
replace_checksum "$ARCHIVE_NAME" "$(digest "$MIRROR_ROOT/v0.29.0/$ARCHIVE_NAME")"
run_case --cli-only
record_result 'duplicate executable member is rejected' failure
assert_true 'duplicate executable reaches layout validation' out_has 'executable count'

if tar --help 2>&1 | grep -q -- '--transform'; then
    new_case traversal
    make_fixture Linux x86_64
    tar -czf "$MIRROR_ROOT/v0.29.0/$ARCHIVE_NAME" --transform='s|^|../|' \
        -C "$FIXTURE_ROOT" "$ARCHIVE_ROOT"
    replace_checksum "$ARCHIVE_NAME" "$(digest "$MIRROR_ROOT/v0.29.0/$ARCHIVE_NAME")"
    run_case --cli-only
    record_result 'traversing archive name is rejected' failure
    assert_true 'traversal reaches layout validation' out_has 'unexpected root, traversal'
fi

printf '# ownership, generations, and failure isolation\n'
new_case unrelated-library-content
make_fixture Linux x86_64
mkdir -p "$CASE_ROOT/install/lib/apm"
printf 'unrelated\n' > "$CASE_ROOT/install/lib/apm/keep"
run_case --cli-only
record_result 'unrelated library content does not block installation' success
assert_true 'unrelated library content is preserved' file_has "$CASE_ROOT/install/lib/apm/keep" 'unrelated'

new_case unrelated-command
make_fixture Linux x86_64
printf 'unrelated command\n' > "$CASE_INSTALL/apm"
run_case --cli-only
record_result 'unrelated command is not overwritten' failure
assert_true 'unrelated command reaches ownership validation' out_has 'refusing to overwrite unrelated APM command'
assert_true 'unrelated command content is preserved' file_has "$CASE_INSTALL/apm" 'unrelated command'
assert_true 'unrelated command failure leaves no generation behind' \
    test -z "$(find "$CASE_ROOT/install/lib/apm/releases" -mindepth 1 -print -quit 2>/dev/null)"

new_case unrelated-symlink
make_fixture Linux x86_64
ln -s /usr/bin/env "$CASE_INSTALL/apm"
run_case --cli-only
record_result 'unrelated symlink is not overwritten' failure
assert_true 'unrelated symlink reaches ownership validation' out_has 'refusing to overwrite an unrelated APM symlink'
assert_true 'unrelated symlink is preserved' test "$(readlink "$CASE_INSTALL/apm")" = /usr/bin/env

new_case symlinked-ancestor
make_fixture Linux x86_64
mkdir -p "$CASE_ROOT/physical-root/nested"
ln -s "$CASE_ROOT/physical-root" "$CASE_ROOT/linked-root"
CASE_INSTALL_DIR="$CASE_ROOT/linked-root/nested/bin"
run_case --cli-only
record_result 'symlinked install ancestor is rejected' failure
assert_true 'symlinked ancestor reaches path validation' out_has 'has a symlinked path component'
assert_true 'symlinked ancestor target is not mutated' \
    test ! -e "$CASE_ROOT/physical-root/nested/lib"

new_case supersede
make_fixture Linux x86_64
run_case --cli-only
record_result 'first generation installs' success
first_release=$(active_release)
printf 'first generation\n' > "$first_release/_internal/generation"
sleep 1
run_case --cli-only
record_result 'second run installs a new generation' success
assert_true 'second run activates a different generation' test "$(active_release)" != "$first_release"
assert_true 'superseded generation is removed' test ! -e "$first_release"
assert_true 'exactly one generation remains' \
    test "$(find "$CASE_ROOT/install/lib/apm/releases" -mindepth 1 -maxdepth 1 | wc -l | tr -d ' ')" -eq 1
assert_true 'activated command is usable after supersession' file_has <("$CASE_INSTALL/apm" --version) '0.29.0'
assert_true 'supersession releases the lock' test ! -e "$CASE_ROOT/install/lib/apm/.lock"

new_case legacy-layout
make_fixture Linux x86_64
mkdir -p "$CASE_ROOT/install/lib/apm/_internal"
printf 'v0.28.0\n' > "$CASE_ROOT/install/lib/apm/.apm-installed"
printf 'old bundle\n' > "$CASE_ROOT/install/lib/apm/_internal/old"
printf '#!/bin/sh\nexit 0\n' > "$CASE_ROOT/install/lib/apm/apm"
chmod +x "$CASE_ROOT/install/lib/apm/apm"
ln -s "$CASE_ROOT/install/lib/apm/apm" "$CASE_INSTALL/apm"
run_case --cli-only
record_result 'legacy single-bundle layout is replaced' success
assert_true 'legacy layout activates a generation' test -d "$(active_release)"
assert_true 'legacy bundle executable is removed' test ! -e "$CASE_ROOT/install/lib/apm/apm"
assert_true 'legacy bundle tree is removed' test ! -e "$CASE_ROOT/install/lib/apm/_internal"
assert_true 'legacy ownership marker is removed' test ! -e "$CASE_ROOT/install/lib/apm/.apm-installed"

new_case superseded-cleanup-failure
make_fixture Linux x86_64
run_case --cli-only
record_result 'cleanup failure fixture installs prior generation' success
first_release=$(active_release)
sleep 1
real_rm=$(command -v rm)
cat > "$CASE_BIN/rm" <<EOF
#!/usr/bin/env bash
for path in "\$@"; do
    case "\$path" in '$first_release') exit 73 ;; esac
done
exec '$real_rm' "\$@"
EOF
chmod +x "$CASE_BIN/rm"
run_case --cli-only
record_result 'superseded generation cleanup failure leaves a successful install' success
assert_true 'superseded cleanup failure is diagnosed' out_has 'unable to remove a superseded APM release'
assert_true 'new generation is active despite cleanup failure' test "$(active_release)" != "$first_release"
assert_true 'command is usable despite cleanup failure' file_has <("$CASE_INSTALL/apm" --version) '0.29.0'
assert_true 'cleanup failure still releases the lock' test ! -e "$CASE_ROOT/install/lib/apm/.lock"

new_case traversal-symlink
make_fixture Linux x86_64
mkdir -p "$CASE_ROOT/install/lib/apm/releases" "$CASE_ROOT/elsewhere"
printf 'unrelated command\n' > "$CASE_ROOT/elsewhere/apm"
ln -s "$CASE_ROOT/install/lib/apm/releases/../../../elsewhere/apm" "$CASE_INSTALL/apm"
run_case --cli-only
record_result 'symlink with a traversal component is not overwritten' failure
assert_true 'traversal symlink reaches ownership validation' out_has 'refusing to overwrite an unrelated APM symlink'
assert_true 'traversal symlink is preserved' \
    test "$(readlink "$CASE_INSTALL/apm")" = "$CASE_ROOT/install/lib/apm/releases/../../../elsewhere/apm"
assert_true 'traversal symlink target is untouched' file_has "$CASE_ROOT/elsewhere/apm" 'unrelated command'

new_case unmanaged-generation-symlink
make_fixture Linux x86_64
mkdir -p "$CASE_ROOT/install/lib/apm/releases/v0.28.0-unmarked"
printf '#!/bin/sh\nexit 0\n' > "$CASE_ROOT/install/lib/apm/releases/v0.28.0-unmarked/apm"
ln -s "$CASE_ROOT/install/lib/apm/releases/v0.28.0-unmarked/apm" "$CASE_INSTALL/apm"
run_case --cli-only
record_result 'symlink into a directory outside the generation grammar is not overwritten' failure
assert_true 'unmanaged generation symlink reaches ownership validation' out_has 'refusing to overwrite an unrelated APM symlink'
assert_true 'unmanaged generation symlink is preserved' \
    test "$(readlink "$CASE_INSTALL/apm")" = "$CASE_ROOT/install/lib/apm/releases/v0.28.0-unmarked/apm"

new_case unowned-legacy-bundle
make_fixture Linux x86_64
mkdir -p "$CASE_ROOT/install/lib/apm/_internal"
printf 'user bundle\n' > "$CASE_ROOT/install/lib/apm/_internal/keep"
printf '#!/bin/sh\nexit 0\n' > "$CASE_ROOT/install/lib/apm/apm"
chmod +x "$CASE_ROOT/install/lib/apm/apm"
ln -s "$CASE_ROOT/install/lib/apm/apm" "$CASE_INSTALL/apm"
run_case --cli-only
record_result 'symlink to an unmarked legacy bundle is not overwritten' failure
assert_true 'unowned legacy bundle is diagnosed with the command and its target' \
    out_has "refusing to overwrite an APM symlink to an unowned bundle: $CASE_INSTALL/apm -> $CASE_ROOT/install/lib/apm/apm"
assert_true 'unowned legacy symlink is preserved' test "$(readlink "$CASE_INSTALL/apm")" = "$CASE_ROOT/install/lib/apm/apm"
assert_true 'unowned legacy executable is preserved' test -x "$CASE_ROOT/install/lib/apm/apm"
assert_true 'unowned legacy tree is preserved' file_has "$CASE_ROOT/install/lib/apm/_internal/keep" 'user bundle'
assert_true 'unowned legacy bundle blocks generation creation' \
    test -z "$(find "$CASE_ROOT/install/lib/apm/releases" -mindepth 1 -maxdepth 1 2>/dev/null)"

new_case unowned-generation-target
make_fixture Linux x86_64
unowned_release="$CASE_ROOT/install/lib/apm/releases/v0.28.0-20260101T000000Z-4242"
mkdir -p "$unowned_release"
printf '#!/bin/sh\nexit 0\n' > "$unowned_release/apm"
chmod +x "$unowned_release/apm"
ln -s "$unowned_release/apm" "$CASE_INSTALL/apm"
run_case --cli-only
record_result 'symlink to an unmarked generation-named directory is not overwritten' failure
assert_true 'unowned generation target is diagnosed' \
    out_has "refusing to overwrite an APM symlink to an unowned bundle: $CASE_INSTALL/apm -> $unowned_release/apm"
assert_true 'unowned generation symlink is preserved' test "$(readlink "$CASE_INSTALL/apm")" = "$unowned_release/apm"
assert_true 'unowned generation executable is preserved' test -x "$unowned_release/apm"

new_case symlinked-marker-target
make_fixture Linux x86_64
marked_release="$CASE_ROOT/install/lib/apm/releases/v0.28.0-20260101T000000Z-4242"
mkdir -p "$marked_release"
printf 'v0.28.0\n' > "$CASE_ROOT/elsewhere-marker"
ln -s "$CASE_ROOT/elsewhere-marker" "$marked_release/.apm-installed"
printf '#!/bin/sh\nexit 0\n' > "$marked_release/apm"
chmod +x "$marked_release/apm"
ln -s "$marked_release/apm" "$CASE_INSTALL/apm"
run_case --cli-only
record_result 'symlink to a bundle whose marker is a symlink is not overwritten' failure
assert_true 'symlinked marker is diagnosed as unowned' out_has 'refusing to overwrite an APM symlink to an unowned bundle'
assert_true 'symlinked marker bundle is preserved' test -L "$marked_release/.apm-installed" -a -x "$marked_release/apm"

new_case dangling-legacy-symlink
make_fixture Linux x86_64
mkdir -p "$CASE_ROOT/install/lib/apm"
ln -s "$CASE_ROOT/install/lib/apm/apm" "$CASE_INSTALL/apm"
run_case --cli-only
record_result 'dangling symlink to a removed legacy bundle is repaired' success
assert_true 'dangling legacy symlink is replaced' test -d "$(active_release)"
assert_true 'repaired legacy command is usable' file_has <("$CASE_INSTALL/apm" --version) '0.29.0'

new_case dangling-generation-symlink
make_fixture Linux x86_64
mkdir -p "$CASE_ROOT/install/lib/apm/releases"
ln -s "$CASE_ROOT/install/lib/apm/releases/v0.28.0-20260101T000000Z-4242/apm" "$CASE_INSTALL/apm"
run_case --cli-only
record_result 'dangling symlink to a removed generation is repaired' success
assert_true 'dangling generation symlink is replaced' test -d "$(active_release)"
assert_true 'repaired command is usable' file_has <("$CASE_INSTALL/apm" --version) '0.29.0'

new_case unmarked-stage-entry
make_fixture Linux x86_64
mkdir -p "$CASE_ROOT/install/lib/apm/releases/.stage-notes" \
    "$CASE_ROOT/install/lib/apm/releases/.stage-v0.28.0-20260101T000000Z-1"
printf 'user notes\n' > "$CASE_ROOT/install/lib/apm/releases/.stage-notes/keep"
printf 'v0.28.0\n' > "$CASE_ROOT/install/lib/apm/releases/.stage-v0.28.0-20260101T000000Z-1/.apm-installed"
run_case --cli-only
record_result 'unmarked stage-like directory survives cleanup' success
assert_true 'unmarked stage-like directory is named in a warning' \
    out_has "warning: leaving an unrecognized entry in the APM releases directory: $CASE_ROOT/install/lib/apm/releases/.stage-notes"
assert_true 'unmarked stage-like directory is preserved' file_has "$CASE_ROOT/install/lib/apm/releases/.stage-notes/keep" 'user notes'
assert_true 'marked abandoned stage is removed' test ! -e "$CASE_ROOT/install/lib/apm/releases/.stage-v0.28.0-20260101T000000Z-1"
assert_true 'unmarked stage case leaves the install usable' file_has <("$CASE_INSTALL/apm" --version) '0.29.0'

new_case nested-symlink-generation
make_fixture Linux x86_64
mkdir -p "$CASE_ROOT/install/lib/apm/releases" "$CASE_ROOT/outside"
printf '#!/bin/sh\nexit 0\n' > "$CASE_ROOT/outside/apm"
ln -s "$CASE_ROOT/outside" "$CASE_ROOT/install/lib/apm/releases/v0.29.0-20260101T000000Z-4242"
ln -s "$CASE_ROOT/install/lib/apm/releases/v0.29.0-20260101T000000Z-4242/apm" "$CASE_INSTALL/apm"
run_case --cli-only
record_result 'well-formed symlink through a symlinked generation directory is not overwritten' failure
assert_true 'symlinked generation directory is diagnosed' out_has 'refusing to overwrite an APM symlink whose target resolves through another symlink'
assert_true 'symlinked generation directory link is preserved' \
    test "$(readlink "$CASE_INSTALL/apm")" = "$CASE_ROOT/install/lib/apm/releases/v0.29.0-20260101T000000Z-4242/apm"
assert_true 'symlinked generation directory target is preserved' test -f "$CASE_ROOT/outside/apm"

new_case symlinked-generation-executable
make_fixture Linux x86_64
mkdir -p "$CASE_ROOT/install/lib/apm/releases/v0.29.0-20260101T000000Z-4242" "$CASE_ROOT/outside"
printf '#!/bin/sh\nexit 0\n' > "$CASE_ROOT/outside/apm"
ln -s "$CASE_ROOT/outside/apm" "$CASE_ROOT/install/lib/apm/releases/v0.29.0-20260101T000000Z-4242/apm"
ln -s "$CASE_ROOT/install/lib/apm/releases/v0.29.0-20260101T000000Z-4242/apm" "$CASE_INSTALL/apm"
run_case --cli-only
record_result 'well-formed symlink to a symlinked generation executable is not overwritten' failure
assert_true 'symlinked generation executable is diagnosed' out_has 'refusing to overwrite an APM symlink whose target resolves through another symlink'
assert_true 'symlinked generation executable link is preserved' \
    test "$(readlink "$CASE_INSTALL/apm")" = "$CASE_ROOT/install/lib/apm/releases/v0.29.0-20260101T000000Z-4242/apm"

new_case foreign-stage-collision
make_fixture Linux x86_64
real_mkdir=$(command -v mkdir)
# Another process creates the stage path first; this run's mkdir then fails.
cat > "$CASE_BIN/mkdir" <<EOF
#!/usr/bin/env bash
for argument in "\$@"; do
    case "\$argument" in
        */.stage-*)
            '$real_mkdir' "\$argument"
            printf 'foreign\n' > "\$argument/keep"
            printf '%s\n' "\$argument" > '$CASE_ROOT/collided-stage'
            exit 1
            ;;
    esac
done
exec '$real_mkdir' "\$@"
EOF
chmod +x "$CASE_BIN/mkdir"
run_case --cli-only
record_result 'stage collision after preflight is surfaced' failure
assert_true 'stage collision is reached' test -f "$CASE_ROOT/collided-stage"
assert_true 'stage collision is diagnosed' out_has 'unable to create'
assert_true 'colliding stage created by another process is preserved' \
    file_has "$(cat "$CASE_ROOT/collided-stage")/keep" 'foreign'
assert_true 'stage collision releases the lock' test ! -e "$CASE_ROOT/install/lib/apm/.lock"

new_case foreign-releases-entries
make_fixture Linux x86_64
run_case --cli-only
record_result 'foreign entries fixture installs prior generation' success
first_release=$(active_release)
mkdir "$CASE_ROOT/install/lib/apm/releases/notes"
printf 'user notes\n' > "$CASE_ROOT/install/lib/apm/releases/notes/todo"
printf 'user file\n' > "$CASE_ROOT/install/lib/apm/releases/README.txt"
mkdir "$CASE_ROOT/install/lib/apm/releases/v0.28.0-unmarked"
sleep 1
run_case --cli-only
record_result 'foreign entries do not block supersession' success
assert_true 'foreign entries are diagnosed' out_has 'leaving an unrecognized entry in the APM releases directory'
assert_true 'foreign directory is preserved' file_has "$CASE_ROOT/install/lib/apm/releases/notes/todo" 'user notes'
assert_true 'foreign file is preserved' file_has "$CASE_ROOT/install/lib/apm/releases/README.txt" 'user file'
assert_true 'unmarked release-like directory is preserved' test -d "$CASE_ROOT/install/lib/apm/releases/v0.28.0-unmarked"
assert_true 'marked superseded generation is still removed' test ! -e "$first_release"
assert_true 'command is usable beside foreign entries' file_has <("$CASE_INSTALL/apm" --version) '0.29.0'

new_case signal-after-activation
make_fixture Linux x86_64
run_case --cli-only
record_result 'activation signal fixture installs prior generation' success
prior_release=$(active_release)
sleep 1
real_mv=$(command -v mv)
cat > "$CASE_BIN/mv" <<EOF
#!/usr/bin/env bash
'$real_mv' "\$@" || exit \$?
for argument in "\$@"; do
    case "\$argument" in */.apm-v0.29.0-*) : > '$CASE_ROOT/activation-signal'; kill -TERM "\$PPID" ;; esac
done
EOF
chmod +x "$CASE_BIN/mv"
run_case --cli-only
record_result 'interruption after activation exits by signal' failure
assert_true 'activation signal follows the link rename' test -f "$CASE_ROOT/activation-signal"
assert_true 'activation signal exits 130' test "$STATUS" -eq 130
assert_true 'activation signal keeps the new generation active' test "$(active_release)" != "$prior_release"
assert_true 'activated generation survives the interrupted cleanup' test -x "$(active_release)/apm"
assert_true 'activated command is usable after interruption' file_has <("$CASE_INSTALL/apm" --version) '0.29.0'
assert_true 'activation signal releases the lock' test ! -e "$CASE_ROOT/install/lib/apm/.lock"
assert_true 'activation signal leaves no stage behind' \
    test -z "$(find "$CASE_ROOT/install/lib/apm/releases" -name '.stage-*' -print -quit)"

# Fail each step once. The active generation must be untouched by any failure
# before the single activating rename, and nothing partial may remain.
for prior in existing fresh; do
    for fault in copy checksum execution version banner rename link; do
        new_case "isolation-$prior-$fault"
        make_fixture Linux x86_64
        prior_release=''
        if [ "$prior" = existing ]; then
            run_case --cli-only
            record_result "$prior $fault fixture installs prior generation" success
            prior_release=$(active_release)
            printf 'prior release\n' > "$prior_release/_internal/old"
            sleep 1
        fi
        case "$fault" in
            copy) command_name='cp'; pattern='*/.stage-*' ;;
            rename) command_name='mv'; pattern='*/.stage-*' ;;
            link) command_name='ln'; pattern='*/.apm-v0.29.0-*' ;;
            checksum) command_name='sha256sum'; pattern='*/.stage-*/apm' ;;
            execution|version|banner)
                cat > "$BUNDLE_ROOT/apm" <<EOF
#!/usr/bin/env bash
case "\$0" in
    */.stage-*/apm)
        : > '$CASE_ROOT/fault-hit'
        [ '$fault' != execution ] || exit 73
        if [ '$fault' = banner ]; then printf 'no version\n'; exit 0; fi
        printf 'APM version 9.9.9\n'
        exit 0
        ;;
esac
printf 'APM version 0.29.0\n'
EOF
                tar -czf "$MIRROR_ROOT/v0.29.0/$ARCHIVE_NAME" -C "$FIXTURE_ROOT" "$ARCHIVE_ROOT"
                replace_checksum "$ARCHIVE_ROOT/apm" "$(digest "$BUNDLE_ROOT/apm")"
                replace_checksum "$ARCHIVE_NAME" "$(digest "$MIRROR_ROOT/v0.29.0/$ARCHIVE_NAME")"
                ;;
        esac
        case "$fault" in
            copy|rename|link|checksum)
                real_command=$(command -v "$command_name")
                cat > "$CASE_BIN/$command_name" <<EOF
#!/usr/bin/env bash
for argument in "\$@"; do
    case "\$argument" in
        $pattern)
            if [ ! -f '$CASE_ROOT/fault-hit' ]; then
                : > '$CASE_ROOT/fault-hit'
                exit 73
            fi
            ;;
    esac
done
exec '$real_command' "\$@"
EOF
                chmod +x "$CASE_BIN/$command_name"
                ;;
        esac
        run_case --cli-only
        record_result "$prior $fault failure is surfaced" failure
        assert_true "$prior $fault injection was reached" test -f "$CASE_ROOT/fault-hit"
        assert_true "$prior $fault releases the installation lock" test ! -e "$CASE_ROOT/install/lib/apm/.lock"
        case "$fault" in
            execution|banner)
                assert_true "$prior $fault uses a phase-neutral version diagnostic" out_has 'the APM executable'
                assert_true "$prior $fault is not misreported as a mismatch" out_lacks 'does not report the pinned'
                ;;
            version)
                assert_true "$prior $fault reports the pin mismatch" out_has 'does not report the pinned v0.29.0'
                ;;
        esac
        if [ "$prior" = existing ]; then
            assert_true "$fault keeps the prior generation active" test "$(active_release)" = "$prior_release"
            assert_true "$fault preserves prior generation content" file_has "$prior_release/_internal/old" 'prior release'
            assert_true "$fault preserves usable command" file_has <("$CASE_INSTALL/apm" --version) '0.29.0'
            assert_true "$fault leaves exactly one generation" \
                test "$(find "$CASE_ROOT/install/lib/apm/releases" -mindepth 1 -maxdepth 1 | wc -l | tr -d ' ')" -eq 1
        else
            assert_true "$fault leaves no generation" \
                test -z "$(find "$CASE_ROOT/install/lib/apm/releases" -mindepth 1 -print -quit)"
            assert_true "$fault leaves no command link" test ! -e "$CASE_INSTALL/apm" -a ! -L "$CASE_INSTALL/apm"
        fi
        assert_true "$prior $fault leaves no staged link" \
            test -z "$(find "$CASE_INSTALL" -name '.apm-*' -print -quit)"
    done
done

printf '# interruption and serialization\n'
new_case signal-during-staging
make_fixture Linux x86_64
run_case --cli-only
record_result 'staging signal fixture installs prior generation' success
prior_release=$(active_release)
printf 'prior release\n' > "$prior_release/_internal/old"
sleep 1
real_cp=$(command -v cp)
cat > "$CASE_BIN/cp" <<EOF
#!/usr/bin/env bash
'$real_cp' "\$@" || exit \$?
for argument in "\$@"; do
    case "\$argument" in */.stage-*/) : > '$CASE_ROOT/staging-signal'; kill -TERM "\$PPID" ;; esac
done
EOF
chmod +x "$CASE_BIN/cp"
run_case --cli-only
record_result 'interruption during staging aborts installation' failure
assert_true 'staging signal follows a completed copy' test -f "$CASE_ROOT/staging-signal"
assert_true 'staging signal releases the lock' test ! -e "$CASE_ROOT/install/lib/apm/.lock"
assert_true 'staging signal keeps the prior generation active' test "$(active_release)" = "$prior_release"
assert_true 'staging signal preserves a usable command' file_has <("$CASE_INSTALL/apm" --version) '0.29.0'
assert_true 'staging signal cleans the staged generation' \
    test -z "$(find "$CASE_ROOT/install/lib/apm/releases" -name '.stage-*' -print -quit)"

new_case signal-during-lock-acquire
make_fixture Linux x86_64
real_mkdir=$(command -v mkdir)
cat > "$CASE_BIN/mkdir" <<EOF
#!/usr/bin/env bash
'$real_mkdir' "\$@" || exit \$?
case "\$*" in
    *'/lib/apm/.lock') : > '$CASE_ROOT/lock-acquire-signal'; kill -TERM "\$PPID" ;;
esac
EOF
chmod +x "$CASE_BIN/mkdir"
run_case --cli-only
record_result 'interruption between lock creation and ownership record is discarded' success
assert_true 'lock acquire signal was sent' test -f "$CASE_ROOT/lock-acquire-signal"
assert_true 'lock acquire signal leaves no stale lock' test ! -e "$CASE_ROOT/install/lib/apm/.lock"
assert_true 'lock acquire signal leaves the install usable' file_has <("$CASE_INSTALL/apm" --version) '0.29.0'

new_case signal-during-lock-release
make_fixture Linux x86_64
real_rmdir=$(command -v rmdir)
cat > "$CASE_BIN/rmdir" <<EOF
#!/usr/bin/env bash
'$real_rmdir' "\$@" || exit \$?
[ ! -f '$CASE_ROOT/lock-release-signal' ] || exit 0
# Another bootstrap takes the lock immediately, then the signal lands.
mkdir "\$1"
: > '$CASE_ROOT/lock-release-signal'
kill -TERM "\$PPID"
EOF
chmod +x "$CASE_BIN/rmdir"
run_case --cli-only
record_result 'interruption during lock release exits by signal' failure
assert_true 'lock release signal follows the removal' test -f "$CASE_ROOT/lock-release-signal"
assert_true 'lock release signal does not remove the next owner lock' test -d "$CASE_ROOT/install/lib/apm/.lock"
assert_true 'lock release signal leaves the new generation active' file_has <("$CASE_INSTALL/apm" --version) '0.29.0'

# File barriers make the ordering deterministic; polling only bounds fixture failures.
# Invoked indirectly by assert_true.
# shellcheck disable=SC2317
wait_for_file() {
    local path=$1 attempt=0
    while [ ! -f "$path" ] && [ "$attempt" -lt 200 ]; do
        sleep 0.05
        attempt=$((attempt + 1))
    done
    test -f "$path"
}

new_case concurrent-bootstrap
make_fixture Linux x86_64
real_cp=$(command -v cp)
real_sleep=$(command -v sleep)
cat > "$CASE_BIN/cp" <<EOF
#!/usr/bin/env bash
for argument in "\$@"; do
    case "\$argument" in
        */.stage-*/)
            : > '$CASE_ROOT/owner-staging'
            while [ ! -f '$CASE_ROOT/release-owner' ]; do '$real_sleep' 0.05; done
            ;;
    esac
done
exec '$real_cp' "\$@"
EOF
chmod +x "$CASE_BIN/cp"
(
    CASE_ACTOR=first
    run_case --cli-only
    printf '%s\n' "$STATUS" > "$CASE_ROOT/first-status"
    printf '%s\n' "$OUTPUT" > "$CASE_ROOT/first-output"
) &
first_pid=$!
assert_true 'owner holds the lock while staging' wait_for_file "$CASE_ROOT/owner-staging"
CASE_ACTOR=second
run_case --cli-only
record_result 'contender fails fast while the lock is held' failure
assert_true 'contender names the lock it needs' out_has "another bootstrap owns $CASE_ROOT/install/lib/apm/.lock"
assert_true 'contender does not remove the owner lock' test -d "$CASE_ROOT/install/lib/apm/.lock"
: > "$CASE_ROOT/release-owner"
wait "$first_pid"
assert_true 'owner completes after the contender fails' file_has "$CASE_ROOT/first-status" '0'
assert_true 'owner leaves a usable command' file_has <("$CASE_INSTALL/apm" --version) '0.29.0'
assert_true 'owner releases the lock' test ! -e "$CASE_ROOT/install/lib/apm/.lock"

new_case concurrent-deployment
make_fixture Linux x86_64
real_sleep=$(command -v sleep)
# The fixture CLI blocks during the native handoff so a contender can run then.
cat > "$BUNDLE_ROOT/apm" <<EOF
#!/usr/bin/env bash
printf '%s\n' "\$0 \$*" >> '$CALL_LOG'
case "\${1-}" in
    --version) printf 'Agent Package Manager (APM) CLI version 0.29.0 (fixture)\n' ;;
    install)
        : > '$CASE_ROOT/owner-deploying'
        while [ ! -f '$CASE_ROOT/release-owner' ]; do '$real_sleep' 0.05; done
        ;;
esac
exit 0
EOF
tar -czf "$MIRROR_ROOT/v0.29.0/$ARCHIVE_NAME" -C "$FIXTURE_ROOT" "$ARCHIVE_ROOT"
replace_checksum "$ARCHIVE_ROOT/apm" "$(digest "$BUNDLE_ROOT/apm")"
replace_checksum "$ARCHIVE_NAME" "$(digest "$MIRROR_ROOT/v0.29.0/$ARCHIVE_NAME")"
(
    CASE_ACTOR=first
    run_case --repo
    printf '%s\n' "$STATUS" > "$CASE_ROOT/first-status"
) &
first_pid=$!
assert_true 'owner reaches the native handoff' wait_for_file "$CASE_ROOT/owner-deploying"
owner_release=$(active_release)
CASE_ACTOR=second
run_case --cli-only
record_result 'contender fails fast during the native handoff' failure
assert_true 'contender is told the lock is held' out_has "another bootstrap owns $CASE_ROOT/install/lib/apm/.lock"
assert_true 'contender leaves the owner generation active' test "$(active_release)" = "$owner_release"
assert_true 'contender leaves the owner generation intact' test -d "$owner_release/_internal"
: > "$CASE_ROOT/release-owner"
wait "$first_pid"
assert_true 'owner completes its deployment' file_has "$CASE_ROOT/first-status" '0'
assert_true 'owner runs every native step from its generation' file_has "$CALL_LOG" 'compile --target codex,copilot'
assert_true 'owner releases the lock after the handoff' test ! -e "$CASE_ROOT/install/lib/apm/.lock"

for lock_kind in directory file symlink; do
    new_case "lock-$lock_kind"
    make_fixture Linux x86_64
    run_case --cli-only
    record_result "$lock_kind lock fixture installs prior generation" success
    prior_release=$(active_release)
    printf 'prior release\n' > "$prior_release/_internal/old"
    lock_path="$CASE_ROOT/install/lib/apm/.lock"
    case "$lock_kind" in
        directory) mkdir "$lock_path" ;;
        file) printf 'unrelated\n' > "$lock_path" ;;
        symlink)
            mkdir "$CASE_ROOT/lock-target"
            ln -s "$CASE_ROOT/lock-target" "$lock_path"
            ;;
    esac
    cat > "$CASE_BIN/sleep" <<EOF
#!/usr/bin/env bash
printf '%s\n' "\$*" >> '$CASE_ROOT/waits'
EOF
    chmod +x "$CASE_BIN/sleep"
    run_case --cli-only
    record_result "$lock_kind lock blocks installation" failure
    assert_true "$lock_kind lock is rejected without waiting" test ! -f "$CASE_ROOT/waits"
    if [ "$lock_kind" = directory ]; then
        assert_true 'directory lock diagnostic names the lock and manual recovery' out_has "another bootstrap owns $lock_path; wait for it to finish, or remove that directory if no bootstrap is running"
    else
        assert_true "$lock_kind lock is diagnosed as unrelated" out_has "refusing to use an unrelated entry as the APM installation lock: $lock_path"
        assert_true "$lock_kind lock is not misreported as another bootstrap" out_lacks 'another bootstrap owns'
    fi
    assert_true "$lock_kind lock is not removed by a non-owner" test -e "$lock_path" -o -L "$lock_path"
    assert_true "$lock_kind lock preserves the active generation" test "$(active_release)" = "$prior_release"
    assert_true "$lock_kind lock preserves usable command" file_has <("$CASE_INSTALL/apm" --version) '0.29.0'
done

printf '\n%d cases, %d failures\n' "$CASES" "$FAILURES"
exit "$((FAILURES > 0 ? 1 : 0))"
