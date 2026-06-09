"""Inject a temporary CPU stress fault into a Kubernetes service container.

Default target:
- namespace: online-boutique
- service label: app=redis-cart
- container: redis
- duration: 120 seconds
- workers: 2

The script also writes aiops_agent/output/last_fault_injection.json so the
online AIOps agent can include the known fault-injection context in its report.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_RECORD_PATH = Path("aiops_agent/output/last_fault_injection.json")


def run_command(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a command and return its completed process."""

    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    if check and result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise RuntimeError(f"命令执行失败：{' '.join(command)}\n{message}")

    return result


def find_running_pod(namespace: str, service: str) -> dict[str, Any]:
    """Find one Running pod whose app label matches the service name."""

    result = run_command(
        [
            "kubectl",
            "get",
            "pods",
            "-n",
            namespace,
            "-l",
            f"app={service}",
            "-o",
            "json",
        ]
    )
    payload = json.loads(result.stdout)

    candidates: list[dict[str, Any]] = []
    for item in payload.get("items", []):
        phase = str(item.get("status", {}).get("phase") or "")
        deletion_timestamp = item.get("metadata", {}).get("deletionTimestamp")
        if phase == "Running" and not deletion_timestamp:
            candidates.append(item)

    if not candidates:
        raise RuntimeError(
            f"未找到服务 {service!r} 的 Running Pod。"
            "请先执行 kubectl get pods -n "
            f"{namespace} -l app={service} 检查状态。"
        )

    # Prefer the newest non-terminating pod.
    candidates.sort(
        key=lambda item: str(
            item.get("metadata", {}).get("creationTimestamp") or ""
        ),
        reverse=True,
    )
    return candidates[0]


def ensure_container_exists(pod: dict[str, Any], container: str) -> None:
    """Ensure the requested container exists in the selected pod."""

    names = {
        str(item.get("name"))
        for item in pod.get("spec", {}).get("containers", [])
        if item.get("name")
    }
    if container not in names:
        raise RuntimeError(
            f"Pod 中不存在容器 {container!r}。可用容器：{sorted(names)}"
        )


def write_fault_record(path: Path, payload: dict[str, Any]) -> None:
    """Persist fault-injection context for the online agent."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def build_stress_command(duration_seconds: int, workers: int) -> str:
    """Build a BusyBox/Alpine-compatible shell CPU workload."""

    # Each worker repeatedly performs integer operations and periodically checks
    # the wall clock. The command exits automatically after the requested time.
    worker = (
        f'end=$(( $(date +%s) + {duration_seconds} )); '
        'while [ "$(date +%s)" -lt "$end" ]; do '
        'i=0; '
        'while [ "$i" -lt 80000 ]; do i=$((i + 1)); done; '
        "done"
    )

    return (
        "n=0; "
        f'while [ "$n" -lt {workers} ]; do '
        f"sh -c '{worker}' & "
        'n=$((n + 1)); '
        "done; "
        "wait"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inject temporary CPU stress into a Kubernetes container."
    )
    parser.add_argument("--namespace", default="online-boutique")
    parser.add_argument("--service", default="redis-cart")
    parser.add_argument("--container", default="redis")
    parser.add_argument("--duration-seconds", type=int, default=120)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument(
        "--record-path",
        default=str(DEFAULT_RECORD_PATH),
        help="Fault-injection record consumed by the online AIOps agent.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    if args.duration_seconds < 20:
        raise ValueError("--duration-seconds 建议至少为 20 秒")
    if args.workers < 1 or args.workers > 8:
        raise ValueError("--workers 必须在 1 到 8 之间")

    pod = find_running_pod(args.namespace, args.service)
    ensure_container_exists(pod, args.container)

    pod_name = str(pod["metadata"]["name"])
    pod_uid = str(pod["metadata"].get("uid") or "")
    injected_at = datetime.now(timezone.utc)

    record: dict[str, Any] = {
        "enabled": True,
        "status": "running",
        "type": "cpu_stress",
        "target_service": args.service,
        "namespace": args.namespace,
        "target_pod": pod_name,
        "target_pod_uid": pod_uid,
        "target_container": args.container,
        "duration_seconds": args.duration_seconds,
        "workers": args.workers,
        "source": "scripts/inject_cpu_stress.py",
        "injected_at": injected_at.isoformat(),
    }
    record_path = Path(args.record_path)
    write_fault_record(record_path, record)

    print(f"[CPU Stress] 服务：{args.service}")
    print(f"[CPU Stress] Pod：{pod_name}")
    print(f"[CPU Stress] 容器：{args.container}")
    print(
        f"[CPU Stress] 持续 {args.duration_seconds} 秒，"
        f"并发 worker 数：{args.workers}"
    )
    print(f"[CPU Stress] 故障记录：{record_path}")
    print("[CPU Stress] 正在注入，请保持此终端运行……")

    shell_command = build_stress_command(
        duration_seconds=args.duration_seconds,
        workers=args.workers,
    )
    result = run_command(
        [
            "kubectl",
            "exec",
            pod_name,
            "-n",
            args.namespace,
            "-c",
            args.container,
            "--",
            "sh",
            "-c",
            shell_command,
        ],
        check=False,
    )

    finished_at = datetime.now(timezone.utc)
    record["finished_at"] = finished_at.isoformat()
    record["status"] = "completed" if result.returncode == 0 else "failed"
    if result.returncode != 0:
        record["error"] = result.stderr.strip() or result.stdout.strip()
    write_fault_record(record_path, record)

    if result.returncode != 0:
        print("[CPU Stress] 注入失败：")
        print(record.get("error") or "unknown error")
        return result.returncode

    print("[CPU Stress] 注入结束，容器中的负载进程已自动退出。")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n[CPU Stress] 用户中断。")
        raise SystemExit(130)
    except Exception as exc:  # noqa: BLE001
        print(f"[CPU Stress] 失败：{exc}", file=sys.stderr)
        raise SystemExit(1)
