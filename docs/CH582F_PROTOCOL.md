# CH582F ↔ SN32F299 UART Protocol — AJAZZ AK820PRO

Two independent sources feed this document:

1. **Static** — disassembly of `fcn.0000be74` in the SN32F299 stock firmware
   (internal RAM addresses, flag semantics, the internal state machine).
2. **Live** — logic-analyzer captures of the real UART traffic between the stock
   firmware and the CH582F module (Raspberry Pi Pico + sigrok/PulseView UART
   decode, 115200 8N1), plus the working QMK reimplementation in
   `keyboards/a_jazz/ak820pro/bluetooth/ch582f_ajazz.c`.

**Where the two disagree, the live capture wins for on-wire *semantics*** — the
disassembly tells you what the firmware *does* with a byte, the capture tells you
what the byte actually *means*. The most important corrections from live capture:
`0xA1` carries **keystrokes**, `0xA3` carries **consumer/media (encoder) usages**,
`0x5C` is **battery**, `0x5A` is the **host LED state**, the second `0x5B` byte is a
**connection-state code (not a slot)**, and `61 0D 0A` is a bidirectional **ACK
token (not a disconnect)** — both the MCU and the module emit it to ack frames.

> This document describes the protocol **as actually implemented and confirmed
> working** in the QMK port. Where the shipped driver deviates from or narrows the
> stock behaviour (only BT slots 1–3, `0xA3` reused for consumer control, an active
> battery poll), the implemented reality is documented and the stock/disassembly
> reading is flagged.

---

## Physical Layer

| Parameter | Value |
|-----------|-------|
| Peripheral | UART2 (`0x40054000`), ChibiOS `SD2` |
| Baud rate | 115200 |
| Format | 8N1 |
| TX pin (SN32 → CH582F) | **B7** (P1.7), UTXD2 via PFPA `0b11` |
| RX pin (CH582F → SN32) | **B6** (P1.6), URXD2 via PFPA `0b11` |
| IRQ | IRQ8 (UART2IRQ) |

> Pin names are the SN32/QMK port labels (`B`= port 1) that the capture rig was
> probed on and that the QMK driver configures in `early_hardware_init_post`. The
> stock disassembly references these as P3.6/P3.7; the probed pads carrying the
> traffic are B7 (TX) and B6 (RX).

---

## Frame Formats

Both directions use a **sum-checksum** family:

```
TX:  [CMD,  param0..paramN, SUM]      SUM = (CMD + Σparams) & 0xFF
RX:  [TYPE, data,           SUM]      SUM = (TYPE + data)   & 0xFF   (3-byte form)
```

The RX stream is **not uniformly 3 bytes** and **drops bytes on bursts**, and it
interleaves a literal-text ACK token (`61 0D 0A` = `"a\r\n"`, where the trailing
`0x0A` is a real LF, *not* a checksum: `0x61+0x0D = 0x6E ≠ 0x0A`). A fixed 3-byte
state machine desyncs permanently. Parse with a **self-resyncing rolling 3-byte
window** and drain the whole RX queue each task tick.

The default ChibiOS serial input queue is sufficient **only if** the queue is
drained fully every task tick; the QMK driver caps a single drain at 64 bytes to
bound latency while still clearing a connect burst.

---

## TX: SN32 → CH582F (Commands)

Packet assembled at RAM `0x20002692`, transmitted via `fcn.0001871A`.

| CMD | Name | Payload | Notes |
|-----|------|---------|-------|
| `0xA1` | **Keyboard HID boot report** | `mods, 0x00, k0..k5` (8 bytes) | **Wireless keystrokes.** Standard USB HID boot report verbatim. ⚠️ The disassembly labels this "channel connect"; on the wire it carries keypresses. |
| `0xA2` | **NKRO report** | 14-byte key bitmap | Emitted when many keys are held; `0xA1` covers normal 6KRO. The QMK port reports NKRO as unsupported over BT, so it sends only `0xA1`. |
| `0xA3` | **Consumer / media (encoder)** | `usage_lo, usage_hi` (2 bytes, LE) | **Volume/media usages** (the rotary encoder). Confirmed working over BT **and** 2.4G. ⚠️ The disassembly labels `0xA3` "BT address"; on the wire the module accepts it as a consumer report. |
| `0xA4` | Parameter | 2 bytes | Config parameter (`0x2000009E+1`). Not used by the QMK port. |
| `0xA5` | Status | `val, 0x10|0x00` | 2nd byte `0x10` if `*0x2000006A != 0`. Inert when probed live (no reply). Not used by the QMK port. |
| `0xA6` | **Channel / mode select + status poll** | 1 byte (see below) | See encoding below. Select is sent **twice**. High nibble `3` = select slot, `5` = pair, `0x53` (`'S'`) = battery/status poll. |
| `0xA7` | Short connect | 1 byte (`0x20000161`) | ⚠️ Live: drops the link — **do not send**. |
| `0xA8` | Connect extended | `data[1..6]` | 6-byte extended connection data. |
| `0xA9` | Device name | `"AK820 5.1-$"` | BT advertising name (flash `0x19A2B`, `$` terminator). |
| `0xAA` | Unknown | — | Inert when probed live (no reply). |
| `0xAB` | Extended data | `data[1..4]` | |

### `0xA6` channel / mode byte

| Byte | Value | Meaning |
|------|-------|---------|
| `'0'` | 0x30 | 2.4G dongle (peer) — `CH582_PROFILE_PEER_24G` |
| `'1'` | 0x31 | **select** BT slot 1 |
| `'2'` | 0x32 | **select** BT slot 2 |
| `'3'` | 0x33 | **select** BT slot 3 |
| `'5'` | 0x35 | 2.4G pairing mode — `CH582_PROFILE_PAIR_24G` |
| `'Q'` | **0x51** | **PAIR current slot** (see below) |
| `'S'` | **0x53** | **battery / status poll** — module replies with a `5C <pct>` frame |

> **Only BT slots 1–3 exist** (matching the stock hardware — there is no slot 4).
> The profile enum is `CH582_PROFILE_PEER_24G` (0x30), `CH582_PROFILE_BT_1..3`
> (0x31–0x33), `CH582_PROFILE_PAIR_24G` (0x35). The old `0x34` "slot 4" select does
> not exist. (`0x34` still appears on the **RX** side as a `5B` connect-attempt
> *state* code — a different direction; see the `5B` table.)

### Pairing command — `A6 51`  *(live discovery)*

Pairing is a **constant, slotless** `A6 51` (sum `0xF7`), sent **twice**, that puts
the **currently-selected** slot into advertising/pairing. It carries **no slot of
its own** — slot-2 and slot-3 pairings both emit the identical `A6 51`. So the slot
must already be selected with `A6 3x` first. This is exactly why the stock UX only
lets you pair the *active* slot. (`A6 53` seen in traces is the **battery/status
poll**, not a slot select — see the `0xA6` table above.)

The select param's high nibble is the discriminator: **`A6 3x` = select**,
**`A6 5x` = pair**.

---

## RX: CH582F → SN32 (Events)

Received into RAM buffer `0x20002670`. Live-decoded semantics:

| Frame | Meaning | Notes |
|-------|---------|-------|
| `61 0D 0A` | **ACK token** (`'a' \r \n`) | Bidirectional ack (`"a\r\n"`); both MCU and module emit it. ⚠️ NOT a disconnect. Ignore for connection state. The RX line is otherwise silent at steady idle. |
| `5A <led> <sum>` | **Host keyboard LED bitmap** | USB LED bits: `0x02` = Caps ON, `0x00` = off, `0xFF` = init. Lets the keyboard mirror host Caps Lock over BT. ⚠️ Disassembly read this as "connection speed". |
| `5B <code> <sum>` | **Connection-STATE code** | `<code>` is a **state, not a slot** (same `5B 32` for any slot). See state table. |
| `5C <pct> <sum>` | **Battery percent** (decimal) | `5C 64 C0` = 100%. Sent **in reply to the `A6 53` poll**; the module does not stream it unprompted. ⚠️ Disassembly read this as "brightness". Must NEVER be used as a connected signal. |

### ACK behaviour (implemented)

Mirroring the stock firmware, the QMK driver replies to each **`5B`** (connection
state) and **`5C`** (battery) frame with the raw `61 0D 0A` ACK token (~1.3 ms
later). It does **not** ack `5A` (LED) frames. This is enabled by default
(`CH582_ACK_FRAMES`); it made cold-boot connects behave like the stock peer.

### `5B` connection-state codes

| Code | Meaning | Connected? |
|------|---------|-----------|
| `0x31` | Advertising / **pairing** (waiting to bond) | no |
| `0x32` | **Link established** — the *only* "connected" signal | **yes** |
| `0x33` / `0x34` | Connect **attempt** — link down / retrying; a failed link stops here and never reaches `0x32` | no |
| `0x23` | Idle / finalize / cleared-pending — periodic, appears both connected and disconnected | ignore |

**Parser rule (shipped):** set connected only on `5B 32`; clear on `5B 31/33/34`;
ignore `5B 23`, `5C`, `5A`, and `61 0D 0A` for connection state.

---

## Observed connection lifecycle (live)

A successful pairing/connect, as captured on the RX line:

```
5B 23 7E          idle
5B 31 8C  (×N)    advertising / pairing
5B 32 8D  (×N)    LINK ESTABLISHED   ← connected latches here
61 0D 0A          (MCU acks each 5B/5C)
5C 64 C0          battery 100% (in reply to an A6 53 poll)
```

A **failed** link (e.g. host BT turned off) instead shows `5B 33`/`5B 34` and then
settles back to `5B 23` **without ever reaching `5B 32`** — that is how a drop is
signalled. The RX line is silent at steady idle; battery (`5C`) appears only when
the keyboard polls with `A6 53`.

---

## Internal firmware state machine (`*0x200002CB`) — *static*

From disassembly; these are the firmware's *internal* states, not on-wire bytes.

| Value | Meaning |
|-------|---------|
| 0x00 | Idle / disconnected |
| 0x03 / 0x04 | BT connecting (variants) |
| 0x05 | 2.4G connecting |
| 0x06 / 0x07 | BT connected (variants) |
| 0x09 | BT connected (6-byte extended) |
| 0x0C | BT connected (9-byte extended) |
| 0x0A | 2.4G connected |
| 0x10 | Special / transition |
| 0x22 | 2.4G connected (confirmed) |

---

## Key RAM addresses — *static*

| Address | Purpose |
|---------|---------|
| `0x20002692` | TX packet assembly buffer |
| `0x20002670` | RX response buffer |
| `0x20000153` | TX command buffer `[cmd, channel]` |
| `0x20000154` | Channel ASCII byte |
| `0x20000147` | TX busy flag (0 = idle) |
| `0x2000014B` | Transfer lock flag |
| `0x2000014C` | TX lock flag |
| `0x2000014D` | Disconnect pending |
| `0x2000014E` | Connect pending |
| `0x2000014F` | Reconnect pending |
| `0x20000150` | BT name send pending |
| `0x20000151` | BT connecting flag |
| `0x20000152` | BT connected flag |
| `0x200002CB` | BT state machine (table above) |
| `0x200002CF` | UART RX data pending flag |
| `0x20000176` | Reconnect interval (ms) |
| `0x2000017C` | Fast timeout (ms) |
| `0x20001360` | BT poll interval (from CH582F) |
| `0x20000183` | BT device name length |
| `0x2000006A` | Status flag: include `0x10` in `0xA5` |

## Flash constants

| Address | Content |
|---------|---------|
| `0x19A2B` | BT device name: `"AK820 5.1-$"` (`$` = terminator) |

---

## QMK implementation notes

The working reimplementation lives in
`keyboards/a_jazz/ak820pro/bluetooth/ch582f_ajazz.c` and is built with
`BLUETOOTH_ENABLE = yes` / `BLUETOOTH_DRIVER = custom`.

- **QMK Bluetooth driver API (no `host_set_driver` hack).** With
  `BLUETOOTH_DRIVER = custom`, QMK core routes reports to the `bluetooth_*`
  functions whenever Bluetooth is the active host and to the USB driver otherwise
  — core does the USB/wireless routing, so there is no `host_driver_t` wrapper and
  no clobber. The driver provides `bluetooth_init` (starts `SD2`), `bluetooth_task`
  (pumps `ch582_task`), `bluetooth_is_connected`, and the send hooks below.
- **Keystrokes.** `bluetooth_send_keyboard()` → `ch582_send_keyboard_report()` →
  `A1 <mods,0x00,k0..k5>`. `bluetooth_can_send_nkro()` returns **false**, so QMK
  sends a plain 6KRO boot report over BT (USB keeps NKRO).
- **Consumer / encoder.** `bluetooth_send_consumer(usage)` → `A3 <usage LE>`; gated
  on the link being up. Confirmed working over BT and 2.4G. Mouse/system are stubs.
- **Profile select.** `ch582_set_profile(profile)` → `A6 <0x30+slot>`; sets
  `connect_requested` and re-issues the select every **500 ms**
  (`CH582_CONNECT_RETRY_MS`) while requested-but-not-connected, so a cold boot
  directly into BT recovers the first dropped select. The retry is gated on
  `!is_module_connected` so it can never bounce a live link.
- **Pairing.** `ch582_enter_pairing()` → `A6 51` ×2 (pairs the current slot);
  `ch582_pair(profile)` = select + enter_pairing.
- **Select / pair UX (matches stock).** Short-press Fn+Q/W/E selects a BT slot.
  Holding the **already-selected** slot (re)starts a link attempt and only enters
  pairing if the link is still down after a **10 s** timeout (a link that comes up
  during the hold aborts pairing). A press on a non-selected slot only selects it.
- **Battery poll.** The driver sends `A6 53` every **5 s**
  (`CH582_BATTERY_POLL_MS`, in all modes incl. USB-charging) and reads the `5C`
  reply into `ch582_get_battery()`.
- **LED mirror.** `5A` (when connected, low-5-bits sane) → `host_leds` →
  `bluetooth_keyboard_leds()`, so the host's Caps Lock is mirrored over BT.
- **ACK.** `5B`/`5C` frames are acked with `61 0D 0A` (`CH582_ACK_FRAMES`).

---

## Notes

- This protocol is active only in BT (`*0x20000164 == 1`) or 2.4G (`== 2`) mode.
- In USB mode (`== 0`) UART2 is idle and the CH582F is bypassed — the SN32's own
  USB peripheral handles HID.
- The module must **stay powered** even when BT is unused: it still answers the
  `A6 53` battery poll. Do not hardware-reset it to force a disconnect.
- The module is **silent at steady idle** — it does not stream status frames. The
  only way to read battery is to poll it with `A6 53` (the driver does this every
  5 s); `5C` comes back in reply. `0xA5` and `0xAA` get no reply; `0xA7` actively
  drops the link.
- The `0xA9` device name advertises this keyboard to BT hosts as **"AK820 5.1"**.
