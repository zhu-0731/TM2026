# ChaosMesh + Prometheus 故障注入实验指南（精简版）

> 只做一个 CPU Stress 实验，采集基线和故障数据，进行对比分析。

---

## 前置条件

```bash
# 1. 确认微服务运行正常
kubectl get pods -n default

# 2. 确认 Prometheus 运行正常
kubectl get pods -n monitoring

# 3. 确认 ChaosMesh 运行正常
kubectl get pods -n chaos-testing

# 4. 确认 Grafana 可访问
kubectl port-forward svc/grafana -n monitoring 3000:3000
# 浏览器访问 http://localhost:3000
```

---

## 实验步骤

### 步骤 1：采集正常状态基线（5分钟）

```bash
cd tests/prometheus

python collect_metrics.py \
  --url http://localhost:9090 \
  --mode baseline \
  --duration 300 \
  --output baseline_metrics.json
```

**期间观察 Grafana：**
- 打开 "Pod CPU 使用率" 面板
- 记录 frontend 的 CPU 基线值（约 0.5%~1%）
- 截图保存

---

### 步骤 2：注入 CPU 压力故障

```bash
# 注入故障
kubectl apply -f chaos-experiments/cpu-stress-frontend.yaml

# 确认实验已创建
kubectl get stresschaos -n chaos-testing
```

**实验配置：**
- 目标：frontend Pod
- 负载：2 个 worker，80% CPU
- 持续时间：180 秒（3分钟）

---

### 步骤 3：采集故障期间数据（3分钟）

```bash
# 在另一个终端窗口执行
python collect_metrics.py \
  --url http://localhost:9090 \
  --mode chaos \
  --duration 180 \
  --experiment cpu_stress \
  --output chaos_cpu_metrics.json
```

**期间观察 Grafana：**
- 观察 "Pod CPU 使用率" 面板中 frontend CPU 飙升
- 观察 "核心服务 CPU 对比" 面板
- 截图保存故障期间状态

---

### 步骤 4：停止故障

```bash
# 180 秒后故障自动停止，或手动删除
kubectl delete -f chaos-experiments/cpu-stress-frontend.yaml

# 确认实验已删除
kubectl get stresschaos -n chaos-testing
# 预期输出: No resources found
```

**观察恢复：**
- 在 Grafana 中观察 frontend CPU 是否恢复正常
- 截图保存恢复状态

---

### 步骤 5：对比分析

```bash
python collect_metrics.py \
  --mode compare \
  --baseline baseline_metrics.json \
  --chaos chaos_cpu_metrics.json \
  --output comparison_cpu.json
```

**输出示例：**
```
对比分析: 正常状态 vs 故障状态
============================================================

  pod_cpu_usage:
    基线: 0.008500
    故障: 0.825000
    变化: +9605.88% ↑

  pod_memory_usage:
    基线: 64.500000
    故障: 65.200000
    变化: +1.09% ↑
```

---

## 手动验证关键指标

```bash
# 在实验期间，每 30 秒记录一次 frontend CPU
for i in {1..10}; do
  echo "=== 采样 $i - $(date) ==="
  
  curl -s "http://localhost:9090/api/v1/query?query=rate(container_cpu_usage_seconds_total%7Bnamespace%3D%22default%22%2Cpod%3D~%22frontend-.*%22%7D%5B5m%5D)" | grep -o '"value":\[[^]]*\]'
  
  sleep 30
done
```

---

## 实验数据汇总

| 阶段 | 时间 | CPU 使用率 | 截图 |
|-----|------|-----------|------|
| 基线 | 实验前 | ~0.5% | 截图1 |
| 故障 | 注入后 | ~80%+ | 截图2 |
| 恢复 | 停止后 | ~0.5% | 截图3 |

---

## 论文可用数据

1. **基线数据文件**：`baseline_metrics.json`
2. **故障数据文件**：`chaos_cpu_metrics.json`
3. **对比分析报告**：`comparison_cpu.json`
4. **Grafana 截图**：3张（基线/故障/恢复）

---

## 清理

```bash
# 删除实验
kubectl delete -f chaos-experiments/ --ignore-not-found=true

# 确认清理
kubectl get stresschaos,networkchaos,podchaos -n chaos-testing
```

---

## 常见问题

**Q: 故障注入后 Grafana 没有明显变化？**
A: 检查是否正确选择了时间范围（Last 5 minutes），并点击 Refresh 按钮。

**Q: CPU 没有飙升到 80%？**
A: 可能是 Pod 资源限制导致。检查 frontend 的 resources.limits.cpu 是否为 200m，这样最多只能用到 20% 节点 CPU。

**Q: 采集脚本报错？**
A: 确保 Prometheus port-forward 正常：`kubectl port-forward svc/prometheus -n monitoring 9090:9090`
