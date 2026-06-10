@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo ============================================
echo OnlineBoutique Selenium 功能与性能测试
echo 阶段三：前端自动化测试
echo ============================================
echo.

REM 检查参数
if "%1"=="" (
    echo 用法: run_selenium_tests.bat [chrome^|edge^|firefox^|all^|chaos]
    echo.
    echo 模式说明:
    echo   chrome  - 运行 Chrome 浏览器测试
echo   edge    - 运行 Edge 浏览器测试
echo   all     - 运行所有浏览器测试
echo   chaos   - 运行故障注入集成测试
echo.
    echo 示例:
    echo   run_selenium_tests.bat chrome
echo   run_selenium_tests.bat all
echo   run_selenium_tests.bat chaos --experiment cpu_stress
echo.
    exit /b 1
)

REM 设置前端地址（根据实际环境修改）
set FRONTEND_URL=http://localhost:18080

REM 验证前端可访问
echo [检查] 验证前端服务可访问...
curl -s !FRONTEND_URL! >nul 2>&1
if errorlevel 1 (
    echo [警告] 前端服务 !FRONTEND_URL! 无法访问
    echo [提示] 尝试启动 port-forward...
    echo   kubectl port-forward svc/frontend-external 18080:80 -n default --address 0.0.0.0
    pause
    exit /b 1
)
echo [OK] 前端服务可访问

REM 安装依赖
echo.
echo [1/4] 安装依赖...
pip install -q -r requirements.txt
if errorlevel 1 (
    echo [错误] 依赖安装失败
    exit /b 1
)
echo [OK] 依赖已安装

REM 根据参数执行不同模式
if /i "%1"=="all" (
    echo.
    echo [2/4] 运行 Chrome 测试...
    set TEST_BROWSER=chrome
    pytest test_selenium_performance.py -v --html=report_chrome.html --self-contained-html
    
    echo.
    echo [3/4] 运行 Edge 测试...
    set TEST_BROWSER=edge
    pytest test_selenium_performance.py -v --html=report_edge.html --self-contained-html
    
    echo.
    echo [4/4] 测试完成！
    echo ============================================
    echo 报告文件:
    echo   - report_chrome.html
echo   - report_edge.html
echo ============================================
    
) else if /i "%1"=="chaos" (
    echo.
    echo [Chaos 模式] 运行故障注入集成测试...
    python run_selenium_with_chaos.py %2 %3 %4 %5 %6
    
) else (
    echo.
    echo [2/3] 运行 %1 测试...
    set TEST_BROWSER=%1
    pytest test_selenium_performance.py -v --html=report_%1.html --self-contained-html
    
    echo.
    echo [3/3] 测试完成！
    echo 报告文件: report_%1.html
)

echo.
echo 性能数据文件:
dir /b selenium_*.json 2>nul

echo.
pause
