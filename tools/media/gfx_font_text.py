#!/usr/bin/env python3
"""Render text in a font stored in a Scaleform .gfx font library (SWF DefineFont3 glyph outlines).

usage: gfx_font_text.py FONTLIB.gfx "FONT NAME" "TEXT" HEIGHT_PX OUT.png [--list]

Writes a white-on-transparent RGBA PNG of TEXT, cap/x-height scaled so the EM square is HEIGHT_PX tall.
Glyph outlines are filled even-odd (as SWF fonts are) at 4x and downsampled for antialiasing.
Uses only Pillow. --list prints the font names in the library and exits.
"""
import sys, zlib
from PIL import Image, ImageDraw, ImageChops


class Bits:
    def __init__(self, b, pos):
        self.b, self.byte, self.bit = b, pos, 0

    def ub(self, n):
        v = 0
        for _ in range(n):
            v = (v << 1) | ((self.b[self.byte] >> (7 - self.bit)) & 1)
            self.bit += 1
            if self.bit == 8:
                self.bit, self.byte = 0, self.byte + 1
        return v

    def sb(self, n):
        v = self.ub(n)
        return v - (1 << n) if n and v & (1 << (n - 1)) else v


def tags(body):
    nbits = body[0] >> 3
    pos = (5 + 4 * nbits + 7) // 8 + 4
    while pos < len(body):
        tc = int.from_bytes(body[pos:pos + 2], 'little'); pos += 2
        t, l = tc >> 6, tc & 63
        if l == 63:
            l = int.from_bytes(body[pos:pos + 4], 'little'); pos += 4
        yield t, pos, l
        if t == 0:
            return
        pos += l


def font3(body, pos):
    flags = body[pos + 2]
    wide_off = flags & 0x08
    has_layout = flags & 0x80
    nl = body[pos + 4]
    name = body[pos + 5:pos + 5 + nl].decode('latin1').rstrip('\0')
    p = pos + 5 + nl
    ng = int.from_bytes(body[p:p + 2], 'little'); p += 2
    ow = 4 if wide_off else 2
    table = p
    offs = [int.from_bytes(body[table + i * ow:table + (i + 1) * ow], 'little') for i in range(ng)]
    code_off = int.from_bytes(body[table + ng * ow:table + (ng + 1) * ow], 'little')
    cp = table + code_off
    codes = [int.from_bytes(body[cp + 2 * i:cp + 2 * i + 2], 'little') for i in range(ng)]
    adv = None
    if has_layout:
        lp = cp + 2 * ng + 6
        adv = [int.from_bytes(body[lp + 2 * i:lp + 2 * i + 2], 'little', signed=True) for i in range(ng)]
    return name, ng, table, offs, codes, adv


def shape_contours(body, start):
    """SWF SHAPE -> list of contours, each a list of (x, y) points in font units (y down), curves flattened."""
    r = Bits(body, start)
    nfill, nline = r.ub(4), r.ub(4)
    x = y = 0
    contours, cur = [], []
    while True:
        if r.ub(1) == 0:
            new, ls, fs1, fs0, move = r.ub(1), r.ub(1), r.ub(1), r.ub(1), r.ub(1)
            if not (new or ls or fs1 or fs0 or move):
                break
            if move:
                n = r.ub(5)
                x, y = r.sb(n), r.sb(n)
                if len(cur) > 2:
                    contours.append(cur)
                cur = [(x, y)]
            if fs0:
                r.ub(nfill)
            if fs1:
                r.ub(nfill)
            if ls:
                r.ub(nline)
        else:
            straight, n = r.ub(1), r.ub(4) + 2
            if straight:
                if r.ub(1):
                    x += r.sb(n); y += r.sb(n)
                elif r.ub(1):
                    y += r.sb(n)
                else:
                    x += r.sb(n)
                cur.append((x, y))
            else:
                cx, cy = x + r.sb(n), y + r.sb(n)
                ax, ay = cx + r.sb(n), cy + r.sb(n)
                for k in range(1, 9):
                    t = k / 8
                    cur.append(((1 - t) ** 2 * x + 2 * (1 - t) * t * cx + t * t * ax,
                                (1 - t) ** 2 * y + 2 * (1 - t) * t * cy + t * t * ay))
                x, y = ax, ay
    if len(cur) > 2:
        contours.append(cur)
    return contours


def main():
    lib = sys.argv[1]
    b = open(lib, 'rb').read()
    body = zlib.decompress(b[8:]) if b[:3] in (b'CFX', b'CWS') else b[8:]
    fonts = {}
    for t, pos, l in tags(body):
        if t == 75:
            f = font3(body, pos)
            fonts[f[0]] = f
    if '--list' in sys.argv:
        for n, f in fonts.items():
            print(repr(n), f[1], 'glyphs')
        return
    fname, text, height, out = sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5]
    name, ng, table, offs, codes, adv = fonts[fname]
    idx = {c: i for i, c in enumerate(codes)}
    ss = 4
    scale = height * ss / 20480.0          # DefineFont3 EM square = 1024 * 20 units
    base = int(0.82 * height * ss)          # baseline position inside the canvas
    pen, glyphs = 0.0, []
    for ch in text:
        i = idx[ord(ch)]
        glyphs.append((pen, shape_contours(body, table + offs[i])))
        pen += (adv[i] if adv else 20480 * 0.5)
    pad = int(0.15 * height * ss)
    w = int(pen * scale) + 2 * pad
    h = int(1.1 * height * ss) + 2 * pad
    base += pad
    mask = Image.new('L', (w, h), 0)
    for px, contours in glyphs:
        for c in contours:
            m = Image.new('L', (w, h), 0)
            ImageDraw.Draw(m).polygon([(pad + (px + cx) * scale, base + cy * scale) for cx, cy in c], fill=255)
            mask = ImageChops.logical_xor(mask.convert('1'), m.convert('1')).convert('L')
    mask = mask.resize((w // ss, h // ss), Image.LANCZOS)
    img = Image.new('RGBA', mask.size, (255, 255, 255, 0))
    img.putalpha(mask)
    img.save(out)
    print('wrote', out, img.size)


main()
