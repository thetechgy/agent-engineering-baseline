#!/usr/bin/env bash
set -euo pipefail
umask 077
root="$RUNNER_TEMP/code-mode-evidence"
experiment="$GITHUB_WORKSPACE/investigations/code-mode-evidence"
mkdir -p "$root/evidence" "$root/context"
git clone --quiet --depth=1 --branch rust-v0.166.0 https://github.com/openai/codex.git "$root/source"
test "$(git -C "$root/source" rev-parse HEAD)" = 6ff1e1ca3b30fc8b914720681fcf5fe62e95f856
git -C "$root/source" fetch --quiet --depth=1 origin tag rust-v0.165.0
git -C "$root/source" diff rust-v0.165.0 HEAD -- codex-rs/code-mode-protocol/src/grpc/codex.code_mode.v1.proto codex-rs/core/src/code_mode_host.rs codex-rs/code-mode/src/grpc_session > "$root/evidence/version-diff.txt"
for version in 166 165; do
  context="$root/context/$version"
  mkdir -p "$context/bindings"
  cp "$experiment/"{Dockerfile,requirements.txt,stock.py,native.py,lifecycle.py} "$context/"
  cp "$GITHUB_WORKSPACE/investigations/native-codex-qualification/aeb_native_qualification/helpers/native_controller.py" "$context/controller.py"
  cp "$GITHUB_WORKSPACE/investigations/native-codex-qualification/aeb_native_qualification/helpers/attack.py" "$context/attack.py"
  for component in codex codex-code-mode-host; do
    archive="$root/$version-$component.tar.gz"
    curl --fail --location --silent --show-error --proto '=https' --proto-redir '=https' "https://github.com/openai/codex/releases/download/rust-v0.$version.0/$component-x86_64-unknown-linux-musl.tar.gz" -o "$archive"
    case "$version-$component" in
      166-codex) digest=a0bf572d2f93f056c6712a6da348e96078dc84f3885fd7be67807ef389cb3978 ;;
      166-codex-code-mode-host) digest=7588334fd47bc4003d970b70dfd4d1e4578491b1e9baa72976a4c2d7e97590da ;;
      165-codex) digest=be635d3486a5bd060d0fff582ae6d30160280c31344dd85719707fa920e187f0 ;;
      165-codex-code-mode-host) digest=9577b09b2a546eeb3da8a09807de6d58fbaa207755256390113772ea4f05235e ;;
    esac
    printf '%s  %s\n' "$digest" "$archive" | sha256sum -c
    tar -xzf "$archive" -C "$context"
  done
  git -C "$root/source" show "rust-v0.$version.0:codex-rs/code-mode-protocol/src/grpc/codex.code_mode.v1.proto" > "$context/bindings/code_mode.proto"
  git -C "$root/source" show "rust-v0.$version.0:codex-rs/models-manager/models.json" > "$context/catalog.json"
  docker build --quiet -t "aeb-cm:$version" "$context"
  name="aeb-cm-$GITHUB_RUN_ID-$version"
  trap 'docker rm -f "$name" >/dev/null 2>&1 || true' EXIT
  docker run -d --name "$name" --network=none --cap-drop=ALL --security-opt=no-new-privileges --pids-limit=256 --memory=2g --cpus=2 "aeb-cm:$version"
  docker inspect "$name" > "$root/evidence/container-$version.json"
  docker exec "$name" python -m grpc_tools.protoc -I/opt/experiment/bindings --python_out=/workspace --grpc_python_out=/workspace /opt/experiment/bindings/code_mode.proto
  docker exec "$name" python /opt/experiment/stock.py --host /opt/experiment/codex-code-mode-host-x86_64-unknown-linux-musl --out /workspace/stock.json
  docker exec "$name" python /opt/experiment/native.py --host /opt/experiment/codex-code-mode-host-x86_64-unknown-linux-musl --codex /opt/experiment/codex-x86_64-unknown-linux-musl --catalog /opt/experiment/catalog.json --controller /opt/experiment/controller.py --out /workspace/native.json
  docker cp "$name:/workspace/stock.json" "$root/evidence/stock-$version.json"
  docker cp "$name:/workspace/native.json" "$root/evidence/native-$version.json"
  if [ "$version" = 166 ]; then
    docker exec "$name" python /opt/experiment/native.py --attacks --host /opt/experiment/codex-code-mode-host-x86_64-unknown-linux-musl --codex /opt/experiment/codex-x86_64-unknown-linux-musl --catalog /opt/experiment/catalog.json --controller /opt/experiment/controller.py --out /workspace/producer.json
    docker cp "$name:/workspace/producer.json" "$root/evidence/producer.json"
    docker exec "$name" python /opt/experiment/lifecycle.py --host /opt/experiment/codex-code-mode-host-x86_64-unknown-linux-musl --out /workspace/lifecycle.json
    docker cp "$name:/workspace/lifecycle.json" "$root/evidence/lifecycle.json"
  fi
  docker rm -f "$name"
  trap - EXIT
done
python3 "$experiment/check.py" "$root/evidence"
python3 "$experiment/check_producer.py" "$root/evidence"
python3 "$experiment/outcome_security.py" > "$root/evidence/outcome-security.json"
git -C "$root/source" apply --check "$experiment/callback-observation.patch"
git -C "$root/source" apply "$experiment/callback-observation.patch"
git -C "$root/source" diff --stat > "$root/evidence/patch-stat.txt"
cd "$root/source/codex-rs"
rustup toolchain install 1.95.0 --profile minimal
python3 "$experiment/prepare_v8.py" "$root/source" "$root/v8"
export RUSTY_V8_ARCHIVE="$root/v8/librusty_v8_ptrcomp_sandbox_release_x86_64-unknown-linux-gnu.a.gz"
export RUSTY_V8_SRC_BINDING_PATH="$root/v8/src_binding_ptrcomp_sandbox_release_x86_64-unknown-linux-gnu.rs"
set +e
timeout 1200 cargo build --locked -p codex-code-mode-host -j 2 > "$root/evidence/patch-build.log" 2>&1
build_status=$?
set -e
printf '{"build_exit":%s,"security_admission":"unavailable-pending-patch-qualification"}\n' "$build_status" > "$root/evidence/patch-build.json"
if [ "$build_status" != 0 ]; then
  # Diagnose the release boundary independently. Never build with a new lock.
  git -C "$root/source" apply -R "$experiment/callback-observation.patch"
  cp Cargo.lock "$root/original-Cargo.lock"
  set +e
  timeout 120 cargo build --locked -p codex-code-mode-host -j 2 > "$root/evidence/unmodified-build.log" 2>&1
  baseline_status=$?
  timeout 60 cargo metadata --offline --format-version 1 > /dev/null 2> "$root/evidence/diagnostic-metadata.log"
  diagnostic_status=$?
  set -e
  git diff -- Cargo.lock > "$root/evidence/diagnostic-lock-delta.txt"
  cp "$root/original-Cargo.lock" Cargo.lock
  git diff --exit-code -- Cargo.lock
  printf '{"unmodified_build_exit":%s,"diagnostic_metadata_exit":%s,"candidate_lock_used_for_build":false}\n' "$baseline_status" "$diagnostic_status" > "$root/evidence/build-boundary.json"
fi
if [ "$build_status" = 0 ]; then
  chmod 0555 target/debug/codex-code-mode-host
  sha256sum target/debug/codex-code-mode-host > "$root/evidence/patch-binary.sha256"
  name="aeb-cm-$GITHUB_RUN_ID-patched"
  trap 'docker rm -f "$name" >/dev/null 2>&1 || true' EXIT
  docker run -d --name "$name" --network=none --cap-drop=ALL --security-opt=no-new-privileges --pids-limit=256 --memory=2g --cpus=2 aeb-cm:166
  docker cp target/debug/codex-code-mode-host "$name:/workspace/patched-host"
  docker exec "$name" python -m grpc_tools.protoc -I/opt/experiment/bindings --python_out=/workspace --grpc_python_out=/workspace /opt/experiment/bindings/code_mode.proto
  docker exec -e AEB_CALLBACK_JOURNAL=/workspace/callbacks.jsonl "$name" python /opt/experiment/stock.py --host /workspace/patched-host --out /workspace/patched.json
  docker cp "$name:/workspace/patched.json" "$root/evidence/patched.json"
  docker cp "$name:/workspace/callbacks.jsonl" "$root/evidence/callbacks.jsonl"
  python3 "$experiment/check_patch.py" "$root/evidence"
  docker rm -f "$name"
  trap - EXIT
fi
