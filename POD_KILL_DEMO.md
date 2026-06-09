# 固定 Pod Kill 大作业演示方案

## 目标

固定删除 `online-boutique` 命名空间中的 `redis-cart` Pod。在线 Agent 通过连续 Pod 快照检测旧 Pod 消失和新 Pod 出现，并自动补充 Kubernetes Event、Pod 状态和 Prometheus 指标，最后生成诊断报告。

## 1. 启动系统

```powershell
minikube start
kubectl get pods -n online-boutique
```

确保所有 Pod 基本为 `Running` 和 `Ready`。

## 2. 启动 Prometheus 端口转发

根据你的 Prometheus Service 名称执行，例如：

```powershell
kubectl port-forward -n monitoring svc/prometheus-k8s 9090:9090
```

如果你使用的是其他 Service，请先查看：

```powershell
kubectl get svc -A | findstr prometheus
```

## 3. 启动 Agent

在项目根目录执行：

```powershell
python -m aiops_agent.main --mode online --prometheus-url http://127.0.0.1:9090 --namespace online-boutique --interval-seconds 10 --cooldown-seconds 180
```

启动后应看到：

```text
[初始化] 已记录 N 个 Pod，后续将检测 Pod 删除和重建。
```

必须先让 Agent 至少完成一次正常巡检，再注入故障，这样它才有旧 Pod 快照可用于比较。

## 4. 注入固定故障

新开一个 PowerShell 终端：

```powershell
python scripts/inject_pod_kill.py --service redis-cart --namespace online-boutique
```

脚本会：

1. 查找 redis-cart Pod；
2. 删除该 Pod；
3. 等待 Deployment 创建替代 Pod；
4. 输出旧 Pod 和新 Pod 名称。

## 5. 观察结果

Agent 下一轮巡检应检测到：

- `pod_deleted` 或 `pod_recreated`；
- 受影响服务为 `redis-cart`；
- 旧 Pod UID/名称消失；
- 新 Pod UID/名称出现；
- 自动查询当前 Pod 状态；
- 自动查询相关 Kubernetes Event；
- 将 redis-cart 加入候选根因并赋予高生命周期证据分。

报告目录：

```text
aiops_agent/output/online_reports/
```

重点查看 Markdown 报告中的：

- Kubernetes 生命周期证据；
- 候选根因排序；
- Agent 工具调用轨迹；
- 综合解释。

## 6. 演示时建议同时打开

终端一：Agent 在线巡检。

终端二：

```powershell
kubectl get pods -n online-boutique -w
```

终端三：故障注入脚本。

这样现场可以清楚看到旧 Pod 消失、新 Pod 创建以及 Agent 自动生成报告的完整过程。
