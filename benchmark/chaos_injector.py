"""
ChaosMesh experiment lifecycle manager.
Applies experiments, monitors status, records precise timestamps,
returns IncidentConfig list for dataset labeling.
"""
from __future__ import annotations

import sys
import time
import json
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class InjectionResult:
    incident_id: str
    fault_type: str
    target_service: str
    root_cause_service: str
    severity: str
    injection_start: datetime
    injection_end: datetime
    effect_start: datetime     # injection_start + propagation_delay
    effect_end: datetime
    recovery_end: datetime
    root_cause_dims: list[str]
    secondary_dims: list[str]
    experiment_name: str
    experiment_kind: str
    success: bool
    error: str = ""


# Fault definitions: maps fault_type → (experiment yaml, metadata)
FAULT_DEFINITIONS: dict[str, dict] = {
    "cpu_stress": {
        "yaml": "deploy/chaos/inc001_cpu_stress_recommendationservice.yaml",
        "kind": "StressChaos",
        "name": "inc001-cpu-stress-recommendationservice",
        "target_service": "recommendationservice",
        "root_cause_service": "recommendationservice",
        "severity": "high",
        "propagation_delay_sec": 5,   # seconds after injection before effect visible
        "recovery_buffer_sec": 30,    # seconds after experiment ends for recovery
        "root_cause_dims": [
            "recommendationservice_cpu_usage",
            "recommendationservice_latency_p95",
        ],
        "secondary_dims": ["frontend_latency_p95"],
    },
    "pod_kill": {
        "yaml": "deploy/chaos/inc002_pod_kill_cartservice.yaml",
        "kind": "PodChaos",
        "name": "inc002-pod-kill-cartservice",
        "target_service": "cartservice",
        "root_cause_service": "cartservice",
        "severity": "critical",
        "propagation_delay_sec": 5,
        "recovery_buffer_sec": 60,    # pod needs time to restart
        "root_cause_dims": [
            "cartservice_restart_count",
            "cartservice_error_rate",
            "cartservice_qps",
        ],
        "secondary_dims": ["frontend_error_rate"],
    },
    "network_delay": {
        "yaml": "deploy/chaos/inc003_network_delay_frontend.yaml",
        "kind": "NetworkChaos",
        "name": "inc003-network-delay-frontend",
        "target_service": "frontend",
        "root_cause_service": "frontend",
        "severity": "medium",
        "propagation_delay_sec": 3,
        "recovery_buffer_sec": 20,
        "root_cause_dims": [
            "frontend_latency_p95",
            "frontend_error_rate",
        ],
        "secondary_dims": [
            "checkoutservice_latency_p95",
            "cartservice_latency_p95",
        ],
    },
}

# Fault duration must match the `duration` field in the YAML
FAULT_DURATION_SEC = 60


def _kubectl(args: list[str], namespace: str = "online-boutique") -> tuple[int, str, str]:
    cmd = ["kubectl", "-n", namespace] + args
    result = subprocess.run(cmd, capture_output=True, text=True,
                            env={"DOCKER_HOST": "npipe:////./pipe/docker_engine",
                                 **__import__("os").environ})
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def apply_experiment(yaml_path: Path, dry_run: bool = False) -> tuple[bool, str]:
    """Apply a ChaosMesh experiment YAML. Returns (success, error_msg)."""
    if dry_run:
        print(f"  [dry-run] would apply: {yaml_path}")
        return True, ""
    rc, out, err = _kubectl(["apply", "-f", str(yaml_path)])
    if rc != 0:
        return False, err
    return True, ""


def delete_experiment(kind: str, name: str, dry_run: bool = False) -> None:
    """Delete a ChaosMesh experiment (stops the fault immediately)."""
    if dry_run:
        print(f"  [dry-run] would delete: {kind}/{name}")
        return
    _kubectl(["delete", kind.lower(), name, "--ignore-not-found=true"])


def wait_for_experiment_running(kind: str, name: str, timeout_sec: int = 30) -> bool:
    """Wait until experiment phase = Running."""
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        rc, out, _ = _kubectl(["get", kind.lower(), name,
                                "-o", "jsonpath={.status.conditions[?(@.type==\"AllRecovered\")].status}"])
        # For new experiments, AllRecovered is False = experiment is active
        # Also check for Running phase
        rc2, phase, _ = _kubectl(["get", kind.lower(), name,
                                   "-o", "jsonpath={.status.experiment.desiredPhase}"])
        if rc2 == 0 and phase in ("Run", "run"):
            return True
        # Simpler check: experiment exists and has injection records
        rc3, inj, _ = _kubectl(["get", kind.lower(), name,
                                 "-o", "jsonpath={.status.experiment.containerRecords}"])
        if rc3 == 0 and inj and inj != "null":
            return True
        time.sleep(2)
    return False  # Timeout — experiment may still be running


def run_injection(
    fault_type: str,
    incident_id: str,
    project_root: Path,
    dry_run: bool = False,
) -> InjectionResult:
    """
    Apply one ChaosMesh experiment, wait for FAULT_DURATION_SEC, then clean up.
    Returns precise timestamps for dataset labeling.
    """
    defn = FAULT_DEFINITIONS[fault_type]
    yaml_path = project_root / defn["yaml"]

    print(f"  [{incident_id}] Applying {defn['kind']}: {defn['name']}")
    injection_start = _now()

    ok, err = apply_experiment(yaml_path, dry_run=dry_run)
    if not ok:
        print(f"  [{incident_id}] ERROR applying experiment: {err}", file=sys.stderr)
        return InjectionResult(
            incident_id=incident_id, fault_type=fault_type,
            target_service=defn["target_service"],
            root_cause_service=defn["root_cause_service"],
            severity=defn["severity"],
            injection_start=injection_start, injection_end=injection_start,
            effect_start=injection_start, effect_end=injection_start,
            recovery_end=injection_start,
            root_cause_dims=defn["root_cause_dims"],
            secondary_dims=defn["secondary_dims"],
            experiment_name=defn["name"], experiment_kind=defn["kind"],
            success=False, error=err,
        )

    print(f"  [{incident_id}] Experiment applied at {_ts(injection_start)}")

    if not dry_run:
        # Wait for controller to process and confirm running
        time.sleep(3)
        running = wait_for_experiment_running(defn["kind"], defn["name"])
        if not running:
            # Fail hard — do not silently continue with unconfirmed injection
            err_msg = (f"ChaosMesh experiment {defn['kind']}/{defn['name']} "
                       f"did not reach Running state within timeout")
            print(f"  [{incident_id}] ERROR: {err_msg}", file=sys.stderr)
            delete_experiment(defn["kind"], defn["name"])
            return InjectionResult(
                incident_id=incident_id, fault_type=fault_type,
                target_service=defn["target_service"],
                root_cause_service=defn["root_cause_service"],
                severity=defn["severity"],
                injection_start=injection_start, injection_end=injection_start,
                effect_start=injection_start, effect_end=injection_start,
                recovery_end=injection_start,
                root_cause_dims=defn["root_cause_dims"],
                secondary_dims=defn["secondary_dims"],
                experiment_name=defn["name"], experiment_kind=defn["kind"],
                success=False, error=err_msg,
            )

    effect_start = injection_start + timedelta(seconds=defn["propagation_delay_sec"])

    # Wait for fault duration
    print(f"  [{incident_id}] Fault active — waiting {FAULT_DURATION_SEC}s ...")
    if not dry_run:
        time.sleep(FAULT_DURATION_SEC)

    injection_end = _now()
    effect_end = injection_end

    # Clean up experiment
    print(f"  [{incident_id}] Cleaning up experiment ...")
    delete_experiment(defn["kind"], defn["name"], dry_run=dry_run)

    recovery_end = injection_end + timedelta(seconds=defn["recovery_buffer_sec"])
    if not dry_run:
        print(f"  [{incident_id}] Waiting {defn['recovery_buffer_sec']}s for recovery ...")
        time.sleep(defn["recovery_buffer_sec"])

    print(f"  [{incident_id}] Done. effect_window: {_ts(effect_start)} → {_ts(effect_end)}")

    return InjectionResult(
        incident_id=incident_id,
        fault_type=fault_type,
        target_service=defn["target_service"],
        root_cause_service=defn["root_cause_service"],
        severity=defn["severity"],
        injection_start=injection_start,
        injection_end=injection_end,
        effect_start=effect_start,
        effect_end=effect_end,
        recovery_end=recovery_end,
        root_cause_dims=defn["root_cause_dims"],
        secondary_dims=defn["secondary_dims"],
        experiment_name=defn["name"],
        experiment_kind=defn["kind"],
        success=True,
    )


def results_to_mock_incidents(results: list[InjectionResult]) -> list:
    """Convert InjectionResult list to MockIncident objects, preserving real timestamps."""
    from .mock_data import MockIncident
    incs = []
    for r in results:
        if not r.success:
            continue
        incs.append(MockIncident(
            incident_id=r.incident_id,
            fault_type=r.fault_type,
            target_service=r.target_service,
            root_cause_service=r.root_cause_service,
            severity=r.severity,
            duration_sec=FAULT_DURATION_SEC,
            effect_start=r.effect_start,
            effect_end=r.effect_end,
            root_cause_dims=r.root_cause_dims,
            secondary_dims=r.secondary_dims,
            # Preserve real ChaosMesh timestamps (distinct from effect times)
            injection_start=r.injection_start,
            injection_end=r.injection_end,
            recovery_end=r.recovery_end,
        ))
    return incs
