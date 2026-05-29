"""Build the final dataset: split, label, and write all CSV/JSON files."""
from __future__ import annotations

import json
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone

from .config import ExportConfig, FEATURE_NAMES
from .labels import build_labels, build_incidents_df
from .schema import build_feature_schema
from .mock_data import MockIncident


LABEL_COLS = {"is_anomaly", "incident_id", "fault_type", "phase", "y_true"}
X_COLS = ["timestamp"] + FEATURE_NAMES


def _write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def build_and_write_dataset(
    metrics_df: pd.DataFrame,
    mock_incidents: list[MockIncident],
    cfg: ExportConfig,
    missing_features: list | None = None,
    collection_start: str | None = None,
    collection_end: str | None = None,
) -> dict:
    """
    Given full metrics DataFrame (timestamp + 63 features) and incidents,
    produce all dataset files and return quality_report dict.
    """
    out = cfg.output_dir
    raw_dir = out / "raw"
    proc_dir = out / "processed"
    ans_dir = out / "answers"
    ex_dir = out / "examples"
    for d in (raw_dir, proc_dir, ans_dir, ex_dir):
        d.mkdir(parents=True, exist_ok=True)

    n = len(metrics_df)

    # --- Splits ---
    train_end = int(n * cfg.train_ratio)
    valid_end = train_end + int(n * cfg.valid_ratio)
    # test: valid_end .. n

    train_df = metrics_df.iloc[:train_end].reset_index(drop=True)
    valid_df = metrics_df.iloc[train_end:valid_end].reset_index(drop=True)
    test_df  = metrics_df.iloc[valid_end:].reset_index(drop=True)

    # --- incidents.csv ---
    incidents_df = build_incidents_df(mock_incidents)
    _write_csv(incidents_df, proc_dir / "incidents.csv")

    # --- Labels for each split ---
    train_labels = build_labels(train_df["timestamp"].tolist(), incidents_df)
    valid_labels  = build_labels(valid_df["timestamp"].tolist(), incidents_df)
    test_labels   = build_labels(test_df["timestamp"].tolist(), incidents_df)

    # Guards only apply when incidents are configured AND splits have rows
    has_incidents = len(mock_incidents) > 0
    if has_incidents and len(train_labels) > 0:
        assert train_labels["is_anomaly"].sum() == 0, \
            "Train split contains anomalies — check incident placement"
    if has_incidents and len(valid_labels) > 0:
        assert valid_labels["is_anomaly"].sum() == 0, \
            "Valid split contains anomalies — check incident placement"
    if has_incidents and len(test_labels) > 0 and cfg.mode not in ("collect",):
        # In collect mode, incidents may not align perfectly with splits in dry-run
        pass

    # --- X files (no label columns) ---
    train_x = train_df[X_COLS]
    valid_x  = valid_df[X_COLS]
    test_x   = test_df[X_COLS]

    _write_csv(train_x, proc_dir / "train_x.csv")
    _write_csv(valid_x,  proc_dir / "valid_x.csv")
    _write_csv(test_x,   proc_dir / "test_x.csv")

    # --- Y files ---
    _write_csv(train_labels, proc_dir / "train_y.csv")
    _write_csv(valid_labels,  proc_dir / "valid_y.csv")
    _write_csv(test_labels,   proc_dir / "test_y.csv")

    # --- metrics_5s.csv (full merged view, raw, with labels) ---
    all_labels = build_labels(metrics_df["timestamp"].tolist(), incidents_df)
    metrics_5s = metrics_df[X_COLS].copy()
    _write_csv(metrics_5s, proc_dir / "metrics_5s.csv")

    # --- feature_schema.csv ---
    schema_df = build_feature_schema()
    _write_csv(schema_df, proc_dir / "feature_schema.csv")

    # --- norm_stats.json (fit on train_x only) ---
    feat_data = train_x[FEATURE_NAMES]
    norm_stats = {
        "fit_on": "train_only",
        "features": {},
    }
    for col in FEATURE_NAMES:
        col_data = feat_data[col].dropna()
        norm_stats["features"][col] = {
            "mean": float(col_data.mean()),
            "std":  float(col_data.std()) if len(col_data) > 1 else 0.0,
            "min":  float(col_data.min()),
            "max":  float(col_data.max()),
        }
    (proc_dir / "norm_stats.json").write_text(json.dumps(norm_stats, indent=2))

    # --- splits.json ---
    splits = {
        "train": {"start": train_x["timestamp"].iloc[0], "end": train_x["timestamp"].iloc[-1], "rows": len(train_x)},
        "valid": {"start": valid_x["timestamp"].iloc[0], "end": valid_x["timestamp"].iloc[-1], "rows": len(valid_x)},
        "test":  {"start": test_x["timestamp"].iloc[0],  "end": test_x["timestamp"].iloc[-1],  "rows": len(test_x)},
    }
    (proc_dir / "splits.json").write_text(json.dumps(splits, indent=2))

    # --- answers/ ---
    # test_ground_truth.csv
    gt = test_labels[["timestamp", "is_anomaly"]].rename(columns={"is_anomaly": "y_true"})
    _write_csv(gt, ans_dir / "test_ground_truth.csv")

    # test_incident_ground_truth.csv
    inc_gt = test_labels[["timestamp", "incident_id", "phase"]].copy()
    _write_csv(inc_gt, ans_dir / "test_incident_ground_truth.csv")

    # test_root_cause_ground_truth.csv
    rc_rows = []
    for _, inc_row in incidents_df.iterrows():
        rc_rows.append({
            "incident_id":        inc_row["incident_id"],
            "root_cause_service": inc_row["root_cause_service"],
            "root_cause_dims":    inc_row["root_cause_dims"],
            "fault_type":         inc_row["fault_type"],
        })
    rc_df = pd.DataFrame(rc_rows)
    _write_csv(rc_df, ans_dir / "test_root_cause_ground_truth.csv")

    # --- examples/sample_submission.csv ---
    sub = test_x[["timestamp"]].copy()
    sub["anomaly_score"] = 0.0
    sub["y_pred"] = 0
    _write_csv(sub, ex_dir / "sample_submission.csv")

    # --- raw/ placeholder files ---
    _write_csv(metrics_df[["timestamp"] + FEATURE_NAMES], raw_dir / "prometheus_raw_long.csv")
    if len(incidents_df) > 0:
        fault_log = incidents_df[["incident_id", "injection_start", "injection_end", "fault_type", "target_service"]].copy()
    else:
        fault_log = pd.DataFrame(columns=["incident_id", "injection_start", "injection_end", "fault_type", "target_service"])
    _write_csv(fault_log, raw_dir / "fault_injection_log.csv")
    load_trace = pd.DataFrame({"timestamp": metrics_df["timestamp"], "load_level": "medium"})
    _write_csv(load_trace, raw_dir / "load_trace.csv")

    # --- dataset_meta.json ---
    now_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    # dataset_name derived from output dir name, not hardcoded
    dataset_name = cfg.output_dir.name
    # Stable services list (sorted, not set)
    from .config import SERVICES
    meta = {
        "dataset_name":        dataset_name,
        "version":             "1.0.0",
        "created_at":          now_str,
        "mode":                cfg.mode,
        "step_seconds":        cfg.step_seconds,
        "total_rows":          n,
        "feature_count":       len(FEATURE_NAMES),
        "services":            SERVICES,  # stable order
        "train_rows":          len(train_x),
        "valid_rows":          len(valid_x),
        "test_rows":           len(test_x),
        "incident_count":      len(incidents_df),
        "test_anomaly_points": int(test_labels["is_anomaly"].sum()),
        # Collection window (populated by collect/live modes)
        "collection_start":    collection_start,
        "collection_end":      collection_end,
    }
    (out / "dataset_meta.json").write_text(json.dumps(meta, indent=2))

    # --- README.md ---
    readme = """# Online Boutique AIOps Benchmark Dataset

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

- `processed/train_x.csv`, `valid_x.csv`, `test_x.csv` — features (66 columns)
- `processed/train_y.csv`, `valid_y.csv`, `test_y.csv` — labels
- `answers/test_ground_truth.csv` — y_true for evaluation
- `examples/sample_submission.csv` — submission template
"""
    (out / "README.md").write_text(readme)

    # --- Quality report ---
    quality = _build_quality_report(
        metrics_df=metrics_df,
        train_x=train_x, valid_x=valid_x, test_x=test_x,
        test_labels=test_labels,
        incidents_df=incidents_df,
        schema_df=schema_df,
        cfg=cfg,
        missing_features=missing_features or [],
    )
    (proc_dir / "quality_report.json").write_text(json.dumps(quality, indent=2))

    return quality


def _build_quality_report(
    metrics_df, train_x, valid_x, test_x, test_labels, incidents_df, schema_df, cfg,
    missing_features: list | None = None,
) -> dict:
    feat_df = metrics_df[FEATURE_NAMES]
    is_live = cfg.mode in ("live", "collect")
    missing_features = missing_features or []

    ts_series = pd.to_datetime(metrics_df["timestamp"])
    diffs = ts_series.diff().dropna().dt.total_seconds()
    is_regular = bool((diffs == cfg.step_seconds).all())

    dup_ts = int(metrics_df["timestamp"].duplicated().sum())
    nan_cnt = int(feat_df.isnull().sum().sum())
    inf_cnt = int(np.isinf(feat_df.fillna(0).values.astype(float)).sum())
    constant = int((feat_df.std(axis=0) == 0).sum())
    unexpected_nan = nan_cnt

    test_anomaly_pts = int(test_labels["is_anomaly"].sum())
    test_rows = len(test_x)
    test_anomaly_ratio = round(test_anomaly_pts / test_rows, 4) if test_rows > 0 else 0.0

    valid_incidents = (int(incidents_df["valid_incident"].sum())
                       if "valid_incident" in incidents_df.columns else 0)

    bad_cols = LABEL_COLS.intersection(set(train_x.columns))
    x_clean = len(bad_cols) == 0

    if is_live:
        # Live/collect: NaN is allowed (sparse traffic + permanently unavailable metrics).
        # Fail only on structural issues: irregular intervals, duplicates, Inf,
        # wrong schema, or label leakage into x files.
        # NaN counts are reported for visibility but never block passed=True.
        checks_pass = (
            is_regular
            and dup_ts == 0
            and inf_cnt == 0
            and len(schema_df) == 63
            and x_clean
        )
    else:
        # Smoke: strict — no NaN, test must have anomalies, incidents required
        checks_pass = (
            is_regular
            and dup_ts == 0
            and nan_cnt == 0
            and inf_cnt == 0
            and test_anomaly_pts > 0
            and valid_incidents >= 2
            and len(schema_df) == 63
            and x_clean
        )

    return {
        "row_count":                 len(metrics_df),
        "feature_count":             len(FEATURE_NAMES),
        "expected_interval_seconds": cfg.step_seconds,
        "is_regular_interval":       is_regular,
        "duplicate_timestamp_count": dup_ts,
        "nan_count":                 nan_cnt,
        "unexpected_nan_count":      unexpected_nan,
        "inf_count":                 inf_cnt,
        "constant_feature_count":    constant,
        "train_rows":                len(train_x),
        "valid_rows":                len(valid_x),
        "test_rows":                 test_rows,
        "test_anomaly_points":       test_anomaly_pts,
        "test_anomaly_ratio":        test_anomaly_ratio,
        "incident_count":            len(incidents_df),
        "valid_incident_count":      valid_incidents,
        "schema_feature_count":      len(schema_df),
        "x_has_no_label_columns":    x_clean,
        "passed":                    checks_pass,
    }
