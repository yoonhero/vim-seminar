import asyncio
import tempfile
import unittest
from types import SimpleNamespace

import asyncssh
import pyte
from test_games import until

from be_vim.room import Room
from be_vim.terminal import DiffRenderer, Frame
from be_vim.transport import Server, session


class Peer:
    def __init__(self, connection, process):
        self.connection = connection
        self.process = process
        self.screen = pyte.Screen(100, 32)
        self.stream = pyte.Stream(self.screen)
        self.task = asyncio.create_task(self.read())

    async def read(self):
        while data := await self.process.stdout.read(8192):
            self.stream.feed(data)

    def send(self, text):
        self.process.stdin.write(text)

    def text(self):
        return "\n".join(self.screen.display)

    async def close(self):
        self.connection.close()
        await self.connection.wait_closed()
        self.task.cancel()
        await asyncio.gather(self.task, return_exceptions=True)


class SSHFlow(unittest.IsolatedAsyncioTestCase):
    async def test_real_three_terminal_demo_practice_keys_and_naming(self):
        args = SimpleNamespace(
            duration=120,
            freeze=30,
            keyword="rice bowl",
            data=tempfile.mkdtemp(),
            host_password="test-only-password",
        )
        room = Room(args)
        await room.setup()
        room.run(load_model=False)
        server = await asyncssh.create_server(
            lambda: Server(room),
            "127.0.0.1",
            0,
            server_host_keys=[asyncssh.generate_private_key("ssh-ed25519")],
            process_factory=lambda p: session(p, room),
            line_editor=False,
        )
        peers = []

        async def connect(host=False):
            c = await asyncssh.connect(
                "127.0.0.1",
                server.get_port(),
                username="presenter" if host else "guest",
                password=args.host_password if host else None,
                known_hosts=None,
            )
            peer = Peer(
                c,
                await c.create_process(term_type="xterm-256color", term_size=(100, 32)),
            )
            peers.append(peer)
            return peer

        try:
            host = await connect(True)
            alice = await connect()
            bob = await connect()
            await until(lambda: len(room.players) == 2)
            await until(lambda: "너도 이제" in alice.text())
            self.assertNotIn("닉네임 (", alice.text())
            host.send("n")
            await asyncio.sleep(0.1)
            self.assertEqual(room.slide, 0)
            host.send("\x1b[6~")
            await until(lambda: room.slide == 1)
            host.send("iDEMO\x1b\r")
            await until(lambda: room.presenter.name == "DEMO")
            await until(lambda: "DEMO" in host.text())
            self.assertNotIn("DEMO", alice.text())
            alice.send("iALICE\x1b\r")
            bob.send("iBOB\x1b\r")
            await until(
                lambda: {p.name for p in room.players.values()} == {"ALICE", "BOB"}
            )
            await until(lambda: "ALICE" in alice.text() and "BOB" in bob.text())
            self.assertNotIn("name: BOB", alice.text())
            alice.send("\x1b[6~")
            await asyncio.sleep(0.1)
            self.assertEqual(room.slide, 1)
            host.send("\x07n")
            await until(lambda: room.slide == 2)
            host.send("lll")
            await until(lambda: room.presenter.current.arena.started)
            self.assertTrue(
                all(not p.current.arena.started for p in room.players.values())
            )
            alice.send("l")
            await until(lambda: next(iter(room.players.values())).current.arena.started)
            self.assertFalse(list(room.players.values())[1].current.arena.started)
        finally:
            for p in peers:
                await p.close()
            server.close()
            await server.wait_closed()
            await room.close()

    def test_incremental_renderer_does_not_clear_each_frame(self):
        r = DiffRenderer()
        f = Frame(80, 30)
        f.text(5, 5, "*")
        self.assertIn("\x1b[2J", r.render(f))
        g = Frame(80, 30)
        g.text(5, 6, "*")
        diff = r.render(g)
        self.assertNotIn("\x1b[2J", diff)
        self.assertLess(len(diff), 150)
