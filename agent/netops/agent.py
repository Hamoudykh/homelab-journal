"""The agent itself: gather context, ask the model, report the answer."""

from __future__ import annotations

from dataclasses import dataclass

from .config import Config
from .llm import Completion, LLMError, OllamaClient
from .notify import TelegramNotifier
from .prometheus import PrometheusClient, PrometheusError
from .snapshot import Snapshot, collect

SYSTEM_PROMPT = """You are a network and infrastructure operations assistant for a small
home data centre lab. You are given a factual snapshot of monitoring data.

The lab consists of:
- pve01 (192.168.1.6): Proxmox VE hypervisor, Intel i7-10700, 16 GB RAM.
  Also runs node_exporter and blackbox_exporter. Intel AMT on port 16992.
- infra01 (192.168.1.174): Debian VM running dnsmasq, authoritative DNS for lab.home.arpa.
- mon01 (192.168.1.12): LXC container running Prometheus, Grafana and Alertmanager.
- gpu-node (192.168.1.88): Windows workstation, RTX 4070 Ti SUPER, runs Ollama.
- 192.168.1.1: ISP router (HOT Box), the default gateway and DHCP server.

Rules:
- Reason only from the data given. Never invent metrics that are not present.
- If something is wrong, say what is wrong, what the most likely cause is, and
  what to check next - in that order.
- Prefer the lowest layer that explains the symptom. A cable or link problem
  explains more than an application problem.
- If everything is healthy, say so briefly and name anything worth watching.
- Be concise. No preamble, no restating the question."""

HEALTH_PROMPT = """Assess the health of the lab from this snapshot.

{snapshot}

Give: a one-line overall verdict, then any problems found with likely cause and
next check, then anything worth watching. Keep it under 200 words."""

ALERT_PROMPT = """An alert has fired in the lab.

ALERT: {alert_name}
SEVERITY: {severity}
SUMMARY: {summary}

Current monitoring snapshot:

{snapshot}

Diagnose it: what is most likely happening, why, and the specific next command
or check to confirm. Under 200 words."""


@dataclass
class Diagnosis:
    snapshot: Snapshot
    completion: Completion

    def as_report(self) -> str:
        c = self.completion
        return (
            f"{c.text}\n\n"
            f"-- {c.tokens} tokens in {c.seconds:.1f}s "
            f"({c.tokens_per_second:.1f} tok/s)"
        )


class NetOpsAgent:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.prometheus = PrometheusClient(config.prometheus_url, config.request_timeout)
        self.llm = OllamaClient(config.ollama_url, config.ollama_model, config.llm_timeout)
        self.notifier = TelegramNotifier(config.telegram_token, config.telegram_chat_id)

    def snapshot(self) -> Snapshot:
        return collect(self.prometheus)

    def health_check(self, snapshot: Snapshot | None = None) -> Diagnosis:
        snap = snapshot or self.snapshot()
        completion = self.llm.complete(
            system=SYSTEM_PROMPT,
            prompt=HEALTH_PROMPT.format(snapshot=snap.to_text()),
        )
        return Diagnosis(snapshot=snap, completion=completion)

    def diagnose_alert(self, name: str, severity: str, summary: str) -> Diagnosis:
        snap = self.snapshot()
        completion = self.llm.complete(
            system=SYSTEM_PROMPT,
            prompt=ALERT_PROMPT.format(
                alert_name=name,
                severity=severity,
                summary=summary,
                snapshot=snap.to_text(),
            ),
        )
        return Diagnosis(snapshot=snap, completion=completion)

    def ask(self, question: str) -> Diagnosis:
        snap = self.snapshot()
        prompt = f"{snap.to_text()}\n\nQuestion: {question}"
        completion = self.llm.complete(system=SYSTEM_PROMPT, prompt=prompt)
        return Diagnosis(snapshot=snap, completion=completion)

    def notify(self, text: str) -> bool:
        return self.notifier.send(text)


__all__ = [
    "NetOpsAgent",
    "Diagnosis",
    "PrometheusError",
    "LLMError",
]
