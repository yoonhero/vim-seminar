import asyncio
import tempfile
import unittest
from types import SimpleNamespace

from be_vim.physics import Arena
from be_vim.room import Room
from be_vim.slides import SLIDES


async def until(check, timeout=3):
    async with asyncio.timeout(timeout):
        while not check():
            await asyncio.sleep(0.025)


async def keys(room, person, text):
    for char in text:
        await room.handle(
            person,
            {"\x1b": "Escape", "\r": "Enter", "\x16": "ControlV"}.get(char, char),
        )


class Lessons(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.room = Room(
            SimpleNamespace(
                duration=4,
                freeze=2,
                keyword="rice bowl",
                data=tempfile.mkdtemp(),
                font="/System/Library/Fonts/Menlo.ttc",
                host_password="test-only",
            )
        )
        await self.room.setup()
        self.room.run(load_model=False)
        async with self.room.lock:
            self.a = await self.room.add_player()
            self.b = await self.room.add_player()

    async def asyncTearDown(self):
        await self.room.close()

    async def enter(self, kind):
        idx = next(i for i, s in enumerate(SLIDES) if s.kind == kind)
        async with self.room.lock:
            await self.room.goto(idx - self.room.slide)

    async def test_nickname_is_insert_game_and_demo_is_separate(self):
        self.assertFalse(self.a.named)
        async with self.room.lock:
            await self.room.goto(1)
        await keys(self.room, self.room.presenter, "iDEMO\x1b\r")
        await until(
            lambda: self.room.presenter.named and self.room.presenter.name == "DEMO"
        )
        await keys(self.room, self.a, "iALICE\x1b\r")
        await until(lambda: self.a.named)
        await keys(self.room, self.b, "iBOB\x1b\r")
        await until(lambda: self.b.named)
        self.assertEqual(
            (self.a.name, self.b.name, self.room.presenter.name),
            ("ALICE", "BOB", "DEMO"),
        )
        self.assertIsNot(self.a.current, self.room.presenter.current)

    async def test_korean_names_in_practice_with_enter_or_escape_enter(self):
        await self.enter("name")
        await keys(self.room, self.a, "i고래\r")
        await keys(self.room, self.b, "i상어\x1b\r")
        self.assertEqual((self.a.name, self.b.name), ("고래", "상어"))
        self.assertIn("고래", "".join(self.a.current.scene()["lines"][8]))

    async def test_late_arrival_rehearses_independently_then_rejoins(self):
        room = self.room
        await room.goto(4)
        late = await room.add_player()
        for _ in range(3):
            await room.handle(late, "PageUp")
        self.assertEqual(room.page(late), 1)
        await keys(room, late, "i고래\r")
        self.assertEqual(late.name, "고래")
        await room.goto(1)
        self.assertEqual(room.page(late), 1)
        self.assertEqual(room.page(self.a), 5)
        await room.handle(late, "PageDown")
        await room.handle(late, "h")
        self.assertTrue(late.current.arena.started)
        await room.handle(late, "ControlG")
        await room.handle(late, "l")
        self.assertIsNone(late.review_slide)
        self.assertIsNot(late.current, room.presenter.current)
        await room.handle(late, "PageDown")
        self.assertEqual(room.page(late), room.slide)

    async def test_every_lesson_can_be_won_without_advancing_others(self):
        solutions = {
            "jumps": ["3j", "6l4k", "6j11h3k"],
            "words": ["2w", "2e", "4b"],
            "search": ["f*", ";", "/crack\r", "n"],
            "visual": ["v2l", "v3l", "\x164l2jr#"],
            "clone": ["v2ly8lv2lp", "v2ly6j8lv2lp", "u"],
            "change": ["dw", "ciwopen\x1bw.w."],
        }
        for kind, rounds in solutions.items():
            with self.subTest(kind=kind):
                await self.enter(kind)
                slide = self.room.slide
                for index, text in enumerate(rounds):
                    await keys(self.room, self.a, text)
                    try:
                        await until(
                            lambda index=index: (
                                self.a.current.complete or self.a.current.awaiting_next
                            )
                        )
                    except TimeoutError:
                        print(
                            "FAILED",
                            kind,
                            index,
                            self.a.current.snapshot,
                            self.a.current.feedback,
                        )
                        raise
                    if index < len(rounds) - 1:
                        await keys(self.room, self.a, "\r")
                self.assertTrue(self.a.current.complete)
                self.assertFalse(self.b.current.complete)
                self.assertEqual(self.b.current.stage, 0)
                self.assertEqual(self.room.slide, slide)
                async with self.room.lock:
                    await self.room.goto(-1)
                    await self.room.goto(1)
                self.assertTrue(self.a.current.complete)

    async def test_alternate_exit_and_either_seam(self):
        from be_vim.chapter import next_step

        await self.enter("words")
        a = self.a.current
        await keys(self.room, self.a, "2w\r2e\r")
        self.assertEqual(next_step("words", a), "?  힌트")
        await keys(self.room, self.a, "?")
        self.assertFalse(a.keys)
        await keys(self.room, self.a, "w")
        self.assertTrue(a.complete)
        await self.enter("visual")
        await keys(self.room, self.a, "v2l\r")
        await keys(self.room, self.a, "fSv3l")
        self.assertTrue(self.a.current.awaiting_next)
        self.assertFalse(self.b.current.awaiting_next)

    async def test_wall_guide_tracks_partial_input_and_local_reset(self):
        from be_vim.chapter import next_step

        await self.enter("search")
        game = self.a.current
        await keys(self.room, self.a, "f")
        self.assertIn("*", next_step("search", game))
        await keys(self.room, self.a, "*")
        self.assertEqual(game.cleared, 1)
        await self.room.handle(self.a, "ControlL")
        await keys(self.room, self.a, "f*")
        self.assertEqual(game.cleared, 1)
        self.assertEqual(self.b.current.cleared, 0)
        await self.enter("jumps")
        start = self.a.current.snapshot["cursor"]
        await self.room.handle(self.a, "Down")
        self.assertEqual(self.a.current.snapshot["cursor"], (start[0]+1, start[1]))

    async def test_maze_wall_stops_count_and_hint_routes_out_of_dead_end(self):
        from be_vim.chapter import next_step
        await self.enter("jumps")
        a = self.a.current
        await keys(self.room, self.a, "9l")
        self.assertEqual(a.snapshot["cursor"], (3, 26))
        self.assertIn("6h", next_step("jumps", a))
        await keys(self.room, self.a, "j")
        self.assertEqual(a.snapshot["cursor"], (3, 26))
        await keys(self.room, self.a, "6h3j")
        self.assertTrue(a.awaiting_next)
        self.assertFalse(self.b.current.trail)

    async def test_result_waits_for_enter_and_retry_is_local(self):
        await self.enter("jumps")
        await keys(self.room, self.a, "3j")
        game = self.a.current
        self.assertTrue(game.awaiting_next)
        await asyncio.sleep(0.8)
        self.assertEqual(game.stage, 0)
        self.assertEqual(game.snapshot["cursor"], (6, 20))
        await keys(self.room, self.a, "\r")
        self.assertEqual(game.stage, 1)
        self.assertEqual(game.snapshot["cursor"], (6, 20))
        await keys(self.room, self.a, "j")
        await self.room.handle(self.a, "ControlL")
        self.assertEqual(game.snapshot["cursor"], (6, 20))
        self.assertEqual(self.b.current.stage, 0)

    async def test_slow_find_and_replace_do_not_block_room(self):
        await self.enter("search")
        await keys(self.room, self.a, "f")
        await asyncio.sleep(0.15)
        self.assertTrue(self.a.current.snapshot["pending"])
        await keys(self.room, self.b, "f*")
        self.assertTrue(self.b.current.awaiting_next)
        await keys(self.room, self.a, "*")
        self.assertTrue(self.a.current.awaiting_next)
        await self.enter("clone")
        await keys(self.room, self.a, "r")
        await asyncio.sleep(0.15)
        # Changing slides also cancels a pending native command safely.
        await self.enter("words")
        await keys(self.room, self.a, "w")
        self.assertEqual(self.a.current.snapshot["cursor"], (8, 5))

    async def test_buffer_cursor_is_restored(self):
        await self.enter("words")
        await keys(self.room, self.a, "w")
        await self.enter("visual")
        await self.enter("words")
        self.assertEqual(self.a.current.snapshot["cursor"], (8, 5))

    async def test_palette_rectangle_recolour_undo_and_erase(self):
        from PIL import ImageColor, ImageFont

        from be_vim.editor import COLORS
        from be_vim.scoring import Judge
        await self.enter("draw")
        game = self.a.current
        await keys(self.room, self.a, "p3v2lj")
        self.assertEqual(len(game.snapshot["selected"]), 6)
        await keys(self.room, self.a, " ")
        def check_ink(index):
            for y in range(2):
                self.assertEqual(game.snapshot["lines"][y][:4], "███ ")
                self.assertEqual(game.snapshot["colors"][y][:3], [index]*3)
        check_ink(2)
        await keys(self.room, self.a, "p4v2lj ")
        check_ink(3)
        await keys(self.room, self.a, "u")
        check_ink(2)
        judge = Judge.__new__(Judge)
        judge.font = ImageFont.load_default()
        image = judge.render(game.snapshot)
        self.assertEqual(image.getpixel((35,47)), ImageColor.getrgb(COLORS[2]))
        self.assertEqual(image.getpixel((36,47)), (0,0,0))
        await keys(self.room, self.a, "v2ljx")
        self.assertEqual(game.snapshot["lines"][1][:4], "    ")
        await keys(self.room, self.a, "u")
        check_ink(2)
        self.assertEqual(self.b.current.snapshot["lines"][0][:4], "    ")

    async def test_block_glyphs_use_cells_for_cursor_and_selection(self):
        await self.enter("draw")
        host = self.room.presenter
        await keys(self.room, host, "r█lv2lr▓")
        scene = host.current.snapshot
        self.assertEqual(scene["lines"][0][:4], "█▓▓▓")
        self.assertEqual(scene["cursor"], (0, 1))
        await keys(self.room, host, "v2l")
        self.assertEqual(
            set(host.current.snapshot["selected"]), {(0, 1), (0, 2), (0, 3)}
        )
        await keys(self.room, host, "\x1bu")
        self.assertEqual(host.current.snapshot["lines"][0][:4], "█   ")

    async def test_pinball_is_personal_and_demo_pause_preserves_practice(self):
        await self.enter("paddle")
        host = self.room.presenter
        await keys(self.room, self.a, "ll")
        await keys(self.room, host, "h")
        await asyncio.sleep(0.15)
        self.assertTrue(self.a.current.arena.started)
        self.assertTrue(host.current.arena.started)
        self.assertFalse(self.b.current.arena.started)
        before = self.a.current.arena.x
        await asyncio.sleep(0.15)
        self.assertNotEqual(self.a.current.arena.x, before)
        await asyncio.sleep(0.15)
        self.assertNotEqual(self.a.current.arena.x, before)


class Physics(unittest.TestCase):
    def test_keystone_clears_only_its_course(self):
        a = Arena()
        a.started = True
        x, y, _, _ = a.keystone
        a.x, a.y, a.vx, a.vy = x + 1, y - .15, 0, 8
        a.step(1/120)
        self.assertEqual(a.hits, 5)
        self.assertEqual(len(a.bricks), 10)
        self.assertFalse(any(brick[1] == y for brick in a.bricks))

    def test_fixed_step_is_independent_of_frame_rate(self):
        a = Arena()
        b = Arena()
        a.key("l")
        b.key("l")
        for _ in range(60):
            a.step(1 / 30)
        for _ in range(240):
            b.step(1 / 120)
        self.assertAlmostEqual(a.x, b.x, places=8)
        self.assertAlmostEqual(a.y, b.y, places=8)

    def test_last_brick_auto_advances_both_orientations(self):
        a = Arena()
        a.key(" ")
        for wave in (1, 2):
            a.bricks = [(10, 5, 3, 1)]
            a.x, a.y, a.vx, a.vy = 9.7, 5.5, 12, 0
            a.step(1/120)
            self.assertEqual(a.wave, wave + 1)
            self.assertEqual(a.hits, wave)
            self.assertTrue(a.started)
            for _ in range(90):
                a.step(1/120)
            self.assertEqual(a.stage, wave % 2)
            self.assertLessEqual(a.serve_delay, 0)

    def test_miss_reserves_automatically_without_resetting_bricks(self):
        a = Arena()
        a.key(" ")
        a.x, a.y, a.vy = 2, 15.49, 5
        bricks = a.bricks.copy()
        a.step(1/120)
        self.assertEqual(a.misses, 1)
        for _ in range(100):
            a.step(1/120)
        self.assertLess(a.y, a.depth - 1)
        self.assertEqual(a.bricks, bricks)

    def test_paddle_offset_steers_without_changing_visible_speed(self):
        import math

        for offset in (-3, 0, 3):
            a = Arena()
            a.key(" ")
            a.x, a.y = a.paddle + offset, a.depth - .01
            a.vx, a.vy = 0, 6
            a.step(1/120)
            self.assertLess(a.vy, 0)
            self.assertAlmostEqual(math.hypot(a.vx, 2*a.vy), 12)
            self.assertEqual((a.vx > 0) - (a.vx < 0), (offset > 0) - (offset < 0))

    def test_brick_corner_reflects_both_axes(self):
        a = Arena()
        a.key(" ")
        a.bricks = [(10, 5, 3, 1), (30, 3, 1, 1)]
        a.x, a.y, a.vx, a.vy = 9.7, 4.85, 12, 6
        a.step(1/120)
        self.assertEqual((a.vx, a.vy, a.hits), (-12, -6, 1))
