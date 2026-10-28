#!/bin/sh
# Read-only: compare live and test container mounts, image and webhook settings.
set -eu
live=${1:-voicepipeline}
test_container=${2:-voicepipeline-isolated-test}
[ "$live" != "$test_container" ] || { echo 'Live and test containers must differ.' >&2; exit 1; }
for c in "$live" "$test_container"; do
  docker inspect "$c" >/dev/null
  docker inspect "$c" --format 'Container {{.Name}} | state={{.State.Status}} | image={{.Image}}'
done
for destination in /data /models; do
  live_source=$(docker inspect "$live" --format "{{range .Mounts}}{{if eq .Destination \"$destination\"}}{{.Source}}{{end}}{{end}}")
  test_source=$(docker inspect "$test_container" --format "{{range .Mounts}}{{if eq .Destination \"$destination\"}}{{.Source}}{{end}}{{end}}")
  [ -n "$live_source" ] && [ -n "$test_source" ] || { echo "Missing $destination mount; isolation is not verified." >&2; exit 2; }
  [ "$live_source" != "$test_source" ] || { echo "Shared $destination mount; isolation is not verified." >&2; exit 2; }
  # Distinct bind mount strings can still point at the same directory through symlinks.
  live_real=$(readlink -f -- "$live_source")
  test_real=$(readlink -f -- "$test_source")
  [ -n "$live_real" ] && [ -n "$test_real" ] && [ "$live_real" != "$test_real" ] || { echo "Shared or unresolved $destination path." >&2; exit 2; }
  case "$live_real/" in "$test_real/"*) echo "Nested $destination paths are not isolated." >&2; exit 2;; esac
  case "$test_real/" in "$live_real/"*) echo "Nested $destination paths are not isolated." >&2; exit 2;; esac
  printf '%s\n' "$destination: distinct paths ($live_real and $test_real)"
done
echo 'Checking the test database webhook flag and environment flag (values only):'
docker exec "$test_container" python -c '
import os, sqlite3
conn=sqlite3.connect("file:/data/speaker.db?mode=ro", uri=True)
row=conn.execute("SELECT value FROM settings WHERE key = ?", ("ha_webhook_enabled",)).fetchone()
conn.close()
db=str(row[0]).strip().lower() if row else "false"
env=os.getenv("HA_WEBHOOK_ENABLED", "false").strip().lower()
print("webhook in database:", db, "| environment:", env)
if db == "true" or env == "true": raise SystemExit("Webhook may be enabled; review before testing.")
'
echo 'Mount paths and webhook flags checked. This does not verify audio isolation or speaker accuracy.'
