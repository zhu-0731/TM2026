@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo ============================================
echo Selenium + ChaosMesh 故障注入集成测试
echo ============================================
echo.

REM 检查参数
if "%1"=="" (
    echo 用法: run_chaos_test.bat [cpu_stress^|memory_stress^|network_delay^|pod_kill]
    echo.
    echo 示例:
    echo   run_chaos_test.bat cpu_stress
    echo   run_chaos_test.bat memory_stress
    echo   run_chaos_test.bat network_delay
    echo   run_chaos_test.bat pod_kill
    echo.
    pause
    exit /b 1
)

set EXPERIMENT=%1
set FRONTEND_URL=http://localhost:18080

REM 验证前端可访问
echo [1/6] 检查前端服务...
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
echo [2/6] 安装依赖...
pip install -q -r requirements.txt
if errorlevel 1 (
    echo [错误] 依赖安装失败
    pause
    exit /b 1
)
echo [OK] 依赖已安装

REM 步骤1: 基线测试
echo.
echo [3/6] 运行基线测试（正常状态）...
set TEST_BROWSER=chrome
set TEST_MODE=baseline
pytest test_selenium_performance.py -v --tb=short
echo [OK] 基线测试完成

REM 步骤2: 注入故障
echo.
echo [4/6] 注入故障: !EXPERIMENT!...
kubectl apply -f ..\..\chaos-experiments\!EXPERIMENT!.yaml
if errorlevel 1 (
    echo [错误] 故障注入失败
    pause
    exit /b 1
)
echo [OK] 故障已注入

echo [等待] 等待故障生效（5秒）...
timeout /t 5 /nobreak >nul

REM 步骤3: 故障期间测试
echo.
echo [5/6] 运行故障期间测试...
set CHAOS_TYPE=!EXPERIMENT!
set TEST_MODE=chaos
pytest test_selenium_chaos.py -v --tb=short --html=report_chaos_!EXPERIMENT!.html --self-contained-html
echo [OK] 故障期间测试完成

REM 步骤4: 停止故障
echo.
echo [6/6] 停止故障...
kubectl delete -f ..\..\chaos-experiments\!EXPERIMENT!.yaml --ignore-not-found=true
echo [OK] 故障已停止

REM 显示结果
echo.
echo ============================================
echo Chaos 测试完成！
echo ============================================
echo.
echo 实验类型: !EXPERIMENT!
echo.
echo 报告文件:
echo   - report_chrome.html (基线)
echo   - report_chaos_!EXPERIMENT!.html (故障期间)
echo.
echo 性能数据文件:
dir /b selenium_*.json 2>nul
echo.
pause
