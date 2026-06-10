# Prometheus + Grafana 监控部署指南

> 本指南记录 OnlineBoutique 微服务系统中 Prometheus 和 Grafana 的完整部署过程，包括问题排查和解决方案。

---

## 目录

- [环境信息](#环境信息)
- [部署流程](#部署流程)
- [遇到的问题与解决方案](#遇到的问题与解决方案)
- [Grafana 仪表盘配置](#grafana-仪表盘配置)
- [关键 PromQL 查询](#关键-promql-查询)
- [故障注入监控验证](#故障注入监控验证)

---

## 环境信息

| 组件 | 版本 | 部署方式 |
|-----|------|---------|
| Kubernetes (Minikube) | v1.38.1 | Docker driver |
| Prometheus | v2.55.1 | Deployment + NodePort |
| Grafana | 11.3.1 | Deployment + NodePort |
| cAdvisor | 内置在 kubelet 中 | 通过 kubernetes-cadvisor job 抓取 |

### 服务访问地址

```bash
# Prometheus
kubectl port-forward svc/prometheus -n monitoring 9090:9090
# 访问: http://localhost:9090

# Grafana
kubectl port-forward svc/grafana -n monitoring 3000:3000
# 访问: http://localhost:3000
# 账号: admin / admin
```

---

## 部署流程

### 1. 部署 Prometheus + Grafana

```bash
# 使用 Kustomize 一键部署
kubectl apply -k monitoring/
```

部署的资源包括：
- `prometheus-rbac.yaml` - RBAC 权限配置
- `prometheus-config.yaml` - Prometheus 抓取配置
- `prometheus-deployment.yaml` - Prometheus 部署
- `grafana-deployment.yaml` - Grafana 部署

### 2. 为微服务添加 Prometheus 监控注解

Prometheus 通过 Pod 注解自动发现目标。需要为每个微服务添加：

```yaml
prometheus.io/scrape: "true"
prometheus.io/port: "8080"
prometheus.io/path: "/metrics"
```

**批量添加脚本：**

```bash
bash monitoring/add-prometheus-annotations.sh
```

该脚本会为以下服务添加注解：
- frontend (8080)
- checkoutservice (5050)
- cartservice (7070)
- productcatalogservice (3550)
- currencyservice (7000)
- paymentservice (50051)
- shippingservice (50051)
- emailservice (8080)
- adservice (9555)
- recommendationservice (8080)
- couponservice (8080)

### 3. 配置 Grafana 数据源

```
1. 登录 Grafana → Configuration → Data Sources → Add data source
2. 选择 Prometheus
3. URL: http://prometheus:9090
4. 点击 Save & Test
```

### 4. 导入仪表盘

```
1. Dashboards → Import
2. 上传 monitoring/grafana-dashboard-fixed.json
3. 数据源选择 prometheus-1
4. 点击 Import
```

---

## 遇到的问题与解决方案

### 问题 1：Grafana 显示 "No data"

**现象：** 导入仪表盘后所有面板显示 "No data"

**原因：** 微服务 Pod 没有 `prometheus.io/scrape` 注解，Prometheus 无法发现目标

**解决：**
```bash
# 为所有微服务添加注解
bash monitoring/add-prometheus-annotations.sh

# 验证注解是否生效
kubectl get pods -n default -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.metadata.annotations.prometheus\.io/scrape}{"\n"}{end}'
```

### 问题 2：服务可用性显示全 Down

**现象：** `up{job="onlineboutique-services"}` 值为 0，所有服务显示 Down

**原因：** OnlineBoutique 微服务代码本身**没有集成 Prometheus 客户端库**，不暴露 `/metrics` 端点

**分析：**
- Prometheus 能发现 Pod（有注解）
- 但抓取 `/metrics` 时返回 404
- 所以 `up` 指标为 0

**解决：** 这是预期行为。应用层指标（请求数、响应时间）需要修改代码添加。容器层指标（CPU、内存）通过 cAdvisor 获取，不受影响。

### 问题 3：kube-state-metrics 安装失败

**现象：** kube-state-metrics Pod 状态为 ImagePullBackOff

**原因：** 国内网络无法拉取 `bitnami/kube-state-metrics` 镜像

**尝试过的镜像：**
- `registry.cn-hangzhou.aliyuncs.com/google_containers/kube-state-metrics:v2.10.1` ❌ 不可用
- `bitnami/kube-state-metrics:2.10.1` ❌ 拉取失败

**影响：** `kube_` 开头的指标（如 `kube_pod_status_phase`、`kube_pod_container_status_restarts_total`）无法获取

**替代方案：** 使用 cAdvisor 指标替代，仪表盘已调整为仅使用 cAdvisor 可用指标

### 问题 4：网络指标 No data

**现象：** `container_network_receive_bytes_total` 和 `container_network_transmit_bytes_total` 无数据

**原因：** Minikube 的 cAdvisor 配置不包含网络统计，或网络指标在节点级别而非 Pod 级别

**解决：** 从仪表盘中移除网络面板，替换为内存工作集对比面板

### 问题 5：cAdvisor 指标标签不匹配

**现象：** 查询 `container_cpu_usage_seconds_total{container!="POD"}` 无结果

**原因：** Minikube cAdvisor 指标**没有 `container` 标签**，只有 `pod` 和 `namespace` 标签

**正确的查询方式：**
```promql
# ❌ 错误（有 container 标签过滤）
container_cpu_usage_seconds_total{namespace="default",container!="",container!="POD"}

# ✅ 正确（Minikube cAdvisor 无 container 标签）
container_cpu_usage_seconds_total{namespace="default"}
```

---

## Grafana 仪表盘配置

### 最终仪表盘面板

| 面板 | 查询 | 用途 |
|-----|------|------|
| 服务可用性 | `up{job="onlineboutique-services"}` | 显示应用指标暴露状态（预期全 Down） |
| Pod CPU 使用率 | `rate(container_cpu_usage_seconds_total{namespace="default"}[5m])` | 所有 Pod CPU |
| Pod 内存使用量 | `container_memory_usage_bytes{namespace="default"} / 1024 / 1024` | 所有 Pod 内存 |
| Pod 内存工作集 WSS | `container_memory_working_set_bytes{namespace="default"} / 1024 / 1024` | 实际使用内存 |
| 故障注入内存监控 | `container_memory_usage_bytes{namespace="default",pod=~"frontend-.*"}` | 目标服务内存 |
| 核心服务 CPU 对比 | `rate(container_cpu_usage_seconds_total{namespace="default",pod=~"frontend-.*"}[5m])` | frontend/checkoutservice/cartservice |
| 核心服务内存对比 | `container_memory_working_set_bytes{namespace="default",pod=~"frontend-.*"}` | frontend/cartservice/checkoutservice |
| 故障注入 CPU 监控 | `rate(container_cpu_usage_seconds_total{namespace="default",pod=~"frontend-.*"}[5m])` | frontend/cartservice/couponservice |

### 仪表盘文件

- `monitoring/grafana-dashboard-fixed.json` - 最终可用版本（仅 cAdvisor 指标）
- `monitoring/grafana-dashboard.json` - 原始版本（需要 kube-state-metrics 和应用指标）

---

## 关键 PromQL 查询

### 容器资源监控（cAdvisor）

```promql
# Pod CPU 使用率
rate(container_cpu_usage_seconds_total{namespace="default"}[5m])

# Pod 内存使用量 (MB)
container_memory_usage_bytes{namespace="default"} / 1024 / 1024

# Pod 内存工作集 (MB)
container_memory_working_set_bytes{namespace="default"} / 1024 / 1024

# 指定服务的 CPU
rate(container_cpu_usage_seconds_total{namespace="default",pod=~"frontend-.*"}[5m])

# 指定服务的内存
container_memory_usage_bytes{namespace="default",pod=~"cartservice-.*"} / 1024 / 1024
```

### 服务可用性

```promql
# 应用层可用性（需要应用暴露 /metrics）
up{job="onlineboutique-services"}

# Kubernetes Pod 状态（需要 kube-state-metrics）
kube_pod_status_phase{namespace="default",phase="Running"}
```

---

## 故障注入监控验证

### 实验 1：CPU Stress（frontend）

```bash
# 注入故障
kubectl apply -f chaos-experiments/cpu-stress-frontend.yaml

# 在 Grafana/Prometheus 中观察
# 面板: 故障注入 CPU 监控 / Pod CPU 使用率
# 预期: frontend CPU 使用率飙升

# 停止故障
kubectl delete -f chaos-experiments/cpu-stress-frontend.yaml
```

### 实验 2：Memory Stress（cartservice）

```bash
# 注入故障
kubectl apply -f chaos-experiments/memory-stress-cartservice.yaml

# 在 Grafana/Prometheus 中观察
# 面板: 故障注入内存监控 / Pod 内存使用量
# 预期: cartservice 内存使用量上升

# 停止故障
kubectl delete -f chaos-experiments/memory-stress-cartservice.yaml
```

### 实验 3：Network Delay（checkoutservice）

```bash
# 注入故障
kubectl apply -f chaos-experiments/network-delay-checkoutservice.yaml

# 观察: 需要通过应用层指标或外部测试工具观察延迟
# cAdvisor 不直接提供网络延迟指标

# 停止故障
kubectl delete -f chaos-experiments/network-delay-checkoutservice.yaml
```

### 实验 4：Pod Kill（couponservice）

```bash
# 注入故障
kubectl apply -f chaos-experiments/pod-kill-couponservice.yaml

# 在 Grafana/Prometheus 中观察
# 面板: Pod CPU 使用率 / Pod 内存使用量
# 预期: couponservice Pod 消失后重新出现

# 停止故障
kubectl delete -f chaos-experiments/pod-kill-couponservice.yaml
```

---

## 数据采集脚本

```bash
# 采集基线数据
cd tests/prometheus
python collect_metrics.py --mode baseline --duration 300

# 采集故障期间数据
python collect_metrics.py --mode chaos --duration 180 --experiment cpu_stress

# 对比分析
python collect_metrics.py --mode compare --baseline baseline.json --chaos chaos.json
```

---

## 总结

| 指标类型 | 可用性 | 来源 |
|---------|--------|------|
| CPU 使用率 | ✅ | cAdvisor |
| 内存使用量 | ✅ | cAdvisor |
| 内存工作集 | ✅ | cAdvisor |
| 网络流量 | ❌ | Minikube cAdvisor 不提供 |
| Pod 状态 | ❌ | 需要 kube-state-metrics |
| 容器重启 | ❌ | 需要 kube-state-metrics |
| 应用请求数 | ❌ | 需要应用集成 Prometheus 客户端 |
| 应用响应时间 | ❌ | 需要应用集成 Prometheus 客户端 |

**对于故障注入实验，cAdvisor 提供的 CPU 和内存指标已足够支持论文数据收集。**
