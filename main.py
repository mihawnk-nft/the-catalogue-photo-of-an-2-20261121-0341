#!/usr/bin/env python3
"""The Invisible Ink Printer - make.fun the-catalogue-photo-of-an-2-20261121-0341.

A catalogue photograph of an impossible gadget, drawn procedurally and
written to /output/entry.png. Pure Python stdlib, no network, deterministic.

The gadget: a sleek studio-shot printer whose only output is a perfectly
blank page - it prints in invisible ink. One accessory sharpens the joke:
a cartridge of invisible ink standing beside it.
"""

import math
import os
import struct
import zlib

W, H = 1024, 1024
OUT = "/output/entry.png"

buf = bytearray(W * H * 3)


# ---------------------------------------------------------------- colors
def mix(c1, c2, t):
    return (round(c1[0] + (c2[0] - c1[0]) * t),
            round(c1[1] + (c2[1] - c1[1]) * t),
            round(c1[2] + (c2[2] - c1[2]) * t))


def _row_bytes(color, width):
    return bytes(color) * width


def put_pixel(x, y, color):
    if 0 <= x < W and 0 <= y < H:
        i = (y * W + x) * 3
        buf[i:i + 3] = bytes(color)


def fill_rect(x0, y0, x1, y1, color):
    x0 = max(0, int(x0)); y0 = max(0, int(y0))
    x1 = min(W, int(x1)); y1 = min(H, int(y1))
    if x1 <= x0 or y1 <= y0:
        return
    row = _row_bytes(color, x1 - x0)
    for y in range(y0, y1):
        i = (y * W + x0) * 3
        buf[i:i + len(row)] = row


def vgrad_rect(x0, y0, x1, y1, top, bottom):
    """Vertical gradient rectangle, slice-filled row by row (fast)."""
    x0 = max(0, int(x0)); y0 = max(0, int(y0))
    x1 = min(W, int(x1)); y1 = min(H, int(y1))
    if x1 <= x0 or y1 <= y0:
        return
    span = max(1, y1 - y0 - 1)
    for y in range(y0, y1):
        c = mix(top, bottom, (y - y0) / span)
        row = _row_bytes(c, x1 - x0)
        i = (y * W + x0) * 3
        buf[i:i + len(row)] = row


def hgrad_rect(x0, y0, x1, y1, left, right):
    x0 = max(0, int(x0)); y0 = max(0, int(y0))
    x1 = min(W, int(x1)); y1 = min(H, int(y1))
    if x1 <= x0 or y1 <= y0:
        return
    width = x1 - x0
    for x in range(x0, x1):
        c = mix(left, right, (x - x0) / max(1, width - 1))
        col = _row_bytes(c, 1)
        for y in range(y0, y1):
            i = (y * W + x) * 3
            buf[i:i + 3] = col


def fill_ellipse(cx, cy, rx, ry, color):
    for y in range(max(0, int(cy - ry)), min(H, int(cy + ry) + 1)):
        dy = (y - cy) / ry
        if abs(dy) >= 1:
            continue
        dx = rx * math.sqrt(1 - dy * dy)
        fill_rect(cx - dx, y, cx + dx + 1, y + 1, color)


def ellipse_rows(cx, cy, rx, ry, color_fn):
    """Ellipse filled with a per-row color from color_fn(y)."""
    for y in range(max(0, int(cy - ry)), min(H, int(cy + ry) + 1)):
        dy = (y - cy) / ry
        if abs(dy) >= 1:
            continue
        dx = rx * math.sqrt(1 - dy * dy)
        fill_rect(cx - dx, y, cx + dx + 1, y + 1, color_fn(y))


def polygon(points, color):
    """Scanline-filled polygon (solid color)."""
    if len(points) < 3:
        return
    ys = [p[1] for p in points]
    y0, y1 = max(0, int(min(ys))), min(H, int(max(ys)) + 1)
    n = len(points)
    for y in range(y0, y1):
        xs = []
        for i in range(n):
            x1, y1p = points[i]
            x2, y2p = points[(i + 1) % n]
            if (y1p <= y < y2p) or (y2p <= y < y1p):
                t = (y - y1p) / (y2p - y1p)
                xs.append(x1 + t * (x2 - x1))
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            fill_rect(xs[i], y, xs[i + 1] + 1, y + 1, color)


def polygon_vgrad(points, top, bottom, y_top, y_bot):
    """Polygon filled with a vertical gradient between y_top and y_bot."""
    if len(points) < 3:
        return
    ys = [p[1] for p in points]
    y0, y1 = max(0, int(min(ys))), min(H, int(max(ys)) + 1)
    n = len(points)
    for y in range(y0, y1):
        xs = []
        for i in range(n):
            x1, y1p = points[i]
            x2, y2p = points[(i + 1) % n]
            if (y1p <= y < y2p) or (y2p <= y < y1p):
                t = (y - y1p) / (y2p - y1p)
                xs.append(x1 + t * (x2 - x1))
        xs.sort()
        c = mix(top, bottom, (y - y_top) / max(1, y_bot - y_top))
        for i in range(0, len(xs) - 1, 2):
            fill_rect(xs[i], y, xs[i + 1] + 1, y + 1, c)


def rrect(x0, y0, x1, y1, r, color):
    """Filled rounded rectangle (solid color)."""
    x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
    r = min(r, (x1 - x0) // 2, (y1 - y0) // 2)
    fill_rect(x0 + r, y0, x1 - r, y1, color)
    fill_rect(x0, y0 + r, x0 + r, y1 - r, color)
    fill_rect(x1 - r, y0 + r, x1, y1 - r, color)
    for cx, cy in ((x0 + r, y0 + r), (x1 - r, y0 + r),
                   (x0 + r, y1 - r), (x1 - r, y1 - r)):
        for y in range(cy - r, cy + r + 1):
            dy = (y - cy) / r
            if abs(dy) >= 1:
                continue
            dx = r * math.sqrt(1 - dy * dy)
            if cx < x0 + r or (cx > x1 - r and cy < y0 + r):
                pass
            # left corners fill from cx-dx..cx ; right corners cx..cx+dx
            if cx == x0 + r:
                fill_rect(cx - dx, y, cx + 1, y + 1, color)
            else:
                fill_rect(cx, y, cx + dx + 1, y + 1, color)


def rrect_vgrad(x0, y0, x1, y1, r, top, bottom):
    """Rounded rect with vertical gradient: draw per-row slices."""
    x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
    r = min(r, (x1 - x0) // 2, (y1 - y0) // 2)
    for y in range(y0, y1):
        c = mix(top, bottom, (y - y0) / max(1, y1 - y0 - 1))
        if y < y0 + r:
            dy = (y - (y0 + r)) / r
            dx = r * math.sqrt(max(0.0, 1 - dy * dy))
            fill_rect(x0 + r - dx, y, x1 - r + dx + 1, y + 1, c)
        elif y >= y1 - r:
            dy = (y - (y1 - r)) / r
            dx = r * math.sqrt(max(0.0, 1 - dy * dy))
            fill_rect(x0 + r - dx, y, x1 - r + dx + 1, y + 1, c)
        else:
            fill_rect(x0, y, x1, y + 1, c)


def soft_shadow(cx, cy, rx, ry, strength=0.30, bands=5):
    """Layered translucent-look shadow: nested ellipses, each a pre-blend
    of black over the background gradient at that row."""
    bg_top, bg_bot = (245, 242, 237), (220, 215, 206)
    for b in range(bands, 0, -1):
        t = b / bands
        rrx, rry = rx * t, ry * t
        alpha = strength * (1.0 - t * 0.55) / bands * 1.6

        def color_fn(y, alpha=alpha):
            bg = mix(bg_top, bg_bot, y / (H - 1))
            return mix(bg, (60, 55, 48), min(0.55, alpha))

        ellipse_rows(cx, cy, rrx, rry, color_fn)


# ------------------------------------------------------------------- font
# 5x7 bitmap font, only the glyphs the artwork needs.
FONT = {
    "A": (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "B": ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    "C": (".####", "#....", "#....", "#....", "#....", "#....", ".####"),
    "E": ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    "F": ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    "G": (".####", "#....", "#....", "#.###", "#...#", "#...#", ".###."),
    "H": ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "I": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"),
    "K": ("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
    "L": ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
    "N": ("#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"),
    "O": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "P": ("####.", "#...#", "#...#", "####.", "#....", "#....", "#...."),
    "R": ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    "S": (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    "T": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    "V": ("#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."),
    "Y": ("#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."),
    "0": (".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."),
    "%": ("#...#", "#..#.", "...#.", "..#..", ".#...", "#..#.", "#...#"),
    ".": (".....", ".....", ".....", ".....", ".....", "..##.", "..##."),
    "-": (".....", ".....", ".....", "#####", ".....", ".....", "....."),
    " ": (".....", ".....", ".....", ".....", ".....", ".....", "....."),
}


def text_width(s, scale):
    return len(s) * (6 * scale) - scale


def draw_text(s, x, y, scale, color):
    cx = x
    for ch in s:
        glyph = FONT.get(ch.upper(), FONT[" "])
        for row, bits in enumerate(glyph):
            for col, bit in enumerate(bits):
                if bit == "#":
                    fill_rect(cx + col * scale, y + row * scale,
                              cx + (col + 1) * scale, y + (row + 1) * scale,
                              color)
        cx += 6 * scale


# ------------------------------------------------------------------ scene
def draw_scene():
    # 1. Studio backdrop: warm vertical gradient + soft glow top-centre.
    vgrad_rect(0, 0, W, H, (246, 243, 238), (219, 214, 205))
    # Floor line: the backdrop meets the floor with a faint horizon.
    fill_rect(0, 800, W, 802, (198, 192, 182))
    vgrad_rect(0, 802, W, H, (208, 202, 192), (196, 190, 179))

    # 2. Soft shadows on the floor.
    soft_shadow(500, 812, 400, 40, strength=0.30)
    soft_shadow(890, 812, 78, 16, strength=0.28)

    # 3. The accessory: ONE invisible-ink cartridge, standing right.
    #    Body: dark navy, slight vertical shading, rounded top cap.
    rrect_vgrad(842, 652, 940, 802, 10, (52, 62, 78), (30, 36, 48))
    rrect(852, 640, 930, 660, 6, (38, 46, 60))          # cap
    fill_rect(852, 660, 930, 664, (88, 100, 120))        # cap seam
    #    Label band.
    fill_rect(846, 690, 936, 776, (244, 242, 236))
    #    Label text.
    draw_text("INVISIBLE", 846 + (90 - text_width("INVISIBLE", 1)) // 2,
              700, 1, (35, 40, 52))
    draw_text("INK", 846 + (90 - text_width("INK", 1)) // 2, 712, 1,
              (35, 40, 52))
    #    Droplet outline: teal drop, hollowed by a smaller label-coloured one.
    fill_ellipse(891, 742, 13, 16, (47, 168, 160))
    polygon([(891, 720), (880, 742), (902, 742)], (47, 168, 160))
    fill_ellipse(891, 744, 8, 10, (244, 242, 236))
    polygon([(891, 728), (885, 744), (897, 744)], (244, 242, 236))
    #    Cartridge highlight edge.
    fill_rect(846, 652, 849, 802, (96, 108, 128))

    # 4. The printer: 3/4 studio view, matte white body.
    #    Right side face (darker, recedes).
    polygon_vgrad([(760, 480), (818, 424), (818, 724), (760, 780)],
                  (214, 210, 202), (178, 172, 162), 424, 780)
    #    Top face (lightest).
    polygon_vgrad([(200, 480), (258, 424), (818, 424), (760, 480)],
                  (253, 251, 247), (232, 228, 220), 424, 480)
    #    Top lid panel + control button (subtle seam, same family as top).
    polygon([(300, 468), (340, 438), (700, 438), (660, 468)],
            (240, 237, 229))
    fill_ellipse(720, 452, 16, 7, (52, 52, 58))          # round button
    fill_ellipse(720, 452, 10, 4, (84, 84, 92))
    fill_ellipse(688, 451, 6, 3, (55, 201, 120))         # green LED on top
    #    Front face.
    rrect_vgrad(200, 480, 760, 780, 14, (251, 249, 244), (226, 222, 213))
    #    Top edge highlight + lid seam.
    fill_rect(204, 482, 756, 486, (255, 255, 255))
    fill_rect(204, 500, 756, 503, (214, 209, 200))
    #    Brand text on the product (text belongs to the product).
    brand = "INVISIBLE INK"
    draw_text(brand, 480 - text_width(brand, 4) // 2, 548, 4, (58, 58, 64))
    tag = "PRINTS NOTHING - PERFECTLY"
    draw_text(tag, 480 - text_width(tag, 2) // 2, 606, 2, (110, 105, 96))
    model = "PRT-0"
    draw_text(model, 480 - text_width(model, 2) // 2, 640, 2, (140, 135, 126))
    #    Status LED on the front.
    fill_ellipse(700, 566, 8, 8, (55, 201, 120))
    fill_ellipse(698, 564, 3, 3, (190, 245, 210))

    # 5. The blank page, emerging from the output slot (caught mid-use).
    polygon_vgrad([(296, 700), (664, 700), (704, 872), (262, 872)],
                  (255, 255, 255), (238, 236, 230), 700, 872)
    fill_rect(262, 868, 704, 872, (206, 202, 194))       # page bottom edge
    polygon([(664, 700), (704, 872), (696, 872), (660, 700)],
            (214, 211, 204))                             # page right edge
    #    Soft shadow the page casts on the floor.
    soft_shadow(483, 880, 220, 12, strength=0.18)

    # 6. Output slot drawn OVER the top of the page: the page comes out of it.
    rrect(258, 686, 702, 712, 8, (38, 38, 44))
    rrect(266, 692, 694, 700, 4, (18, 18, 22))
    fill_rect(258, 712, 702, 715, (255, 255, 255))       # lip highlight


# -------------------------------------------------------------------- png
def save_png(path):
    raw = bytearray()
    stride = W * 3
    for y in range(H):
        raw.append(0)  # filter: none
        raw += buf[y * stride:(y + 1) * stride]
    data = zlib.compress(bytes(raw), 9)

    def chunk(kind, payload):
        c = struct.pack(">I", len(payload)) + kind + payload
        return c + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", data) + chunk(b"IEND", b""))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


def main():
    draw_scene()
    size = save_png(OUT)
    if size > 1024 * 1024:
        raise ValueError("output exceeds 1 MiB: %d bytes" % size)
    print("wrote %s (%d bytes, %dx%d)" % (OUT, size, W, H))


if __name__ == "__main__":
    main()
