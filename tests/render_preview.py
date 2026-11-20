"""Actual terminal-frame captures, including presenter and two private game views."""

import asyncio
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw, ImageFont

from be_vim.render import make_frame
from be_vim.room import Room
from be_vim.slides import DRAWING_PROMPT, SLIDES

FONT = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 20)
SYM = ImageFont.truetype("/System/Library/Fonts/Apple Symbols.ttf", 20)
KO = ImageFont.truetype("/System/Library/Fonts/AppleSDGothicNeo.ttc", 20)


def save(frame, path):
    im = Image.new("RGB", (frame.w * 12, frame.h * 24), "black")
    d = ImageDraw.Draw(im)
    for y, row in enumerate(frame.rows):
        for x, c in enumerate(row):
            if not c.ch:
                continue
            d.rectangle((x * 12, y * 24, x * 12 + (23 if x + 1 < len(row) and not row[x + 1].ch else 11), y * 24 + 23), fill=c.bg)
            if c.ch != " ":
                d.text(
                    (x * 12, y * 24),
                    c.ch,
                    font=KO
                    if 0xAC00 <= ord(c.ch) <= 0xD7AF
                    else SYM
                    if 0x2500 <= ord(c.ch) <= 0x28FF
                    else FONT,
                    fill=c.fg,
                )
    im.save(path)


async def main():
    out = Path("previews/interactive-v2")
    out.mkdir(parents=True, exist_ok=True)
    r = Room(SimpleNamespace(duration=120, freeze=30, keyword=DRAWING_PROMPT))
    await r.setup()
    try:
        a = await r.add_player()
        b = await r.add_player()
        save(make_frame(r, a, 100, 32), out / "cover.png")
        for kind in [
            "name",
            "paddle",
            "jumps",
            "words",
            "search",
            "visual",
            "clone",
            "change",
            "draw",
        ]:
            i = next(i for i, s in enumerate(SLIDES) if s.kind == kind)
            await r.goto(i - r.slide)
            if kind == "name":
                for k in "iDEMO\x1b":
                    await r.handle(r.presenter, "Escape" if k == "\x1b" else k)
                await r.presenter.current.update(0.1)
                save(make_frame(r, r.presenter, 100, 32), out / "name-demo.png")
            if kind == "paddle":
                await r.handle(a, "l")
                a.current.arena.step(0.15)
                save(make_frame(r, a, 100, 32), out / "paddle-alice.png")
                save(make_frame(r, b, 100, 32), out / "paddle-bob.png")
            save(make_frame(r, a, 100, 32), out / (kind + ".png"))
            save(make_frame(r, a, 80, 24), out / (kind + "-compact.png"))
        print("Rendered", len(list(out.glob("*.png"))), "actual frames")
    finally:
        await r.close()


if __name__ == "__main__":
    asyncio.run(main())
