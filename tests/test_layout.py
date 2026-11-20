import asyncio
import copy
import tempfile
import unittest
from types import SimpleNamespace

import asyncssh
from test_games import until
from test_session import Peer
from wcwidth import wcswidth

from be_vim.layout import measure, wrap
from be_vim.physics import Arena
from be_vim.render import make_frame
from be_vim.room import Room
from be_vim.transport import Server, session

SIZES = [
    (24, 12),
    (32, 16),
    (48, 20),
    (60, 24),
    (80, 24),
    (100, 32),
    (160, 50),
    (240, 80),
]


def overlap(a, b):
    return max(a.x, b.x) < min(a.x + a.w, b.x + b.w) and max(a.y, b.y) < min(
        a.y + a.h, b.y + b.h
    )


class LayoutTest(unittest.TestCase):
    def test_regions_fit_and_do_not_overlap(self):
        for w, h in SIZES:
            for board in [False, True]:
                with self.subTest(size=(w, h), board=board):
                    l = measure(w, h, board)
                    regions = [
                        l.header,
                        l.title,
                        l.goal,
                        l.stage,
                        l.status,
                        l.feedback,
                        l.controls,
                    ]
                    if l.hint:
                        regions.append(l.hint)
                    if l.scoreboard:
                        regions.append(l.scoreboard)
                    for i, r in enumerate(regions):
                        self.assertGreater(r.w, 0)
                        self.assertGreater(r.h, 0)
                        self.assertGreaterEqual(r.x, 0)
                        self.assertGreaterEqual(r.y, 0)
                        self.assertLessEqual(r.x + r.w, w)
                        self.assertLessEqual(r.y + r.h, h)
                        for other in regions[i + 1 :]:
                            self.assertFalse(overlap(r, other))

    def test_reading_gap_and_canvas_board_alignment(self):
        from be_vim.layout import viewport

        for w, h in [(80, 24), (100, 32), (140, 44), (240, 80)]:
            layout = measure(w, h, True)
            self.assertGreater(layout.goal.y, layout.title.y + layout.title.h)
            canvas, _ = viewport(layout.stage, 40, 16)
            self.assertEqual(canvas.y - 1, layout.scoreboard.y)
            self.assertEqual(canvas.y + canvas.h, layout.scoreboard.y + layout.scoreboard.h - 1)
            self.assertLessEqual(layout.scoreboard.x - (canvas.x + canvas.w), 5)

    def test_lesson_pane_does_not_move_between_cursors(self):
        from be_vim.render import draw_scene
        from be_vim.terminal import Frame

        for w, h in [(80, 24), (140, 44)]:
            regions = []
            for cursor in [(0, 0), (8, 12), (15, 39)]:
                f = Frame(w, h)
                scene = {"lines": ["x" * 40] * 16, "cursor": cursor}
                draw_scene(f, scene, measure(w, h).stage, kind="words")
                regions.append({(x, y) for y, row in enumerate(f.rows)
                                for x, cell in enumerate(row) if cell.ch.strip()})
            self.assertEqual(regions[0], regions[1])
            self.assertEqual(regions[1], regions[2])

    def test_lesson_feedback_follows_native_pane(self):
        for w, h in SIZES:
            for kind in ("words", "change", "jumps", "search", "visual", "clone"):
                with self.subTest(size=(w, h), kind=kind):
                    layout = measure(w, h, kind=kind)
                    self.assertLessEqual(layout.stage.h, 18)
                    self.assertEqual(layout.status.y, layout.stage.y + layout.stage.h)
                    self.assertEqual(layout.feedback.y, layout.status.y + 1)
                    if layout.hint:
                        self.assertEqual(layout.hint.y, layout.feedback.y + 1)
                    self.assertLess(layout.feedback.y, layout.controls.y)

    def test_scoreboard_moves_under_game(self):
        self.assertEqual(measure(100, 32, True).board_mode, "side")
        l = measure(60, 24, True)
        self.assertEqual(l.board_mode, "stack")
        self.assertGreater(l.scoreboard.y, l.stage.y)

    def test_unicode_wrap_respects_cell_width(self):
        for width in (4, 12, 30):
            for line in wrap("한글과 ASCII의 긴 안내문을 줄바꿈합니다.", width, 3):
                self.assertLessEqual(wcswidth(line), width)

    def test_arena_resizes_without_changing_world(self):
        a = Arena()
        a.key("l")
        a.step(0.1)
        before = copy.deepcopy(vars(a))
        for w, h in ((12, 5), (40, 16), (100, 40), (200, 80)):
            picture = a.picture(w, h)
            self.assertEqual(len(picture), h)
            self.assertTrue(all(len(row) == w for row in picture))
        self.assertEqual(vars(a), before)


class ResizeSSH(unittest.IsolatedAsyncioTestCase):
    async def test_live_resize_keeps_game_and_slide(self):
        args = SimpleNamespace(
            duration=120,
            freeze=30,
            keyword="rice bowl",
            host_password="test-only",
            data=tempfile.mkdtemp(),
        )
        r = Room(args)
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
        c = await asyncssh.connect(
            "127.0.0.1", server.get_port(), username="guest", known_hosts=None
        )
        peer = Peer(
            c, await c.create_process(term_type="xterm-256color", term_size=(80, 24))
        )
        try:
            await until(lambda: len(r.players) == 1)
            async with r.lock:
                await r.goto(3)
            person = next(iter(r.players.values()))
            peer.send("j")
            await until(lambda: person.current.snapshot["cursor"][0] == 4)
            game = person.current
            position = game.snapshot["cursor"]
            for w, h in ((160, 50), (48, 20), (100, 32)):
                peer.screen.resize(lines=h, columns=w)
                peer.process.change_terminal_size(w, h)
                await until(lambda: "벽을 타고 균열로 이동" in peer.text())
                await asyncio.sleep(0.12)
                self.assertIs(person.current, game)
                self.assertEqual(game.snapshot["cursor"], position)
                self.assertEqual(r.slide, 3)
                self.assertNotIn("넓혀주세요", peer.text())
            for w, h in SIZES:
                frame = make_frame(r, person, w, h)
                self.assertEqual((frame.w, frame.h), (w, h))
        finally:
            await peer.close()
            server.close()
            await server.wait_closed()
            await r.close()
