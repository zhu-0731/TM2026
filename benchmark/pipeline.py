"""
Automated train/validate/test + evaluation pipeline for the
Online Boutique AIOps RCA dataset.

The user supplies a detector implementing the `AnomalyDetector` protocol
(fit + predict). The pipeline handles everything else:

  - loading train/valid/test splits and the held-out answer files
  - standardizing features with TRAIN-ONLY statistics (no leakage)
  - running the user's fit / predict
  - the full anomaly-detection metric suite (see benchmark.metrics):
    point-level, ranking (AUPRC/AUROC), event-level, detection delay,
    false-alarm, point-adjust, grouped-by-fault/service, threshold provenance
  - plotting score timelines and PR/ROC curves
  - writing every artifact into output/<timestamp>_<run_name>/ so repeated
    runs never overwrite each other

Typical usage (see notebooks/demo_pipeline.ipynb):

    from benchmark.pipeline import Pipeline, DatasetBundle

    bundle = DatasetBundle.load("data/datasets/online_boutique_rca_full_v1")

    class MyDetector:
        def fit(self, train_x, train_y, valid_x, valid_y, ctx): ...
        def predict(self, test_x, ctx): return scores  # 1D, len == len(test_x)

    pipe = Pipeline(bundle, run_name="my_detector", threshold_mode="best_f1")
    result = pipe.run(MyDetector())
    print(result.metrics)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Protocol, runtime_checkable

import numpy as np
import pandas as pd

from . import metrics as M


# ─────────────────────────────────────────────────────────────────────────────
# Detector contract
# ─────────────────────────────────────────────────────────────────────────────

@runtime_checkable
class AnomalyDetector(Protocol):
    """User-implemented detector.

    fit():     train on the (labeled) train + valid splits. May ignore labels
               for an unsupervised method.
    predict(): return a 1D anomaly score per row of test_x (higher = more
               anomalous). Length must equal len(test_x).
    """

    def fit(
        self,
        train_x: pd.DataFrame,
        train_y: pd.DataFrame,
        valid_x: pd.DataFrame,
        valid_y: pd.DataFrame,
        ctx: "PipelineContext",
    ) -> None: ...

    def predict(self, test_x: pd.DataFrame, ctx: "PipelineContext") -> np.ndarray: ...


# ─────────────────────────────────────────────────────────────────────────────
# Dataset loading
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DatasetBundle:
    """All splits + answers + metadata for one assembled dataset."""

    root: Path
    feature_cols: list[str]
    norm_stats: dict
    meta: dict

    train_x: pd.DataFrame
    train_y: pd.DataFrame
    valid_x: pd.DataFrame
    valid_y: pd.DataFrame
    test_x: pd.DataFrame

    # held-out answers (never fed to the detector)
    test_truth: pd.DataFrame           # timestamp, y_true
    test_incident_truth: pd.DataFrame  # timestamp, incident_id, phase
    test_rca_truth: pd.DataFrame       # incident_id, run_id, root_cause_*
    test_incidents: pd.DataFrame       # incident_id, fault_type, target_service, effect_start/end
    sampling_interval_seconds: float = 5.0

    @classmethod
    def load(cls, root: str | Path) -> "DatasetBundle":
        root = Path(root)
        proc = root / "processed"
        ans = root / "answers"

        meta = json.loads((root / "dataset_meta.json").read_text(encoding="utf-8"))
        norm_stats = json.loads((proc / "norm_stats.json").read_text(encoding="utf-8"))
        feature_cols = list(norm_stats["features"].keys())

        def rd(p: Path) -> pd.DataFrame:
            return pd.read_csv(p)

        # incident windows live in answers/ (effect timing is eval ground truth);
        # fall back to processed/incidents.csv for older datasets.
        inc_path = ans / "test_incidents.csv"
        if not inc_path.exists():
            inc_path = proc / "incidents.csv"
        test_incidents = rd(inc_path) if inc_path.exists() else pd.DataFrame()

        return cls(
            root=root,
            feature_cols=feature_cols,
            norm_stats=norm_stats,
            meta=meta,
            train_x=rd(proc / "train_x.csv"),
            train_y=rd(proc / "train_y.csv"),
            valid_x=rd(proc / "valid_x.csv"),
            valid_y=rd(proc / "valid_y.csv"),
            test_x=rd(proc / "test_x.csv"),
            test_truth=rd(ans / "test_ground_truth.csv"),
            test_incident_truth=rd(ans / "test_incident_ground_truth.csv"),
            test_rca_truth=rd(ans / "test_root_cause_ground_truth.csv"),
            test_incidents=test_incidents,
            sampling_interval_seconds=float(meta.get("sampling_interval_seconds", 5)),
        )

    # -- scaling helpers (train-only stats) --

    def scale(self, df: pd.DataFrame) -> pd.DataFrame:
        """Z-score features using train-derived mean/std. timestamp preserved."""
        out = df.copy()
        feats = self.norm_stats["features"]
        for col in self.feature_cols:
            if col not in out.columns:
                continue
            mean = feats[col]["mean"]
            std = feats[col]["std"] or 1.0
            out[col] = (out[col] - mean) / std
        return out


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline context (passed to the detector)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PipelineContext:
    feature_cols: list[str]
    norm_stats: dict
    meta: dict
    output_dir: Path
    scale: Any  # callable(df) -> df, train-only z-score
    extras: dict = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# Result
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PipelineResult:
    run_name: str
    output_dir: Path
    metrics: dict
    scores: np.ndarray
    threshold: float


# ─────────────────────────────────────────────────────────────────────────────
# Plotting
# ─────────────────────────────────────────────────────────────────────────────

_FAULT_COLORS = {"cpu_stress": "#1f77b4", "pod_kill": "#2ca02c",
                 "network_delay": "#9467bd"}


def _plot_all(
    out_dir: Path,
    timestamps: pd.Series,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    scores: np.ndarray,
    threshold: float,
    curves: Optional[dict],
    ranking: dict,
    per_incident: list[dict],
    grouped: dict,
) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    ts = pd.to_datetime(timestamps)

    # 1. Score timeline with anomaly bands + threshold
    fig, ax = plt.subplots(figsize=(14, 4))
    ax.plot(ts, scores, lw=0.8, color="#1f77b4", label="anomaly score")
    ax.axhline(threshold, color="red", ls="--", lw=1, label=f"threshold={threshold:.3g}")
    in_anom, start = False, None
    for i, v in enumerate(y_true):
        if v and not in_anom:
            in_anom = True; start = ts.iloc[i]
        elif not v and in_anom:
            in_anom = False
            ax.axvspan(start, ts.iloc[i], color="orange", alpha=0.25)
    if in_anom:
        ax.axvspan(start, ts.iloc[-1], color="orange", alpha=0.25)
    ax.set_title("Anomaly score timeline (orange = ground-truth anomaly)")
    ax.set_xlabel("time"); ax.set_ylabel("score")
    ax.legend(loc="upper right", fontsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    fig.tight_layout()
    fig.savefig(out_dir / "score_timeline.png", dpi=120)
    plt.close(fig)

    # 2. ROC + PR curves (skip gracefully if undefined / single-class)
    if curves is not None:
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
        roc, pr = curves["roc"], curves["pr"]
        roc_auc = ranking.get("roc_auc")
        pr_auc = ranking.get("pr_auc")
        axes[0].plot(roc["fpr"], roc["tpr"], color="#d62728")
        axes[0].plot([0, 1], [0, 1], ls="--", color="gray", lw=0.8)
        axes[0].set_title(f"ROC (AUC={roc_auc:.3f})" if roc_auc is not None else "ROC (undefined)")
        axes[0].set_xlabel("FPR"); axes[0].set_ylabel("TPR")
        axes[1].plot(pr["recall"], pr["precision"], color="#2ca02c")
        axes[1].set_title(f"Precision-Recall (AUC={pr_auc:.3f})" if pr_auc is not None else "PR (undefined)")
        axes[1].set_xlabel("Recall"); axes[1].set_ylabel("Precision")
        for a in axes:
            a.set_xlim(0, 1); a.set_ylim(0, 1.02); a.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(out_dir / "roc_pr_curves.png", dpi=120)
        plt.close(fig)

    # 3. Score distribution by class
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(scores[y_true == 0], bins=50, alpha=0.6, label="normal", color="#1f77b4", density=True)
    if (y_true == 1).any():
        ax.hist(scores[y_true == 1], bins=50, alpha=0.6, label="anomaly", color="orange", density=True)
    ax.axvline(threshold, color="red", ls="--", lw=1, label="threshold")
    ax.set_title("Score distribution by class")
    ax.set_xlabel("score"); ax.set_ylabel("density"); ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "score_distribution.png", dpi=120)
    plt.close(fig)

    # 4. Per-incident detection delay bar chart (missed incidents marked red)
    if per_incident:
        labels = [p["incident_id"].split("/")[-1] + "\n" + p["incident_id"].split("/")[0].replace("online_boutique_", "")
                  for p in per_incident]
        # short labels: INC-xxx only, color by run via fault_type
        labels = [p["incident_id"].split("/")[-1] for p in per_incident]
        fig, ax = plt.subplots(figsize=(max(12, len(per_incident) * 0.32), 4.5))
        for i, p in enumerate(per_incident):
            if p["detected"] and p["delay_seconds"] is not None:
                ax.bar(i, p["delay_seconds"],
                       color=_FAULT_COLORS.get(p["fault_type"], "#7f7f7f"))
            else:
                # missed: red marker at top of axis
                ax.bar(i, 0.0, color="red")
                ax.scatter(i, 0, marker="x", color="red", s=40, zorder=5)
        ax.set_xticks(range(len(per_incident)))
        ax.set_xticklabels(labels, rotation=90, fontsize=6)
        ax.set_ylabel("detection delay (s)")
        ax.set_title("Per-incident detection delay (red x = missed)")
        # legend
        from matplotlib.patches import Patch
        handles = [Patch(color=_FAULT_COLORS.get(ft, "#7f7f7f"), label=ft)
                   for ft in sorted({p["fault_type"] for p in per_incident})]
        handles.append(Patch(color="red", label="missed"))
        ax.legend(handles=handles, fontsize=8)
        fig.tight_layout()
        fig.savefig(out_dir / "incident_delay_bar.png", dpi=120)
        plt.close(fig)

    # 5. Event recall by fault type (grouped bars: event_recall vs recall@30s)
    er = grouped.get("event_recall_by_fault_type", {})
    r30 = grouped.get("recall_at_30s_by_fault_type", {})
    if er:
        fts = list(er.keys())
        x = np.arange(len(fts)); w = 0.38
        fig, ax = plt.subplots(figsize=(max(5, len(fts) * 1.6), 4.5))
        ax.bar(x - w/2, [er[f] for f in fts], w, label="Event Recall", color="#1f77b4")
        ax.bar(x + w/2, [r30.get(f, 0) for f in fts], w, label="Recall@30s", color="#ff7f0e")
        ax.set_xticks(x); ax.set_xticklabels(fts)
        ax.set_ylim(0, 1.05); ax.set_ylabel("recall")
        ax.set_title("Event Recall vs Recall@30s by fault type")
        for i, f in enumerate(fts):
            ax.text(i - w/2, er[f] + 0.02, f"{er[f]:.2f}", ha="center", fontsize=8)
            ax.text(i + w/2, r30.get(f, 0) + 0.02, f"{r30.get(f, 0):.2f}", ha="center", fontsize=8)
        ax.legend(fontsize=9)
        fig.tight_layout()
        fig.savefig(out_dir / "event_recall_by_fault_type.png", dpi=120)
        plt.close(fig)

    # 6. False-positive timeline (score + FP markers)
    fp_mask = (y_pred == 1) & (y_true == 0)
    fig, ax = plt.subplots(figsize=(14, 4))
    ax.plot(ts, scores, lw=0.7, color="#1f77b4", alpha=0.7, label="anomaly score")
    ax.axhline(threshold, color="red", ls="--", lw=1, label="threshold")
    # shade true anomaly regions lightly for reference
    in_anom, start = False, None
    for i, v in enumerate(y_true):
        if v and not in_anom:
            in_anom = True; start = ts.iloc[i]
        elif not v and in_anom:
            in_anom = False; ax.axvspan(start, ts.iloc[i], color="orange", alpha=0.15)
    if in_anom:
        ax.axvspan(start, ts.iloc[-1], color="orange", alpha=0.15)
    if fp_mask.any():
        ax.scatter(ts[fp_mask], scores[fp_mask], color="red", s=14, zorder=5,
                   label=f"false positive (n={int(fp_mask.sum())})")
    ax.set_title("False-positive timeline (red = FP; orange band = true anomaly)")
    ax.set_xlabel("time"); ax.set_ylabel("score")
    ax.legend(loc="upper right", fontsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    fig.tight_layout()
    fig.savefig(out_dir / "false_positive_timeline.png", dpi=120)
    plt.close(fig)


def _plot_threshold_comparison(out_dir: Path, rows: list[dict]) -> None:
    """5.4 — compare best_f1 vs validation_f1 (and others) side by side."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if len(rows) < 2:
        return
    df = pd.DataFrame(rows)
    df.to_csv(out_dir / "threshold_comparison.csv", index=False)

    # bar groups for the key normalized metrics
    metrics_keys = ["point_f1", "pr_auc", "event_recall", "recall_at_30s"]
    modes = df["threshold_mode"].tolist()
    x = np.arange(len(metrics_keys)); w = 0.8 / max(len(modes), 1)
    fig, ax = plt.subplots(figsize=(10, 4.8))
    for j, (_, row) in enumerate(df.iterrows()):
        vals = [row.get(k) if row.get(k) is not None else 0 for k in metrics_keys]
        ax.bar(x + j * w - 0.4 + w/2, vals, w,
               label=f"{row['threshold_mode']} (deploy={row['threshold_deployable']})")
    ax.set_xticks(x); ax.set_xticklabels(["Point F1", "AUPRC", "Event Recall", "Recall@30s"])
    ax.set_ylim(0, 1.05); ax.set_ylabel("score")
    ax.set_title("Threshold mode comparison")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "threshold_comparison.png", dpi=120)
    plt.close(fig)


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline
# ─────────────────────────────────────────────────────────────────────────────

class Pipeline:
    """Drives fit -> predict -> evaluate -> plot, writing to a timestamped folder.

    threshold_mode:
      "best_f1"       : max F1 on test (upper bound, NOT deployable).
      "validation_f1" : max F1 on validation (deployable).
      "fixed_fpr"     : target FPR on validation normals (deployable; needs fixed_fpr).
    """

    def __init__(
        self,
        bundle: DatasetBundle,
        run_name: str = "run",
        output_root: str | Path = "output",
        scale_features: bool = True,
        threshold_mode: str = "best_f1",
        fixed_fpr: Optional[float] = None,
    ):
        self.bundle = bundle
        self.run_name = run_name
        self.output_root = Path(output_root)
        self.scale_features = scale_features
        self.threshold_mode = threshold_mode
        self.fixed_fpr = fixed_fpr

    def _make_output_dir(self) -> Path:
        stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in self.run_name)
        out = self.output_root / f"{stamp}_{safe}"
        out.mkdir(parents=True, exist_ok=True)
        return out

    def run(
        self,
        detector: Optional[AnomalyDetector] = None,
        submission: pd.DataFrame | None = None,
    ) -> PipelineResult:
        """Run the full pipeline.

        If `submission` is given (timestamp, anomaly_score), it is used directly
        instead of calling detector.predict -- useful for offline submissions.
        """
        b = self.bundle
        out_dir = self._make_output_dir()

        ctx = PipelineContext(
            feature_cols=b.feature_cols,
            norm_stats=b.norm_stats,
            meta=b.meta,
            output_dir=out_dir,
            scale=(b.scale if self.scale_features else (lambda df: df)),
        )

        # Prepare inputs (optionally scaled with train-only stats)
        if self.scale_features:
            train_x = b.scale(b.train_x)
            valid_x = b.scale(b.valid_x)
            test_x = b.scale(b.test_x)
        else:
            train_x, valid_x, test_x = b.train_x, b.valid_x, b.test_x

        # --- fit / predict (test + validation scores) ---
        # Always grab validation scores when a detector is available: needed for
        # deployable thresholds AND for the best_f1-vs-validation_f1 comparison.
        valid_scores = None
        if submission is None:
            if detector is None:
                raise ValueError("provide either a detector or a submission DataFrame")
            detector.fit(train_x, b.train_y, valid_x, b.valid_y, ctx)
            scores = np.asarray(detector.predict(test_x, ctx), dtype=float)
            try:
                valid_scores = np.asarray(detector.predict(valid_x, ctx), dtype=float)
                valid_scores = np.nan_to_num(valid_scores, nan=0.0, posinf=0.0, neginf=0.0)
            except Exception:
                valid_scores = None
        else:
            merged = b.test_x[["timestamp"]].merge(submission, on="timestamp", how="left")
            scores = merged["anomaly_score"].to_numpy(dtype=float)

        if scores.shape[0] != len(b.test_x):
            raise ValueError(
                f"predict returned {scores.shape[0]} scores but test has {len(b.test_x)} rows"
            )
        scores = np.nan_to_num(scores, nan=0.0, posinf=0.0, neginf=0.0)

        # --- threshold selection ---
        y_true = b.test_truth["y_true"].to_numpy().astype(int)
        valid_y = b.valid_y["is_anomaly"].to_numpy().astype(int) if valid_scores is not None else None
        thr_info = M.select_threshold(
            scores, y_true,
            mode=self.threshold_mode,
            valid_scores=valid_scores,
            valid_y=valid_y,
            fixed_fpr=self.fixed_fpr,
        )
        threshold = thr_info["threshold_value"]

        # --- full metric suite ---
        metrics, per_incident = M.compute_all(
            timestamps=b.test_x["timestamp"],
            y_true=y_true,
            scores=scores,
            incidents=b.test_incidents,
            sampling_interval_seconds=b.sampling_interval_seconds,
            threshold_info=thr_info,
        )
        curves = metrics.pop("_curves", None)

        # --- threshold comparison (best_f1 vs validation_f1) ---
        cmp_rows = self._threshold_comparison_rows(
            b, scores, y_true, valid_scores, valid_y
        )

        # --- plots ---
        y_pred = (scores >= threshold).astype(int)
        _plot_all(out_dir, b.test_x["timestamp"], y_true, y_pred, scores,
                  threshold, curves, metrics["ranking"], per_incident, metrics["grouped"])
        if len(cmp_rows) >= 2:
            _plot_threshold_comparison(out_dir, cmp_rows)

        # --- persist artifacts ---
        metrics_out = {
            "run_name": self.run_name,
            "dataset": b.meta.get("dataset_name", ""),
            "scaled_features": self.scale_features,
            "sampling_interval_seconds": b.sampling_interval_seconds,
            **metrics,
        }
        (out_dir / "metrics.json").write_text(
            json.dumps(metrics_out, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # predictions
        pd.DataFrame({
            "timestamp": b.test_x["timestamp"],
            "anomaly_score": scores,
            "y_pred": (scores >= threshold).astype(int),
            "y_true": y_true,
        }).to_csv(out_dir / "predictions.csv", index=False)

        # per-incident breakdown (full schema)
        if per_incident:
            cols = ["incident_id", "fault_type", "target_service",
                    "effect_start", "effect_end", "detected",
                    "first_alarm_time", "delay_seconds",
                    "detected_within_15s", "detected_within_30s", "detected_within_60s"]
            pd.DataFrame(per_incident)[cols].to_csv(out_dir / "per_incident.csv", index=False)

        self._print_summary(out_dir, metrics_out)
        return PipelineResult(self.run_name, out_dir, metrics_out, scores, threshold)

    def _threshold_comparison_rows(
        self,
        b: DatasetBundle,
        scores: np.ndarray,
        y_true: np.ndarray,
        valid_scores: Optional[np.ndarray],
        valid_y: Optional[np.ndarray],
    ) -> list[dict]:
        """Evaluate the same scores under multiple threshold modes for comparison.

        Always includes best_f1 (upper bound); adds validation_f1 when validation
        scores are available. Each row carries the headline metrics.
        """
        modes = [("best_f1", {})]
        if valid_scores is not None and valid_y is not None:
            modes.append(("validation_f1", {}))

        rows = []
        for mode, _ in modes:
            try:
                ti = M.select_threshold(
                    scores, y_true, mode=mode,
                    valid_scores=valid_scores, valid_y=valid_y,
                    fixed_fpr=self.fixed_fpr,
                )
                mm, _ = M.compute_all(
                    timestamps=b.test_x["timestamp"], y_true=y_true, scores=scores,
                    incidents=b.test_incidents,
                    sampling_interval_seconds=b.sampling_interval_seconds,
                    threshold_info=ti,
                )
                rows.append({
                    "threshold_mode":       ti["threshold_mode"],
                    "threshold":            ti["threshold_value"],
                    "threshold_deployable": ti["threshold_deployable"],
                    "point_f1":             mm["point_level"]["point_f1"],
                    "pr_auc":               mm["ranking"]["pr_auc"],
                    "event_recall":         mm["event_level"]["event_recall"],
                    "recall_at_30s":        mm["event_level"]["recall_at_30s"],
                    "false_alarms_per_hour": mm["false_alarm"]["false_alarms_per_hour"],
                    "median_delay_seconds": mm["event_level"]["median_detection_delay_seconds"],
                    "missed_incidents":     mm["event_level"]["missed_incidents"],
                })
            except Exception:
                continue
        return rows

    @staticmethod
    def _print_summary(out_dir: Path, m: dict) -> None:
        pt = m["point_level"]
        rk = m["ranking"]
        ev = m["event_level"]
        fa = m["false_alarm"]
        th = m["threshold"]

        def _fmt(v, nd=3):
            return "null" if v is None else f"{v:.{nd}f}"

        print(f"\n{'='*60}\n Pipeline result -> {out_dir}\n{'='*60}")
        print(f" Point-wise F1     : {_fmt(pt['point_f1'])}   "
              f"(P={_fmt(pt['point_precision'])} R={_fmt(pt['point_recall'])})")
        print(f" AUPRC             : {_fmt(rk['pr_auc'])}")
        print(f" AUROC             : {_fmt(rk['roc_auc'])}")
        print(f" Event Recall      : {_fmt(ev['event_recall'])}   "
              f"({ev['detected_incidents']}/{ev['detected_incidents']+ev['missed_incidents']} incidents)")
        print(f" Recall@30s        : {_fmt(ev['recall_at_30s'])}")
        print(f" False alarms/hour : {_fmt(fa['false_alarms_per_hour'])}")
        print(f" Median delay (s)  : {_fmt(ev['median_detection_delay_seconds'])}")
        miss = ev["missed_incident_ids"]
        print(f" Missed incidents  : {len(miss)}" + (f" -> {miss}" if miss else ""))
        print(f" Threshold         : {_fmt(th['threshold_value'], 4)} "
              f"[{th['threshold_mode']}, deployable={th['threshold_deployable']}]")
        if m.get("warnings"):
            for w in m["warnings"]:
                print(f" WARNING: {w}")
        print(f" Artifacts         : metrics.json, predictions.csv, per_incident.csv,")
        print(f"                     score_timeline.png, roc_pr_curves.png, score_distribution.png")
        print("="*60)
