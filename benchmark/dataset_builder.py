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


# ─────────────────────────────────────────────────────────────────────────────
# Run-based output (live / collect)
# ─────────────────────────────────────────────────────────────────────────────

def build_and_write_run(
    metrics_df: pd.DataFrame,
    mock_incidents: list,
    cfg: ExportConfig,
    run_id: str,
    imputation_stats: dict | None = None,
    missing_features: list | None = None,
    collection_start: str | None = None,
    collection_end: str | None = None,
    chaos_enabled: bool = False,
    run_type: str = "normal",
) -> dict:
    """
    Write a single collection run in run-based format (no train/valid/test split).
    Returns quality_report dict.  passed=False causes the caller to exit(1).

    Output structure:
      <cfg.output_dir>/
        processed/
          run_x.csv        timestamp + 63 features, no NaN/Inf, no labels
          run_y.csv        timestamp, is_anomaly, incident_id, phase
          metrics_5s.csv   same as run_x (full view)
          incidents.csv
          feature_schema.csv
          norm_stats.json
          quality_report.json
        answers/
          ground_truth.csv
          incident_ground_truth.csv
          root_cause_ground_truth.csv
        raw/
          prometheus_raw_long.csv
          chaos_events.csv
          load_trace.csv
        examples/
          sample_submission.csv
        run_meta.json
        README.md
    """
    out = cfg.output_dir
    proc_dir = out / "processed"
    ans_dir = out / "answers"
    raw_dir = out / "raw"
    ex_dir = out / "examples"
    for d in (proc_dir, ans_dir, raw_dir, ex_dir):
        d.mkdir(parents=True, exist_ok=True)

    imputation_stats = imputation_stats or {}
    missing_features = missing_features or []

    # --- run_x.csv (no labels, no NaN/Inf) ---
    run_x = metrics_df[X_COLS].copy()
    _write_csv(run_x, proc_dir / "run_x.csv")

    # --- metrics_5s.csv (same as run_x, full snapshot) ---
    _write_csv(run_x, proc_dir / "metrics_5s.csv")

    # --- incidents.csv ---
    incidents_df = build_incidents_df(mock_incidents)
    _write_csv(incidents_df, proc_dir / "incidents.csv")

    # --- run_y.csv ---
    run_labels = build_labels(metrics_df["timestamp"].tolist(), incidents_df)
    _write_csv(run_labels, proc_dir / "run_y.csv")

    # --- feature_schema.csv ---
    schema_df = build_feature_schema()
    _write_csv(schema_df, proc_dir / "feature_schema.csv")

    # --- norm_stats.json (fit on all run data) ---
    feat_data = run_x[FEATURE_NAMES]
    norm_stats: dict = {"fit_on": "run_all", "features": {}}
    for col in FEATURE_NAMES:
        col_data = feat_data[col].dropna()
        norm_stats["features"][col] = {
            "mean": float(col_data.mean()) if len(col_data) else 0.0,
            "std":  float(col_data.std())  if len(col_data) > 1 else 0.0,
            "min":  float(col_data.min())  if len(col_data) else 0.0,
            "max":  float(col_data.max())  if len(col_data) else 0.0,
        }
    (proc_dir / "norm_stats.json").write_text(json.dumps(norm_stats, indent=2))

    # --- answers/ ---
    gt = run_labels[["timestamp", "is_anomaly"]].rename(columns={"is_anomaly": "y_true"})
    _write_csv(gt, ans_dir / "ground_truth.csv")
    _write_csv(run_labels[["timestamp", "incident_id", "phase"]], ans_dir / "incident_ground_truth.csv")
    rc_rows = [
        {
            "incident_id":        row["incident_id"],
            "root_cause_service": row["root_cause_service"],
            "root_cause_dims":    row["root_cause_dims"],
            "fault_type":         row["fault_type"],
        }
        for _, row in incidents_df.iterrows()
    ]
    _write_csv(pd.DataFrame(rc_rows), ans_dir / "root_cause_ground_truth.csv")

    # --- examples/sample_submission.csv ---
    sub = run_x[["timestamp"]].copy()
    sub["anomaly_score"] = 0.0
    sub["y_pred"] = 0
    _write_csv(sub, ex_dir / "sample_submission.csv")

    # --- raw/ ---
    _write_csv(run_x, raw_dir / "prometheus_raw_long.csv")
    if len(incidents_df) > 0:
        chaos_log = incidents_df[[
            "incident_id", "injection_start", "injection_end", "fault_type", "target_service"
        ]].copy()
    else:
        chaos_log = pd.DataFrame(columns=[
            "incident_id", "injection_start", "injection_end", "fault_type", "target_service"
        ])
    _write_csv(chaos_log, raw_dir / "chaos_events.csv")
    _write_csv(
        pd.DataFrame({"timestamp": metrics_df["timestamp"], "load_level": "medium"}),
        raw_dir / "load_trace.csv",
    )

    # --- quality_report.json ---
    quality = _build_quality_report_run(
        metrics_df=metrics_df,
        run_x=run_x,
        run_labels=run_labels,
        incidents_df=incidents_df,
        schema_df=schema_df,
        gt=gt,
        sub=sub,
        cfg=cfg,
        imputation_stats=imputation_stats,
        missing_features=missing_features,
        run_type=run_type,
    )
    (proc_dir / "quality_report.json").write_text(json.dumps(quality, indent=2))

    # --- run_meta.json ---
    from .config import SERVICES
    now_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_meta = {
        "run_id":                    run_id,
        "mode":                      cfg.mode,
        "dataset_type":              "run_collection",
        "run_type":                  run_type,
        "collection_start":          collection_start,
        "collection_end":            collection_end,
        "created_at":                now_str,
        "sampling_interval_seconds": cfg.step_seconds,
        "feature_count":             len(FEATURE_NAMES),
        "services":                  SERVICES,
        "metrics_per_service":       ["qps", "latency_p95", "error_rate",
                                      "cpu_usage", "memory_usage", "restart_count"],
        "chaos_enabled":             chaos_enabled,
        "prometheus_url":            cfg.prometheus_url,
        "namespace":                 "online-boutique",
        "incidents_count":           len(incidents_df),
        "anomaly_points":            int(run_labels["is_anomaly"].sum()),
        "timezone":                  "UTC",
        "run_dir":                   str(out),
    }
    (out / "run_meta.json").write_text(json.dumps(run_meta, indent=2))

    # --- README.md ---
    readme = (
        f"# Online Boutique AIOps Benchmark - Run {run_id}\n\n"
        f"Run type: {run_type}\n"
        f"Collection: {collection_start} → {collection_end}\n"
        f"Incidents: {len(incidents_df)}\n"
        f"Anomaly points: {run_meta['anomaly_points']}\n"
        f"Quality passed: {quality['passed']}\n\n"
        "## Files\n\n"
        "- `processed/run_x.csv` — features (63 cols, no NaN/Inf, no labels)\n"
        "- `processed/run_y.csv` — labels (is_anomaly, incident_id, phase)\n"
        "- `processed/incidents.csv` — fault injection events\n"
        "- `answers/ground_truth.csv` — y_true for evaluation\n"
        "- `examples/sample_submission.csv` — submission template\n"
    )
    (out / "README.md").write_text(readme)

    return quality


def _build_quality_report_run(
    metrics_df: pd.DataFrame,
    run_x: pd.DataFrame,
    run_labels: pd.DataFrame,
    incidents_df: pd.DataFrame,
    schema_df: pd.DataFrame,
    gt: pd.DataFrame,
    sub: pd.DataFrame,
    cfg: ExportConfig,
    imputation_stats: dict,
    missing_features: list,
    run_type: str,
) -> dict:
    """Strict quality report for a single run. Any hard-fail → passed=False."""
    feat_df = run_x[FEATURE_NAMES]

    ts_series = pd.to_datetime(metrics_df["timestamp"])
    diffs = ts_series.diff().dropna().dt.total_seconds()
    is_regular = bool(len(diffs) > 0 and (diffs == cfg.step_seconds).all())

    dup_ts = int(metrics_df["timestamp"].duplicated().sum())
    nan_cnt = int(feat_df.isnull().sum().sum())
    inf_cnt = int(np.isinf(feat_df.fillna(0).values.astype(float)).sum())
    constant = int((feat_df.std(axis=0, ddof=0) == 0).sum())

    anomaly_pts = int(run_labels["is_anomaly"].sum())
    run_rows = len(run_x)
    anomaly_ratio = round(anomaly_pts / run_rows, 4) if run_rows > 0 else 0.0

    valid_incidents = (
        int(incidents_df["valid_incident"].sum())
        if "valid_incident" in incidents_df.columns else 0
    )

    bad_cols = LABEL_COLS.intersection(set(run_x.columns))
    x_clean = len(bad_cols) == 0

    gt_consistent = bool(len(gt) == len(run_labels) and
                         (gt["y_true"].values == run_labels["is_anomaly"].values).all())

    sub_ts_ok = bool(len(sub) == len(run_x) and
                     (sub["timestamp"].values == run_x["timestamp"].values).all())

    # root_cause_dims must reference valid feature names
    schema_features = set(schema_df["feature_name"].tolist())
    rca_ok = True
    if len(incidents_df) > 0 and "root_cause_dims" in incidents_df.columns:
        for dims_str in incidents_df["root_cause_dims"]:
            for dim in str(dims_str).split(";"):
                if dim.strip() and dim.strip() not in schema_features:
                    rca_ok = False
                    break

    # incidents must not overlap
    incidents_overlap = False
    if len(incidents_df) > 1 and "effect_start" in incidents_df.columns:
        rows = incidents_df.sort_values("effect_start").reset_index(drop=True)
        for i in range(len(rows) - 1):
            es_next = rows.loc[i + 1, "effect_start"]
            ee_curr = rows.loc[i, "effect_end"]
            if es_next < ee_curr:
                incidents_overlap = True
                break

    # Hard fail conditions
    fail_reasons: list[str] = []
    if nan_cnt > 0:
        fail_reasons.append(f"run_x contains {nan_cnt} NaN values")
    if inf_cnt > 0:
        fail_reasons.append(f"run_x contains {inf_cnt} Inf values")
    if not x_clean:
        fail_reasons.append(f"run_x contains label columns: {sorted(bad_cols)}")
    if len(FEATURE_NAMES) != 63:
        fail_reasons.append(f"feature_count={len(FEATURE_NAMES)} != 63")
    if len(schema_df) != 63:
        fail_reasons.append(f"schema_feature_count={len(schema_df)} != 63")
    if not is_regular:
        fail_reasons.append("timestamps not at regular 5s intervals")
    if dup_ts > 0:
        fail_reasons.append(f"duplicate_timestamp_count={dup_ts}")
    if not gt_consistent:
        fail_reasons.append("ground_truth y_true != run_y is_anomaly")
    if not sub_ts_ok:
        fail_reasons.append("sample_submission timestamps != run_x timestamps")
    if not rca_ok:
        fail_reasons.append("root_cause_dims reference features not in schema")
    if incidents_overlap:
        fail_reasons.append("incidents have overlapping effect windows")
    if run_type == "chaos" and anomaly_pts == 0:
        fail_reasons.append("chaos run has anomaly_points=0 — injection may have failed")
    if run_type == "chaos" and len(incidents_df) == 0:
        fail_reasons.append("chaos run has no incidents in incidents.csv")
    if missing_features:
        remaining = imputation_stats.get("remaining_nan_count", 0)
        if remaining > 0:
            fail_reasons.append(
                f"missing_features not fully handled: {missing_features[:5]}, "
                f"{remaining} NaN remain after imputation"
            )
    if imputation_stats.get("remaining_nan_count", 0) > 0:
        fail_reasons.append(
            f"imputation did not resolve all NaN: "
            f"{imputation_stats['remaining_nan_count']} remain in "
            f"{imputation_stats.get('remaining_nan_features', [])[:5]}"
        )

    checks_pass = len(fail_reasons) == 0

    return {
        "row_count":                 len(metrics_df),
        "feature_count":             len(FEATURE_NAMES),
        "expected_interval_seconds": cfg.step_seconds,
        "is_regular_interval":       is_regular,
        "duplicate_timestamp_count": dup_ts,
        "missing_value_count":       nan_cnt,
        "nan_count":                 nan_cnt,
        "inf_count":                 inf_cnt,
        "constant_feature_count":    constant,
        "run_rows":                  run_rows,
        "anomaly_points":            anomaly_pts,
        "anomaly_ratio":             anomaly_ratio,
        "incident_count":            len(incidents_df),
        "valid_incident_count":      valid_incidents,
        "schema_feature_count":      len(schema_df),
        "x_has_no_label_columns":    x_clean,
        "imputation_strategy":       imputation_stats.get("imputation_strategy", "none"),
        "imputed_value_count":       imputation_stats.get("imputed_value_count", 0),
        "imputed_features":          imputation_stats.get("imputed_features", {}),
        "missing_features":          missing_features,
        "ground_truth_consistent":   gt_consistent,
        "sample_submission_ts_ok":   sub_ts_ok,
        "rca_dims_valid":            rca_ok,
        "fail_reasons":              fail_reasons,
        "passed":                    checks_pass,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Smoke-mode output (train/valid/test split — used only for smoke testing)
# ─────────────────────────────────────────────────────────────────────────────

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
    Used by smoke mode only.
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

    train_df = metrics_df.iloc[:train_end].reset_index(drop=True)
    valid_df = metrics_df.iloc[train_end:valid_end].reset_index(drop=True)
    test_df  = metrics_df.iloc[valid_end:].reset_index(drop=True)

    # --- incidents.csv ---
    incidents_df = build_incidents_df(mock_incidents)
    _write_csv(incidents_df, proc_dir / "incidents.csv")

    # --- Labels ---
    train_labels = build_labels(train_df["timestamp"].tolist(), incidents_df)
    valid_labels  = build_labels(valid_df["timestamp"].tolist(), incidents_df)
    test_labels   = build_labels(test_df["timestamp"].tolist(), incidents_df)

    has_incidents = len(mock_incidents) > 0
    if has_incidents and len(train_labels) > 0:
        assert train_labels["is_anomaly"].sum() == 0, \
            "Train split contains anomalies — check incident placement"
    if has_incidents and len(valid_labels) > 0:
        assert valid_labels["is_anomaly"].sum() == 0, \
            "Valid split contains anomalies — check incident placement"

    # --- X / Y files ---
    train_x = train_df[X_COLS]
    valid_x  = valid_df[X_COLS]
    test_x   = test_df[X_COLS]

    _write_csv(train_x, proc_dir / "train_x.csv")
    _write_csv(valid_x,  proc_dir / "valid_x.csv")
    _write_csv(test_x,   proc_dir / "test_x.csv")
    _write_csv(train_labels, proc_dir / "train_y.csv")
    _write_csv(valid_labels,  proc_dir / "valid_y.csv")
    _write_csv(test_labels,   proc_dir / "test_y.csv")

    # --- metrics_5s.csv ---
    _write_csv(metrics_df[X_COLS], proc_dir / "metrics_5s.csv")

    # --- feature_schema.csv ---
    schema_df = build_feature_schema()
    _write_csv(schema_df, proc_dir / "feature_schema.csv")

    # --- norm_stats.json (fit on train only) ---
    feat_data = train_x[FEATURE_NAMES]
    norm_stats: dict = {"fit_on": "train_only", "features": {}}
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
    gt = test_labels[["timestamp", "is_anomaly"]].rename(columns={"is_anomaly": "y_true"})
    _write_csv(gt, ans_dir / "test_ground_truth.csv")
    _write_csv(test_labels[["timestamp", "incident_id", "phase"]], ans_dir / "test_incident_ground_truth.csv")
    rc_rows = [
        {
            "incident_id":        row["incident_id"],
            "root_cause_service": row["root_cause_service"],
            "root_cause_dims":    row["root_cause_dims"],
            "fault_type":         row["fault_type"],
        }
        for _, row in incidents_df.iterrows()
    ]
    _write_csv(pd.DataFrame(rc_rows), ans_dir / "test_root_cause_ground_truth.csv")

    # --- examples/sample_submission.csv ---
    sub = test_x[["timestamp"]].copy()
    sub["anomaly_score"] = 0.0
    sub["y_pred"] = 0
    _write_csv(sub, ex_dir / "sample_submission.csv")

    # --- raw/ ---
    _write_csv(metrics_df[["timestamp"] + FEATURE_NAMES], raw_dir / "prometheus_raw_long.csv")
    if len(incidents_df) > 0:
        fault_log = incidents_df[[
            "incident_id", "injection_start", "injection_end", "fault_type", "target_service"
        ]].copy()
    else:
        fault_log = pd.DataFrame(columns=[
            "incident_id", "injection_start", "injection_end", "fault_type", "target_service"
        ])
    _write_csv(fault_log, raw_dir / "fault_injection_log.csv")
    _write_csv(
        pd.DataFrame({"timestamp": metrics_df["timestamp"], "load_level": "medium"}),
        raw_dir / "load_trace.csv",
    )

    # --- dataset_meta.json ---
    now_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    from .config import SERVICES
    meta = {
        "dataset_name":        cfg.output_dir.name,
        "version":             "1.0.0",
        "created_at":          now_str,
        "mode":                cfg.mode,
        "step_seconds":        cfg.step_seconds,
        "total_rows":          n,
        "feature_count":       len(FEATURE_NAMES),
        "services":            SERVICES,
        "train_rows":          len(train_x),
        "valid_rows":          len(valid_x),
        "test_rows":           len(test_x),
        "incident_count":      len(incidents_df),
        "test_anomaly_points": int(test_labels["is_anomaly"].sum()),
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

## Output Structure

- `processed/train_x.csv`, `valid_x.csv`, `test_x.csv` — features (63 columns)
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
    metrics_df: pd.DataFrame,
    train_x: pd.DataFrame,
    valid_x: pd.DataFrame,
    test_x: pd.DataFrame,
    test_labels: pd.DataFrame,
    incidents_df: pd.DataFrame,
    schema_df: pd.DataFrame,
    cfg: ExportConfig,
    missing_features: list | None = None,
) -> dict:
    feat_df = metrics_df[FEATURE_NAMES]

    ts_series = pd.to_datetime(metrics_df["timestamp"])
    diffs = ts_series.diff().dropna().dt.total_seconds()
    is_regular = bool(len(diffs) > 0 and (diffs == cfg.step_seconds).all())

    dup_ts = int(metrics_df["timestamp"].duplicated().sum())
    nan_cnt = int(feat_df.isnull().sum().sum())
    inf_cnt = int(np.isinf(feat_df.fillna(0).values.astype(float)).sum())
    constant = int((feat_df.std(axis=0, ddof=0) == 0).sum())

    test_anomaly_pts = int(test_labels["is_anomaly"].sum())
    test_rows = len(test_x)
    test_anomaly_ratio = round(test_anomaly_pts / test_rows, 4) if test_rows > 0 else 0.0

    valid_incidents = (
        int(incidents_df["valid_incident"].sum())
        if "valid_incident" in incidents_df.columns else 0
    )

    bad_cols = LABEL_COLS.intersection(set(train_x.columns))
    x_clean = len(bad_cols) == 0

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
