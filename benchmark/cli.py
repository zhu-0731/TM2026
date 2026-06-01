"""CLI entry point for the benchmark dataset exporter."""
from __future__ import annotations

import csv
import sys
import json
import time
import random
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

from .config import ExportConfig


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_datetime(s: str) -> datetime:
    """Parse ISO 8601 UTC timestamp (e.g. 2026-05-29T12:00:00Z)."""
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def _update_manifest(run_dir: Path, run_meta: dict, quality: dict) -> None:
    """Append this run's summary to <run_dir.parent>/manifest.csv."""
    runs_root = run_dir.parent
    manifest_path = runs_root / "manifest.csv"
    row = {
        "run_id":           run_meta.get("run_id", ""),
        "run_dir":          str(run_dir),
        "collection_start": run_meta.get("collection_start", ""),
        "collection_end":   run_meta.get("collection_end", ""),
        "mode":             run_meta.get("mode", ""),
        "feature_count":    run_meta.get("feature_count", 63),
        "incident_count":   run_meta.get("incidents_count", 0),
        "anomaly_points":   run_meta.get("anomaly_points", 0),
        "quality_passed":   quality.get("passed", False),
    }
    header = list(row.keys())
    exists = manifest_path.exists()
    try:
        with open(manifest_path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=header)
            if not exists:
                writer.writeheader()
            writer.writerow(row)
        print(f"[manifest] Updated: {manifest_path}")
    except OSError as e:
        print(f"[manifest] WARNING: could not write manifest: {e}", file=sys.stderr)


# ─────────────────────────────────────────────────────────────────────────────
# smoke
# ─────────────────────────────────────────────────────────────────────────────

def cmd_smoke(args: argparse.Namespace) -> None:
    from .mock_data import generate_mock_data
    from .dataset_builder import build_and_write_dataset

    cfg = ExportConfig(
        output_dir=Path(args.output),
        step_seconds=args.step_seconds,
        duration_minutes=args.duration_minutes,
        mode="smoke",
    )

    print(f"[smoke] Generating {args.duration_minutes}min mock data ({args.step_seconds}s step)...")
    metrics_df, mock_incidents = generate_mock_data(cfg)
    print(f"[smoke] Generated {len(metrics_df)} time points, {len(mock_incidents)} incidents")

    quality = build_and_write_dataset(metrics_df, mock_incidents, cfg)
    print(f"[smoke] Dataset written to: {cfg.output_dir}")
    print(f"[smoke] Quality report: passed={quality['passed']}")

    if not quality["passed"]:
        print("ERROR: Quality checks failed. See quality_report.json for details.", file=sys.stderr)
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# live  (run-based, no train/valid/test split)
# ─────────────────────────────────────────────────────────────────────────────

def cmd_live(args: argparse.Namespace) -> None:
    from .exporter import fetch_live_data, impute_features
    from .dataset_builder import build_and_write_run

    cfg = ExportConfig(
        output_dir=Path(args.output),
        step_seconds=args.step_seconds,
        lookback_minutes=args.lookback_minutes,
        prometheus_url=args.prometheus_url,
        mode="live",
    )

    queries_path = Path(args.queries_config)
    if not queries_path.exists():
        print(f"ERROR: Queries config not found: {queries_path}", file=sys.stderr)
        sys.exit(1)

    start_dt: datetime | None = _parse_datetime(args.start_time) if args.start_time else None
    end_dt:   datetime | None = _parse_datetime(args.end_time)   if args.end_time   else None

    if start_dt or end_dt:
        print(f"[live] Fetching window: {args.start_time} → {args.end_time or 'now'} ...")
    else:
        print(f"[live] Fetching last {args.lookback_minutes}min from {args.prometheus_url}...")

    metrics_df, missing = fetch_live_data(cfg, queries_path, start=start_dt, end=end_dt)

    if missing:
        print(f"[live] WARNING: {len(missing)} features missing from Prometheus: {missing[:5]}")

    # Impute NaN values
    metrics_df, imputation_stats = impute_features(metrics_df)
    total_imputed = imputation_stats["imputed_value_count"]
    if total_imputed > 0:
        print(f"[live] Imputed {total_imputed} values across "
              f"{len(imputation_stats['imputed_features'])} features")
    remaining_nan = imputation_stats["remaining_nan_count"]
    if remaining_nan > 0:
        print(f"[live] WARNING: {remaining_nan} NaN values remain after imputation — "
              f"quality will fail: {imputation_stats['remaining_nan_features'][:5]}",
              file=sys.stderr)

    # Determine run_id and timestamps
    run_id = getattr(args, "run_id", None) or cfg.output_dir.name
    now = datetime.now(tz=timezone.utc)
    if start_dt:
        cs_str = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        cs_str = (now - timedelta(minutes=args.lookback_minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")
    ce_str = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ") if end_dt else now.strftime("%Y-%m-%dT%H:%M:%SZ")

    quality = build_and_write_run(
        metrics_df, [], cfg,
        run_id=run_id,
        imputation_stats=imputation_stats,
        missing_features=missing,
        collection_start=cs_str,
        collection_end=ce_str,
        chaos_enabled=False,
        run_type="normal",
    )

    print(f"[live] Run written to: {cfg.output_dir}")
    print(f"[live] Quality report: passed={quality['passed']}")
    for reason in quality.get("fail_reasons", []):
        print(f"  FAIL: {reason}", file=sys.stderr)

    # Update manifest
    run_meta_path = cfg.output_dir / "run_meta.json"
    if run_meta_path.exists():
        run_meta = json.loads(run_meta_path.read_text())
        _update_manifest(cfg.output_dir, run_meta, quality)

    if not quality["passed"]:
        print("ERROR: Quality checks failed. See processed/quality_report.json.", file=sys.stderr)
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# collect  (ChaosMesh fault injection + run-based export)
# ─────────────────────────────────────────────────────────────────────────────

def cmd_collect(args: argparse.Namespace) -> None:
    """
    Fault injection + data collection pipeline:
      1. Warmup phase  (normal traffic, no faults)
      2. Inject fault  (ChaosMesh experiment, record exact timestamps)
      3. Wait for recovery
      4. Repeat for each fault type / round
      5. Fetch full window from Prometheus
      6. Impute NaN values
      7. Build run-based dataset with real RCA ground truth
    """
    from .exporter import fetch_live_data, impute_features
    from .dataset_builder import build_and_write_run
    from .chaos_injector import (
        run_injection, results_to_mock_incidents, FAULT_DEFINITIONS
    )

    fault_types: list[str] = args.fault_types
    for ft in fault_types:
        if ft not in FAULT_DEFINITIONS:
            print(f"ERROR: Unknown fault type '{ft}'. "
                  f"Available: {list(FAULT_DEFINITIONS)}", file=sys.stderr)
            sys.exit(1)

    cfg = ExportConfig(
        output_dir=Path(args.output),
        step_seconds=args.step_seconds,
        prometheus_url=args.prometheus_url,
        mode="collect",
    )

    queries_path = Path(args.queries_config)
    if not queries_path.exists():
        print(f"ERROR: Queries config not found: {queries_path}", file=sys.stderr)
        sys.exit(1)

    project_root = Path(__file__).parent.parent
    dry_run: bool = args.dry_run

    rounds: int = args.rounds
    gap_jitter_sec: int = args.gap_jitter

    print("=" * 60)
    print(" ChaosMesh Fault Injection + Data Collection")
    print("=" * 60)
    print(f" Fault types:     {fault_types}")
    print(f" Rounds:          {rounds}")
    print(f" Warmup:          {args.warmup_minutes}min")
    print(f" Intra-round gap: {args.gap_minutes}min ±{gap_jitter_sec}s jitter")
    if rounds > 1:
        print(f" Inter-round gap: {args.round_gap_minutes}min ±{gap_jitter_sec}s jitter")
    print(f" Step:            {args.step_seconds}s")
    print(f" Output:          {cfg.output_dir}")
    print(f" Dry-run:         {dry_run}")
    print("=" * 60)

    def _jittered_sleep(base_minutes: float, label: str) -> None:
        jitter = random.uniform(0, gap_jitter_sec) if gap_jitter_sec > 0 else 0
        total = base_minutes * 60 + jitter
        jitter_str = f" (+{jitter:.0f}s jitter)" if jitter > 0 else ""
        print(f"\n[collect] {label}: {base_minutes}min{jitter_str} ...")
        if not dry_run:
            time.sleep(total)

    collection_start = datetime.now(tz=timezone.utc)
    print(f"\n[collect] Collection start: {collection_start.strftime('%Y-%m-%dT%H:%M:%SZ')}")

    # --- Warmup ---
    print(f"\n[collect] Warmup phase: {args.warmup_minutes}min normal traffic ...")
    if not dry_run:
        time.sleep(args.warmup_minutes * 60)

    # --- Fault injection (multi-round) ---
    injection_results = []
    inc_counter = 1

    for round_idx in range(rounds):
        if rounds > 1:
            print(f"\n[collect] ===== Round {round_idx + 1}/{rounds} =====")

        for idx, fault_type in enumerate(fault_types):
            inc_id = f"INC-{inc_counter:03d}"
            inc_counter += 1

            print(f"\n[collect] === Injecting {inc_id}: {fault_type} ===")
            result = run_injection(
                fault_type=fault_type,
                incident_id=inc_id,
                project_root=project_root,
                dry_run=dry_run,
            )
            injection_results.append(result)

            is_last_in_round = idx == len(fault_types) - 1
            if not is_last_in_round:
                _jittered_sleep(args.gap_minutes, "Gap between faults")

        is_last_round = round_idx == rounds - 1
        if not is_last_round:
            _jittered_sleep(args.round_gap_minutes,
                            f"Gap between rounds ({round_idx+1}→{round_idx+2})")

    collection_end = datetime.now(tz=timezone.utc)
    print(f"\n[collect] All injections complete. "
          f"End: {collection_end.strftime('%Y-%m-%dT%H:%M:%SZ')}")

    # --- Dry-run summary ---
    if dry_run:
        total_sec = sum(
            60 + FAULT_DEFINITIONS[ft].get("recovery_buffer_sec", 30)
            for ft in fault_types
        ) + args.warmup_minutes * 60 + args.gap_minutes * 60 * (len(fault_types) - 1)
        print(f"\n[dry-run] Estimated total time: {total_sec // 60}min {total_sec % 60}s")
        for r in injection_results:
            print(f"  {r.incident_id} ({r.fault_type}): "
                  f"{r.effect_start.strftime('%H:%M:%SZ')} → {r.effect_end.strftime('%H:%M:%SZ')}")
        print("[dry-run] Done.")
        return

    # --- Fetch from Prometheus ---
    total_minutes = int((collection_end - collection_start).total_seconds() / 60) + 1
    print(f"\n[collect] Fetching {total_minutes}min of data from Prometheus ...")
    metrics_df, missing = fetch_live_data(
        cfg, queries_path,
        start=collection_start,
        end=collection_end,
    )
    print(f"[collect] Got {len(metrics_df)} time points, {len(missing)} features missing")

    # --- Impute NaN ---
    metrics_df, imputation_stats = impute_features(metrics_df)
    total_imputed = imputation_stats["imputed_value_count"]
    if total_imputed > 0:
        print(f"[collect] Imputed {total_imputed} values across "
              f"{len(imputation_stats['imputed_features'])} features")
    remaining_nan = imputation_stats["remaining_nan_count"]
    if remaining_nan > 0:
        print(f"[collect] WARNING: {remaining_nan} NaN remain after imputation — "
              f"quality will fail: {imputation_stats['remaining_nan_features'][:5]}",
              file=sys.stderr)

    # --- Build incidents ---
    incidents = results_to_mock_incidents(injection_results)
    successful = [r for r in injection_results if r.success]
    failed = [r for r in injection_results if not r.success]

    if failed:
        print(f"\n[collect] WARNING: {len(failed)} injections failed: "
              f"{[r.incident_id for r in failed]}", file=sys.stderr)
    if not incidents:
        print("[collect] WARNING: No successful incidents — dataset will have no anomaly labels",
              file=sys.stderr)

    run_type = "chaos" if incidents else "normal"
    run_id = getattr(args, "run_id", None) or cfg.output_dir.name
    cs_str = collection_start.strftime("%Y-%m-%dT%H:%M:%SZ")
    ce_str = collection_end.strftime("%Y-%m-%dT%H:%M:%SZ")

    # --- Build dataset (run-based) ---
    quality = build_and_write_run(
        metrics_df, incidents, cfg,
        run_id=run_id,
        imputation_stats=imputation_stats,
        missing_features=missing,
        collection_start=cs_str,
        collection_end=ce_str,
        chaos_enabled=True,
        run_type=run_type,
    )

    print(f"\n[collect] Run written to: {cfg.output_dir}")
    print(f"[collect] Incidents: {len(successful)} successful, {len(failed)} failed")
    print(f"[collect] Anomaly points: {quality['anomaly_points']}")
    print(f"[collect] Quality report: passed={quality['passed']}")
    for reason in quality.get("fail_reasons", []):
        print(f"  FAIL: {reason}", file=sys.stderr)

    # --- injection_log.json (backward compat) ---
    log = []
    for r in injection_results:
        log.append({
            "incident_id":       r.incident_id,
            "fault_type":        r.fault_type,
            "target_service":    r.target_service,
            "injection_start":   r.injection_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "injection_end":     r.injection_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "effect_start":      r.effect_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "effect_end":        r.effect_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "success":           r.success,
            "error":             r.error,
            "experiment_name":   r.experiment_name,
        })
    log_path = cfg.output_dir / "injection_log.json"
    log_path.write_text(json.dumps(log, indent=2))
    print(f"[collect] Injection log: {log_path}")

    # --- Update manifest ---
    run_meta_path = cfg.output_dir / "run_meta.json"
    if run_meta_path.exists():
        run_meta = json.loads(run_meta_path.read_text())
        _update_manifest(cfg.output_dir, run_meta, quality)

    if not quality["passed"]:
        print("ERROR: Quality checks failed. See processed/quality_report.json.", file=sys.stderr)
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# assemble  (combine multiple runs into train/valid/test dataset)
# ─────────────────────────────────────────────────────────────────────────────

def cmd_assemble(args: argparse.Namespace) -> None:
    """
    Combine quality-passed runs into a train/valid/test dataset.

    Split policy (last3_valid_last2_test):
      - Sort runs by collection_start (ascending)
      - last 2 runs → test
      - 3rd-to-last run → valid
      - all earlier runs → train
      - Minimum 4 runs required
    """
    import pandas as pd
    from .schema import build_feature_schema
    from .config import FEATURE_NAMES, SERVICES

    runs_root = Path(args.runs_root)
    output = Path(args.output)

    if not runs_root.exists():
        print(f"ERROR: runs_root does not exist: {runs_root}", file=sys.stderr)
        sys.exit(1)

    # Discover quality-passed runs
    runs: list[dict] = []
    for meta_path in sorted(runs_root.glob("*/run_meta.json")):
        meta = json.loads(meta_path.read_text())
        run_dir = meta_path.parent
        qr_path = run_dir / "processed" / "quality_report.json"
        if not qr_path.exists():
            print(f"  [skip] {run_dir.name}: no quality_report.json")
            continue
        qr = json.loads(qr_path.read_text())
        if not qr.get("passed", False):
            reasons = qr.get("fail_reasons", ["unknown"])[:2]
            print(f"  [skip] {run_dir.name}: quality_passed=False ({reasons})")
            continue
        run_x_path  = run_dir / "processed" / "run_x.csv"
        run_y_path  = run_dir / "processed" / "run_y.csv"
        if not (run_x_path.exists() and run_y_path.exists()):
            print(f"  [skip] {run_dir.name}: missing run_x.csv or run_y.csv")
            continue
        runs.append({
            "run_id":           meta.get("run_id", run_dir.name),
            "collection_start": meta.get("collection_start", ""),
            "run_dir":          run_dir,
            "run_x_path":       run_x_path,
            "run_y_path":       run_y_path,
            "incidents_path":   run_dir / "processed" / "incidents.csv",
        })

    runs.sort(key=lambda x: x["collection_start"])
    n = len(runs)
    print(f"[assemble] Found {n} quality-passed runs under {runs_root}")

    if n < 4:
        print(f"ERROR: Need at least 4 quality-passed runs, found {n}. "
              "Collect more runs before assembling.", file=sys.stderr)
        sys.exit(1)

    train_runs = runs[:-3]
    valid_runs = runs[-3:-2]
    test_runs  = runs[-2:]

    print(f"  train: {[r['run_id'] for r in train_runs]}")
    print(f"  valid: {[r['run_id'] for r in valid_runs]}")
    print(f"  test:  {[r['run_id'] for r in test_runs]}")

    def load_run(r: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        x = pd.read_csv(r["run_x_path"])
        y = pd.read_csv(r["run_y_path"])
        inc = pd.read_csv(r["incidents_path"]) if r["incidents_path"].exists() else pd.DataFrame()
        # Ensure correct column order
        ts_col = ["timestamp"]
        feat_cols = [c for c in FEATURE_NAMES if c in x.columns]
        x = x[ts_col + feat_cols]
        # Namespace incident_id by run so IDs stay unique after cross-run concat.
        # Each run numbers incidents from INC-001, so two runs would otherwise collide.
        rid = r["run_id"]
        if "incident_id" in y.columns:
            mask = y["incident_id"].notna()
            y.loc[mask, "incident_id"] = rid + "/" + y.loc[mask, "incident_id"].astype(str)
        if not inc.empty and "incident_id" in inc.columns:
            inc = inc.copy()
            inc["run_id"] = rid
            inc["incident_id"] = rid + "/" + inc["incident_id"].astype(str)
        return x, y, inc

    def concat_runs(run_list: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        xs, ys, incs = [], [], []
        for r in run_list:
            x, y, inc = load_run(r)
            xs.append(x)
            ys.append(y)
            if not inc.empty:
                incs.append(inc)
        x_all   = pd.concat(xs, ignore_index=True)
        y_all   = pd.concat(ys, ignore_index=True)
        inc_all = pd.concat(incs, ignore_index=True) if incs else pd.DataFrame()
        return x_all, y_all, inc_all

    train_x, train_y, _        = concat_runs(train_runs)
    valid_x, valid_y, _        = concat_runs(valid_runs)
    test_x,  test_y,  test_inc = concat_runs(test_runs)

    proc_dir = output / "processed"
    ans_dir  = output / "answers"
    ex_dir   = output / "examples"
    for d in (proc_dir, ans_dir, ex_dir):
        d.mkdir(parents=True, exist_ok=True)

    # train/valid: features + labels both provided (user trains on these).
    # test: features only in processed/; labels held in answers/ (blind eval).
    train_x.to_csv(proc_dir / "train_x.csv", index=False)
    train_y.to_csv(proc_dir / "train_y.csv", index=False)
    valid_x.to_csv(proc_dir / "valid_x.csv", index=False)
    valid_y.to_csv(proc_dir / "valid_y.csv", index=False)
    test_x.to_csv(proc_dir / "test_x.csv",   index=False)

    if not test_inc.empty:
        test_inc.to_csv(proc_dir / "incidents.csv", index=False)

    # Feature schema
    schema_df = build_feature_schema()
    schema_df.to_csv(proc_dir / "feature_schema.csv", index=False)

    # Normalization stats — fit on TRAIN ONLY to prevent leakage.
    # valid/test must be transformed with these same stats by the consumer.
    feat_cols = [c for c in FEATURE_NAMES if c in train_x.columns]
    norm_features: dict[str, dict] = {}
    for col in feat_cols:
        s = train_x[col]
        norm_features[col] = {
            "mean": float(s.mean()),
            "std":  float(s.std(ddof=1)) if len(s) > 1 else 0.0,
            "min":  float(s.min()),
            "max":  float(s.max()),
        }
    norm_stats = {
        "fit_on": "train_only",
        "note": "Apply these train-derived stats to valid/test; do NOT refit on valid/test.",
        "features": norm_features,
    }
    (proc_dir / "norm_stats.json").write_text(json.dumps(norm_stats, indent=2))

    # Ground truth files (test split)
    gt = test_y[["timestamp", "is_anomaly"]].rename(columns={"is_anomaly": "y_true"})
    gt.to_csv(ans_dir / "test_ground_truth.csv", index=False)
    test_y[["timestamp", "incident_id", "phase"]].to_csv(
        ans_dir / "test_incident_ground_truth.csv", index=False
    )
    if not test_inc.empty and "root_cause_dims" in test_inc.columns:
        rc_rows = [
            {
                "incident_id":        row.get("incident_id", ""),
                "run_id":             row.get("run_id", ""),
                "root_cause_service": row.get("root_cause_service", ""),
                "root_cause_dims":    row.get("root_cause_dims", ""),
                "fault_type":         row.get("fault_type", ""),
            }
            for _, row in test_inc.iterrows()
        ]
        pd.DataFrame(rc_rows).to_csv(ans_dir / "test_root_cause_ground_truth.csv", index=False)

    # Sample submission template (anomaly score per test timestamp, all zeros).
    sample = pd.DataFrame({"timestamp": test_x["timestamp"], "anomaly_score": 0.0})
    sample.to_csv(ex_dir / "sample_submission.csv", index=False)

    # dataset_meta.json
    now_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    meta_out = {
        "dataset_name":        output.name,
        "assembled_from":      [r["run_id"] for r in runs],
        "train_runs":          [r["run_id"] for r in train_runs],
        "valid_runs":          [r["run_id"] for r in valid_runs],
        "test_runs":           [r["run_id"] for r in test_runs],
        "run_windows":         {r["run_id"]: r["collection_start"] for r in runs},
        "split_policy":        "last3_valid_last2_test",
        "temporal_order":      "runs sorted by collection_start; train precedes valid precedes test (no future leakage)",
        "created_at":          now_str,
        "feature_count":       len(FEATURE_NAMES),
        "services":            SERVICES,
        "train_rows":          len(train_x),
        "valid_rows":          len(valid_x),
        "test_rows":           len(test_x),
        "train_anomaly_points": int(train_y["is_anomaly"].sum()),
        "valid_anomaly_points": int(valid_y["is_anomaly"].sum()),
        "test_anomaly_points":  int(test_y["is_anomaly"].sum()),
        "norm_stats_fit_on":   "train_only",
        "test_labels_location": "answers/ (test_y not in processed/ to keep eval blind)",
    }
    (output / "dataset_meta.json").write_text(json.dumps(meta_out, indent=2))

    print(f"[assemble] Dataset written to: {output}")
    print(f"  train: {len(train_x)} rows")
    print(f"  valid: {len(valid_x)} rows")
    print(f"  test:  {len(test_x)} rows, {int(test_y['is_anomaly'].sum())} anomaly points")


# ─────────────────────────────────────────────────────────────────────────────
# main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Online Boutique AIOps dataset exporter")
    sub = parser.add_subparsers(dest="command", required=True)

    # --- smoke ---
    p_smoke = sub.add_parser("smoke", help="Generate mock dataset (no cluster needed)")
    p_smoke.add_argument("--output", required=True)
    p_smoke.add_argument("--duration-minutes", type=int, default=10)
    p_smoke.add_argument("--step-seconds", type=int, default=5)

    # --- live ---
    p_live = sub.add_parser("live", help="Export a run from Prometheus (no fault injection)")
    p_live.add_argument("--output", required=True,
                        help="Run output directory (e.g. data/runs/run_20260529_1)")
    p_live.add_argument("--run-id", default=None,
                        help="Run ID string; defaults to the output directory name")
    p_live.add_argument("--prometheus-url", default="http://localhost:9090")
    p_live.add_argument("--lookback-minutes", type=int, default=10)
    p_live.add_argument("--step-seconds", type=int, default=5)
    p_live.add_argument("--queries-config", default="configs/prometheus_queries.yaml")
    p_live.add_argument("--start-time", default=None,
                        help="Explicit start time (ISO 8601 UTC, e.g. 2026-05-29T18:00:00Z)")
    p_live.add_argument("--end-time", default=None,
                        help="Explicit end time (ISO 8601 UTC); defaults to now")

    # --- collect ---
    p_collect = sub.add_parser(
        "collect",
        help="ChaosMesh fault injection + data collection (full RCA pipeline)"
    )
    p_collect.add_argument("--output", required=True,
                           help="Run output directory (e.g. data/runs/run_20260529_1)")
    p_collect.add_argument("--run-id", default=None,
                           help="Run ID string; defaults to the output directory name")
    p_collect.add_argument("--prometheus-url", default="http://localhost:9090")
    p_collect.add_argument("--step-seconds", type=int, default=5)
    p_collect.add_argument("--queries-config", default="configs/prometheus_queries.yaml")
    p_collect.add_argument(
        "--fault-types", nargs="+",
        default=["cpu_stress", "pod_kill"],
        choices=["cpu_stress", "pod_kill", "network_delay"],
        help="Fault types to inject (in order)",
    )
    p_collect.add_argument("--warmup-minutes",      type=int, default=5,
                           help="Normal traffic warmup before first fault")
    p_collect.add_argument("--gap-minutes",          type=int, default=3,
                           help="Gap between faults within a round")
    p_collect.add_argument("--rounds",               type=int, default=1,
                           help="Number of injection rounds")
    p_collect.add_argument("--round-gap-minutes",    type=int, default=5,
                           help="Gap between rounds (only used when --rounds > 1)")
    p_collect.add_argument("--gap-jitter",           type=int, default=0,
                           help="Max random seconds added to each gap (uniform 0..N)")
    p_collect.add_argument("--dry-run", action="store_true",
                           help="Print plan without actually injecting faults")

    # --- assemble ---
    p_assemble = sub.add_parser(
        "assemble",
        help="Combine multiple quality-passed runs into train/valid/test dataset"
    )
    p_assemble.add_argument("--runs-root", default="data/runs",
                            help="Directory containing run subdirectories")
    p_assemble.add_argument("--output", required=True,
                            help="Output directory for the assembled dataset")
    p_assemble.add_argument("--split-policy", default="last3_valid_last2_test",
                            choices=["last3_valid_last2_test"],
                            help="How to assign runs to splits")

    args = parser.parse_args()
    if args.command == "smoke":
        cmd_smoke(args)
    elif args.command == "live":
        cmd_live(args)
    elif args.command == "collect":
        cmd_collect(args)
    elif args.command == "assemble":
        cmd_assemble(args)


if __name__ == "__main__":
    main()
