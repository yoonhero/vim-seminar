import itertools
import unittest

from be_vim.glyph_shader import paint
from be_vim.layout import Rect
from be_vim.terminal import Frame


class GlyphShader(unittest.TestCase):
    def test_real_ascii_cells_animate(self):
        for effect in range(3):
            first, second = Frame(64, 32), Frame(64, 32)
            paint(first, Rect(0, 0, 64, 32), 0, effect)
            paint(second, Rect(0, 0, 64, 32), 2, effect)
            self.assertNotEqual(first.rows, second.rows)
            cells = [c for row in first.rows for c in row if c.ch.strip()]
            self.assertGreater(len(cells), 70)
            self.assertTrue(all(len(c.ch) == 1 and c.ch.isascii() for c in cells))

    def test_content_region_is_untouched(self):
        f = Frame(80, 32)
        box = Rect(22, 6, 40, 16)
        for y in range(box.y, box.y + box.h):
            f.text(y, box.x, "X" * box.w)
        for effect in range(3):
            paint(f, Rect(0, 0, 80, 32), 1, effect, protect=box)
            for y in range(box.y, box.y + box.h):
                self.assertTrue(
                    all(c.ch == "X" for c in f.rows[y][box.x : box.x + box.w])
                )

    def test_free_swimming_moves_in_both_axes_without_jumps(self):
        import math

        from be_vim.glyph_shader import FISH, pose

        for fish in FISH:
            points = [pose(fish, i * 0.1, 100, 40) for i in range(1200)]
            self.assertGreater(
                max(p[0] for p in points) - min(p[0] for p in points), 30
            )
            self.assertGreater(
                max(p[1] for p in points) - min(p[1] for p in points), 14
            )
            for before, after in itertools.pairwise(points):
                self.assertLess(
                    math.hypot(after[0] - before[0], after[1] - before[1]), 1
                )
                turn = math.atan2(
                    math.sin(after[2] - before[2]), math.cos(after[2] - before[2])
                )
                self.assertLess(abs(turn), 0.25)

    def test_sans_title_is_real_ascii_and_fits(self):
        from be_vim.typography import WORDS, lines

        for word in WORDS.values():
            for width, height in [(22, 1), (60, 5), (100, 7)]:
                art = lines(word, width, height)
                self.assertLessEqual(len(art), height)
                self.assertTrue(
                    all(len(line) <= width and line.isascii() for line in art)
                )
