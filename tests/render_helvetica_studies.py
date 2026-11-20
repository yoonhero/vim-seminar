"""Compare native character compositions using measured Helvetica Neue outlines."""
import json
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from render_preview import save

from be_vim.glyph_shader import paint
from be_vim.layout import Rect
from be_vim.render import text
from be_vim.slides import SUBTITLE
from be_vim.terminal import GRAY, WHITE, Frame

OUT = Path('previews/helvetica-studies')
LABELS = ['01 · 대각선 구도', '02 · 같은 눈높이', '03 · 중앙 타이틀']


@lru_cache
def title(height):
    font = ImageFont.truetype('/System/Library/Fonts/HelveticaNeue.ttc', 320, index=10)
    box = font.getbbox('Be Vim')
    mask = Image.new('L', (box[2] - box[0], box[3] - box[1]))
    ImageDraw.Draw(mask).text((-box[0], -box[1]), 'Be Vim', font=font, fill=255)
    # Terminal cells are twice as tall as wide. Keep the typeface's aspect ratio.
    width = round(mask.width / mask.height * height * 2)
    mask = mask.resize((width, height), Image.Resampling.LANCZOS)
    cells = []
    for y in range(height):
        for x in range(width):
            coverage = mask.getpixel((x, y)) / 255
            if coverage < .16:
                continue
            glyph = '#' if coverage >= .52 else '+'
            strength = min(1, .4 + coverage * .75)
            color = '#' + ''.join(f'{round(int(WHITE[i:i+2], 16) * strength):02x}' for i in (1, 3, 5))
            cells.append((x, y, glyph, color))
    return width, cells


def frame(variant, t):
    f = Frame(140, 44)
    if variant == 0:
        x, y, size = 8, 5, 9
        water = Rect(30, 16, 104, 24)
        caption = Rect(8, 40, 124, 2)
    elif variant == 1:
        x, y, size = 6, 15, 7
        water = Rect(76, 4, 60, 34)
        caption = Rect(6, 28, 66, 2)
    else:
        size = 9
        x, y = (140 - title(size)[0]) // 2, 6
        water = Rect(10, 17, 120, 22)
        caption = Rect(8, 40, 124, 2)
    paint(f, water, t, 0)
    text(f, Rect(x, y-3, 60, 1), '너도 이제,', GRAY)
    for dx, dy, char, color in title(size)[1]:
        f.text(y+dy, x+dx, char, color)
    text(f, caption, SUBTITLE, GRAY, center=variant == 2)
    return f


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    styles, lookup, sequences = [], {}, []
    for variant in range(3):
        save(frame(variant, 6), OUT / f'{variant+1:02}.png')
        sequence = []
        for tick in range(240):
            f = frame(variant, tick / 12)
            texts, colors = [], []
            for row in f.rows:
                chars, codes = [], []
                for c in row:
                    if not c.ch:
                        continue
                    pair = (c.fg, c.bg)
                    if pair not in lookup:
                        lookup[pair] = len(styles)
                        styles.append(pair)
                    chars.append(c.ch)
                    codes.append(chr(65 + lookup[pair]))
                texts.append(''.join(chars))
                colors.append(''.join(codes))
            sequence.append([texts, colors])
        sequences.append(sequence)
    data = json.dumps({'styles': styles, 'frames': sequences}, ensure_ascii=False)
    template = (Path(__file__).with_name('helvetica-studies.html')).read_text()
    (OUT / 'index.html').write_text(template.replace('__FRAME_DATA__', data))
    sheet = Image.new('RGB', (1008, 2052), '#121212')
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype('/System/Library/Fonts/AppleSDGothicNeo.ttc', 22)
    for i, label in enumerate(LABELS):
        draw.text((20, i*684+12), label, font=font, fill='#e8e3d9')
        shot = Image.open(OUT / f'{i+1:02}.png').resize((1008, 634), Image.Resampling.LANCZOS)
        sheet.paste(shot, (0, i*684+36))
    sheet.save(OUT / 'comparison.png')
    print('Three Helvetica Neue Medium studies: actual ASCII cells, 20 seconds each')


if __name__ == '__main__':
    main()

