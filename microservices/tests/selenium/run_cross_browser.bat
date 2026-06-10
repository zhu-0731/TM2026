@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo ============================================
echo OnlineBoutique 跨浏览器兼容性测试
echo 支持: Chrome、Edge、Firefox
echo ============================================
echo.

REM 设置前端地址
set FRONTEND_URL=http://localhost:18080

REM 验证前端可访问
echo [检查] 验证前端服务可访问...
curl -s !FRONTEND_URL! >nul 2>&1
if errorlevel 1 (
    echo [错误] 前端服务 !FRONTEND_URL! 无法访问
    echo [提示] 请先运行: kubectl port-forward svc/frontend-external 18080:80 -n default --address 0.0.0.0
    pause
    exit /b 1
)
echo [OK] 前端服务可访问
echo.

REM 安装依赖
echo [1/5] 安装依赖...
pip install -q -r requirements.txt
if errorlevel 1 (
    echo [错误] 依赖安装失败
    pause
    exit /b 1
)
echo [OK] 依赖已安装
echo.

REM 检查浏览器安装
echo [2/5] 检查浏览器安装...
set CHROME_FOUND=0
set EDGE_FOUND=0
set FIREFOX_FOUND=0

if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" set CHROME_FOUND=1
if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" set CHROME_FOUND=1

if exist "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" set EDGE_FOUND=1
if exist "C:\Program Files\Microsoft\Edge\Application\msedge.exe" set EDGE_FOUND=1

if exist "C:\Program Files\Mozilla Firefox\firefox.exe" set FIREFOX_FOUND=1
if exist "C:\Program Files (x86)\Mozilla Firefox\firefox.exe" set FIREFOX_FOUND=1

echo   Chrome:  !CHROME_FOUND! (1=已安装, 0=未安装)
echo   Edge:    !EDGE_FOUND! (1=已安装, 0=未安装)
echo   Firefox: !FIREFOX_FOUND! (1=已安装, 0=未安装)
echo.

REM 运行 Chrome 测试
if !CHROME_FOUND!==1 (
    echo [3/5] 运行 Chrome 浏览器测试...
    set TEST_BROWSER=chrome
    set TEST_MODE=baseline
    pytest test_selenium_performance.py -v --html=report_chrome.html --self-contained-html
    if errorlevel 1 (
        echo [警告] Chrome 测试失败，继续其他浏览器...
    ) else (
        echo [OK] Chrome 测试完成
    )
    echo.
) else (
    echo [跳过] Chrome 未安装，跳过测试
    echo.
)

REM 运行 Edge 测试
if !EDGE_FOUND!==1 (
    echo [4/5] 运行 Edge 浏览器测试...
    set TEST_BROWSER=edge
    set TEST_MODE=baseline
    pytest test_selenium_performance.py -v --html=report_edge.html --self-contained-html
    if errorlevel 1 (
        echo [警告] Edge 测试失败，继续其他浏览器...
    ) else (
        echo [OK] Edge 测试完成
    )
    echo.
) else (
    echo [跳过] Edge 未安装，跳过测试
    echo.
)

REM 运行 Firefox 测试
if !FIREFOX_FOUND!==1 (
    echo [5/5] 运行 Firefox 浏览器测试...
    set TEST_BROWSER=firefox
    set TEST_MODE=baseline
    pytest test_selenium_performance.py -v --html=report_firefox.html --self-contained-html
    if errorlevel 1 (
        echo [警告] Firefox 测试失败
    ) else (
        echo [OK] Firefox 测试完成
    )
    echo.
) else (
    echo [跳过] Firefox 未安装，跳过测试
    echo.
)

REM 生成跨浏览器对比报告
echo [汇总] 生成跨浏览器对比报告...
python -c "
import sys
sys.path.insert(0, '.')
from test_selenium_performance import _generate_cross_browser_report
import json, glob

results = {}
perf_data = {}
for browser in ['chrome', 'edge', 'firefox']:
    json_files = glob.glob(f'selenium_baseline_{browser}_*.json')
    results[browser] = len(json_files) > 0
    if json_files:
        with open(json_files[-1], 'r', encoding='utf-8') as f:
            perf_data[browser] = json.load(f)

_generate_cross_browser_report(results, perf_data)
print('[OK] 对比报告已生成')
"

REM 显示结果
echo.
echo ============================================
echo 跨浏览器测试完成！
echo ============================================
echo.
echo 详细报告文件:
if !CHROME_FOUND!==1 echo   - report_chrome.html
if !EDGE_FOUND!==1 echo   - report_edge.html
if !FIREFOX_FOUND!==1 echo   - report_firefox.html
echo.
echo 对比报告:
echo   - cross_browser_report.md
echo.
echo 性能数据文件:
dir /b selenium_baseline_*.json 2>nul
echo.
pause
