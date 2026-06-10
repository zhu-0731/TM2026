# ChaosMesh 故障注入实验指南

> 本指南记录 OnlineBoutique 微服务系统中 ChaosMesh 的部署与 4 种故障注入实验的完整步骤。

---

## 目录

- [环境检查](#环境检查)
- [ChaosMesh 部署](#chaosmesh-部署)
- [故障注入实验](#故障注入实验)
  - [实验 1：CPU 压力测试（frontend）](#实验-1cpu-压力测试frontend)
  - [实验 2：内存压力测试（cartservice）](#实验-2内存压力测试cartservice)
  - [实验 3：网络延迟测试（checkoutservice）](#实验-3网络延迟测试checkoutservice)
  - [实验 4：Pod 杀死测试（couponservice）](#实验-4pod-杀死测试couponservice)
- [实验数据采集](#实验数据采集)
- [实验清理](#实验清理)
- [常见问题](#常见问题)

---

## 环境检查

### 1. 确认微服务正常运行

```bash
kubectl get pods -n default
```

所有 Pod 状态应为 `Running`：

```
NAME                                     READY   STATUS    RESTARTS   AGE
frontend-d756b6c99-nxnbk                 1/1     Running   0          10m
checkoutservice-596f6b78bb-zrv6k         1/1     Running   0          10m
cartservice-6d8596764d-hgnrr             1/1     Running   0          10m
couponservice-75bfd5cff5-kj4mk           1/1     Running   0          10m
...
```

### 2. 确认 Prometheus 和 Grafana 正常运行

```bash
kubectl get pods -n monitoring
```

```
NAME                                  READY   STATUS    RESTARTS   AGE
prometheus-6dd4994988-p6svh         1/1     Running   0          2h
grafana-65c78f747d-95cmq            1/1     Running   0          3h
```

### 3. 确认前端可访问

```bash
# 获取访问地址
minikube service frontend-external --url -n default

# 或 port-forward
kubectl port-forward svc/frontend-external 8080:80 -n default
# 访问: http://localhost:8080
```

---

## ChaosMesh 部署

### 方式一：Helm 安装（推荐）

```bash
# 添加 Helm 仓库
helm repo add chaos-mesh https://charts.chaos-mesh.org
helm repo update

# 安装 ChaosMesh
helm install chaos-mesh chaos-mesh/chaos-mesh \
  -n chaos-mesh \
  --create-namespace \
  --version 2.6.3
```

### 方式二：脚本安装

```bash
# 使用官方安装脚本
curl -sSL https://mirrors.chaos-mesh.org/v2.6.3/install.sh | bash
```

### 验证安装

```bash
# 查看 ChaosMesh 组件 Pod
kubectl get pods -n chaos-mesh
```

预期输出：

```
NAME                                        READY   STATUS    RESTARTS   AGE
chaos-controller-manager-xxx                1/1     Running   0          2m
chaos-daemon-xxx                            1/1     Running   0          2m
chaos-dashboard-xxx                         1/1     Running   0          2m
```

### 访问 Chaos Dashboard

```bash
kubectl port-forward -n chaos-mesh svc/chaos-dashboard 2333:2333
```

浏览器访问：`http://localhost:2333`

---

## 故障注入实验

### 实验准备

```bash
# 创建实验命名空间
kubectl create namespace chaos-testing 2>/dev/null || true

# 确认 Prometheus 数据正常
curl -s "http://localhost:9090/api/v1/query?query=rate(container_cpu_usage_seconds_total{namespace=\"default\"}[5m])" | head -c 100
```

---

### 实验 1：CPU 压力测试（frontend）

**目标：** 对 frontend 服务注入 CPU 压力，观察 CPU 使用率飙升

**实验配置：** `chaos-experiments/cpu-stress-frontend.yaml`

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: StressChaos
metadata:
  name: cpu-stress-frontend
  namespace: chaos-testing
spec:
  mode: one
  selector:
    namespaces:
      - default
    labelSelectors:
      app: frontend
  stressors:
    cpu:
      workers: 2
      load: 80
  duration: "180s"
```

**执行步骤：**

```bash
# 1. 记录基线数据（开始前在 Grafana 截图或记录）
# 观察: Pod CPU 使用率面板，frontend CPU 应在 1-3%

# 2. 注入故障
echo "=== 注入 CPU 压力到 frontend ==="
kubectl apply -f chaos-experiments/cpu-stress-frontend.yaml

# 3. 观察指标变化（在 Grafana 或 Prometheus 中）
# - Pod CPU 使用率面板: frontend CPU 应飙升到 80%+
# - 故障注入 CPU 监控面板: frontend 线条急剧上升

# 4. 等待 3 分钟（180秒），或手动停止
sleep 180

# 5. 停止故障
echo "=== 停止 CPU 压力 ==="
kubectl delete -f chaos-experiments/cpu-stress-frontend.yaml

# 6. 观察恢复（约 30-60 秒后 CPU 恢复正常）
```

**预期现象：**

| 阶段 | frontend CPU | 其他服务 |
|-----|-------------|---------|
| 基线 | 1-3% | 正常 |
| 故障注入 | 80%+ | 正常 |
| 停止后 | 逐渐恢复至 1-3% | 正常 |

---

### 实验 2：内存压力测试（cartservice）

**目标：** 对 cartservice 注入内存压力，观察内存使用量上升

**实验配置：** `chaos-experiments/memory-stress-cartservice.yaml`

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: StressChaos
metadata:
  name: memory-stress-cartservice
  namespace: chaos-testing
spec:
  mode: one
  selector:
    namespaces:
      - default
    labelSelectors:
      app: cartservice
  stressors:
    memory:
      workers: 1
      size: "256MB"
  duration: "180s"
```

**执行步骤：**

```bash
# 1. 记录基线数据
# 观察: Pod 内存使用量面板，cartservice 内存应在 20-50MB

# 2. 注入故障
echo "=== 注入内存压力到 cartservice ==="
kubectl apply -f chaos-experiments/memory-stress-cartservice.yaml

# 3. 观察指标变化
# - Pod 内存使用量面板: cartservice 内存应增加 256MB
# - 故障注入内存监控面板: cartservice 线条上升

# 4. 等待 3 分钟或手动停止
sleep 180

# 5. 停止故障
echo "=== 停止内存压力 ==="
kubectl delete -f chaos-experiments/memory-stress-cartservice.yaml

# 6. 观察恢复
```

**预期现象：**

| 阶段 | cartservice 内存 | 说明 |
|-----|-----------------|------|
| 基线 | 20-50MB | 正常 |
| 故障注入 | +256MB | 内存压力注入 |
| 停止后 | 恢复基线 | 压力释放 |

---

### 实验 3：网络延迟测试（checkoutservice）

**目标：** 对 checkoutservice 注入网络延迟，观察服务响应变慢

**实验配置：** `chaos-experiments/network-delay-checkoutservice.yaml`

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: network-delay-checkoutservice
  namespace: chaos-testing
spec:
  action: delay
  mode: one
  selector:
    namespaces:
      - default
    labelSelectors:
      app: checkoutservice
  delay:
    latency: "200ms"
    correlation: "100"
    jitter: "10ms"
  duration: "180s"
```

**执行步骤：**

```bash
# 1. 记录基线数据
# 观察: 核心服务 CPU 对比面板，所有服务正常

# 2. 注入故障
echo "=== 注入网络延迟到 checkoutservice ==="
kubectl apply -f chaos-experiments/network-delay-checkoutservice.yaml

# 3. 观察影响
# 由于 cAdvisor 不直接提供网络延迟指标，需要通过以下方式观察:
# - 前端页面响应变慢（下单操作延迟增加）
# - 核心服务 CPU 对比: checkoutservice 可能有变化

# 4. 使用 Selenium 测试前端响应
cd tests/selenium
HEADLESS=true python test_chaos_resilience.py

# 5. 等待 3 分钟或手动停止
sleep 180

# 6. 停止故障
echo "=== 停止网络延迟 ==="
kubectl delete -f chaos-experiments/network-delay-checkoutservice.yaml
```

**预期现象：**

| 阶段 | 前端响应 | 下单操作 |
|-----|---------|---------|
| 基线 | < 1s | 正常 |
| 故障注入 | 明显变慢 | 延迟增加 200ms+ |
| 停止后 | 恢复正常 | 正常 |

---

### 实验 4：Pod 杀死测试（couponservice）

**目标：** 随机杀死 couponservice Pod，观察服务恢复能力

**实验配置：** `chaos-experiments/pod-kill-couponservice.yaml`

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: pod-kill-couponservice
  namespace: chaos-testing
spec:
  action: pod-kill
  mode: one
  selector:
    namespaces:
      - default
    labelSelectors:
      app: couponservice
  duration: "180s"
```

**执行步骤：**

```bash
# 1. 记录基线数据
# 观察: Pod CPU 使用率面板，couponservice 正常运行

# 2. 注入故障
echo "=== 开始杀死 couponservice Pod ==="
kubectl apply -f chaos-experiments/pod-kill-couponservice.yaml

# 3. 实时观察 Pod 状态
watch kubectl get pods -n default | grep couponservice

# 预期输出变化:
# couponservice-75bfd5cff5-kj4mk   1/1   Running   0   5m
# couponservice-75bfd5cff5-kj4mk   0/1   Error     0   5m  (被杀死)
# couponservice-75bfd5cff5-xxx     0/1   ContainerCreating   0   0s  (新 Pod)
# couponservice-75bfd5cff5-xxx     1/1   Running   0   10s  (恢复)

# 4. 在 Grafana 观察
# - Pod CPU 使用率: couponservice 线条中断后恢复
# - Pod 内存使用量: couponservice 线条中断后恢复

# 5. 等待 3 分钟或手动停止
sleep 180

# 6. 停止故障
echo "=== 停止 Pod 杀死 ==="
kubectl delete -f chaos-experiments/pod-kill-couponservice.yaml
```

**预期现象：**

| 阶段 | couponservice Pod | 其他服务 |
|-----|------------------|---------|
| 基线 | Running | 正常 |
| 故障注入 | 被杀死 → 重建 → Running | 正常 |
| 停止后 | 稳定 Running | 正常 |

---

## 实验数据采集

### 使用 Prometheus 采集脚本

```bash
cd tests/prometheus

# 1. 采集正常状态基线（实验前）
python collect_metrics.py \
  --url http://localhost:9090 \
  --mode baseline \
  --duration 300 \
  --output baseline_metrics.json

# 2. 注入故障并采集故障期间数据
kubectl apply -f ../../chaos-experiments/cpu-stress-frontend.yaml

python collect_metrics.py \
  --url http://localhost:9090 \
  --mode chaos \
  --duration 180 \
  --experiment cpu_stress \
  --output chaos_cpu_metrics.json

kubectl delete -f ../../chaos-experiments/cpu-stress-frontend.yaml

# 3. 对比分析
python collect_metrics.py \
  --mode compare \
  --baseline baseline_metrics.json \
  --chaos chaos_cpu_metrics.json \
  --output comparison_cpu.json
```

### 手动采集关键指标

```bash
# 在实验期间，每 30 秒记录一次
for i in {1..10}; do
  echo "=== 采样 $i ==="
  echo "时间: $(date)"
  
  # CPU
  curl -s "http://localhost:9090/api/v1/query?query=rate(container_cpu_usage_seconds_total%7Bnamespace%3D%22default%22%2Cpod%3D~%22frontend-.*%22%7D%5B5m%5D)" | grep -o '"value":\[[^]]*\]'
  
  # 内存
  curl -s "http://localhost:9090/api/v1/query?query=container_memory_usage_bytes%7Bnamespace%3D%22default%22%2Cpod%3D~%22frontend-.*%22%7D" | grep -o '"value":\[[^]]*\]'
  
  sleep 30
done
```

---

## 实验清理

### 删除所有故障注入实验

```bash
# 删除所有 ChaosMesh 实验
kubectl delete stresschaos --all -n chaos-testing
kubectl delete networkchaos --all -n chaos-testing
kubectl delete podchaos --all -n chaos-testing

# 或一键删除
kubectl delete -f chaos-experiments/ --ignore-not-found=true
```

### 验证清理

```bash
# 确认没有运行的实验
kubectl get stresschaos,networkchaos,podchaos -n chaos-testing

# 预期输出: No resources found
```

### 卸载 ChaosMesh（如需完全移除）

```bash
helm uninstall chaos-mesh -n chaos-mesh
kubectl delete namespace chaos-mesh
```

---

## 常见问题

### Q1: ChaosMesh 实验无效果

**检查：**
```bash
# 1. 检查 ChaosMesh 组件是否运行
kubectl get pods -n chaos-mesh

# 2. 检查实验状态
kubectl describe stresschaos cpu-stress-frontend -n chaos-testing

# 3. 检查 Pod 选择器是否匹配
kubectl get pods -n default -l app=frontend
```

### Q2: 故障注入后 Grafana 看不到变化

**检查：**
```bash
# 1. 确认 Prometheus 能抓取到指标
curl -s "http://localhost:9090/api/v1/query?query=rate(container_cpu_usage_seconds_total%7Bnamespace%3D%22default%22%7D%5B5m%5D)"

# 2. 确认 Grafana 时间范围正确（Last 5 minutes）

# 3. 确认 Grafana 刷新间隔（10s）
```

### Q3: Pod 杀死实验后服务不恢复

**检查：**
```bash
# 查看 Pod 状态
kubectl get pods -n default

# 查看事件
kubectl get events -n default --sort-by='.lastTimestamp' | tail -20

# 手动删除异常 Pod（Deployment 会自动重建）
kubectl delete pod <pod-name> -n default
```

### Q4: 如何同时注入多种故障

```bash
# 可以同时应用多个实验
kubectl apply -f chaos-experiments/cpu-stress-frontend.yaml
kubectl apply -f chaos-experiments/memory-stress-cartservice.yaml

# 观察复合故障的影响

# 分别停止
kubectl delete -f chaos-experiments/cpu-stress-frontend.yaml
kubectl delete -f chaos-experiments/memory-stress-cartservice.yaml
```

---

## 实验记录模板

| 实验 | 目标服务 | 故障类型 | 持续时间 | 基线 CPU | 基线内存 | 峰值 CPU | 峰值内存 | 恢复时间 | 备注 |
|-----|---------|---------|---------|---------|---------|---------|---------|---------|------|
| 1 | frontend | CPU Stress | 180s | | | | | | |
| 2 | cartservice | Memory Stress | 180s | | | | | | |
| 3 | checkoutservice | Network Delay | 180s | | | | | | |
| 4 | couponservice | Pod Kill | 180s | | | | | | |
