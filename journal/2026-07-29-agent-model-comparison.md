# 2026-07-29 — Building the NetOps agent, and what the models got wrong

**Goal:** an agent that reads live telemetry and answers "what is wrong and what should
I check next", rather than a chatbot.

Code: [`agent/`](../agent/). Runs against live Prometheus, reasons with a model on the GPU
node, reports to Telegram.

## Architecture

```
Prometheus  ──►  snapshot.py  ──►  agent.py  ──►  Ollama (GPU node)
(telemetry)      (context)         (prompting)     (reasoning)
                                        │
                                        └────────►  Telegram
```

Deliberately split into small modules with one responsibility each. The one that matters
most is `snapshot.py`: a model can only reason about what it is handed, so **context quality
dominates model size**. Most of the engineering effort went there, not into the prompt.

`python -m netops snapshot` prints that context with no model involved — which makes it the
first thing to check when an answer looks wrong. It separates "the agent reasoned badly" from
"the agent was given bad data", which are completely different bugs.

## Failure 1 — the agent inventing concerns

First run, `llama3.1:8b`, generic prompt:

> pve01's high CPU usage (0.3%) might be due to the node_exporter and blackbox_exporter
> running on it... Worth watching is pve01's disk usage (/ 12.2%), which might indicate a
> potential storage issue

Both wrong. 0.3% CPU is idle. A filesystem 12.2% full is nearly empty. The model quoted real
numbers and then manufactured concern about them, because nothing told it what *normal* is.

**Fix: put the baseline in the system prompt.** Explicit thresholds, plus the measured
baselines from the earlier latency work:

```
KNOWN-NORMAL BASELINE - these are healthy, do NOT report them as problems:
- CPU busy under 50% is idle to light. Only sustained load above 80% is notable.
- Filesystem under 80% used is fine. 12% used is nearly empty.
- Latency between lab machines is 0.2-0.7 ms...
- The ISP router normally answers in 1.2-1.6 ms, roughly five times slower. This is
  EXPECTED: consumer gateways deprioritise responding to ICMP. It is not congestion,
  packet loss, or a fault.
- Do NOT describe a value as high or concerning unless it crosses a threshold above.
  Quoting a number does not make it a problem.
```

This is why the earlier baseline work paid off twice. Knowing that the router answers in
~1.4 ms was useful to a human; it turned out to be **essential context for the model**.

After the fix, the same model correctly reported the lab healthy and stopped inventing
problems.

## Failure 2 — hallucinating a metric

The improved prompt fixed the false positives but exposed something worse. `llama3.1:8b`
reported:

> gpu-node (192.168.1.88) has a significantly higher latency than other lab machines at
> **8.84 ms**

The actual snapshot said **1.60 ms**. The figure 8.84 appears nowhere in the data. The model
invented it, despite an explicit instruction not to invent metrics.

Then, asked about the router, it answered:

> Latency to 192.168.1.1 is 8.84 ms, which is within the expected range of 1.2-1.6 ms

Which is self-contradictory *and* attributes one host's number to another.

**A fabricated metric is far more dangerous than a missed one.** An agent that stays quiet
gets ignored; an agent that confidently reports a number that does not exist sends you
chasing a fault that was never there. For operations work this is disqualifying.

## Model comparison

Same prompts, same context, same hardware (RTX 4070 Ti SUPER, 16 GB):

| | `llama3.1:8b` | `qwen2.5:14b` |
|---|---|---|
| Speed | ~102 tok/s | ~57 tok/s |
| VRAM | ~5.3 GB | ~9 GB |
| False positives after prompt fix | none | none |
| Hallucinated metrics | **yes** | no |
| Confused one host's data with another | **yes** | no |
| Router latency question | contradicted itself | correct and concise |

`qwen2.5:14b` on the same question:

> The latency to 192.168.1.1 is approximately 5 times higher because it is the ISP router,
> which typically deprioritizes responding to ICMP requests compared to internal network
> devices. This is expected behavior and not a problem.

Correct, sourced from the given context, no invention.

**Decision: `qwen2.5:14b` is now the default.** For an operations agent, being right matters
far more than being fast. Nobody needs a diagnosis in 1 second rather than 2.5 seconds; a
wrong diagnosis costs an hour.

## A real observation the monitoring caught

While pulling the 9 GB model, latency to the GPU node rose from its **0.62 ms baseline to
1.60 ms** — the download was saturating that link. The lab observed its own activity
degrading its own network, and the baseline is what made it visible.

That is exactly what network contention during model loading looks like in a real cluster,
in miniature.

## Lessons

- **Context beats model size.** The prompt fix improved output more than doubling parameters.
- **Baselines are agent infrastructure**, not just human documentation.
- **Test the context separately from the reasoning** — `snapshot` with no model was the tool
  that caught the hallucination.
- **Verify agent output against source data.** Trusting it because it is fluent is how you
  chase phantom faults.
- **Speed is the wrong optimisation target for ops.** Correctness wins.

## Open items

- [ ] Have the agent quote the exact metric values it is reasoning about, so hallucination is
      visible in the output itself
- [ ] Try a stronger API model on hard cases and compare against the local one
- [ ] Fault-injection test: unplug a cable, stop a service, and score the diagnosis against
      the known cause
- [ ] Wire to Alertmanager via the webhook receiver so real alerts flow through it
