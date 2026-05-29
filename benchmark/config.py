from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import yaml


SERVICES = [
    "frontend", "cartservice", "checkoutservice", "currencyservice",
    "emailservice", "paymentservice", "productcatalogservice",
    "recommendationservice", "shippingservice", "adservice", "redis-cart",
]

METRICS = ["qps", "latency_p95", "error_rate", "cpu_usage", "memory_usage", "restart_count"]

# redis-cart uses TCP/Redis protocol — Istio has no HTTP metrics for it.
# Only cpu_usage, memory_usage, restart_count are available.
_REDIS_METRICS = ["cpu_usage", "memory_usage", "restart_count"]

FEATURE_NAMES = (
    [f"{svc}_{met}" for svc in SERVICES[:-1] for met in METRICS]
    + [f"redis-cart_{met}" for met in _REDIS_METRICS]
)

assert len(FEATURE_NAMES) == 63


@dataclass
class IncidentConfig:
    incident_id: str
    fault_type: str
    target_service: str
    root_cause_service: str
    severity: str
    duration_sec: int
    root_cause_dims: list[str]
    secondary_dims: list[str]


@dataclass
class ExportConfig:
    output_dir: Path
    step_seconds: int = 5
    duration_minutes: int = 10
    prometheus_url: str = "http://localhost:9090"
    lookback_minutes: int = 10
    mode: str = "smoke"
    train_ratio: float = 0.5
    valid_ratio: float = 0.2
    # test_ratio is implicit: 1 - train - valid = 0.3

    def load_incidents_from_yaml(self, path: Path) -> list[IncidentConfig]:
        if not path.exists():
            return []
        with open(path) as f:
            data = yaml.safe_load(f)
        result = []
        for inc in data.get("incidents", []):
            result.append(IncidentConfig(**inc))
        return result
