#!/bin/sh
# Install the tested-domain bridge from this package, preserving the existing entry.
set -eu
config_dir=${1:-/config}
source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/custom_components/jarvis_voice_bridge
components="$config_dir/custom_components"
target="$components/jarvis_voice_bridge"
backups="$config_dir/jarvis_voice_bridge_backups"
[ -d "$target" ] && [ -d "$source_dir" ] || { echo 'Existing bridge or candidate not found; nothing changed.' >&2; exit 1; }
[ ! -L "$target" ] || { echo 'Bridge directory is a symlink; manual review required.' >&2; exit 1; }
# A second run is a no-op when the installed candidate is already exact.
if (cd "$target" && sha256sum -c - >/dev/null 2>&1 <<'EOF'
0e06a83ba083389a642feeb8be48f6b42f4794f194decfd430580d0faffd942f  __init__.py
45cb8ffb1495e32ed9a8469ac076989dcafc214ab2a17a408124d86c26a66d57  config_flow.py
f21c8620c2914d05a34117c35e518b8733e43a0ee76f37d8bd3c3c6bc2db2a85  conversation.py
1e8c374d23f22eced55ac09b83b2d584c8f0303fe0df4d096b1191a5fce2ef39  manifest.json
55940b9c03d0884ab17fa3623d1a8c0a7b75e7888be3d62d153d8c3bb7029070  models.py
80c07b194cc9eec16da676fc8a7083d535928417e0269757c25db0438d813d95  stt.py
f8b139382cbca76e2e789328f2002cb536abcf0bb9aed2a83ad6c1cba7312ffd  strings.json
EOF
); then
    echo 'Jarvis Voice Bridge 0.2.0 is already installed; nothing changed.'
    exit 0
fi
# Only the original bridge version can be upgraded automatically. Do not overwrite edits.
(cd "$target" && sha256sum -c - >/dev/null <<'EOF'
0e06a83ba083389a642feeb8be48f6b42f4794f194decfd430580d0faffd942f  __init__.py
566807c9046e64671fda33fd7fb08bd4d3233babd76fca02f627f2ca7a5c0cbd  config_flow.py
f21c8620c2914d05a34117c35e518b8733e43a0ee76f37d8bd3c3c6bc2db2a85  conversation.py
c25e07c49f8d775200dee23776da342345b934e20f5f4f496cb8f5821b4980c5  manifest.json
55940b9c03d0884ab17fa3623d1a8c0a7b75e7888be3d62d153d8c3bb7029070  models.py
0477507a1a3a02c46b6679e0037bcb7b423866801e05e26becf16132510ca853  stt.py
e08c1a4b1941f268803c719f616d046f4e6e97c152765a65862faf4256fe477c  strings.json
EOF
) || { echo 'Existing bridge differs from verified version; nothing changed.' >&2; exit 2; }
(cd "$source_dir" && sha256sum -c - >/dev/null <<'EOF'
0e06a83ba083389a642feeb8be48f6b42f4794f194decfd430580d0faffd942f  __init__.py
45cb8ffb1495e32ed9a8469ac076989dcafc214ab2a17a408124d86c26a66d57  config_flow.py
f21c8620c2914d05a34117c35e518b8733e43a0ee76f37d8bd3c3c6bc2db2a85  conversation.py
1e8c374d23f22eced55ac09b83b2d584c8f0303fe0df4d096b1191a5fce2ef39  manifest.json
55940b9c03d0884ab17fa3623d1a8c0a7b75e7888be3d62d153d8c3bb7029070  models.py
80c07b194cc9eec16da676fc8a7083d535928417e0269757c25db0438d813d95  stt.py
f8b139382cbca76e2e789328f2002cb536abcf0bb9aed2a83ad6c1cba7312ffd  strings.json
EOF
) || { echo 'Candidate checksum mismatch; nothing changed.' >&2; exit 2; }
mkdir -p -m 700 -- "$backups"
backup=$(mktemp -d "$backups/bridge.XXXXXXXX")
chmod 700 "$backup"
cp -a -- "$target/." "$backup/"
staging=$(mktemp -d "$components/.jarvis-bridge.XXXXXXXX")
cp -a -- "$source_dir/." "$staging/"
# Existing runtime objects remain in memory until Home Assistant restarts.
old="$components/.jarvis-bridge-old.$$"
[ ! -e "$old" ] || { echo "Temporary path exists. Backup: $backup" >&2; exit 1; }
mv -- "$target" "$old"
if ! mv -- "$staging" "$target"; then
    mv -- "$old" "$target"
    echo "Install failed; previous bridge restored. Backup: $backup" >&2
    exit 1
fi
rm -rf -- "$old"
echo "Bridge files installed. Backup: $backup"
echo 'Restart Home Assistant, then verify the existing pipeline and entity IDs.'
echo 'Existing registry names may still contain Test; rename their display names in Home Assistant if desired.'
