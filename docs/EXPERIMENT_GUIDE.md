# 故障注入实验操作指南

从零开始完整运行一次 ChaosMesh 故障注入 + AIOps 数据采集实验。

---

## 前置条件

- Docker Desktop 已启动
- minikube 已启动（`minikube status` 显示 `host: Running`）
- Online Boutique 和 ChaosMesh Pod 全部就绪

验证命令（PowerShell）：

```powershell
$env:DOCKER_HOST = "npipe:////./pipe/docker_engine"
kubectl get pods -n online-boutique   # 期望 12 个 2/2 Running
kubectl get pods -n chaos-testing     # 期望 6 个 Running
```

---

## 第一步：开启 Port-Forward（保持不关）

打开一个 **Git Bash** 终端，进入项目目录后运行：

```bash
cd "e:/0projects/0000Testing-and-Maintenance/Final-exp"
bash scripts/setup_port_forward.sh
```

等看到 `Port-forwards active` 后不要关闭这个窗口。  
访问 Grafana 实时监控：http://localhost:3000/d/f9R_XXJvz/online-boutique-aiops（admin/admin）

---

## 第二步：运行故障注入与采集

另开一个 **Git Bash** 终端，直接调用 Python CLI：

```bash
cd "e:/0projects/0000Testing-and-Maintenance/Final-exp"

python -m benchmark.cli collect \
    --output data/runs/run_01 \
    --fault-types cpu_stress pod_kill \
    --warmup-minutes 5 \
    --gap-minutes 3
```

脚本自动完成：**预热 → 故障注入 → 等待恢复 → 从 Prometheus 拉取数据 → NaN 补全 → 写出数据集**。

默认时长约 **15 分钟**（5min 预热 + 2 个故障各 60s + 恢复 + 间隔）。

---

## 常用参数组合

**先演练，不真实注入：**
```bash
python -m benchmark.cli collect \
    --output data/runs/run_dry \
    --fault-types cpu_stress pod_kill \
    --warmup-minutes 5 --gap-minutes 3 \
    --dry-run
```

**3 种故障（约 22 分钟）：**
```bash
python -m benchmark.cli collect \
    --output data/runs/run_02 \
    --fault-types cpu_stress pod_kill network_delay \
    --warmup-minutes 5 --gap-minutes 3
```

**多轮注入（模拟系统长时间运行，随机间隔）：**
```bash
python -m benchmark.cli collect \
    --output data/runs/run_03 \
    --fault-types cpu_stress pod_kill \
    --warmup-minutes 5 \
    --rounds 3 \
    --round-gap-minutes 5 \
    --gap-jitter 60
```

> `--rounds 3` 表示将 `cpu_stress → pod_kill` 循环注入 3 次，故障编号连续（INC-001 ~ INC-006）。  
> `--gap-jitter 60` 表示每个间隔额外叠加 0~60 秒随机时间。

**PowerShell 多行写法（用反引号续行）：**
```powershell
python -m benchmark.cli collect `
    --output data/runs/run_01 `
    --fault-types cpu_stress pod_kill `
    --warmup-minutes 5 `
    --rounds 3 `
    --round-gap-minutes 5 `
    --gap-jitter 60
```

---

## 所有参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--output` | 必填 | 本次 run 的输出目录（如 `data/runs/run_01`） |
| `--run-id` | 目录名 | Run ID 字符串，记录在 run_meta.json 中 |
| `--fault-types` | `cpu_stress pod_kill` | 故障类型，可选 `cpu_stress` `pod_kill` `network_delay` |
| `--warmup-minutes` | `5` | 首次注入前的正常流量时长（分钟） |
| `--gap-minutes` | `3` | 同一轮内两次故障之间的间隔（分钟） |
| `--rounds` | `1` | 注入轮数，多于 1 时循环执行 fault-types |
| `--round-gap-minutes` | `5` | 轮与轮之间的间隔（分钟），仅 rounds>1 时有效 |
| `--gap-jitter` | `0` | 每个间隔额外叠加的最大随机秒数（均匀分布） |
| `--step-seconds` | `5` | Prometheus 采样间隔 |
| `--prometheus-url` | `http://localhost:9090` | Prometheus 地址 |
| `--dry-run` | — | 演练模式，不实际注入故障 |

---

## 数据集保存位置（run-based 格式）

每次采集输出到 `--output` 指定的目录，结构如下：

```
data/runs/run_01/
│
├── injection_log.json              ← ChaosMesh 真实注入记录（含注入/生效时间戳）
├── run_meta.json                   ← run 元信息（run_id、采集窗口、feature_count 等）
├── README.md
│
├── processed/
│   ├── run_x.csv                   ← 本次 run 特征（timestamp + 63 列，无 NaN/Inf）
│   ├── run_y.csv                   ← 本次 run 标签（is_anomaly, incident_id, phase）
│   ├── metrics_5s.csv              ← 同 run_x（完整快照）
│   ├── incidents.csv               ← 故障事件表
│   ├── feature_schema.csv          ← 63 个特征的名称与含义
│   ├── norm_stats.json             ← 均值/方差（基于本次 run 全量数据）
│   └── quality_report.json        ← 质量检查报告（passed/fail_reasons）
│
├── answers/
│   ├── ground_truth.csv            ← y_true（用于评估）
│   ├── incident_ground_truth.csv   ← 每个异常点对应的故障 ID
│   └── root_cause_ground_truth.csv ← 根因服务 + 根因指标维度
│
├── raw/
│   ├── prometheus_raw_long.csv
│   ├── chaos_events.csv
│   └── load_trace.csv
│
└── examples/
    └── sample_submission.csv
```

多次采集时，每次 run 独立保存：
```
data/runs/
├── run_01/   ← 第1次采集
├── run_02/   ← 第2次采集
├── run_03/   ← 第3次采集
├── ...
└── manifest.csv  ← 自动维护，记录所有 run 的摘要
```

---

## 合并多次采集（assemble）

积累 4 次以上 quality_passed=true 的 run 后，用 assemble 命令生成 train/valid/test 数据集：

```bash
python -m benchmark.cli assemble \
    --runs-root data/runs \
    --output data/datasets/online_boutique_rca_v1
```

划分规则：
- 最后 2 次 run → test set
- 倒数第 3 次 run → valid set
- 更早的 run → train set

---

## 验证单次 run

采集完成后用以下命令快速核查：

```bash
python -c "
import json
from pathlib import Path

base = Path('data/runs/run_01')

q = json.loads((base / 'processed/quality_report.json').read_text())
print('质量检查:')
print(f'  passed:           {q[\"passed\"]}')
print(f'  row_count:        {q[\"row_count\"]}')
print(f'  nan_count:        {q[\"nan_count\"]}')
print(f'  imputed_count:    {q[\"imputed_value_count\"]}')
print(f'  anomaly_points:   {q[\"anomaly_points\"]}')
print(f'  valid_incidents:  {q[\"valid_incident_count\"]}')
if q.get(\"fail_reasons\"):
    for r in q[\"fail_reasons\"]:
        print(f'  FAIL: {r}')

print()
log = json.loads((base / 'injection_log.json').read_text())
print('注入记录:')
for e in log:
    print(f'  {e[\"incident_id\"]} ({e[\"fault_type\"]}): '
          f'注入={e[\"injection_start\"]}  生效={e[\"effect_start\"]}  成功={e[\"success\"]}')
"
```

---

## 故障排除

**`Prometheus: UNREACHABLE`**  
→ port-forward 未启动或已断开，重新执行 `bash scripts/setup_port_forward.sh`。

**`ChaosMesh experiment did not reach Running state`**  
→ ChaosMesh 控制器未就绪：
```bash
export DOCKER_HOST="npipe:////./pipe/docker_engine"
kubectl rollout restart deployment chaos-controller-manager -n chaos-testing
kubectl rollout status deployment chaos-controller-manager -n chaos-testing --timeout=60s
```

**`quality_report.passed=False` 且 `nan_count>0`**  
→ NaN 补全失败，查看 `fail_reasons` 定位具体特征。  
→ 常见原因：某服务 pod 完全不可达，所有数据点缺失（ffill 无法补全首段全缺）。  
→ 可在服务恢复后重新采集，或检查 Prometheus targets 是否 scrape 到该服务。

**`quality_report.passed=False` 且 `anomaly_points=0`（chaos run）**  
→ ChaosMesh 注入失败，故障未生效。检查 `injection_log.json` 中 `success` 字段。

**port-forward 中断，注入已完成但导出失败**  
→ 重启 port-forward 后，用 reexport 工具从已有 Prometheus 数据重新导出（无需重跑实验）：
```bash
# 编辑 benchmark/reexport.py 中的时间戳，参考 injection_log.json
python -m benchmark.reexport
```
