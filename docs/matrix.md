Markdown
# AK820PRO Shared-Pin Matrix Architecture & Multiplexing Guide

## 1. Hardware Overview
The AJAZZ AK820PRO uses a highly efficient shared-pin architecture to save microcontroller (MCU) pins. The column pins are shared between the mechanical switch matrix and the RGB LED matrix. 

To prevent the switch scanner and the LEDs from interfering with each other, the board relies on a mixed-logic transistor design and **Time-Division Multiplexing (TDM)**.

### Component Breakdown
* **Column Power Transistors (High-Side):** `2TY` (S8550) **PNP** Transistors. 
  * Connected to `VDD` (Power).
  * **Logic: Active-LOW**. The MCU must drive the shared column pin LOW (0V) to pull current out of the transistor's base, turning it ON and sourcing power to the LED anodes.
* **LED Row Transistors (Low-Side):** `J3Y` (S8050) **NPN** Transistors.
  * Connected to `GND` (VSS).
  * **Logic: Active-HIGH**. The MCU must drive the LED row pin HIGH (3.3V) to turn it ON, sinking the LED current to ground.
* **Isolation Diodes:** Both the switch circuits and the LED column circuits feature blocking diodes. Their **Cathodes (-)** (the side with the line) face the Shared Column Pin. This allows the Active-LOW logic from the MCU to pass through while preventing unwanted back-flow between matrix nodes.

---

## 2. Hardware Schematic (Single Key/LED Node)

```text
                           VDD (Power)
                            │
                            ▼ (Emitter)
                        ┌───────┐
                        │  2TY  │ (PNP Column Power Transistor)
              (Base)  ┌─┤ (PNP) ├─┐ (Collector)
                      │ └───────┘ │
                      │           │
                 [1K Resistor] [100 Ohm Resistor]
                      │           │
             (Anode)  │           │
             [Diode 2]            │
            (Cathode) │           │     RGB LED (e.g., Red Channel)
                      │           │   ┌─────────────┐
SHARED COLUMN PIN ────┼───────────┴───┤+ Anode      │
(From MCU: Active LO) │               │             │
            (Cathode) │    Cathode (-)├─────┐ (Collector)
             [Diode 1]                └─────│───────┘
             (Anode)  │                     │
                      │                 ┌───┴───┐
                  [ Switch ]            │  J3Y  │ (NPN Row Transistor)
                      │         (Base)┌─┤ (NPN) ├─┐ (Emitter)
                      │               │ └───────┘ │
SWITCH ROW PIN ───────┘        [1K Resistor]      │
(To MCU: Input pulled HI)             │           ▼
                                 LED ROW PIN     GND (VSS)
                            (From MCU: Active HI)
```

## 3. Multiplexing Strategy (Firmware Implementation)

Because the columns are shared, driving a column LOW activates both the LED power (via the PNP transistor) and the switch scanner (via the switch diode). The MCU must alternate rapidly between reading switches and driving LEDs.

### Phase 1: Scanning the Switches (LEDs OFF)
During this phase, the firmware checks for keystrokes. We must ensure the LEDs do not light up.

1. **Disable LED Rows**: Drive all LED Row pins **LOW** (0V). This keeps the J3Y NPN transistors turned OFF, cutting the LEDs off from ground.
2. **Arm Switch Rows**: Ensure the MCU Switch Row pins are configured as INPUT with PULL-UP (idling at 3.3V).
3. **Strobe Column**: Drive the target Shared Column pin **LOW** (0V).

- *The Physics*: This LOW signal passes through Diode 1. If the switch is pressed, it pulls the MCU Switch Row pin LOW, registering a keystroke.
- *Note*: Diode 2 also allows current to flow out of the `2TY` transistor base, turning it ON and sending power to the LED Anodes. However, because we disabled the LED Rows in Step 1, the LEDs remain dark.
4. **Read & Reset**: Read the switch row states, then drive the Shared Column pin back to **HIGH** (3.3V) to turn it off.

### Phase 2: Driving the LEDs (Switches Ignored)

Immediately after scanning the keys, the firmware switches to lighting the LEDs.

1. **Deafen Switch Scanner**: The firmware pauses the matrix scanning logic. Any LOW signals appearing on the Switch Row pins are completely ignored by the software.
2. **Activate LED Row**: Drive the target LED Row pin **HIGH** (3.3V). This opens the `J3Y` NPN transistor, connecting that specific color channel (Red, Green, or Blue) to ground.
3. **Strobe Column**: Drive the target Shared Column pin **LOW** (0V). (This is often pulsed rapidly using PWM to control color mixing and brightness).
    - The Physics: The 2TY PNP transistor turns on, dumping VDD into the LED. Because the LED Row is active, the circuit is completed and the LED lights up.
4. **Reset**: Drive the Shared Column **HIGH** and the LED Row **LOW** before looping back to Phase 1.