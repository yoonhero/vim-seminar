"""Full seminar via three actual SSH terminals; real 120s round and neural scores."""

import argparse
import asyncio
import copy
import json
import math
import time
from pathlib import Path
from types import SimpleNamespace

import asyncssh
from render_preview import save
from test_session import Peer

from be_vim.room import Room
from be_vim.scoring import Judge
from be_vim.slides import RICE
from be_vim.terminal import Frame
from be_vim.transport import Server, session

OUT = Path("previews/full-flow")


async def wait(check, timeout=10):
    async with asyncio.timeout(timeout):
        while not check():
            await asyncio.sleep(0.025)


async def main(duration=120, freeze=30):
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"checks": [], "duration": duration, "freeze": freeze}
    start = time.monotonic()

    def mark(label):
        item = {"check": label, "elapsed": round(time.monotonic() - start, 2)}
        report["checks"].append(item)
        print(json.dumps(item, ensure_ascii=False), flush=True)

    def capture(peer, name):
        (OUT / (name + ".txt")).write_text(peer.text())
        f = Frame(peer.screen.columns, peer.screen.lines)
        for y in range(f.h):
            for x in range(f.w):
                cell = peer.screen.buffer[y][x]

                def color(v, default):
                    return "#" + v if len(v) == 6 else default

                f.text(
                    y,
                    x,
                    cell.data,
                    color(cell.fg, "#e8e3d9"),
                    color(cell.bg, "#000000"),
                )
        save(f, OUT / (name + ".png"))

    args = SimpleNamespace(
        duration=duration,
        freeze=freeze,
        keyword="rice bowl",
        font="/System/Library/Fonts/Menlo.ttc",
        data=str(OUT / "rounds"),
        host_password="local-test-only",
    )
    room = Room(args)
    await room.setup()
    peers = []
    server = None
    try:
        room.judge = await asyncio.to_thread(Judge, args.font)
        room.run(load_model=False)
        server = await asyncssh.create_server(
            lambda: Server(room),
            "127.0.0.1",
            0,
            server_host_keys=[asyncssh.generate_private_key("ssh-ed25519")],
            process_factory=lambda p: session(p, room),
            line_editor=False,
        )

        async def connect(host=False):
            c = await asyncssh.connect(
                "127.0.0.1",
                server.get_port(),
                username="presenter" if host else "guest",
                password=args.host_password if host else None,
                known_hosts=None,
            )

            class RecordedPeer(Peer):
                async def read(self):
                    with (OUT / f"ssh-{len(peers)}.ansi").open("w") as raw:
                        while data := await self.process.stdout.read(8192):
                            raw.write(data)
                            raw.flush()
                            self.stream.feed(data)

            peer = RecordedPeer(
                c,
                await c.create_process(term_type="xterm-256color", term_size=(100, 32)),
            )
            peers.append(peer)
            return peer

        host = await connect(True)
        alice = await connect()
        bob = await connect()
        await wait(lambda: len(room.players) == 2)
        a, b = list(room.players.values())
        await wait(lambda: "너도 이제" in alice.text())
        capture(alice, "00-cover")
        mark("SSH presenter + two participants; cover without nickname prompt")

        async def next_slide(index):
            host.send("\x07n")
            await wait(lambda: room.slide == index and not room.transitioning)
            await wait(lambda: f"{index + 1:02}/12" in bob.text())

        await next_slide(1)
        host.send("iDEMO\x1b\r")
        await wait(lambda: room.presenter.current.complete)
        assert not a.named
        await wait(lambda: "DEMO" in host.text())
        alice.send("iALICE\x1b\r")
        bob.send("iBOB\x1b\r")
        await wait(lambda: a.named and b.named)
        assert (a.name, b.name) == ("ALICE", "BOB")
        mark("i nickname: independent naming from first input")
        await next_slide(2)
        host.send("l")
        await wait(lambda: room.presenter.current.arena.started)
        assert not a.current.arena.started and not b.current.arena.started

        async def play(peer, person):
            deadline = time.monotonic() + 100
            while person.current.arena.hits < 3:
                assert time.monotonic() < deadline, (
                    "paddle could not finish with SSH controls"
                )
                arena = person.current.arena
                destination = arena.x if arena.stage == 0 else arena.y
                difference = destination - arena.target
                threshold = 0.9 if arena.stage == 0 else 0.4
                if abs(difference) > threshold:
                    peer.send(
                        ("h" if difference < 0 else "l")
                        if arena.stage == 0
                        else ("k" if difference < 0 else "j")
                    )
                elif not arena.started:
                    peer.send(" ")
                await asyncio.sleep(0.035)

        await asyncio.gather(play(alice, a), play(bob, b))
        capture(alice, "02-paddle-complete")
        mark(
            "paddle: two independent SSH players each broke three bricks without waiting between hits"
        )
        solutions = {
            3: ["3j", "6l4k", "6j11h3k"],
            4: ["2w", "2e", "4b"],
            5: ["f*", ";", "/crack\r", "n"],
            6: ["v2l", "v3l", "\x164l2jr#"],
            7: ["v2ly8lv2lp", "v2ly6j8lv2lp", "u"],
            8: ["dw", "ciwopen\x1bw.w."],
        }
        for index, steps in solutions.items():
            await next_slide(index)
            host.send(steps[0])
            await wait(lambda: room.presenter.current.awaiting_next)
            await wait(lambda: "Enter 다음 문제" in host.text())
            assert not a.current.awaiting_next and not b.current.awaiting_next
            capture(host, f"{index:02}-presenter")
            for n, keys in enumerate(steps):
                alice.send(keys)
                await wait(lambda: a.current.awaiting_next or a.current.complete)
                assert b.current.stage == n and not b.current.complete
                bob.send(keys)
                await wait(lambda: b.current.awaiting_next or b.current.complete)
                if n < len(steps) - 1:
                    alice.send("\r")
                    bob.send("\r")
                    await wait(
                        lambda n=n: (
                            a.current.stage == n + 1 and b.current.stage == n + 1
                        )
                    )
            assert room.slide == index
            assert a.current.complete and b.current.complete
            capture(alice, f"{index:02}-practice-complete")
            mark(
                f"{room.kind}: independent presenter and participant completion"
            )
        await next_slide(9)
        host.send("r#")
        await wait(lambda: room.presenter.current.snapshot["lines"][0][0] == "#")
        alice.send("r+")
        await wait(lambda: a.current.snapshot["lines"][0][0] == "+")
        host.send("\x07s")
        await wait(lambda: room.round_phase == "running")
        assert (
            len(room.roster) == 2
            and "host" not in room.roster
        )
        assert a.current.snapshot["lines"][0][0] == " "
        # All drawing commands travel through SSH; no buffer injection.
        for y, line in enumerate(RICE):
            alice.send("gg" + (f"{y}j" if y else "") + "0i" + line + "\x1b")
            await asyncio.sleep(0.04)
        bob.send("r.")
        await wait(lambda: b.current.snapshot["lines"][0][0] == ".")
        await wait(lambda: all(v is not None for v in room.live.values()), 60)
        await wait(lambda: room.live[a.id] > room.live[b.id], 60)
        await wait(lambda: all(f"{s:.1f}" in alice.text() for s in room.live.values()))
        capture(alice, "09-live")
        host.send("\x07n")
        await asyncio.sleep(0.15)
        assert room.slide == 9
        mark(
            "drawing: demo reset, simultaneous start, host excluded, live neural scores; navigation locked"
        )
        await wait(lambda: room.frozen is not None, 125)
        frozen = copy.deepcopy(room.frozen)
        frozen_order = room.standings()
        assert freeze - 2 <= room.remaining() <= freeze + 0.1
        await wait(lambda: "점수 동결" in alice.text())
        capture(alice, "09-frozen")
        bob.send("gg0r█")
        await wait(lambda: b.current.snapshot["lines"][0][0] == "█")
        await asyncio.sleep(min(6, freeze / 2))
        assert room.frozen == frozen and room.standings() == frozen_order
        mark(f"last {freeze} seconds: public score/rank frozen; drawing still editable")
        await wait(lambda: room.round_phase == "done", 65)
        assert (
            all(math.isfinite(s) for s in room.final.values()) and len(room.final) == 2
        )
        assert room.final_art[b.id]["lines"][0][0] == "█"
        before = copy.deepcopy(a.current.snapshot["lines"])
        alice.send("gg0rX")
        await asyncio.sleep(0.15)
        assert a.current.snapshot["lines"] == before
        assert room.frozen == frozen
        assert len(list((OUT / "rounds").glob("*/results.json"))) >= 1
        report["scores"] = {
            room.players[p].name: round(s, 4) for p, s in room.final.items()
        }
        capture(alice, "09-submitted")
        mark(
            "deadline: input locked, final real scores and artwork saved, hidden until reveal"
        )
        await next_slide(10)
        for i in range(2):
            host.send("\x07r")
            await wait(lambda: room.reveal_phase == "focus")
            focused = room.focus
            await wait(
                lambda focused=focused: (
                    "@" + room.players[focused].name in alice.text()
                    and "@" + room.players[focused].name in bob.text()
                )
            )
            (bob if focused == a.id else alice).send("v")
            await wait(lambda: room.reveal_phase == "score")
            assert room.focus == focused
            capture(alice, f"10-reveal-{i + 1}")
            await wait(lambda: room.reveal_phase == "idle")
            assert len(room.revealed) == i + 1
        await wait(lambda: "최종" in alice.text() and "최종" in bob.text())
        assert room.standings() == sorted(
            room.final.items(), key=lambda r: (-r[1], r[0])
        )
        assert room.votes
        capture(alice, "10-final-ranking")
        mark("gallery: synchronized artwork, score then rank, voting, final standings")
        await next_slide(11)
        await wait(lambda: "AI 우승" in alice.text() and "관객상" in bob.text())
        await wait(
            lambda: "관객상 (공동)" in alice.text() and "ALICE, BOB" in alice.text()
        )
        capture(alice, "11-end")
        mark("closing slide: AI winner and audience award")
        report["passed"] = True
    except BaseException as exc:
        report["passed"] = False
        report["error"] = repr(exc)
        for i, p in enumerate(peers):
            try:
                capture(p, f"failure-{i}")
            except IndexError:
                (OUT / f"failure-{i}-cells.json").write_text(
                    json.dumps(
                        [
                            [p.screen.buffer[y][x].data for x in range(100)]
                            for y in range(32)
                        ],
                        ensure_ascii=False,
                    )
                )
        raise
    finally:
        (OUT / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2)
        )
        for peer in peers:
            await peer.close()
        if server:
            server.close()
            await server.wait_closed()
        await room.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=int, default=120)
    parser.add_argument("--freeze", type=int, default=30)
    options = parser.parse_args()
    asyncio.run(main(options.duration, options.freeze))
