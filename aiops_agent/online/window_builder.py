"""Build online analysis windows compatible with the offline diagnosis pipeline."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from aiops_agent.offline.models import DatasetArtifacts, DiagnosticWindow


def build_online_window(
    dataset: DatasetArtifacts,
    features: pd.DataFrame,
    trigger_context: dict[str, object],
) -> DiagnosticWindow:
    """Convert a realtime metrics frame into a DiagnosticWindow."""

    if features.empty:
        raise ValueError("Online features frame is empty.")

    labels = pd.DataFrame(
        {
            "timestamp": features["timestamp"],
            "incident_id": ["" for _ in range(len(features))],
            "phase": ["online_monitor" for _ in range(len(features))],
        }
    )

    metadata = {
        "dataset_name": dataset.meta.get("dataset_name", dataset.root.name),
        "sampling_interval_seconds": dataset.meta.get("sampling_interval_seconds", 5),
        "feature_count": len([column for column in features.columns if column != "timestamp"]),
        "mode": "online",
        "trigger_context": trigger_context,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    return DiagnosticWindow(
        dataset_name=f"{metadata['dataset_name']}_online",
        split="online",
        start_index=0,
        end_index=len(features) - 1,
        features=features.reset_index(drop=True),
        labels=labels.reset_index(drop=True),
        metadata=metadata,
    )
