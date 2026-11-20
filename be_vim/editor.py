"""One native Neovim process per person; separate buffers per slide."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import pynvim

W, H = 40, 16
COLORS = ["#e8e3d9", "#78aba5", "#c5aa72", "#c48372", "#8795b1", "#ad91ad"]
PIXELS = tuple(chr(0xE000 + i) for i in range(len(COLORS)))
BRUSHES = ".+:#@░▒▓█▀▄"


@dataclass
class Paint:
    colors: list = field(default_factory=lambda: [[0] * W for _ in range(H)])
    before: tuple | None = None
    history: dict = field(default_factory=dict)


class Editor:
    def __init__(self):
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.ink = 0
        self.active = ""
        self.buffers = {}
        self.positions = {}
        self.snapshots = {}
        self.paint = {}
        self.closed = False

    async def call(self, fn, *args):
        return await asyncio.get_running_loop().run_in_executor(self.pool, fn, *args)

    async def start(self):
        await self.call(self._start)

    def _start(self):
        self.n = pynvim.attach(
            "child",
            argv=["nvim", "--clean", "-n", "-i", "NONE", "--embed", "--headless"],
        )
        self.n.command(
            "set virtualedit=all nowrap noswapfile undolevels=200 timeoutlen=200"
        )
        self.n.command("set shell=/usr/bin/false modelines=0 nomodeline")
        for mode in ["n", "x"]:
            for key in [
                ":",
                "!",
                "Q",
                "K",
                "Z",
                "@",
                "q",
                '"',
                "[",
                "]",
                "<C-r>",
                "<C-w>",
                "<C-]>",
                "<C-o>",
            ]:
                self.n.command(f"{mode}noremap {key} <Nop>")
        self.n.command("nnoremap g <Nop>")
        self.n.command("nnoremap gg gg")
        self.n.command("nnoremap gv gv")
        self.n.command("inoremap <C-r> <Nop>")

    async def activate(self, name, lines=None, cursor=(0, 0), reset=False):
        await self.call(self._activate, name, lines, cursor, reset)

    def _activate(self, name, lines, cursor, reset):
        self.n.input("<Esc>")
        if self.active:
            self.positions[self.active] = self.n.funcs.getcurpos()
        fresh = name not in self.buffers
        if fresh:
            self.buffers[name] = self.n.api.create_buf(False, True)
            self.paint[name] = Paint()
        self.n.current.buffer = self.buffers[name]
        self.active = name
        if fresh or reset:
            self.n.current.buffer.options["undolevels"] = -1
            self.n.current.buffer[:] = lines or [" " * W for _ in range(H)]
            self.n.current.buffer.options["undolevels"] = 200
            self.n.current.window.cursor = (cursor[0] + 1, cursor[1])
            self.paint[name] = Paint()
        elif name in self.positions:
            self.n.funcs.setpos(".", self.positions[name][:4])

    async def key(self, key):
        if key == "\t":
            self.ink = (self.ink + 1) % len(COLORS)
            return
        special = {
            "\x1b": "<Esc>",
            "\x7f": "<BS>",
            "\b": "<BS>",
            "\x16": "<C-v>",
            "\r": "<CR>",
            "\n": "<CR>",
        }
        if key in special:
            key = special[key]
        elif not (len(key) == 1 and (" " <= key <= "~" or key in BRUSHES or (self.active == "name" and key.isalnum()))):
            return
        elif key == "<":
            key = "<LT>"
        await self.call(self.n.input, key)

    async def fill(self, erase=False):
        # A distinct one-column glyph per ink keeps colour-only edits undoable in Vim.
        pixel = " " if erase else PIXELS[self.ink]
        await self.call(self.n.input, "r" + pixel)

    async def snapshot(self):
        return await self.call(self._snapshot)

    def _snapshot(self):
        if self.n.api.get_mode()["blocking"] and self.active in self.snapshots:
            return {**self.snapshots[self.active], "pending": True}
        data = self.n.exec_lua(
            """return {lines=vim.api.nvim_buf_get_lines(0,0,-1,false), cursor={vim.fn.line('.'),vim.fn.virtcol('.')-1}, mode=vim.fn.mode(), anchor={0,vim.fn.line('v'),vim.fn.virtcol('v'),0}, command=vim.fn.getcmdtype()..vim.fn.getcmdline()}"""
        )
        raw = data["lines"]
        row, col = data["cursor"]
        mode = data["mode"]
        text = tuple(
            "".join(
                c if 32 <= ord(c) < 127 or c in BRUSHES else " " for c in line[:W]
            ).ljust(W)
            for line in (raw + [""] * H)[:H]
        )
        pixels = {}
        if self.active == "draw":
            grid = [list(line) for line in text]
            for y, line in enumerate(raw[:H]):
                for x, ch in enumerate(line[:W]):
                    if ch in PIXELS:
                        grid[y][x] = "█"
                        pixels[y, x] = PIXELS.index(ch)
            text = tuple("".join(line) for line in grid)
        paint = self.paint[self.active]
        if text != paint.before:
            if text in paint.history:
                paint.colors = [r[:] for r in paint.history[text]]
            else:
                for y, line in enumerate(text):
                    for x, c in enumerate(line):
                        if paint.before is None or c != paint.before[y][x]:
                            paint.colors[y][x] = self.ink
                paint.history[text] = [r[:] for r in paint.colors]
                if len(paint.history) > 128:
                    del paint.history[next(iter(paint.history))]
            paint.before = text
        selected = []
        ay, ax = data["anchor"][1] - 1, data["anchor"][2] - 1
        if mode in ("v", "V", "\x16"):
            for y in range(H):
                for x in range(W):
                    if mode == "\x16":
                        inside = min(ay, row - 1) <= y <= max(ay, row - 1) and min(
                            ax, col
                        ) <= x <= max(ax, col)
                    elif mode == "V":
                        inside = min(ay, row - 1) <= y <= max(ay, row - 1)
                    else:
                        inside = (
                            min(ay * W + ax, (row - 1) * W + col)
                            <= y * W + x
                            <= max(ay * W + ax, (row - 1) * W + col)
                        )
                    if inside:
                        selected.append((y, x))
        colors = [r[:] for r in paint.colors]
        for (y, x), ink in pixels.items():
            colors[y][x] = ink
        snapshot = {
            "pending": False,
            "lines": list(text),
            "raw_lines": raw,
            "colors": colors,
            "cursor": (row - 1, col),
            "selected": selected,
            "mode": mode,
            "command": data["command"],
        }
        self.snapshots[self.active] = snapshot
        return snapshot

    async def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            try:
                await self.call(self.n.command, "qa!")
            except (EOFError, OSError):
                pass
            await self.call(self.n.close)
        finally:
            self.pool.shutdown(wait=False)
