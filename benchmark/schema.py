import pandas as pd
from .config import SERVICES, METRICS, FEATURE_NAMES, _REDIS_METRICS


METRIC_META = {
    "qps":           {"unit": "req/s",  "expected_min": 0,    "expected_max": 10000},
    "latency_p95":   {"unit": "ms",     "expected_min": 0,    "expected_max": 60000},
    "error_rate":    {"unit": "ratio",  "expected_min": 0,    "expected_max": 1},
    "cpu_usage":     {"unit": "cores",  "expected_min": 0,    "expected_max": 16},
    "memory_usage":  {"unit": "MiB",    "expected_min": 0,    "expected_max": 8192},
    "restart_count": {"unit": "count",  "expected_min": 0,    "expected_max": 100},
}


def build_feature_schema() -> pd.DataFrame:
    rows = []
    for svc in SERVICES:
        metrics = _REDIS_METRICS if svc == "redis-cart" else METRICS
        for met in metrics:
            fname = f"{svc}_{met}"
            meta = METRIC_META[met]
            rows.append({
                "feature_name":   fname,
                "service":        svc,
                "metric_type":    met,
                "unit":           meta["unit"],
                "source":         "prometheus",
                "model_input":    True,
                "expected_min":   meta["expected_min"],
                "expected_max":   meta["expected_max"],
            })
    df = pd.DataFrame(rows)
    assert len(df) == 63
    return df
