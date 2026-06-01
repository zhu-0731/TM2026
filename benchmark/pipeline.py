"""
Automated train/validate/test + evaluation pipeline for the
Online Boutique AIOps RCA dataset.

The user supplies a detector implementing the `AnomalyDetector` protocol
(fit + predict). The pipeline handles everything else:

  - loading train/valid/test splits and the held-out answer files
  - standardizing features with TRAIN-ONLY statistics (no leakage)
  - running the user's fit / predict
  - evaluating anomaly-detection metrics against answers/
  - plotting score timelines and a PR/ROC summary
  - writing every artifact into output/<timestamp>_<run_name>/ so repeated
    runs never overwrite each other

Typical usage (see notebooks/demo_pipeline.ipynb):

    from benchmark.pipeline import Pipeline, DatasetBundle

    bundle = DatasetBundle.load("data/datasets/online_boutique_rca_full_v1")

    class MyDetector:
        def fit(self, train_x, train_y, valid_x, valid_y, ctx): ...
        def predict(self, test_x, ctx): return scores  # 1D array, len == len(test_x)

    pipe = Pipeline(bundle, run_name="my_detector")
    result = pipe.run(MyDetector())
    print(result.metrics)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import numpy as np
import pandas as pd


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
    test_truth: pd.DataFrame          # timestamp, y_true
    test_incident_truth: pd.DataFrame  # timestamp, incident_id, phase
    test_rca_truth: pd.DataFrame       # incident_id, run_id, root_cause_*

    @classmethod
    def load(cls, root: str | Path) -> "DatasetBundle":
        root = Path(root)
        proc = root / "processed"
        ans = root / "answers"

        meta = json.loads((root / "dataset_meta.json").read_text())
        norm_stats = json.loads((proc / "norm_stats.json").read_text())
        feature_cols = list(norm_stats["features"].keys())

        def rd(p: Path) -> pd.DataFrame:
            return pd.read_csv(p)

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
# Evaluation
# ─────────────────────────────────────────────────────────────────────────────

def _best_f1_threshold(y_true: np.ndarray, scores: np.ndarray) -> tuple[float, float]:
    """Pick the score threshold that maximizes F1 on the test scores.

    Returns (threshold, best_f1). Threshold candidates are the unique scores.
    """
    order = np.argsort(-scores)
    s_sorted = scores[order]
    y_sorted = y_true[order]
    tp = np.cumsum(y_sorted)
    fp = np.cumsum(1 - y_sorted)
    total_pos = max(int(y_true.sum()), 1)
    precision = tp / np.maximum(tp + fp, 1)
    recall = tp / total_pos
    f1 = 2 * precision * recall / np.maximum(precision + recall, 1e-12)
    if len(f1) == 0:
        return 0.0, 0.0
    best = int(np.argmax(f1))
    return float(s_sorted[best]), float(f1[best])


def _auc(x: np.ndarray, y: np.ndarray) -> float:
    """Trapezoidal AUC for x sorted ascending."""
    order = np.argsort(x)
    return float(np.trapz(y[order], x[order]))


def evaluate_detection(y_true: np.ndarray, scores: np.ndarray) -> tuple[dict, float]:
    """Compute detection metrics. Returns (metrics_dict, chosen_threshold)."""
    y_true = np.asarray(y_true).astype(int)
    scores = np.asarray(scores, dtype=float)

    threshold, best_f1 = _best_f1_threshold(y_true, scores)
    y_pred = (scores >= threshold).astype(int)

    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    fp = int(((y_pred == 1) & (y_true == 0)).sum())
    fn = int(((y_pred == 0) & (y_true == 1)).sum())
    tn = int(((y_pred == 0) & (y_true == 0)).sum())

    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-12)

    # ROC / PR AUC via threshold sweep
    thresholds = np.unique(scores)
    if len(thresholds) > 500:
        thresholds = np.quantile(scores, np.linspace(0, 1, 500))
    tprs, fprs, precs, recs = [], [], [], []
    P = max(int(y_true.sum()), 1)
    N = max(int((1 - y_true).sum()), 1)
    for t in thresholds:
        yp = (scores >= t).astype(int)
        _tp = int(((yp == 1) & (y_true == 1)).sum())
        _fp = int(((yp == 1) & (y_true == 0)).sum())
        tprs.append(_tp / P)
        fprs.append(_fp / N)
        precs.append(_tp / max(_tp + _fp, 1))
        recs.append(_tp / P)
    roc_auc = _auc(np.array(fprs), np.array(tprs))
    pr_auc = _auc(np.array(recs), np.array(precs))

    metrics = {
        "threshold": threshold,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "best_f1_at_threshold": round(best_f1, 4),
        "roc_auc": round(roc_auc, 4),
        "pr_auc": round(pr_auc, 4),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "n_test": int(len(y_true)),
        "n_anomaly": int(y_true.sum()),
        "_roc": {"fpr": fprs, "tpr": tprs},
        "_pr": {"recall": recs, "precision": precs},
    }
    return metrics, threshold


def evaluate_rca(
    test_incident_truth: pd.DataFrame,
    scores: np.ndarray,
    threshold: float,
) -> dict:
    """Per-incident detection: was each labeled incident flagged at all?

    An incident counts as detected if any timestamp inside it has score >= threshold.
    """
    df = test_incident_truth.copy()
    df["score"] = scores
    df = df[df["incident_id"].notna()]
    if df.empty:
        return {"incidents_total": 0, "incidents_detected": 0, "incident_detection_rate": 0.0}

    detected = 0
    per_incident = []
    for inc_id, grp in df.groupby("incident_id"):
        hit = bool((grp["score"] >= threshold).any())
        detected += int(hit)
        per_incident.append({
            "incident_id": inc_id,
            "detected": hit,
            "max_score": float(grp["score"].max()),
            "n_points": int(len(grp)),
        })
    total = len(per_incident)
    return {
        "incidents_total": total,
        "incidents_detected": detected,
        "incident_detection_rate": round(detected / max(total, 1), 4),
        "per_incident": per_incident,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Plotting
# ─────────────────────────────────────────────────────────────────────────────

def _plot_all(
    out_dir: Path,
    timestamps: pd.Series,
    y_true: np.ndarray,
    scores: np.ndarray,
    threshold: float,
    metrics: dict,
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
    # shade true anomaly regions
    in_anom = False
    start = None
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

    # 2. ROC + PR curves
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    roc, pr = metrics["_roc"], metrics["_pr"]
    axes[0].plot(roc["fpr"], roc["tpr"], color="#d62728")
    axes[0].plot([0, 1], [0, 1], ls="--", color="gray", lw=0.8)
    axes[0].set_title(f"ROC (AUC={metrics['roc_auc']:.3f})")
    axes[0].set_xlabel("FPR"); axes[0].set_ylabel("TPR")
    axes[1].plot(pr["recall"], pr["precision"], color="#2ca02c")
    axes[1].set_title(f"Precision-Recall (AUC={metrics['pr_auc']:.3f})")
    axes[1].set_xlabel("Recall"); axes[1].set_ylabel("Precision")
    for a in axes:
        a.set_xlim(0, 1); a.set_ylim(0, 1.02); a.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_dir / "roc_pr_curves.png", dpi=120)
    plt.close(fig)

    # 3. Score distribution by class
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(scores[y_true == 0], bins=50, alpha=0.6, label="normal", color="#1f77b4", density=True)
    ax.hist(scores[y_true == 1], bins=50, alpha=0.6, label="anomaly", color="orange", density=True)
    ax.axvline(threshold, color="red", ls="--", lw=1, label="threshold")
    ax.set_title("Score distribution by class")
    ax.set_xlabel("score"); ax.set_ylabel("density"); ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "score_distribution.png", dpi=120)
    plt.close(fig)


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline
# ─────────────────────────────────────────────────────────────────────────────

class Pipeline:
    """Drives fit → predict → evaluate → plot, writing to a timestamped folder."""

    def __init__(
        self,
        bundle: DatasetBundle,
        run_name: str = "run",
        output_root: str | Path = "output",
        scale_features: bool = True,
    ):
        self.bundle = bundle
        self.run_name = run_name
        self.output_root = Path(output_root)
        self.scale_features = scale_features

    def _make_output_dir(self) -> Path:
        stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in self.run_name)
        out = self.output_root / f"{stamp}_{safe}"
        out.mkdir(parents=True, exist_ok=True)
        return out

    def run(self, detector: AnomalyDetector, submission: pd.DataFrame | None = None) -> PipelineResult:
        """Run the full pipeline.

        If `submission` is given (timestamp, anomaly_score), it is used directly
        instead of calling detector.predict — useful for offline submissions.
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

        # --- fit / predict ---
        if submission is None:
            detector.fit(train_x, b.train_y, valid_x, b.valid_y, ctx)
            scores = np.asarray(detector.predict(test_x, ctx), dtype=float)
        else:
            merged = b.test_x[["timestamp"]].merge(submission, on="timestamp", how="left")
            scores = merged["anomaly_score"].to_numpy(dtype=float)

        if scores.shape[0] != len(b.test_x):
            raise ValueError(
                f"predict returned {scores.shape[0]} scores but test has {len(b.test_x)} rows"
            )
        scores = np.nan_to_num(scores, nan=0.0, posinf=0.0, neginf=0.0)

        # --- evaluate ---
        y_true = b.test_truth["y_true"].to_numpy()
        det_metrics, threshold = evaluate_detection(y_true, scores)
        rca_metrics = evaluate_rca(b.test_incident_truth, scores, threshold)

        # --- plots ---
        _plot_all(out_dir, b.test_x["timestamp"], y_true, scores, threshold, det_metrics)

        # --- persist artifacts ---
        # strip private curve data before writing the headline metrics
        public_det = {k: v for k, v in det_metrics.items() if not k.startswith("_")}
        metrics_out = {
            "run_name": self.run_name,
            "dataset": b.meta.get("dataset_name", ""),
            "detection": public_det,
            "rca": {k: v for k, v in rca_metrics.items() if k != "per_incident"},
            "scaled_features": self.scale_features,
        }
        (out_dir / "metrics.json").write_text(json.dumps(metrics_out, indent=2))

        # full submission + per-incident breakdown
        pd.DataFrame({
            "timestamp": b.test_x["timestamp"],
            "anomaly_score": scores,
            "y_pred": (scores >= threshold).astype(int),
            "y_true": y_true,
        }).to_csv(out_dir / "predictions.csv", index=False)
        if rca_metrics.get("per_incident"):
            pd.DataFrame(rca_metrics["per_incident"]).to_csv(
                out_dir / "per_incident.csv", index=False
            )

        self._print_summary(out_dir, public_det, rca_metrics)
        return PipelineResult(self.run_name, out_dir, metrics_out, scores, threshold)

    @staticmethod
    def _print_summary(out_dir: Path, det: dict, rca: dict) -> None:
        print(f"\n{'='*52}\n Pipeline result -> {out_dir}\n{'='*52}")
        print(f" Detection:  F1={det['f1']:.3f}  P={det['precision']:.3f}  "
              f"R={det['recall']:.3f}  ROC-AUC={det['roc_auc']:.3f}  PR-AUC={det['pr_auc']:.3f}")
        print(f" Threshold:  {det['threshold']:.4g}  "
              f"(TP={det['tp']} FP={det['fp']} FN={det['fn']} TN={det['tn']})")
        print(f" RCA:        {rca['incidents_detected']}/{rca['incidents_total']} incidents "
              f"detected ({rca['incident_detection_rate']*100:.1f}%)")
        print(f" Artifacts:  metrics.json, predictions.csv, per_incident.csv,")
        print(f"             score_timeline.png, roc_pr_curves.png, score_distribution.png")
        print("="*52)
