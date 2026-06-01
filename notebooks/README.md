# Notebooks

## demo_pipeline.ipynb

演示如何读取 `online_boutique_rca_full_v1` 数据集，并用自动化 pipeline 完成
训练 / 验证 / 测试 + 完整指标评测 + 绘图。

### 快速开始

```bash
# 从项目根目录启动
jupyter notebook notebooks/demo_pipeline.ipynb
```

### 你需要做的

在 notebook 的 **第 3 节** 实现一个检测器类，只需两个方法：

```python
class MyDetector:
    def fit(self, train_x, train_y, valid_x, valid_y, ctx):
        # 训练。train_x/valid_x 已用 train-only 统计量标准化。
        ...
    def predict(self, test_x, ctx) -> np.ndarray:
        # 返回一维异常分数，长度 == len(test_x)，越大越异常。
        ...
```

### Pipeline 自动完成

- 用 **train-only** 统计量标准化（防泄露）
- 调用你的 `fit` / `predict`
- 选阈值（`threshold_mode`）并对照 `answers/` 计算完整指标体系
- 绘图（7 张）
- 所有产物写入 `output/<时间戳>_<run_name>/`，**每次运行独立目录，不覆盖**

### 阈值模式

| 模式 | 含义 | 可部署 |
|------|------|--------|
| `best_f1` | 在 test 上最大化 F1 | ❌ 仅作上界 |
| `validation_f1` | 在 validation 上最大化 F1 | ✅ |
| `fixed_fpr` | validation 正常点控制目标 FPR（需 `fixed_fpr=`） | ✅ |

> 无论选哪种，pipeline 都会额外输出 best_f1 vs validation_f1 的对比表/图。

---

## 输出产物

每次 `pipe.run()` 在 `output/<时间戳>_<run_name>/` 下生成：

### 数据表（CSV / JSON）

| 文件 | 内容 |
|------|------|
| `metrics.json` | 完整指标，7 大块（见下） |
| `predictions.csv` | 逐时间点 `timestamp, anomaly_score, y_pred, y_true` |
| `per_incident.csv` | 每个 incident：`incident_id, fault_type, target_service, effect_start, effect_end, detected, first_alarm_time, delay_seconds, detected_within_{15,30,60}s` |
| `threshold_comparison.csv` | best_f1 vs validation_f1 并排对比（threshold / deployable / point_f1 / pr_auc / event_recall / recall@30s / FA per hour / median_delay / missed） |

### 图表（PNG）

| 文件 | 内容 | 用途 |
|------|------|------|
| `score_timeline.png` | 异常分数时间线 + 真实异常带 + 阈值线 | 整体检测概览 |
| `roc_pr_curves.png` | ROC 与 PR 曲线 | 排序质量（与阈值无关） |
| `score_distribution.png` | 正常 vs 异常的分数分布直方图 | 看类间可分性、阈值是否合理 |
| `incident_delay_bar.png` | 逐 incident 检测延迟柱状图（按 fault_type 着色，漏检红叉） | 哪些故障检测慢 / 漏检 |
| `event_recall_by_fault_type.png` | 各故障类型的 Event Recall vs Recall@30s | 最关键分组图：快/慢传播故障对比 |
| `false_positive_timeline.png` | 分数时间线 + 误报红点标记 | 误报是随机噪声还是集中在某些时段 |
| `threshold_comparison.png` | best_f1 vs validation_f1 关键指标分组柱状图 | 上界 vs 可部署性能差距 |

---

## metrics.json 结构

```
point_level   : point_precision/recall/f1/accuracy/specificity, TP/FP/TN/FN
ranking       : pr_auc, roc_auc            (y_true 单类时为 null + warning)
event_level   : event_recall, detected/missed_incidents, missed_incident_ids,
                recall_at_{15,30,60}s,
                mean/median/p90/max_detection_delay_seconds,
                per_incident_delay_seconds
false_alarm   : false_alarms_per_hour, false_positive_points,
                normal_points, normal_duration_hours, alarm_ratio
point_adjust  : point_adjust_precision/recall/f1   (OmniAnomaly/USAD 协议，仅补充)
grouped       : *_by_fault_type / *_by_service
                (event_recall, recall_at_30s, median_delay, point_f1)
threshold     : threshold_mode, threshold_value, threshold_deployable,
                use_pred, best_f1, validation_f1, fixed_fpr
warnings      : 评测过程中的告警（如 AUPRC/AUROC 因单类而为 null）
```

### 事件命中与延迟规则

- **事件命中**：某 incident 的 `[effect_start, effect_end]` 内只要有一个 `y_pred=1` 即算检测到。
- **检测延迟**：`delay = first_alarm_time - effect_start`（秒）。漏检 incident 不计入延迟均值，单独在 `missed_incidents` 统计。
- **误报率**：`false_alarms_per_hour = FP / (normal_points * sampling_interval_seconds / 3600)`。
- **point-adjust**：真实异常段内只要命中一点，整段视为正确检出后重算点级指标——仅作与 OmniAnomaly/USAD 对齐的补充，不作主指标。

> `output/` 已在 `.gitignore` 中。仓库内保留一次示例运行 `output/20260601_035535_my_detector/` 供参考。

---

## 编程接口

不依赖 notebook 也可直接用：

```python
from benchmark.pipeline import Pipeline, DatasetBundle

bundle = DatasetBundle.load("data/datasets/online_boutique_rca_full_v1")
pipe = Pipeline(bundle, run_name="my_detector", threshold_mode="validation_f1")
result = pipe.run(MyDetector())
print(result.metrics)
```
