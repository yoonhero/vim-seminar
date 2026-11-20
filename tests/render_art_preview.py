"""Render the actual terminal views at desktop and compact sizes."""

import asyncio
from pathlib import Path
from types import SimpleNamespace

from render_preview import save

from be_vim.render import make_frame
from be_vim.room import Room
from be_vim.slides import DRAWING_PROMPT, RICE, SLIDES


async def main():
    out = Path("previews/ascii-studio")
    out.mkdir(parents=True, exist_ok=True)
    room = Room(SimpleNamespace(duration=120, freeze=30, keyword=DRAWING_PROMPT))
    await room.setup()
    try:
        person = await room.add_player()
        for index, slide in enumerate(SLIDES):
            if slide.kind == "gallery":
                continue
            await room.goto(index - room.slide)
            if slide.kind == "draw":
                await room.presenter.editor.activate("draw", RICE, reset=True)
                await room.presenter.current.update(0)
            for w, h in [(100, 36), (80, 24), (48, 20)]:
                save(
                    make_frame(room, person, w, h),
                    out / f"{index:02}-{slide.kind}-{w}.png",
                )
        print("Rendered actual frames:", out)
    finally:
        await room.close()


if __name__ == "__main__":
    asyncio.run(main())
