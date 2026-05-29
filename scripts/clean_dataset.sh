#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OUTPUT_DIR="$PROJECT_ROOT/data/datasets/online_boutique_short_fault_v1"

if [ -d "$OUTPUT_DIR" ]; then
    echo "Removing: $OUTPUT_DIR"
    rm -rf "$OUTPUT_DIR"
    echo "Done."
else
    echo "Nothing to clean: $OUTPUT_DIR does not exist."
fi
