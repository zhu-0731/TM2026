"""End-to-end offline diagnosis workflow."""

from __future__ import annotations

from pathlib import Path

from .detector import RuleBasedDetector
from .diagnoser import RuleBasedDiagnoser
from .loader import build_window, load_dataset
from .reporter import ReportWriter
from .models import StructuredReport


def run_replay(
    dataset_root: str | Path,
    split: str = "valid",
    start_index: int = 0,
    window_size: int = 120,
    output_dir: str | Path = "aiops_agent/output",
) -> StructuredReport:
    """Run one end-to-end offline diagnosis over a selected time window."""

    dataset = load_dataset(dataset_root)
    window = build_window(dataset, split=split, start_index=start_index, window_size=window_size)

    detector = RuleBasedDetector()
    detection = detector.detect(dataset, window)

    diagnoser = RuleBasedDiagnoser()
    diagnosis = diagnoser.diagnose(detection)

    writer = ReportWriter()
    return writer.write(window, diagnosis, output_dir=output_dir)
