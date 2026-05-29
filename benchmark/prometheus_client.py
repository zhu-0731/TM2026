"""Prometheus HTTP API client."""
from __future__ import annotations

import requests
import pandas as pd
from datetime import datetime, timezone
from typing import Optional


class PrometheusClient:
    def __init__(self, url: str = "http://localhost:9090"):
        self.url = url.rstrip("/")

    def query_range(
        self,
        query: str,
        start: datetime,
        end: datetime,
        step: int,
    ) -> Optional[pd.Series]:
        """
        Query Prometheus range API. Returns a Series indexed by UTC timestamp string,
        or None if no data returned.
        """
        params = {
            "query": query,
            "start": start.timestamp(),
            "end":   end.timestamp(),
            "step":  f"{step}s",
        }
        try:
            resp = requests.get(f"{self.url}/api/v1/query_range", params=params, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise RuntimeError(f"Prometheus query failed: {e}") from e

        data = resp.json()
        if data.get("status") != "success":
            raise RuntimeError(f"Prometheus returned non-success: {data.get('error', data)}")

        results = data.get("data", {}).get("result", [])
        if not results:
            return None

        # Take first result set (assumes single-series queries per feature)
        values = results[0].get("values", [])
        if not values:
            return None

        index = []
        vals = []
        for ts_epoch, val_str in values:
            ts = datetime.fromtimestamp(float(ts_epoch), tz=timezone.utc)
            index.append(ts.strftime("%Y-%m-%dT%H:%M:%SZ"))
            vals.append(float(val_str))

        return pd.Series(vals, index=index)

    def check_reachable(self) -> bool:
        try:
            resp = requests.get(f"{self.url}/-/healthy", timeout=5)
            return resp.status_code == 200
        except requests.RequestException:
            return False
