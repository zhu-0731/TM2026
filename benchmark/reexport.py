"""
Re-export a dataset run from already-collected Prometheus data.

Use when the ChaosMesh injection succeeded but the dataset export failed,
to avoid re-running the experiment. Edit the timestamps and incident
definitions below to match your actual injection run.

Usage:
    python -m benchmark.reexport
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

# ── Edit these to match your actual injection run ────────────────────────
# Run: 2026-05-30 failed collection, 4 rounds × (cpu_stress + pod_kill)
# Timestamps from: kubectl get events -n online-boutique -o json
COLLECTION_START = datetime(2026, 5, 30,  6, 40, 47, tzinfo=timezone.utc)  # INC-001 Applied - 5min warmup
COLLECTION_END   = datetime(2026, 5, 30,  7, 38, 43, tzinfo=timezone.utc)  # INC-008 Recovered + 90s

INCIDENTS = [
    # Round 1
    {
        "incident_id":        "INC-001",
        "fault_type":         "cpu_stress",
        "target_service":     "recommendationservice",
        "root_cause_service": "recommendationservice",
        "severity":           "high",
        "duration_sec":       60,
        "injection_start": datetime(2026, 5, 30,  6, 45, 47, tzinfo=timezone.utc),
        "injection_end":   datetime(2026, 5, 30,  6, 46, 46, tzinfo=timezone.utc),
        "recovery_end":    datetime(2026, 5, 30,  6, 47, 16, tzinfo=timezone.utc),
        "effect_start":    datetime(2026, 5, 30,  6, 45, 52, tzinfo=timezone.utc),
        "effect_end":      datetime(2026, 5, 30,  6, 46, 46, tzinfo=timezone.utc),
        "root_cause_dims": ["recommendationservice_cpu_usage", "recommendationservice_latency_p95"],
        "secondary_dims":  ["frontend_latency_p95"],
    },
    {
        "incident_id":        "INC-002",
        "fault_type":         "pod_kill",
        "target_service":     "cartservice",
        "root_cause_service": "cartservice",
        "severity":           "critical",
        "duration_sec":       60,
        "injection_start": datetime(2026, 5, 30,  6, 50, 37, tzinfo=timezone.utc),
        "injection_end":   datetime(2026, 5, 30,  6, 51, 41, tzinfo=timezone.utc),
        "recovery_end":    datetime(2026, 5, 30,  6, 52, 41, tzinfo=timezone.utc),
        "effect_start":    datetime(2026, 5, 30,  6, 50, 42, tzinfo=timezone.utc),
        "effect_end":      datetime(2026, 5, 30,  6, 51, 41, tzinfo=timezone.utc),
        "root_cause_dims": ["cartservice_restart_count", "cartservice_error_rate", "cartservice_qps"],
        "secondary_dims":  ["frontend_error_rate"],
    },
    # Round 2
    {
        "incident_id":        "INC-003",
        "fault_type":         "cpu_stress",
        "target_service":     "recommendationservice",
        "root_cause_service": "recommendationservice",
        "severity":           "high",
        "duration_sec":       60,
        "injection_start": datetime(2026, 5, 30,  6, 57, 38, tzinfo=timezone.utc),
        "injection_end":   datetime(2026, 5, 30,  6, 58, 38, tzinfo=timezone.utc),
        "recovery_end":    datetime(2026, 5, 30,  6, 59,  8, tzinfo=timezone.utc),
        "effect_start":    datetime(2026, 5, 30,  6, 57, 43, tzinfo=timezone.utc),
        "effect_end":      datetime(2026, 5, 30,  6, 58, 38, tzinfo=timezone.utc),
        "root_cause_dims": ["recommendationservice_cpu_usage", "recommendationservice_latency_p95"],
        "secondary_dims":  ["frontend_latency_p95"],
    },
    {
        "incident_id":        "INC-004",
        "fault_type":         "pod_kill",
        "target_service":     "cartservice",
        "root_cause_service": "cartservice",
        "severity":           "critical",
        "duration_sec":       60,
        "injection_start": datetime(2026, 5, 30,  7, 11, 32, tzinfo=timezone.utc),
        "injection_end":   datetime(2026, 5, 30,  7, 12, 35, tzinfo=timezone.utc),
        "recovery_end":    datetime(2026, 5, 30,  7, 13, 35, tzinfo=timezone.utc),
        "effect_start":    datetime(2026, 5, 30,  7, 11, 37, tzinfo=timezone.utc),
        "effect_end":      datetime(2026, 5, 30,  7, 12, 35, tzinfo=timezone.utc),
        "root_cause_dims": ["cartservice_restart_count", "cartservice_error_rate", "cartservice_qps"],
        "secondary_dims":  ["frontend_error_rate"],
    },
    # Round 3
    {
        "incident_id":        "INC-005",
        "fault_type":         "cpu_stress",
        "target_service":     "recommendationservice",
        "root_cause_service": "recommendationservice",
        "severity":           "high",
        "duration_sec":       60,
        "injection_start": datetime(2026, 5, 30,  7, 18, 28, tzinfo=timezone.utc),
        "injection_end":   datetime(2026, 5, 30,  7, 19, 28, tzinfo=timezone.utc),
        "recovery_end":    datetime(2026, 5, 30,  7, 19, 58, tzinfo=timezone.utc),
        "effect_start":    datetime(2026, 5, 30,  7, 18, 33, tzinfo=timezone.utc),
        "effect_end":      datetime(2026, 5, 30,  7, 19, 28, tzinfo=timezone.utc),
        "root_cause_dims": ["recommendationservice_cpu_usage", "recommendationservice_latency_p95"],
        "secondary_dims":  ["frontend_latency_p95"],
    },
    {
        "incident_id":        "INC-006",
        "fault_type":         "pod_kill",
        "target_service":     "cartservice",
        "root_cause_service": "cartservice",
        "severity":           "critical",
        "duration_sec":       60,
        "injection_start": datetime(2026, 5, 30,  7, 23, 56, tzinfo=timezone.utc),
        "injection_end":   datetime(2026, 5, 30,  7, 24, 59, tzinfo=timezone.utc),
        "recovery_end":    datetime(2026, 5, 30,  7, 25, 59, tzinfo=timezone.utc),
        "effect_start":    datetime(2026, 5, 30,  7, 24,  1, tzinfo=timezone.utc),
        "effect_end":      datetime(2026, 5, 30,  7, 24, 59, tzinfo=timezone.utc),
        "root_cause_dims": ["cartservice_restart_count", "cartservice_error_rate", "cartservice_qps"],
        "secondary_dims":  ["frontend_error_rate"],
    },
    # Round 4
    {
        "incident_id":        "INC-007",
        "fault_type":         "cpu_stress",
        "target_service":     "recommendationservice",
        "root_cause_service": "recommendationservice",
        "severity":           "high",
        "duration_sec":       60,
        "injection_start": datetime(2026, 5, 30,  7, 30, 26, tzinfo=timezone.utc),
        "injection_end":   datetime(2026, 5, 30,  7, 31, 26, tzinfo=timezone.utc),
        "recovery_end":    datetime(2026, 5, 30,  7, 31, 56, tzinfo=timezone.utc),
        "effect_start":    datetime(2026, 5, 30,  7, 30, 31, tzinfo=timezone.utc),
        "effect_end":      datetime(2026, 5, 30,  7, 31, 26, tzinfo=timezone.utc),
        "root_cause_dims": ["recommendationservice_cpu_usage", "recommendationservice_latency_p95"],
        "secondary_dims":  ["frontend_latency_p95"],
    },
    {
        "incident_id":        "INC-008",
        "fault_type":         "pod_kill",
        "target_service":     "cartservice",
        "root_cause_service": "cartservice",
        "severity":           "critical",
        "duration_sec":       60,
        "injection_start": datetime(2026, 5, 30,  7, 36,  9, tzinfo=timezone.utc),
        "injection_end":   datetime(2026, 5, 30,  7, 37, 12, tzinfo=timezone.utc),
        "recovery_end":    datetime(2026, 5, 30,  7, 38, 12, tzinfo=timezone.utc),
        "effect_start":    datetime(2026, 5, 30,  7, 36, 14, tzinfo=timezone.utc),
        "effect_end":      datetime(2026, 5, 30,  7, 37, 12, tzinfo=timezone.utc),
        "root_cause_dims": ["cartservice_restart_count", "cartservice_error_rate", "cartservice_qps"],
        "secondary_dims":  ["frontend_error_rate"],
    },
]

OUTPUT_DIR = Path("data/datasets/online_boutique_rca_4")
PROM_URL   = "http://localhost:9090"
QUERIES    = Path("configs/prometheus_queries.yaml")
STEP       = 5
RUN_ID     = "online_boutique_rca_4"
# ────────────────────────────────────────────────────────────────────────


def main():
    from benchmark.config import ExportConfig
    from benchmark.exporter import fetch_live_data, impute_features
    from benchmark.dataset_builder import build_and_write_run
    from benchmark.mock_data import MockIncident

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)

    cfg = ExportConfig(
        output_dir=OUTPUT_DIR,
        step_seconds=STEP,
        prometheus_url=PROM_URL,
        mode="collect",
    )

    ts = lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"Fetching from Prometheus: {ts(COLLECTION_START)} → {ts(COLLECTION_END)} ...")
    metrics_df, missing = fetch_live_data(
        cfg, QUERIES,
        start=COLLECTION_START,
        end=COLLECTION_END,
    )
    print(f"Got {len(metrics_df)} time points, {len(missing)} features missing")

    # Impute NaN
    metrics_df, imputation_stats = impute_features(metrics_df)
    if imputation_stats["imputed_value_count"] > 0:
        print(f"Imputed {imputation_stats['imputed_value_count']} values")
    if imputation_stats["remaining_nan_count"] > 0:
        print(f"WARNING: {imputation_stats['remaining_nan_count']} NaN remain after imputation")

    incidents = [
        MockIncident(
            incident_id=inc["incident_id"],
            fault_type=inc["fault_type"],
            target_service=inc["target_service"],
            root_cause_service=inc["root_cause_service"],
            severity=inc["severity"],
            duration_sec=inc["duration_sec"],
            effect_start=inc["effect_start"],
            effect_end=inc["effect_end"],
            root_cause_dims=inc["root_cause_dims"],
            secondary_dims=inc["secondary_dims"],
            injection_start=inc["injection_start"],
            injection_end=inc["injection_end"],
            recovery_end=inc["recovery_end"],
        )
        for inc in INCIDENTS
    ]

    quality = build_and_write_run(
        metrics_df, incidents, cfg,
        run_id=RUN_ID,
        imputation_stats=imputation_stats,
        missing_features=missing,
        collection_start=ts(COLLECTION_START),
        collection_end=ts(COLLECTION_END),
        chaos_enabled=True,
        run_type="chaos",
    )
    print(f"\nRun: {OUTPUT_DIR}")
    print(f"Anomaly points: {quality['anomaly_points']}")
    print(f"Quality passed: {quality['passed']}")
    for reason in quality.get("fail_reasons", []):
        print(f"  FAIL: {reason}")

    # Write injection_log.json (backward compat)
    log = [
        {
            "incident_id":      inc["incident_id"],
            "fault_type":       inc["fault_type"],
            "target_service":   inc["target_service"],
            "injection_start":  ts(inc["injection_start"]),
            "injection_end":    ts(inc["injection_end"]),
            "recovery_end":     ts(inc["recovery_end"]),
            "effect_start":     ts(inc["effect_start"]),
            "effect_end":       ts(inc["effect_end"]),
            "success":          True,
            "source":           "reexport_from_real_chaosmesh_run",
        }
        for inc in INCIDENTS
    ]
    log_path = OUTPUT_DIR / "injection_log.json"
    log_path.write_text(json.dumps(log, indent=2))
    print(f"Injection log: {log_path}")

    if not quality["passed"]:
        import sys
        sys.exit(1)


if __name__ == "__main__":
    main()
