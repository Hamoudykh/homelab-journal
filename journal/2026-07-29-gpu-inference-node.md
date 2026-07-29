# 2026-07-29 — GPU inference node and GPU telemetry

**Goal:** run real AI workloads in the lab, and monitor the thing that actually matters in an
AI data centre — GPU utilisation, memory, thermals, and power draw.

## Heterogeneous lab, on purpose

The lab now has two very different machines, and the split mirrors real AI infrastructure:

| Role | Machine | Why |
|---|---|---|
| **Control plane** | `pve01` — i7-10700, 16 GB, no GPU | Always on. Runs services, monitoring, orchestration. Cheap to leave running |
| **GPU node** | `MUHAMMAD` — i9-14900KF, 48 GB, RTX 4070 Ti SUPER 16 GB | Where inference runs, because that is where the accelerator is |

That is the same division as a real cluster: control plane on modest always-on hardware,
compute on expensive accelerators that are scheduled rather than idle.

**Two honest constraints**, both genuine learning material: the GPU node is not always on, and
gaming competes for the GPU. Contention for scarce accelerators is *the* defining operational
problem in AI infrastructure.

## Ollama

Installed as the **standalone zip** rather than the installer — extracted to
`%LOCALAPPDATA%\Programs\Ollama`, so no administrator rights were needed. (The MSI route had
already failed at 1603 for exactly that reason.)

Configuration, set as persistent user environment variables:

| Variable | Value | Why |
|---|---|---|
| `OLLAMA_HOST` | `0.0.0.0:11434` | Listen on the LAN so `pve01` can call it, not just localhost |
| `OLLAMA_KEEP_ALIVE` | `5m` | Unload the model from VRAM after 5 minutes idle, so gaming is unaffected |

Model: `llama3.1:8b` (4.9 GB on disk, 5.3 GB resident).

## Measured performance

```
NAME           SIZE      PROCESSOR    CONTEXT
llama3.1:8b    5.3 GB    100% GPU     4096
```

| Measurement | Result |
|---|---|
| First request (cold) | 22.9 tok/s |
| Subsequent (model resident) | **103.8 tok/s** |

The gap is entirely **model load time** — roughly 25 seconds to move 5 GB into VRAM. The cold
number is not the model being slow; it is the storage-to-VRAM transfer being counted in the
average.

This matters operationally and is worth internalising: in a real serving environment, cold
starts dominate tail latency, which is why production inference keeps models resident and why
`KEEP_ALIVE` is a real tuning decision rather than a detail.

## GPU telemetry

`nvidia_gpu_exporter` v1.13.1 (utkuozdemir), extracted to
`%LOCALAPPDATA%\Programs\nvidia_gpu_exporter`, listening on **:9835**. It shells out to
`nvidia-smi` and exposes the results in Prometheus format.

Idle versus loaded, same GPU:

| Metric | Idle | Model resident |
|---|---|---|
| VRAM used | 2.19 GB | 7.69 GB |
| Power draw | 14.7 W | 56.8 W (sampled) |
| Temperature | 49 °C | 49 °C |

**This is the on-thesis part.** AI data centres are designed around exactly these numbers —
power per rack and the heat that follows from it. A 4070 Ti SUPER is rated to 285 W; a rack of
H100s is 700 W *each*. Watching a single GPU's draw swing from 15 W to 57 W just by loading a
model is the same phenomenon that forces liquid cooling and 100 kW racks at scale.

## Blocked: Windows Firewall

Windows silently created **inbound block rules** for both `ollama.exe` and
`nvidia_gpu_exporter.exe` — standard behaviour when a non-elevated process starts listening.
So `mon01` cannot scrape either yet.

Fixing it needs administrator rights. In an **elevated** PowerShell on the GPU node:

```powershell
Get-NetFirewallRule | Where-Object { $_.DisplayName -in 'ollama.exe','nvidia_gpu_exporter.exe' } | Remove-NetFirewallRule
New-NetFirewallRule -DisplayName "Ollama LAN" -Direction Inbound -Protocol TCP -LocalPort 11434 -RemoteAddress 192.168.1.0/24 -Action Allow
New-NetFirewallRule -DisplayName "NVIDIA GPU exporter LAN" -Direction Inbound -Protocol TCP -LocalPort 9835 -RemoteAddress 192.168.1.0/24 -Action Allow
```

Removing the block rules first is not optional — **in Windows Firewall a block rule beats an
allow rule**, so adding an allow while the auto-created block still exists changes nothing.

`-RemoteAddress 192.168.1.0/24` restricts both to the LAN. Neither service should ever be
reachable from the internet: Ollama has no authentication whatsoever.

## Then add to Prometheus

On `mon01`, append to `/etc/prometheus/prometheus.yml`:

```yaml
  - job_name: gpu
    static_configs:
      - targets: ['192.168.1.88:9835']
        labels:
          instance: gpu-node
```

## Persistence

Both services have shortcuts in the user's Startup folder, so they come back after a reboot.
Not as robust as a Windows service (which would need admin and would run without a login), but
adequate for a workstation.

## Open items

- [ ] Firewall rules (needs an elevated shell at the machine)
- [ ] Prometheus scrape job for the GPU exporter
- [ ] Grafana dashboard: GPU utilisation, VRAM, temperature, power draw
- [ ] Static lease for the GPU node so `192.168.1.88` cannot move
- [ ] DNS record `gpu01.lab.home.arpa`
- [ ] The NetOps agent: consume Prometheus + Alertmanager, reason with the local model, report
      diagnoses to Telegram
- [ ] Measure tokens/sec per watt — a genuinely data-centre-shaped metric
