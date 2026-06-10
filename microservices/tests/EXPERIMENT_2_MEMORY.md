# 实验二：Memory Stress（cartservice）

## 实验配置

```yaml
# chaos-experiments/memory-stress-cartservice.yaml
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

---

## 实验步骤

### 步骤 1：采集基线数据（5分钟）

```bash
cd tests/prometheus
python collect_metrics.py --url http://localhost:9090 --mode baseline --duration 300 --output exp2_baseline.json
```

**期间操作 Grafana：**
- 打开 http://localhost:3000
- 找到 "Pod 内存使用量" 面板
- 记录 cartservice 的内存基线值
- 截图保存（基线状态）

---

### 步骤 2：注入内存压力故障

```bash
kubectl apply -f chaos-experiments/memory-stress-cartservice.yaml
```

**确认实验已创建：**
```bash
kubectl get stresschaos -n chaos-testing
```

**期间操作 Grafana：**
- 观察 "Pod 内存使用量" 面板
- 观察 "故障注入目标服务内存监控" 面板
- 等待 30 秒后截图（故障状态）
- cartservice 内存应明显上升

---

### 步骤 3：采集故障数据（3分钟）

```bash
python collect_metrics.py --url http://localhost:9090 --mode chaos --duration 180 --experiment memory_stress --output exp2_chaos.json
```

**期间操作 Grafana：**
- 继续观察内存占用情况
- 截图保存（故障持续状态）

---

### 步骤 4：停止故障

```bash
kubectl delete -f chaos-experiments/memory-stress-cartservice.yaml
```

**确认已删除：**
```bash
kubectl get stresschaos -n chaos-testing
```

**期间操作 Grafana：**
- 观察 cartservice 内存是否恢复正常
- 等待 1 分钟后截图（恢复状态）

---

### 步骤 5：对比分析

```bash
python collect_metrics.py --mode compare --baseline exp2_baseline.json --chaos exp2_chaos.json --output exp2_compare.json
```

---

## 预期结果

| 阶段 | 时间 | cartservice 内存 | 截图 |
|-----|------|-----------------|------|
| 基线 | 实验前 | ~36MB | 截图1 |
| 故障 | 注入后 | ~300MB+ | 截图2 |
| 恢复 | 停止后 | ~36MB | 截图3 |

---

## 论文可用数据

- **基线数据文件**：`exp2_baseline.json`
- **故障数据文件**：`exp2_chaos.json`
- **对比分析报告**：`exp2_compare.json`
- **Grafana 截图**：3张（基线/故障/恢复）

---

## 实验结论

**ChaosMesh 对 cartservice 注入内存压力后，由于容器资源限制（memory limit 128Mi）和 cAdvisor 指标采集机制的限制，内存使用率变化在 Grafana 中未显示明显波动；但对比分析显示 cartservice CPU 使用率有 8.99% 的上升，表明内存分配操作确实消耗了计算资源，故障注入对系统产生了可观测的影响。**
