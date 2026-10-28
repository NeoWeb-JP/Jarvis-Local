#!/bin/sh
# Read-only deployment inventory; run on the VoicePipeline host.
set -eu
container="${1:-voicepipeline}"
command -v docker >/dev/null 2>&1 || { echo 'Docker not found'; exit 1; }
docker inspect "$container" --format 'Container: {{.Name}} | Image: {{.Config.Image}} | Status: {{.State.Status}}'
echo 'VoicePipeline overrides and persistent mounts:'
docker inspect "$container" --format '{{range .Mounts}}{{if or (eq .Destination "/app/pipeline/wyoming_server.py") (eq .Destination "/app/pipeline/models/speaker_id.py") (eq .Destination "/data") (eq .Destination "/models")}}{{println .Destination "<-" .Source}}{{end}}{{end}}'
echo 'Active source checksums:'
docker exec "$container" sha256sum /app/pipeline/wyoming_server.py /app/pipeline/models/speaker_id.py
echo 'Container state only; transcription and identity require an end-to-end test.'
