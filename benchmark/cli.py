"""CLI entry point for the benchmark dataset exporter."""
from __future__ import annotations

import sys
import json
import time
import random
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

from .config import ExportConfig


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


def _parse_datetime(s: str) -> datetime:
    """Parse ISO 8601 UTC timestamp (e.g. 2026-05-29T12:00:00Z)."""
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def cmd_live(args: argparse.Namespace) -> None:
    from .exporter import fetch_live_data
    from .dataset_builder import build_and_write_dataset

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

    # Support explicit time window (overrides lookback_minutes)
    start_dt: datetime | None = _parse_datetime(args.start_time) if args.start_time else None
    end_dt:   datetime | None = _parse_datetime(args.end_time)   if args.end_time   else None

    if start_dt or end_dt:
        window_desc = f"{args.start_time} → {args.end_time or 'now'}"
        print(f"[live] Fetching explicit window: {window_desc} from {args.prometheus_url}...")
    else:
        print(f"[live] Fetching last {args.lookback_minutes}min from {args.prometheus_url}...")

    metrics_df, missing = fetch_live_data(cfg, queries_path, start=start_dt, end=end_dt)

    if missing:
        print(f"[live] WARNING: {len(missing)} features missing: {missing[:5]}...")

    cs_str = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ") if start_dt else None
    ce_str = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")   if end_dt   else None
    quality = build_and_write_dataset(
        metrics_df, [], cfg,
        missing_features=missing,
        collection_start=cs_str,
        collection_end=ce_str,
    )
    print(f"[live] Dataset written to: {cfg.output_dir}")
    print(f"[live] Quality report: passed={quality['passed']}")

    if not quality["passed"]:
        print("ERROR: Quality checks failed. See quality_report.json for details.", file=sys.stderr)
        sys.exit(1)


def cmd_collect(args: argparse.Namespace) -> None:
    """
    Fault injection + data collection pipeline:
      1. Warmup phase  (normal traffic, no faults)
      2. Inject fault  (ChaosMesh experiment, record exact timestamps)
      3. Wait for recovery
      4. Repeat for each fault type
      5. Fetch full window from Prometheus
      6. Build labeled dataset with real RCA ground truth
    """
    from .exporter import fetch_live_data
    from .dataset_builder import build_and_write_dataset
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
        train_ratio=args.train_ratio,
        valid_ratio=args.valid_ratio,
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
    print(f" Fault types:   {fault_types}")
    print(f" Rounds:        {rounds}")
    print(f" Warmup:        {args.warmup_minutes}min")
    print(f" Intra-round gap: {args.gap_minutes}min ±{gap_jitter_sec}s jitter")
    if rounds > 1:
        print(f" Inter-round gap: {args.round_gap_minutes}min ±{gap_jitter_sec}s jitter")
    print(f" Step:          {args.step_seconds}s")
    print(f" Output:        {cfg.output_dir}")
    print(f" Dry-run:       {dry_run}")
    print("=" * 60)

    def _jittered_sleep(base_minutes: float, label: str) -> None:
        """Sleep base_minutes with up to gap_jitter_sec of random extra time."""
        jitter = random.uniform(0, gap_jitter_sec) if gap_jitter_sec > 0 else 0
        total = base_minutes * 60 + jitter
        jitter_str = f" (+{jitter:.0f}s jitter)" if jitter > 0 else ""
        print(f"\n[collect] {label}: {base_minutes}min{jitter_str} ...")
        if not dry_run:
            time.sleep(total)

    collection_start = datetime.now(tz=timezone.utc)
    print(f"\n[collect] Collection start: {collection_start.strftime('%Y-%m-%dT%H:%M:%SZ')}")

    # --- Warmup phase ---
    print(f"\n[collect] Warmup phase: {args.warmup_minutes}min normal traffic ...")
    if not dry_run:
        time.sleep(args.warmup_minutes * 60)

    # --- Fault injection phases (multi-round) ---
    injection_results = []
    inc_counter = 1  # global incident counter across all rounds

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

            # Intra-round gap (skip after last fault in current round)
            is_last_in_round = idx == len(fault_types) - 1
            if not is_last_in_round:
                _jittered_sleep(args.gap_minutes, "Gap between faults")

        # Inter-round gap (skip after final round)
        is_last_round = round_idx == rounds - 1
        if not is_last_round:
            _jittered_sleep(args.round_gap_minutes, f"Gap between rounds ({round_idx+1}→{round_idx+2})")

    collection_end = datetime.now(tz=timezone.utc)
    print(f"\n[collect] All injections complete. "
          f"Collection end: {collection_end.strftime('%Y-%m-%dT%H:%M:%SZ')}")

    # --- Dry-run: print summary and exit ---
    if dry_run:
        total_sec = sum(
            60 + FAULT_DEFINITIONS[ft].get("recovery_buffer_sec", 30)
            for ft in fault_types
        ) + args.warmup_minutes * 60 + args.gap_minutes * 60 * (len(fault_types) - 1)
        print(f"\n[dry-run] Plan summary:")
        print(f"  Estimated total time: {total_sec // 60}min {total_sec % 60}s")
        print(f"  Faults: {fault_types}")
        for r in injection_results:
            print(f"  {r.incident_id} ({r.fault_type}): "
                  f"effect_start={r.effect_start.strftime('%H:%M:%SZ')}, "
                  f"effect_end={r.effect_end.strftime('%H:%M:%SZ')}")
        print("[dry-run] Done. Use without --dry-run to actually run.")
        return

    # --- Fetch data from Prometheus ---
    total_minutes = int((collection_end - collection_start).total_seconds() / 60) + 1
    print(f"\n[collect] Fetching {total_minutes}min of data from Prometheus ...")
    metrics_df, missing = fetch_live_data(
        cfg, queries_path,
        start=collection_start,
        end=collection_end,
    )
    print(f"[collect] Got {len(metrics_df)} time points, "
          f"{len(missing)} features missing")

    # --- Convert injection results to MockIncident format ---
    incidents = results_to_mock_incidents(injection_results)
    successful = [r for r in injection_results if r.success]
    failed = [r for r in injection_results if not r.success]

    if failed:
        print(f"\n[collect] WARNING: {len(failed)} injections failed: "
              f"{[r.incident_id for r in failed]}", file=sys.stderr)

    if not incidents:
        print("[collect] WARNING: No successful incidents — dataset will have no anomaly labels",
              file=sys.stderr)

    # --- Compute split ratios so faults always land in test ---
    # train: warmup period (before first fault) × 0.85
    # valid: warmup period × 0.15
    # test: everything from first fault onset onward
    if successful:
        first_effect = min(r.effect_start for r in successful)
        total_sec = (collection_end - collection_start).total_seconds()
        warmup_sec = (first_effect - collection_start).total_seconds()
        # train: first 80% of warmup; valid: next 10%; test: last 10% of warmup + all faults
        # Subtracting 30s buffer ensures first fault always lands inside test
        buffer_sec = 30
        cfg.train_ratio = round(min((warmup_sec * 0.80) / total_sec, 0.7), 3)
        cfg.valid_ratio = round(min(((warmup_sec - buffer_sec) * 0.10) / total_sec, 0.15), 3)
        print(f"[collect] Auto-computed splits: "
              f"train={cfg.train_ratio:.1%}  valid={cfg.valid_ratio:.1%}  "
              f"test={1-cfg.train_ratio-cfg.valid_ratio:.1%}")
        print(f"[collect] First fault at {first_effect.strftime('%H:%M:%SZ')} "
              f"({warmup_sec/60:.1f}min into collection)")

    cs_str = collection_start.strftime("%Y-%m-%dT%H:%M:%SZ")
    ce_str = collection_end.strftime("%Y-%m-%dT%H:%M:%SZ")

    # --- Build dataset ---
    quality = build_and_write_dataset(
        metrics_df, incidents, cfg,
        missing_features=missing,
        collection_start=cs_str,
        collection_end=ce_str,
    )
    print(f"\n[collect] Dataset written to: {cfg.output_dir}")
    print(f"[collect] Incidents: {len(successful)} successful, {len(failed)} failed")
    print(f"[collect] Test anomaly points: {quality['test_anomaly_points']}")
    print(f"[collect] Quality report: passed={quality['passed']}")

    # Save injection log
    log = []
    for r in injection_results:
        log.append({
            "incident_id": r.incident_id,
            "fault_type": r.fault_type,
            "target_service": r.target_service,
            "injection_start": r.injection_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "injection_end": r.injection_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "effect_start": r.effect_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "effect_end": r.effect_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "success": r.success,
            "error": r.error,
            "experiment_name": r.experiment_name,
        })
    log_path = cfg.output_dir / "injection_log.json"
    log_path.write_text(json.dumps(log, indent=2))
    print(f"[collect] Injection log: {log_path}")

    if not quality["passed"] and not dry_run:
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Online Boutique AIOps dataset exporter")
    sub = parser.add_subparsers(dest="command", required=True)

    # --- smoke ---
    p_smoke = sub.add_parser("smoke", help="Generate mock dataset (no cluster needed)")
    p_smoke.add_argument("--output", required=True)
    p_smoke.add_argument("--duration-minutes", type=int, default=10)
    p_smoke.add_argument("--step-seconds", type=int, default=5)

    # --- live ---
    p_live = sub.add_parser("live", help="Export from Prometheus (no fault injection)")
    p_live.add_argument("--output", required=True)
    p_live.add_argument("--prometheus-url", default="http://localhost:9090")
    p_live.add_argument("--lookback-minutes", type=int, default=10)
    p_live.add_argument("--step-seconds", type=int, default=5)
    p_live.add_argument("--queries-config", default="configs/prometheus_queries.yaml")
    p_live.add_argument("--start-time", default=None,
                        help="Explicit start time (ISO 8601 UTC, e.g. 2026-05-29T18:00:00Z); "
                             "overrides --lookback-minutes")
    p_live.add_argument("--end-time", default=None,
                        help="Explicit end time (ISO 8601 UTC); defaults to now")

    # --- collect ---
    p_collect = sub.add_parser(
        "collect",
        help="ChaosMesh fault injection + data collection (full RCA pipeline)"
    )
    p_collect.add_argument("--output", required=True)
    p_collect.add_argument("--prometheus-url", default="http://localhost:9090")
    p_collect.add_argument("--step-seconds", type=int, default=5)
    p_collect.add_argument("--queries-config", default="configs/prometheus_queries.yaml")
    p_collect.add_argument(
        "--fault-types", nargs="+",
        default=["cpu_stress", "pod_kill"],
        choices=["cpu_stress", "pod_kill", "network_delay"],
        help="Fault types to inject (in order)",
    )
    p_collect.add_argument("--warmup-minutes", type=int, default=5,
                           help="Normal traffic warmup before first fault")
    p_collect.add_argument("--gap-minutes", type=int, default=3,
                           help="Normal traffic gap between faults within a round")
    p_collect.add_argument("--rounds", type=int, default=1,
                           help="Number of injection rounds (fault sequence repeats N times)")
    p_collect.add_argument("--round-gap-minutes", type=int, default=5,
                           help="Normal traffic gap between rounds (only used when --rounds > 1)")
    p_collect.add_argument("--gap-jitter", type=int, default=0,
                           help="Max random seconds added to each gap interval (uniform 0..N)")
    p_collect.add_argument("--train-ratio", type=float, default=0.5)
    p_collect.add_argument("--valid-ratio", type=float, default=0.2)
    p_collect.add_argument("--dry-run", action="store_true",
                           help="Print plan without actually injecting faults")

    args = parser.parse_args()
    if args.command == "smoke":
        cmd_smoke(args)
    elif args.command == "live":
        cmd_live(args)
    elif args.command == "collect":
        cmd_collect(args)


if __name__ == "__main__":
    main()
