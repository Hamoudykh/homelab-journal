# NetOps Agent

An LLM-assisted operations agent for the lab. It reads live telemetry from
Prometheus, reasons about it with a locally hosted model on the GPU node, and
reports to Telegram.

It is deliberately not a chatbot. It answers one question: *what is wrong, and
what should I check next?*

## Design

```
Prometheus  ──►  snapshot.py  ──►  agent.py  ──►  Ollama (GPU node)
(telemetry)      (context)         (prompting)     (reasoning)
                                        │
                                        └────────►  Telegram
```

| Module | Responsibility |
|---|---|
| `config.py` | Environment-driven settings. No secrets in the repo |
| `prometheus.py` | Thin client over the Prometheus HTTP API |
| `snapshot.py` | Turns PromQL results into a compact text picture of the lab |
| `llm.py` | Ollama client, returns text plus token timings |
| `notify.py` | Telegram delivery, silent no-op when unconfigured |
| `agent.py` | Orchestration and prompts |
| `__main__.py` | CLI and the Alertmanager webhook server |

The interesting part is `snapshot.py`. A model can only reason about what it is
given, so the quality of the context matters far more than the size of the model.

## Usage

```bash
pip install -r requirements.txt

python -m netops snapshot                  # raw context, no model involved
python -m netops health                    # model-written health assessment
python -m netops health --notify           # ...and send it to Telegram
python -m netops ask "why is latency to the router higher than everything else?"
python -m netops serve                     # listen for Alertmanager webhooks
```

`snapshot` is the one to reach for when debugging: it shows exactly what the
model will see, with no inference involved.

## Configuration

All optional; the defaults match the lab.

| Variable | Default |
|---|---|
| `PROMETHEUS_URL` | `http://192.168.1.12:9090` |
| `ALERTMANAGER_URL` | `http://192.168.1.12:9093` |
| `OLLAMA_URL` | `http://127.0.0.1:11434` |
| `OLLAMA_MODEL` | `llama3.1:8b` |
| `TELEGRAM_BOT_TOKEN` | unset — notifications disabled |
| `TELEGRAM_CHAT_ID` | unset — notifications disabled |

Telegram credentials are read from the environment only, never from a file in
this repository.

## Wiring it to Alertmanager

Run `python -m netops serve`, then add a webhook receiver on `mon01` so alerts
flow through the agent before reaching the phone:

```yaml
receivers:
  - name: netops-agent
    webhook_configs:
      - url: http://<agent-host>:9099/
```

## Scheduled health checks

`--only-if-broken` makes the agent silent when everything is fine, so it can run
on a timer without becoming noise:

```bash
python -m netops health --only-if-broken --notify
```
