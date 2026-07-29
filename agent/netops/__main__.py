"""Command line entry point.

    python -m netops snapshot          print raw lab state, no model involved
    python -m netops health            ask the model for a health assessment
    python -m netops ask "question"    ask a free-form question about the lab
    python -m netops serve             listen for Alertmanager webhooks
"""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import __version__, config
from .agent import LLMError, NetOpsAgent, PrometheusError


def _build_agent() -> NetOpsAgent:
    return NetOpsAgent(config.load())


# --- commands ------------------------------------------------------------


def cmd_snapshot(args: argparse.Namespace) -> int:
    """No model, no network beyond Prometheus. Useful for checking context."""
    agent = _build_agent()
    print(agent.snapshot().to_text())
    return 0


def cmd_health(args: argparse.Namespace) -> int:
    agent = _build_agent()
    snap = agent.snapshot()

    if args.only_if_broken and not snap.has_problems:
        print("Everything healthy, nothing to report.")
        return 0

    diagnosis = agent.health_check(snap)
    print(diagnosis.as_report())

    if args.notify:
        sent = agent.notify(f"Lab health check\n\n{diagnosis.completion.text}")
        print("sent to telegram" if sent else "telegram not configured")
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    agent = _build_agent()
    diagnosis = agent.ask(args.question)
    print(diagnosis.as_report())
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    """Receive Alertmanager webhooks, diagnose each alert, forward to Telegram."""
    agent = _build_agent()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *log_args) -> None:  # quieter default logging
            print(f"[webhook] {fmt % log_args}")

        def do_POST(self) -> None:  # noqa: N802 - name required by BaseHTTPRequestHandler
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"

            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                print("[webhook] ignoring non-JSON body")
                return

            for alert in payload.get("alerts", []):
                labels = alert.get("labels", {})
                name = labels.get("alertname", "unknown")
                severity = labels.get("severity", "none")
                summary = alert.get("annotations", {}).get("summary", "")
                status = alert.get("status", "firing")

                if status != "firing":
                    print(f"[webhook] {name} resolved, skipping analysis")
                    continue

                print(f"[webhook] diagnosing {name} ({severity})")
                try:
                    diagnosis = agent.diagnose_alert(name, severity, summary)
                except (PrometheusError, LLMError) as exc:
                    print(f"[webhook] diagnosis failed: {exc}")
                    agent.notify(f"ALERT {name}\n{summary}\n\n(agent unavailable: {exc})")
                    continue

                message = f"ALERT: {name} [{severity}]\n{summary}\n\n{diagnosis.completion.text}"
                agent.notify(message)
                print(f"[webhook] {name} handled in {diagnosis.completion.seconds:.1f}s")

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"netops agent listening on http://{args.host}:{args.port}/  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping")
    finally:
        server.server_close()
    return 0


# --- wiring --------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="netops", description="LLM-assisted NetOps agent")
    parser.add_argument("--version", action="version", version=f"netops {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("snapshot", help="print the raw lab state").set_defaults(func=cmd_snapshot)

    p_health = sub.add_parser("health", help="model-written health assessment")
    p_health.add_argument("--notify", action="store_true", help="also send to Telegram")
    p_health.add_argument(
        "--only-if-broken",
        action="store_true",
        help="stay silent when nothing is wrong (for scheduled runs)",
    )
    p_health.set_defaults(func=cmd_health)

    p_ask = sub.add_parser("ask", help="ask a question about the lab")
    p_ask.add_argument("question")
    p_ask.set_defaults(func=cmd_ask)

    p_serve = sub.add_parser("serve", help="listen for Alertmanager webhooks")
    p_serve.add_argument("--host", default="0.0.0.0")
    p_serve.add_argument("--port", type=int, default=9099)
    p_serve.set_defaults(func=cmd_serve)

    args = parser.parse_args(argv)

    try:
        return args.func(args)
    except PrometheusError as exc:
        print(f"Prometheus problem: {exc}", file=sys.stderr)
        return 2
    except LLMError as exc:
        print(f"Model problem: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
