@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

REM JMeter 路径（相对项目根目录）
set JMETER_PATH=E:\Testing and Maintenance\microservices-demo\apache-jmeter-5.6.3\bin\jmeter.bat
set TEST_PLAN=onlineboutique_test_plan.jmx

echo ============================================
echo OnlineBoutique JMeter 性能测试
echo ============================================
echo.

REM 检查 JMeter
if not exist "!JMETER_PATH!" (
    echo [错误] JMeter 未找到: !JMETER_PATH!
    pause
    exit /b 1
)

REM 创建目录
if not exist results mkdir results
if not exist report mkdir report

echo [1/4] 运行基准测试（10用户，5分钟）...
"!JMETER_PATH!" -n -t !TEST_PLAN! -l results/baseline.jtl -e -o report/baseline -Jjmeter.save.saveservice.output_format=csv
echo [OK] 基准测试完成
echo.

echo [2/4] 运行负载测试（50用户，10分钟）...
"!JMETER_PATH!" -n -t !TEST_PLAN! -l results/load.jtl -e -o report/load -Jjmeter.save.saveservice.output_format=csv
echo [OK] 负载测试完成
echo.

echo [3/4] 运行压力测试（100用户，10分钟）...
"!JMETER_PATH!" -n -t !TEST_PLAN! -l results/stress.jtl -e -o report/stress -Jjmeter.save.saveservice.output_format=csv
echo [OK] 压力测试完成
echo.

echo [4/4] 运行峰值测试（200用户，5分钟）...
"!JMETER_PATH!" -n -t !TEST_PLAN! -l results/spike.jtl -e -o report/spike -Jjmeter.save.saveservice.output_format=csv
echo [OK] 峰值测试完成
echo.

echo ============================================
echo 所有测试完成！
echo ============================================
echo.
echo 报告位置:
echo   - report/baseline/index.html
echo   - report/load/index.html
echo   - report/stress/index.html
echo   - report/spike/index.html
echo.
pause
