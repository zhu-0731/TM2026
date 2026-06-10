@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo ============================================
echo OnlineBoutique 单浏览器测试
echo ============================================
echo.

REM 检查参数
if "%1"=="" (
    echo 用法: run_single_test.bat [chrome^|edge] [测试编号]
    echo.
    echo 示例:
    echo   run_single_test.bat chrome              运行所有测试
    echo   run_single_test.bat chrome 01           只运行 test_01_page_load
    echo   run_single_test.bat edge 08             只运行 test_08_apply_coupon
    echo   run_single_test.bat chrome 09-14        运行 test_09 到 test_14
    echo.
    pause
    exit /b 1
)

set BROWSER=%1
set TEST_FILTER=%2
set FRONTEND_URL=http://localhost:18080

REM 验证前端可访问
echo [1/3] 检查前端服务...
curl -s !FRONTEND_URL! >nul 2>&1
if errorlevel 1 (
    echo [错误] 前端服务无法访问
    echo [提示] 请先运行: kubectl port-forward svc/frontend-external 18080:80 -n default --address 0.0.0.0
    pause
    exit /b 1
)
echo [OK] 前端服务可访问

REM 安装依赖
echo.
echo [2/3] 安装依赖...
pip install -q -r requirements.txt
if errorlevel 1 (
    echo [错误] 依赖安装失败
    pause
    exit /b 1
)
echo [OK] 依赖已安装

REM 构建测试过滤器
set TEST_BROWSER=!BROWSER!
set TEST_MODE=baseline

if "!TEST_FILTER!"=="" (
    set PYTEST_FILTER=
    echo [3/3] 运行 !BROWSER! 所有测试...
) else (
    set PYTEST_FILTER=-k test_!TEST_FILTER!
    echo [3/3] 运行 !BROWSER! 测试: test_!TEST_FILTER!...
)

REM 运行测试
pytest test_selenium_performance.py -v --tb=short !PYTEST_FILTER! --html=report_!BROWSER!.html --self-contained-html

REM 显示结果
echo.
echo ============================================
echo 测试完成！
echo ============================================
echo.
echo 报告文件: report_!BROWSER!.html
echo.
echo 性能数据文件:
dir /b selenium_baseline_!BROWSER!_*.json 2>nul
echo.
pause
