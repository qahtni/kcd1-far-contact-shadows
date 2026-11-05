#!/usr/bin/env python3
"""Nexus thumbnail (16:9, 1920x1080) in the header banner's style: screenshot, dark left side, title in the game's font.

usage: make_thumbnail.py SCREENSHOT FONTLIB.gfx OUT.jpg [zoom=1.0] [fx=0.5] [fy=0.5]
zoom > 1 crops into the screenshot around the focus point fx, fy (0..1). FONTLIB = the game's
Libs/UI/gfxfontlib_glyphs.gfx; text is drawn in WHS Champ Fleury Pro (KCD's menu font) by gfx_font_text.py.
The title is large and on two lines so it stays readable on the small mod tiles.
"""
import os, subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageFilter

src, fontlib, out = sys.argv[1:4]
opts = dict(a.split('=', 1) for a in sys.argv[4:])
zoom, fx, fy = float(opts.get('zoom', 1)), float(opts.get('fx', 0.5)), float(opts.get('fy', 0.5))
here = os.path.dirname(os.path.abspath(__file__))
FONT = 'WHS Champ Fleury Pro'
W, H = 1920, 1080

im = Image.open(src).convert('RGB')
cw, ch = im.width / zoom, im.width / zoom * H / W
x0 = min(max(0, im.width * fx - cw / 2), im.width - cw)
y0 = min(max(0, im.height * fy - ch / 2), im.height - ch)
im = im.crop((round(x0), round(y0), round(x0 + cw), round(y0 + ch))).resize((W, H), Image.LANCZOS)
shade = Image.new('RGB', (W, H), (8, 8, 6))
g = Image.new('L', (W, H)); gd = ImageDraw.Draw(g)
for x in range(W):  # dark gradient on the left for the text
    gd.line([(x, 0), (x, H)], fill=int(215 * max(0.0, 1 - x / 1180) ** 1.5))
im = Image.composite(shade, im, g)
v = Image.new('L', (W, H)); vd = ImageDraw.Draw(v)
for y in range(H):  # soft top and bottom vignette
    t = max((y - H * 0.6) / (H * 0.4), (H * 0.18 - y) / (H * 0.18), 0.0)
    vd.line([(0, y), (W, y)], fill=int(120 * t ** 2))
im = Image.composite(shade, im, v).convert('RGBA')


def text(t, em):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, 't.png')
        subprocess.run([sys.executable, '-I', f'{here}/gfx_font_text.py', fontlib, FONT, t, str(em), p], check=True,
                       stdout=subprocess.DEVNULL)
        a = Image.open(p).getchannel('A')
        return a.crop(a.getbbox())  # trim to the letters themselves


t1, t2 = text('Far Contact', 200), text('Shadows', 200)
sub, small = text('Expanded Screen Space Shadows', 66), text('Kingdom Come: Deliverance', 50)
gap_title, gap_rule, gap_small = 34, 30, 30
block = t1.height + gap_title + t2.height + 2 * gap_rule + 3 + sub.height + gap_small + small.height
y = (H - block) // 2
x = 100
y2 = y + t1.height + gap_title
rule_y = y2 + t2.height + gap_rule
lines = [(t1, (240, 228, 200), y), (t2, (240, 228, 200), y2), (sub, (225, 210, 175), rule_y + 3 + gap_rule),
         (small, (190, 180, 160), rule_y + 3 + gap_rule + sub.height + gap_small)]
shadow = Image.new('L', (W, H), 0)
for a, c, ly in lines:
    shadow.paste(a, (x + 4, ly + 5), a)
shadow = shadow.filter(ImageFilter.GaussianBlur(6)).point(lambda v: v * 210 // 255)
im = Image.alpha_composite(im, Image.merge('RGBA', (*[Image.new('L', (W, H), 0)] * 3, shadow)))
for a, c, ly in lines:
    im.paste(Image.new('RGBA', a.size, c + (255,)), (x, ly), a)
ImageDraw.Draw(im).line([(x, rule_y), (x + max(sub.width, t1.width), rule_y)], fill=(200, 170, 110), width=3)
print('title', t1.size, t2.size, 'subtitle', sub.size, 'small', small.size, 'block', y, y + block)
im.convert('RGB').save(out, quality=92, optimize=True)
print('wrote', out, os.path.getsize(out) // 1024, 'KB')
