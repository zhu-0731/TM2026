#!/usr/bin/env bash
# 故障注入 + 数据采集一体化脚本
# 用法:
#   bash scripts/run_fault_collection.sh                          # 默认: cpu_stress + pod_kill
#   bash scripts/run_fault_collection.sh --faults "cpu_stress"   # 只注入 cpu_stress
#   bash scripts/run_fault_collection.sh --faults "cpu_stress pod_kill network_delay"
#   bash scripts/run_fault_collection.sh --dry-run               # 预演，不真实注入
#   bash scripts/run_fault_collection.sh --warmup 3 --gap 2      # 自定义时间参数
set -euo pipefail

export DOCKER_HOST="npipe:////./pipe/docker_engine"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# ── 默认参数 ──────────────────────────────────────────────────────────────
OUTPUT_DIR="data/datasets/online_boutique_rca_1"
PROM_URL="http://localhost:9090"
STEP=5
FAULTS="cpu_stress pod_kill"
WARMUP=5
GAP=3
ROUNDS=1
ROUND_GAP=5
GAP_JITTER=0
DRY_RUN=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --output)         OUTPUT_DIR="$2"; shift 2 ;;
        --prometheus-url) PROM_URL="$2"; shift 2 ;;
        --faults)         FAULTS="$2"; shift 2 ;;
        --warmup)         WARMUP="$2"; shift 2 ;;
        --gap)            GAP="$2"; shift 2 ;;
        --rounds)         ROUNDS="$2"; shift 2 ;;
        --round-gap)      ROUND_GAP="$2"; shift 2 ;;
        --gap-jitter)     GAP_JITTER="$2"; shift 2 ;;
        --dry-run)        DRY_RUN="--dry-run"; shift ;;
        --step)           STEP="$2"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

# ── Find Python ───────────────────────────────────────────────────────────
PYTHON=""
for candidate in python python3; do
    if command -v "$candidate" &>/dev/null; then
        if "$candidate" -c "import sys; assert sys.version_info >= (3,10)" 2>/dev/null; then
            PYTHON="$candidate"; break
        fi
    fi
done
[ -z "$PYTHON" ] && { echo "ERROR: Python 3.10+ not found" >&2; exit 1; }

# ── 前置检查 ──────────────────────────────────────────────────────────────
echo "========================================================"
echo " ChaosMesh 故障注入 + AIOps 数据采集"
echo "========================================================"
echo " 故障类型:    $FAULTS"
echo " 注入轮数:    ${ROUNDS}轮"
echo " 预热时间:    ${WARMUP}min"
echo " 轮内间隔:    ${GAP}min ±${GAP_JITTER}s 随机抖动"
[ "$ROUNDS" -gt 1 ] && echo " 轮间间隔:    ${ROUND_GAP}min ±${GAP_JITTER}s 随机抖动"
echo " 采样步长:    ${STEP}s"
echo " Prometheus:  $PROM_URL"
echo " 输出目录:    $OUTPUT_DIR"
[ -n "$DRY_RUN" ] && echo " ⚠️  DRY-RUN 模式（不实际注入）"
echo "========================================================"

# 检查 Prometheus 是否可达
"$PYTHON" -c "
import urllib.request, sys
try:
    urllib.request.urlopen('$PROM_URL/-/healthy', timeout=5)
    print('Prometheus: OK')
except Exception as e:
    print(f'ERROR: Prometheus not reachable at $PROM_URL: {e}', file=sys.stderr)
    print('  Run: bash scripts/setup_port_forward.sh', file=sys.stderr)
    sys.exit(1)
" || exit 1

# 检查 ChaosMesh
export DOCKER_HOST="npipe:////./pipe/docker_engine"
if ! kubectl get pods -n chaos-testing --no-headers 2>/dev/null | grep -q "Running"; then
    echo "ERROR: ChaosMesh not running in chaos-testing namespace" >&2
    echo "  Run: DOCKER_HOST=npipe:////./pipe/docker_engine minikube start" >&2
    exit 1
fi
echo "ChaosMesh: OK"

# 检查 online-boutique pods
if ! kubectl get pods -n online-boutique --no-headers 2>/dev/null | grep -q "Running"; then
    echo "ERROR: online-boutique pods not running" >&2
    exit 1
fi
echo "Online Boutique: OK"

# 清理旧输出
if [ -d "$OUTPUT_DIR" ] && [ -z "$DRY_RUN" ]; then
    echo "Cleaning old output: $OUTPUT_DIR"
    rm -rf "$OUTPUT_DIR"
fi

FAULT_COUNT=$(echo "$FAULTS" | wc -w)
ROUND_TOTAL=$(( WARMUP + ROUNDS * (FAULT_COUNT * 2) + (FAULT_COUNT - 1) * GAP + (ROUNDS - 1) * ROUND_GAP + 2 ))

echo ""
echo "Starting collection pipeline ..."
echo "  Total estimated time: ~${ROUND_TOTAL}min (${ROUNDS} round(s) × ${FAULT_COUNT} fault(s))"
echo ""

# ── 运行故障注入 + 采集 ──────────────────────────────────────────────────
"$PYTHON" -m benchmark.cli collect \
    --output "$OUTPUT_DIR" \
    --prometheus-url "$PROM_URL" \
    --step-seconds "$STEP" \
    --queries-config configs/prometheus_queries.yaml \
    --fault-types $FAULTS \
    --warmup-minutes "$WARMUP" \
    --gap-minutes "$GAP" \
    --rounds "$ROUNDS" \
    --round-gap-minutes "$ROUND_GAP" \
    --gap-jitter "$GAP_JITTER" \
    ${DRY_RUN}

# ── 结果检查 ─────────────────────────────────────────────────────────────
echo ""
echo "========================================================"
echo " 结果文件:"
echo "========================================================"
PROC="$OUTPUT_DIR/processed"
ANS="$OUTPUT_DIR/answers"

for f in \
    "$PROC/train_x.csv" "$PROC/test_x.csv" \
    "$PROC/train_y.csv" "$PROC/test_y.csv" \
    "$PROC/incidents.csv" "$PROC/quality_report.json" \
    "$ANS/test_ground_truth.csv" "$ANS/test_root_cause_ground_truth.csv" \
    "$OUTPUT_DIR/injection_log.json"
do
    if [ -f "$f" ]; then
        lines=$(wc -l < "$f" 2>/dev/null || echo "?")
        echo "  ✓ $(basename "$f") ($lines lines)"
    else
        echo "  ✗ MISSING: $f" >&2
    fi
done

# 打印质量报告摘要
QUALITY_REL="$OUTPUT_DIR/processed/quality_report.json"
if [ -f "$QUALITY_REL" ]; then
    echo ""
    echo "--- 质量报告 ---"
    "$PYTHON" -c "
import json
d = json.load(open('$QUALITY_REL'))
keys = ['row_count','train_rows','valid_rows','test_rows',
        'test_anomaly_points','test_anomaly_ratio','incident_count',
        'valid_incident_count','missing_feature_count','passed']
for k in keys:
    print(f'  {k}: {d.get(k)}')
"
fi

echo ""
PASSED=$("$PYTHON" -c "import json; print(json.load(open('$QUALITY_REL'))['passed'])" 2>/dev/null || echo "False")
if [ "$PASSED" = "True" ]; then
    echo "============================="
    echo "  SUCCESS — 数据集已生成"
    echo "  $OUTPUT_DIR"
    echo "============================="
else
    echo "WARNING: 质量检查未完全通过，详见 quality_report.json" >&2
fi
