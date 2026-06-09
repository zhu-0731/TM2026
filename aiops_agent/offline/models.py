"""Shared data models for offline diagnosis."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class DatasetArtifacts:
    """In-memory representation of one assembled RCA dataset."""

    root: Path
    meta: dict[str, Any]
    norm_stats: dict[str, Any]
    feature_schema: pd.DataFrame
    train_x: pd.DataFrame
    train_y: pd.DataFrame
    valid_x: pd.DataFrame
    valid_y: pd.DataFrame
    test_x: pd.DataFrame
    test_y: pd.DataFrame
    test_rca_truth: pd.DataFrame

    @property
    def feature_columns(self) -> list[str]:
        return [col for col in self.train_x.columns if col != "timestamp"]


@dataclass
class DiagnosticWindow:
    """One continuous time window selected for diagnosis."""

    dataset_name: str
    split: str
    start_index: int
    end_index: int
    features: pd.DataFrame
    labels: pd.DataFrame
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def start_time(self) -> str:
        return str(self.features.iloc[0]["timestamp"])

    @property
    def end_time(self) -> str:
        return str(self.features.iloc[-1]["timestamp"])


@dataclass
class MetricEvidence:
    """One suspicious metric signal found during detection."""

    service: str
    metric: str
    feature_name: str
    score: float
    observed_value: float
    baseline_mean: float
    baseline_std: float
    reason: str


@dataclass
class DetectionResult:
    """Output of the anomaly detector stage."""

    is_anomaly: bool
    abnormal_services: list[str]
    abnormal_metrics: list[MetricEvidence]
    incident_ids: list[str]
    notes: list[str] = field(default_factory=list)


@dataclass
class DiagnosisResult:
    """Output of the root-cause analysis stage."""

    is_anomaly: bool
    abnormal_services: list[str]
    suspected_root_cause_service: str | None
    supporting_metrics: list[MetricEvidence]
    candidate_scores: dict[str, float]
    incident_ids: list[str]
    summary: str


@dataclass
class StructuredReport:
    """Serializable report written to JSON and Markdown."""

    mode: str
    dataset_name: str
    split: str
    start_time: str
    end_time: str
    start_index: int
    end_index: int
    is_anomaly: bool
    abnormal_services: list[str]
    suspected_root_cause_service: str | None
    incident_ids: list[str]
    evidence: list[dict[str, Any]]
    candidate_scores: dict[str, float]
    summary: str
    agent_context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
