# 2026-07-29 — Remote access with Tailscale

**Goal:** reach the lab from outside the house without exposing anything to the internet.

**Outcome:** `pve01` acts as a subnet router on a private WireGuard mesh. The whole
`192.168.1.0/24` lab is reachable from any signed-in device, anywhere.

## Why not port forwarding

The obvious approach is forwarding a port on the router to SSH. It is also the wrong one.

Anything forwarded to the internet is scanned within hours — SSH on a public IP sees
credential-stuffing attempts continuously. And the lab has services that must **never** be
exposed:

- **Intel AMT (16992)** runs below the operating system, can power-cycle and reinstall the
  machine, and has a history of remotely exploitable authentication bypasses
  (INTEL-SA-00075). It is currently unencrypted HTTP with digest auth.
- **Proxmox (8006)** is root-equivalent control of every VM.
- **Ollama (11434)** has no authentication at all.

A VPN inverts the problem: instead of opening a door and defending it, nothing is exposed and
only authenticated devices can reach anything.

## Why Tailscale specifically

It is WireGuard with the hard parts handled: no port forwarding, no static public IP, and it
works behind carrier-grade NAT. Devices authenticate to a coordination service, then talk
peer-to-peer and encrypted. Free for personal use.

## Setup

On `pve01`:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
tailscale up --advertise-routes=192.168.1.0/24 --accept-routes
```

`--advertise-routes` is what makes this useful. Without it you reach only pve01 itself;
with it, pve01 becomes a **subnet router** — a gateway into the whole LAN, so every device
in the lab becomes reachable even though only pve01 runs Tailscale.

That matters because AMT, the router, and the switches can never run a VPN client. One
subnet router covers everything.

`tailscale up` prints a login URL that must be opened and authenticated. **This is easy to
miss**: the command appears to succeed, but until that URL is visited the machine has not
joined and the admin console shows "waiting for your first device".

Then the laptop signs in with the same account, and in the admin console the machine's
**Subnets** badge is clicked to **approve** `192.168.1.0/24`. Advertised routes are inactive
until explicitly approved — a sensible default, since a subnet router is a gateway into an
entire network.

## Result

| | |
|---|---|
| `pve01` Tailscale IP | `100.96.157.50` |
| Laptop Tailscale IP | `100.123.133.83` |
| Routed subnet | `192.168.1.0/24` via pve01 |

From anywhere, using the ordinary LAN addresses:

```bash
ssh root@192.168.1.6          # the hypervisor
https://192.168.1.6:8006      # Proxmox
http://192.168.1.12:3000      # Grafana
http://192.168.1.6:16992      # AMT
```

Nothing is exposed publicly. The router has no forwarded ports.

## Testing it honestly

Testing from the home network proves nothing — traffic goes over the LAN directly and never
touches the tunnel. The only valid test is from a **different network**: turn off Wi-Fi,
tether to mobile data, and connect.

Same discipline as the rest of the lab: a test that cannot fail is not a test.

## Open items

- [ ] Install Tailscale on the Windows GPU node (blocked: MSI needs admin, exit 1603)
- [ ] Consider Tailscale ACLs to restrict which devices may reach AMT
- [ ] MagicDNS, so `pve01` resolves without an IP
- [ ] Tailscale on the phone, so Grafana is reachable from anywhere
