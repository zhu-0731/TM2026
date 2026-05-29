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

---

## 第二步：运行故障注入与采集

另开一个 **Git Bash** 终端，直接调用 Python CLI：

```bash
cd "e:/0projects/0000Testing-and-Maintenance/Final-exp"

python -m benchmark.cli collect \
    --output data/datasets/online_boutique_rca_v1 \
    --fault-types cpu_stress pod_kill \
    --warmup-minutes 5 \
    --gap-minutes 3
```

脚本自动完成：**预热 → 故障注入 → 等待恢复 → 从 Prometheus 拉取数据 → 写出数据集**。

默认时长约 **15 分钟**（5min 预热 + 2 个故障各 60s + 恢复 + 间隔）。

---

## 常用参数组合

**先演练，不真实注入：**
```bash
python -m benchmark.cli collect \
    --output data/datasets/online_boutique_rca_v1 \
    --fault-types cpu_stress pod_kill \
    --warmup-minutes 5 --gap-minutes 3 \
    --dry-run
```

**3 种故障（约 22 分钟）：**
```bash
python -m benchmark.cli collect \
    --output data/datasets/online_boutique_rca_v1 \
    --fault-types cpu_stress pod_kill network_delay \
    --warmup-minutes 5 --gap-minutes 3
```

**多轮注入（模拟系统长时间运行，随机间隔）：**
```bash
python -m benchmark.cli collect \
    --output data/datasets/online_boutique_rca_v1 \
    --fault-types cpu_stress pod_kill \
    --warmup-minutes 5 \
    --rounds 3 \
    --round-gap-minutes 5 \
    --gap-jitter 60
```

> `--rounds 3` 表示将 `cpu_stress → pod_kill` 循环注入 3 次，故障编号连续（INC-001 ~ INC-006）。  
> `--gap-jitter 60` 表示每个间隔额外叠加 0~60 秒随机时间。

**自定义输出目录（不覆盖旧数据）：**
```bash
python -m benchmark.cli collect `
    --output data/datasets/online_boutique_rca_v1 `
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
| `--output` | 必填 | 数据集输出目录 |
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

## 数据集保存位置

输出到 `--output` 指定的目录，结构如下：

```
data/datasets/online_boutique_rca_v1/
│
├── injection_log.json              ← ChaosMesh 真实注入记录（含注入/生效时间戳）
├── dataset_meta.json               ← 采集窗口、服务列表、行数等元信息
│
├── processed/
│   ├── train_x.csv                 ← 训练特征（正常流量）
│   ├── train_y.csv                 ← 训练标签（全为 is_anomaly=0）
│   ├── valid_x.csv                 ← 验证特征
│   ├── valid_y.csv                 ← 验证标签
│   ├── test_x.csv                  ← 测试特征（含故障期间）
│   ├── test_y.csv                  ← 测试标签（故障行 is_anomaly=1）
│   ├── incidents.csv               ← 故障事件表（injection/effect 时间分离）
│   ├── quality_report.json         ← 质量检查报告
│   ├── feature_schema.csv          ← 66 个特征的名称与含义
│   ├── norm_stats.json             ← 均值/方差（仅基于 train_x）
│   └── splits.json                 ← train/valid/test 边界时间戳
│
└── answers/
    ├── test_ground_truth.csv           ← y_true（用于评估）
    ├── test_incident_ground_truth.csv  ← 每个异常点对应的故障 ID
    └── test_root_cause_ground_truth.csv← 根因服务 + 根因指标维度
```

---

## 验证数据集

采集完成后用以下命令快速核查：

```bash
python -c "
import json
from pathlib import Path

base = Path('data/datasets/online_boutique_rca_v1')

q = json.loads((base / 'processed/quality_report.json').read_text())
print('质量检查:')
print(f'  passed:              {q[\"passed\"]}')
print(f'  row_count:           {q[\"row_count\"]}')
print(f'  test_anomaly_points: {q[\"test_anomaly_points\"]}')
print(f'  valid_incident_count:{q[\"valid_incident_count\"]}')
print(f'  missing_features:    {q[\"missing_features\"]}')

print()
log = json.loads((base / 'injection_log.json').read_text())
print('注入记录:')
for e in log:
    print(f'  {e[\"incident_id\"]} ({e[\"fault_type\"]}): '
          f'注入={e[\"injection_start\"]}  生效={e[\"effect_start\"]}  成功={e[\"success\"]}')
"
```

上次真实运行的输出：

```
质量检查:
  passed:              True
  row_count:           140
  test_anomaly_points: 24
  valid_incident_count:2
  missing_features:    ['redis-cart_qps', 'redis-cart_latency_p95', 'redis-cart_error_rate']

注入记录:
  INC-001 (cpu_stress): 注入=2026-05-29T04:30:48Z  生效=2026-05-29T04:30:53Z  成功=True
  INC-002 (pod_kill):   注入=2026-05-29T04:35:22Z  生效=2026-05-29T04:35:27Z  成功=True
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

**`quality_report.passed=False` 且 `test_anomaly_points=0`**  
→ 故障落在了 train split 而非 test split，增大预热时间：
```bash
python -m benchmark.cli collect --output ... --warmup-minutes 8 ...
```

**port-forward 中断，注入已完成但导出失败**  
→ 重启 port-forward 后，用 reexport 工具从已有 Prometheus 数据重新导出（无需重跑实验）：
```bash
# 编辑 benchmark/reexport.py 中的时间戳，参考 injection_log.json
python -m benchmark.reexport
```
