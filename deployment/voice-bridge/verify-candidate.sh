#!/bin/sh
# Check candidate overlays against active container without changing the deployment.
set -eu
container=${1:-voicepipeline}
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
command -v docker >/dev/null 2>&1 || { echo 'Docker is required.' >&2; exit 1; }
command -v sha256sum >/dev/null 2>&1 || { echo 'sha256sum is required.' >&2; exit 1; }
docker inspect "$container" >/dev/null
printf '%s\n' 'Running container and immutable image ID:'
docker inspect "$container" --format '{{.Name}} {{.Image}} {{.State.Status}}'
printf '%s\n' 'Persistent and source mounts:'
docker inspect "$container" --format '{{range .Mounts}}{{if or (eq .Destination "/app/pipeline/wyoming_server.py") (eq .Destination "/app/pipeline/models/speaker_id.py") (eq .Destination "/data") (eq .Destination "/models")}}{{println .Destination "<-" .Source}}{{end}}{{end}}'
status=0
for spec in 'wyoming_server.py:/app/pipeline/wyoming_server.py' 'speaker_id.py:/app/pipeline/models/speaker_id.py'; do
    filename=${spec%%:*}
    target=${spec#*:}
    candidate=$(sha256sum "$script_dir/voicepipeline/$filename" | cut -d ' ' -f 1)
    active=$(docker exec "$container" sha256sum "$target" | cut -d ' ' -f 1)
    printf '%s\n' "$target" "  active:    $active" "  candidate: $candidate"
    if [ "$active" != "$candidate" ]; then
        echo '  DIFFERENT: review before any migration.'
        status=1
    else
        echo '  MATCH: active source matches candidate.'
    fi
done
if [ "$status" -ne 0 ]; then
    echo 'No files or containers were changed. A source difference is not proof of incompatibility.'
    exit 2
fi
echo 'Source files match. This does not test identity transport or prove upgrades are compatible.'
