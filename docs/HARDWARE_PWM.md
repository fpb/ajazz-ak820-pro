# Hardware-PWM RGB for the AK820 Pro (SN32F299)

Status: **IMPLEMENTED and working** on branch `ak820pro-rgbhw` (off `ak820pro-rgbsoft`).
All 15 columns are driven by hardware PWM spread over CT16B0+B1+B2 — zero-CPU, correct
colours, no flicker. The ChibiOS (submodule) changes are captured as
`keyboards/a_jazz/ak820pro/hardware_pwm.diff`; the board opts in via
`SN32F2XX_PWM_MULTI_TIMER` + `SN32F2XX_PWM_COL_MAP` + `SN32F2XX_PWM_PFPA_CT16B{0,1,2}`.
Software PWM (`ak820pro-rgbsoft`) still exists and also works.

The routing/channel-map/PFPA design below all held up on hardware. What the original
sketch got **wrong** was the difficulty: CT16B0/B2 are a *different peripheral* than
CT16B1 (see "Register-model gotchas" at the end), and synchronisation was NOT trivial.

## Why hardware PWM is non-trivial here

The RGB matrix drives brightness on the **15 columns** (COL2ROW), multiplexing the
18 LED rows (6 key-rows x R,B,G). Hardware PWM needs **one PWM channel per column,
all active at once** (15 channels) while a single row is lit.

The SonixQMK `drivers/led/sn32f2xx.c` + ChibiOS `hal_pwm_lld.c` drive a **single
timer, CT16B1**. On the SN32F299/F290, CT16B1 has only **12 usable PWM channels**
(`SN32_CT16B1_CHANNELS = 13`, minus one for the period). 15 > 12, and the driver's
`channel = pio_value % PWM_CHANNELS` mapping collides by pigeonhole. So single-timer
hardware PWM is impossible.

F290 spreads PWM over **six** CT16 timers (CT16B0..B5). CT16B1 has 12 channels; the
others are small (B0/B2/B4/B5 = 4 PWM outputs each; B3 = 2). Hardware PWM therefore
requires **multi-timer** support.

## The channel-count minimisation (solved: 3 timers)

Per-column PFPA options (from the SN32F299 datasheet pin-mux table). `Bx.y` =
CT16Bx PWM channel y:

| Col | Options |
|-----|---------|
| A4  | B1.4 |
| A5  | B1.5 |
| C0  | B1.8, B2.0 |
| C1  | B2.1 |
| C2  | B2.2, B3.0 |
| C3  | B2.3, B3.1 |
| A6  | B1.6 |
| A7  | B1.7 |
| C4  | B1.9 |
| C5  | B0.1, B2.0, B4.1 |
| C6  | B0.0, B3.0, B4.1, B5.0 |
| C7  | B0.2, B1.10, B4.0, B5.1 |
| C14 | B0.3 |
| C8  | B0.2, B5.2 |
| C9  | B0.1, B1.11, B5.3 |

Single-option columns force **CT16B0** (C14), **CT16B1** (A4/A5/A6/A7/C4), and
**CT16B2** (C1) — so **3 timers is the floor**. It is also achievable (C6's `B0.0`
option keeps everything on B0/B1/B2). CT16B0 ends up exactly full, so 3 is minimal.

### Final column -> (timer, channel) map

| Column | Timer.ch | Column | Timer.ch |
|--------|----------|--------|----------|
| A4  | B1.4 | C5  | B0.1 |
| A5  | B1.5 | C6  | B0.0 |
| C0  | B1.8 | C7  | B1.10 |
| C1  | B2.1 | C14 | B0.3 |
| C2  | B2.2 | C8  | B0.2 |
| C3  | B2.3 | C9  | B1.11 |
| A6  | B1.6 |     |      |
| A7  | B1.7 |     |      |
| C4  | B1.9 |     |      |

Per timer (all channels distinct, within capacity):
- **CT16B0** — 0(C6), 1(C5), 2(C8), 3(C14)  -> 4/4 (full)
- **CT16B1** — 4,5,6,7,8,9,10,11 (A4,A5,A6,A7,C0,C4,C7,C9) -> 8/12
- **CT16B2** — 1(C1), 2(C2), 3(C3) -> 3/4

## Implementation sketch

### 1. mcuconf.h
```c
#define SN32_PWM_USE_CT16B0 TRUE
#define SN32_PWM_USE_CT16B1 TRUE
#define SN32_PWM_USE_CT16B2 TRUE
// Remove SN32_PWM_NO_RESET: hardware PWM wants the period match to auto-reset the
// counter (software PWM needed the manual reset; hardware does not).
```

### 2. ChibiOS LLD (`hal_pwm_lld.c`) — the bulk of the work
1. **Instantiate PWMD0/PWMD2** — mirror the `#if SN32_PWM_USE_CT16B1` blocks:
   `PWMDriver PWMD0, PWMD2;`, their `OSAL_IRQ_HANDLER`s ->
   `pwm_lld_serve_interrupt(&PWMDx)`, and `sys1EnableCT16Bx()` / reset / NVIC in
   `pwm_lld_start`.
2. **De-hardcode `PWM_CHANNELS`** (crux). The file uses the single macro everywhere
   (channel loops, period register `MR[PWM_CHANNELS]`, PFPA loop). B0/B2 have only 4
   channels. Replace with **`pwmp->channels`** (already per-driver from
   `pwm_lld_init`), so each timer uses its own count and its own period register
   `MR[pwmp->channels]`.
3. **F290 PFPA** — the existing block is `#if defined(SN32F240B/240C)` and uses 1-bit
   A/B selectors (`SN_PFPA->CT16B1 |= (1<<i)`). F290's PFPA differs: CT16B1 is 1-bit
   per channel, but CT16B0/B2 are **2-bit per channel** (`PWMn : 2`), one register per
   timer (`SN_PFPA->CT16B0/B1/B2`, base 0x40042000). The exact selector values are
   solved below (datasheet-verified against SN32F299 sec. 6.4; pin notation
   P0=A,P1=B,P2=C,P3=D). For this fixed column set the three writes are constant:
```c
   // ch0->P2.6(C6)=0b10, ch1->P2.5(C5)=0b11, ch2->P2.8(C8)=0b11, ch3->P2.14(C14)=0b11
   SN_PFPA->CT16B0 = 0x3332;
   // ch4..7->P0.4..7(A4..A7)=0, ch8->P2.0(C0)=1, ch9->P2.4(C4)=1, ch10->P2.7(C7)=1, ch11->P2.9(C9)=1
   SN_PFPA->CT16B1 = 0x0F00;
   // ch1->P2.1(C1)=00, ch2->P2.2(C2)=00, ch3->P2.3(C3)=00 (all the default 00 option)
   SN_PFPA->CT16B2 = 0x0000;
```
   (In the generalised LLD these would be computed per-channel from the config; the
   constants above are the target result.)

#### Full PFPA verification (datasheet sec. 6.4)
Every column's target pin is a valid PFPA option for its assigned channel:

| Col (pin) | Timer.ch | PFPA field | Selector | code |
|-----------|----------|------------|----------|------|
| C6 (P2.6)  | B0.0  | CT16B0 PWM0[1:0]   | P2.6  | 10 |
| C5 (P2.5)  | B0.1  | CT16B0 PWM1[5:4]   | P2.5  | 11 |
| C8 (P2.8)  | B0.2  | CT16B0 PWM2[9:8]   | P2.8  | 11 |
| C14 (P2.14)| B0.3  | CT16B0 PWM3[13:12] | P2.14 | 11 |
| A4 (P0.4)  | B1.4  | CT16B1 PWM04[4]    | P0.4  | 0  |
| A5 (P0.5)  | B1.5  | CT16B1 PWM05[5]    | P0.5  | 0  |
| A6 (P0.6)  | B1.6  | CT16B1 PWM06[6]    | P0.6  | 0  |
| A7 (P0.7)  | B1.7  | CT16B1 PWM07[7]    | P0.7  | 0  |
| C0 (P2.0)  | B1.8  | CT16B1 PWM08[8]    | P2.0  | 1  |
| C4 (P2.4)  | B1.9  | CT16B1 PWM09[9]    | P2.4  | 1  |
| C7 (P2.7)  | B1.10 | CT16B1 PWM10[10]   | P2.7  | 1  |
| C9 (P2.9)  | B1.11 | CT16B1 PWM11[11]   | P2.9  | 1  |
| C1 (P2.1)  | B2.1  | CT16B2 PWM1[3:2]   | P2.1  | 00 |
| C2 (P2.2)  | B2.2  | CT16B2 PWM2[5:4]   | P2.2  | 00 |
| C3 (P2.3)  | B2.3  | CT16B2 PWM3[7:6]   | P2.3  | 00 |

No open items remain: routing, channel map, and PFPA codes are all fixed.

### 3. QMK driver (`sn32f2xx.c`) — spread columns over 3 drivers
Replace the single `chan_col_order[]`/`PWMD1` model with the solved table:
```c
// index = column index in SN32F2XX_RGB_MATRIX_COL_PINS order
static const struct { PWMDriver *drv; uint8_t ch; } col_pwm[15] = {
    {&PWMD1,4}, {&PWMD1,5}, {&PWMD1,8}, {&PWMD2,1}, {&PWMD2,2}, {&PWMD2,3}, // A4,A5,C0,C1,C2,C3
    {&PWMD1,6}, {&PWMD1,7}, {&PWMD1,9}, {&PWMD0,1}, {&PWMD0,0}, {&PWMD1,10},// A6,A7,C4,C5,C6,C7
    {&PWMD0,3}, {&PWMD0,2}, {&PWMD1,11},                                    // C14,C8,C9
};
```
- **Config**: one `PWMConfig` per timer; mark each used channel with the active level,
  the rest `PWM_OUTPUT_DISABLED`; set mode/pfpamsk so `pwm_lld_start` programs PFPA.
- **Scan** (`update_pwm_channels`, HARDWARE_PWM path): change
  `pwmEnableChannel(pwmp, chan_col_order[col], v)` ->
  `pwmEnableChannel(col_pwm[col].drv, col_pwm[col].ch, v)`.
- **Row mux** (18 GPIO rows) is unchanged.

### 4. Start-up and the scan tick — the sync is NOT "just co-locate pwmStart"
This was the sketch's key wrong assumption. On this driver PWMD1's PWM cycle is **not**
free-running on its hardware MR reset — `rgb_callback` re-arms PWMD1's counter to
`UINT16_MAX` every period, and *that* ISR re-arm is what phase-locks B1's PWM to the row
scan. Aux timers left on their own hardware reset free-run and drift against B1's
ISR-driven cadence → **irregular flicker + a one-phase colour rotation (R→Y, G→C, B→M)**.

Fix: re-arm all three counters on the same boundary, inside the callback:
```c
pwm_lld_change_counter(pwmp,   UINT16_MAX);   // PWMD1 (existing)
pwm_lld_change_counter(&PWMD0, UINT16_MAX);   // aux timers, same boundary
pwm_lld_change_counter(&PWMD2, UINT16_MAX);
```
A one-off counter align at init only *reduced* the drift; the per-cycle re-arm removes it.
Only PWMD1 owns the period-match callback (advances the LED row, reloads all 15 duties).

## Register-model gotchas (SN32F290) — why CT16B0/B2 ≠ CT16B1
CT16B0/B2 are a *different peripheral* than CT16B1, verified against sec 10.8:
- **CT16B0 is the ChibiOS OS-tick counter** (`SN32_ST_USE_TIMER` default). Reusing it for
  PWM ran the clock/animations fast → move the tick counter to unused **CT16B5**
  (`#define SN32_ST_USE_TIMER SN32_TIM_CT16B5`; the tick *interrupt* is always the ARM
  SysTick, only the counter is a CT16). Unavoidable: col C14 can only route to CT16B0.3.
- **Write-protect key:** MR / PWMCTRL / MCTRL of every CT16 *except* CT16B1 ignore writes
  unless `0x5A` is in bits[31:24]. CT16B1 is unlocked.
- **No PWMENB/PWMIOENB** on B0/B2/B5 (CT16B1 only). Enable + IO-enable + mode all live in
  the single **PWMCTRL** (0x98): PWMnEN bit n, PWMnMODE bits[4+2n], PWMnIOEN bits[20+n].
- **Period register is MR9**, not MR[channels] (=MR4). MCTRL exposes only MR0-3 + MR9;
  MR9RST is bit 22.

## Payoff and what becomes removable
Brightness is generated in silicon: no continuously-running software-PWM ISR, so the
CPU is freed. That removes the flicker/typing tradeoff entirely and lets you revert:
- `SN32F2XX_PWM_CONTROL` -> `HARDWARE_PWM` (drop the `rgb_callback` bit-bang loop),
- the LCD per-second-flush throttling (was needed to feed the software scan),
- the `HUE_STEP=2` / `LED_PROCESS_LIMIT` tuning.

## Effort / risk summary (in hindsight)
- **Bulk**: the LLD generalisation (B0/B2 drivers + `pwmp->channels` + the whole
  PWMCTRL-only register model + MR9 period + `0x5A` keying + aux re-arm sync).
- **The design data was right**: routing, column->(timer,channel) map, and PFPA
  register values were all correct on hardware.
- **What was underestimated**: the per-timer register-model differences and the
  synchronisation (six datasheet-driven fixes, each a hardware flash-test round). The
  "shared-clock timers don't drift" claim was false in practice — they needed the
  per-cycle ISR re-arm.
- Touches vendored ChibiOS + the shared QMK driver, so it should be **upstreamed to
  SonixQMK** — multi-timer + F290 register-model support would benefit any SN32F290 RGB
  board.
- Verdict: a real driver project, done. Software PWM also still ships and works.
