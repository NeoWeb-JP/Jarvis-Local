#!/bin/sh
# Install only into the existing disposable isolated container. Never recreate it.
set -eu
umask 077
live=voicepipeline
test_container=voicepipeline-isolated-test
test_root=/opt/voicepipeline-isolated-test
revision=e71c2d7e11800152ecefb67f327f4d589dfea9a0
base="https://raw.githubusercontent.com/NeoWeb-JP/Jarvis-Local/$revision/deployment/voice-bridge/experiments/history-correction"
backup=''
work=''
changed=0

mount_source() {
  docker inspect "$1" --format "{{range .Mounts}}{{if eq .Destination \"$2\"}}{{.Source}}{{end}}{{end}}"
}
cleanup() {
  rc=$?
  trap - EXIT
  if [ "$rc" -ne 0 ] && [ "$changed" -eq 1 ]; then
    echo 'Isolated installation failed; attempting to restore the two original files.' >&2
    docker cp "$backup/api.py" "$test_container:/app/api/main.py" || echo 'Could not restore API file.' >&2
    docker cp "$backup/ui.js" "$test_container:/app/ui/app.js" || echo 'Could not restore UI file.' >&2
    if [ "$(docker inspect "$test_container" --format '{{.State.Running}}' 2>/dev/null || true)" = true ]; then
      docker restart "$test_container" >/dev/null || echo 'Could not restart the test container.' >&2
    else
      docker start "$test_container" >/dev/null || echo 'Could not start the test container.' >&2
    fi
    echo "Inspect the isolated container before retrying. Backup: $backup" >&2
  fi
  [ -z "$work" ] || rm -rf -- "$work"
  exit "$rc"
}
trap cleanup EXIT

expected_image='sha256:aefd844361f6816721a5497d25eefbfdf670e33df81c0e16dde533f68e510a55'
[ "$(docker inspect "$test_container" --format '{{.State.Running}}')" = true ]
[ "$(docker inspect "$test_container" --format '{{.Image}}')" = "$expected_image" ]
[ "$(readlink -f "$(mount_source "$live" /data)")" = /opt/voicepipeline/data ]
[ "$(readlink -f "$(mount_source "$live" /models)")" = /opt/voicepipeline/models ]
[ "$(readlink -f "$(mount_source "$test_container" /data)")" = "$test_root/data" ]
[ "$(readlink -f "$(mount_source "$test_container" /models)")" = "$test_root/models" ]

# These files must be in the isolated container's writable layer, not a host bind.
destinations=$(docker inspect "$test_container" --format '{{range .Mounts}}{{println .Destination}}{{end}}')
while IFS= read -r dest; do
  case "$dest" in
    /|/app|/app/api|/app/api/main.py|/app/ui|/app/ui/app.js)
      echo "Refusing test installation: unexpected mount $dest" >&2; exit 1;;
  esac
done <<EOF
$destinations
EOF

docker exec "$test_container" python -c '
import os, sqlite3
for path in ("/app/api/main.py", "/app/ui/app.js"):
    if not os.path.isfile(path) or os.path.islink(path):
        raise SystemExit("Expected a regular, non-symlink source file: " + path)
db = sqlite3.connect("file:/data/speaker.db?mode=ro", uri=True)
row = db.execute("SELECT value FROM settings WHERE key=?", ("ha_webhook_enabled",)).fetchone()
db.close()
values = [str(row[0]).strip().lower() if row else "false", os.getenv("HA_WEBHOOK_ENABLED", "false").strip().lower()]
if any(value not in ("false", "0", "off", "") for value in values):
    raise SystemExit("Test webhook may be enabled; stopping.")
'

test_api=$(docker exec "$test_container" sha256sum /app/api/main.py | awk '{print $1}')
test_ui=$(docker exec "$test_container" sha256sum /app/ui/app.js | awk '{print $1}')
[ "$test_api" = 83b8285bc91b451fcf1e1b80db141cf9d3f1620026186d7f511f128066e8c386 ]
[ "$test_ui" = e4156a695b1c6a20e8a1700a565b3070918174fd805d1fd9aeb87cb1066d7be1 ]

work=$(mktemp -d /tmp/jarvis-correction.XXXXXX)
curl -fsS "$base/api.py" -o "$work/api.py"
curl -fsS "$base/ui.js" -o "$work/ui.js"
printf '%s\n' \
  "c091056b85fdddd484111424969b80e784e030c44b184e9f384d36269db128b6  $work/api.py" \
  "0da39a86f952369c7438ad774f2d4dabea700cf252fd88a3c3330f953fd8a8e4  $work/ui.js" | sha256sum -c -

backup=$(mktemp -d "$test_root/history-correction-backup.XXXXXX")
docker cp "$test_container:/app/api/main.py" "$backup/api.py"
docker cp "$test_container:/app/ui/app.js" "$backup/ui.js"
docker exec -i "$test_container" python - > "$backup/speaker.db" <<'PY'
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
echo "Isolated backup: $backup"

changed=1
docker stop "$test_container" >/dev/null
docker cp "$work/api.py" "$test_container:/app/api/main.py"
docker cp "$work/ui.js" "$test_container:/app/ui/app.js"
docker start "$test_container" >/dev/null
new_api=$(docker exec "$test_container" sha256sum /app/api/main.py | awk '{print $1}')
new_ui=$(docker exec "$test_container" sha256sum /app/ui/app.js | awk '{print $1}')
[ "$new_api" = c091056b85fdddd484111424969b80e784e030c44b184e9f384d36269db128b6 ]
[ "$new_ui" = 0da39a86f952369c7438ad774f2d4dabea700cf252fd88a3c3330f953fd8a8e4 ]
changed=0
echo 'History correction candidate installed in the isolated container.'
echo 'Production was not changed or restarted.'
