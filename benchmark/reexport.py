"""
Re-export a dataset from already-collected Prometheus data.

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

OUTPUT_DIR = Path("data/datasets/online_boutique_rca_v1")
PROM_URL   = "http://localhost:9090"
QUERIES    = Path("configs/prometheus_queries.yaml")
STEP       = 5
# ────────────────────────────────────────────────────────────────────────


def main():
    from benchmark.config import ExportConfig
    from benchmark.exporter import fetch_live_data
    from benchmark.dataset_builder import build_and_write_dataset
    from benchmark.mock_data import MockIncident

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)

    total_sec  = (COLLECTION_END - COLLECTION_START).total_seconds()
    first_fault = min(inc["effect_start"] for inc in INCIDENTS)
    warmup_sec  = (first_fault - COLLECTION_START).total_seconds()

    train_ratio = round(min((warmup_sec * 0.80) / total_sec, 0.70), 3)
    valid_ratio = round(min(((warmup_sec - 30) * 0.10) / total_sec, 0.15), 3)
    print(f"Splits: train={train_ratio:.1%}  valid={valid_ratio:.1%}  "
          f"test={1-train_ratio-valid_ratio:.1%}")

    cfg = ExportConfig(
        output_dir=OUTPUT_DIR,
        step_seconds=STEP,
        prometheus_url=PROM_URL,
        mode="collect",
        train_ratio=train_ratio,
        valid_ratio=valid_ratio,
    )

    ts = lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"Fetching from Prometheus: {ts(COLLECTION_START)} → {ts(COLLECTION_END)} ...")
    metrics_df, missing = fetch_live_data(
        cfg, QUERIES,
        start=COLLECTION_START,
        end=COLLECTION_END,
    )
    print(f"Got {len(metrics_df)} time points, {len(missing)} features missing")

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

    quality = build_and_write_dataset(
        metrics_df, incidents, cfg,
        missing_features=missing,
        collection_start=ts(COLLECTION_START),
        collection_end=ts(COLLECTION_END),
    )
    print(f"\nDataset: {OUTPUT_DIR}")
    print(f"Test anomaly points: {quality['test_anomaly_points']}")
    print(f"Quality passed:      {quality['passed']}")

    # Write injection_log.json to prove real ChaosMesh execution
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
            "experiment_name":  f"inc00{i+1}-{inc['fault_type'].replace('_','-')}-{inc['target_service']}",
            "source":           "reexport_from_real_chaosmesh_run",
        }
        for i, inc in enumerate(INCIDENTS)
    ]
    log_path = OUTPUT_DIR / "injection_log.json"
    log_path.write_text(json.dumps(log, indent=2))
    print(f"Injection log:       {log_path}")

    if not quality["passed"]:
        import sys
        sys.exit(1)


if __name__ == "__main__":
    main()
