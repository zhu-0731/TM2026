"""
Anomaly-detection evaluation metrics for the Online Boutique AIOps benchmark.

Implements point-level, ranking, event-level, latency, false-alarm,
point-adjust, and grouped (by fault_type / target_service) metrics, plus
threshold provenance. All functions are pure: they take y_true / y_pred /
scores / incident windows and return plain dicts that JSON-serialize cleanly.

Conventions
-----------
- timestamps are ISO-8601 UTC strings ("...Z").
- scores: higher = more anomalous.
- y_pred is derived from scores at a chosen threshold (>=).
- "null" (Python None) is emitted where a metric is undefined (e.g. AUROC
  when y_true is single-class); a matching warning string is collected.
"""
from __future__ import annotations

import warnings
from typing import Optional

import numpy as np
import pandas as pd


# ─────────────────────────────────────────────────────────────────────────────
# Point-level
# ─────────────────────────────────────────────────────────────────────────────

def point_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """Confusion-matrix-based point-wise metrics."""
    y_true = np.asarray(y_true).astype(int)
    y_pred = np.asarray(y_pred).astype(int)

    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    fp = int(((y_pred == 1) & (y_true == 0)).sum())
    tn = int(((y_pred == 0) & (y_true == 0)).sum())
    fn = int(((y_pred == 0) & (y_true == 1)).sum())

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall    = tp / (tp + fn) if (tp + fn) else 0.0
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    accuracy  = (tp + tn) / max(tp + fp + tn + fn, 1)
    specificity = tn / (tn + fp) if (tn + fp) else 0.0

    return {
        "point_precision":   round(precision, 6),
        "point_recall":      round(recall, 6),
        "point_f1":          round(f1, 6),
        "point_accuracy":    round(accuracy, 6),
        "point_specificity": round(specificity, 6),
        "TP": tp, "FP": fp, "TN": tn, "FN": fn,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Ranking (AUPRC / AUROC) — undefined for single-class y_true
# ─────────────────────────────────────────────────────────────────────────────

def _trapz(x: np.ndarray, y: np.ndarray) -> float:
    order = np.argsort(x)
    return float(np.trapz(y[order], x[order]))


def ranking_metrics(y_true: np.ndarray, scores: np.ndarray,
                    warnings_out: Optional[list] = None) -> dict:
    """ROC-AUC and PR-AUC via threshold sweep.

    Returns null for both if y_true is all-0 or all-1 (undefined), and records
    a warning string in `warnings_out`.
    """
    y_true = np.asarray(y_true).astype(int)
    scores = np.asarray(scores, dtype=float)

    pos = int(y_true.sum())
    neg = int((1 - y_true).sum())

    if pos == 0 or neg == 0:
        msg = (f"AUPRC/AUROC undefined: y_true is single-class "
               f"(positives={pos}, negatives={neg}); returning null")
        if warnings_out is not None:
            warnings_out.append(msg)
        warnings.warn(msg)
        return {"pr_auc": None, "roc_auc": None}

    thresholds = np.unique(scores)
    if len(thresholds) > 1000:
        thresholds = np.quantile(scores, np.linspace(0, 1, 1000))
    # sweep high->low so curves go left->right
    thresholds = np.sort(thresholds)[::-1]

    tprs, fprs, precs, recs = [], [], [], []
    for t in thresholds:
        yp = (scores >= t).astype(int)
        tp = int(((yp == 1) & (y_true == 1)).sum())
        fp = int(((yp == 1) & (y_true == 0)).sum())
        tprs.append(tp / pos)
        fprs.append(fp / neg)
        precs.append(tp / max(tp + fp, 1))
        recs.append(tp / pos)

    roc_auc = _trapz(np.array(fprs), np.array(tprs))
    pr_auc  = _trapz(np.array(recs), np.array(precs))
    return {
        "pr_auc":  round(pr_auc, 6),
        "roc_auc": round(roc_auc, 6),
        "_roc": {"fpr": fprs, "tpr": tprs},
        "_pr":  {"recall": recs, "precision": precs},
    }


# ─────────────────────────────────────────────────────────────────────────────
# Event-level + detection delay
# ─────────────────────────────────────────────────────────────────────────────

def _to_dt(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, utc=True)


def event_and_delay_metrics(
    timestamps: pd.Series,
    y_pred: np.ndarray,
    incidents: pd.DataFrame,
) -> dict:
    """Event-level recall, recall@{15,30,60}s, and detection delay.

    An incident is detected if ANY point inside [effect_start, effect_end]
    has y_pred == 1. Delay = first_alarm_time - effect_start (seconds), where
    first_alarm_time is the earliest y_pred==1 timestamp within the window.
    recall@Ns counts incidents whose first alarm is within N seconds of
    effect_start.
    """
    ts = _to_dt(pd.Series(timestamps).reset_index(drop=True))
    yp = np.asarray(y_pred).astype(int)

    per_incident = []
    delays = []  # seconds, detected only

    for _, inc in incidents.iterrows():
        eff_start = pd.to_datetime(inc["effect_start"], utc=True)
        eff_end   = pd.to_datetime(inc["effect_end"], utc=True)
        in_window = (ts >= eff_start) & (ts <= eff_end)
        win_idx = np.where(in_window.to_numpy())[0]

        detected = False
        first_alarm_time = None
        delay = None
        if win_idx.size > 0:
            alarms = win_idx[yp[win_idx] == 1]
            if alarms.size > 0:
                detected = True
                first_alarm_time = ts.iloc[int(alarms[0])]
                delay = (first_alarm_time - eff_start).total_seconds()
                delays.append(delay)

        per_incident.append({
            "incident_id":   inc.get("incident_id", ""),
            "fault_type":    inc.get("fault_type", ""),
            "target_service": inc.get("target_service", ""),
            "effect_start":  inc["effect_start"],
            "effect_end":    inc["effect_end"],
            "detected":      detected,
            "first_alarm_time": (first_alarm_time.strftime("%Y-%m-%dT%H:%M:%SZ")
                                 if first_alarm_time is not None else None),
            "delay_seconds": (round(delay, 3) if delay is not None else None),
            "detected_within_15s": bool(delay is not None and delay <= 15),
            "detected_within_30s": bool(delay is not None and delay <= 30),
            "detected_within_60s": bool(delay is not None and delay <= 60),
        })

    total = len(per_incident)
    detected_list = [p for p in per_incident if p["detected"]]
    missed_list   = [p for p in per_incident if not p["detected"]]
    n_detected = len(detected_list)

    def _rate(pred_key: str) -> float:
        return round(sum(1 for p in per_incident if p[pred_key]) / max(total, 1), 6)

    delays_arr = np.array(delays, dtype=float)
    if delays_arr.size > 0:
        delay_stats = {
            "mean_detection_delay_seconds":   round(float(delays_arr.mean()), 3),
            "median_detection_delay_seconds": round(float(np.median(delays_arr)), 3),
            "p90_detection_delay_seconds":    round(float(np.percentile(delays_arr, 90)), 3),
            "max_detection_delay_seconds":    round(float(delays_arr.max()), 3),
        }
    else:
        delay_stats = {
            "mean_detection_delay_seconds":   None,
            "median_detection_delay_seconds": None,
            "p90_detection_delay_seconds":    None,
            "max_detection_delay_seconds":    None,
        }

    return {
        "event_recall":       round(n_detected / max(total, 1), 6),
        "detected_incidents": n_detected,
        "missed_incidents":   len(missed_list),
        "missed_incident_ids": [p["incident_id"] for p in missed_list],
        "recall_at_15s":      _rate("detected_within_15s"),
        "recall_at_30s":      _rate("detected_within_30s"),
        "recall_at_60s":      _rate("detected_within_60s"),
        **delay_stats,
        "per_incident_delay_seconds": {
            p["incident_id"]: p["delay_seconds"] for p in detected_list
        },
        "_per_incident": per_incident,  # consumed by per_incident.csv writer
    }


# ─────────────────────────────────────────────────────────────────────────────
# False-alarm metrics
# ─────────────────────────────────────────────────────────────────────────────

def false_alarm_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    sampling_interval_seconds: float,
) -> dict:
    """False positives per hour over normal (non-anomaly) duration."""
    y_true = np.asarray(y_true).astype(int)
    y_pred = np.asarray(y_pred).astype(int)

    normal_points = int((y_true == 0).sum())
    fp = int(((y_pred == 1) & (y_true == 0)).sum())
    total_points = int(len(y_true))
    n_alarms = int((y_pred == 1).sum())

    normal_hours = normal_points * sampling_interval_seconds / 3600.0
    far = (fp / normal_hours) if normal_hours > 0 else None

    return {
        "false_alarms_per_hour": (round(far, 6) if far is not None else None),
        "false_positive_points": fp,
        "normal_points":         normal_points,
        "normal_duration_hours": round(normal_hours, 6),
        "alarm_ratio":           round(n_alarms / max(total_points, 1), 6),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Point-adjust (OmniAnomaly / USAD protocol)
# ─────────────────────────────────────────────────────────────────────────────

def point_adjust_metrics(
    timestamps: pd.Series,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    incidents: pd.DataFrame,
) -> dict:
    """Point-adjust: if any point in a true anomaly segment is flagged, the
    WHOLE segment is counted as correctly detected, then point metrics recomputed.

    Segments are taken from incident effect windows (the canonical anomaly
    intervals), which matches the labeling source.
    """
    ts = _to_dt(pd.Series(timestamps).reset_index(drop=True))
    yp_adj = np.asarray(y_pred).astype(int).copy()

    for _, inc in incidents.iterrows():
        eff_start = pd.to_datetime(inc["effect_start"], utc=True)
        eff_end   = pd.to_datetime(inc["effect_end"], utc=True)
        in_window = ((ts >= eff_start) & (ts <= eff_end)).to_numpy()
        if in_window.any() and (yp_adj[in_window] == 1).any():
            yp_adj[in_window] = 1

    pm = point_metrics(y_true, yp_adj)
    return {
        "point_adjust_precision": pm["point_precision"],
        "point_adjust_recall":    pm["point_recall"],
        "point_adjust_f1":        pm["point_f1"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Grouped metrics (by fault_type / target_service)
# ─────────────────────────────────────────────────────────────────────────────

def grouped_metrics(
    timestamps: pd.Series,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    incidents: pd.DataFrame,
    per_incident: list[dict],
) -> dict:
    """Per-group event_recall, recall_at_30s, median_delay, and point_f1.

    Groups are computed for both fault_type and target_service. point_f1 per
    group restricts point-level scoring to that group's incident windows
    (normal points shared across all groups are included for context).
    """
    ts = _to_dt(pd.Series(timestamps).reset_index(drop=True))
    y_true = np.asarray(y_true).astype(int)
    y_pred = np.asarray(y_pred).astype(int)

    pi_by_id = {p["incident_id"]: p for p in per_incident}

    def _group(group_col: str, want_point_f1: bool) -> dict:
        out: dict[str, dict] = {}
        for gval, grp in incidents.groupby(group_col):
            incs = grp["incident_id"].tolist()
            pis = [pi_by_id[i] for i in incs if i in pi_by_id]
            total = len(pis)
            detected = sum(1 for p in pis if p["detected"])
            within30 = sum(1 for p in pis if p["detected_within_30s"])
            delays = [p["delay_seconds"] for p in pis if p["delay_seconds"] is not None]
            entry = {
                "event_recall":  round(detected / max(total, 1), 6),
                "recall_at_30s": round(within30 / max(total, 1), 6),
                "median_delay_seconds": (round(float(np.median(delays)), 3) if delays else None),
                "incidents": total,
            }
            if want_point_f1:
                # point_f1 over union of this group's windows + all normal points
                mask = np.zeros(len(ts), dtype=bool)
                for _, inc in grp.iterrows():
                    es = pd.to_datetime(inc["effect_start"], utc=True)
                    ee = pd.to_datetime(inc["effect_end"], utc=True)
                    mask |= ((ts >= es) & (ts <= ee)).to_numpy()
                mask |= (y_true == 0)  # include normal points
                pm = point_metrics(y_true[mask], y_pred[mask])
                entry["point_f1"] = pm["point_f1"]
            out[str(gval)] = entry
        return out

    ft = _group("fault_type", want_point_f1=True)
    svc = _group("target_service", want_point_f1=False)

    return {
        "event_recall_by_fault_type":  {k: v["event_recall"]  for k, v in ft.items()},
        "recall_at_30s_by_fault_type": {k: v["recall_at_30s"] for k, v in ft.items()},
        "median_delay_by_fault_type":  {k: v["median_delay_seconds"] for k, v in ft.items()},
        "point_f1_by_fault_type":      {k: v["point_f1"] for k, v in ft.items()},
        "event_recall_by_service":     {k: v["event_recall"]  for k, v in svc.items()},
        "recall_at_30s_by_service":    {k: v["recall_at_30s"] for k, v in svc.items()},
        "median_delay_by_service":     {k: v["median_delay_seconds"] for k, v in svc.items()},
    }


# ─────────────────────────────────────────────────────────────────────────────
# Threshold selection
# ─────────────────────────────────────────────────────────────────────────────

def select_threshold(
    scores: np.ndarray,
    y_true: np.ndarray,
    mode: str = "best_f1",
    valid_scores: Optional[np.ndarray] = None,
    valid_y: Optional[np.ndarray] = None,
    fixed_fpr: Optional[float] = None,
) -> dict:
    """Choose a decision threshold and report its provenance / deployability.

    Modes
    -----
    best_f1   : maximize F1 on the TEST set. Upper-bound only; not deployable
                (peeks at test labels). threshold_deployable=False.
    validation_f1 : maximize F1 on the VALIDATION set (requires valid_scores +
                valid_y). Deployable. threshold_deployable=True.
    fixed_fpr : pick threshold giving a target FPR on validation normals
                (requires valid_scores + valid_y + fixed_fpr). Deployable.

    Returns a dict with threshold_mode / threshold_value / threshold_deployable
    plus best_f1 / validation_f1 / fixed_fpr fields where applicable.
    """
    scores = np.asarray(scores, dtype=float)
    y_true = np.asarray(y_true).astype(int)

    def _best_f1(s: np.ndarray, y: np.ndarray) -> tuple[float, float]:
        if y.sum() == 0:
            return float(np.max(s)) if s.size else 0.0, 0.0
        order = np.argsort(-s)
        ss, ys = s[order], y[order]
        tp = np.cumsum(ys)
        fp = np.cumsum(1 - ys)
        prec = tp / np.maximum(tp + fp, 1)
        rec = tp / max(int(y.sum()), 1)
        f1 = 2 * prec * rec / np.maximum(prec + rec, 1e-12)
        b = int(np.argmax(f1))
        return float(ss[b]), float(f1[b])

    info: dict = {
        "threshold_mode": mode,
        "use_pred": True,
        "best_f1": None,
        "validation_f1": None,
        "fixed_fpr": fixed_fpr,
    }

    # always report the test best-F1 as an upper bound for reference
    test_thr, test_best_f1 = _best_f1(scores, y_true)
    info["best_f1"] = round(test_best_f1, 6)

    if mode == "best_f1":
        info["threshold_value"] = round(test_thr, 6)
        info["threshold_deployable"] = False

    elif mode == "validation_f1":
        if valid_scores is None or valid_y is None:
            raise ValueError("validation_f1 mode requires valid_scores and valid_y")
        v_thr, v_f1 = _best_f1(np.asarray(valid_scores, float),
                               np.asarray(valid_y).astype(int))
        info["threshold_value"] = round(v_thr, 6)
        info["validation_f1"] = round(v_f1, 6)
        info["threshold_deployable"] = True

    elif mode == "fixed_fpr":
        if valid_scores is None or valid_y is None or fixed_fpr is None:
            raise ValueError("fixed_fpr mode requires valid_scores, valid_y, fixed_fpr")
        vs = np.asarray(valid_scores, float)
        vy = np.asarray(valid_y).astype(int)
        normal_scores = vs[vy == 0]
        if normal_scores.size == 0:
            raise ValueError("fixed_fpr mode requires normal points in validation")
        # threshold = (1 - fpr) quantile of normal scores
        thr = float(np.quantile(normal_scores, 1.0 - fixed_fpr))
        info["threshold_value"] = round(thr, 6)
        info["threshold_deployable"] = True

    else:
        raise ValueError(f"unknown threshold mode: {mode}")

    return info


# ─────────────────────────────────────────────────────────────────────────────
# Top-level orchestrator
# ─────────────────────────────────────────────────────────────────────────────

def compute_all(
    timestamps: pd.Series,
    y_true: np.ndarray,
    scores: np.ndarray,
    incidents: pd.DataFrame,
    sampling_interval_seconds: float,
    threshold_info: dict,
) -> tuple[dict, list[dict]]:
    """Compute the full metric suite at the threshold in `threshold_info`.

    Returns (metrics_dict, per_incident_rows).
    """
    warnings_out: list[str] = []
    scores = np.asarray(scores, dtype=float)
    y_true = np.asarray(y_true).astype(int)
    threshold = threshold_info["threshold_value"]
    y_pred = (scores >= threshold).astype(int)

    point = point_metrics(y_true, y_pred)
    ranking = ranking_metrics(y_true, scores, warnings_out)
    ranking_public = {k: v for k, v in ranking.items() if not k.startswith("_")}

    event = event_and_delay_metrics(timestamps, y_pred, incidents)
    per_incident = event.pop("_per_incident")

    false_alarm = false_alarm_metrics(y_true, y_pred, sampling_interval_seconds)
    padj = point_adjust_metrics(timestamps, y_true, y_pred, incidents)
    grouped = grouped_metrics(timestamps, y_true, y_pred, incidents, per_incident)

    metrics = {
        "threshold": {
            "threshold_mode":       threshold_info["threshold_mode"],
            "threshold_value":      threshold_info["threshold_value"],
            "threshold_deployable": threshold_info["threshold_deployable"],
            "use_pred":             threshold_info.get("use_pred", True),
            "best_f1":              threshold_info.get("best_f1"),
            "validation_f1":        threshold_info.get("validation_f1"),
            "fixed_fpr":            threshold_info.get("fixed_fpr"),
        },
        "point_level":   point,
        "ranking":       ranking_public,
        "event_level":   {k: v for k, v in event.items()},
        "false_alarm":   false_alarm,
        "point_adjust":  padj,
        "grouped":       grouped,
        "warnings":      warnings_out,
    }
    # attach curves for plotting (private, stripped before JSON by caller if desired)
    if "_roc" in ranking:
        metrics["_curves"] = {"roc": ranking["_roc"], "pr": ranking["_pr"]}

    return metrics, per_incident
