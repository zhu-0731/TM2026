# Online Boutique AIOps Benchmark

本项目为 Online Boutique 微服务系统提供三类工具：
1. **AIOps 数据集导出管线** — 生成用于异常检测模型训练的多变量时序数据集
2. **Selenium 功能测试** — 自动化浏览器测试，验证前端功能
3. **JMeter 性能测试** — 并发负载测试，评估系统性能

---

## 目录

- [环境要求](#环境要求)
- [快速启动（环境准备）](#快速启动)
- [Selenium 功能测试](#selenium-功能测试)
- [JMeter 性能测试](#jmeter-性能测试)
- [AIOps 数据采集](#aiops-数据采集)
- [数据集文件结构](#数据集文件结构)
- [字段含义说明](#字段含义说明)

---

## 环境要求

| 工具 | 版本 | 用途 |
|------|------|------|
| Python | ≥ 3.10 | 数据采集 / Selenium 测试 |
| minikube | ≥ v1.30 | 本地 Kubernetes 集群 |
| kubectl | 与集群版本匹配 | K8s 管理 |
| istioctl | v1.26+ | 服务网格（获取 qps/latency 指标） |
| Chrome | 任意 | Selenium 主要测试浏览器 |
| Firefox | 任意（可选） | 跨浏览器兼容性测试 |
| JMeter | ≥ 5.6 | 性能测试 |

---

## 快速启动

### 1. 启动 minikube

```bash
# Windows 上需要先确认 Docker Desktop 正在运行
DOCKER_HOST="npipe:////./pipe/docker_engine" minikube start
```

### 2. 安装 Python 依赖

```bash
pip install -r requirements.txt
pip install -r tests/selenium/requirements.txt
```

### 3. 启动所有 Port-Forward（独立终端）

```bash
bash scripts/setup_port_forward.sh
```

启动后各服务地址：

| 服务 | 地址 |
|------|------|
| Online Boutique 前端 | http://localhost:8080 |
| Prometheus | http://localhost:9090 |
| SockShop 前端（如需） | http://localhost:8081 |

---

## Selenium 功能测试

### 测试覆盖范围

| 测试类 | 测试用例 | 说明 |
|--------|----------|------|
| TC-B01 主页加载 | 4 | 标题、商品列表、导航栏、SLA（<10s） |
| TC-B02 商品浏览 | 3 | 点击商品、价格验证、货币切换 |
| TC-B03 购物车 | 3 | 加购、购物车内容、结账表单出现 |
| TC-B04 结账流程 | 2 | 表单可见性、端到端下单确认 |
| TC-CB 跨浏览器 | 4×2 | Chrome + Firefox 各跑一遍 |

### 运行方式

```bash
# 方式1：一键运行脚本（推荐）
bash scripts/run_selenium_tests.sh

# 方式2：只跑功能测试（Chrome headless）
bash scripts/run_selenium_tests.sh --test boutique

# 方式3：跑跨浏览器测试
bash scripts/run_selenium_tests.sh --cross-browser

# 方式4：可视化模式（浏览器窗口可见）
bash scripts/run_selenium_tests.sh --visible

# 方式5：指定浏览器
bash scripts/run_selenium_tests.sh --browser firefox

# 方式6：直接用 pytest
cd tests/selenium
export BOUTIQUE_URL=http://localhost:8080
python -m pytest test_boutique_functional.py -v \
    --html=results/report.html --self-contained-html
```

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `BOUTIQUE_URL` | `http://localhost:8080` | Online Boutique 前端地址 |
| `SELENIUM_BROWSER` | `chrome` | 浏览器：`chrome` / `firefox` |
| `SELENIUM_HEADLESS` | `true` | `false` 可见窗口模式 |
| `PAGE_TIMEOUT` | `30` | 页面加载超时（秒） |

### 查看测试报告

测试完成后，HTML 报告自动生成：

```
tests/selenium/results/
  report_final.html       ← 主报告，浏览器直接打开
  report_boutique.html    ← 功能测试报告
  report_cross_browser.html ← 跨浏览器报告
  timing_metrics.json     ← 页面加载时间、交互响应时间数据
  screenshots/            ← 各步骤截图（主页、购物车、订单确认等）
```

直接打开 HTML 报告：

```bash
# Windows
start tests/selenium/results/report_final.html

# Linux/Mac
open tests/selenium/results/report_final.html
```

### 性能指标说明（timing_metrics.json）

每条记录格式：
```json
{
  "test": "boutique_homepage_load",
  "value_ms": 2238.0,
  "url": "http://localhost:8080",
  "browser": "chrome"
}
```

指标含义：

| 指标名 | 含义 |
|--------|------|
| `boutique_homepage_load` | 主页完整加载时间（loadEventEnd - navigationStart） |
| `boutique_homepage_sla` | SLA 检测值，目标 < 10000ms |
| `boutique_product_click_ms` | 点击商品到详情页显示的响应时间 |
| `boutique_currency_switch_ms` | 货币切换到页面更新的响应时间 |
| `boutique_add_to_cart_ms` | 点击加购到购物车页面就绪的时间 |
| `boutique_checkout_submit_ms` | 提交订单到确认页面出现的时间 |
| `cross_browser_boutique_load_chrome` | Chrome 主页加载时间 |
| `cross_browser_boutique_load_firefox` | Firefox 主页加载时间 |
| `cross_chrome_ttfb_ms` | Chrome 首字节时间（TTFB） |
| `cross_firefox_ttfb_ms` | Firefox 首字节时间（TTFB） |
| `cross_chrome_dom_load_ms` | Chrome DOMContentLoaded 时间 |
| `cross_firefox_dom_load_ms` | Firefox DOMContentLoaded 时间 |

---

## JMeter 性能测试

### 测试计划说明

**Online Boutique 测试计划** (`tests/jmeter/plans/online_boutique_load_test.jmx`)

| 场景 | 虚拟用户数 | 说明 |
|------|-----------|------|
| 场景1 正常负载 | 10 | 完整用户流程：浏览→加购→结账 |
| 场景2 中等负载 | 30 | 只读型：主页 + 商品浏览 |
| 场景3 峰值负载 | 50 | 仅主页，压测极限并发 |

每个 HTTP 请求配置了响应时间断言：主页 < 3s，加购 < 5s，下单 < 10s。

### JMeter 安装位置

JMeter 5.6.3 已安装在：`E:\apache-jmeter-5.6.3\`

可执行文件：`E:\apache-jmeter-5.6.3\bin\jmeter.bat`

如需重新安装或在其他机器上安装：
```bash
# 下载（使用 archive 镜像）
curl -fsSL --insecure -o jmeter.zip \
  "https://archive.apache.org/dist/jmeter/binaries/apache-jmeter-5.6.3.zip"
# 解压到目标目录
unzip jmeter.zip -d /e/
```

### 运行方式

**方式1：命令行无头模式（推荐，自动生成 HTML 报告）**

```bash
# 确保 port-forward 已启动（http://localhost:8080）
bash scripts/run_jmeter_tests.sh --target boutique \
    --jmeter /c/jmeter/bin/jmeter.bat

# 自定义并发和时长
bash scripts/run_jmeter_tests.sh \
    --target boutique \
    --users 30 \
    --duration 120 \
    --ramp-up 15 \
    --jmeter /c/jmeter/bin/jmeter.bat
```

**方式2：JMeter GUI 模式（可视化，适合调试）**

```bash
# 打开 JMeter GUI
/c/jmeter/bin/jmeter.bat

# 在 GUI 中：
# File → Open → tests/jmeter/plans/online_boutique_load_test.jmx
# 点击 Run → Start (Ctrl+R)
# 在 Summary Report 监听器中查看实时结果
```

**方式3：命令行指定参数覆盖**

```bash
/c/jmeter/bin/jmeter.bat \
  -n \
  -t tests/jmeter/plans/online_boutique_load_test.jmx \
  -l tests/jmeter/results/result.jtl \
  -e -o tests/jmeter/results/html_report \
  -Jbase_url=localhost \
  -Jbase_port=8080 \
  -Jduration=60 \
  -Jramp_up=10
```

### 查看结果

```
tests/jmeter/results/
  boutique_results.jtl      ← 原始结果（CSV 格式，每行一个请求）
  boutique_report/
    index.html              ← JMeter HTML 报告（直接打开）
  boutique_console.log      ← 运行日志
```

打开 HTML 报告：
```bash
start tests/jmeter/results/boutique_report/index.html
```

脚本自动解析 JTL 并打印摘要：
```
--- boutique_results.jtl 性能指标摘要 ---
  总请求数:     1234
  成功率:       98.5%  (错误率: 1.5%)
  平均响应时间: 450ms
  P50响应时间: 380ms
  P90响应时间: 890ms
  P95响应时间: 1200ms
  最大响应时间: 4500ms
  最小响应时间: 12ms
```

### JTL 文件字段说明

| 字段 | 含义 |
|------|------|
| `timestamp` | 请求发起时间（Unix ms） |
| `elapsed` | 响应时间（ms） |
| `label` | 请求名称（如 "01-访问主页"） |
| `responseCode` | HTTP 状态码 |
| `success` | 是否成功（true/false） |
| `bytes` | 响应体大小（字节） |
| `latency` | 首字节时间（ms） |
| `connectTime` | TCP 连接建立时间（ms） |
| `threadName` | 虚拟用户线程名 |
| `URL` | 请求 URL |

---

## AIOps 数据采集

### 模式一：Smoke 模式（Mock 数据，无需集群）

生成结构完整的样例数据集，用于验证下游模型接口。

```bash
bash scripts/run_smoke_export.sh
```

或直接：

```bash
python -m benchmark.cli smoke \
    --output data/datasets/online_boutique_short_fault_v1 \
    --duration-minutes 10 \
    --step-seconds 5
```

- 生成 120 个 5s 等间隔时间点（10分钟）
- 包含 2 个预设故障事件（INC-001 cpu_stress / INC-002 pod_kill）
- 故障落在 test split，train/valid 全部正常

### 模式二：Live 模式（真实 Prometheus 数据）

从真实 Online Boutique 集群采集数据。

**前提：** minikube 运行、Istio 注入完成、port-forward 启动

```bash
# 终端1：保持 port-forward
bash scripts/setup_port_forward.sh

# 终端2：采集数据
bash scripts/run_live_export.sh \
    --prometheus-url http://localhost:9090 \
    --lookback-minutes 30
```

或直接：

```bash
python -m benchmark.cli live \
    --prometheus-url http://localhost:9090 \
    --output data/datasets/online_boutique_short_fault_v1 \
    --lookback-minutes 30 \
    --step-seconds 5 \
    --queries-config configs/prometheus_queries.yaml
```

**可用指标（63/66）：**
- `cpu_usage`、`memory_usage`、`restart_count`：通过 cAdvisor / kube-state-metrics 采集，所有 11 个服务均可用
- `qps`、`latency_p95`、`error_rate`：通过 Istio Envoy 采集，redis-cart（TCP 协议）不可用

**长时间采集（真实实验）：**

```bash
# 采集最近 24 小时数据（生产级）
python -m benchmark.cli live \
    --prometheus-url http://localhost:9090 \
    --output data/datasets/online_boutique_24h \
    --lookback-minutes 1440 \
    --step-seconds 5
```

### 清理旧数据

```bash
bash scripts/clean_dataset.sh
```

---

## 数据集文件结构

```
data/datasets/online_boutique_short_fault_v1/
│
├── dataset_meta.json              # 数据集全局元信息
│
├── raw/                           # 原始采集数据（未处理）
│   ├── prometheus_raw_long.csv    # 从 Prometheus 拉取的原始时序数据
│   ├── fault_injection_log.csv    # 故障注入记录（smoke模式有值）
│   └── load_trace.csv             # 负载轨迹标记（high/medium/low）
│
├── processed/                     # 模型可用的处理后数据
│   ├── metrics_5s.csv             # 全量时序数据（timestamp + 66特征，5s间隔）
│   ├── feature_schema.csv         # 66个特征的元数据说明
│   │
│   ├── train_x.csv                # 训练集特征（无标签）
│   ├── valid_x.csv                # 验证集特征（无标签）
│   ├── test_x.csv                 # 测试集特征（无标签）
│   │
│   ├── train_y.csv                # 训练集标签（全为0，正常段）
│   ├── valid_y.csv                # 验证集标签（全为0，正常段）
│   ├── test_y.csv                 # 测试集标签（含异常点，smoke模式）
│   │
│   ├── incidents.csv              # 故障事件真实答案（事件级）
│   │
│   ├── norm_stats.json            # 标准化统计量（仅基于 train_x 计算）
│   ├── splits.json                # 数据集切分边界（时间戳 + 行数）
│   └── quality_report.json        # 数据质量检查报告
│
├── answers/                       # 真实答案（评估用）
│   ├── test_ground_truth.csv      # 点级别异常标签（timestamp, y_true）
│   ├── test_incident_ground_truth.csv  # 事件级别标签（含 incident_id, phase）
│   └── test_root_cause_ground_truth.csv # 根因标签（根因服务、根因维度）
│
└── examples/
    └── sample_submission.csv      # 提交模板（模型预测填写格式）
```

---

## 字段含义说明

### train_x.csv / valid_x.csv / test_x.csv（特征文件）

**格式：** 每行一个时间点，每列一个监控指标。

| 字段名模式 | 示例 | 含义 |
|-----------|------|------|
| `timestamp` | `2026-05-29T00:00:00Z` | UTC 时间戳，ISO 8601 格式，等间隔（5s） |
| `{service}_qps` | `frontend_qps` | 服务每秒请求数（req/s）；来源：Istio `istio_requests_total` |
| `{service}_latency_p95` | `frontend_latency_p95` | P95 响应延迟（ms）；来源：Istio `istio_request_duration_milliseconds_bucket` |
| `{service}_error_rate` | `frontend_error_rate` | 5xx 错误率，范围 [0,1]；来源：Istio，正常时为 0.0 |
| `{service}_cpu_usage` | `frontend_cpu_usage` | CPU 使用量（核心数）；来源：cAdvisor `container_cpu_usage_seconds_total` |
| `{service}_memory_usage` | `frontend_memory_usage` | 内存使用量（MiB）；来源：cAdvisor `container_memory_working_set_bytes` |
| `{service}_restart_count` | `frontend_restart_count` | Pod 累计重启次数；来源：kube-state-metrics `kube_pod_container_status_restarts_total` |

**11个服务：** `frontend`, `cartservice`, `checkoutservice`, `currencyservice`, `emailservice`, `paymentservice`, `productcatalogservice`, `recommendationservice`, `shippingservice`, `adservice`, `redis-cart`

**注意：** `redis-cart` 的 `qps`、`latency_p95`、`error_rate` 在 live 模式下为 NaN（Redis 使用 TCP 协议，Istio 无 HTTP 层指标）。

---

### train_y.csv / valid_y.csv / test_y.csv（标签文件）

| 字段 | 类型 | 含义 |
|------|------|------|
| `timestamp` | string | UTC 时间戳，与对应 x 文件完全对齐 |
| `is_anomaly` | int (0/1) | 该时间点是否为异常：1=异常，0=正常 |
| `incident_id` | string | 所属故障事件 ID（如 `INC-001`），正常点为空 |
| `phase` | string | 时间点阶段：`normal`（正常）/ `fault_effect`（故障生效期） |

**切分规则（smoke模式）：**
- `train_y` / `valid_y`：`is_anomaly` 全为 0（无故障）
- `test_y`：包含正常点和异常点，异常点对应 `incident_id`

---

### incidents.csv（故障事件表）

| 字段 | 含义 |
|------|------|
| `incident_id` | 事件唯一 ID（如 `INC-001`） |
| `injection_start` | 故障注入开始时间（UTC ISO） |
| `injection_end` | 故障注入结束时间（UTC ISO） |
| `effect_start` | 异常效应开始时间（评估标签用此字段） |
| `effect_end` | 异常效应结束时间 |
| `recovery_end` | 恢复完成时间 |
| `fault_type` | 故障类型：`cpu_stress` / `pod_kill` / `network_delay` |
| `target_service` | 直接注入故障的目标服务 |
| `root_cause_service` | 根因服务（可能与 target 不同） |
| `severity` | 故障严重程度：`low` / `medium` / `high` / `critical` |
| `duration_sec` | 故障持续秒数（1分钟故障=60） |
| `valid_incident` | 是否为有效故障事件（`true`/`false`） |
| `root_cause_dims` | 根因特征维度，分号分隔（如 `recommendationservice_cpu_usage;recommendationservice_latency_p95`） |
| `secondary_dims` | 受波及的次级维度，分号分隔 |

---

### feature_schema.csv（特征元数据）

| 字段 | 含义 |
|------|------|
| `feature_name` | 特征全名（格式：`{service}_{metric_type}`） |
| `service` | 所属微服务名称 |
| `metric_type` | 指标类型：`qps` / `latency_p95` / `error_rate` / `cpu_usage` / `memory_usage` / `restart_count` |
| `unit` | 单位：`req/s` / `ms` / `ratio` / `cores` / `MiB` / `count` |
| `source` | 数据来源：`prometheus` |
| `model_input` | 是否作为模型输入（均为 `True`） |
| `expected_min` | 该指标的预期最小值（正常范围下限） |
| `expected_max` | 该指标的预期最大值（正常范围上限） |

---

### norm_stats.json（标准化统计量）

```json
{
  "fit_on": "train_only",
  "features": {
    "frontend_qps": {
      "mean": 2.51,
      "std": 0.18,
      "min": 2.20,
      "max": 2.82
    }
  }
}
```

| 字段 | 含义 |
|------|------|
| `fit_on` | 统计量仅基于训练集计算（`train_only`），防止数据泄露 |
| `features.{name}.mean` | 该特征在训练集上的均值 |
| `features.{name}.std` | 该特征在训练集上的标准差 |
| `features.{name}.min` | 该特征在训练集上的最小值 |
| `features.{name}.max` | 该特征在训练集上的最大值 |

---

### splits.json（数据切分边界）

```json
{
  "train": {"start": "...", "end": "...", "rows": 60},
  "valid": {"start": "...", "end": "...", "rows": 24},
  "test":  {"start": "...", "end": "...", "rows": 36}
}
```

**切分比例（smoke模式）：** train 50% / valid 20% / test 30%

---

### quality_report.json（质量检查报告）

| 字段 | 含义 |
|------|------|
| `row_count` | 总时间点数 |
| `feature_count` | 特征数（应为66） |
| `expected_interval_seconds` | 预期采样间隔（秒） |
| `is_regular_interval` | 是否等间隔（true=通过） |
| `duplicate_timestamp_count` | 重复时间戳数（应为0） |
| `missing_value_count` | 缺失值总数 |
| `nan_count` | NaN 总数 |
| `inf_count` | 无穷值总数（应为0） |
| `constant_feature_count` | 常量特征数（方差为0，仅供参考） |
| `train_rows` / `valid_rows` / `test_rows` | 各切分行数 |
| `test_anomaly_points` | 测试集中异常点数 |
| `test_anomaly_ratio` | 测试集异常比例 |
| `incident_count` | 故障事件总数 |
| `valid_incident_count` | 有效故障事件数 |
| `schema_feature_count` | feature_schema.csv 行数（应为66） |
| `x_has_no_label_columns` | x 文件不含标签列（true=通过） |
| `missing_features` | 无法从 Prometheus 获取数据的特征列表 |
| `missing_feature_count` | 缺失特征数 |
| `passed` | 质量检查是否全部通过 |

---

### answers/test_ground_truth.csv（点级别评估答案）

| 字段 | 含义 |
|------|------|
| `timestamp` | UTC 时间戳，与 `test_x.csv` 完全对齐 |
| `y_true` | 真实标签：1=异常，0=正常 |

---

### answers/test_incident_ground_truth.csv（事件级别评估答案）

| 字段 | 含义 |
|------|------|
| `timestamp` | UTC 时间戳 |
| `incident_id` | 所属故障事件 ID（正常点为空） |
| `phase` | 时间点阶段：`normal` / `fault_effect` |

---

### answers/test_root_cause_ground_truth.csv（根因评估答案）

| 字段 | 含义 |
|------|------|
| `incident_id` | 故障事件 ID |
| `root_cause_service` | 根因微服务名 |
| `root_cause_dims` | 根因特征维度（分号分隔） |
| `fault_type` | 故障类型 |

---

### examples/sample_submission.csv（模型提交模板）

| 字段 | 含义 |
|------|------|
| `timestamp` | UTC 时间戳，与 `test_x.csv` 完全对齐 |
| `anomaly_score` | 模型输出的异常分数（越高越异常，初始填0） |
| `y_pred` | 模型二值预测：1=异常，0=正常（初始填0） |

---

### dataset_meta.json（数据集全局元信息）

| 字段 | 含义 |
|------|------|
| `dataset_name` | 数据集名称 |
| `version` | 版本号 |
| `created_at` | 生成时间（UTC） |
| `mode` | 生成模式：`smoke`（mock）/ `live`（真实采集） |
| `step_seconds` | 采样间隔（秒） |
| `total_rows` | 总时间点数 |
| `feature_count` | 特征数（66） |
| `services` | 包含的微服务列表 |
| `train_rows` / `valid_rows` / `test_rows` | 各切分行数 |
| `incident_count` | 故障事件数（live 模式无注入则为0） |
| `test_anomaly_points` | 测试集异常点数 |
