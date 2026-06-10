# Prometheus + Grafana + ChaosMesh 监控与故障注入部署指南

## 一、Prometheus 部署

已部署完成！Prometheus 正在运行：

```bash
# 查看状态
kubectl get pods -n monitoring
kubectl get svc -n monitoring
```

### 访问 Prometheus

```bash
kubectl port-forward svc/prometheus -n monitoring 9090:9090
```

浏览器访问：`http://localhost:9090`

### Prometheus 配置说明

配置文件：`monitoring/prometheus-config.yaml`

抓取目标：
- Prometheus 自身 (`localhost:9090`)
- Kubernetes API Server
- Kubernetes Nodes
- Kubernetes Pods（带 `prometheus.io/scrape: "true"` 注解的 Pod）
- OnlineBoutique 微服务（通过 `app` 标签识别）

## 二、Grafana 部署

### 方案 A：使用 Helm（推荐，需网络通畅）

```bash
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update
helm install grafana grafana/grafana -n monitoring --set admin.password=admin
```

### 方案 B：使用本地 YAML（网络受限时使用）

由于当前环境网络限制，Grafana 镜像无法拉取。请按以下步骤操作：

#### 1. 在有网络的环境下载镜像

```bash
# 在能访问外网的机器上
docker pull grafana/grafana:11.3.1
docker save grafana/grafana:11.3.1 -o grafana.tar

# 传输到当前环境
docker load -i grafana.tar
minikube image load grafana/grafana:11.3.1
```

#### 2. 修改镜像地址

编辑 `monitoring/grafana-deployment.yaml`：

```yaml
image: grafana/grafana:11.3.1  # 改为本地镜像名
```

#### 3. 部署

```bash
kubectl apply -f monitoring/grafana-deployment.yaml
```

#### 4. 访问 Grafana

```bash
kubectl port-forward svc/grafana -n monitoring 3000:3000
```

浏览器访问：`http://localhost:3000`
- 用户名：`admin`
- 密码：`admin`

#### 5. 配置 Prometheus 数据源

1. 登录 Grafana
2. Configuration → Data Sources → Add data source
3. 选择 Prometheus
4. URL: `http://prometheus:9090`
5. Save & Test

#### 6. 导入仪表盘

推荐仪表盘：
- **Kubernetes Cluster Monitoring** (ID: 7249)
- **Node Exporter Full** (ID: 1860)
- **Microservices Demo** (自定义)

## 三、为微服务添加 Prometheus 监控注解

编辑 `kubernetes-manifests/frontend.yaml` 等文件，在 Pod 模板添加注解：

```yaml
metadata:
  annotations:
    prometheus.io/scrape: "true"
    prometheus.io/port: "8080"
    prometheus.io/path: "/metrics"
```

注意：OnlineBoutique 的微服务需要集成 Prometheus 客户端库才能暴露指标。

## 四、ChaosMesh 部署

### 1. 安装 ChaosMesh

```bash
# 使用 Helm
helm repo add chaos-mesh https://charts.chaos-mesh.org
helm repo update
helm install chaos-mesh chaos-mesh/chaos-mesh -n chaos-mesh --create-namespace

# 或使用 kubectl
curl -sSL https://mirrors.chaos-mesh.org/v2.6.3/install.sh | bash
```

### 2. 验证安装

```bash
kubectl get pods -n chaos-mesh
```

### 3. 访问 Chaos Dashboard

```bash
kubectl port-forward -n chaos-mesh svc/chaos-dashboard 2333:2333
```

浏览器访问：`http://localhost:2333`

### 4. 故障注入示例

#### Pod 故障（杀死 Pod）

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: frontend-pod-kill
  namespace: chaos-mesh
spec:
  action: pod-kill
  mode: one
  selector:
    namespaces:
      - default
    labelSelectors:
      app: frontend
  duration: 30s
```

#### 网络延迟

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: checkoutservice-delay
  namespace: chaos-mesh
spec:
  action: delay
  mode: one
  selector:
    namespaces:
      - default
    labelSelectors:
      app: checkoutservice
  delay:
    latency: 500ms
    correlation: '100'
    jitter: 0ms
  duration: 5m
```

#### CPU 压力

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: StressChaos
metadata:
  name: cpu-stress
  namespace: chaos-mesh
spec:
  mode: one
  selector:
    namespaces:
      - default
    labelSelectors:
      app: frontend
  stressors:
    cpu:
      workers: 2
      load: 80
  duration: 5m
```

## 五、监控指标说明

### 关键指标

| 指标 | 说明 | 来源 |
|-----|------|------|
| `request_duration_seconds` | 请求处理时间 | 应用暴露 |
| `request_count` | 请求数量 | 应用暴露 |
| `http_requests_total` | HTTP 请求总数 | 应用暴露 |
| `container_cpu_usage_seconds_total` | CPU 使用率 | cAdvisor |
| `container_memory_usage_bytes` | 内存使用量 | cAdvisor |
| `kube_pod_status_phase` | Pod 状态 | kube-state-metrics |

### Prometheus 查询示例

```promql
# 请求速率
rate(http_requests_total[5m])

# 平均响应时间
rate(request_duration_seconds_sum[5m]) / rate(request_duration_seconds_count[5m])

# 错误率
rate(http_requests_total{status=~"5.."}[5m])

# CPU 使用率
rate(container_cpu_usage_seconds_total[5m])

# 内存使用
container_memory_usage_bytes
```

## 六、故障注入实验流程

### 实验 1：Pod 故障

1. 在 Grafana 中观察正常状态的仪表盘
2. 使用 ChaosMesh 注入 Pod Kill 故障
3. 观察 Prometheus 指标变化（Pod 重启、请求失败率上升）
4. 在 Grafana 中查看故障影响

### 实验 2：网络延迟

1. 对 `checkoutservice` 注入 500ms 延迟
2. 观察前端响应时间增加
3. 查看请求超时/错误率变化

### 实验 3：CPU 压力

1. 对 `frontend` 注入 CPU 压力
2. 观察响应时间增加、吞吐量下降
3. 查看 HPA（如配置）自动扩容

## 七、数据收集与论文复现

### 收集的数据

1. **正常状态基线**
   - 各服务响应时间 P50/P95/P99
   - 请求成功率
   - CPU/内存使用率

2. **故障状态数据**
   - 故障注入期间的指标变化
   - 恢复时间（MTTR）
   - 错误传播路径

3. **对比分析**
   - 故障前后性能对比
   - 不同故障类型的影响程度

### 导出数据

```bash
# Prometheus 数据查询
 curl 'http://localhost:9090/api/v1/query_range?query=rate(http_requests_total[5m])&start=2024-01-01T00:00:00Z&end=2024-01-01T01:00:00Z&step=15s'

# Grafana 仪表盘导出
# Share → Export → Save to file
```

## 八、常见问题

### Q: Prometheus 无法抓取 Pod 指标
A: 检查 Pod 是否有 `prometheus.io/scrape: "true"` 注解

### Q: Grafana 无法连接 Prometheus
A: 检查 Service 名称和端口，确保在同一 namespace 或使用 FQDN

### Q: ChaosMesh 实验无效果
A: 检查 Pod 选择器是否匹配，确认 ChaosMesh 组件正常运行
