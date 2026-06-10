# ChaosMesh 故障注入实验命令（直接复制粘贴版）

> 以下命令按实验分组，可直接复制到对应窗口执行。
> **注意：必须先开两个命令行窗口，窗口1在 `tests/prometheus` 目录，窗口2在 `microservices-demo` 根目录。**

---

## 实验一：CPU 压力测试（frontend）- 已完成

### 窗口1 - 采集基线
```cmd
cd tests/prometheus
python collect_metrics.py --url http://localhost:9090 --mode baseline --duration 300 --output exp1_baseline.json
```

### 窗口2 - 注入故障
```cmd
cd E:\Testing and Maintenance\microservices-demo
kubectl apply -f chaos-experiments/cpu-stress-frontend.yaml
kubectl get stresschaos -n chaos-testing
```

### 窗口1 - 采集故障数据
```cmd
python collect_metrics.py --url http://localhost:9090 --mode chaos --duration 180 --experiment cpu_stress --output exp1_chaos.json
```

### 窗口2 - 停止故障
```cmd
kubectl delete -f chaos-experiments/cpu-stress-frontend.yaml
kubectl get stresschaos -n chaos-testing
```

### 窗口1 - 对比分析
```cmd
python collect_metrics.py --mode compare --baseline exp1_baseline.json --chaos exp1_chaos.json --output exp1_compare.json
```

---

## 实验二：内存压力测试（cartservice）

### 窗口1 - 采集基线
```cmd
cd tests/prometheus
python collect_metrics.py --url http://localhost:9090 --mode baseline --duration 300 --output exp2_baseline.json
```

### 窗口2 - 注入故障
```cmd
cd E:\Testing and Maintenance\microservices-demo
kubectl apply -f chaos-experiments/memory-stress-cartservice.yaml
kubectl get stresschaos -n chaos-testing
```

### 窗口1 - 采集故障数据
```cmd
python collect_metrics.py --url http://localhost:9090 --mode chaos --duration 180 --experiment memory_stress --output exp2_chaos.json
```

### 窗口2 - 停止故障
```cmd
kubectl delete -f chaos-experiments/memory-stress-cartservice.yaml
kubectl get stresschaos -n chaos-testing
```

### 窗口1 - 对比分析
```cmd
python collect_metrics.py --mode compare --baseline exp2_baseline.json --chaos exp2_chaos.json --output exp2_compare.json
```

---

## 实验三：网络延迟测试（checkoutservice）

### 窗口1 - 采集基线
```cmd
cd tests/prometheus
python collect_metrics.py --url http://localhost:9090 --mode baseline --duration 300 --output exp3_baseline.json
```

### 窗口2 - 注入故障
```cmd
cd E:\Testing and Maintenance\microservices-demo
kubectl apply -f chaos-experiments/network-delay-checkoutservice.yaml
kubectl get networkchaos -n chaos-testing
```

### 窗口1 - 采集故障数据
```cmd
python collect_metrics.py --url http://localhost:9090 --mode chaos --duration 180 --experiment network_delay --output exp3_chaos.json
```

### 窗口2 - 停止故障
```cmd
kubectl delete -f chaos-experiments/network-delay-checkoutservice.yaml
kubectl get networkchaos -n chaos-testing
```

### 窗口1 - 对比分析
```cmd
python collect_metrics.py --mode compare --baseline exp3_baseline.json --chaos exp3_chaos.json --output exp3_compare.json
```

---

## 实验四：Pod 杀死测试（couponservice）

### 窗口1 - 采集基线
```cmd
cd tests/prometheus
python collect_metrics.py --url http://localhost:9090 --mode baseline --duration 300 --output exp4_baseline.json
```

### 窗口2 - 注入故障
```cmd
cd E:\Testing and Maintenance\microservices-demo
kubectl apply -f chaos-experiments/pod-kill-couponservice.yaml
kubectl get podchaos -n chaos-testing
```

### 窗口1 - 采集故障数据
```cmd
python collect_metrics.py --url http://localhost:9090 --mode chaos --duration 180 --experiment pod_kill --output exp4_chaos.json
```

### 窗口2 - 停止故障
```cmd
kubectl delete -f chaos-experiments/pod-kill-couponservice.yaml
kubectl get podchaos -n chaos-testing
```

### 窗口1 - 对比分析
```cmd
python collect_metrics.py --mode compare --baseline exp4_baseline.json --chaos exp4_chaos.json --output exp4_compare.json
```

---

## 实验清理（全部完成后执行）

```cmd
kubectl delete stresschaos --all -n chaos-testing
kubectl delete networkchaos --all -n chaos-testing
kubectl delete podchaos --all -n chaos-testing
```

---

## 文件命名对照表

| 实验 | 基线文件 | 故障文件 | 对比文件 |
|-----|---------|---------|---------|
| 实验一 CPU | exp1_baseline.json | exp1_chaos.json | exp1_compare.json |
| 实验二 内存 | exp2_baseline.json | exp2_chaos.json | exp2_compare.json |
| 实验三 网络 | exp3_baseline.json | exp3_chaos.json | exp3_compare.json |
| 实验四 Pod Kill | exp4_baseline.json | exp4_chaos.json | exp4_compare.json |

---

## 截图时机提醒

| 实验 | 截图1（基线） | 截图2（故障） | 截图3（恢复） |
|-----|------------|------------|------------|
| 实验一 CPU | Pod CPU 使用率 | 核心服务 CPU 对比 | CPU 回落 |
| 实验二 内存 | Pod 内存使用量 | 故障注入内存监控 | 内存回落 |
| 实验三 网络 | 核心服务 CPU 对比 | 核心服务 CPU 对比 | CPU 恢复 |
| 实验四 Pod Kill | kubectl get pods | kubectl get pods（重启中） | kubectl get pods（已恢复） |
