# Services and Ports

## How to read an address

An address like `192.168.1.12:3000` has two parts:

- **`192.168.1.12`** — the **IP address**. *Which machine* on the network.
- **`3000`** — the **port**. *Which service* on that machine.

One machine runs many services at once. The IP gets traffic to the right machine; the port
gets it to the right program inside that machine. Ports range from 0 to 65535.

**Why some URLs have no port.** Browsers assume **80** for `http://` and **443** for
`https://`. So `http://192.168.1.1` really means `http://192.168.1.1:80` — the port is
implied, not absent. Anything running on a different port has to be typed explicitly.

Ports are also why `192.168.1.6` can serve the Proxmox interface on 8006 *and* the Intel AMT
interface on 16992 at the same time, from what are effectively two different computers (the
OS and the management engine) sharing one address.

## The lab

| URL | What it is | Notes |
|---|---|---|
| `http://192.168.1.1` | Router admin (HOT Box 5F) | Port 80 implied. DHCP, static leases, port status |
| `https://192.168.1.6:8006` | **Proxmox** web interface | Manage the host, VMs, containers. Self-signed cert warning is expected |
| `http://192.168.1.6:16992` | **Intel AMT** web interface | Out-of-band: power control, hardware inventory, event log. Works even when the OS is off |
| `http://192.168.1.6:9100/metrics` | **node_exporter** raw output | Plain text metrics. What Prometheus reads — worth looking at once to see what a scrape target actually is |
| `http://192.168.1.12:3000` | **Grafana** | Dashboards and graphs |
| `http://192.168.1.12:9090` | **Prometheus** | Metric storage. `Status → Targets` shows what it is scraping and whether each is healthy |
| `http://127.0.0.1:3000` | **MeshCommander** (on the Windows PC) | AMT KVM, Serial-over-LAN, IDE-R. Only runs while `meshcommander` is running in a terminal |

Note that Grafana and MeshCommander both use port 3000 — on *different machines*, so there is
no conflict. Two services can share a port number as long as they are not on the same host.

## Not for a browser

| Address | Service |
|---|---|
| `192.168.1.6:22` | SSH to pve01 — `ssh root@192.168.1.6` |
| `192.168.1.174:22` | SSH to infra01 |
| `192.168.1.12:22` | SSH to mon01 |
| `192.168.1.174:53` | DNS on infra01 (dnsmasq) |
| `192.168.1.6:16994` | AMT redirection — Serial-over-LAN and IDE-R |

## Machines

| Name | Address | Type | Runs |
|---|---|---|---|
| `pve01` | 192.168.1.6 | Physical (ThinkCentre M90t) | Proxmox VE, node_exporter, Intel AMT |
| `infra01` | 192.168.1.174 | VM (100) | dnsmasq — DNS for `lab.home.arpa` |
| `mon01` | 192.168.1.12 | LXC container (101) | Prometheus, Grafana |

## Well-known ports worth memorising

| Port | Service |
|---|---|
| 22 | SSH |
| 53 | DNS |
| 80 | HTTP |
| 443 | HTTPS |
| 3000 | Grafana (by convention, not a standard) |
| 8006 | Proxmox VE |
| 9090 | Prometheus |
| 9100 | node_exporter |
| 16992–16995 | Intel AMT |
