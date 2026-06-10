@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo ============================================
echo OnlineBoutique Selenium 测试运行脚本
echo ============================================
echo.

REM 设置前端地址
set FRONTEND_URL=http://localhost:18080

REM 验证前端可访问
echo [1/5] 检查前端服务...
curl -s !FRONTEND_URL! >nul 2>&1
if errorlevel 1 (
    echo [错误] 前端服务 !FRONTEND_URL! 无法访问
    echo [提示] 请先运行: kubectl port-forward svc/frontend-external 18080:80 -n default --address 0.0.0.0
    pause
    exit /b 1
)
echo [OK] 前端服务可访问

REM 安装依赖
echo.
echo [2/5] 安装依赖...
pip install -q -r requirements.txt
if errorlevel 1 (
    echo [错误] 依赖安装失败
    pause
    exit /b 1
)
echo [OK] 依赖已安装

REM 运行 Chrome 测试
echo.
echo [3/4] 运行 Chrome 浏览器测试...
set TEST_BROWSER=chrome
set TEST_MODE=baseline
pytest test_selenium_performance.py -v --html=report_chrome.html --self-contained-html
echo [OK] Chrome 测试完成

REM Edge 测试需要网络下载驱动，如网络受限可跳过
REM 如需运行 Edge，请手动下载 EdgeDriver 并设置 EDGE_DRIVER_PATH 环境变量
echo.
echo [4/4] Edge 测试已跳过（网络受限无法自动下载驱动）
echo   [提示] 如需测试 Edge，请:
echo     1. 从 https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/ 下载驱动
echo     2. 设置环境变量: set EDGE_DRIVER_PATH=路径\msedgedriver.exe
echo     3. 运行: run_single_test.bat edge

REM 显示结果
echo.
echo ============================================
echo 测试完成！
echo ============================================
echo.
echo 报告文件:
echo   - report_chrome.html
echo.
echo 性能数据文件:
dir /b selenium_baseline_*.json 2>nul
echo.
pause
