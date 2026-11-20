"""Author portable terminal titles from Helvetica Neue Medium; no runtime font needed."""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from be_vim.typography import WORDS

font = ImageFont.truetype('/System/Library/Fonts/HelveticaNeue.ttc', 320, index=10)
assets = {}
for word in WORDS.values():
    box = font.getbbox(word)
    mask = Image.new('L', (box[2] - box[0], box[3] - box[1]))
    ImageDraw.Draw(mask).text((-box[0], -box[1]), word, font=font, fill=255)
    assets[word] = {}
    for height in (5, 7, 9):
        width = round(mask.width / mask.height * height * 2)
        scaled = mask.resize((width, height), Image.Resampling.LANCZOS)
        coverage = [[scaled.getpixel((x, y)) for x in range(width)] for y in range(height)]
        lines = [''.join(' ' if v / 255 < .16 else '#' if v / 255 >= .52 else '+' for v in row) for row in coverage]
        assets[word][str(height)] = {'lines': lines, 'coverage': coverage}
Path('be_vim/assets/sans-titles.json').write_text(json.dumps(assets) + '\n')
print('Authored all 12 titles at 5, 7 and 9 rows')
