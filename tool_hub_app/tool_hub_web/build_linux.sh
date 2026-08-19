#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$SCRIPT_DIR"
cmake -S cpp -B build/outdoor-pcd-to-pgm
cmake --build build/outdoor-pcd-to-pgm -j"$(nproc)"
mkdir -p bin
cp build/outdoor-pcd-to-pgm/outdoor_pcd_to_pgm bin/outdoor_pcd_to_pgm
cmake -S cpp -B build/pcd-chunker
cmake --build build/pcd-chunker -j"$(nproc)"
cp build/pcd-chunker/pcd_chunker bin/pcd_chunker
python3 -m PyInstaller --noconfirm tool_hub.spec
