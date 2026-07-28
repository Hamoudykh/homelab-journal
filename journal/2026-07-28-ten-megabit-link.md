# 2026-07-28 — Diagnosing a link stuck at 10 Mbps

**Symptom:** the router's LAN page showed port LAN 3 connected at **10 Mbps, full duplex**,
while LAN 4 was at 1000. Nothing was failing — the network worked, just at one percent of
the capacity it should have had.

Found by reading the router's Physical Ports table while doing something unrelated
(adding a DHCP reservation). Nothing alerted; nothing was broken enough to notice.

## Why a slow link is worth chasing

Gigabit Ethernet needs all four wire pairs. 100 Mbps needs two. So a damaged cable does not
usually cause a *failure* — it causes a silent negotiation down to a slower speed, and
everything keeps working. This is one of the most common invisible faults in the field.

Everything done the previous day — the AMT console, the KVM screen, and a 1.6 GB ISO
streamed over IDE-R — went through this 10 Mbps link.

## Isolating the fault

Three suspects: the server's NIC, the cable, the router port. The method was to eliminate
them one at a time rather than swapping parts and seeing if the symptom disappeared.

**1. Is the server's NIC limited?** Asked the server directly rather than guessing:

```
ethtool nic0
```

`Advertised link modes:` included `1000baseT/Full` and auto-negotiation was on. The NIC was
offering gigabit. **NIC eliminated** — and this cost one command instead of a cable swap.

**2. Are the cable and router port capable?** Left the cable in router LAN 3, unplugged the
server end, and plugged that end into the Pockethernet 2. Ran the live link test.

Result: **1000 Mbps full duplex.** Both the cable and the port do gigabit.

This is stronger evidence than a wiremap would have been. Wiremap only proves continuity
and correct pairing; an actual gigabit link proves all four pairs carry gigabit signalling
under real conditions. The planned TDR test was unnecessary — a better test had already
answered the question.

**3. So what was left?** All three components were individually fine, which pointed at the
*negotiation* rather than any part.

## Root cause

Ethernet auto-negotiation runs **once, at link-up**. Both ends advertise their capabilities,
agree on the best common mode, and that result stands until the link is reset. It does not
retry or improve later.

If a link trains badly during that one handshake — a partially seated plug, a marginal
contact, electrical noise at that instant — it can settle on 10 Mbps and stay there
indefinitely. Everything works, so nothing complains.

Unplugging the cable for the Pockethernet test and reconnecting it forced a fresh
negotiation:

```
Link partner advertised link modes:  10baseT/Half 10baseT/Full
                                     100baseT/Half 100baseT/Full
                                     1000baseT/Half 1000baseT/Full
Speed: 1000Mb/s
Duplex: Full
Auto-negotiation: on
```

The router port had been advertising gigabit the whole time. The link had simply been stuck
in a bad result since it was first connected — during a rushed session the previous day.

## Takeaways

- **A working link is not a healthy link.** Check negotiated speed, not just connectivity.
- **Read evidence before changing the system.** One `ethtool` command distinguished three
  hypotheses; swapping parts would have tested them one at a time and explained nothing.
- **Test equipment can substitute for an endpoint.** Putting the tester where the server was
  isolated two components at once.
- **The thing you skip testing is disproportionately likely to be the broken one.** The
  cable tested the day before was a spare; the cable actually carrying traffic was never
  tested.
- When a link is stuck at a low speed, **bounce it before replacing anything** — negotiation
  only happens at link-up.

## Also completed

- **DHCP reservation** created on the router (Static leases → bridge `brlan0`) binding MAC
  `2c:f0:5d:bc:81:49` to `192.168.1.6`. The pool runs `.2`–`.253` with a one-hour lease, so
  the hypervisor's static address was sitting unprotected inside the range.
- **Switched to SSH** (`ssh root@192.168.1.6`) for day-to-day administration. The Proxmox
  web console is laggy and has poor copy/paste — it is the fallback for when the network
  stack is broken, not the everyday tool.

Access hierarchy, each layer depending on less than the one above it:
SSH → Proxmox web console → AMT KVM → ATEN crash cart.
