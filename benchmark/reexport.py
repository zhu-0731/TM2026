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
COLLECTION_START = datetime(2026, 5, 28, 18, 54, 10, tzinfo=timezone.utc)
COLLECTION_END   = datetime(2026, 5, 28, 19,  5, 47, tzinfo=timezone.utc)

INCIDENTS = [
    {
        "incident_id":        "INC-001",
        "fault_type":         "cpu_stress",
        "target_service":     "recommendationservice",
        "root_cause_service": "recommendationservice",
        "severity":           "high",
        "duration_sec":       60,
        # ChaosMesh kubectl apply/delete timestamps
        "injection_start": datetime(2026, 5, 28, 18, 59, 10, tzinfo=timezone.utc),
        "injection_end":   datetime(2026, 5, 28, 19,  0, 13, tzinfo=timezone.utc),
        "recovery_end":    datetime(2026, 5, 28, 19,  0, 43, tzinfo=timezone.utc),
        # Anomaly effect window (injection + propagation delay)
        "effect_start":    datetime(2026, 5, 28, 18, 59, 15, tzinfo=timezone.utc),
        "effect_end":      datetime(2026, 5, 28, 19,  0, 13, tzinfo=timezone.utc),
        "root_cause_dims": [
            "recommendationservice_cpu_usage",
            "recommendationservice_latency_p95",
        ],
        "secondary_dims": ["frontend_latency_p95"],
    },
    {
        "incident_id":        "INC-002",
        "fault_type":         "pod_kill",
        "target_service":     "cartservice",
        "root_cause_service": "cartservice",
        "severity":           "critical",
        "duration_sec":       60,
        "injection_start": datetime(2026, 5, 28, 19,  3, 44, tzinfo=timezone.utc),
        "injection_end":   datetime(2026, 5, 28, 19,  4, 47, tzinfo=timezone.utc),
        "recovery_end":    datetime(2026, 5, 28, 19,  5, 47, tzinfo=timezone.utc),
        "effect_start":    datetime(2026, 5, 28, 19,  3, 49, tzinfo=timezone.utc),
        "effect_end":      datetime(2026, 5, 28, 19,  4, 47, tzinfo=timezone.utc),
        "root_cause_dims": [
            "cartservice_restart_count",
            "cartservice_error_rate",
            "cartservice_qps",
        ],
        "secondary_dims": ["frontend_error_rate"],
    },
]

OUTPUT_DIR = Path("data/runs/reexport")
PROM_URL   = "http://localhost:9090"
QUERIES    = Path("configs/prometheus_queries.yaml")
STEP       = 5
RUN_ID     = "reexport"
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
