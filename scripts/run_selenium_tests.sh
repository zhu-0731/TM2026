#!/usr/bin/env bash
# Selenium 功能测试启动脚本
# 用法:
#   bash scripts/run_selenium_tests.sh              # 默认 Chrome headless
#   bash scripts/run_selenium_tests.sh --browser firefox
#   bash scripts/run_selenium_tests.sh --visible    # 非 headless 模式
#   bash scripts/run_selenium_tests.sh --test boutique  # 只跑 Online Boutique
#   bash scripts/run_selenium_tests.sh --test sockshop  # 只跑 SockShop
#   bash scripts/run_selenium_tests.sh --cross-browser  # 跨浏览器测试
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SELENIUM_DIR="$PROJECT_ROOT/tests/selenium"
RESULTS_DIR="$SELENIUM_DIR/results"

# ── 默认参数 ──────────────────────────────────────────────────────────────
BROWSER="chrome"
HEADLESS="true"
TEST_TARGET="all"   # all | boutique | sockshop | cross
BOUTIQUE_URL="${BOUTIQUE_URL:-http://localhost:8080}"
SOCKSHOP_URL="${SOCKSHOP_URL:-http://localhost:8081}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --browser)    BROWSER="$2"; shift 2 ;;
        --visible)    HEADLESS="false"; shift ;;
        --test)       TEST_TARGET="$2"; shift 2 ;;
        --cross-browser) TEST_TARGET="cross"; shift ;;
        --boutique-url) BOUTIQUE_URL="$2"; shift 2 ;;
        --sockshop-url) SOCKSHOP_URL="$2"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

echo "========================================================"
echo " Selenium 功能测试"
echo "========================================================"
echo " Browser:     $BROWSER  (headless=$HEADLESS)"
echo " Boutique:    $BOUTIQUE_URL"
echo " SockShop:    $SOCKSHOP_URL"
echo " Target:      $TEST_TARGET"
echo "========================================================"

# ── Find Python ───────────────────────────────────────────────────────────
PYTHON=""
for candidate in python python3; do
    if command -v "$candidate" &>/dev/null; then
        if "$candidate" -c "import sys; assert sys.version_info >= (3,10)" 2>/dev/null; then
            PYTHON="$candidate"
            break
        fi
    fi
done
[ -z "$PYTHON" ] && { echo "ERROR: Python 3.10+ not found." >&2; exit 1; }

# ── Install dependencies ──────────────────────────────────────────────────
echo ""
echo "Installing Selenium dependencies..."
"$PYTHON" -m pip install -q -r "$SELENIUM_DIR/requirements.txt"

mkdir -p "$RESULTS_DIR/screenshots"

# ── Port-forward check ────────────────────────────────────────────────────
echo ""
echo "Checking service connectivity..."

check_url() {
    "$PYTHON" -c "
import urllib.request, sys
try:
    urllib.request.urlopen('$1', timeout=5)
    print('  $1: OK')
except Exception as e:
    print(f'  $1: UNREACHABLE ({e})')
    print('  Hint: Run scripts/setup_port_forward.sh in another terminal')
    sys.exit(1)
"
}

if [ "$TEST_TARGET" = "boutique" ] || [ "$TEST_TARGET" = "all" ] || [ "$TEST_TARGET" = "cross" ]; then
    check_url "$BOUTIQUE_URL" || exit 1
fi
if [ "$TEST_TARGET" = "sockshop" ] || [ "$TEST_TARGET" = "all" ] || [ "$TEST_TARGET" = "cross" ]; then
    check_url "$SOCKSHOP_URL" || { echo "SockShop not reachable, skipping SockShop tests"; }
fi

# ── Run tests ─────────────────────────────────────────────────────────────
echo ""
echo "Running tests..."

export SELENIUM_BROWSER="$BROWSER"
export SELENIUM_HEADLESS="$HEADLESS"
export BOUTIQUE_URL="$BOUTIQUE_URL"
export SOCKSHOP_URL="$SOCKSHOP_URL"

cd "$SELENIUM_DIR"

case "$TEST_TARGET" in
    boutique)
        "$PYTHON" -m pytest test_boutique_functional.py -v \
            --html=results/report_boutique.html --self-contained-html
        ;;
    sockshop)
        "$PYTHON" -m pytest test_sockshop_functional.py -v \
            --html=results/report_sockshop.html --self-contained-html
        ;;
    cross)
        "$PYTHON" -m pytest test_cross_browser.py -v \
            --html=results/report_cross_browser.html --self-contained-html
        ;;
    all)
        "$PYTHON" -m pytest test_boutique_functional.py test_sockshop_functional.py -v \
            --html=results/report.html --self-contained-html
        ;;
esac

echo ""
echo "========================================================"
echo " 测试完成！报告位置:"
echo "   $RESULTS_DIR/report*.html"
echo "   $RESULTS_DIR/timing_metrics.json"
echo "   $RESULTS_DIR/screenshots/"
echo "========================================================"
