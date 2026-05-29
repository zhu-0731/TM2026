#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OUTPUT_DIR="$PROJECT_ROOT/data/datasets/online_boutique_short_fault_v1"
QUALITY_REL="data/datasets/online_boutique_short_fault_v1/processed/quality_report.json"

cd "$PROJECT_ROOT"

echo "=== Online Boutique AIOps Benchmark - Smoke Export ==="
echo "Project root: $PROJECT_ROOT"

# Find a working Python (prefer 'python' over 'python3' to avoid Windows App Store stubs)
PYTHON=""
for candidate in python python3; do
    if command -v "$candidate" &>/dev/null; then
        if PY_VERSION=$("$candidate" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null); then
            PYTHON="$candidate"
            break
        fi
    fi
done
if [ -z "$PYTHON" ]; then
    echo "ERROR: No working Python found. Please install Python 3.10+" >&2
    exit 1
fi
echo "Python: $(command -v $PYTHON) ($PY_VERSION)"

# Install dependencies
echo "Installing dependencies..."
"$PYTHON" -m pip install -q -r requirements.txt

# Clean old output
if [ -d "$OUTPUT_DIR" ]; then
    echo "Cleaning old output: $OUTPUT_DIR"
    rm -rf "$OUTPUT_DIR"
fi

# Run smoke export
echo "Running smoke export (10 min, 5s step)..."
"$PYTHON" -m benchmark.cli smoke \
    --output "$OUTPUT_DIR" \
    --duration-minutes 10 \
    --step-seconds 5

echo ""
echo "=== Output Directory: $OUTPUT_DIR ==="

# Print key file line counts (POSIX paths work for wc -l in bash)
PROC="$OUTPUT_DIR/processed"
ANS="$OUTPUT_DIR/answers"
EX="$OUTPUT_DIR/examples"

echo ""
echo "--- File line counts (header + data rows) ---"
for f in \
    "$PROC/train_x.csv" \
    "$PROC/valid_x.csv" \
    "$PROC/test_x.csv" \
    "$PROC/train_y.csv" \
    "$PROC/valid_y.csv" \
    "$PROC/test_y.csv" \
    "$PROC/incidents.csv" \
    "$PROC/feature_schema.csv" \
    "$PROC/metrics_5s.csv" \
    "$ANS/test_ground_truth.csv" \
    "$ANS/test_incident_ground_truth.csv" \
    "$ANS/test_root_cause_ground_truth.csv" \
    "$EX/sample_submission.csv" \
    "$OUTPUT_DIR/dataset_meta.json"
do
    if [ -f "$f" ]; then
        lines=$(wc -l < "$f")
        echo "  $(basename "$f"): $lines lines"
    else
        echo "  MISSING: $f" >&2
    fi
done

# Quality check (use relative path so Windows Python can resolve it)
echo ""
echo "--- Quality Report ---"
if [ ! -f "$PROC/quality_report.json" ]; then
    echo "ERROR: quality_report.json not found" >&2
    exit 1
fi

PASSED=$("$PYTHON" -c "import json; d=json.load(open('$QUALITY_REL')); print(d['passed'])")
"$PYTHON" -c "
import json
d = json.load(open('$QUALITY_REL'))
for k, v in d.items():
    print(f'  {k}: {v}')
"

echo ""
if [ "$PASSED" = "True" ]; then
    echo "============================="
    echo "         SUCCESS             "
    echo "============================="
else
    echo "ERROR: Quality checks FAILED (passed=false). See quality_report.json" >&2
    exit 1
fi
