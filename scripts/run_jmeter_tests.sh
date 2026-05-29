#!/usr/bin/env bash
# JMeter 性能测试启动脚本
# 用法:
#   bash scripts/run_jmeter_tests.sh                    # 两个系统都测
#   bash scripts/run_jmeter_tests.sh --target boutique  # 只测 Online Boutique
#   bash scripts/run_jmeter_tests.sh --target sockshop  # 只测 SockShop
#   bash scripts/run_jmeter_tests.sh --users 50 --duration 120
#   bash scripts/run_jmeter_tests.sh --jmeter /path/to/jmeter
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
JMETER_DIR="$PROJECT_ROOT/tests/jmeter"
PLANS_DIR="$JMETER_DIR/plans"
RESULTS_DIR="$JMETER_DIR/results"

# ── 默认参数 ──────────────────────────────────────────────────────────────
TARGET="all"
BOUTIQUE_HOST="${BOUTIQUE_HOST:-localhost}"
BOUTIQUE_PORT="${BOUTIQUE_PORT:-8080}"
SOCKSHOP_HOST="${SOCKSHOP_HOST:-localhost}"
SOCKSHOP_PORT="${SOCKSHOP_PORT:-8081}"
USERS="${JMETER_USERS:-10}"
DURATION="${JMETER_DURATION:-60}"
RAMP_UP="${JMETER_RAMP_UP:-10}"
JMETER_BIN=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --target)       TARGET="$2"; shift 2 ;;
        --boutique-host) BOUTIQUE_HOST="$2"; shift 2 ;;
        --boutique-port) BOUTIQUE_PORT="$2"; shift 2 ;;
        --sockshop-host) SOCKSHOP_HOST="$2"; shift 2 ;;
        --sockshop-port) SOCKSHOP_PORT="$2"; shift 2 ;;
        --users)         USERS="$2"; shift 2 ;;
        --duration)      DURATION="$2"; shift 2 ;;
        --ramp-up)       RAMP_UP="$2"; shift 2 ;;
        --jmeter)        JMETER_BIN="$2"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

# ── 找到 JMeter 可执行文件 ────────────────────────────────────────────────
if [ -z "$JMETER_BIN" ]; then
    for candidate in jmeter jmeter.bat \
                     "/e/apache-jmeter-5.6.3/bin/jmeter.bat" \
                     "/c/jmeter/bin/jmeter.bat" \
                     "$HOME/jmeter/bin/jmeter" \
                     "/opt/jmeter/bin/jmeter"; do
        if command -v "$candidate" &>/dev/null 2>&1 || [ -f "$candidate" ]; then
            JMETER_BIN="$candidate"
            break
        fi
    done
fi

if [ -z "$JMETER_BIN" ]; then
    echo "ERROR: JMeter not found." >&2
    echo "  请安装 JMeter 并确保 jmeter 命令在 PATH 中，或使用 --jmeter 参数指定路径。" >&2
    echo "  下载地址: https://jmeter.apache.org/download_jmeter.cgi" >&2
    echo "" >&2
    echo "  快速安装 (Windows):" >&2
    echo "    1. 下载 apache-jmeter-5.6.3.zip" >&2
    echo "    2. 解压到 C:\\jmeter" >&2
    echo "    3. 再运行: bash scripts/run_jmeter_tests.sh --jmeter /c/jmeter/bin/jmeter.bat" >&2
    exit 1
fi

echo "========================================================"
echo " JMeter 性能测试"
echo "========================================================"
echo " JMeter:      $JMETER_BIN"
echo " Target:      $TARGET"
echo " Users:       $USERS  |  Duration: ${DURATION}s  |  Ramp-up: ${RAMP_UP}s"
echo " Boutique:    $BOUTIQUE_HOST:$BOUTIQUE_PORT"
echo " SockShop:    $SOCKSHOP_HOST:$SOCKSHOP_PORT"
echo "========================================================"

mkdir -p "$RESULTS_DIR"

run_plan() {
    local plan="$1"
    local result_jtl="$2"
    local report_dir="$3"
    local extra_props="$4"

    local plan_name
    plan_name="$(basename "$plan" .jmx)"

    echo ""
    echo ">>> 运行测试计划: $plan_name"
    echo "    结果: $result_jtl"

    # 如果已有旧结果，先清理
    rm -f "$result_jtl"
    rm -rf "$report_dir"
    mkdir -p "$report_dir"

    "$JMETER_BIN" \
        -n \
        -t "$plan" \
        -l "$result_jtl" \
        -e -o "$report_dir" \
        -Jramp_up="$RAMP_UP" \
        -Jduration="$DURATION" \
        $extra_props \
        2>&1 | tee "$RESULTS_DIR/${plan_name}_console.log"

    echo "    完成。HTML 报告: $report_dir/index.html"
}

# ── 运行 Online Boutique 测试 ─────────────────────────────────────────────
if [ "$TARGET" = "boutique" ] || [ "$TARGET" = "all" ]; then
    run_plan \
        "$PLANS_DIR/online_boutique_load_test.jmx" \
        "$RESULTS_DIR/boutique_results.jtl" \
        "$RESULTS_DIR/boutique_report" \
        "-Jbase_url=$BOUTIQUE_HOST -Jbase_port=$BOUTIQUE_PORT"
fi

# ── 运行 SockShop 测试 ────────────────────────────────────────────────────
if [ "$TARGET" = "sockshop" ] || [ "$TARGET" = "all" ]; then
    run_plan \
        "$PLANS_DIR/sockshop_load_test.jmx" \
        "$RESULTS_DIR/sockshop_results.jtl" \
        "$RESULTS_DIR/sockshop_report" \
        "-Jbase_host=$SOCKSHOP_HOST -Jbase_port=$SOCKSHOP_PORT"
fi

# ── 汇总结果 ──────────────────────────────────────────────────────────────
echo ""
echo "========================================================"
echo " 测试完成！结果文件:"
for f in "$RESULTS_DIR"/*.jtl; do
    [ -f "$f" ] && echo "   JTL:  $f"
done
for d in "$RESULTS_DIR"/*_report; do
    [ -d "$d" ] && echo "   HTML: $d/index.html"
done
for f in "$RESULTS_DIR"/*_console.log; do
    [ -f "$f" ] && echo "   LOG:  $f"
done
echo "========================================================"

# ── 打印关键性能指标摘要（从 JTL 解析）────────────────────────────────
PYTHON=""
for candidate in python python3; do
    if command -v "$candidate" &>/dev/null; then
        if "$candidate" -c "import sys; assert sys.version_info >= (3,10)" 2>/dev/null; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [ -n "$PYTHON" ]; then
    for jtl in "$RESULTS_DIR"/*.jtl; do
        [ -f "$jtl" ] || continue
        echo ""
        echo "--- $(basename "$jtl") 性能指标摘要 ---"
        "$PYTHON" -c "
import csv, statistics, sys
from pathlib import Path

path = Path('$jtl')
rows = []
with open(path, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        try:
            rows.append({
                'label':   row.get('label', ''),
                'elapsed': int(row.get('elapsed', 0)),
                'success': row.get('success', 'true').lower() == 'true',
                'bytes':   int(row.get('bytes', 0)),
            })
        except (ValueError, KeyError):
            pass

if not rows:
    print('  (无数据)')
    sys.exit(0)

elapsed_vals = [r['elapsed'] for r in rows]
success_count = sum(1 for r in rows if r['success'])
total = len(rows)
error_rate = (total - success_count) / total * 100

print(f'  总请求数:    {total}')
print(f'  成功率:      {success_count/total*100:.1f}%  (错误率: {error_rate:.1f}%)')
print(f'  平均响应时间: {statistics.mean(elapsed_vals):.0f}ms')
print(f'  P50响应时间: {statistics.median(elapsed_vals):.0f}ms')
print(f'  P90响应时间: {sorted(elapsed_vals)[int(len(elapsed_vals)*0.90)]:.0f}ms')
print(f'  P95响应时间: {sorted(elapsed_vals)[int(len(elapsed_vals)*0.95)]:.0f}ms')
print(f'  最大响应时间: {max(elapsed_vals):.0f}ms')
print(f'  最小响应时间: {min(elapsed_vals):.0f}ms')
" 2>/dev/null || true
    done
fi
