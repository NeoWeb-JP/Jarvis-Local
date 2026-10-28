#!/bin/sh
# Prepare isolated, reviewable files only. Never touches the running container.
set -eu
container=${1:-voicepipeline}
output=${2:-./jarvis-voice-stage}
expected_image='sha256:aefd844361f6816721a5497d25eefbfdf670e33df81c0e16dde533f68e510a55'
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
case "$output" in *'
'*|*'"'*|*':'*|*'$'*) echo 'Unsupported output path.' >&2; exit 1;; esac
[ ! -e "$output" ] || { echo 'Output path already exists; refusing to overwrite it.' >&2; exit 1; }
actual_image=$(docker inspect "$container" --format '{{.Image}}')
[ "$actual_image" = "$expected_image" ] || { echo 'Image differs from the verified version. Nothing staged.' >&2; exit 2; }
sh "$script_dir/verify-candidate.sh" "$container" || { echo 'Source files differ. Nothing staged.' >&2; exit 2; }
mkdir -m 700 -- "$output"
out_abs=$(CDPATH= cd -- "$output" && pwd)
cp -- "$script_dir/voicepipeline/wyoming_server.py" "$out_abs/wyoming_server.py"
cp -- "$script_dir/voicepipeline/speaker_id.py" "$out_abs/speaker_id.py"
cat > "$out_abs/compose.jarvis-stage.yaml" <<EOF
# Review before use. Do not apply alongside other overrides mounting these paths.
services:
  voicepipeline:
    volumes:
      - "$out_abs/wyoming_server.py:/app/pipeline/wyoming_server.py:ro"
      - "$out_abs/speaker_id.py:/app/pipeline/models/speaker_id.py:ro"
EOF
cat > "$out_abs/IMAGE-ID.txt" <<EOF
$expected_image
EOF
printf 'Prepared candidate at %s\n' "$out_abs"
echo 'No container was stopped, started, or modified. Do not apply without reviewing the full compose configuration.'
