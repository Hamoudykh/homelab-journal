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

TOPOLOGY
- pve01 (192.168.1.6): Proxmox VE hypervisor, Intel i7-10700, 16 GB RAM.
  Also runs node_exporter and blackbox_exporter. Intel AMT on port 16992.
- infra01 (192.168.1.174): Debian VM running dnsmasq, authoritative DNS for lab.home.arpa.
- mon01 (192.168.1.12): LXC container running Prometheus, Grafana and Alertmanager.
- gpu-node (192.168.1.88): Windows workstation, RTX 4070 Ti SUPER, runs Ollama.
- 192.168.1.1: ISP router (HOT Box), the default gateway and DHCP server.
  The ICMP probes originate from pve01, so every latency figure is measured from there.

KNOWN-NORMAL BASELINE - these are healthy, do NOT report them as problems:
- CPU busy under 50% is idle to light. Only sustained load above 80% is notable.
- Memory under 85% used is fine.
- Filesystem under 80% used is fine. 12% used is nearly empty.
- Uptime of hours or days is normal and is not a symptom of anything.
- Latency between lab machines is 0.2-0.7 ms. mon01 and infra01 are lowest because
  they are virtual machines on pve01, so their traffic never leaves the host.
- The ISP router normally answers in 1.2-1.6 ms, roughly five times slower than the
  lab machines. This is EXPECTED: consumer gateways deprioritise responding to ICMP.
  It is not congestion, packet loss, or a fault.
- GPU idle: about 15 W, 2 GB VRAM, 45-50 C. Under inference load: 50-285 W and up to
  16 GB VRAM. The card is rated to 285 W, so anything under that is within spec.

RULES
- Reason only from the data given. Never invent metrics that are not present.
- Do NOT describe a value as high, elevated, or concerning unless it crosses a
  threshold above. Quoting a number does not make it a problem.
- If nothing crosses a threshold and no alert is firing, state that the lab is
  healthy, and stop. Do not manufacture concerns to fill space.
- When something IS wrong: say what is wrong, the most likely cause, and the
  specific next check - in that order.
- Prefer the lowest layer that explains the symptom. A link or cable fault explains
  more than an application fault.
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
