"""Dataset loading and window slicing for offline diagnosis."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .models import DatasetArtifacts, DiagnosticWindow


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def load_dataset(dataset_root: str | Path) -> DatasetArtifacts:
    """Load the assembled RCA dataset from disk."""

    root = Path(dataset_root)
    processed_dir = root / "processed"
    answers_dir = root / "answers"

    meta = json.loads((root / "dataset_meta.json").read_text(encoding="utf-8"))
    norm_stats = json.loads((processed_dir / "norm_stats.json").read_text(encoding="utf-8"))
    feature_schema = _read_csv(processed_dir / "feature_schema.csv")

    test_ground_truth = _read_csv(answers_dir / "test_ground_truth.csv")
    test_incident_truth = _read_csv(answers_dir / "test_incident_ground_truth.csv")
    test_y = test_ground_truth.merge(
        test_incident_truth[["timestamp", "incident_id", "phase"]],
        on="timestamp",
        how="left",
    )

    return DatasetArtifacts(
        root=root,
        meta=meta,
        norm_stats=norm_stats,
        feature_schema=feature_schema,
        train_x=_read_csv(processed_dir / "train_x.csv"),
        train_y=_read_csv(processed_dir / "train_y.csv"),
        valid_x=_read_csv(processed_dir / "valid_x.csv"),
        valid_y=_read_csv(processed_dir / "valid_y.csv"),
        test_x=_read_csv(processed_dir / "test_x.csv"),
        test_y=test_y,
        test_rca_truth=_read_csv(answers_dir / "test_root_cause_ground_truth.csv"),
    )


def select_split_frames(dataset: DatasetArtifacts, split: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return features and labels for the selected split."""

    split = split.lower()
    if split == "train":
        return dataset.train_x, dataset.train_y
    if split == "valid":
        return dataset.valid_x, dataset.valid_y
    if split == "test":
        return dataset.test_x, dataset.test_y
    raise ValueError(f"Unsupported split: {split}")


def build_window(
    dataset: DatasetArtifacts,
    split: str,
    start_index: int,
    window_size: int,
) -> DiagnosticWindow:
    """Build one analysis window from a dataset split."""

    features, labels = select_split_frames(dataset, split)
    if start_index < 0:
        raise ValueError("start_index must be >= 0")
    if window_size <= 0:
        raise ValueError("window_size must be > 0")
    if start_index >= len(features):
        raise ValueError(f"start_index {start_index} is outside split length {len(features)}")

    end_index = min(start_index + window_size, len(features))
    window_features = features.iloc[start_index:end_index].reset_index(drop=True)
    window_labels = labels.iloc[start_index:end_index].reset_index(drop=True)

    metadata = {
        "dataset_name": dataset.meta.get("dataset_name", dataset.root.name),
        "sampling_interval_seconds": dataset.meta.get("sampling_interval_seconds", 5),
        "feature_count": dataset.meta.get("feature_count", len(dataset.feature_columns)),
    }
    return DiagnosticWindow(
        dataset_name=metadata["dataset_name"],
        split=split,
        start_index=start_index,
        end_index=end_index - 1,
        features=window_features,
        labels=window_labels,
        metadata=metadata,
    )
