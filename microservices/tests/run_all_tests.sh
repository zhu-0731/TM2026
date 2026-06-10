#!/bin/bash
# OnlineBoutique 完整测试脚本
# 一键运行所有测试：Prometheus监控 + ChaosMesh故障注入 + Selenium功能测试 + JMeter性能测试

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 配置
FRONTEND_URL=${FRONTEND_URL:-"http://localhost:8080"}
PROMETHEUS_URL=${PROMETHEUS_URL:-"http://localhost:9090"}
RESULTS_DIR="test_results_$(date +%Y%m%d_%H%M%S)"

# 创建结果目录
mkdir -p "$RESULTS_DIR"

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  OnlineBoutique 完整测试套件${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "配置信息:"
echo "  前端地址: $FRONTEND_URL"
echo "  Prometheus: $PROMETHEUS_URL"
echo "  结果目录: $RESULTS_DIR"
echo ""

# ============================================
# 阶段一：环境检查
# ============================================
echo -e "${YELLOW}[阶段一] 环境检查${NC}"
echo "--------------------------------------------"

# 检查 kubectl
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}错误: kubectl 未安装${NC}"
    exit 1
fi

# 检查 Minikube 状态
if ! minikube status &> /dev/null; then
    echo -e "${RED}错误: Minikube 未启动${NC}"
    echo "请运行: minikube start --driver=docker --memory=8192 --cpus=4"
    exit 1
fi

# 检查微服务状态
echo "检查微服务状态..."
kubectl get pods -n default || true

# 检查前端可访问性
echo "检查前端服务..."
if curl -s "$FRONTEND_URL" > /dev/null; then
    echo -e "${GREEN}前端服务可访问${NC}"
else
    echo -e "${YELLOW}警告: 前端服务可能未就绪，尝试 port-forward...${NC}"
    kubectl port-forward svc/frontend-external 8080:80 -n default &
    sleep 3
fi

echo ""

# ============================================
# 阶段二：Prometheus 数据采集（基线）
# ============================================
echo -e "${YELLOW}[阶段二] Prometheus 数据采集 - 基线${NC}"
echo "--------------------------------------------"

# 检查 Prometheus
echo "检查 Prometheus..."
if ! curl -s "$PROMETHEUS_URL/api/v1/status/targets" > /dev/null; then
    echo -e "${YELLOW}Prometheus 未就绪，尝试 port-forward...${NC}"
    kubectl port-forward svc/prometheus 9090:9090 -n monitoring &
    sleep 3
fi

# 采集基线数据
echo "采集基线数据（5分钟）..."
cd tests/prometheus
python collect_metrics.py \
    --url "$PROMETHEUS_URL" \
    --mode baseline \
    --duration 300 \
    --output "../../$RESULTS_DIR/baseline_metrics.json" || true
cd ../..

echo ""

# ============================================
# 阶段三：Selenium 功能测试
# ============================================
echo -e "${YELLOW}[阶段三] Selenium 功能测试${NC}"
echo "--------------------------------------------"

cd tests/selenium

# 安装依赖
pip install -q -r requirements.txt 2>/dev/null || true

# 运行基础功能测试
echo "运行基础功能测试..."
python test_onlineboutique.py 2>&1 | tee "../../$RESULTS_DIR/selenium_basic.log" || true

# 运行增强功能测试（Chrome）
echo ""
echo "运行增强功能测试（Chrome）..."
HEADLESS=true FRONTEND_URL="$FRONTEND_URL" \
    python test_onlineboutique_advanced.py 2>&1 | tee "../../$RESULTS_DIR/selenium_advanced.log" || true

cd ../..

echo ""

# ============================================
# 阶段四：JMeter 性能测试（基线）
# ============================================
echo -e "${YELLOW}[阶段四] JMeter 性能测试 - 基线${NC}"
echo "--------------------------------------------"

cd tests/jmeter
mkdir -p results report

# 检查 JMeter
if ! command -v jmeter &> /dev/null; then
    echo -e "${YELLOW}警告: JMeter 未安装，跳过性能测试${NC}"
else
    # 修改测试计划中的目标地址
    sed -i "s|<stringProp name=\"Argument.value\">localhost</stringProp>|<stringProp name=\"Argument.value\">${FRONTEND_URL#http://}</stringProp>|g" onlineboutique_test_plan.jmx || true
    
    # 运行基准测试
    echo "运行基准测试（10用户，5分钟）..."
    jmeter -n -t onlineboutique_test_plan.jmx \
        -l "results/baseline_results.jtl" \
        -e -o "report/baseline" 2>&1 | tee "../../$RESULTS_DIR/jmeter_baseline.log" || true
    
    # 复制报告
    cp -r report/baseline "../../$RESULTS_DIR/" 2>/dev/null || true
fi

cd ../..

echo ""

# ============================================
# 阶段五：ChaosMesh 故障注入
# ============================================
echo -e "${YELLOW}[阶段五] ChaosMesh 故障注入${NC}"
echo "--------------------------------------------"

# 检查 ChaosMesh
echo "检查 ChaosMesh..."
if ! kubectl get pods -n chaos-mesh &> /dev/null; then
    echo -e "${YELLOW}ChaosMesh 未安装，尝试安装...${NC}"
    helm repo add chaos-mesh https://charts.chaos-mesh.org 2>/dev/null || true
    helm repo update 2>/dev/null || true
    helm install chaos-mesh chaos-mesh/chaos-mesh -n chaos-mesh --create-namespace 2>/dev/null || true
    sleep 10
fi

# 故障注入实验列表
EXPERIMENTS=(
    "cpu-stress-frontend:CPU压力测试"
    "memory-stress-cartservice:内存压力测试"
    "network-delay-checkoutservice:网络延迟测试"
    "pod-kill-couponservice:Pod杀死测试"
)

for exp in "${EXPERIMENTS[@]}"; do
    IFS=':' read -r exp_file exp_name <<< "$exp"
    
    echo ""
    echo -e "${YELLOW}实验: $exp_name${NC}"
    echo "--------------------------------------------"
    
    # 注入故障
    echo "注入故障..."
    kubectl apply -f "chaos-experiments/${exp_file}.yaml"
    
    # 等待故障生效
    sleep 10
    
    # 采集故障期间数据
    echo "采集故障期间数据..."
    cd tests/prometheus
    python collect_metrics.py \
        --url "$PROMETHEUS_URL" \
        --mode chaos \
        --duration 180 \
        --experiment "$exp_file" \
        --output "../../$RESULTS_DIR/chaos_${exp_file}_metrics.json" || true
    cd ../..
    
    # 运行 Selenium 故障期间测试
    echo "运行故障期间功能测试..."
    cd tests/selenium
    HEADLESS=true FRONTEND_URL="$FRONTEND_URL" \
        python test_chaos_resilience.py 2>&1 | tee "../../$RESULTS_DIR/selenium_chaos_${exp_file}.log" || true
    cd ../..
    
    # 运行 JMeter 故障期间测试
    if command -v jmeter &> /dev/null; then
        echo "运行故障期间性能测试..."
        cd tests/jmeter
        jmeter -n -t onlineboutique_test_plan.jmx \
            -l "results/chaos_${exp_file}_results.jtl" \
            -e -o "report/chaos_${exp_file}" 2>&1 | tee "../../$RESULTS_DIR/jmeter_chaos_${exp_file}.log" || true
        cp -r "report/chaos_${exp_file}" "../../$RESULTS_DIR/" 2>/dev/null || true
        cd ../..
    fi
    
    # 停止故障
    echo "停止故障..."
    kubectl delete -f "chaos-experiments/${exp_file}.yaml" --ignore-not-found=true
    
    # 等待恢复
    echo "等待系统恢复..."
    sleep 30
    
done

echo ""

# ============================================
# 阶段六：数据对比分析
# ============================================
echo -e "${YELLOW}[阶段六] 数据对比分析${NC}"
echo "--------------------------------------------"

cd tests/prometheus

# 对比每个实验的数据
for exp_file in cpu-stress-frontend memory-stress-cartservice network-delay-checkoutservice pod-kill-couponservice; do
    baseline="../../$RESULTS_DIR/baseline_metrics.json"
    chaos="../../$RESULTS_DIR/chaos_${exp_file}_metrics.json"
    
    if [ -f "$baseline" ] && [ -f "$chaos" ]; then
        echo "对比: $exp_file"
        python collect_metrics.py \
            --mode compare \
            --baseline "$baseline" \
            --chaos "$chaos" \
            --output "../../$RESULTS_DIR/comparison_${exp_file}.json" || true
    fi
done

cd ../..

echo ""

# ============================================
# 测试完成汇总
# ============================================
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  测试完成！${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "结果文件:"
ls -la "$RESULTS_DIR/"
echo ""
echo "查看报告:"
echo "  - Selenium 日志: $RESULTS_DIR/selenium_*.log"
echo "  - JMeter 报告: $RESULTS_DIR/baseline/index.html"
echo "  - Prometheus 数据: $RESULTS_DIR/*_metrics.json"
echo "  - 对比分析: $RESULTS_DIR/comparison_*.json"
echo ""
