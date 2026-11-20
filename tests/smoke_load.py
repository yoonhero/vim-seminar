"""Bounded local 30-session pinball transport check (without neural inference)."""

import asyncio
import json
import statistics
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

import asyncssh

from be_vim.room import Room
from be_vim.transport import Server, session


async def main():
    r = Room(
        SimpleNamespace(
            duration=120,
            freeze=30,
            keyword="rice bowl",
            host_password="test-only",
            data=tempfile.mkdtemp(),
        )
    )
    await r.setup()
    r.run(load_model=False)
    server = await asyncssh.create_server(
        lambda: Server(r),
        "127.0.0.1",
        0,
        server_host_keys=[asyncssh.generate_private_key("ssh-ed25519")],
        process_factory=lambda p: session(p, r),
        line_editor=False,
    )
    conns = []
    readers = []
    chunks = [[] for _ in range(30)]
    pipes = []

    async def connect(i):
        c = await asyncssh.connect(
            "127.0.0.1", server.get_port(), username="guest", known_hosts=None
        )
        conns.append(c)
        p = await c.create_process(term_type="xterm-256color", term_size=(100, 32))
        pipes.append(p)

        async def drain():
            while data := await p.stdout.read(65536):
                chunks[i].append(data)

        readers.append(asyncio.create_task(drain()))

    try:
        await asyncio.gather(*(connect(i) for i in range(30)))
        async with asyncio.timeout(10):
            while len(r.players) != 30:
                await asyncio.sleep(0.01)
        async with r.lock:
            await r.goto(2)
        for p in pipes:
            p.stdin.write("l")
        await asyncio.sleep(0.3)
        for c in chunks:
            c.clear()

        async def drive():
            while True:
                for p in pipes:
                    p.stdin.write("hl")
                await asyncio.sleep(0.1)

        readers.append(asyncio.create_task(drive()))
        start = time.monotonic()
        await asyncio.sleep(4)
        elapsed = time.monotonic() - start
        outputs = ["".join(c) for c in chunks]
        report = {
            "sessions": len(r.players),
            "seconds": round(elapsed, 3),
            "active_games": sum(
                (
                    p.current.arena.started
                    or p.current.arena.misses > 0
                    or p.current.arena.hits > 0
                )
                for p in r.players.values()
            ),
            "median_updates_per_second": round(
                statistics.median(s.count("\x1b[0m") / elapsed for s in outputs), 1
            ),
            "min_updates_per_second": round(
                min(s.count("\x1b[0m") / elapsed for s in outputs), 1
            ),
            "total_bytes": sum(len(s.encode()) for s in outputs),
            "full_screen_clears_after_warmup": sum(s.count("\x1b[2J") for s in outputs),
        }
        assert report["sessions"] == 30 and report["active_games"] == 30
        assert report["full_screen_clears_after_warmup"] == 0
        Path("previews/interactive-v2/load-check.json").write_text(
            json.dumps(report, indent=2)
        )
        print(json.dumps(report))
    finally:
        for c in conns:
            c.close()
        await asyncio.gather(*(c.wait_closed() for c in conns))
        for t in readers:
            t.cancel()
        await asyncio.gather(*readers, return_exceptions=True)
        server.close()
        await server.wait_closed()
        await r.close()


asyncio.run(main())
