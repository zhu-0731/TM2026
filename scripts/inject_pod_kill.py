"""Inject a reproducible Pod Kill fault and record its context."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_RECORD_PATH = "aiops_agent/output/last_fault_injection.json"


def run_command(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inject a Kubernetes Pod Kill fault")
    parser.add_argument("--service", default="redis-cart")
    parser.add_argument("--namespace", default="online-boutique")
    parser.add_argument("--label-key", default="app")
    parser.add_argument("--wait-seconds", type=int, default=60)
    parser.add_argument("--record-path", default=DEFAULT_RECORD_PATH)
    return parser


def get_pod_names(namespace: str, label_key: str, service: str) -> list[str]:
    result = run_command(
        [
            "kubectl",
            "get",
            "pods",
            "-n",
            namespace,
            "-l",
            f"{label_key}={service}",
            "-o",
            "json",
        ]
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "kubectl get pods failed")

    payload = json.loads(result.stdout)
    return [
        str(item.get("metadata", {}).get("name"))
        for item in payload.get("items", [])
        if item.get("metadata", {}).get("name")
    ]


def main() -> None:
    args = build_parser().parse_args()
    before = get_pod_names(args.namespace, args.label_key, args.service)
    if not before:
        raise RuntimeError(
            f"未找到服务 {args.service} 的 Pod，"
            f"请确认标签 {args.label_key}={args.service}"
        )

    target_pod = before[0]
    injected_at = datetime.now(timezone.utc)

    print(f"[故障注入] 目标服务：{args.service}")
    print(f"[故障注入] 删除 Pod：{target_pod}")

    result = run_command(
        ["kubectl", "delete", "pod", target_pod, "-n", args.namespace],
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "kubectl delete pod failed")

    print(result.stdout.strip())

    record = {
        "enabled": True,
        "type": "pod_kill",
        "target_service": args.service,
        "namespace": args.namespace,
        "target_pod": target_pod,
        "source": "scripts/inject_pod_kill.py",
        "injected_at": injected_at.isoformat(),
    }
    record_path = Path(args.record_path)
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[故障注入] 已记录故障上下文：{record_path}")

    deadline = time.time() + args.wait_seconds
    print("[故障注入] 等待控制器创建替代 Pod……")
    while time.time() < deadline:
        current = get_pod_names(args.namespace, args.label_key, args.service)
        replacements = [name for name in current if name != target_pod]
        if replacements:
            print(f"[故障注入] 已发现替代 Pod：{replacements[0]}")
            return
        time.sleep(2)

    print("[故障注入] 超时前未发现替代 Pod，请手动执行 kubectl get pods 检查。")


if __name__ == "__main__":
    main()
