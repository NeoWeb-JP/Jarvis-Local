#!/bin/sh
# Stage and compare only. Never stop, start, recreate or change a container.
set -eu
umask 077
root=/opt/voicepipeline
live=voicepipeline
test_container=voicepipeline-isolated-test
revision=ef51052f728afffc3874d1eea091a52cb52f057b
base="https://raw.githubusercontent.com/NeoWeb-JP/Jarvis-Local/$revision/deployment/voice-bridge/experiments/history-correction"
expected_image='sha256:aefd844361f6816721a5497d25eefbfdf670e33df81c0e16dde533f68e510a55'
expected_files="$root/compose.yaml,$root/compose.override.yaml,$root/compose.bridge-test.yaml,$root/compose.cache-test.yaml"
work=''
cleanup() { rc=$?; trap - EXIT; [ -z "$work" ] || rm -rf -- "$work"; exit "$rc"; }
trap cleanup EXIT

command -v python3 >/dev/null || { echo 'python3 is required on the voice server.' >&2; exit 1; }
[ "$(docker inspect "$live" --format '{{.State.Running}}')" = true ]
[ "$(docker inspect "$live" --format '{{.Image}}')" = "$expected_image" ]
[ "$(docker inspect "$live" --format '{{index .Config.Labels "com.docker.compose.project"}}')" = voicepipeline ]
[ "$(docker inspect "$live" --format '{{index .Config.Labels "com.docker.compose.service"}}')" = voicepipeline ]
[ "$(docker inspect "$live" --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}')" = "$root" ]
[ "$(docker inspect "$live" --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}')" = "$expected_files" ]

file_sha() { docker exec "$1" sha256sum "$2" | awk '{print $1}'; }
[ "$(file_sha "$live" /app/api/main.py)" = 83b8285bc91b451fcf1e1b80db141cf9d3f1620026186d7f511f128066e8c386 ]
[ "$(file_sha "$live" /app/ui/app.js)" = e4156a695b1c6a20e8a1700a565b3070918174fd805d1fd9aeb87cb1066d7be1 ]
[ "$(file_sha "$live" /app/pipeline/models/speaker_id.py)" = fb5c6f04121e61a4ae1e7d84cc8615c22eaa032aaa58154bf324952f98c9640f ]
[ "$(file_sha "$test_container" /app/api/main.py)" = 56a085ecf601ba243d908f9acfd19fd175cb4ed5f411b58b50b6893f9c782a47 ]
[ "$(file_sha "$test_container" /app/ui/app.js)" = bd8584122297456d6b7a67112f030ed62a72aae8485b68201ad2dea086e66e87 ]

stage=$(mktemp -d "$root/history-correction-stage.XXXXXX")
work=$(mktemp -d "$stage/private.XXXXXX")
echo "Staging directory: $stage"
curl -fsS "$base/api.py" -o "$stage/api.py"
curl -fsS "$base/ui.js" -o "$stage/ui.js"
curl -fsS "$base/check_compose.py" -o "$stage/check_compose.py"
printf '%s\n' \
 "56a085ecf601ba243d908f9acfd19fd175cb4ed5f411b58b50b6893f9c782a47  $stage/api.py" \
 "bd8584122297456d6b7a67112f030ed62a72aae8485b68201ad2dea086e66e87  $stage/ui.js" \
 "95246da241a505fe224f7beac72adf8db0ce1f9b68671a46815de7b99f352826  $stage/check_compose.py" | sha256sum -c -

cat > "$stage/compose.history-correction.yaml" <<EOF
services:
  voicepipeline:
    volumes:
      - type: bind
        source: $stage/api.py
        target: /app/api/main.py
        read_only: true
      - type: bind
        source: $stage/ui.js
        target: /app/ui/app.js
        read_only: true
EOF

cd "$root"
# The complete resolved models may contain credentials. Save them only in a
# private temporary directory, inspect locally, and remove them on exit.
docker compose --project-directory "$root" -p voicepipeline \
  -f "$root/compose.yaml" -f "$root/compose.override.yaml" \
  -f "$root/compose.bridge-test.yaml" -f "$root/compose.cache-test.yaml" \
  config --format json > "$work/before.json"
docker compose --project-directory "$root" -p voicepipeline \
  -f "$root/compose.yaml" -f "$root/compose.override.yaml" \
  -f "$root/compose.bridge-test.yaml" -f "$root/compose.cache-test.yaml" \
  -f "$stage/compose.history-correction.yaml" config --format json > "$work/after.json"
docker inspect "$live" --format '{{json .Mounts}}' > "$work/mounts.json"
python3 "$stage/check_compose.py" "$work/before.json" "$work/after.json" "$work/mounts.json" "$stage"
image_ref=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["services"]["voicepipeline"]["image"])' "$work/before.json")
image_id=$(docker image inspect "$image_ref" --format '{{.Id}}')
[ "$image_id" = "$expected_image" ] || { echo 'Compose image tag resolves to a different image; stopping.' >&2; exit 1; }
echo 'Compose image resolves to the running image ID.'

sha256sum "$root/compose.yaml" "$root/compose.override.yaml" \
  "$root/compose.bridge-test.yaml" "$root/compose.cache-test.yaml" \
  "$root/jarvis-speaker-cache-fix.py" "$root/jarvis-bridge-wyoming.py" \
  "$stage/api.py" "$stage/ui.js" "$stage/check_compose.py" \
  "$stage/compose.history-correction.yaml" > "$stage/source-checksums.txt"
if [ -f "$root/.env" ]; then sha256sum "$root/.env" >> "$stage/source-checksums.txt"; fi
echo 'Source checksums saved privately for the later deployment review.'
echo 'No container was stopped, started, recreated or modified.'
