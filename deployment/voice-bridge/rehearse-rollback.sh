#!/bin/sh
# Rehearse patch update and rollback ONLY on the isolated test container.
set -eu
live=voicepipeline
trial=voicepipeline-isolated-test
expected_image='sha256:aefd844361f6816721a5497d25eefbfdf670e33df81c0e16dde533f68e510a55'
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
sh "$script_dir/check-isolation.sh" "$live" "$trial"
[ "$(docker inspect "$trial" --format '{{.Image}}')" = "$expected_image" ] || { echo 'Test image differs; rehearsal aborted.' >&2; exit 2; }
[ "$(docker inspect "$trial" --format '{{.State.Running}}')" = true ] || { echo 'Test container is not running.' >&2; exit 2; }
source_path() { docker inspect "$1" --format "{{range .Mounts}}{{if eq .Destination \"$2\"}}{{.Source}}{{end}}{{end}}"; }
source_live=$(source_path "$live" /app/pipeline/wyoming_server.py)
source_test=$(source_path "$trial" /app/pipeline/wyoming_server.py)
[ -f "$source_live" ] && [ -f "$source_test" ] || { echo 'Expected source mounts missing.' >&2; exit 2; }
source_live=$(readlink -f -- "$source_live")
source_test=$(readlink -f -- "$source_test")
[ "$source_live" != "$source_test" ] || { echo 'Test and production share the patch source; aborted.' >&2; exit 2; }
expected=$(sha256sum "$script_dir/voicepipeline/wyoming_server.py" | cut -d ' ' -f 1)
original=$(sha256sum "$source_test" | cut -d ' ' -f 1)
[ "$original" = "$expected" ] || { echo 'Test source differs from candidate; aborted.' >&2; exit 2; }
backup_dir=$(mktemp -d "${TMPDIR:-/tmp}/jarvis-rollback.XXXXXXXX")
chmod 700 "$backup_dir"
cp -p -- "$source_test" "$backup_dir/wyoming_server.py"
restore_needed=0
restore() {
  if [ "$restore_needed" = 1 ]; then
    echo 'Restoring the isolated test source.' >&2
    if docker stop "$trial" >/dev/null; then
      cp -- "$backup_dir/wyoming_server.py" "$source_test"
      docker start "$trial" >/dev/null
      restore_needed=0
    else
      echo "Could not stop test container. Original patch saved at $backup_dir/wyoming_server.py" >&2
      return 1
    fi
  fi
}
trap 'restore' EXIT
trap 'exit 1' HUP INT TERM
# A harmless comment represents a new overlay, allowing byte-level rollback to be tested.
docker stop "$trial" >/dev/null
restore_needed=1
printf '\n# Jarvis isolated rollback rehearsal\n' >> "$source_test"
docker start "$trial" >/dev/null
updated=$(docker exec "$trial" sha256sum /app/pipeline/wyoming_server.py | cut -d ' ' -f 1)
[ "$updated" != "$original" ] || { echo 'Test overlay did not change; aborting.' >&2; exit 2; }
restore
restored=$(docker exec "$trial" sha256sum /app/pipeline/wyoming_server.py | cut -d ' ' -f 1)
[ "$restored" = "$original" ] || { echo "Restored checksum does not match; backup is at $backup_dir/wyoming_server.py" >&2; exit 2; }
echo "Patch checksum restored. The isolated container was restarted twice; production was not restarted. Backup: $backup_dir"
echo 'Check the test container logs and run an end-to-end speech test before using it.'
