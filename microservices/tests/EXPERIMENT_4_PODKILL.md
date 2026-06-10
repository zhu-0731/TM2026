# 实验四：Pod Kill（couponservice）

## 实验配置

```yaml
# chaos-experiments/pod-kill-couponservice.yaml
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

---

## 实验步骤

### 步骤 1：采集基线数据（5分钟）

```bash
cd tests/prometheus
python collect_metrics.py --url http://localhost:9090 --mode baseline --duration 300 --output exp4_baseline.json
```

**期间操作 kubectl：**
- 记录 couponservice Pod 名称
- 截图保存（基线状态）

```bash
kubectl get pods -n default | findstr couponservice
```

---

### 步骤 2：注入 Pod 杀死故障

```bash
kubectl apply -f chaos-experiments/pod-kill-couponservice.yaml
```

**确认实验已创建：**
```bash
kubectl get podchaos -n chaos-testing
```

**期间操作 kubectl：**
- 持续观察 couponservice Pod 状态
- Pod 会被杀死并重新创建
- 记录 Pod 名称变化
- 截图保存（故障状态）

```bash
kubectl get pods -n default | findstr couponservice
```

---

### 步骤 3：采集故障数据（3分钟）

```bash
python collect_metrics.py --url http://localhost:9090 --mode chaos --duration 180 --experiment pod_kill --output exp4_chaos.json
```

**期间操作 kubectl：**
- 继续观察 Pod 重启情况
- 截图保存（故障持续状态）

---

### 步骤 4：停止故障

```bash
kubectl delete -f chaos-experiments/pod-kill-couponservice.yaml
```

**确认已删除：**
```bash
kubectl get podchaos -n chaos-testing
```

**期间操作 kubectl：**
- 确认 couponservice Pod 稳定运行
- 截图保存（恢复状态）

---

### 步骤 5：对比分析

```bash
python collect_metrics.py --mode compare --baseline exp4_baseline.json --chaos exp4_chaos.json --output exp4_compare.json
```

---

## 预期结果

| 阶段 | 时间 | couponservice Pod | 截图 |
|-----|------|------------------|------|
| 基线 | 实验前 | Running，名称稳定 | 截图1 |
| 故障 | 注入后 | 被杀死，重新创建，名称变化 | 截图2 |
| 恢复 | 停止后 | Running，名称稳定 | 截图3 |

---

## 论文可用数据

- **基线数据文件**：`exp4_baseline.json`
- **故障数据文件**：`exp4_chaos.json`
- **对比分析报告**：`exp4_compare.json`
- **kubectl 截图**：3张（基线/故障/恢复）

---

## 实验结论（待补充）

**【请做完实验后，发截图和对比分析结果给我，我会帮您写一句话结论】**
