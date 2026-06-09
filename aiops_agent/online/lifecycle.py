"""Kubernetes Pod lifecycle snapshots and change detection for online diagnosis."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class PodRecord:
    name: str
    uid: str
    service: str
    phase: str
    ready: bool
    restart_count: int
    creation_timestamp: str
    deletion_timestamp: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "uid": self.uid,
            "service": self.service,
            "phase": self.phase,
            "ready": self.ready,
            "restart_count": self.restart_count,
            "creation_timestamp": self.creation_timestamp,
            "deletion_timestamp": self.deletion_timestamp,
        }


@dataclass
class PodSnapshot:
    captured_at: str
    pods: dict[str, PodRecord] = field(default_factory=dict)
    error: str | None = None


class KubernetesLifecycleWatcher:
    """Detect Pod deletion/recreation by comparing consecutive cluster snapshots."""

    def __init__(self, namespace: str = "online-boutique") -> None:
        self.namespace = namespace

    def capture(self) -> PodSnapshot:
        cmd = ["kubectl", "get", "pods", "-n", self.namespace, "-o", "json"]
        try:
            run = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return PodSnapshot(
                captured_at=datetime.now(timezone.utc).isoformat(),
                error=f"kubectl 执行失败：{exc}",
            )

        if run.returncode != 0:
            return PodSnapshot(
                captured_at=datetime.now(timezone.utc).isoformat(),
                error=run.stderr.strip() or "kubectl get pods 执行失败",
            )

        try:
            payload = json.loads(run.stdout)
        except json.JSONDecodeError as exc:
            return PodSnapshot(
                captured_at=datetime.now(timezone.utc).isoformat(),
                error=f"Pod JSON 解析失败：{exc}",
            )

        pods: dict[str, PodRecord] = {}
        for item in payload.get("items", []):
            metadata = item.get("metadata", {})
            status = item.get("status", {})
            name = str(metadata.get("name") or "")
            uid = str(metadata.get("uid") or "")
            if not name or not uid:
                continue

            labels = metadata.get("labels", {}) or {}
            service = self._service_name(labels, name)
            container_statuses = status.get("containerStatuses", []) or []
            ready = bool(container_statuses) and all(
                bool(container.get("ready")) for container in container_statuses
            )
            restart_count = sum(
                int(container.get("restartCount", 0) or 0)
                for container in container_statuses
            )
            pods[uid] = PodRecord(
                name=name,
                uid=uid,
                service=service,
                phase=str(status.get("phase") or "Unknown"),
                ready=ready,
                restart_count=restart_count,
                creation_timestamp=str(metadata.get("creationTimestamp") or ""),
                deletion_timestamp=metadata.get("deletionTimestamp"),
            )

        return PodSnapshot(
            captured_at=datetime.now(timezone.utc).isoformat(),
            pods=pods,
        )

    def compare(self, previous: PodSnapshot, current: PodSnapshot) -> dict[str, Any]:
        if previous.error or current.error:
            return {
                "triggered": False,
                "reason": current.error or previous.error,
                "events": [],
                "affected_services": [],
                "previous_capture": previous.captured_at,
                "current_capture": current.captured_at,
            }

        removed_uids = set(previous.pods) - set(current.pods)
        added_uids = set(current.pods) - set(previous.pods)
        removed = [previous.pods[uid] for uid in sorted(removed_uids)]
        added = [current.pods[uid] for uid in sorted(added_uids)]

        removed_by_service: dict[str, list[PodRecord]] = {}
        added_by_service: dict[str, list[PodRecord]] = {}
        for pod in removed:
            removed_by_service.setdefault(pod.service, []).append(pod)
        for pod in added:
            added_by_service.setdefault(pod.service, []).append(pod)

        events: list[dict[str, Any]] = []
        services = sorted(set(removed_by_service) | set(added_by_service))
        for service in services:
            old_pods = removed_by_service.get(service, [])
            new_pods = added_by_service.get(service, [])
            if old_pods and new_pods:
                event_type = "pod_recreated"
                explanation = f"{service} 的旧 Pod 消失并出现新 Pod，疑似 Pod Kill 或滚动重建。"
            elif old_pods:
                event_type = "pod_deleted"
                explanation = f"{service} 的 Pod 从集群快照中消失。"
            else:
                # 仅新增 Pod 通常发生在初始扩容，不单独作为故障触发。
                continue

            events.append(
                {
                    "event_type": event_type,
                    "service": service,
                    "detected_at": current.captured_at,
                    "removed_pods": [pod.to_dict() for pod in old_pods],
                    "added_pods": [pod.to_dict() for pod in new_pods],
                    "explanation": explanation,
                    "score": 20.0 if event_type == "pod_recreated" else 16.0,
                }
            )

        affected_services = sorted({event["service"] for event in events})
        reason = "；".join(event["explanation"] for event in events)
        return {
            "triggered": bool(events),
            "reason": reason or "Pod 快照未发现删除或重建变化。",
            "events": events,
            "affected_services": affected_services,
            "previous_capture": previous.captured_at,
            "current_capture": current.captured_at,
        }

    @staticmethod
    def _service_name(labels: dict[str, Any], pod_name: str) -> str:
        for key in (
            "app",
            "app.kubernetes.io/name",
            "k8s-app",
            "component",
        ):
            value = labels.get(key)
            if value:
                return str(value)

        # Online Boutique Pod 通常为 service-name-<hash>-<suffix>。
        parts = pod_name.split("-")
        if len(parts) >= 3:
            return "-".join(parts[:-2])
        return pod_name
