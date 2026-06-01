"""Live Prometheus data exporter."""
from __future__ import annotations

import sys
import yaml
import pandas as pd
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from .config import ExportConfig, FEATURE_NAMES, SERVICES, _REDIS_METRICS
from .prometheus_client import PrometheusClient


def load_prometheus_queries(path: Path) -> dict[str, str]:
    """Load feature->PromQL mapping from YAML."""
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("queries", {})


def fetch_live_data(
    cfg: ExportConfig,
    queries_path: Path,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> tuple[pd.DataFrame, list[str]]:
    """
    Fetch data from Prometheus for all 66 features.

    Args:
        cfg: Export configuration (prometheus_url, step_seconds, lookback_minutes).
        queries_path: Path to prometheus_queries.yaml.
        start: Explicit start time (overrides lookback_minutes if provided).
        end: Explicit end time (overrides now() if provided).

    Returns:
        (df, missing_features) where df has columns [timestamp] + FEATURE_NAMES.
        Timestamps come from the first successful Prometheus query_range response.
    """
    client = PrometheusClient(cfg.prometheus_url)
    if not client.check_reachable():
        print(f"ERROR: Prometheus not reachable at {cfg.prometheus_url}", file=sys.stderr)
        sys.exit(1)

    queries = load_prometheus_queries(queries_path)

    if end is None:
        end = datetime.now(tz=timezone.utc)
    if start is None:
        start = end - timedelta(minutes=cfg.lookback_minutes)

    missing_features: list[str] = []
    master_timestamps: list[str] | None = None
    series_map: dict[str, pd.Series] = {}

    for fname in FEATURE_NAMES:
        query = queries.get(fname)
        if not query:
            missing_features.append(fname)
            continue
        try:
            series = client.query_range(query, start, end, cfg.step_seconds)
        except RuntimeError as e:
            print(f"WARNING: {fname} query failed: {e}", file=sys.stderr)
            missing_features.append(fname)
            continue

        if series is None:
            missing_features.append(fname)
        else:
            if master_timestamps is None:
                master_timestamps = list(series.index)
            series_map[fname] = series

    if master_timestamps is None:
        n_points = int((end - start).total_seconds()) // cfg.step_seconds
        master_timestamps = [
            (start + timedelta(seconds=i * cfg.step_seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")
            for i in range(n_points)
        ]
        print("WARNING: No Prometheus queries returned data — using synthetic timestamp grid",
              file=sys.stderr)

    n_points = len(master_timestamps)
    data: dict[str, list] = {"timestamp": master_timestamps}

    for fname in FEATURE_NAMES:
        if fname in series_map:
            aligned = series_map[fname].reindex(master_timestamps)
            data[fname] = aligned.tolist()
        else:
            data[fname] = [float("nan")] * n_points

    df = pd.DataFrame(data)
    return df, missing_features


MAX_FORWARD_FILL = 4


def impute_features(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Impute NaN values in feature columns using metric-type-aware strategies.

    Strategy:
    - error_rate / latency_p95: if same-service qps == 0 (or NaN), fill with 0.0.
      Fallback: forward-fill up to MAX_FORWARD_FILL for isolated scrape gaps when qps > 0.
    - cpu_usage / memory_usage / restart_count: forward-fill up to MAX_FORWARD_FILL.

    Returns (imputed_df, imputation_stats).
    """
    out = df.copy()
    imputed_features: dict[str, int] = {}

    for svc in SERVICES:
        if svc != "redis-cart":
            qps_col = f"{svc}_qps"
            if qps_col in out.columns:
                qps_zero = out[qps_col].fillna(0) == 0
                for met in ("error_rate", "latency_p95"):
                    col = f"{svc}_{met}"
                    if col not in out.columns:
                        continue
                    # Pass 1: qps==0 → metric must be 0 (no traffic)
                    fill_mask = qps_zero & out[col].isna()
                    n = int(fill_mask.sum())
                    if n:
                        out.loc[fill_mask, col] = 0.0
                        imputed_features[col] = imputed_features.get(col, 0) + n
                    # Pass 2: qps>0 but histogram scrape gap → forward-fill
                    n_before = int(out[col].isna().sum())
                    if not n_before:
                        continue
                    out[col] = out[col].ffill(limit=MAX_FORWARD_FILL)
                    n_filled = n_before - int(out[col].isna().sum())
                    if n_filled:
                        imputed_features[col] = imputed_features.get(col, 0) + n_filled

        for met in ("cpu_usage", "memory_usage", "restart_count"):
            col = f"{svc}_{met}"
            if col not in out.columns:
                continue
            n_before = int(out[col].isna().sum())
            if not n_before:
                continue
            # ffill then bfill: covers gaps up to 2×MAX_FORWARD_FILL sandwiched between valid values
            out[col] = out[col].ffill(limit=MAX_FORWARD_FILL).bfill(limit=MAX_FORWARD_FILL)
            n_after = int(out[col].isna().sum())
            n_filled = n_before - n_after
            if n_filled:
                imputed_features[col] = imputed_features.get(col, 0) + n_filled

    feat_cols = [f for f in FEATURE_NAMES if f in out.columns]
    remaining_nan_count = int(out[feat_cols].isna().sum().sum())
    remaining_nan_features = [c for c in feat_cols if out[c].isna().any()]

    return out, {
        "imputation_strategy": "zero_qps_fill0_and_ffill_bfill_limit4",
        "imputed_value_count": sum(imputed_features.values()),
        "imputed_features": imputed_features,
        "remaining_nan_count": remaining_nan_count,
        "remaining_nan_features": remaining_nan_features,
    }
