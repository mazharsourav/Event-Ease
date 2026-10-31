"""Generated pictures for demo data: poster artwork, venue photos, avatars and a gallery image.

Nothing here needs the network or any file shipped with the project. Pictures are drawn with Pillow, so a
fresh checkout can be filled with demo data and every page that shows an image has one to show.
"""
import io
import math
import random
import textwrap

from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont

# (background, ink, accent): artwork is where a page's only colour comes from
PALETTES = [
    ('#E8452C', '#FFF4E0', '#1B1B1B'),
    ('#1F5FBF', '#F4F1E8', '#FFC94A'),
    ('#F2B632', '#1B1B1B', '#E8452C'),
    ('#2E8B6A', '#F7F2E4', '#1B1B1B'),
    ('#7B3FA0', '#F6EFE3', '#FFD166'),
    ('#D94F8A', '#FFF6EA', '#1B1B1B'),
    ('#1B1B1B', '#F4F1E8', '#E8452C'),
    ('#3AA6B9', '#10242B', '#FFF4E0'),
]

FONT_CANDIDATES = [
    r'C:\Windows\Fonts\bahnschrift.ttf',
    r'C:\Windows\Fonts\arialbd.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    '/Library/Fonts/Arial Bold.ttf',
]


def _font(size):
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _file(image, name):
    buffer = io.BytesIO()
    image.convert('RGB').save(buffer, format='JPEG', quality=86)
    return ContentFile(buffer.getvalue(), name=name)


def _wrapped(draw, text, font, width):
    """Break text into lines no wider than `width` pixels."""
    words, lines, line = text.split(), [], ''
    for word in words:
        trial = f'{line} {word}'.strip()
        if draw.textlength(trial, font=font) <= width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def poster(title, subtitle='', palette=0, size=(1200, 800), seed=None):
    """A typeset poster: bold shapes, the title in capitals, a small line underneath."""
    background, ink, accent = PALETTES[palette % len(PALETTES)]
    rng = random.Random(seed if seed is not None else title)
    width, height = size
    image = Image.new('RGB', size, background)
    draw = ImageDraw.Draw(image)

    kind = rng.choice(['circles', 'stripes', 'rays'])
    if kind == 'circles':
        for _ in range(5):
            radius = rng.randint(height // 6, height // 2)
            cx, cy = rng.randint(width // 3, width), rng.randint(0, height)
            draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=accent if rng.random() > .4 else ink)
    elif kind == 'stripes':
        step = rng.randint(60, 110)
        for x in range(-height, width + height, step):
            draw.polygon([(x, 0), (x + step // 2, 0), (x + step // 2 - height, height), (x - height, height)], fill=accent)
    else:
        cx, cy = width * .78, height * .3
        for i in range(0, 360, 18):
            a1, a2 = math.radians(i), math.radians(i + 9)
            r = width * 1.2
            draw.polygon([(cx, cy), (cx + r * math.cos(a1), cy + r * math.sin(a1)),
                          (cx + r * math.cos(a2), cy + r * math.sin(a2))], fill=accent)

    # A solid plate keeps the title readable on any shape behind it
    plate_top = int(height * .5)
    draw.rectangle((0, plate_top, width, height), fill=background)
    draw.rectangle((0, plate_top, width, plate_top + 8), fill=ink)

    font = _font(int(height * .115))
    y = plate_top + 36
    for line in _wrapped(draw, title.upper(), font, width - 120)[:3]:
        draw.text((60, y), line, font=font, fill=ink)
        y += int(height * .125)
    if subtitle:
        draw.text((60, height - 80), subtitle.upper(), font=_font(int(height * .04)), fill=ink)
    return image


def poster_file(name, title, subtitle='', palette=0, **kwargs):
    return _file(poster(title, subtitle, palette, **kwargs), name)


def hall(title, palette=0, seed=None, size=(1200, 800)):
    """A stylised room: floor, back wall, windows or arches and a few lights. No text."""
    background, ink, accent = PALETTES[palette % len(PALETTES)]
    rng = random.Random(seed if seed is not None else title)
    width, height = size
    image = Image.new('RGB', size, ink)
    draw = ImageDraw.Draw(image)
    horizon = int(height * .62)
    draw.rectangle((0, 0, width, horizon), fill=background)
    draw.rectangle((0, horizon, width, height), fill=accent)

    columns = rng.randint(4, 7)
    gap = width / columns
    for i in range(columns):
        x = gap * i + gap * .2
        w = gap * .6
        if rng.random() > .5:
            draw.rectangle((x, horizon * .22, x + w, horizon * .9), fill=ink)
        else:
            draw.pieslice((x, horizon * .12, x + w, horizon * .12 + w), 180, 360, fill=ink)
            draw.rectangle((x, horizon * .12 + w / 2, x + w, horizon * .9), fill=ink)
    for _ in range(rng.randint(5, 9)):
        x = rng.randint(40, width - 40)
        draw.ellipse((x - 14, 40, x + 14, 68), fill=ink)
        draw.line((x, 0, x, 40), fill=ink, width=3)
    for row in range(5):
        y = horizon + 30 + row * 52
        draw.line((0, y, width, y), fill=ink, width=2 + row)
    return image


def hall_file(name, title, palette=0, **kwargs):
    return _file(hall(title, palette, **kwargs), name)


def avatar_file(name, initials, palette=0):
    background, ink, _ = PALETTES[palette % len(PALETTES)]
    image = Image.new('RGB', (400, 400), background)
    draw = ImageDraw.Draw(image)
    font = _font(170)
    text = initials.upper()[:2]
    box = draw.textbbox((0, 0), text, font=font)
    draw.text(((400 - (box[2] - box[0])) / 2 - box[0], (400 - (box[3] - box[1])) / 2 - box[1]), text, font=font, fill=ink)
    return _file(image, name)


def photo_file(name, title, palette=0, seed=None):
    """A square-ish picture for comments, blog posts and chat."""
    return _file(poster(title, '', palette, size=(900, 600), seed=seed), name)


def text_file(name, body):
    return ContentFile(textwrap.dedent(body).encode('utf-8'), name=name)
