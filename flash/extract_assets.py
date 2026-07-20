#!/usr/bin/env python3
"""Extract the LCD image assets from the AK820 Pro stock flash image.

Each section is a run of `count` images stored back-to-back as raw RGB565,
hi-byte first (panel order), no header and no padding between frames. The
section table below was derived by hand; every entry is checked against the
next entry's offset so a wrong dimension shows up as a chain break rather
than a silently mis-decoded image.

Writes lossless PNGs plus a manifest.json that records enough to pull the
exact same bytes back out of the firmware later.
"""
import json
import os
import struct
import zlib

BASE = os.path.dirname(os.path.abspath(__file__))
STOCK = os.path.join(BASE, "LCD firmware",
                     "盛冠_SG8975_新0.85横屏_20251127_01.bin")
DUMP = os.path.join(BASE, "flash.bin")
OUT = os.path.join(BASE, "extracted")

# offset, count, width, height, name
#
# The all-zero entries are not padding: the SPI-to-SPI DMA can only stream from
# flash, never from RAM, so erasing a region needs a blank *source* in flash of
# exactly that geometry. Hence one blank per blit size that needs clearing --
# 128x128 full-screen at offset 0, plus per-icon blanks alongside their icons.
SECTIONS = [
    (0x000000,  1, 128, 128, "screen_clear_black"),
    (0x008000,  6,  31,  16, "battery"),
    (0x009740, 10,  22,  22, "status_icons"),
    (0x00BD10,  1,  31,  16, "charging_battery"),
    (0x00C0F0,  8,  22,  22, "additional_status_icons"),
    # Solid 0xFFFF -- a *white* fill source, despite the original note calling
    # this one black. 240 px, one distinct value.
    (0x00DF30,  1,  16,  15, "white_fill_16x15"),
    (0x00E110, 24, 128, 128, "chinese_menu_screens"),
    (0x0CE110,  3, 128,  54, "bt_connection_status"),
    (0x0D8310,  1, 128, 128, "usb_dongle"),
    (0x0E0310,  3, 128,  54, "dongle_connection_status"),
    (0x0EA510,  6, 128, 128, "chinese_config_menu"),
    (0x11A510,  1,  36,  22, "volume_up"),
    (0x11AB40,  1,  36,  22, "volume_up_clear"),
    (0x11B170,  1,  25,  14, "volume_down"),
    # Only 186 zero bytes here, short of a full 25x14 blank -- see chain check.
    (0x11B42C,  1,  93,   1, "volume_down_clear"),
    (0x11B4E6,  1, 128, 128, "chinese_language_menu"),
    # Text strips (128x25), not full screens -- the Chinese peer of english_text_images.
    (0x1234E6,  2, 128,  25, "chinese_text_images"),
    (0x1266E6, 16, 128, 128, "english_menu_screens"),
    (0x1A66E6,  2, 128,  25, "english_text_images"),
    # Top 7 rows of a third label, cut off where the animation starts at
    # 0x1AA000 (26 trailing bytes are not a whole row). Text is stored as
    # whole-word bitmaps throughout -- there is no glyph atlas anywhere in
    # this image, so nothing here composes strings at runtime.
    (0x1A98E6,  1, 128,   7, "text_label_truncated"),
]


# The stock image stores RGB565 lo-byte-first. Note this is the opposite of the
# hi-byte-first panel order res/mkraw.py emits in the QMK tree -- assets reused
# from here must be swapped before they are fed to the panel or the DMA.
LITTLE_ENDIAN = True


def rgb565_to_rgb888(buf, w, h):
    """Unpack RGB565 into flat RGB triples, replicating the top bits into the
    low bits so full-scale values stay full-scale."""
    out = bytearray(w * h * 3)
    for i in range(w * h):
        lo, hi = (0, 1) if LITTLE_ENDIAN else (1, 0)
        v = (buf[i * 2 + hi] << 8) | buf[i * 2 + lo]
        r = (v >> 11) & 0x1F
        g = (v >> 5) & 0x3F
        b = v & 0x1F
        out[i * 3] = (r << 3) | (r >> 2)
        out[i * 3 + 1] = (g << 2) | (g >> 4)
        out[i * 3 + 2] = (b << 3) | (b >> 2)
    return bytes(out)


def write_png(path, rgb, w, h):
    """Minimal PNG writer (stdlib zlib only -- no Pillow in this tree)."""
    raw = b"".join(b"\x00" + rgb[y * w * 3:(y + 1) * w * 3] for y in range(h))

    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c))

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 9))
           + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)


stock = open(STOCK, "rb").read()
dump = open(DUMP, "rb").read()
os.makedirs(OUT, exist_ok=True)

# The animation is relocated between firmware versions; everything below it is
# aligned 1:1, so the dump cross-check uses the same offset.
manifest = {
    "source": os.path.basename(STOCK),
    "format": "rgb565_le",
    "note": "offsets are into the stock image; the dump is byte-aligned with "
            "it below 0x1AA000",
    "sections": [],
}

# Blank regions exist to be DMA erase sources, so flag them as such rather than
# leaving a consumer to wonder why an all-black PNG is in the set.
BLANK = {"screen_clear_black", "white_fill_16x15", "volume_up_clear", "volume_down_clear"}

print(f"{'name':<26} {'offset':>9} {'count':>5} {'size':>9}  chain  dump")
print("-" * 72)

for idx, (off, count, w, h, name) in enumerate(SECTIONS):
    size = count * w * h * 2
    end = off + size

    # Chain check: does this section end where the next one begins?
    if idx + 1 < len(SECTIONS):
        nxt = SECTIONS[idx + 1][0]
        chain = "ok" if end == nxt else f"{end - nxt:+d}"
    else:
        chain = "end"

    data = stock[off:end]
    # Does the dump agree here? Anything but 0 means damage or a version delta.
    ndiff = sum(1 for x, y in zip(data, dump[off:end]) if x != y)

    d = os.path.join(OUT, name)
    os.makedirs(d, exist_ok=True)
    for i in range(count):
        fr = data[i * w * h * 2:(i + 1) * w * h * 2]
        fn = f"{name}.png" if count == 1 else f"{name}_{i:03d}.png"
        write_png(os.path.join(d, fn), rgb565_to_rgb888(fr, w, h), w, h)

    manifest["sections"].append({
        "name": name, "offset": off, "offset_hex": f"0x{off:06X}",
        "count": count, "width": w, "height": h,
        "frame_bytes": w * h * 2, "size": size,
        "dir": name, "dump_bytes_differing": ndiff,
        "role": "dma_erase_source" if name in BLANK else "image",
        "all_zero": not any(data),
    })
    print(f"{name:<26} 0x{off:06X} {count:>5} {size:>9,}  {chain:>5}  "
          f"{'clean' if ndiff == 0 else str(ndiff) + ' differ'}")

with open(os.path.join(OUT, "manifest.json"), "w") as f:
    json.dump(manifest, f, indent=2)

total = sum(s["size"] for s in manifest["sections"])
print(f"\n{len(SECTIONS)} sections, "
      f"{sum(s['count'] for s in manifest['sections'])} images, {total:,} bytes")
print(f"-> {OUT}")
