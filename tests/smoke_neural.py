"""Actual local SigLIP inference through deadline, freeze and shared reveal."""

import asyncio
import math
import tempfile
from types import SimpleNamespace

from be_vim.room import Room
from be_vim.scoring import Judge
from be_vim.slides import RICE, SLIDES


async def wait(check, seconds=60):
    async with asyncio.timeout(seconds):
        while not check():
            await asyncio.sleep(0.025)


async def main():
    room = Room(
        SimpleNamespace(
            duration=5,
            freeze=2,
            keyword="rice bowl",
            data=tempfile.mkdtemp(),
            font="/System/Library/Fonts/Menlo.ttc",
        )
    )
    await room.setup()
    room.judge = await asyncio.to_thread(Judge, room.args.font)
    room.run(load_model=False)
    try:
        async with room.lock:
            a = await room.add_player()
            b = await room.add_player()
            a.name = "rice"
            b.name = "blank"
            await room.goto(next(i for i, s in enumerate(SLIDES) if s.kind == "draw"))
        self_demo = room.presenter.current
        await room.handle(room.presenter, "F5")
        assert room.presenter.id not in room.roster
        async with room.lock:
            await a.editor.activate("draw", RICE, reset=True)
            a.current.snapshot = await a.editor.snapshot()
        await wait(lambda: room.frozen is not None)
        frozen = dict(room.frozen)
        await wait(lambda: room.round_phase == "done")
        assert room.frozen == frozen and len(room.final) == 2
        assert all(math.isfinite(v) for v in room.final.values())
        assert room.final[a.id] > room.final[b.id]
        async with room.lock:
            await room.goto(1)
        await room.handle(room.presenter, "F6")
        assert room.reveal_phase == "focus"
        await wait(lambda: room.reveal_phase == "score")
        await wait(lambda: room.reveal_phase == "idle")
        await room.handle(room.presenter, "F6")
        await wait(lambda: len(room.revealed) == 2 and room.reveal_phase == "idle")
        assert room.presenter.games["draw"] is self_demo
        print(
            "PASS real neural round:",
            {room.players[p].name: round(s, 3) for p, s in room.final.items()},
        )
        print(
            "PASS frozen snapshot, host excluded, focus -> score -> move -> final, saved art"
        )
    finally:
        await room.close()


asyncio.run(main())
