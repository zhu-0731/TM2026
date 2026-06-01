# Notebooks

## demo_pipeline.ipynb

演示如何读取 `online_boutique_rca_full_v1` 数据集，并用自动化 pipeline 完成
训练 / 验证 / 测试 + 评测 + 绘图。

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
- 对照 `answers/` 评测：F1 / Precision / Recall / ROC-AUC / PR-AUC，以及逐 incident 检出率
- 绘图：分数时间线、ROC-PR 曲线、分数分布
- 所有产物写入 `output/<时间戳>_<run_name>/`，**每次运行独立目录，不覆盖**

### 输出产物

每次运行生成：

| 文件 | 内容 |
|------|------|
| `metrics.json` | 检测 + RCA 指标汇总 |
| `predictions.csv` | 逐时间点的 score / y_pred / y_true |
| `per_incident.csv` | 每个 incident 是否被检出 |
| `score_timeline.png` | 异常分数时间线（叠加真实异常区间） |
| `roc_pr_curves.png` | ROC 与 PR 曲线 |
| `score_distribution.png` | 正常 vs 异常的分数分布 |

> `output/` 已在 `.gitignore` 中，实验结果不入库。

### 编程接口

不依赖 notebook 也可直接用：

```python
from benchmark.pipeline import Pipeline, DatasetBundle

bundle = DatasetBundle.load("data/datasets/online_boutique_rca_full_v1")
pipe = Pipeline(bundle, run_name="my_detector")
result = pipe.run(MyDetector())
print(result.metrics)
```
