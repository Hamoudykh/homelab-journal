"""Collect a point-in-time picture of the lab from Prometheus.

The agent is only as good as the context it is given, so this module is where
most of the real thinking lives. It turns a pile of PromQL into a compact text
report that a language model can reason about.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .prometheus import Alert, PrometheusClient, Target

# PromQL kept in one place so the queries are easy to read and tune.
QUERIES = {
    "cpu_busy_pct": '100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)',
    "memory_used_pct": "(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100",
    "root_disk_used_pct": '100 - (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"} * 100)',
    "uptime_seconds": "node_time_seconds - node_boot_time_seconds",
    "probe_up": "probe_success",
    "probe_latency_ms": "probe_duration_seconds * 1000",
    "gpu_util_pct": "nvidia_smi_utilization_gpu_ratio * 100",
    "gpu_vram_gb": "nvidia_smi_memory_used_bytes / 1024 / 1024 / 1024",
    "gpu_temp_c": "nvidia_smi_temperature_gpu",
    "gpu_power_w": "nvidia_smi_power_draw_watts",
}


@dataclass
class Snapshot:
    taken_at: datetime
    targets: list[Target] = field(default_factory=list)
    alerts: list[Alert] = field(default_factory=list)
    hosts: dict[str, dict[str, float]] = field(default_factory=dict)
    probes: dict[str, dict[str, float]] = field(default_factory=dict)
    gpu: dict[str, float] = field(default_factory=dict)

    @property
    def has_problems(self) -> bool:
        return bool(self.alerts) or any(not t.is_up for t in self.targets)

    def to_text(self) -> str:
        """Render the snapshot as the context block handed to the model."""
        lines: list[str] = []
        stamp = self.taken_at.strftime("%Y-%m-%d %H:%M:%S UTC")
        lines.append(f"LAB STATE AT {stamp}")

        lines.append("\n[SCRAPE TARGETS]")
        for t in sorted(self.targets, key=lambda x: (x.job, x.instance)):
            status = "UP" if t.is_up else "DOWN"
            line = f"  {t.job}/{t.instance}: {status}"
            if t.last_error:
                line += f" -- error: {t.last_error}"
            lines.append(line)

        lines.append("\n[REACHABILITY]")
        if not self.probes:
            lines.append("  (no ICMP probe data)")
        for instance, values in sorted(self.probes.items()):
            up = values.get("probe_up", 0.0)
            latency = values.get("probe_latency_ms")
            state = "reachable" if up == 1.0 else "UNREACHABLE"
            suffix = f", {latency:.2f} ms" if latency is not None else ""
            lines.append(f"  {instance}: {state}{suffix}")

        lines.append("\n[HOST RESOURCES]")
        if not self.hosts:
            lines.append("  (no node_exporter data)")
        for instance, values in sorted(self.hosts.items()):
            parts = []
            if "cpu_busy_pct" in values:
                parts.append(f"cpu {values['cpu_busy_pct']:.1f}%")
            if "memory_used_pct" in values:
                parts.append(f"mem {values['memory_used_pct']:.1f}%")
            if "root_disk_used_pct" in values:
                parts.append(f"disk / {values['root_disk_used_pct']:.1f}%")
            if "uptime_seconds" in values:
                parts.append(f"up {values['uptime_seconds'] / 3600:.1f}h")
            lines.append(f"  {instance}: " + ", ".join(parts))

        if self.gpu:
            lines.append("\n[GPU]")
            lines.append(
                "  util {util:.0f}%, vram {vram:.2f} GB, {temp:.0f} C, {power:.1f} W".format(
                    util=self.gpu.get("gpu_util_pct", 0.0),
                    vram=self.gpu.get("gpu_vram_gb", 0.0),
                    temp=self.gpu.get("gpu_temp_c", 0.0),
                    power=self.gpu.get("gpu_power_w", 0.0),
                )
            )

        lines.append("\n[FIRING ALERTS]")
        if not self.alerts:
            lines.append("  none")
        for a in self.alerts:
            lines.append(f"  {a.name} ({a.severity}, {a.state}): {a.summary}")

        return "\n".join(lines)


def collect(client: PrometheusClient) -> Snapshot:
    """Query Prometheus and assemble a Snapshot."""
    snap = Snapshot(taken_at=datetime.now(timezone.utc))

    snap.targets = client.targets()
    snap.alerts = client.firing_alerts()

    # Per-host resource metrics, keyed by the instance label.
    for name in ("cpu_busy_pct", "memory_used_pct", "root_disk_used_pct", "uptime_seconds"):
        for instance, value in client.labelled_values(QUERIES[name], "instance").items():
            snap.hosts.setdefault(instance, {})[name] = value

    # ICMP probe results, also keyed by instance.
    for name in ("probe_up", "probe_latency_ms"):
        for instance, value in client.labelled_values(QUERIES[name], "instance").items():
            snap.probes.setdefault(instance, {})[name] = value

    # GPU metrics are a single card, so a flat dict is enough.
    for name in ("gpu_util_pct", "gpu_vram_gb", "gpu_temp_c", "gpu_power_w"):
        value = client.scalar(QUERIES[name])
        if value is not None:
            snap.gpu[name] = value

    return snap
