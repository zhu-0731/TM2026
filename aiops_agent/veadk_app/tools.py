"""VeADK tools wrapping the offline diagnosis pipeline."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AIOPS_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = AIOPS_ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aiops_agent.offline.detector import RuleBasedDetector
from aiops_agent.offline.diagnoser import RuleBasedDiagnoser
from aiops_agent.offline.loader import build_window, load_dataset, select_split_frames
from aiops_agent.offline.models import (
    DatasetArtifacts,
    DetectionResult,
    DiagnosisResult,
    DiagnosticWindow,
)
from aiops_agent.offline.reporter import ReportWriter

DEFAULT_DATASET_ROOT = PROJECT_ROOT / "data" / "datasets" / "online_boutique_rca_full_v1"
DEFAULT_OUTPUT_DIR = AIOPS_ROOT / "output" / "veadk_reports"

_STATE: dict[str, Any] = {
    "dataset_root": None,
    "dataset": None,
    "window": None,
    "detection": None,
    "diagnosis": None,
    "report": None,
    "report_paths": None,
    "scan_results": None,
    "tool_history": [],
}


def _dataset_path(dataset_root: str | None) -> Path:
    return Path(dataset_root) if dataset_root else DEFAULT_DATASET_ROOT


def _output_path(output_dir: str | None) -> Path:
    return Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR


def _load_dataset_once(dataset_root: str | None) -> DatasetArtifacts:
    path = _dataset_path(dataset_root)
    dataset = load_dataset(path)
    _STATE["dataset_root"] = str(path)
    _STATE["dataset"] = dataset
    return dataset


def _reset_analysis_state(clear_scan_results: bool = False) -> None:
    _STATE["window"] = None
    _STATE["detection"] = None
    _STATE["diagnosis"] = None
    _STATE["report"] = None
    _STATE["report_paths"] = None
    if clear_scan_results:
        _STATE["scan_results"] = None


def _ensure_window() -> tuple[DatasetArtifacts, DiagnosticWindow]:
    dataset = _STATE.get("dataset")
    window = _STATE.get("window")
    if dataset is None or window is None:
        raise ValueError("当前还没有已加载的时间窗口，请先调用 load_window_tool。")
    return dataset, window


def _ensure_detection() -> tuple[DatasetArtifacts, DiagnosticWindow, DetectionResult]:
    dataset, window = _ensure_window()
    detection = _STATE.get("detection")
    if detection is None:
        raise ValueError("当前还没有异常检测结果，请先调用 detect_anomaly_tool。")
    return dataset, window, detection


def _ensure_diagnosis() -> tuple[DiagnosticWindow, DiagnosisResult]:
    window = _STATE.get("window")
    diagnosis = _STATE.get("diagnosis")
    if window is None or diagnosis is None:
        raise ValueError("当前还没有根因分析结果，请先调用 diagnose_root_cause_tool。")
    return window, diagnosis


def _window_summary(window: DiagnosticWindow) -> dict[str, Any]:
    return {
        "dataset_name": window.dataset_name,
        "split": window.split,
        "start_index": window.start_index,
        "end_index": window.end_index,
        "start_time": window.start_time,
        "end_time": window.end_time,
        "row_count": len(window.features),
        "incident_ids": sorted(
            {
                str(incident_id)
                for incident_id in window.labels.get("incident_id", [])
                if isinstance(incident_id, str) and incident_id
            }
        ),
    }


def _window_anomaly_score(detection: DetectionResult) -> float:
    if not detection.abnormal_metrics:
        return 0.0
    return round(sum(item.score for item in detection.abnormal_metrics), 3)


def _service_names(dataset: DatasetArtifacts) -> list[str]:
    services = set()
    for feature_name in dataset.feature_columns:
        if "_" not in feature_name:
            continue
        services.add(feature_name.split("_", 1)[0])
    return sorted(services)


def _summarize_result(tool_name: str, result: dict[str, Any]) -> dict[str, Any]:
    if tool_name == "summarize_dataset_tool":
        return {
            "status": result.get("status"),
            "dataset_name": result.get("dataset_name"),
            "feature_count": result.get("feature_count"),
            "splits": result.get("splits"),
        }
    if tool_name == "inspect_current_state_tool":
        return {
            "status": result.get("status"),
            "loaded_window": result.get("loaded_window"),
            "has_detection": result.get("has_detection"),
            "has_diagnosis": result.get("has_diagnosis"),
            "tool_history_count": result.get("tool_history_count"),
        }
    if tool_name == "show_ranked_windows_tool":
        return {
            "status": result.get("status"),
            "window_count": result.get("window_count"),
            "top_windows": result.get("top_windows"),
        }
    if tool_name == "show_tool_history_tool":
        return {
            "status": result.get("status"),
            "call_count": result.get("call_count"),
        }
    if tool_name == "load_window_tool":
        return {
            "status": result.get("status"),
            "window": result.get("window"),
        }
    if tool_name == "detect_anomaly_tool":
        return {
            "status": result.get("status"),
            "is_anomaly": result.get("is_anomaly"),
            "abnormal_services": result.get("abnormal_services"),
            "incident_ids": result.get("incident_ids"),
        }
    if tool_name == "diagnose_root_cause_tool":
        return {
            "status": result.get("status"),
            "suspected_root_cause_service": result.get("suspected_root_cause_service"),
            "candidate_scores": result.get("candidate_scores"),
        }
    if tool_name == "write_report_tool":
        return {
            "status": result.get("status"),
            "json_report": result.get("json_report"),
            "markdown_report": result.get("markdown_report"),
        }
    if tool_name == "find_anomalous_windows_tool":
        return {
            "status": result.get("status"),
            "anomalous_window_count": result.get("anomalous_window_count"),
            "top_windows": result.get("top_windows"),
        }
    if tool_name == "continue_with_ranked_window_tool":
        return {
            "status": result.get("status"),
            "selected_rank": result.get("selected_rank"),
            "selected_window": result.get("selected_window"),
            "suspected_root_cause_service": result.get("diagnosis", {}).get(
                "suspected_root_cause_service"
            ),
        }
    if tool_name == "run_full_offline_diagnosis_tool":
        return {
            "status": result.get("status"),
            "window": result.get("window"),
            "suspected_root_cause_service": result.get("diagnosis", {}).get(
                "suspected_root_cause_service"
            ),
        }
    return {"status": result.get("status"), "message": result.get("message")}


def _record_tool_call(
    tool_name: str,
    arguments: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    _STATE["tool_history"].append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool_name": tool_name,
            "arguments": arguments,
            "result_summary": _summarize_result(tool_name, result),
        }
    )
    return result


def _build_report_agent_context() -> dict[str, Any]:
    scan_results = _STATE.get("scan_results") or []
    window = _STATE.get("window")
    selected_window = None
    if window is not None:
        selected_window = next(
            (
                item
                for item in scan_results
                if item["split"] == window.split
                and item["start_index"] == window.start_index
                and item["end_index"] == window.end_index
            ),
            None,
        )

    return {
        "dataset_root": _STATE.get("dataset_root"),
        "tool_call_count": len(_STATE.get("tool_history") or []),
        "tool_trace": (_STATE.get("tool_history") or [])[-12:],
        "scan_result_count": len(scan_results),
        "selected_window": selected_window,
        "latest_report_paths": _STATE.get("report_paths"),
    }


def summarize_dataset_tool(dataset_root: str | None = None) -> dict[str, Any]:
    """Show the offline dataset structure, split sizes, and covered services."""

    dataset = _load_dataset_once(dataset_root)
    result = {
        "status": "ok",
        "message": "离线数据集概览已生成。",
        "dataset_root": _STATE["dataset_root"],
        "dataset_name": dataset.meta.get("dataset_name", dataset.root.name),
        "feature_count": len(dataset.feature_columns),
        "services": _service_names(dataset),
        "splits": {
            "train": len(dataset.train_x),
            "valid": len(dataset.valid_x),
            "test": len(dataset.test_x),
        },
        "sampling_interval_seconds": dataset.meta.get("sampling_interval_seconds", 5),
    }
    return _record_tool_call(
        "summarize_dataset_tool",
        {"dataset_root": dataset_root},
        result,
    )


def inspect_current_state_tool() -> dict[str, Any]:
    """Show what the offline agent has already loaded, detected, diagnosed, and written."""

    window = _STATE.get("window")
    detection = _STATE.get("detection")
    diagnosis = _STATE.get("diagnosis")
    result = {
        "status": "ok",
        "message": "当前离线 Agent 状态已整理。",
        "dataset_root": _STATE.get("dataset_root"),
        "loaded_window": _window_summary(window) if window is not None else None,
        "has_detection": detection is not None,
        "has_diagnosis": diagnosis is not None,
        "latest_detection": (
            {
                "is_anomaly": detection.is_anomaly,
                "abnormal_services": detection.abnormal_services,
                "incident_ids": detection.incident_ids,
            }
            if detection is not None
            else None
        ),
        "latest_diagnosis": (
            {
                "suspected_root_cause_service": diagnosis.suspected_root_cause_service,
                "candidate_scores": diagnosis.candidate_scores,
                "summary": diagnosis.summary,
            }
            if diagnosis is not None
            else None
        ),
        "latest_report_paths": _STATE.get("report_paths"),
        "scan_result_count": len(_STATE.get("scan_results") or []),
        "tool_history_count": len(_STATE.get("tool_history") or []),
    }
    return _record_tool_call("inspect_current_state_tool", {}, result)


def show_ranked_windows_tool(top_k: int = 3) -> dict[str, Any]:
    """Return the suspicious windows discovered by the latest scan."""

    scan_results = _STATE.get("scan_results") or []
    result = {
        "status": "ok",
        "message": "最近一次异常窗口扫描结果已返回。",
        "window_count": len(scan_results),
        "top_windows": scan_results[: max(1, top_k)],
    }
    return _record_tool_call(
        "show_ranked_windows_tool",
        {"top_k": top_k},
        result,
    )


def show_tool_history_tool(limit: int = 10) -> dict[str, Any]:
    """Return the recent offline tool call trace for explanation/reporting."""

    history = _STATE.get("tool_history") or []
    result = {
        "status": "ok",
        "message": "最近工具调用轨迹已返回。",
        "call_count": len(history),
        "recent_calls": history[-max(1, limit) :],
    }
    return _record_tool_call(
        "show_tool_history_tool",
        {"limit": limit},
        result,
    )


def find_anomalous_windows_tool(
    split: str = "valid",
    window_size: int = 120,
    step_size: int = 60,
    dataset_root: str | None = None,
    min_score: float = 3.0,
    max_evidence_items: int = 8,
    top_k: int = 3,
) -> dict[str, Any]:
    """Scan one split and return the most suspicious time windows."""

    if window_size <= 0:
        raise ValueError("window_size 必须大于 0。")
    if step_size <= 0:
        raise ValueError("step_size 必须大于 0。")
    if top_k <= 0:
        raise ValueError("top_k 必须大于 0。")

    dataset = _load_dataset_once(dataset_root)
    _reset_analysis_state(clear_scan_results=True)
    features, _ = select_split_frames(dataset, split)
    detector = RuleBasedDetector(min_score=min_score, max_evidence_items=max_evidence_items)

    total_rows = len(features)
    scan_results: list[dict[str, Any]] = []
    scanned_count = 0

    for start_index in range(0, total_rows, step_size):
        window = build_window(dataset, split=split, start_index=start_index, window_size=window_size)
        detection = detector.detect(dataset, window)
        scanned_count += 1
        if detection.is_anomaly:
            scan_results.append(
                {
                    "split": split,
                    "start_index": window.start_index,
                    "end_index": window.end_index,
                    "start_time": window.start_time,
                    "end_time": window.end_time,
                    "row_count": len(window.features),
                    "anomaly_score": _window_anomaly_score(detection),
                    "abnormal_services": detection.abnormal_services[:5],
                    "incident_ids": detection.incident_ids,
                    "top_evidence": [
                        {
                            "feature_name": item.feature_name,
                            "service": item.service,
                            "metric": item.metric,
                            "score": item.score,
                            "reason": item.reason,
                        }
                        for item in detection.abnormal_metrics[:3]
                    ],
                }
            )
        if start_index + window_size >= total_rows:
            break

    scan_results.sort(key=lambda item: item["anomaly_score"], reverse=True)
    ranked_results = [
        {"rank": rank, **item}
        for rank, item in enumerate(scan_results[:top_k], start=1)
    ]
    _STATE["scan_results"] = ranked_results

    result = {
        "status": "ok",
        "message": "异常时间段扫描完成。",
        "split": split,
        "window_size": window_size,
        "step_size": step_size,
        "total_rows": total_rows,
        "scanned_window_count": scanned_count,
        "anomalous_window_count": len(scan_results),
        "top_windows": ranked_results,
    }
    return _record_tool_call(
        "find_anomalous_windows_tool",
        {
            "split": split,
            "window_size": window_size,
            "step_size": step_size,
            "dataset_root": dataset_root,
            "min_score": min_score,
            "max_evidence_items": max_evidence_items,
            "top_k": top_k,
        },
        result,
    )


def load_window_tool(
    split: str = "valid",
    start_index: int = 0,
    window_size: int = 120,
    dataset_root: str | None = None,
) -> dict[str, Any]:
    """Load one time window from the offline dataset."""

    dataset = _load_dataset_once(dataset_root)
    window = build_window(dataset, split=split, start_index=start_index, window_size=window_size)
    _reset_analysis_state(clear_scan_results=False)
    _STATE["window"] = window
    result = {
        "status": "ok",
        "message": "时间窗口加载成功。",
        "window": _window_summary(window),
    }
    return _record_tool_call(
        "load_window_tool",
        {
            "split": split,
            "start_index": start_index,
            "window_size": window_size,
            "dataset_root": dataset_root,
        },
        result,
    )


def detect_anomaly_tool(min_score: float = 3.0, max_evidence_items: int = 8) -> dict[str, Any]:
    """Run rule-based anomaly detection on the loaded window."""

    dataset, window = _ensure_window()
    detector = RuleBasedDetector(min_score=min_score, max_evidence_items=max_evidence_items)
    detection = detector.detect(dataset, window)
    _STATE["detection"] = detection
    result = {
        "status": "ok",
        "message": "异常检测完成。",
        "is_anomaly": detection.is_anomaly,
        "abnormal_services": detection.abnormal_services,
        "incident_ids": detection.incident_ids,
        "top_evidence": [
            {
                "service": item.service,
                "metric": item.metric,
                "feature_name": item.feature_name,
                "score": item.score,
                "reason": item.reason,
            }
            for item in detection.abnormal_metrics
        ],
        "notes": detection.notes,
    }
    return _record_tool_call(
        "detect_anomaly_tool",
        {
            "min_score": min_score,
            "max_evidence_items": max_evidence_items,
        },
        result,
    )


def diagnose_root_cause_tool() -> dict[str, Any]:
    """Run root-cause diagnosis on the current detection result."""

    _, _, detection = _ensure_detection()
    diagnoser = RuleBasedDiagnoser()
    diagnosis = diagnoser.diagnose(detection)
    _STATE["diagnosis"] = diagnosis
    result = {
        "status": "ok",
        "message": "根因分析完成。",
        "is_anomaly": diagnosis.is_anomaly,
        "suspected_root_cause_service": diagnosis.suspected_root_cause_service,
        "abnormal_services": diagnosis.abnormal_services,
        "candidate_scores": diagnosis.candidate_scores,
        "supporting_metrics": [
            {
                "service": item.service,
                "metric": item.metric,
                "feature_name": item.feature_name,
                "score": item.score,
                "reason": item.reason,
            }
            for item in diagnosis.supporting_metrics
        ],
        "summary": diagnosis.summary,
    }
    return _record_tool_call("diagnose_root_cause_tool", {}, result)


def write_report_tool(output_dir: str | None = None) -> dict[str, Any]:
    """Write the current diagnosis result to JSON and Markdown reports."""

    window, diagnosis = _ensure_diagnosis()
    writer = ReportWriter()
    out_dir = _output_path(output_dir)
    report = writer.write(
        window,
        diagnosis,
        output_dir=out_dir,
        agent_context=_build_report_agent_context(),
    )
    stem = f"{window.split}_{window.start_index}_{window.end_index}"
    report_paths = {
        "json_report": str(out_dir / f"{stem}.json"),
        "markdown_report": str(out_dir / f"{stem}.md"),
    }
    _STATE["report"] = report
    _STATE["report_paths"] = report_paths
    result = {
        "status": "ok",
        "message": "诊断报告已生成。",
        **report_paths,
        "summary": report.summary,
    }
    return _record_tool_call(
        "write_report_tool",
        {"output_dir": output_dir},
        result,
    )


def continue_with_ranked_window_tool(
    rank: int = 1,
    output_dir: str | None = None,
    min_score: float = 3.0,
    max_evidence_items: int = 8,
) -> dict[str, Any]:
    """Continue diagnosis from a previously scanned suspicious window."""

    ranked_results = _STATE.get("scan_results") or []
    if not ranked_results:
        raise ValueError("当前没有可继续分析的扫描结果，请先调用 find_anomalous_windows_tool。")

    selected = next((item for item in ranked_results if item["rank"] == rank), None)
    if selected is None:
        raise ValueError(f"没有找到 rank={rank} 的异常窗口，请先查看 show_ranked_windows_tool。")

    result = run_full_offline_diagnosis_tool(
        split=selected["split"],
        start_index=selected["start_index"],
        window_size=selected["row_count"],
        dataset_root=_STATE.get("dataset_root"),
        output_dir=output_dir,
        min_score=min_score,
        max_evidence_items=max_evidence_items,
    )
    enriched = {
        **result,
        "selected_rank": rank,
        "selected_window": selected,
    }
    return _record_tool_call(
        "continue_with_ranked_window_tool",
        {
            "rank": rank,
            "output_dir": output_dir,
            "min_score": min_score,
            "max_evidence_items": max_evidence_items,
        },
        enriched,
    )


def run_full_offline_diagnosis_tool(
    split: str = "valid",
    start_index: int = 0,
    window_size: int = 120,
    dataset_root: str | None = None,
    output_dir: str | None = None,
    min_score: float = 3.0,
    max_evidence_items: int = 8,
) -> dict[str, Any]:
    """Run the full offline diagnosis pipeline in one call."""

    load_result = load_window_tool(
        split=split,
        start_index=start_index,
        window_size=window_size,
        dataset_root=dataset_root,
    )
    detect_result = detect_anomaly_tool(
        min_score=min_score,
        max_evidence_items=max_evidence_items,
    )
    diagnose_result = diagnose_root_cause_tool()
    report_result = write_report_tool(output_dir=output_dir)
    result = {
        "status": "ok",
        "message": "完整离线诊断流程执行完成。",
        "window": load_result["window"],
        "detection": detect_result,
        "diagnosis": diagnose_result,
        "report": report_result,
    }
    return _record_tool_call(
        "run_full_offline_diagnosis_tool",
        {
            "split": split,
            "start_index": start_index,
            "window_size": window_size,
            "dataset_root": dataset_root,
            "output_dir": output_dir,
            "min_score": min_score,
            "max_evidence_items": max_evidence_items,
        },
        result,
    )
