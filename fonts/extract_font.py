#!/usr/bin/env python3
"""Extract the 8x16 ASCII bitmap font from the AK820 Pro stock MCU firmware.

Found by density-scanning the firmware (the font sits in a sparse 0.16
bit-density region among ~0.40-0.49 code) and then testing row strides for
vertical correlation.

Two things make this font easy to misread:
  * bit order is LSB-first -- rendering MSB-first gives mirrored glyphs, which
    stay legible enough to look almost right;
  * glyphs are 8px wide -- laid out in 16px cells the letters appear doubled.

Emits a raw .bin, a per-glyph contact sheet, and a C table for QMK.
"""
import os
import struct
import zlib

BASE = os.path.dirname(os.path.abspath(__file__))
FW = os.path.join(BASE, "..", "StockFWBinaries",
                  "AJAZZ_AK820PRO_PID_8009_V1.13_SN32F290.bin")

FONT_OFF = 0x1AD0D      # ASCII 0x20 (space); verified by row-ink profile
GW, GH = 8, 16
FIRST, COUNT = 0x20, 96
GLYPH_BYTES = GH        # 1 byte per row at 8px wide


def png(path, rgb, w, h):
    raw = b"".join(b"\x00" + rgb[y * w * 3:(y + 1) * w * 3] for y in range(h))

    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c))

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n"
                + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw, 9))
                + chunk(b"IEND", b""))


def sheet(data, cols, scale, path, gap=1):
    """Contact sheet: every glyph in ASCII order, one cell each."""
    rows = (COUNT + cols - 1) // cols
    W, H = cols * (GW + gap) * scale, rows * (GH + gap) * scale
    out = bytearray(W * H * 3)
    for g in range(COUNT):
        gx, gy = (g % cols) * (GW + gap), (g // cols) * (GH + gap)
        for y in range(GH):
            b = data[g * GLYPH_BYTES + y]
            for x in range(GW):
                if (b >> x) & 1:                      # LSB-first
                    for dy in range(scale):
                        for dx in range(scale):
                            i = (((gy + y) * scale + dy) * W
                                 + ((gx + x) * scale + dx)) * 3
                            out[i] = out[i + 1] = out[i + 2] = 255
    png(path, bytes(out), W, H)
    return W, H


fw = open(FW, "rb").read()
data = fw[FONT_OFF:FONT_OFF + COUNT * GLYPH_BYTES]

with open(os.path.join(BASE, "ascii_8x16.bin"), "wb") as f:
    f.write(data)

sheet(data, 16, 6, os.path.join(BASE, "ascii_8x16.png"))
sheet(data, 32, 3, os.path.join(BASE, "ascii_8x16_strip.png"))

with open(os.path.join(BASE, "ascii_8x16.c"), "w") as f:
    f.write("// 8x16 ASCII font lifted from AK820 Pro stock firmware V1.13\n"
            f"// (offset 0x{FONT_OFF:05X}). Bit order is LSB-first: bit 0 is the\n"
            "// leftmost pixel, so shift with (b >> x) & 1, not (b >> (7-x)) & 1.\n"
            f"// {COUNT} glyphs, ASCII 0x{FIRST:02X}..0x{FIRST + COUNT - 1:02X},"
            f" {GLYPH_BYTES} bytes each.\n\n"
            "#include <stdint.h>\n\n"
            f"#define FONT_FIRST_CHAR 0x{FIRST:02X}\n"
            f"#define FONT_GLYPH_COUNT {COUNT}\n"
            f"#define FONT_WIDTH {GW}\n#define FONT_HEIGHT {GH}\n\n"
            f"const uint8_t font_8x16[{COUNT}][{GLYPH_BYTES}] = {{\n")
    for g in range(COUNT):
        ch = chr(FIRST + g)
        label = "space" if ch == " " else ch
        row = ", ".join(f"0x{b:02X}" for b in
                        data[g * GLYPH_BYTES:(g + 1) * GLYPH_BYTES])
        f.write(f"    {{ {row} }},  // 0x{FIRST + g:02X} {label}\n")
    f.write("};\n")

print(f"font @ 0x{FONT_OFF:05X}  {COUNT} glyphs  {GW}x{GH}  {len(data)} bytes")
for n in ("ascii_8x16.bin", "ascii_8x16.png", "ascii_8x16_strip.png",
          "ascii_8x16.c"):
    p = os.path.join(BASE, n)
    print(f"  {n:<22} {os.path.getsize(p):>7,} bytes")
