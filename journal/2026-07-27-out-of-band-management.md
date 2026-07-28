# 2026-07-27 — Out-of-band management and Proxmox install

**Goal:** turn an ex-corporate Lenovo ThinkCentre M90t into a Proxmox hypervisor,
starting from a machine with no monitor, no keyboard, and no known specifications.

**Outcome:** Proxmox VE 9.2 running on `pve01` at `192.168.1.6`, fully administered
over the network. Intel AMT provides remote power control, console, and BIOS access.

---

## What was built

1. Console access to a headless machine via ATEN CV211CP crash cart.
2. Intel AMT enabled and provisioned — out-of-band management over Ethernet.
3. Full hardware inventory captured remotely, before installing anything.
4. Proxmox VE 9.2 installed from USB, driven entirely through the AMT KVM.
5. First cable certification and LLDP neighbor discovery with the Pockethernet 2.

## Key concept: in-band vs out-of-band management

**In-band** management goes through the running operating system — SSH, RDP, an agent.
Convenient, and it dies exactly when it is most needed.

**Out-of-band** management uses a separate processor with its own network path that does
not care whether the OS exists. Intel AMT, Dell iDRAC, HPE iLO, and IPMI are all
out-of-band. This is why a machine that is powered off can still be powered on remotely.

Nearly downloaded a 1.4 GB Intel Management Engine *driver* before realising it was the
wrong side of this distinction — that driver runs inside the managed OS, which is
precisely what out-of-band management is designed not to depend on.

## AMT configuration

Entered MEBx with **Ctrl+P** at the Lenovo splash (default password `admin`, forced change
on first login). Enabled:

- Manageability Feature Selection
- SOL / Storage Redirection / KVM
- User Consent → **None** (otherwise KVM requires someone physically present to read a
  6-digit code off the screen — sensible for corporate desktops, useless for a headless lab)
- Power policy allowing the management engine to stay alive in S0–S5, which is what makes
  remote power-on possible
- **Activate Network Access** — nothing listens until this is done

AMT ports: **16992** HTTP, **16993** TLS, **16994/16995** redirection (SOL and IDE-R).
It rides the onboard NIC only; USB or add-in NICs will not carry it.

**Security note.** AMT sits below the OS, so the OS cannot defend it. It has a serious
CVE history (INTEL-SA-00075, a remotely exploitable auth bypass). Currently running
unencrypted on port 16992 with digest auth. Must move to a dedicated management VLAN,
and ideally TLS on 16993.

## Things that broke, and why

**Black screen after Ubuntu booted.** The crash cart renders text-mode video reliably but
could not display the graphical login. The machine was healthy the whole time. Lesson:
"black screen" is not one fault — separate *no signal* from *a signal that is blank*.

**F1 did nothing at POST.** Two causes stacked. Lenovo uses F1/F12, not Del. More
importantly, **Fast Boot was enabled**, which skips USB initialisation during POST, so the
adapter's emulated keyboard was never ready in the window when the hotkey mattered. The
BIOS help text said outright that Fast Boot should be off when booting from CD/DVD or
network. Found by reading the screen instead of hunting for the setting I assumed I needed.

**Server invisible on the network.** Everything up to that point had worked over the crash
cart cable, which carries no network. There was simply no Ethernet cable plugged in.
Lesson: confirm layer 1 before touching software.

**IDE-R boot failed.** Booting the Proxmox ISO over AMT redirection did not work: the
IDE-R session does not survive the "Reset to IDE-R CDROM" action on this firmware, and
IDE-R is a legacy-BIOS feature that interacts poorly with UEFI-mode boot. Predicted the
session would drop, tested it, confirmed it, and fell back to a USB stick after three
attempts. Knowing when to stop optimising a path is its own skill.

**Password typed into the username field.** At the `pve01 login:` prompt. Usernames are
echoed to screen, and failed logins record the attempted username in `/var/log/auth.log`
— so the password ended up in a log file in plain text. Password was changed immediately.
This is why auth logs are treated as sensitive files.

## Pockethernet 2 — first measurements

The test list maps directly onto the OSI model, which is also the order to troubleshoot in:

| Layer | Tests |
|---|---|
| Physical | Wiremap, TDR (length and fault distance, ~0.4 m resolution), toner, port blinker |
| Physical / data link | Link speed and duplex negotiation, PoE class and PSE type |
| Data link | VLAN tagging and detection, CDP/LLDP |
| Network | DHCP (IPv4), ping, IPv6 |

**Cable test** (tester one end, terminator the other): result `4-pair straight (S)` — all
eight conductors correct, no opens, shorts, reversals or split pairs, and a continuous
shield (STP). A shield only helps if properly grounded; grounded at both ends it can
create a ground loop and be worse than none.

**Live port test** (no terminator — the switch is the far end): pulled `192.168.1.33` via
DHCP, and LLDP returned Port ID `D8:78:7F:1C:2A:8F` with TTL 180.

That MAC matches what ARP reported for the gateway — **the same device identified by two
independent methods**, which is how a network map earns trust.

LLDP allows several Port ID formats; consumer gear reports a MAC, managed switches report
readable interface names. **LLDP TTL is seconds of validity, not the IP hop-count TTL** —
same three letters, different layer, different meaning.

## Install decisions

| Decision | Choice | Reasoning |
|---|---|---|
| Filesystem | ext4, not ZFS | ZFS ARC wants RAM this host does not have, and on a single disk there is no redundant copy to self-heal from — overhead without the main benefit |
| Installer | Terminal UI | Text renders reliably over a constrained remote console; graphical modes had already failed twice |
| Addressing | Static `192.168.1.6/24` | Servers get static addresses, clients get DHCP. A hypervisor's address is referenced by browsers, SSH, and later Ansible — it must not move |
| DNS | `192.168.1.1` (router) | One place to change DNS later; insulates against ISP resolver changes; the router can also answer for local names |
| Interface pinning | Enabled | Interface names silently renaming after a hardware change is a classic way to lose remote access |

`.6` is also the address AMT uses — AMT and the host share one NIC and one IP by default,
with AMT answering on 16992–16995 and Proxmox on 8006.

## Verification

Confirmed from a separate machine rather than trusting the install:

```
Port 8006 reachable: True
HTTP 200 — Server: pve-api-daemon/3.0
Page title: pve01 - Proxmox Virtual Environment
```

The Proxmox ISO was verified against its published SHA256 before use, and the Rufus
binary's Authenticode signature was checked. Compromised distribution mirrors are a real
attack path — Linux Mint shipped a backdoored ISO from its own website in 2016.

## Process failure to record

The drives held a Lytx Ubuntu installation that **was never inspected before being
overwritten**. Flagged three times, skipped anyway under momentum. Nothing was lost that
mattered, but in a real decommissioning that is the omission that becomes a compliance
incident.

## Open items

- [ ] DHCP reservation on the router for MAC `2c:f0:5d:bc:81:49` — `.6` is a static
      address sitting inside the DHCP pool
- [ ] Move AMT onto a dedicated management VLAN; TLS on 16993
- [ ] Populate RAM slots 2 and 4
- [ ] BIOS firmware update (current image dates from 2020)
