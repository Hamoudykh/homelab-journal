# Hardware Inventory

## pve01 — Lenovo ThinkCentre M90t (Gen 1)

Model `11D0S0F600`. Verified 2026-07-27 via Intel AMT hardware inventory, not from
the vendor spec sheet — the machine is ex-corporate and may have been modified.

| Component | Detail |
|---|---|
| CPU | Intel Core i7-10700 — 8C/16T, 2.9 GHz base / 4.8 GHz boost, Comet Lake, vPro |
| Virtualization | VT-x and VT-d (so PCIe passthrough is available) |
| Chipset | Intel Q470 |
| RAM | 16 GB — 2× 8 GB Samsung DDR4-2933 (M378A1K43DB2-CVF) in slots 1 and 3 |
| RAM headroom | Slots 2 and 4 empty; platform maximum 128 GB |
| Storage | 1× Intel SSD 660p 1 TB NVMe (QLC) + DVD-RW |
| Network | Intel I219-LM 1 GbE, single port (`e1000e` driver) |
| Expansion | PCIe 3.0 ×16, ×4, ×1 — all free |
| BIOS | M2TKT33A, dated 2020-11-20 |
| Management | Intel AMT 14.0.33.1125 |

### Notes and constraints

- **16 GB RAM is the binding constraint on this host.** Cores and disk are ample.
  A matched pair of DDR4-2933 UDIMMs in slots 2 and 4 is the highest-value upgrade.
- The 660p is a **QLC** drive with modest write endurance. Keep Prometheus retention
  short and be deliberate about anything that writes continuously.
- A **single 1 GbE port** limits topology work. A used Intel I350-T4 (quad gigabit)
  or X520 (10 GbE) in the free ×4 slot is the planned expansion.
- BIOS is from late 2020 — a firmware update is worth doing for CPU microcode and
  security fixes.

### BIOS settings changed

| Setting | Was | Now | Why |
|---|---|---|---|
| Fast Boot | Enabled | Disabled | Skipped USB init during POST, so pre-boot keyboards did not work |
| Option Keys Display | Disabled | Enabled | Machine now shows its own boot hotkeys |
| Option Keys Display Style | — | Normal | One forgiving Enter keypress instead of racing a function key |

## Test equipment

- **Pockethernet 2** — RJ45 tester, Bluetooth LE to phone app. Wiremap, TDR, PoE,
  link, VLAN, DHCP, CDP/LLDP, toner, port blinker. Dual terminator for cable tests.
- **Oscium Nomad + Hamina Onsite** — Wi-Fi survey kit.
- **ATEN CV211CP** — crash cart adapter (VGA + USB to laptop). Fallback console.
