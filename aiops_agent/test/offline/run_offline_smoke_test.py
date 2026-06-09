"""Offline mode smoke test for the AIOps agent.

This script runs one end-to-end offline diagnosis request through the unified
entrypoint, then validates that both JSON and Markdown reports are generated
with the expected core structure.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def find_project_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "main.py").exists() and (parent / "veadk_app").exists():
            return parent
    raise RuntimeError("无法自动定位 aiops_agent 项目根目录，请确认脚本仍在当前仓库内。")


PROJECT_ROOT = find_project_root()
WORKSPACE_ROOT = PROJECT_ROOT.parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output" / "veadk_reports"
DEFAULT_RESULTS_DIR = Path(__file__).resolve().parent / "results"
DEFAULT_PROMPT = (
    "请先总结数据集，再扫描 valid split 中最异常的窗口，并继续分析排名第一的窗口，"
    "最后生成完整报告。"
)

REQUIRED_JSON_KEYS = {
    "mode",
    "dataset_name",
    "split",
    "start_time",
    "end_time",
    "start_index",
    "end_index",
    "is_anomaly",
    "summary",
    "agent_context",
}

REQUIRED_MD_SNIPPETS = [
    "# AIOps 离线诊断报告",
    "## 一、事件概览",
    "## 三、Agent 分析过程",
    "## 八、Agent 工具调用轨迹",
    "## 九、报告解释",
]


@dataclass
class SmokeResult:
    passed: bool
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    json_report: str | None
    markdown_report: str | None
    details: dict[str, Any]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run an offline AIOps smoke test.")
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable used to run the agent. Defaults to the current interpreter.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory where offline reports are expected to be generated.",
    )
    parser.add_argument(
        "--results-dir",
        default=str(DEFAULT_RESULTS_DIR),
        help="Directory where the smoke test transcript/result files will be written.",
    )
    parser.add_argument(
        "--prompt",
        default=DEFAULT_PROMPT,
        help="One-shot offline prompt used to drive the diagnosis flow.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=300,
        help="Max seconds to wait for the offline agent command to complete.",
    )
    parser.add_argument(
        "--clean-output",
        action="store_true",
        help="Delete existing offline JSON/MD reports before running the test.",
    )
    return parser


def clean_output_dir(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for pattern in ("*.json", "*.md"):
        for file_path in output_dir.glob(pattern):
            file_path.unlink()


def snapshot_reports(output_dir: Path) -> set[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    return set(output_dir.glob("*.json")) | set(output_dir.glob("*.md"))


def run_agent(command: list[str], timeout_seconds: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=WORKSPACE_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout_seconds,
        errors="replace",
    )


def pick_latest_report_pair(new_files: set[Path]) -> tuple[Path | None, Path | None]:
    json_files = sorted(
        (path for path in new_files if path.suffix.lower() == ".json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    md_files = sorted(
        (path for path in new_files if path.suffix.lower() == ".md"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return (json_files[0] if json_files else None, md_files[0] if md_files else None)


def validate_json_report(json_path: Path) -> dict[str, Any]:
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    missing_keys = sorted(REQUIRED_JSON_KEYS - set(payload.keys()))
    details = {
        "missing_keys": missing_keys,
        "mode": payload.get("mode"),
        "split": payload.get("split"),
        "window": {
            "start_index": payload.get("start_index"),
            "end_index": payload.get("end_index"),
        },
        "summary_length": len(str(payload.get("summary", ""))),
        "tool_call_count": payload.get("agent_context", {}).get("tool_call_count"),
    }
    if missing_keys:
        raise AssertionError(f"JSON 报告缺少关键字段: {missing_keys}")
    if payload.get("mode") != "offline":
        raise AssertionError(f"JSON 报告 mode 异常: {payload.get('mode')!r}")
    return details


def validate_markdown_report(md_path: Path) -> dict[str, Any]:
    content = md_path.read_text(encoding="utf-8")
    missing_sections = [snippet for snippet in REQUIRED_MD_SNIPPETS if snippet not in content]
    details = {
        "missing_sections": missing_sections,
        "line_count": len(content.splitlines()),
    }
    if missing_sections:
        raise AssertionError(f"Markdown 报告缺少关键章节: {missing_sections}")
    return details


def write_result_files(results_dir: Path, smoke: SmokeResult) -> dict[str, str]:
    results_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    result_json = results_dir / f"offline_smoke_result_{timestamp}.json"
    transcript_txt = results_dir / f"offline_smoke_transcript_{timestamp}.txt"

    result_json.write_text(
        json.dumps(
            {
                "passed": smoke.passed,
                "command": smoke.command,
                "returncode": smoke.returncode,
                "json_report": smoke.json_report,
                "markdown_report": smoke.markdown_report,
                "details": smoke.details,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    transcript_txt.write_text(
        "\n".join(
            [
                "[COMMAND]",
                " ".join(smoke.command),
                "",
                "[STDOUT]",
                smoke.stdout,
                "",
                "[STDERR]",
                smoke.stderr,
            ]
        ),
        encoding="utf-8",
    )
    return {
        "result_json": str(result_json),
        "transcript_txt": str(transcript_txt),
    }


def main() -> int:
    args = build_parser().parse_args()

    output_dir = Path(args.output_dir)
    results_dir = Path(args.results_dir)

    if args.clean_output:
        clean_output_dir(output_dir)

    before_files = snapshot_reports(output_dir)
    command = [
        args.python,
        "-m",
        "aiops_agent.main",
        "--mode",
        "offline",
        "--prompt",
        args.prompt,
    ]

    try:
        completed = run_agent(command, args.timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        smoke = SmokeResult(
            passed=False,
            command=command,
            returncode=-1,
            stdout=exc.stdout or "",
            stderr=(exc.stderr or "") + f"\n[timeout] 命令执行超过 {args.timeout_seconds} 秒。",
            json_report=None,
            markdown_report=None,
            details={"error": "timeout"},
        )
        files = write_result_files(results_dir, smoke)
        print("离线测试失败：执行超时。")
        print(json.dumps(files, ensure_ascii=False, indent=2))
        return 1

    after_files = snapshot_reports(output_dir)
    new_files = after_files - before_files
    json_report, markdown_report = pick_latest_report_pair(new_files)

    details: dict[str, Any] = {
        "new_files": sorted(str(path) for path in new_files),
    }
    passed = completed.returncode == 0

    if not json_report or not markdown_report:
        passed = False
        details["error"] = "missing_report_files"
    else:
        try:
            details["json_validation"] = validate_json_report(json_report)
            details["markdown_validation"] = validate_markdown_report(markdown_report)
        except Exception as exc:  # noqa: BLE001
            passed = False
            details["error"] = str(exc)

    smoke = SmokeResult(
        passed=passed,
        command=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        json_report=str(json_report) if json_report else None,
        markdown_report=str(markdown_report) if markdown_report else None,
        details=details,
    )

    files = write_result_files(results_dir, smoke)

    print("=" * 60)
    print("离线模式冒烟测试结果")
    print("=" * 60)
    print(f"通过状态: {'PASS' if smoke.passed else 'FAIL'}")
    print(f"返回码: {smoke.returncode}")
    print(f"JSON 报告: {smoke.json_report}")
    print(f"Markdown 报告: {smoke.markdown_report}")
    print("结果文件:")
    print(json.dumps(files, ensure_ascii=False, indent=2))

    if not smoke.passed:
        print("详细失败信息:")
        print(json.dumps(smoke.details, ensure_ascii=False, indent=2))
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
