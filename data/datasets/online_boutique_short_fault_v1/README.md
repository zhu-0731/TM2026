# Online Boutique AIOps Benchmark Dataset

## Quick Start

```bash
pip install -r requirements.txt
bash scripts/run_smoke_export.sh
```

## Live Mode

```bash
bash scripts/run_live_export.sh --prometheus-url http://localhost:9090
```

## Output Structure

- `processed/train_x.csv`, `valid_x.csv`, `test_x.csv` ！ features (66 columns)
- `processed/train_y.csv`, `valid_y.csv`, `test_y.csv` ！ labels
- `answers/test_ground_truth.csv` ！ y_true for evaluation
- `examples/sample_submission.csv` ！ submission template
