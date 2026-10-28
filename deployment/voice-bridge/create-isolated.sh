#!/bin/sh
# Create a separate test copy. Does not stop or overwrite the live installation.
set -eu
live=voicepipeline
test_container=voicepipeline-isolated-test
test_dir=${1:-/opt/voicepipeline-isolated-test}
expected_image='sha256:aefd844361f6816721a5497d25eefbfdf670e33df81c0e16dde533f68e510a55'
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
[ ! -e "$test_dir" ] || { echo 'Test directory already exists; refusing to overwrite.' >&2; exit 1; }
if docker inspect "$test_container" >/dev/null 2>&1; then echo 'Test container already exists; refusing to overwrite.' >&2; exit 1; fi
[ "$(docker inspect "$live" --format '{{.Image}}')" = "$expected_image" ] || { echo 'Unexpected live image; no changes made.' >&2; exit 2; }
sh "$script_dir/verify-candidate.sh" "$live" || { echo 'Live patch differs from candidate; no changes made.' >&2; exit 2; }
mount_source() { docker inspect "$live" --format "{{range .Mounts}}{{if eq .Destination \"$1\"}}{{.Source}}{{end}}{{end}}"; }
data_dir=$(mount_source /data)
models_dir=$(mount_source /models)
[ -d "$data_dir" ] && [ -d "$models_dir" ] || { echo 'Data or model bind mount missing; no changes made.' >&2; exit 2; }
[ -f "$data_dir/speaker.db" ] || { echo 'speaker.db missing; no changes made.' >&2; exit 2; }
case "$test_dir" in /*) ;; *) echo 'Use an absolute test directory path.' >&2; exit 2;; esac
case "$test_dir" in *:*|*'$'*|*'"'*) echo 'Unsupported test directory path.' >&2; exit 2;; esac
test_parent=$(CDPATH= cd -- "$(dirname -- "$test_dir")" && pwd -P)
data_real=$(CDPATH= cd -- "$data_dir" && pwd -P)
models_real=$(CDPATH= cd -- "$models_dir" && pwd -P)
for source in "$data_real" "$models_real"; do
  case "$test_parent/" in "$source/"*) echo 'Test directory cannot be inside live data or models.' >&2; exit 2;; esac
done
mkdir -m 700 -- "$test_dir"
mkdir -- "$test_dir/data" "$test_dir/models"
printf '%s\n' 'Copying recorded data and models. The copy may omit clips created during this operation.'
cp -a -- "$data_dir/." "$test_dir/data/"
cp -a -- "$models_dir/." "$test_dir/models/"
cp -- "$script_dir/voicepipeline/wyoming_server.py" "$test_dir/wyoming_server.py"
cp -- "$script_dir/voicepipeline/speaker_id.py" "$test_dir/speaker_id.py"
# Take a consistent SQLite snapshot through the live container. Only the copied
# database is changed; disable its webhook before writing to the test directory.
docker exec -i "$live" python - > "$test_dir/data/speaker.db.snapshot" <<'PY'
import os, shutil, sqlite3, sys, tempfile
fd, path = tempfile.mkstemp(suffix='.db')
os.close(fd)
try:
    source = sqlite3.connect('file:/data/speaker.db?mode=ro', uri=True)
    destination = sqlite3.connect(path)
    source.backup(destination)
    destination.execute('UPDATE settings SET value = ? WHERE key = ?', ('false', 'ha_webhook_enabled'))
    destination.commit()
    destination.close()
    source.close()
    with open(path, 'rb') as stream:
        shutil.copyfileobj(stream, sys.stdout.buffer)
finally:
    os.unlink(path)
PY
rm -f -- "$test_dir/data/speaker.db-wal" "$test_dir/data/speaker.db-shm"
mv -- "$test_dir/data/speaker.db.snapshot" "$test_dir/data/speaker.db"
docker run -d --name "$test_container" --pull never \
  -p 10301:10300 -p 8001:8000 \
  -v "$test_dir/data:/data" -v "$test_dir/models:/models" \
  -v "$test_dir/wyoming_server.py:/app/pipeline/wyoming_server.py:ro" \
  -v "$test_dir/speaker_id.py:/app/pipeline/models/speaker_id.py:ro" \
  "$expected_image"
printf '%s\n' 'Test container created. Inspect its logs and run check-isolation.sh before using it.'
printf '%s\n' 'If setup failed, the new directory is retained for inspection; the live container was not changed.'
