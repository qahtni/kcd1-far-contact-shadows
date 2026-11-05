#!/usr/bin/env python3
"""Nexus header banner (1300x372) from a 4K screenshot: crop, darken the left side, title in the game's font.

usage: make_banner.py SCREENSHOT TOP_FRACTION FONTLIB.gfx OUT.jpg
TOP_FRACTION 0..1 = where the crop band sits. FONTLIB = the game's Libs/UI/gfxfontlib_glyphs.gfx;
text is drawn in WHS Champ Fleury Pro (KCD's menu font) by gfx_font_text.py.
"""
import os, subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageFilter

src, top, fontlib, out = sys.argv[1], float(sys.argv[2]), sys.argv[3], sys.argv[4]
here = os.path.dirname(os.path.abspath(__file__))
FONT = 'WHS Champ Fleury Pro'
W, H = 1300, 372

im = Image.open(src).convert('RGB')
cw = im.width; ch = round(cw * H / W)
y0 = round((im.height - ch) * top)
im = im.crop((0, y0, cw, y0 + ch)).resize((W, H), Image.LANCZOS)
shade = Image.new('RGB', (W, H), (8, 8, 6))
g = Image.new('L', (W, H)); gd = ImageDraw.Draw(g)
for x in range(W):  # dark gradient on the left for the text
    gd.line([(x, 0), (x, H)], fill=int(205 * max(0.0, 1 - x / 760) ** 1.6))
im = Image.composite(shade, im, g)
v = Image.new('L', (W, H)); vd = ImageDraw.Draw(v)
for y in range(H):  # soft bottom vignette
    vd.line([(0, y), (W, y)], fill=int(110 * max(0.0, (y - H * 0.55) / (H * 0.45)) ** 2))
im = Image.composite(shade, im, v).convert('RGBA')


def text(t, em):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, 't.png')
        subprocess.run([sys.executable, '-I', f'{here}/gfx_font_text.py', fontlib, FONT, t, str(em), p], check=True,
                       stdout=subprocess.DEVNULL)
        return Image.open(p).getchannel('A').copy()


def ink(a):
    return a.crop(a.getbbox())  # trim the PNG to the letters themselves


title, sub, small = ink(text('Far Contact Shadows', 78)), ink(text('Expanded Screen Space Shadows', 36)), \
    ink(text('Kingdom Come: Deliverance', 27))
gap_rule, gap_small = 16, 20
block = title.height + 2 * gap_rule + 2 + sub.height + gap_small + small.height
y = (H - block) // 2 - 6
x = 58
rule_y = y + title.height + gap_rule
lines = [(title, (240, 228, 200), y), (sub, (225, 210, 175), rule_y + 2 + gap_rule),
         (small, (190, 180, 160), rule_y + 2 + gap_rule + sub.height + gap_small)]
shadow = Image.new('L', (W, H), 0)
for a, c, ly in lines:
    shadow.paste(a, (x + 2, ly + 3), a)
shadow = shadow.filter(ImageFilter.GaussianBlur(3)).point(lambda v: v * 200 // 255)
im = Image.alpha_composite(im, Image.merge('RGBA', (*[Image.new('L', (W, H), 0)] * 3, shadow)))
for a, c, ly in lines:
    im.paste(Image.new('RGBA', a.size, c + (255,)), (x, ly), a)
ImageDraw.Draw(im).line([(x, rule_y), (x + sub.width, rule_y)], fill=(200, 170, 110), width=2)
print('title', title.size, 'subtitle', sub.size, 'small', small.size, 'block top', y)
im.convert('RGB').save(out, quality=95)
print('wrote', out)
