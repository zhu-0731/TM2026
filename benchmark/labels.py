"""Generate y labels from incidents and timestamps."""
from __future__ import annotations

import pandas as pd
from datetime import datetime, timezone


def parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def build_labels(timestamps: list[str], incidents_df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns DataFrame with columns: timestamp, is_anomaly, incident_id, phase.
    incidents_df must have columns: incident_id, effect_start, effect_end.
    Raises if incidents overlap.
    """
    # Parse incident windows
    windows = []
    for _, row in incidents_df.iterrows():
        es = parse_ts(row["effect_start"])
        ee = parse_ts(row["effect_end"])
        windows.append((row["incident_id"], es, ee))

    # Check overlap
    windows_sorted = sorted(windows, key=lambda x: x[1])
    for i in range(len(windows_sorted) - 1):
        if windows_sorted[i][2] > windows_sorted[i + 1][1]:
            raise ValueError(
                f"Overlapping incidents: {windows_sorted[i][0]} and {windows_sorted[i+1][0]}"
            )

    rows = []
    for ts_str in timestamps:
        ts = parse_ts(ts_str)
        is_anomaly = 0
        inc_id = ""
        phase = "normal"
        for inc_id_w, es, ee in windows:
            if es <= ts < ee:
                is_anomaly = 1
                inc_id = inc_id_w
                phase = "fault_effect"
                break
        rows.append({
            "timestamp": ts_str,
            "is_anomaly": is_anomaly,
            "incident_id": inc_id,
            "phase": phase,
        })
    # Always return DataFrame with correct schema, even for empty timestamp list
    cols = ["timestamp", "is_anomaly", "incident_id", "phase"]
    if not rows:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(rows)


def build_incidents_df(mock_incidents: list) -> pd.DataFrame:
    """Convert MockIncident list to incidents.csv DataFrame.

    Uses real injection_start/injection_end/recovery_end when present
    (ChaosMesh real injection), otherwise falls back to effect times (smoke mode).
    """
    rows = []
    for inc in mock_incidents:
        ts = lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        rows.append({
            "incident_id":          inc.incident_id,
            # Real ChaosMesh timestamps (≠ effect times for real injections)
            "injection_start":      ts(inc.injection_start),
            "injection_end":        ts(inc.injection_end),
            "effect_start":         ts(inc.effect_start),
            "effect_end":           ts(inc.effect_end),
            "recovery_end":         ts(inc.recovery_end),
            "fault_type":           inc.fault_type,
            "target_service":       inc.target_service,
            "root_cause_service":   inc.root_cause_service,
            "severity":             inc.severity,
            "duration_sec":         inc.duration_sec,
            "valid_incident":       True,
            "root_cause_dims":      ";".join(inc.root_cause_dims),
            "secondary_dims":       ";".join(inc.secondary_dims),
        })
    return pd.DataFrame(rows)
