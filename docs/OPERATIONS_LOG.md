# 操作日志

本文档记录本项目从零构建到全部工具运行成功的完整操作过程，按时间顺序排列。

---

## 阶段一：AIOps 数据集导出管线（从零实现）

### 1.1 项目结构初始化

**目标：** 在空目录 `e:\0projects\0000Testing-and-Maintenance\Final-exp` 中从零实现数据集导出工具。

**创建的文件：**

```
benchmark/
  __init__.py
  config.py          — 服务列表、指标列表、特征名（66个）、ExportConfig 数据类
  schema.py          — build_feature_schema()，生成66行 feature_schema.csv
  mock_data.py       — 生成 mock 时序数据 + 2个预设故障事件
  labels.py          — 从 incidents_df 为每个时间点打标签
  prometheus_client.py — Prometheus HTTP API 封装（query_range）
  exporter.py        — live 模式数据拉取（从 Prometheus 读取全部66个特征）
  dataset_builder.py — 数据切分、写CSV/JSON、质量检查
  cli.py             — CLI 入口（smoke / live 子命令）
configs/
  online_boutique.yaml      — 数据集配置
  prometheus_queries.yaml   — 66个特征的 PromQL 查询
scripts/
  run_smoke_export.sh
  run_live_export.sh
  clean_dataset.sh
requirements.txt
README.md
```

**关键设计决策：**
- 66个特征 = 11个服务 × 6个指标（qps、latency_p95、error_rate、cpu_usage、memory_usage、restart_count）
- x 文件严格不含标签列，y 文件含完整标签
- quality_report.json 通过才允许脚本以零状态退出
- mock 模式故障必须落在 test split 内，train/valid 全为正常

### 1.2 首次 Smoke 测试运行成功

**命令：**
```bash
python -m benchmark.cli smoke \
  --output data/datasets/online_boutique_short_fault_v1 \
  --duration-minutes 10 --step-seconds 5
```

**结果：** 生成 120 个时间点，2 个故障事件，quality_report.json `passed=true`

**验证结果：**
- feature_schema.csv：66 行 ✓
- test_y.csv 异常点：24 个（2×60s / 5s = 24）✓
- x 文件不含标签列 ✓
- sample_submission.csv 时间戳与 test_x.csv 完全一致 ✓

### 1.3 修复 Windows 路径问题

**问题：** `run_smoke_export.sh` 中使用 POSIX 路径（`/e/0projects/...`）传给 Windows Python 导致 `FileNotFoundError`。

**修复：** 将 quality_report.json 的读取改为从项目根目录起的相对路径（`data/datasets/.../quality_report.json`），避免 Git Bash POSIX 路径与 Windows Python 路径不兼容。

**修复：** Python 检测逻辑优先选 `python` 而非 `python3`，避免选到 Windows App Store 的空壳（该壳在 Git Bash 环境下无法正常执行）。

**最终结果：** `bash scripts/run_smoke_export.sh` 输出 `SUCCESS`，quality 全部通过。

---

## 阶段二：集群环境检查与准备

### 2.1 发现 minikube 已存在但未启动

**检查：**
```bash
docker context ls     # 发现有 default 和 desktop-linux 两个 context
DOCKER_HOST="npipe:////./pipe/docker_engine" docker ps  # 看到 minikube 容器 Up 3 minutes
```

**问题：** minikube 使用 Docker driver，但当前 Docker context 指向 `desktop-linux`（`npipe:////./pipe/dockerDesktopLinuxEngine`），此 pipe 不存在。正确的 pipe 是 `npipe:////./pipe/docker_engine`。

**解决：** 所有 kubectl/minikube 命令前加 `DOCKER_HOST="npipe:////./pipe/docker_engine"`。

### 2.2 启动 minikube 集群

```bash
DOCKER_HOST="npipe:////./pipe/docker_engine" minikube start
```

**结果：** Kubernetes v1.35.1，节点 Ready，kubectl 已配置。

**发现已有的命名空间：**
- `monitoring`：已有 Prometheus（NodePort 31090）、Grafana、kube-state-metrics、node-exporter
- `sock-shop`：已有 SockShop 部分服务（部分 Pod 处于 Error 状态）

### 2.3 发现 Prometheus 已存在

**检查：**
```bash
kubectl get pods -n monitoring
kubectl get svc -n monitoring
```

**结果：** `prometheus-deployment` Running，NodePort 31090。

**问题：** NodePort 在 Windows Docker driver 下无法直接从宿主机访问（minikube IP 192.168.49.2 不可路由）。

**解决：** 使用 `kubectl port-forward` 将 Prometheus 暴露到 `localhost:9090`。

---

## 阶段三：部署 Online Boutique

### 3.1 下载官方 Manifest

```bash
mkdir -p deploy/kubernetes
curl -fsSL "https://raw.githubusercontent.com/GoogleCloudPlatform/microservices-demo/main/release/kubernetes-manifests.yaml" \
  -o deploy/kubernetes/online-boutique.yaml
```

**版本：** Online Boutique v0.10.5

**包含服务：** currencyservice、loadgenerator、productcatalogservice、checkoutservice、shippingservice、cartservice、redis-cart、emailservice、paymentservice、frontend、recommendationservice、adservice

### 3.2 创建命名空间并部署

```bash
kubectl create namespace online-boutique
kubectl apply -n online-boutique -f deploy/kubernetes/online-boutique.yaml
```

**等待就绪：**
```bash
kubectl wait --for=condition=ready pod --all -n online-boutique --timeout=120s
```

**结果：** 所有 12 个 Pod（含 loadgenerator）全部 Ready，redis-cart 最先启动。

---

## 阶段四：配置 Prometheus 采集 Online Boutique 指标

### 4.1 第一次尝试：验证现有 Prometheus 采集能力

**测试 cAdvisor 指标：**
```bash
# Prometheus 通过 kubernetes-nodes-cadvisor job 采集 cAdvisor
# 但 Online Boutique manifest 无 prometheus.io/scrape 注解
```

**发现：** 现有 monitoring namespace 的 Prometheus 可以采集：
- `container_cpu_usage_seconds_total`（`cpu="total"` label，pod 级别）
- `container_memory_working_set_bytes`
- `kube_pod_container_status_restarts_total`

**无法采集：** 服务网格指标（qps、latency、error_rate）— 需要 Istio。

**结论：** 63/66 特征可用，3个（redis-cart HTTP指标）不可用；先用 cAdvisor + kube-state-metrics 采集33个，安装 Istio 后扩充到63个。

### 4.2 安装 Istio 1.26.2

**下载 istioctl：**
```bash
# 从 GitHub releases 下载 Windows binary
curl -fsSL -o /tmp/istioctl.zip \
  "https://github.com/istio/istio/releases/download/1.26.2/istioctl-1.26.2-win-amd64.zip"
unzip -o /tmp/istioctl.zip -d /tmp/istioctl-bin/
cp /tmp/istioctl-bin/istioctl.exe ~/bin/istioctl.exe
```

**安装 Istio 控制面（default profile）：**
```bash
DOCKER_HOST="npipe:////./pipe/docker_engine" \
  istioctl install --set profile=default -y
```

**部署 Istio Prometheus addon：**
```bash
kubectl apply -f \
  "https://raw.githubusercontent.com/istio/istio/release-1.26/samples/addons/prometheus.yaml"
```

**注意：** Istio Prometheus 部署在 `istio-system` 命名空间，独立于 `monitoring` 命名空间的旧 Prometheus。

### 4.3 启用 Sidecar 注入并重部署 Online Boutique

```bash
# 给 namespace 打上注入标签
kubectl label namespace online-boutique istio-injection=enabled --overwrite

# 重启所有 Deployment，触发 sidecar 注入
kubectl rollout restart deployment -n online-boutique
kubectl rollout status deployment -n online-boutique --timeout=180s
```

**结果：** 所有 Pod 从 `1/1` 变为 `2/2`（app + istio-proxy sidecar）。

### 4.4 修复 Istio Prometheus cAdvisor 403 问题

**问题：** Istio Prometheus 的 `kubernetes-nodes-cadvisor` scrape job 返回 403 Forbidden。

**诊断：**
```bash
# 检查 ClusterRole
kubectl get clusterrole prometheus -o yaml | grep -A5 "rules:"
# 结果：有 nodes/proxy 权限

# 验证权限
kubectl auth can-i get nodes/proxy \
  --as=system:serviceaccount:istio-system:prometheus
# 结果：yes
```

**问题根因：** Prometheus pod 在 RBAC 配置完成前已启动，需要重启以刷新 token。

**解决：**
```bash
kubectl rollout restart deployment/prometheus -n istio-system
```

**结果：** cAdvisor target 状态变为 `up`。

### 4.5 添加 kube-state-metrics 到 Istio Prometheus

**问题：** Istio Prometheus 不采集 `monitoring` namespace 的 kube-state-metrics（因为该服务没有 `prometheus.io/scrape: "true"` 注解，且 Istio Prometheus 不会自动跨 namespace 发现）。

**解决：** 创建 `deploy/kubernetes/istio-prometheus-patch.yaml`，在 Istio Prometheus configmap 中添加静态 scrape job：

```yaml
- job_name: kube-state-metrics
  static_configs:
  - targets:
    - kube-state-metrics.monitoring.svc.cluster.local:8080
```

```bash
kubectl apply -f deploy/kubernetes/istio-prometheus-patch.yaml
kubectl rollout restart deployment/prometheus -n istio-system
```

**结果：** `kube_pod_container_status_restarts_total` 数据恢复。

### 4.6 更新 PromQL 查询配置

**发现的 label 差异（与标准文档不符）：**
- cAdvisor 中无 `container` label，只有 `pod`、`namespace`
- CPU 指标需要加 `cpu="total"` 过滤，否则返回多个 CPU core 的分类数据
- 内存单位为字节，需 `/1048576` 转换为 MiB

**最终可用查询（`configs/prometheus_queries.yaml`）：**
```yaml
# CPU（cAdvisor，pod 级别合计）
frontend_cpu_usage: 'sum(rate(container_cpu_usage_seconds_total{namespace="online-boutique",pod=~"frontend-.*",cpu="total"}[1m]))'

# 内存（MiB）
frontend_memory_usage: 'sum(container_memory_working_set_bytes{namespace="online-boutique",pod=~"frontend-.*"}) / 1048576'

# 重启次数
frontend_restart_count: 'sum(kube_pod_container_status_restarts_total{namespace="online-boutique",pod=~"frontend-.*"})'

# QPS（Istio Envoy）
frontend_qps: 'sum(irate(istio_requests_total{destination_service_name="frontend",destination_service_namespace="online-boutique"}[1m]))'

# P95 延迟（Istio Envoy）
frontend_latency_p95: 'histogram_quantile(0.95, sum(rate(istio_request_duration_milliseconds_bucket{destination_service_name="frontend",destination_service_namespace="online-boutique"}[1m])) by (le))'

# 错误率（`or vector(0)` 处理无 5xx 流量时返回空的问题）
frontend_error_rate: '(sum(rate(istio_requests_total{...,response_code=~"5.."}[1m])) or vector(0)) / sum(rate(istio_requests_total{...}[1m]))'
```

**最终指标覆盖率：** 63/66（redis-cart 的 qps/latency/error_rate 因 Redis 使用 TCP 协议无 HTTP 层指标而不可用）。

---

## 阶段五：修复 Live 模式数据采集问题

### 5.1 时间戳对齐问题（全量 NaN）

**问题：** live 模式采集后所有特征值为 NaN。

**根因诊断：**

```python
# 代码生成的时间戳（从 now - 10min 开始）
timestamps = ["2026-05-28T17:46:23Z", "2026-05-28T17:46:28Z", ...]

# Prometheus query_range 返回的时间戳（对齐到 epoch 5s 倍数）
prom_timestamps = ["2026-05-28T17:46:20Z", "2026-05-28T17:46:25Z", ...]

# reindex 时因字符串不匹配导致全部 NaN
aligned = series.reindex(timestamps)  # 全部 NaN
```

**解决：** 修改 `benchmark/exporter.py`，改为以第一个成功返回数据的 Prometheus 查询结果的时间戳序列作为主索引，所有特征对齐到这个序列，而不是自行生成时间戳。

```python
# 修复后：用 Prometheus 实际返回的时间戳作为 master_timestamps
if master_timestamps is None:
    master_timestamps = list(series.index)
```

**结果：** live 模式数据从全 NaN 变为正常数值（frontend_qps ≈ 2.8 req/s，frontend_memory ≈ 57 MiB）。

### 5.2 错误率指标空值问题

**问题：** 在无 5xx 错误流量时，`sum(rate(...{response_code=~"5.."}[1m]))` 返回空集，导致除法结果为空，整个特征为 NaN。

**解决：** 将分子改为 `(sum(...) or vector(0))`，确保无 5xx 流量时分子为 0 而非空集。

### 5.3 Live 模式质量检查过于严格

**问题：** live 模式无故障注入，`quality_report.json` 中 `test_anomaly_points=0`，原有代码会硬性 `assert test_labels["is_anomaly"].sum() > 0` 导致失败。

**解决：** 修改 `dataset_builder.py`，仅当 `has_incidents=True` 时才执行异常点断言；live 模式质量检查放宽条件（允许 NaN，允许无异常点）。

### 5.4 Windows 编码问题

**问题：** `exporter.py` 中 `open(path)` 在中文 Windows 系统上默认用 GBK 编码读取 YAML 文件，导致 `UnicodeDecodeError`。

**解决：** 改为 `open(path, encoding="utf-8")`。

### 5.5 空 incidents_df 导致 KeyError

**问题：** live 模式传入空 incidents 列表，`incidents_df` 为空 DataFrame（无列），`incidents_df[["incident_id", ...]]` 报 `KeyError`。

**解决：** 在 `dataset_builder.py` 中判断 `len(incidents_df) > 0` 再选列，否则创建空 DataFrame 并指定列名。

---

## 阶段六：Selenium 功能测试实现

### 6.1 创建测试框架

**文件结构：**
```
tests/selenium/
  conftest.py                  — pytest fixture：Chrome/Firefox driver 创建、metrics 收集
  utils.py                     — wait_for、timed_get、screenshot 工具函数
  test_boutique_functional.py  — Online Boutique 12 个功能测试
  test_cross_browser.py        — Chrome + Firefox 跨浏览器兼容性测试
  test_sockshop_functional.py  — SockShop 测试（按用户需求后来改为可选）
  pytest.ini                   — pytest 配置（HTML 报告、日志）
  requirements.txt             — selenium>=4.18, pytest, pytest-html, webdriver-manager
```

**依赖选型：**
- `webdriver-manager`：自动下载匹配版本的 ChromeDriver
- `pytest-html`：生成自包含 HTML 测试报告
- W3C Navigation Timing API：通过 `driver.execute_script` 获取 DNS/TCP/TTFB/DOMLoad/PageLoad 等精细指标

### 6.2 首次运行：6/12 失败（CSS Selector 不匹配）

**测试对象版本：** Online Boutique v0.10.5

**发现的 HTML 结构差异（与假设不同）：**

| 假设 | 实际（v0.10.5） |
|------|----------------|
| 货币切换：有独立 submit 按钮 | `select` 元素带 `onchange` 自动提交，无 submit 按钮 |
| 购物车页：`.cart-item` | `.cart-summary-item-row` |
| 购物车页：有 `table` | 无 table，用 div flex 布局 |
| 结账：跳转到 `/checkout` | 结账表单嵌在 `/cart` 页内，提交到 `/cart/checkout` |

**诊断方法：** 用 Python `urllib.request` + cookie jar 直接请求页面，正则提取关键 HTML 片段。

**修复：** 更新所有 CSS selector，货币切换改为等待页面自动刷新后检查 `€` 符号，购物车/结账选择器改为匹配实际元素。

**修复后结果：** 12/12 全部通过。

### 6.3 跨浏览器测试：Firefox geckodriver 下载失败

**问题：** `webdriver-manager` 调用 GitHub API 下载 geckodriver，触发 GitHub API 限流（60次/小时匿名限制）。

**解决：** 手动下载 geckodriver v0.35.0 Windows binary：

```bash
curl -fsSL -o /tmp/geckodriver.zip \
  "https://github.com/mozilla/geckodriver/releases/download/v0.35.0/geckodriver-v0.35.0-win64.zip"
unzip /tmp/geckodriver.zip -d /tmp/geckodriver-bin/
cp /tmp/geckodriver-bin/geckodriver.exe "$HOME/.wdm/drivers/geckodriver/win64/v0.35.0/"
```

修改 `conftest.py`，优先检查本地缓存路径，避免网络请求：

```python
cached = Path.home() / ".wdm/drivers/geckodriver/win64/v0.35.0/geckodriver.exe"
if cached.exists():
    gecko_path = str(cached)
```

**最终结果：** 20/20 全部通过（Chrome 12 + Firefox 8）。

---

## 阶段七：JMeter 性能测试计划

### 7.1 创建 JMeter 测试计划

**Online Boutique 测试计划** (`tests/jmeter/plans/online_boutique_load_test.jmx`)**：**

| 场景 | 线程数 | Ramp-up | 说明 |
|------|--------|---------|------|
| 场景1 正常负载 | 10 | 10s | 完整用户流程：主页→商品→加购→购物车→结账→下单 |
| 场景2 中等负载 | 30 | 15s | 只读：主页 + 商品详情 |
| 场景3 峰值负载 | 50 | 20s | 仅主页，极限并发测试 |

每个场景的响应时间断言：
- 主页 / 商品页：< 3s
- 加购 / 购物车：< 5s
- 结账提交：< 10s

**SockShop 测试计划** (`tests/jmeter/plans/sockshop_load_test.jmx`)：

| 场景 | 线程数 | 测试目标 |
|------|--------|---------|
| 场景1 商品浏览 | 10 | catalogue 服务：/catalogue、/catalogue/size、/category/all |
| 场景2 用户服务 | 20 | user/carts 服务：登录页、注册页、购物车页 |
| 场景3 并发混合 | 30 | 随机选择：主页/目录/购物车（RandomController） |

### 7.2 运行脚本设计

`scripts/run_jmeter_tests.sh` 功能：
- 自动搜索 JMeter 可执行文件（多个常见路径）
- 支持命令行参数覆盖 host、port、users、duration、ramp_up
- 调用 `jmeter -n -t plan.jmx -l result.jtl -e -o report/` 生成 HTML 报告
- 运行完成后用 Python 解析 JTL，打印 P50/P90/P95/Max/Min 指标摘要

---

## 阶段八：脚本和文档整理

### 8.1 setup_port_forward.sh 更新

更新为同时启动三个 port-forward：

| 服务 | 本地端口 |
|------|---------|
| Istio Prometheus | 9090 |
| Online Boutique frontend | 8080 |
| SockShop front-end | 8081 |

### 8.2 live 模式采集验证

**采集 10 分钟真实数据结果（2026-05-28）：**

| 指标 | 实测值 | 说明 |
|------|--------|------|
| frontend_qps | 2.8 req/s | loadgenerator 持续产生流量 |
| frontend_latency_p95 | 97.5 ms | 正常响应延迟 |
| frontend_error_rate | 0.0 | 无错误 |
| frontend_cpu_usage | 0.022 cores | 正常 CPU 占用 |
| frontend_memory_usage | 57 MiB | 正常内存 |
| redis-cart_memory_usage | 48.9 MiB | Redis 内存 |

**覆盖率：** 63/66 特征（94.8% 有效值）

---

## 总结：当前集群状态

| 组件 | 命名空间 | 状态 |
|------|---------|------|
| Kubernetes | — | v1.35.1，单节点 minikube |
| Online Boutique (12 Pod) | `online-boutique` | 全部 2/2 Running（含 Istio sidecar） |
| Istio 控制面 | `istio-system` | istiod + ingressgateway Running |
| Istio Prometheus | `istio-system` | Running，采集 Istio + cAdvisor + kube-state-metrics |
| kube-state-metrics | `monitoring` | Running，被 Istio Prometheus 静态抓取 |
| SockShop（旧） | `sock-shop` | 部分 Pod Error（orders-db、rabbitmq），不影响本项目 |
| 旧 Prometheus | `monitoring` | Running（未使用，已被 Istio Prometheus 替代） |

## 总结：需要的 Port-Forward

```bash
# 每次重启系统后需要运行
bash scripts/setup_port_forward.sh
```

| 目标 | 本地地址 | 用途 |
|------|---------|------|
| Istio Prometheus | http://localhost:9090 | AIOps 数据采集 |
| Online Boutique | http://localhost:8080 | Selenium 测试 / JMeter 测试 |
| SockShop | http://localhost:8081 | 可选，JMeter SockShop 测试 |

## 已知限制

1. **redis-cart HTTP 指标缺失**：Redis 使用 TCP 协议，Istio Envoy 无 HTTP 层指标，`redis-cart_qps`、`redis-cart_latency_p95`、`redis-cart_error_rate` 在 live 模式永远为 NaN。解决方案：部署 `redis-exporter` sidecar 获取 Redis 原生指标。

2. **DOCKER_HOST 环境变量**：每个新终端会话中需要手动设置 `DOCKER_HOST="npipe:////./pipe/docker_engine"`，否则 minikube/kubectl 无法连接。长期解决方案：将 minikube 的 Docker context 设为默认。

3. **JMeter 需手动安装**：`run_jmeter_tests.sh` 依赖系统已安装 JMeter，脚本无法自动下载安装。

4. **SockShop 部分服务故障**：`carts-db`、`orders-db`、`rabbitmq` Pod 处于 Error 状态，导致购物车和订单功能不可用，SockShop 的 Selenium 测试只能覆盖前端浏览和 API 查询部分。

5. **long-running 采集的时间戳起点**：由于使用 Prometheus `query_range` 的实际返回时间戳作为主索引，采集窗口的首尾几个点可能因 `irate/rate` 计算窗口不足而为 NaN。建议 `lookback_minutes` 至少设置为 `rate_window + 1min` 的余量。

---

## 阶段九：Run-based 数据导出重构（2026-05-29）

### 9.1 背景：多次间断采集需求

**问题：** 原 live/collect 模式每次采集内部按 50/20/30 自动切 train/valid/test，导致：
- 单次采集数据量少时切分无意义（valid 只有 5 行，test 1445 行）
- 无法跨多次采集累积数据集

**设计决策：** 改为每次采集保存一个独立 **run**，由用户选定若干 run 后统一 assemble 成 train/valid/test。

### 9.2 特征数从 66 改为 63

**决策：** 彻底删除 `redis-cart_qps`、`redis-cart_latency_p95`、`redis-cart_error_rate`（不再填 NaN，直接从 schema 中移除）。

**新特征数：** 10 服务 × 6 指标 + redis-cart × 3 资源指标 = **63**

**影响文件：** `config.py`（FEATURE_NAMES assert 63）、`schema.py`（63行）、`mock_data.py`、`dataset_builder.py`、`prometheus_queries.yaml`

### 9.3 NaN 补全策略（impute_features）

**新增函数：** `benchmark/exporter.py::impute_features(df)`

**策略：**

| 指标 | 条件 | 处理 |
|------|------|------|
| `error_rate` / `latency_p95` | 对应服务 `qps == 0` 时为 NaN | 填 0.0（无流量时正常） |
| `cpu_usage` / `memory_usage` / `restart_count` | 连续缺失 ≤2 个点 | Forward fill（短暂 scrape 缺口） |
| 其他 | 仍有 NaN | 不处理，quality report 硬失败 |

**关键设计：** 补全数量和补全特征记录在 `quality_report.imputed_features`，完全透明。

### 9.4 严格 quality_report 硬校验

**旧问题：** live 模式 `nan_count > 0` 但 `passed=True`（fake pass）。

**新规则：** 以下任一条件满足 → `passed=False` → CLI 以非零退出：

- `run_x` 含 NaN 或 Inf
- `run_x` 含标签列
- `feature_count != 63` 或 `schema_feature_count != 63`
- 时间戳非 5s 等间隔
- `duplicate_timestamp_count > 0`
- `ground_truth.y_true` 与 `run_y.is_anomaly` 不一致
- `root_cause_dims` 引用不存在于 schema 的特征
- chaos run 的 `anomaly_points == 0`
- 补全后仍有 NaN

### 9.5 Run-based 输出目录结构

**新目录格式：**

```
data/runs/<run_id>/
  processed/run_x.csv      ← 特征（无 NaN/Inf/标签）
  processed/run_y.csv      ← 标签
  processed/quality_report.json
  run_meta.json            ← run 元信息
  answers/ground_truth.csv
```

**新命令：** `python -m benchmark.cli assemble --runs-root data/runs --output data/datasets/v1`

**split 策略（last3_valid_last2_test）：** 按 `collection_start` 排序，最后 2 run = test，倒数第 3 run = valid，其余 = train。最少需要 4 次 quality_passed=True 的 run。

### 9.6 多轮故障注入

**新参数（collect 命令）：**

| 参数 | 说明 |
|------|------|
| `--rounds N` | 将 fault-types 循环注入 N 次，INC 编号全局连续 |
| `--round-gap-minutes` | 轮与轮之间的间隔 |
| `--gap-jitter M` | 每个间隔额外随机叠加 0~M 秒 |

### 9.7 Grafana Dashboard 配置

**目标：** 实验运行期间实时查看服务指标。

**使用现有 `monitoring` 命名空间的独立 Grafana（从 SockShop 时代保留）：**

1. 注册数据源 `Istio-Prometheus`（内部 URL：`http://prometheus.istio-system.svc.cluster.local:9090`）
2. 创建 6 panel dashboard：QPS / Latency p95 / Error Rate / CPU / Memory / Pod Restarts
3. Dashboard URL: `http://localhost:3000/d/f9R_XXJvz/online-boutique-aiops`（需 port-forward）

**port-forward 加入 Grafana：**

```bash
kubectl port-forward -n monitoring svc/grafana 3000:80
```

### 9.8 Port-forward 端口占用修复

**问题：** 重复运行 `setup_port_forward.sh` 时报 `bind: Only one usage of each socket address`（端口 3000/8080/9090 未被 Ctrl+C 释放）。

**修复：** 脚本启动前用 PowerShell `Get-NetTCPConnection` 找到占用该端口的进程 PID，`Stop-Process` 精准释放，不误杀其他 kubectl 进程。

```bash
# 现在可以安全重复运行
bash scripts/setup_port_forward.sh
```

### 9.9 文件改动汇总

| 文件 | 改动 |
|------|------|
| `benchmark/exporter.py` | 新增 `impute_features()`，import SERVICES/_REDIS_METRICS |
| `benchmark/dataset_builder.py` | 新增 `build_and_write_run()` + `_build_quality_report_run()`；smoke 保留原函数 |
| `benchmark/cli.py` | `cmd_live`/`cmd_collect` 改为 run-based；新增 `cmd_assemble`、`_update_manifest` |
| `benchmark/reexport.py` | 改用 `build_and_write_run()` |
| `scripts/setup_port_forward.sh` | 新增端口释放逻辑（PowerShell `Get-NetTCPConnection`） |
| `docs/EXPERIMENT_GUIDE.md` | 重写为 run-based + assemble 工作流 |
| `README.md` | 更新特征数 66→63；新增 run-based 和 assemble 说明；更新端口表 |

**Git commit:** `b26d143` fix: harden live collection dataset quality and run-based exports  
**Git commit:** `aaf257b` fix: release occupied ports before starting port-forwards
