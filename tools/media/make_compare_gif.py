#!/usr/bin/env python3
"""Labelled 1080p A/B comparison GIFs and stills for the Nexus page.

usage: make_compare_gif.py PAIRS.txt SRC_DIR OUT_DIR FONTLIB.gfx [dur=1.5] [dither=bayer:bayer_scale=4] [only=N] [split=1]

PAIRS.txt: one 'MOD.jpg STOCK.jpg' per line (files in SRC_DIR). For pair N it writes
  OUT_DIR/compare_N.gif          two frames, 'With mod' first (Nexus shows the first frame as the thumbnail)
  OUT_DIR/stills/N_with_mod.jpg, N_without_mod.jpg   labelled 1920x1080 JPEG ('With mod' top right, 'Without mod' top left)
  OUT_DIR/split/N_split.jpg      (split=1 only) left half stock, right half mod, line down the middle
Labels use the game's menu font (WHS Champ Fleury Pro) drawn by gfx_font_text.py.
"""
import os, subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageFilter

pairs_txt, src, out, fontlib = sys.argv[1:5]
opts = dict(a.split('=', 1) for a in sys.argv[5:])
dur = float(opts.get('dur', '1.5'))
dither = opts.get('dither', 'bayer:bayer_scale=4')
only = opts.get('only')
split = opts.get('split') == '1'
here = os.path.dirname(os.path.abspath(__file__))
W, H = 1920, 1080
CREAM = (242, 232, 208)
os.makedirs(f'{out}/stills', exist_ok=True)
tmp = tempfile.mkdtemp(dir=out)


def label(text):
    p = f'{tmp}/{text}.png'
    subprocess.run([sys.executable, '-I', f'{here}/gfx_font_text.py', fontlib, 'WHS Champ Fleury Pro', text, '64', p],
                   check=True, stdout=subprocess.DEVNULL)
    a = Image.open(p).getchannel('A')
    a = a.crop(a.getbbox())
    pad_x, pad_y, m = 26, 16, 32
    box = Image.new('RGBA', (a.width + 2 * pad_x, a.height + 2 * pad_y), (0, 0, 0, 0))
    ImageDraw.Draw(box).rounded_rectangle((0, 0, box.width - 1, box.height - 1), radius=12, fill=(12, 10, 8, 150))
    shadow = Image.new('RGBA', a.size, (0, 0, 0, 255)); shadow.putalpha(a.filter(ImageFilter.GaussianBlur(2)))
    txt = Image.new('RGBA', a.size, CREAM + (255,)); txt.putalpha(a)
    box.alpha_composite(shadow, (pad_x + 2, pad_y + 2))
    box.alpha_composite(txt, (pad_x, pad_y))
    return box, (m, m)


LAB = {'with': label('With mod'), 'without': label('Without mod')}


def load(path):
    im = Image.open(f'{src}/{path}').convert('RGB')
    if im.size != (W, H):
        im = im.resize((W, H), Image.LANCZOS)
    return im.convert('RGBA')


def split_image(mod, stock):
    im = load(stock)
    im.paste(load(mod).crop((W // 2, 0, W, H)), (W // 2, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((W // 2 - 3, 0, W // 2 + 2, H), fill=(12, 10, 8, 255))
    d.rectangle((W // 2 - 1, 0, W // 2, H), fill=CREAM + (255,))
    box, (m, _) = LAB['without']
    im.alpha_composite(box, (m, m))
    box, _ = LAB['with']
    im.alpha_composite(box, (W - m - box.width, m))
    return im.convert('RGB')


def frame(path, which):
    im = load(path)
    box, (m, _) = LAB[which]
    # 'With mod' top right, 'Without mod' top left (same sides as the split images)
    im.alpha_composite(box, (W - m - box.width, m) if which == 'with' else (m, m))
    return im.convert('RGB')


for n, line in enumerate(open(pairs_txt).read().split('\n'), 1):
    if not line.strip() or (only and str(n) != only):
        continue
    mod, stock = line.split()
    if split:
        os.makedirs(f'{out}/split', exist_ok=True)
        split_image(mod, stock).save(f'{out}/split/{n}_split.jpg', quality=90, optimize=True)
        print(n, 'split ->', f'{out}/split/{n}_split.jpg')
        continue
    a, b = frame(mod, 'with'), frame(stock, 'without')
    a.save(f'{out}/stills/{n}_with_mod.jpg', quality=90, optimize=True)
    b.save(f'{out}/stills/{n}_without_mod.jpg', quality=90, optimize=True)
    a.save(f'{tmp}/f1.png'); b.save(f'{tmp}/f2.png')
    gif = f'{out}/compare_{n}.gif'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-framerate', f'1/{dur}', '-i', f'{tmp}/f%d.png',
                    '-vf', f'split[a][b];[a]palettegen=max_colors=256:stats_mode=full[p];[b][p]paletteuse=dither={dither}',
                    '-loop', '0', gif], check=True)
    print(n, mod, stock, '->', gif, os.path.getsize(gif) // 1024, 'KB')
for f in os.listdir(tmp):
    os.remove(f'{tmp}/{f}')
os.rmdir(tmp)
