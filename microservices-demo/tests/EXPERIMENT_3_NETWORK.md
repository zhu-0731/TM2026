# 实验三：Network Delay（checkoutservice）

## 实验配置

```yaml
# chaos-experiments/network-delay-checkoutservice.yaml
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

---

## 实验步骤

### 步骤 1：采集基线数据（5分钟）

```bash
cd tests/prometheus
python collect_metrics.py --url http://localhost:9090 --mode baseline --duration 300 --output exp3_baseline.json
```

**期间操作 Grafana：**
- 打开 http://localhost:3000
- 找到 "核心服务 CPU 对比" 面板
- 记录 checkoutservice 的基线状态
- 截图保存（基线状态）

---

### 步骤 2：注入网络延迟故障

```bash
kubectl apply -f chaos-experiments/network-delay-checkoutservice.yaml
```

**确认实验已创建：**
```bash
kubectl get networkchaos -n chaos-testing
```

**期间操作 Grafana：**
- 观察 "核心服务 CPU 对比" 面板
- 观察 frontend 响应是否变慢（间接影响）
- 等待 30 秒后截图（故障状态）

> 注：网络延迟不会直接体现在 CPU/内存指标上，但可能导致请求堆积、响应时间增加。

---

### 步骤 3：采集故障数据（3分钟）

```bash
python collect_metrics.py --url http://localhost:9090 --mode chaos --duration 180 --experiment network_delay --output exp3_chaos.json
```

**期间操作 Grafana：**
- 继续观察系统状态
- 截图保存（故障持续状态）

---

### 步骤 4：停止故障

```bash
kubectl delete -f chaos-experiments/network-delay-checkoutservice.yaml
```

**确认已删除：**
```bash
kubectl get networkchaos -n chaos-testing
```

**期间操作 Grafana：**
- 观察系统是否恢复正常
- 等待 1 分钟后截图（恢复状态）

---

### 步骤 5：对比分析

```bash
python collect_metrics.py --mode compare --baseline exp3_baseline.json --chaos exp3_chaos.json --output exp3_compare.json
```

---

## 预期结果

| 阶段 | 时间 | 系统状态 | 截图 |
|-----|------|---------|------|
| 基线 | 实验前 | 正常 | 截图1 |
| 故障 | 注入后 | 请求可能堆积 | 截图2 |
| 恢复 | 停止后 | 正常 | 截图3 |

---

## 论文可用数据

- **基线数据文件**：`exp3_baseline.json`
- **故障数据文件**：`exp3_chaos.json`
- **对比分析报告**：`exp3_compare.json`
- **Grafana 截图**：3张（基线/故障/恢复）

---

## 实验结论（待补充）

**【请做完实验后，发截图和对比分析结果给我，我会帮您写一句话结论】**
