# JMeter 性能测试说明

## 测试计划文件

- `onlineboutique_test_plan.jmx` - OnlineBoutique 微服务系统性能测试计划

## 测试场景

| 场景 | 并发用户数 | Ramp-up | 循环次数 | 持续时间 | 状态 |
|-----|-----------|---------|---------|---------|------|
| 场景一：基准测试 | 10 | 30s | 10 | 5分钟 | 默认启用 |
| 场景二：负载测试 | 50 | 60s | 20 | 10分钟 | 禁用 |
| 场景三：压力测试 | 100 | 120s | 30 | 10分钟 | 禁用 |
| 场景四：峰值测试 | 200 | 180s | 50 | 5分钟 | 禁用 |

## 修改目标地址

编辑 `onlineboutique_test_plan.jmx`，找到用户定义的变量：

```xml
<elementProp name="BASE_URL" elementType="Argument">
  <stringProp name="Argument.value">localhost</stringProp>
</elementProp>
```

将 `localhost` 改为你的 Minikube IP 或实际地址。

## 运行测试

### GUI 模式（编辑/调试）

```bash
jmeter onlineboutique_test_plan.jmx
```

### 非 GUI 模式（正式执行）

```bash
# 创建结果目录
mkdir results

# 执行测试
jmeter -n -t onlineboutique_test_plan.jmx -l results/baseline.jtl -e -o report/baseline
```

### 结合故障注入的测试

```bash
# 1. 基线测试
jmeter -n -t onlineboutique_test_plan.jmx -l results/baseline.jtl -e -o report/baseline

# 2. 注入故障
kubectl apply -f ../../chaos-experiments/cpu-stress-frontend.yaml

# 3. 故障期间测试
jmeter -n -t onlineboutique_test_plan.jmx -l results/chaos.jtl -e -o report/chaos

# 4. 停止故障
kubectl delete -f ../../chaos-experiments/cpu-stress-frontend.yaml

# 5. 恢复测试
jmeter -n -t onlineboutique_test_plan.jmx -l results/recovery.jtl -e -o report/recovery
```

## 查看报告

```bash
# 打开 HTML 报告
start report/baseline/index.html
```

## 关键指标

| 指标 | 说明 | 阈值 |
|-----|------|------|
| Average | 平均响应时间 | < 500ms |
| 95% Line | 95% 响应时间 | < 1000ms |
| Throughput | 吞吐量 (RPS) | > 100 |
| Error % | 错误率 | < 1% |
