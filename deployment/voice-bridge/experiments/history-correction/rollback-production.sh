#!/bin/sh
# Restore only the app code by removing the extra Compose override.
# Never replace /data, models, speaker patches, or the database.
set -eu
umask 077
root=/opt/voicepipeline
live=voicepipeline
stage=${1:?Usage: rollback-production.sh /opt/voicepipeline/history-correction-stage.XXXXXX}
case "$stage" in "$root"/history-correction-stage.*) ;; *) echo 'Unexpected staging path.' >&2; exit 1;; esac
[ "$(readlink -f "$stage")" = "$stage" ] || { echo 'Staging path must be a real directory.' >&2; exit 1; }
revision=5e52060f9d5a29319ba35bc09aebbcfda69ba250
base="https://raw.githubusercontent.com/NeoWeb-JP/Jarvis-Local/$revision/deployment/voice-bridge/experiments/history-correction"
expected_image='sha256:aefd844361f6816721a5497d25eefbfdf670e33df81c0e16dde533f68e510a55'
expected_files="$root/compose.yaml,$root/compose.override.yaml,$root/compose.bridge-test.yaml,$root/compose.cache-test.yaml,$stage/compose.history-correction.yaml"
work=''
started=0
cleanup() {
  rc=$?
  trap - EXIT
  if [ "$rc" -ne 0 ] && [ "$started" -eq 1 ]; then
    echo 'Rollback did not complete. Inspect the container before retrying; the database was not restored.' >&2
  fi
  [ -z "$work" ] || rm -rf -- "$work"
  exit "$rc"
}
trap cleanup EXIT

compose_old() {
  docker compose --project-directory "$root" -p voicepipeline \
    -f "$root/compose.yaml" -f "$root/compose.override.yaml" \
    -f "$root/compose.bridge-test.yaml" -f "$root/compose.cache-test.yaml" "$@"
}
compose_new() {
  docker compose --project-directory "$root" -p voicepipeline \
    -f "$root/compose.yaml" -f "$root/compose.override.yaml" \
    -f "$root/compose.bridge-test.yaml" -f "$root/compose.cache-test.yaml" \
    -f "$stage/compose.history-correction.yaml" "$@"
}

[ "$(docker inspect "$live" --format '{{.State.Running}}')" = true ]
[ "$(docker inspect "$live" --format '{{.Image}}')" = "$expected_image" ]
[ "$(docker inspect "$live" --format '{{index .Config.Labels "com.docker.compose.project"}}')" = voicepipeline ]
[ "$(docker inspect "$live" --format '{{index .Config.Labels "com.docker.compose.service"}}')" = voicepipeline ]
[ "$(docker inspect "$live" --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}')" = "$root" ]
[ "$(docker inspect "$live" --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}')" = "$expected_files" ]
sha256sum -c "$stage/source-checksums.txt"
file_sha() { docker exec "$live" sha256sum "$1" | awk '{print $1}'; }
[ "$(file_sha /app/api/main.py)" = 56a085ecf601ba243d908f9acfd19fd175cb4ed5f411b58b50b6893f9c782a47 ]
[ "$(file_sha /app/ui/app.js)" = bd8584122297456d6b7a67112f030ed62a72aae8485b68201ad2dea086e66e87 ]
[ "$(file_sha /app/pipeline/models/speaker_id.py)" = fb5c6f04121e61a4ae1e7d84cc8615c22eaa032aaa58154bf324952f98c9640f ]

work=$(mktemp -d "$stage/private.rollback.XXXXXX")
curl -fsS "$base/check_runtime.py" -o "$work/check_runtime.py"
curl -fsS "$base/check_post_deploy.py" -o "$work/check_post_deploy.py"
printf '%s\n' \
 "51c8efba255b251d6bace8a7f2845574a4535e030e23ecaa46eed9c2ed8c0398  $work/check_runtime.py" \
 "61d07eacfe5b66ca1dfd2f202a7fb4157541f1241e0d493c1f3e700b5782d249  $work/check_post_deploy.py" | sha256sum -c -
cd "$root"
compose_old config --format json > "$work/before.json"
compose_new config --format json > "$work/after.json"
docker inspect "$live" --format '{{json .Mounts}}' > "$work/current-mounts.json"
python3 - "$work/current-mounts.json" "$work/baseline-mounts.json" <<'PY'
import json, sys
mounts = json.load(open(sys.argv[1]))
targets = {'/app/api/main.py', '/app/ui/app.js'}
with open(sys.argv[2], 'w') as stream:
    json.dump([mount for mount in mounts if mount.get('Destination') not in targets], stream)
PY
python3 "$stage/check_compose.py" "$work/before.json" "$work/after.json" "$work/baseline-mounts.json" "$stage"
python3 "$work/check_post_deploy.py" "$work/baseline-mounts.json" "$work/current-mounts.json" "$stage"
image_ref=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["services"]["voicepipeline"]["image"])' "$work/before.json")
docker inspect "$live" > "$work/container-before.json"
docker image inspect "$image_ref" > "$work/image.json"
python3 "$work/check_runtime.py" "$work/before.json" "$work/container-before.json" "$work/image.json"
python3 - "$work/container-before.json" <<'PY'
import json, sys
container = json.load(open(sys.argv[1]))[0]
bindings = (container['HostConfig'].get('PortBindings') or {}).get('8000/tcp') or []
if not any(str(b.get('HostPort')) == '8000' and (b.get('HostIp') or '') in ('', '0.0.0.0', '127.0.0.1') for b in bindings):
    raise SystemExit('Cannot check the management API on localhost:8000; stopping.')
PY

started=1
compose_old up -d --no-deps --no-build --pull never --force-recreate voicepipeline
[ "$(docker inspect "$live" --format '{{.State.Running}}')" = true ]
[ "$(docker inspect "$live" --format '{{.Image}}')" = "$expected_image" ]
[ "$(file_sha /app/api/main.py)" = 83b8285bc91b451fcf1e1b80db141cf9d3f1620026186d7f511f128066e8c386 ]
[ "$(file_sha /app/ui/app.js)" = e4156a695b1c6a20e8a1700a565b3070918174fd805d1fd9aeb87cb1066d7be1 ]
[ "$(file_sha /app/pipeline/models/speaker_id.py)" = fb5c6f04121e61a4ae1e7d84cc8615c22eaa032aaa58154bf324952f98c9640f ]
docker inspect "$live" --format '{{json .Mounts}}' > "$work/restored-mounts.json"
python3 "$stage/check_compose.py" "$work/before.json" "$work/after.json" "$work/restored-mounts.json" "$stage"
docker inspect "$live" > "$work/container-after.json"
python3 "$work/check_runtime.py" "$work/before.json" "$work/container-after.json" "$work/image.json"
tries=0
ready=0
while [ "$tries" -lt 30 ]; do
  if curl -fsS --max-time 1 http://127.0.0.1:8000/api/v1/speakers >/dev/null 2>&1; then ready=1; break; fi
  [ "$(docker inspect "$live" --format '{{.State.Running}}')" = true ] || break
  tries=$((tries + 1))
  sleep 1
done
[ "$ready" -eq 1 ] || { echo 'Management API did not become ready in time.' >&2; exit 1; }
started=0
echo 'Original app restored. Voice data, speaker patch and thresholds were not restored or changed.'
echo 'Verify speech before normal use. Do not use the history-correction Compose wrapper after rollback.'
