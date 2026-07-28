# Home Lab — AI & Infrastructure

A working lab for learning modern data center practice: virtualization, out-of-band
management, network design, telemetry, and automation. Built and documented from scratch.

## Current state

| | |
|---|---|
| Hypervisor | Proxmox VE 9.2 on `pve01` (Lenovo ThinkCentre M90t) |
| Management | Intel AMT 14 out-of-band, plus ATEN CV211CP crash cart as fallback |
| Network | Flat `192.168.1.0/24`; VLAN segmentation planned |
| Test gear | Pockethernet 2, Oscium Nomad + Hamina Onsite |

## Hardware

**pve01** — Lenovo ThinkCentre M90t (11D0S0F600)
Intel Core i7-10700 (8C/16T, vPro) · 16 GB DDR4-2933 (2 of 4 slots populated) ·
1 TB Intel 660p NVMe · Intel I219-LM 1 GbE · Q470 chipset · VT-x/VT-d

Full inventory: [docs/hardware-inventory.md](docs/hardware-inventory.md)

## Conventions

- Hostnames: `<role><nn>[-<function>]`, lowercase, hyphens only
- Management interfaces get their own name: `pve01` is the host, `pve01-amt` is its
  management engine
- Lab domain: `lab.home.arpa` (per RFC 8375 — not `.local`, which RFC 6762 reserves
  for mDNS)

## Journal

Dated entries covering what was built, what broke, and what it taught.

- [2026-07-27 — Out-of-band management and Proxmox install](journal/2026-07-27-out-of-band-management.md)
- [2026-07-28 — Diagnosing a link stuck at 10 Mbps](journal/2026-07-28-ten-megabit-link.md)
- [2026-07-28 — First VM: infra01](journal/2026-07-28-first-vm.md)

## Roadmap

1. **Foundations** — virtualization, L2/L3 on physical switches, observability baseline
2. **Automation & AI networking** — Ansible/IaC, leaf-spine topology, AWS AIF-C01
3. **Capstone** — agentic NetOps diagnostics, zero-touch provisioning, managed edge AI
