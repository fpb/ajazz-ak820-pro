# CH582F ↔ SN32F299 UART Protocol — AJAZZ AK820PRO

Derived from disassembly of `fcn.0000be74` (SN32F299 stock firmware).

## Physical Layer

| Parameter | Value |
|-----------|-------|
| Peripheral | UART2 (`0x40054000`) |
| Baud rate | 115200 |
| Format | 8N1 |
| TX pin | P3.6 (UTXD2, via PFPA) |
| RX pin | P3.7 (URXD2, via PFPA) |
| IRQ | IRQ8 (UART2IRQ) |

---

## TX: SN32 → CH582F (Commands)

**Packet format:** `[CMD, PARAM1..PARAMN, CHECKSUM]`

- Checksum = sum of all bytes including CMD, truncated to uint8
- Packet assembled at RAM `0x20002692`, transmitted via `fcn.0001871A`

| CMD | Name | Params | Data source | Notes |
|-----|------|--------|-------------|-------|
| `0xA1` | Channel connect | 9 | `[channel, key[0..7]]` | channel from `*0x20000154`, 8-byte key from `0x20000093` |
| `0xA2` | Connect with key | 15 | `key[0..14]` from `0x200013F4` | BT reconnect using stored pairing key |
| `0xA3` | BT address | 3 | `addr[0..2]` from `0x2000009B` | Partial BT MAC address |
| `0xA4` | Parameter | 2 | `param[0..1]` from `0x2000009E+1` | 2-byte config parameter |
| `0xA5` | Status | 2 | `[val, 0x10_or_0]` | Second byte = `0x10` if `*0x2000006A` != 0 |
| `0xA6` | Channel select | 2 | `[0xA6, channel_ascii]` | channel = ASCII `'0'`–`'5'` |
| `0xA7` | Short connect | 2 | `[0xA7, byte from 0x20000161]` | |
| `0xA8` | Connect extended | 7 | `data[1..6]` from `0x200000A0` | 6-byte extended connection data |
| `0xA9` | Device name | N | `'AK820 5.1-$'` from flash `0x19A2B` | BT advertising name, length from `*0x20000183` |
| `0xAA` | Unknown | 0 | — | |
| `0xAB` | Extended data | 5 | `data[1..4]` from `0x200000A5` | |

### Channel byte encoding (used in `0xA1` and `0xA6`)

| ASCII byte | Value | Meaning |
|-----------|-------|---------|
| `'0'` | 0x30 | 2.4G default (paired dongle) |
| `'1'` | 0x31 | BT slot 1 |
| `'2'` | 0x32 | BT slot 2 |
| `'3'` | 0x33 | BT slot 3 |
| `'4'` | 0x34 | BT slot 4 |
| `'5'` | 0x35 | 2.4G pairing mode |

---

## RX: CH582F → SN32 (Responses/Events)

**Response format:** `[TYPE, DATA, CHECKSUM]` — 3 bytes

- Checksum = `(TYPE + DATA) & 0xFF`
- Received into RAM buffer `0x20002670`

| Type | Data | Checksum | Event | SN32 action |
|------|------|----------|-------|-------------|
| `0x61` 'a' | `0x0D` | `0x0A` | BT disconnected | Clear all BT flags, reset connection state |
| `0x5B` '[' | `0x43` 'C' | `0x9E` | BT connected (2.4G/type-C) | Clear `*0x200002CB`, `*0x200002CF` |
| `0x5B` '[' | `0x42` 'B' | `0x9D` | BT connected (type-B) | Set `*0x2000014E=1` (connect event) |
| `0x5B` '[' | `0x21` '!' | — | Set reconnect interval | Write 600 to `*0x20000176` |
| `0x5B` '[' | `0x22` '"' | — | Set fast timeout | Write 100 to `*0x2000017C` |
| `0x5B` '[' | `0x23` '#' | — | Clear connection | Clear `*0x20000176`, `*0x2000014A`, `*0x2000014C` |
| `0x5B` '[' | `0x31` '1' | — | BT slot 1 connected | Set channel params, call timing selector |
| `0x5B` '[' | `0x32` '2' | — | BT slot 2 connected | |
| `0x5B` '[' | `0x33` '3' | — | BT slot 3 connected | |
| `0x5C` '\' | varies | — | Brightness/speed control | `gamma_lookup(val, 0x14)` → PWM value |
| `0x5A` 'Z' | speed_byte | — | Connection speed update | Write to `*0x20001360` (BT poll interval) |
| `0x32` '2' | `0x32` '2' | — | 2.4G connected | Set `*0x20000156=1` (connected flag) |
| `0x33` '3' | `0x33` '3' | — | 2.4G disconnect | Set `*0x2000015C=1` |

---

## BT State Machine (`*0x200002CB`)

| Value | Meaning |
|-------|---------|
| 0x00 | Idle / disconnected |
| 0x03 | BT connecting |
| 0x04 | BT connecting (variant) |
| 0x05 | 2.4G connecting |
| 0x06 | BT connected (3-byte response) |
| 0x07 | BT connected (variant) |
| 0x09 | BT connected (6-byte extended) |
| 0x0C | BT connected (9-byte extended) |
| 0x0A | 2.4G connected |
| 0x10 | Special/transition mode |
| 0x22 | 2.4G connected (confirmed) |

---

## Key RAM Addresses

| Address | Purpose |
|---------|---------|
| `0x20002692` | TX packet assembly buffer |
| `0x20002670` | RX response buffer (3 bytes) |
| `0x20000153` | TX command buffer `[cmd, channel]` |
| `0x20000154` | Channel ASCII byte (written by channel selector) |
| `0x20000147` | TX busy flag (0=idle) |
| `0x2000014B` | Transfer lock flag |
| `0x2000014C` | TX lock flag |
| `0x2000014D` | Disconnect pending |
| `0x2000014E` | Connect pending |
| `0x2000014F` | Reconnect pending |
| `0x20000150` | BT name send pending |
| `0x20000151` | BT connecting flag |
| `0x20000152` | BT connected flag |
| `0x200002CB` | BT state machine (see table above) |
| `0x200002CF` | UART RX data pending flag |
| `0x20000176` | Reconnect interval (ms) |
| `0x2000017C` | Fast timeout (ms) |
| `0x20001360` | BT poll interval (from CH582F) |
| `0x20000183` | BT device name length |
| `0x2000006A` | Status flag: include 0x10 in 0xA5 command |

---

## Flash constants

| Address | Content |
|---------|---------|
| `0x19A2B` | BT device name string: `"AK820 5.1-$"` |

---

## Notes

- This protocol is only active in BT (`*0x20000164 == 1`) or 2.4G (`== 2`) mode.
- In USB mode (`*0x20000164 == 0`), UART2 is idle and CH582F is unused.
- The SN32's own USB peripheral handles HID in wired mode — CH582F is bypassed entirely.
- The `0xA9` device name packet identifies this keyboard to BT hosts as **"AK820 5.1"**.
