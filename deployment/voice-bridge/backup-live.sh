#!/bin/sh
# Create a private rollback snapshot. Never changes or stops the live service.
set -eu
live=voicepipeline
out=${1:?Provide a new absolute backup directory}
case "$out" in /*) ;; *) echo 'Use an absolute backup path.' >&2; exit 1;; esac
[ ! -e "$out" ] || { echo 'Backup path exists; refusing to overwrite.' >&2; exit 1; }
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
sh "$script_dir/verify-candidate.sh" "$live"
image=$(docker inspect "$live" --format '{{.Image}}')
expected='sha256:aefd844361f6816721a5497d25eefbfdf670e33df81c0e16dde533f68e510a55'
[ "$image" = "$expected" ] || { echo 'Unverified image; no backup created.' >&2; exit 2; }
source_path() { docker inspect "$live" --format "{{range .Mounts}}{{if eq .Destination \"$1\"}}{{.Source}}{{end}}{{end}}"; }
data=$(source_path /data)
models=$(source_path /models)
[ -d "$data" ] && [ -d "$models" ] && [ -f "$data/speaker.db" ] || { echo 'Required mounts or database missing.' >&2; exit 2; }
parent=$(CDPATH= cd -- "$(dirname -- "$out")" && pwd -P)
for source in "$data" "$models"; do
  actual=$(CDPATH= cd -- "$source" && pwd -P)
  case "$parent/" in "$actual/"*) echo 'Backup cannot be inside a live data or model mount.' >&2; exit 2;; esac
done
mkdir -m 700 -- "$out"
mkdir -m 700 -- "$out/data" "$out/models" "$out/compose"
cp -a -- "$data/." "$out/data/"
cp -a -- "$models/." "$out/models/"
cp -- "$script_dir/voicepipeline/wyoming_server.py" "$out/wyoming_server.py"
cp -- "$script_dir/voicepipeline/speaker_id.py" "$out/speaker_id.py"
# Capture only existing known compose files. They may contain credentials.
for file in compose.yaml compose.override.yaml compose.bridge-test.yaml compose.cache-test.yaml; do
  if [ -f "/opt/voicepipeline/$file" ]; then cp -p -- "/opt/voicepipeline/$file" "$out/compose/$file"; fi
done
printf '%s\n' "$image" > "$out/image-id.txt"
docker exec -i "$live" python - > "$out/data/speaker.db.snapshot" <<'PY'
import os, shutil, sqlite3, sys, tempfile
fd,path=tempfile.mkstemp(suffix='.db');os.close(fd)
try:
    source=sqlite3.connect('file:/data/speaker.db?mode=ro',uri=True)
    dest=sqlite3.connect(path);source.backup(dest);dest.close();source.close()
    with open(path,'rb') as stream:shutil.copyfileobj(stream,sys.stdout.buffer)
finally:os.unlink(path)
PY
rm -f -- "$out/data/speaker.db-wal" "$out/data/speaker.db-shm"
mv -- "$out/data/speaker.db.snapshot" "$out/data/speaker.db"
echo 'Snapshot created. Keep it private. Audio files may have changed while copied; this is not a quiesced full backup.'
