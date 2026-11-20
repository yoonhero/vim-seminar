"""Cell renderer and incremental ANSI updates. Never clear the screen per frame."""

from dataclasses import dataclass

from wcwidth import wcswidth, wcwidth

BLACK = "#000000"
WHITE = "#e8e3d9"
GRAY = "#b8b9b1"
DIM = "#555555"
CYAN = "#98cec4"
YELLOW = "#c5aa72"


@dataclass(frozen=True, slots=True)
class Cell:
    ch: str = " "
    fg: str = WHITE
    bg: str = BLACK


EMPTY = Cell()


class Frame:
    def __init__(self, w, h):
        self.w = w
        self.h = h
        empty = EMPTY
        self.rows = [[empty] * w for _ in range(h)]

    def text(self, y, x, text, fg=WHITE, bg=BLACK):
        if not 0 <= y < self.h:
            return
        for char in text:
            width = max(0, wcwidth(char))
            if width == 0:
                continue
            if 0 <= x and x + width <= self.w:
                self.rows[y][x] = (
                    EMPTY if char == " " and bg == BLACK else Cell(char, fg, bg)
                )
                if width == 2:
                    self.rows[y][x + 1] = Cell("", fg, bg)
            x += width

    def center(self, y, text, fg=WHITE):
        self.text(y, max(0, (self.w - wcswidth(text)) // 2), text, fg)


def ansi_color(color, bg=False):
    return f"\x1b[{48 if bg else 38};2;{int(color[1:3], 16)};{int(color[3:5], 16)};{int(color[5:7], 16)}m"


class DiffRenderer:
    def __init__(self):
        self.previous = None

    def render(self, frame):
        initial = self.previous is None or (self.previous.w, self.previous.h) != (
            frame.w,
            frame.h,
        )
        out = ["\x1b[?25l\x1b[2J"] if initial else []
        style = None
        for y, row in enumerate(frame.rows):
            previous = None if initial else self.previous.rows[y]
            changed = [
                i
                for i, c in enumerate(row)
                if previous is None or (c is not previous[i] and c != previous[i])
            ]
            if not changed:
                continue
            start = changed[0]
            end = changed[-1] + 1
            if start and row[start].ch == "":
                start -= 1
            out.append(f"\x1b[{y + 1};{start + 1}H")
            for cell in row[start:end]:
                if cell.ch == "":
                    continue
                pair = (cell.fg, cell.bg)
                if style != pair:
                    out.append(ansi_color(cell.fg) + ansi_color(cell.bg, True))
                    style = pair
                out.append(cell.ch)
        if out:
            out.append("\x1b[0m")
        self.previous = frame
        return "".join(out)
