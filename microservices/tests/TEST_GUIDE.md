# 微服务测试维护实验完整指南

> 本指南涵盖 **阶段二**（Prometheus + Grafana + ChaosMesh 监控与故障注入）和 **阶段三**（Selenium + JMeter 自动化测试）的完整操作步骤与代码。

---

## 目录

- [前置条件](#前置条件)
- [阶段二：Prometheus & Grafana 监控 + ChaosMesh 故障注入](#阶段二prometheus--grafana-监控--chaosmesh-故障注入)
  - [2.1 部署 Prometheus](#21-部署-prometheus)
  - [2.2 部署 Grafana](#22-部署-grafana)
  - [2.3 配置 Prometheus 数据源](#23-配置-prometheus-数据源)
  - [2.4 导入 Grafana 仪表盘](#24-导入-grafana-仪表盘)
  - [2.5 部署 ChaosMesh](#25-部署-chaosmesh)
  - [2.6 故障注入实验](#26-故障注入实验)
  - [2.7 数据采集与可视化](#27-数据采集与可视化)
- [阶段三：Selenium & JMeter 自动化测试](#阶段三selenium--jmeter-自动化测试)
  - [3.1 环境准备](#31-环境准备)
  - [3.2 Selenium 功能测试](#32-selenium-功能测试)
  - [3.3 JMeter 性能测试](#33-jmeter-性能测试)
- [附录：常见问题](#附录常见问题)

---

## 前置条件

1. **Minikube 集群已启动**
   ```bash
   minikube status
   # 如未启动：minikube start --driver=docker --memory=8192 --cpus=4
   ```

2. **微服务系统已部署**
   ```bash
   kubectl get pods -n default
   # 确保所有 Pod 状态为 Running
   ```

3. **前端可访问**
   ```bash
   # 获取前端访问地址
   minikube service frontend-external --url -n default
   # 或
   kubectl port-forward svc/frontend-external 8080:80 -n default
   ```

4. **必要工具已安装**
   - `kubectl` - Kubernetes 命令行工具
   - `helm` - Kubernetes 包管理器
   - `Python 3.x` + `pip`
   - `JMeter 5.x` - 性能测试工具
   - `Chrome 浏览器` + `ChromeDriver`

---

## 阶段二：Prometheus & Grafana 监控 + ChaosMesh 故障注入

### 核心原理

> **重要说明**：本项目中的微服务（frontend、checkoutservice 等）**没有内置 Prometheus 客户端库**，因此无法直接暴露 `http_requests_total`、`request_duration_seconds` 等应用层指标。
>
> 本方案使用 **Kubernetes 内置的容器指标**（通过 Kubelet/cAdvisor 自动暴露），可以获取：
> - 容器 CPU 使用率
> - 容器内存使用量
> - 容器网络收发速率
> - 容器文件系统使用量
> - Pod 重启次数
>
> 这些指标完全足够用于：
> 1. 监控系统运行状态
> 2. 检测 ChaosMesh 故障注入的影响（CPU 压力、内存压力、网络延迟、Pod 杀死）
> 3. 论文复现所需的数据分析

### 2.1 部署 Prometheus

#### 步骤 1：应用 RBAC 和配置

```bash
# 创建 monitoring 命名空间、ServiceAccount、ClusterRole、ClusterRoleBinding
kubectl apply -f monitoring/prometheus-rbac.yaml

# 应用 Prometheus 配置 ConfigMap
kubectl apply -f monitoring/prometheus-config.yaml
```

#### 步骤 2：部署 Prometheus

```bash
# 部署 Prometheus Deployment 和 NodePort Service
kubectl apply -f monitoring/prometheus-deployment.yaml

# 验证部署
kubectl get pods -n monitoring
kubectl get svc -n monitoring
```

#### 步骤 3：访问 Prometheus

```bash
# Port-forward（推荐）
kubectl port-forward svc/prometheus -n monitoring 9090:9090
```

浏览器访问：`http://localhost:9090`

**验证抓取目标**：
1. 进入 **Status → Targets**
2. 确认以下 job 状态为 **UP**：
   - `prometheus` - Prometheus 自身
   - `kubernetes-cadvisor` - 容器指标（最关键！）
   - `kubernetes-kubelet` - Kubelet 指标
   - `kubernetes-apiservers` - API Server

> 如果 `kubernetes-cadvisor` 显示 DOWN，检查 RBAC 权限是否正确。

#### 步骤 4：验证指标数据

在 Prometheus UI 的 **Graph** 页面，输入以下查询验证是否有数据：

```promql
# 查看所有 Pod 的 CPU 使用率
rate(container_cpu_usage_seconds_total{namespace="default"}[5m])

# 查看所有 Pod 的内存使用量
container_memory_usage_bytes{namespace="default"}

# 查看 Frontend Pod 的 CPU
rate(container_cpu_usage_seconds_total{namespace="default",pod=~"frontend-.*"}[5m])

# 查看 CartService 的内存
container_memory_usage_bytes{namespace="default",pod=~"cartservice-.*"}
```

如果能看到数据，说明 Prometheus 配置正确！

---

### 2.2 部署 Grafana

```bash
# 部署 Grafana
kubectl apply -f monitoring/grafana-deployment.yaml

# 验证部署
kubectl get pods -n monitoring
kubectl get svc -n monitoring
```

访问 Grafana：
```bash
kubectl port-forward svc/grafana -n monitoring 3000:3000
```

浏览器访问：`http://localhost:3000`
- **用户名**：`admin`
- **密码**：`admin`

---

### 2.3 配置 Prometheus 数据源

1. 登录 Grafana
2. 左侧菜单 → **Connections** → **Data Sources** → **Add data source**
3. 选择 **Prometheus**
4. URL 填写：`http://prometheus:9090`
5. 点击 **Save & Test**，确认连接成功

---

### 2.4 导入 Grafana 仪表盘

#### 方法一：导入项目自带的仪表盘（推荐）

1. 左侧菜单 → **Dashboards** → **Import**
2. 点击 **Upload JSON file**
3. 选择 `monitoring/grafana-dashboard.json`
4. 选择 Prometheus 数据源 → **Import**

#### 方法二：手动创建面板

如果导入失败，可以手动创建：

1. 左侧菜单 → **Dashboards** → **New Dashboard** → **Add visualization**
2. 选择 Prometheus 数据源
3. 在 Query 中输入 PromQL：

```promql
# Panel 1: Pod CPU 使用率
rate(container_cpu_usage_seconds_total{namespace="default",container!="",container!="POD"}[5m])

# Panel 2: Pod 内存使用量
container_memory_usage_bytes{namespace="default",container!="",container!="POD"}

# Panel 3: 网络接收速率
rate(container_network_receive_bytes_total{namespace="default"}[5m])

# Panel 4: Frontend CPU (用于观察 CPU Stress 故障)
rate(container_cpu_usage_seconds_total{namespace="default",pod=~"frontend-.*",container!="",container!="POD"}[5m])

# Panel 5: CartService 内存 (用于观察 Memory Stress 故障)
container_memory_usage_bytes{namespace="default",pod=~"cartservice-.*",container!="",container!="POD"}

# Panel 6: CheckoutService 网络 (用于观察 Network Delay 故障)
rate(container_network_receive_bytes_total{namespace="default",pod=~"checkoutservice-.*"}[5m])
```

---

### 2.5 部署 ChaosMesh

#### 步骤 1：安装 ChaosMesh

```bash
# 添加 Helm 仓库
helm repo add chaos-mesh https://charts.chaos-mesh.org
helm repo update

# 安装 ChaosMesh
helm install chaos-mesh chaos-mesh/chaos-mesh -n chaos-mesh --create-namespace

# 或使用脚本安装（国内镜像）
curl -sSL https://mirrors.chaos-mesh.org/v2.6.3/install.sh | bash
```

#### 步骤 2：验证安装

```bash
kubectl get pods -n chaos-mesh
```

#### 步骤 3：访问 Chaos Dashboard

```bash
kubectl port-forward -n chaos-mesh svc/chaos-dashboard 2333:2333
```

浏览器访问：`http://localhost:2333`

---

### 2.6 故障注入实验

#### 实验 1：CPU 压力测试（frontend 服务）

```bash
# 应用 CPU 压力故障
kubectl apply -f chaos-experiments/cpu-stress-frontend.yaml

# 查看实验状态
kubectl get stresschaos -n chaos-testing

# 在 Grafana 中观察 frontend Pod 的 CPU 使用率飙升
```

**预期效果**：
- `kubernetes-cadvisor` 抓取的 `container_cpu_usage_seconds_total` 指标显示 frontend Pod CPU 使用率显著上升
- Grafana 面板 "Frontend CPU (CPU Stress 监控)" 中可以看到明显的峰值

#### 实验 2：内存压力测试（cartservice 服务）

```bash
kubectl apply -f chaos-experiments/memory-stress-cartservice.yaml
```

**预期效果**：
- `container_memory_usage_bytes` 指标显示 cartservice Pod 内存使用量上升约 256MB
- Grafana 面板 "CartService 内存 (Memory Stress 监控)" 中可以看到内存突增

#### 实验 3：网络延迟测试（checkoutservice 服务）

```bash
kubectl apply -f chaos-experiments/network-delay-checkoutservice.yaml
```

**预期效果**：
- 网络收发速率可能下降或出现波动
- Grafana 面板 "CheckoutService 网络" 中可以看到变化

#### 实验 4：Pod 杀死测试（couponservice 服务）

```bash
kubectl apply -f chaos-experiments/pod-kill-couponservice.yaml
```

**预期效果**：
- Pod 重启次数增加
- Pod 状态在 Running 和 Pending/Error 之间切换
- Grafana 面板 "CouponService Pod 状态" 中可以看到变化

#### 清理实验

```bash
# 删除所有故障注入实验
kubectl delete -f chaos-experiments/

# 或按类型删除
kubectl delete stresschaos --all -n chaos-testing
kubectl delete networkchaos --all -n chaos-testing
kubectl delete podchaos --all -n chaos-testing
```

---

### 2.7 数据采集与可视化

#### 关键 PromQL 查询（基于容器指标）

```promql
# ===== CPU 指标 =====

# 所有 Pod CPU 使用率
rate(container_cpu_usage_seconds_total{namespace="default",container!="",container!="POD"}[5m])

# Frontend CPU 使用率
rate(container_cpu_usage_seconds_total{namespace="default",pod=~"frontend-.*",container!="",container!="POD"}[5m])

# CheckoutService CPU 使用率
rate(container_cpu_usage_seconds_total{namespace="default",pod=~"checkoutservice-.*",container!="",container!="POD"}[5m])

# ===== 内存指标 =====

# 所有 Pod 内存使用量
container_memory_usage_bytes{namespace="default",container!="",container!="POD"}

# 工作集内存（更准确的内存使用量）
container_memory_working_set_bytes{namespace="default",container!="",container!="POD"}

# CartService 内存
container_memory_usage_bytes{namespace="default",pod=~"cartservice-.*",container!="",container!="POD"}

# ===== 网络指标 =====

# 网络接收速率
rate(container_network_receive_bytes_total{namespace="default"}[5m])

# 网络发送速率
rate(container_network_transmit_bytes_total{namespace="default"}[5m])

# CheckoutService 网络
rate(container_network_receive_bytes_total{namespace="default",pod=~"checkoutservice-.*"}[5m])

# ===== Pod 状态指标 =====

# Pod 重启次数
kube_pod_container_status_restarts_total{namespace="default"}

# Pod 状态分布
kube_pod_status_phase{namespace="default"}

# Running 状态的 Pod
kube_pod_status_phase{namespace="default",phase="Running"}
```

#### 数据导出（用于论文复现）

```bash
# 使用项目自带的采集脚本
cd tests/prometheus

# 采集基线数据（正常状态）
python collect_metrics.py --mode baseline --duration 300

# 采集故障期间数据
python collect_metrics.py --mode chaos --duration 180 --experiment cpu_stress

# 对比分析
python collect_metrics.py --mode compare --baseline metrics_baseline_xxx.json --chaos metrics_chaos_cpu_stress_xxx.json
```

#### 实验流程（故障注入 + 数据采集）

```
1. 记录基线数据（正常状态，持续 5 分钟）
   → python collect_metrics.py --mode baseline --duration 300

2. 注入故障
   → kubectl apply -f chaos-experiments/xxx.yaml

3. 记录故障期间数据（故障持续期间）
   → python collect_metrics.py --mode chaos --duration 180 --experiment xxx

4. 停止故障
   → kubectl delete -f chaos-experiments/xxx.yaml

5. 记录恢复数据（故障停止后 5 分钟）
   → 再次运行 baseline 采集

6. 对比分析
   → python collect_metrics.py --mode compare --baseline xxx --chaos yyy
```

---

## 阶段三：Selenium & JMeter 自动化测试

### 3.1 环境准备

#### 步骤 1：安装 Python 依赖

```bash
cd tests/selenium

# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

#### 步骤 2：安装 JMeter

```bash
# 下载 JMeter（如未安装）
wget https://dlcdn.apache.org//jmeter/binaries/apache-jmeter-5.6.3.zip
unzip apache-jmeter-5.6.3.zip

# 配置环境变量（Linux/Mac）
export JMETER_HOME=/path/to/apache-jmeter-5.6.3
export PATH=$JMETER_HOME/bin:$PATH

# 验证安装
jmeter --version
```

#### 步骤 3：确认前端服务地址

```bash
# 获取前端访问地址
export FRONTEND_URL=$(minikube service frontend-external --url -n default)
echo $FRONTEND_URL

# 或使用 port-forward
kubectl port-forward svc/frontend-external 8080:80 -n default
export FRONTEND_URL=http://localhost:8080
```

---

### 3.2 Selenium 功能测试

#### 测试脚本位置

- `tests/selenium/test_onlineboutique.py` - 基础功能测试（6个用例）
- `tests/selenium/test_onlineboutique_advanced.py` - 增强版（多浏览器、性能指标、响应式）
- `tests/selenium/test_chaos_resilience.py` - 故障注入期间的功能测试

#### 运行基础测试

```bash
cd tests/selenium

# 运行所有测试
python test_onlineboutique.py

# 运行指定测试
python -m unittest test_onlineboutique.OnlineBoutiqueTest.test_01_homepage_load
```

#### 运行增强测试

```bash
# 无头模式运行
HEADLESS=true python test_onlineboutique_advanced.py

# 指定浏览器
TEST_BROWSER=firefox python test_onlineboutique_advanced.py
TEST_BROWSER=edge python test_onlineboutique_advanced.py

# 跨浏览器测试
CROSS_BROWSER=true python test_onlineboutique_advanced.py
```

#### 运行故障期间测试

```bash
# 在 ChaosMesh 注入故障时运行
HEADLESS=true python test_chaos_resilience.py

# 持续运行（配合故障注入实验）
CONTINUOUS=true DURATION=180 python test_chaos_resilience.py
```

---

### 3.3 JMeter 性能测试

#### 测试计划文件位置

`tests/jmeter/onlineboutique_test_plan.jmx`

#### 运行 JMeter 测试

```bash
cd tests/jmeter
mkdir -p results report

# GUI 模式（编辑测试计划）
jmeter onlineboutique_test_plan.jmx

# 非 GUI 模式（执行测试，推荐）
jmeter -n -t onlineboutique_test_plan.jmx -l results.jtl -e -o report

# 参数说明：
# -n: 非 GUI 模式
# -t: 指定测试计划文件
# -l: 指定结果日志文件
# -e: 测试结束后生成报告
# -o: 指定报告输出目录
```

#### 查看测试结果

```bash
# 生成 HTML 报告后，用浏览器打开
open report/index.html  # Mac
# 或
start report/index.html  # Windows
```

#### 测试场景说明

| 场景 | 并发用户数 | Ramp-up | 持续时间 | 状态 |
|-----|-----------|---------|---------|------|
| 场景一：基准测试 | 10 | 30s | 5分钟 | 默认启用 |
| 场景二：负载测试 | 50 | 60s | 10分钟 | 禁用 |
| 场景三：压力测试 | 100 | 120s | 10分钟 | 禁用 |
| 场景四：峰值测试 | 200 | 180s | 5分钟 | 禁用 |

在 JMeter GUI 中启用/禁用场景：右键 Thread Group → Enable/Disable

---

## 附录：常见问题

### Q1: Grafana 仪表盘没有数据

**原因**：微服务没有暴露应用层指标（如 `http_requests_total`）。

**解决方案**：
1. 确认 Prometheus 能抓取 `kubernetes-cadvisor` 指标
2. 使用容器级别的指标：`container_cpu_usage_seconds_total`、`container_memory_usage_bytes` 等
3. 使用本项目更新后的 `grafana-dashboard.json`，它只使用可用的容器指标

### Q2: Prometheus Targets 中 kubernetes-cadvisor 显示 DOWN

**原因**：RBAC 权限不足或 Kubelet 证书问题。

**解决方案**：
1. 确认 `prometheus-rbac.yaml` 已应用
2. 确认 Prometheus Pod 使用 `serviceAccountName: prometheus`
3. 检查 Prometheus 日志：`kubectl logs -n monitoring deployment/prometheus`

### Q3: 如何给微服务添加应用层指标

如果后续需要应用层指标（如请求数、响应时间），需要修改微服务代码：

**Go 服务（frontend、checkoutservice）**：
```go
import "github.com/prometheus/client_golang/prometheus/promhttp"

// 在 main() 中添加
http.Handle("/metrics", promhttp.Handler())
```

**Python 服务（recommendationservice、emailservice、couponservice）**：
```python
from prometheus_client import start_http_server, Counter, Histogram

# 启动 metrics 服务器
start_http_server(8080)

# 定义指标
REQUEST_COUNT = Counter('http_requests_total', 'Total requests', ['method', 'status'])
REQUEST_DURATION = Histogram('request_duration_seconds', 'Request duration')
```

### Q4: ChaosMesh 实验无效果

**检查步骤**：
1. `kubectl get pods -n chaos-mesh` - 确认 ChaosMesh 组件运行正常
2. `kubectl get stresschaos,networkchaos,podchaos -n chaos-testing` - 确认实验已创建
3. 检查 Pod 选择器是否匹配：`kubectl get pods -n default -l app=frontend`
4. 查看 Chaos Dashboard 中的实验状态

### Q5: 一键运行所有测试

```bash
chmod +x tests/run_all_tests.sh
./tests/run_all_tests.sh
```

---

## 文件结构

```
tests/
├── TEST_GUIDE.md                          # 本指南
├── run_all_tests.sh                       # 一键运行所有测试
├── jmeter/
│   ├── onlineboutique_test_plan.jmx       # JMeter 性能测试计划
│   ├── README.md                          # JMeter 使用说明
│   └── results/                           # 测试结果目录
├── selenium/
│   ├── test_onlineboutique.py             # 基础 Selenium 测试
│   ├── test_onlineboutique_advanced.py    # 增强版 Selenium 测试
│   ├── test_chaos_resilience.py           # 故障期间功能测试
│   └── requirements.txt                   # Python 依赖
└── prometheus/
    ├── collect_metrics.py                 # Prometheus 数据采集工具
    └── requirements.txt                   # Python 依赖

monitoring/
├── prometheus-rbac.yaml                   # Prometheus RBAC
├── prometheus-config.yaml                 # Prometheus 配置（含 cAdvisor 抓取）
├── prometheus-deployment.yaml             # Prometheus 部署
├── grafana-deployment.yaml                # Grafana 部署
├── grafana-dashboard.json                 # 更新后的仪表盘（基于容器指标）
├── kustomization.yaml                     # Kustomize 配置
└── README.md                              # 监控部署指南

chaos-experiments/
├── cpu-stress-frontend.yaml               # CPU 压力测试
├── memory-stress-cartservice.yaml         # 内存压力测试
├── network-delay-checkoutservice.yaml     # 网络延迟测试
└── pod-kill-couponservice.yaml            # Pod 杀死测试
```
