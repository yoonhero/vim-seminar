"""The marked pixels are the actual editable cells, embedded in the specimen."""

import unittest

from be_vim.games import STAGES, puzzle
from be_vim.layout import Rect
from be_vim.specimen import board
from be_vim.terminal import Frame


class SpecimenBoardTest(unittest.TestCase):
    def test_every_stage_places_cursor_and_targets_on_native_text(self):
        for kind in STAGES:
            for stage in range(STAGES[kind]):
                with self.subTest(kind=kind, stage=stage):
                    spec = puzzle(kind, stage)
                    scene = {
                        "lines": spec.rows, "cursor": spec.cursor, "target": spec.target
                    }
                    f = Frame(60, 16)
                    board(f, Rect(0, 0, 60, 16), scene, None, kind)
                    if kind == "jumps":
                        self.assertEqual(sum(cell.ch == "@" for row in f.rows for cell in row), 1)
                        self.assertTrue(any(cell.ch == "*" for row in f.rows for cell in row))
                        continue
                    y, x = spec.cursor
                    self.assertEqual(f.rows[y][10 + x].bg, "#fa8458")
                    for y, x in spec.target:
                        self.assertEqual(f.rows[y][10 + x].ch, spec.rows[y][x])
                    self.assertTrue(any(c.ch in "|;=" for row in f.rows for c in row))

    def test_tuna_selection_is_drawn_once(self):
        spec = puzzle("visual", 0)
        f = Frame(84, 30)
        board(
            f,
            Rect(0, 0, 84, 30),
            {
                "lines": spec.rows,
                "target": spec.target,
                "selected": spec.target,
                "cursor": spec.target[-1],
            },
            None,
            "visual",
        )
        rows = ["".join(c.ch for c in row) for row in f.rows]
        self.assertEqual(sum(row.count("VIM") for row in rows), 1)
        y = next(i for i, row in enumerate(rows) if "VIM" in row)
        x = rows[y].index("VIM")
        self.assertEqual(
            [c.bg for c in f.rows[y][x : x + 3]], ["#285b4d", "#285b4d", "#fa8458"]
        )
