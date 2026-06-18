// GC9107 LCD initialization sequence for AJAZZ AK820PRO
// Derived from disassembly of fcn.00012a2e (SN32F299 stock firmware)
//
// Hardware (confirmed from disassembly):
//   SPI0:  SCK=P3.0, MOSI=P3.2, CS=P1.8 (manual GPIO, active low)
//   DC:    P3.14 (0=command, 1=data)
//   RST:   P0.17 (active low)
//   BL:    P0.16 (active low)
//
// Display offsets (from *0x20000225 after init):
//   x_offset = 1, y_offset = 2
//
// Orientation: MADCTL=0x68 → landscape, MX=1, MV=1, RGB order
// Pixel format: RGB565 (COLMOD=0x05)

// For QMK Quantum Painter, place this in your keyboard's qp_init or
// use as reference for a custom GC9107 driver init sequence.

// Reset sequence (confirmed timings from disassembly):
//   RST HIGH → 20ms → RST LOW → 20ms → RST HIGH → 200ms
//   BL LOW during init (backlight off)
//   CS HIGH (deasserted) throughout init

// --- GC9107 register init sequence ---
// Format: {cmd_or_data, value}
// 0x00 prefix = command (DC=0), 0x01 prefix = data (DC=1)

static const uint8_t gc9107_init_sequence[] = {
    // Sleep Out
    GC9107_CMD, 0x11,
    // No params for SLPOUT — next bytes are separate commands:

    // Frame Rate Control (Normal mode) — B1
    GC9107_CMD, 0xB1,
    GC9107_DAT, 0x05,   // RTNA = 5
    GC9107_DAT, 0x3A,   // FPA = 58 (front porch)
    GC9107_DAT, 0x3A,   // BPA = 58 (back porch)

    // Frame Rate Control (Idle mode) — B2
    GC9107_CMD, 0xB2,
    GC9107_DAT, 0x05,
    GC9107_DAT, 0x3A,
    GC9107_DAT, 0x3A,

    // Frame Rate Control (Partial mode) — B3
    GC9107_CMD, 0xB3,
    GC9107_DAT, 0x05,
    GC9107_DAT, 0x3A,
    GC9107_DAT, 0x3A,
    GC9107_DAT, 0x05,
    GC9107_DAT, 0x3A,
    GC9107_DAT, 0x3A,

    // Display Inversion Control — B4
    GC9107_CMD, 0xB4,
    GC9107_DAT, 0x03,   // Dot inversion all modes

    // Power Control 1 — C0
    GC9107_CMD, 0xC0,
    GC9107_DAT, 0x62,   // VREG1OUT = 4.65V
    GC9107_DAT, 0x02,
    GC9107_DAT, 0x04,

    // Power Control 2 — C1
    GC9107_CMD, 0xC1,
    GC9107_DAT, 0xC0,   // VGH=VCI*4, VGL=-VCI*3

    // Power Control 3 (Normal mode) — C2
    GC9107_CMD, 0xC2,
    GC9107_DAT, 0x0D,
    GC9107_DAT, 0x00,

    // Power Control 4 (Idle mode) — C3
    GC9107_CMD, 0xC3,
    GC9107_DAT, 0x8D,
    GC9107_DAT, 0x6A,

    // Power Control 5 (Partial mode) — C4
    GC9107_CMD, 0xC4,
    GC9107_DAT, 0x8D,
    GC9107_DAT, 0xEE,

    // VCOM Control — C5
    GC9107_CMD, 0xC5,
    GC9107_DAT, 0x12,   // VCOMH = 3.675V

    // Memory Access Control — MADCTL
    GC9107_CMD, 0x36,
    GC9107_DAT, 0x68,   // MX=1, MV=1, BGR=0 → landscape, RGB order

    // Positive Voltage Gamma — E0
    GC9107_CMD, 0xE0,
    GC9107_DAT, 0x03,
    GC9107_DAT, 0x1B,
    GC9107_DAT, 0x12,
    GC9107_DAT, 0x11,
    GC9107_DAT, 0x3F,
    GC9107_DAT, 0x3A,
    GC9107_DAT, 0x32,
    GC9107_DAT, 0x34,
    GC9107_DAT, 0x2F,
    GC9107_DAT, 0x2B,
    GC9107_DAT, 0x30,
    GC9107_DAT, 0x3A,
    GC9107_DAT, 0x00,
    GC9107_DAT, 0x01,
    GC9107_DAT, 0x02,
    GC9107_DAT, 0x05,

    // Negative Voltage Gamma — E1
    GC9107_CMD, 0xE1,
    GC9107_DAT, 0x03,
    GC9107_DAT, 0x1B,
    GC9107_DAT, 0x12,
    GC9107_DAT, 0x11,
    GC9107_DAT, 0x32,
    GC9107_DAT, 0x2F,
    GC9107_DAT, 0x2A,
    GC9107_DAT, 0x2F,
    GC9107_DAT, 0x2E,
    GC9107_DAT, 0x2C,
    GC9107_DAT, 0x35,
    GC9107_DAT, 0x3F,
    GC9107_DAT, 0x00,
    GC9107_DAT, 0x00,
    GC9107_DAT, 0x01,
    GC9107_DAT, 0x05,

    // Interface Pixel Format — COLMOD
    GC9107_CMD, 0x3A,
    GC9107_DAT, 0x05,   // RGB565

    // Display On
    GC9107_CMD, 0x29,

    // Memory Write (trigger pixel data start)
    GC9107_CMD, 0x2C,

    // Display Inversion On
    GC9107_CMD, 0x21,

    // Memory Write again
    GC9107_CMD, 0x2C,
};

// Display window set function (CASET + RASET + RAMWR)
// Confirmed from fcn.00012904 disassembly
// x_offset=1, y_offset=2 must be added to all coordinates
#define GC9107_X_OFFSET 1
#define GC9107_Y_OFFSET 2
#define GC9107_WIDTH    128
#define GC9107_HEIGHT   128

// Quantum Painter driver hint:
// Use qp_gc9107_make_spi_device() with:
//   width=128, height=128 (confirmed panel dimensions)
//   rotation=QP_ROTATION_270 (MADCTL=0x68 = landscape via MX+MV)
//   offset_x=1, offset_y=2
//   invert_colors=true (INVON sent during init)
//
// SPI config:
//   mode=0 (CPOL=0, CPHA=0)
//   MSB first
//   clock: start at 4-8MHz for init, can increase to 24MHz for data
