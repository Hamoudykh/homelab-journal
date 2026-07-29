"""Thin client over the Prometheus and Alertmanager HTTP APIs.

Only the handful of endpoints the agent actually needs. Every call returns plain
Python structures so the rest of the code never touches HTTP.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


class PrometheusError(RuntimeError):
    """Raised when Prometheus is unreachable or returns a non-success status."""


@dataclass
class Target:
    job: str
    instance: str
    health: str
    last_error: str
    scrape_url: str

    @property
    def is_up(self) -> bool:
        return self.health == "up"


@dataclass
class Alert:
    name: str
    severity: str
    summary: str
    state: str
    instance: str


class PrometheusClient:
    def __init__(self, base_url: str, timeout: int = 10) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # --- low level -------------------------------------------------------

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url}{path}"
        try:
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise PrometheusError(f"{url} unreachable: {exc}") from exc

        payload = response.json()
        if payload.get("status") != "success":
            raise PrometheusError(f"{url} returned {payload.get('status')}")
        return payload["data"]

    # --- queries ---------------------------------------------------------

    def instant(self, expr: str) -> list[dict[str, Any]]:
        """Run an instant PromQL query and return its result vector."""
        data = self._get("/api/v1/query", {"query": expr})
        return data.get("result", [])

    def scalar(self, expr: str, default: float | None = None) -> float | None:
        """Run a query expected to yield a single number."""
        result = self.instant(expr)
        if not result:
            return default
        try:
            return float(result[0]["value"][1])
        except (KeyError, IndexError, ValueError):
            return default

    def labelled_values(self, expr: str, label: str) -> dict[str, float]:
        """Run a query and map one label to its value, e.g. instance -> 0.0."""
        out: dict[str, float] = {}
        for series in self.instant(expr):
            key = series.get("metric", {}).get(label)
            if key is None:
                continue
            try:
                out[key] = float(series["value"][1])
            except (KeyError, IndexError, ValueError):
                continue
        return out

    # --- state -----------------------------------------------------------

    def targets(self) -> list[Target]:
        data = self._get("/api/v1/targets")
        return [
            Target(
                job=t["labels"].get("job", "?"),
                instance=t["labels"].get("instance", "?"),
                health=t.get("health", "unknown"),
                last_error=t.get("lastError", ""),
                scrape_url=t.get("scrapeUrl", ""),
            )
            for t in data.get("activeTargets", [])
        ]

    def firing_alerts(self) -> list[Alert]:
        data = self._get("/api/v1/alerts")
        alerts = []
        for a in data.get("alerts", []):
            labels = a.get("labels", {})
            alerts.append(
                Alert(
                    name=labels.get("alertname", "?"),
                    severity=labels.get("severity", "none"),
                    summary=a.get("annotations", {}).get("summary", ""),
                    state=a.get("state", "?"),
                    instance=labels.get("instance", ""),
                )
            )
        return alerts
