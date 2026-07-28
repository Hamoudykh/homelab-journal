# 2026-07-28 — Monitoring: Prometheus and Grafana on mon01

**Goal:** make the lab report on itself instead of having to go and look.

**Outcome:** Prometheus scraping `pve01`, Grafana graphing it, on a container called `mon01`.

## Container instead of a VM

`mon01` is an **LXC container** (CT 101), not a VM. Both give an isolated Debian system, but:

- A **VM** emulates hardware and boots its own kernel. Strong isolation, but it costs RAM and
  a full boot cycle, and installing Debian takes ~15 minutes.
- A **container** shares the host's kernel and is just isolated processes and filesystem. It
  is created from a template in about 30 seconds and uses noticeably less RAM.

With 16 GB on this host, that overhead matters. Containers are also worth knowing in their
own right — they are what almost all modern application infrastructure runs on.

Created with:

```bash
pveam update
pveam download local debian-13-standard_13.6-1_amd64.tar.zst
pct create 101 local:vztmpl/debian-13-standard_13.6-1_amd64.tar.zst \
  --hostname mon01 --cores 2 --memory 4096 --swap 512 \
  --rootfs local-lvm:32 --net0 name=eth0,bridge=vmbr0,ip=dhcp \
  --nameserver 192.168.1.174 --searchdomain lab.home.arpa \
  --unprivileged 1 --onboot 1 --password
```

`pct create` warned *"Systemd 257 detected. You may need to enable nesting."* — modern systemd
inside an unprivileged container needs it. Fixed with `pct set 101 --features nesting=1`.

## The three pieces

**node_exporter** on `pve01` — reads CPU, memory, disk, and network statistics from the
kernel and publishes them as plain text over HTTP on port 9100. It stores nothing.

**Prometheus** on `mon01` — fetches ("scrapes") that endpoint every 15 seconds and stores the
numbers in a time-series database. This is the component that remembers.

**Grafana** on `mon01` — queries Prometheus and draws the graphs. It stores no metrics itself.

Collection, storage, and display are three separate jobs done by three separate programs.
That separation is why any of them can be swapped independently.

`/etc/prometheus/prometheus.yml`:

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: prometheus
    static_configs:
      - targets: ['localhost:9090']

  - job_name: node
    static_configs:
      - targets: ['pve01.lab.home.arpa:9100']
        labels:
          instance: pve01
```

The scrape target is a **name, not an IP** — the first practical payoff from building DNS
first. If pve01's address ever changes, this file does not.

## Gotcha 1 — DHCP overwrote the container's DNS

The scrape failed immediately:

```
Get "http://pve01.lab.home.arpa:9100/metrics": dial tcp:
lookup pve01.lab.home.arpa on 213.57.2.5:53: no such host
```

`213.57.2.5` is the ISP's resolver — not infra01. The `--nameserver` given at creation was
being overwritten at boot by the container's own DHCP client rewriting `/etc/resolv.conf`.

Fixed by switching the container to a static address, which is what a server should have
anyway:

```bash
pct set 101 --net0 name=eth0,bridge=vmbr0,ip=192.168.1.12/24,gw=192.168.1.1 \
  --nameserver 192.168.1.174 --searchdomain lab.home.arpa
pct reboot 101
```

Worth noting how good that error message was: it named the exact resolver that was queried.
Reading the error precisely pointed straight at the cause.

## Gotcha 2 — the dashboard's Instance selector

Dashboard 1860 ("Node Exporter Full") imported but every panel read `N/A` / `No data`.

Cause: the dashboard's **Instance** variable defaulted to `localhost:9090` — Prometheus
scraping *itself*, which produces no node metrics. Selecting `pve01` filled everything in.

The `instance` label is set explicitly in the scrape config, so it reads as `pve01` rather
than `192.168.1.6:9100`. Cleaner in dashboards, but it means knowing which value to select.

## Result

Live on `pve01`: CPU busy, load, RAM used, swap, root filesystem usage, per-interface network
throughput (including the `vmbr0` bridge and each VM's virtual interface), and uptime.

## Access

| Service | URL |
|---|---|
| Grafana | `http://192.168.1.12:3000` |
| Prometheus | `http://192.168.1.12:9090` |
| node_exporter | `http://192.168.1.6:9100/metrics` |

## Network probing with blackbox_exporter

`node_exporter` only reports on machines that run it. To monitor *everything* on the network
— including a router that will never run an agent — the tool is **blackbox_exporter**, which
probes devices from the outside (ICMP, TCP, HTTP) and reports whether they answered and how
long it took.

Installed on **pve01**, not mon01. That was originally a mistake, but it is the better
location: ICMP needs raw sockets, which are restricted inside an unprivileged container and
unrestricted on the host.

Prometheus scrape job — note this one is not a plain target list. Prometheus asks
blackbox_exporter to probe *something else*, so the target has to be rewritten into a query
parameter:

```yaml
  - job_name: ping
    metrics_path: /probe
    params:
      module: [icmp]
    static_configs:
      - targets:
          - 192.168.1.1
          - 192.168.1.6
          - 192.168.1.12
          - 192.168.1.174
          - 192.168.1.88
    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target      # the device to probe
      - source_labels: [__param_target]
        target_label: instance            # label the result with the device
      - target_label: __address__
        replacement: pve01.lab.home.arpa:9115   # who to actually ask
```

Those three relabel rules are the pattern for every blackbox job: move the real target into
`__param_target`, keep it as the `instance` label so graphs are readable, then point the
actual scrape at the exporter.

## Dashboard

`dashboards/network-overview.json` in this repo — imported via Grafana's *Import → Upload
JSON*. Four panels: device up/down tiles, ping latency, availability percentage over 6h, and
per-interface throughput on pve01.

Keeping the dashboard **in Git** rather than only inside Grafana means it is versioned,
reviewable, and reproducible on a fresh install.

### Baseline observed

| Device | Mean latency |
|---|---|
| 192.168.1.1 (router) | 1.52 ms |
| 192.168.1.88 (PC) | 0.583 ms |
| 192.168.1.174 (infra01) | 0.426 ms |
| 192.168.1.12 (mon01) | 0.215 ms |
| 192.168.1.6 (pve01) | 0.207 ms |

The router is roughly seven times slower to answer than anything else — consumer gateways
deprioritise responding to pings. mon01 and infra01 are fast because they are on the same
physical host as the prober; traffic never leaves the machine.

**The value of a baseline is knowing what normal looks like.** If the router later answers at
50 ms, that is now obviously wrong. Without a baseline it would just be a number.

## Open items

- [ ] Add `mon01` to DNS on infra01, and a static lease on the router
- [ ] Install node_exporter on `infra01` and `mon01` so every machine is monitored
- [ ] Add the Proxmox PVE exporter for per-VM metrics
- [ ] Set Prometheus retention deliberately — the host's NVMe is QLC with modest write
      endurance, and a metrics database writes continuously
- [ ] Alerting: something should page when a disk fills or a host stops responding
