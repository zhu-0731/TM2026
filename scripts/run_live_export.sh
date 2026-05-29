#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OUTPUT_DIR="$PROJECT_ROOT/data/datasets/online_boutique_short_fault_v1"

PROM_URL="http://localhost:9090"
LOOKBACK=10

while [[ $# -gt 0 ]]; do
    case "$1" in
        --prometheus-url) PROM_URL="$2"; shift 2 ;;
        --lookback-minutes) LOOKBACK="$2"; shift 2 ;;
        --output) OUTPUT_DIR="$2"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

cd "$PROJECT_ROOT"

echo "=== Online Boutique AIOps Benchmark - Live Export ==="
echo "Prometheus URL: $PROM_URL"
echo "Lookback: ${LOOKBACK}min"
echo ""
echo "NOTE: This mode collects cpu_usage, memory_usage, restart_count via cAdvisor/kube-state-metrics."
echo "      qps, latency_p95, error_rate require Istio — will be reported as missing features."
echo ""

# Find working Python
PYTHON=""
for candidate in python python3; do
    if command -v "$candidate" &>/dev/null; then
        if "$candidate" -c "import sys; assert sys.version_info >= (3,10)" 2>/dev/null; then
            PYTHON="$candidate"
            break
        fi
    fi
done
if [ -z "$PYTHON" ]; then
    echo "ERROR: Python 3.10+ not found." >&2
    exit 1
fi

# Check Prometheus reachability
if ! "$PYTHON" -c "
import urllib.request, sys
try:
    urllib.request.urlopen('$PROM_URL/-/healthy', timeout=5)
except Exception as e:
    print(f'ERROR: Prometheus not reachable at $PROM_URL', file=sys.stderr)
    print(f'  {e}', file=sys.stderr)
    print('', file=sys.stderr)
    print('Hint: Run scripts/setup_port_forward.sh in another terminal first.', file=sys.stderr)
    sys.exit(1)
" 2>&1; then
    exit 1
fi
echo "Prometheus reachable at $PROM_URL"

echo "Installing dependencies..."
"$PYTHON" -m pip install -q -r requirements.txt

if [ -d "$OUTPUT_DIR" ]; then
    echo "Cleaning old output: $OUTPUT_DIR"
    rm -rf "$OUTPUT_DIR"
fi

echo "Running live export (lookback=${LOOKBACK}min, step=5s)..."
"$PYTHON" -m benchmark.cli live \
    --prometheus-url "$PROM_URL" \
    --output "$OUTPUT_DIR" \
    --lookback-minutes "$LOOKBACK" \
    --step-seconds 5 \
    --queries-config configs/prometheus_queries.yaml

QUALITY_REL="data/datasets/online_boutique_short_fault_v1/processed/quality_report.json"
echo ""
echo "--- Quality Report ---"
"$PYTHON" -c "
import json
d = json.load(open('$QUALITY_REL'))
for k, v in d.items():
    if k == 'missing_features':
        print(f'  missing_features ({len(v)}): {v[:3]}...' if len(v) > 3 else f'  missing_features: {v}')
    else:
        print(f'  {k}: {v}')
"

PASSED=$("$PYTHON" -c "import json; d=json.load(open('$QUALITY_REL')); print(d['passed'])")
echo ""
if [ "$PASSED" = "True" ]; then
    echo "Live export complete: $OUTPUT_DIR"
else
    echo "WARNING: Quality checks did not fully pass. See quality_report.json." >&2
    echo "  This is expected if Istio is not installed (qps/latency/error_rate will be missing)."
fi
