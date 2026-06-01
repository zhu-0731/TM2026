"""Generate mock time-series data for smoke testing."""
from __future__ import annotations

import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass

from .config import SERVICES, METRICS, FEATURE_NAMES, _REDIS_METRICS, ExportConfig


@dataclass
class MockIncident:
    incident_id: str
    fault_type: str
    target_service: str
    root_cause_service: str
    severity: str
    duration_sec: int
    effect_start: datetime
    effect_end: datetime
    root_cause_dims: list[str]
    secondary_dims: list[str]
    # Real ChaosMesh timestamps (default to effect times for smoke/mock mode)
    injection_start: datetime | None = None  # when kubectl apply was called
    injection_end: datetime | None = None    # when kubectl delete was called
    recovery_end: datetime | None = None     # when service fully recovered

    def __post_init__(self):
        # Smoke mode: injection times == effect times (no separate injection step)
        if self.injection_start is None:
            self.injection_start = self.effect_start
        if self.injection_end is None:
            self.injection_end = self.effect_end
        if self.recovery_end is None:
            self.recovery_end = self.effect_end


# Normal baseline values per metric type
NORMAL_BASE = {
    "qps":           (100.0,  10.0),   # (mean, std)
    "latency_p95":   (50.0,   5.0),
    "error_rate":    (0.01,   0.002),
    "cpu_usage":     (0.3,    0.05),
    "memory_usage":  (256.0,  20.0),
    "restart_count": (0.0,    0.0),
}


def _normal_series(n: int, metric: str, rng: np.random.Generator) -> np.ndarray:
    mean, std = NORMAL_BASE[metric]
    vals = rng.normal(mean, std, n)
    if metric in ("qps", "latency_p95", "cpu_usage", "memory_usage"):
        vals = np.maximum(vals, 0.0)
    elif metric == "error_rate":
        vals = np.clip(vals, 0.0, 1.0)
    elif metric == "restart_count":
        vals = np.zeros(n)
    return vals


def _apply_anomaly(vals: np.ndarray, metric: str, fault_type: str, mask: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Apply fault-type-specific anomaly pattern to masked indices."""
    out = vals.copy()
    if fault_type == "cpu_stress":
        if metric == "cpu_usage":
            out[mask] *= rng.uniform(5, 10, mask.sum())
        elif metric == "latency_p95":
            out[mask] *= rng.uniform(3, 6, mask.sum())
    elif fault_type == "pod_kill":
        if metric == "restart_count":
            out[mask] += rng.uniform(3, 8, mask.sum())
        elif metric == "error_rate":
            out[mask] = np.clip(out[mask] * rng.uniform(20, 50, mask.sum()), 0, 1)
        elif metric == "qps":
            out[mask] *= rng.uniform(0.1, 0.3, mask.sum())
    elif fault_type == "network_delay":
        if metric == "latency_p95":
            out[mask] *= rng.uniform(8, 15, mask.sum())
        elif metric == "error_rate":
            out[mask] = np.clip(out[mask] * rng.uniform(5, 10, mask.sum()), 0, 1)
    return out


def generate_mock_data(cfg: ExportConfig, seed: int = 42) -> tuple[pd.DataFrame, list[MockIncident]]:
    """
    Returns (metrics_df, incidents) where metrics_df has columns:
      [timestamp] + FEATURE_NAMES (63 cols), all UTC ISO timestamps.
    Incidents are guaranteed to fall within the test split.
    """
    rng = np.random.default_rng(seed)
    n_points = (cfg.duration_minutes * 60) // cfg.step_seconds
    start_ts = datetime(2026, 5, 29, 0, 0, 0, tzinfo=timezone.utc)
    timestamps = [start_ts + timedelta(seconds=i * cfg.step_seconds) for i in range(n_points)]

    # Determine test split boundary
    train_end_idx = int(n_points * cfg.train_ratio)
    valid_end_idx = train_end_idx + int(n_points * cfg.valid_ratio)
    test_start_idx = valid_end_idx  # test begins here

    test_start_ts = timestamps[test_start_idx]
    test_end_ts = timestamps[-1]
    test_duration_sec = (test_end_ts - test_start_ts).total_seconds()

    if test_duration_sec < 130:
        raise ValueError(f"Test split too short ({test_duration_sec}s) to fit 2 incidents of 60s each")

    # Place 2 incidents in test split with no overlap
    # Incident 1: cpu_stress on recommendationservice
    inc1_start_offset = 5  # seconds into test split
    inc1_start = test_start_ts + timedelta(seconds=inc1_start_offset)
    inc1_end = inc1_start + timedelta(seconds=60)

    # Incident 2: pod_kill on cartservice, starts after inc1 ends + buffer
    inc2_start = inc1_end + timedelta(seconds=10)
    inc2_end = inc2_start + timedelta(seconds=60)

    if inc2_end > test_end_ts + timedelta(seconds=cfg.step_seconds):
        raise ValueError("Test split too short to fit 2 non-overlapping incidents")

    incidents = [
        MockIncident(
            incident_id="INC-001",
            fault_type="cpu_stress",
            target_service="recommendationservice",
            root_cause_service="recommendationservice",
            severity="high",
            duration_sec=60,
            effect_start=inc1_start,
            effect_end=inc1_end,
            root_cause_dims=["recommendationservice_cpu_usage", "recommendationservice_latency_p95"],
            secondary_dims=["frontend_latency_p95"],
        ),
        MockIncident(
            incident_id="INC-002",
            fault_type="pod_kill",
            target_service="cartservice",
            root_cause_service="cartservice",
            severity="critical",
            duration_sec=60,
            effect_start=inc2_start,
            effect_end=inc2_end,
            root_cause_dims=["cartservice_restart_count", "cartservice_error_rate", "cartservice_qps"],
            secondary_dims=["frontend_error_rate"],
        ),
    ]

    # Build anomaly mask: ts_index -> (incident, is_secondary)
    # For each timestamp, check if it falls in any incident window
    ts_array = np.array([t.timestamp() for t in timestamps])
    inc1_mask = (ts_array >= inc1_start.timestamp()) & (ts_array < inc1_end.timestamp())
    inc2_mask = (ts_array >= inc2_start.timestamp()) & (ts_array < inc2_end.timestamp())

    # Generate baseline data for all services/metrics
    data = {"timestamp": [t.strftime("%Y-%m-%dT%H:%M:%SZ") for t in timestamps]}

    for svc in SERVICES:
        for met in (_REDIS_METRICS if svc == "redis-cart" else METRICS):
            fname = f"{svc}_{met}"
            vals = _normal_series(n_points, met, rng)

            # Apply INC-001 anomaly (cpu_stress) to root cause dims
            if fname in incidents[0].root_cause_dims:
                vals = _apply_anomaly(vals, met, "cpu_stress", inc1_mask, rng)
            # Apply secondary effect for INC-001
            elif fname in incidents[0].secondary_dims:
                if met == "latency_p95":
                    vals[inc1_mask] *= rng.uniform(1.5, 2.5, inc1_mask.sum())

            # Apply INC-002 anomaly (pod_kill) to root cause dims
            if fname in incidents[1].root_cause_dims:
                vals = _apply_anomaly(vals, met, "pod_kill", inc2_mask, rng)
            # Apply secondary effect for INC-002
            elif fname in incidents[1].secondary_dims:
                if met == "error_rate":
                    vals[inc2_mask] = np.clip(vals[inc2_mask] * rng.uniform(3, 5, inc2_mask.sum()), 0, 1)

            data[fname] = vals

    df = pd.DataFrame(data)
    assert list(df.columns) == ["timestamp"] + FEATURE_NAMES
    return df, incidents
