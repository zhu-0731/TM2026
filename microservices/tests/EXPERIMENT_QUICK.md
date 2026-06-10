# 快速实验指南 - 确保数据准确

## 重要提醒

1. **必须开两个命令行窗口**
   - 窗口1：在 `tests/prometheus` 目录运行采集脚本
   - 窗口2：在 `microservices-demo` 根目录运行 kubectl

2. **必须先注入故障，再采集故障数据**
   - 如果故障没运行，采集到的就是正常数据

3. **文件名必须对应**
   - baseline → chaos → compare 三个文件名要一致

---

## 实验一：CPU Stress（完整流程）

### 窗口1 - 采集基线（5分钟）

```cmd
cd tests/prometheus
python collect_metrics.py --url http://localhost:9090 --mode baseline --duration 300 --output exp1_baseline.json
```

等待5分钟...

### 窗口2 - 注入故障

```cmd
cd E:\Testing and Maintenance\microservices-demo
kubectl apply -f chaos-experiments/cpu-stress-frontend.yaml
kubectl get stresschaos -n chaos-testing
```

确认看到 `cpu-stress-frontend` 状态为 Running

### 窗口1 - 采集故障数据（3分钟）

等基线采集完成后，立即执行：

```cmd
python collect_metrics.py --url http://localhost:9090 --mode chaos --duration 180 --experiment cpu_stress --output exp1_chaos.json
```

等待3分钟...

### 窗口2 - 停止故障

```cmd
kubectl delete -f chaos-experiments/cpu-stress-frontend.yaml
kubectl get stresschaos -n chaos-testing
```

确认显示 No resources found

### 窗口1 - 对比分析

```cmd
python collect_metrics.py --mode compare --baseline exp1_baseline.json --chaos exp1_chaos.json --output exp1_compare.json
```

---

## 预期结果

如果实验成功，对比分析应该显示：

```
pod_cpu_usage_frontend:
  基线: 0.003000
  故障: 0.800000
  变化: +25000% ↑
```

如果变化只有 ±5%，说明：
- ❌ 故障注入时 Pod 还没启动
- ❌ 采集时故障已结束
- ❌ 采集的是正常状态

---

## 验证故障是否生效

### 方法1：看 Grafana
1. 打开 http://localhost:3000
2. 找到 "核心服务 CPU 对比" 面板
3. frontend 的线应该飙升到接近 100%

### 方法2：看 Prometheus
```cmd
curl -s "http://localhost:9090/api/v1/query?query=rate(container_cpu_usage_seconds_total%7Bnamespace%3D%22default%22%2Cpod%3D~%22frontend-.*%22%7D%5B5m%5D)"
```

值应该接近 0.8 或更高（80%+ CPU）

### 方法3：看 Chaos Dashboard
```cmd
kubectl port-forward -n chaos-testing svc/chaos-dashboard 2333:2333
```
浏览器访问 http://localhost:2333

---

## 其他三个实验

只需替换故障文件名和输出文件名：

### 实验二：Memory Stress
```cmd
kubectl apply -f chaos-experiments/memory-stress-cartservice.yaml
python collect_metrics.py --url http://localhost:9090 --mode chaos --duration 180 --experiment memory_stress --output exp2_chaos.json
kubectl delete -f chaos-experiments/memory-stress-cartservice.yaml
```

### 实验三：Network Delay
```cmd
kubectl apply -f chaos-experiments/network-delay-checkoutservice.yaml
python collect_metrics.py --url http://localhost:9090 --mode chaos --duration 180 --experiment network_delay --output exp3_chaos.json
kubectl delete -f chaos-experiments/network-delay-checkoutservice.yaml
```

### 实验四：Pod Kill
```cmd
kubectl apply -f chaos-experiments/pod-kill-couponservice.yaml
python collect_metrics.py --url http://localhost:9090 --mode chaos --duration 180 --experiment pod_kill --output exp4_chaos.json
kubectl delete -f chaos-experiments/pod-kill-couponservice.yaml
```

---

## 截图清单

每个实验需要3张截图：

| 时机 | 截图内容 | Grafana 面板 |
|-----|---------|-------------|
| 基线 | 正常状态 | Pod CPU 使用率 / Pod 内存使用量 |
| 故障 | 注入后30秒 | 同上，观察飙升 |
| 恢复 | 停止后1分钟 | 同上，观察回落 |

---

## 文件命名规范

```
exp1_baseline.json    - CPU 基线
exp1_chaos.json       - CPU 故障
exp1_compare.json     - CPU 对比

exp2_baseline.json    - 内存基线
exp2_chaos.json       - 内存故障
exp2_compare.json     - 内存对比

exp3_baseline.json    - 网络基线
exp3_chaos.json       - 网络故障
exp3_compare.json     - 网络对比

exp4_baseline.json    - Pod Kill 基线
exp4_chaos.json       - Pod Kill 故障
exp4_compare.json     - Pod Kill 对比
```
