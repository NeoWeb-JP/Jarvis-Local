#!/bin/sh
# Apply the tested correction through Compose. Preserve data, image and overlays.
set -eu
umask 077
root=/opt/voicepipeline
live=voicepipeline
stage=${1:?Usage: deploy-production.sh /opt/voicepipeline/history-correction-stage.XXXXXX}
case "$stage" in "$root"/history-correction-stage.*) ;; *) echo 'Unexpected staging path.' >&2; exit 1;; esac
[ "$(readlink -f "$stage")" = "$stage" ] || { echo 'Staging path must be a real directory.' >&2; exit 1; }
revision=5e52060f9d5a29319ba35bc09aebbcfda69ba250
base="https://raw.githubusercontent.com/NeoWeb-JP/Jarvis-Local/$revision/deployment/voice-bridge/experiments/history-correction"
expected_image='sha256:aefd844361f6816721a5497d25eefbfdf670e33df81c0e16dde533f68e510a55'
expected_files="$root/compose.yaml,$root/compose.override.yaml,$root/compose.bridge-test.yaml,$root/compose.cache-test.yaml"
work=''
backup=''
image_ref=''
started=0

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
cleanup() {
  rc=$?
  trap - EXIT
  if [ "$rc" -ne 0 ] && [ "$started" -eq 1 ]; then
    echo 'Deployment failed; checking whether the original Compose configuration can be restored.' >&2
    writable_safe=1
    if docker inspect "$live" >/dev/null 2>&1; then
      if ! docker diff "$live" > "$work/rollback-diff.txt" || \
         ! python3 "$work/check_writable_diff.py" "$work/rollback-diff.txt" >/dev/null 2>&1; then
        writable_safe=0
      fi
    fi
    if [ "$writable_safe" -eq 1 ] && sha256sum -c "$stage/source-checksums.txt" >/dev/null 2>&1 && \
       [ "$(docker image inspect "$image_ref" --format '{{.Id}}' 2>/dev/null || true)" = "$expected_image" ] && \
       compose_old config --format json > "$work/rollback-model.json" 2>/dev/null && \
       python3 -c 'import json,sys; a=json.load(open(sys.argv[1])); b=json.load(open(sys.argv[2])); sys.exit(0 if a==b else 1)' "$work/before.json" "$work/rollback-model.json"; then
      if compose_old up -d --no-deps --no-build --pull never --force-recreate voicepipeline; then
        echo 'Original Compose configuration recreated. Verify voice service before use.' >&2
      else
        echo 'Automatic rollback failed. Inspect the container and backup before retrying.' >&2
      fi
    else
      echo 'Configuration, image or writable-layer state needs review; automatic rollback was not attempted.' >&2
    fi
    echo "Backup: $backup. Do not restore the database snapshot over newer data." >&2
  fi
  [ -z "$work" ] || rm -rf -- "$work"
  exit "$rc"
}
trap cleanup EXIT

[ "$(docker inspect "$live" --format '{{.State.Running}}')" = true ]
[ "$(docker inspect "$live" --format '{{.Image}}')" = "$expected_image" ]
[ "$(docker inspect "$live" --format '{{index .Config.Labels "com.docker.compose.project"}}')" = voicepipeline ]
[ "$(docker inspect "$live" --format '{{index .Config.Labels "com.docker.compose.service"}}')" = voicepipeline ]
[ "$(docker inspect "$live" --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}')" = "$root" ]
[ "$(docker inspect "$live" --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}')" = "$expected_files" ]
sha256sum -c "$stage/source-checksums.txt"
file_sha() { docker exec "$live" sha256sum "$1" | awk '{print $1}'; }
[ "$(file_sha /app/api/main.py)" = 83b8285bc91b451fcf1e1b80db141cf9d3f1620026186d7f511f128066e8c386 ]
[ "$(file_sha /app/ui/app.js)" = e4156a695b1c6a20e8a1700a565b3070918174fd805d1fd9aeb87cb1066d7be1 ]
[ "$(file_sha /app/pipeline/models/speaker_id.py)" = fb5c6f04121e61a4ae1e7d84cc8615c22eaa032aaa58154bf324952f98c9640f ]

work=$(mktemp -d "$stage/private.deploy.XXXXXX")
curl -fsS "$base/check_runtime.py" -o "$work/check_runtime.py"
curl -fsS "$base/check_post_deploy.py" -o "$work/check_post_deploy.py"
diff_url='https://raw.githubusercontent.com/NeoWeb-JP/Jarvis-Local/79b1fdd9edd3a373680904beaf3b1aa2cb47c96c/deployment/voice-bridge/experiments/history-correction/check_writable_diff.py'
curl -fsS "$diff_url" -o "$work/check_writable_diff.py"
printf '%s\n' \
 "51c8efba255b251d6bace8a7f2845574a4535e030e23ecaa46eed9c2ed8c0398  $work/check_runtime.py" \
 "61d07eacfe5b66ca1dfd2f202a7fb4157541f1241e0d493c1f3e700b5782d249  $work/check_post_deploy.py" \
 "c016e23df627c06770c8eded65b1935f38cae571da46ab7173365cfaed19fea7  $work/check_writable_diff.py" | sha256sum -c -
docker diff "$live" > "$work/diff-raw.txt"
python3 "$work/check_writable_diff.py" "$work/diff-raw.txt"

cd "$root"
compose_old config --format json > "$work/before.json"
compose_new config --format json > "$work/after.json"
docker inspect "$live" --format '{{json .Mounts}}' > "$work/before-mounts.json"
python3 "$stage/check_compose.py" "$work/before.json" "$work/after.json" "$work/before-mounts.json" "$stage"
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

backup=$(mktemp -d "$stage/before-deploy.XXXXXX")
docker cp "$live:/app/api/main.py" "$backup/api.py"
docker cp "$live:/app/ui/app.js" "$backup/ui.js"
cp "$work/before-mounts.json" "$backup/mounts.json"
for name in compose.yaml compose.override.yaml compose.bridge-test.yaml compose.cache-test.yaml; do cp -p "$root/$name" "$backup/$name"; done
if [ -f "$root/.env" ]; then cp -p "$root/.env" "$backup/.env"; fi
docker exec -i "$live" python - > "$backup/speaker.db" <<'PY'
import os, shutil, sqlite3, sys, tempfile
fd, path = tempfile.mkstemp(suffix='.db')
os.close(fd)
try:
    source = sqlite3.connect('file:/data/speaker.db?mode=ro', uri=True)
    target = sqlite3.connect(path)
    source.backup(target)
    target.close()
    source.close()
    with open(path, 'rb') as snapshot:
        shutil.copyfileobj(snapshot, sys.stdout.buffer)
finally:
    os.unlink(path)
PY
python3 - "$backup/speaker.db" <<'PY'
import json, sqlite3, sys
db = sqlite3.connect('file:' + sys.argv[1] + '?mode=ro', uri=True)
try:
    if db.execute('PRAGMA quick_check').fetchone()[0] != 'ok': raise ValueError('Snapshot check failed')
    rows = dict(db.execute('SELECT key, value FROM settings WHERE key IN (?, ?)', ('match_threshold', 'speaker_match_thresholds')))
    if float(rows['match_threshold']) != 0.47 or json.loads(rows['speaker_match_thresholds']) != {'jaco': 0.50, 'ed': 0.47}:
        raise ValueError('Voice threshold settings differ from the verified settings')
finally:
    db.close()
PY
echo "Private pre-deployment backup: $backup"

wrapper=$(mktemp "$stage/compose-with-history.XXXXXX")
cat > "$wrapper" <<EOF
#!/bin/sh
set -eu
cd '$root'
exec docker compose --project-directory '$root' -p voicepipeline \\
  -f '$root/compose.yaml' -f '$root/compose.override.yaml' \\
  -f '$root/compose.bridge-test.yaml' -f '$root/compose.cache-test.yaml' \\
  -f '$stage/compose.history-correction.yaml' "\$@"
EOF
chmod 700 "$wrapper"
echo "Future Compose wrapper: $wrapper"

# Check again immediately before recreation; the writable layer is discarded.
docker diff "$live" > "$work/diff-latest.txt"
python3 "$work/check_writable_diff.py" "$work/diff-latest.txt"
cp "$work/diff-latest.txt" "$backup/container-diff.txt"
if grep -Fxq 'A /root/.cache/huggingface/.agent_harnesses.json' "$work/diff-latest.txt"; then
  docker cp "$live:/root/.cache/huggingface/.agent_harnesses.json" "$backup/huggingface-agent-cache.json"
fi
started=1
compose_new up -d --no-deps --no-build --pull never --force-recreate voicepipeline
[ "$(docker inspect "$live" --format '{{.State.Running}}')" = true ]
[ "$(docker inspect "$live" --format '{{.Image}}')" = "$expected_image" ]
[ "$(file_sha /app/api/main.py)" = 56a085ecf601ba243d908f9acfd19fd175cb4ed5f411b58b50b6893f9c782a47 ]
[ "$(file_sha /app/ui/app.js)" = bd8584122297456d6b7a67112f030ed62a72aae8485b68201ad2dea086e66e87 ]
[ "$(file_sha /app/pipeline/models/speaker_id.py)" = fb5c6f04121e61a4ae1e7d84cc8615c22eaa032aaa58154bf324952f98c9640f ]
docker inspect "$live" --format '{{json .Mounts}}' > "$work/after-mounts.json"
python3 "$work/check_post_deploy.py" "$work/before-mounts.json" "$work/after-mounts.json" "$stage"
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
echo 'Production correction installed; the management API responded.'
echo 'Test speaker recognition and History correction before normal use.'
echo "Use the printed Compose wrapper for future Compose commands so the override is included."
