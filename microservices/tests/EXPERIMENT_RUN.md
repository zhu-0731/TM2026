# ChaosMesh 故障注入实验 - 直接复制粘贴版

> 以下命令可直接复制到 Windows 命令行执行，无需修改。

---

## 前置检查

```bash
cd tests/prometheus

# 检查 Prometheus 是否可访问
curl -s http://localhost:9090/api/v1/query?query=up | findstr "status"
```

如果 Prometheus 未启动，先执行：
```bash
kubectl port-forward svc/prometheus -n monitoring 9090:9090
```

---

## 实验一：CPU 压力测试（frontend）

### 步骤 1：采集基线数据（5分钟）

打开第一个命令行窗口，执行：

```bash
cd tests/prometheus
python collect_metrics.py --url http://localhost:9090 --mode baseline --duration 300 --output baseline_cpu.json
```

**期间操作 Grafana：**
1. 打开 http://localhost:3000
2. 找到 "Pod CPU 使用率" 面板
3. 截图保存（基线状态）

---

### 步骤 2：注入 CPU 故障

打开第二个命令行窗口，执行：

```bash
kubectl apply -f chaos-experiments/cpu-stress-frontend.yaml
```

确认实验已创建：
```bash
kubectl get stresschaos -n chaos-testing
```

**期间操作 Grafana：**
1. 观察 "Pod CPU 使用率" 面板
2. 观察 "核心服务 CPU 对比" 面板
3. 等待 30 秒后截图（故障状态）

---

### 步骤 3：采集故障数据（3分钟）

在第一个窗口（基线采集完成后），执行：

```bash
python collect_metrics.py --url http://localhost:9090 --mode chaos --duration 180 --experiment cpu_stress --output chaos_cpu.json
```

**期间操作 Grafana：**
1. 继续观察 CPU 飙升
2. 截图保存（故障持续状态）

---

### 步骤 4：停止故障

在第二个窗口，执行：

```bash
kubectl delete -f chaos-experiments/cpu-stress-frontend.yaml
```

确认已删除：
```bash
kubectl get stresschaos -n chaos-testing
```

**期间操作 Grafana：**
1. 观察 CPU 是否恢复正常
2. 等待 1 分钟后截图（恢复状态）

---

### 步骤 5：对比分析

在第一个窗口，执行：

```bash
python collect_metrics.py --mode compare --baseline baseline_cpu.json --chaos chaos_cpu.json --output comparison_cpu.json
```

---

## 实验二：内存压力测试（cartservice）

### 步骤 1：采集基线

```bash
python collect_metrics.py --url http://localhost:9090 --mode baseline --duration 300 --output baseline_memory.json
```

**Grafana 截图：** "Pod 内存使用量" 面板（基线）

---

### 步骤 2：注入内存故障

```bash
kubectl apply -f chaos-experiments/memory-stress-cartservice.yaml
```

确认：
```bash
kubectl get stresschaos -n chaos-testing
```

**Grafana 截图：** "Pod 内存使用量" 面板（故障）

---

### 步骤 3：采集故障数据

```bash
python collect_metrics.py --url http://localhost:9090 --mode chaos --duration 180 --experiment memory_stress --output chaos_memory.json
```

---

### 步骤 4：停止故障

```bash
kubectl delete -f chaos-experiments/memory-stress-cartservice.yaml
```

**Grafana 截图：** "Pod 内存使用量" 面板（恢复）

---

### 步骤 5：对比分析

```bash
python collect_metrics.py --mode compare --baseline baseline_memory.json --chaos chaos_memory.json --output comparison_memory.json
```

---

## 实验三：网络延迟测试（checkoutservice）

### 步骤 1：采集基线

```bash
python collect_metrics.py --url http://localhost:9090 --mode baseline --duration 300 --output baseline_network.json
```

---

### 步骤 2：注入网络延迟

```bash
kubectl apply -f chaos-experiments/network-delay-checkoutservice.yaml
```

确认：
```bash
kubectl get networkchaos -n chaos-testing
```

---

### 步骤 3：采集故障数据

```bash
python collect_metrics.py --url http://localhost:9090 --mode chaos --duration 180 --experiment network_delay --output chaos_network.json
```

---

### 步骤 4：停止故障

```bash
kubectl delete -f chaos-experiments/network-delay-checkoutservice.yaml
```

---

### 步骤 5：对比分析

```bash
python collect_metrics.py --mode compare --baseline baseline_network.json --chaos chaos_network.json --output comparison_network.json
```

---

## 实验四：Pod 杀死测试（couponservice）

### 步骤 1：采集基线

```bash
python collect_metrics.py --url http://localhost:9090 --mode baseline --duration 300 --output baseline_podkill.json
```

---

### 步骤 2：注入 Pod 杀死

```bash
kubectl apply -f chaos-experiments/pod-kill-couponservice.yaml
```

确认：
```bash
kubectl get podchaos -n chaos-testing
```

---

### 步骤 3：采集故障数据

```bash
python collect_metrics.py --url http://localhost:9090 --mode chaos --duration 180 --experiment pod_kill --output chaos_podkill.json
```

---

### 步骤 4：停止故障

```bash
kubectl delete -f chaos-experiments/pod-kill-couponservice.yaml
```

---

### 步骤 5：对比分析

```bash
python collect_metrics.py --mode compare --baseline baseline_podkill.json --chaos chaos_podkill.json --output comparison_podkill.json
```

---

## 实验清理

```bash
kubectl delete stresschaos --all -n chaos-testing
kubectl delete networkchaos --all -n chaos-testing
kubectl delete podchaos --all -n chaos-testing
```

---

## 论文截图清单

| 实验 | 截图内容 | 用途 |
|-----|---------|------|
| CPU Stress | Grafana Pod CPU 使用率（基线/故障/恢复） | 展示 CPU 飙升 |
| Memory Stress | Grafana Pod 内存使用量（基线/故障/恢复） | 展示内存上升 |
| Network Delay | Grafana 核心服务 CPU 对比 | 展示延迟影响 |
| Pod Kill | kubectl get pods 命令输出 | 展示 Pod 重启 |

---

## 生成的数据文件

```
tests/prometheus/
├── baseline_cpu.json          # CPU 基线数据
├── chaos_cpu.json             # CPU 故障数据
├── comparison_cpu.json        # CPU 对比分析
├── baseline_memory.json       # 内存基线数据
├── chaos_memory.json          # 内存故障数据
├── comparison_memory.json     # 内存对比分析
├── baseline_network.json      # 网络基线数据
├── chaos_network.json         # 网络故障数据
├── comparison_network.json    # 网络对比分析
├── baseline_podkill.json      # Pod Kill 基线数据
├── chaos_podkill.json         # Pod Kill 故障数据
└── comparison_podkill.json    # Pod Kill 对比分析
```
