"""Terminal typography, clock and canvas mount helpers."""

from .layout import Rect
from .terminal import CYAN, DIM, WHITE


def illustration(frame, lines, area, color=WHITE):
    """Place an entire drawing without stretching or cutting its silhouette."""
    w = max(map(len, lines), default=0)
    if w > area.w or len(lines) > area.h:
        return False
    x = area.x + (area.w - w) // 2
    y = area.y + (area.h - len(lines)) // 2
    for n, line in enumerate(lines):
        frame.text(y + n, x, line, color)
    return True


def frame_border(frame, box, paper=False):
    color = "#62635a" if paper else DIM
    frame.text(box.y - 1, box.x - 1, "+" + "-" * box.w + "+", color)
    frame.text(box.y + box.h, box.x - 1, "+" + "-" * box.w + "+", color)
    for row in range(box.y, box.y + box.h):
        frame.text(row, box.x - 1, "|", color)
        frame.text(row, box.x + box.w, "|", color)


DIGITS = {
    "0": [" _ ", "| |", "|_|"],
    "1": ["   ", "  |", "  |"],
    "2": [" _ ", " _|", "|_ "],
    "3": [" _ ", " _|", " _|"],
    "4": ["   ", "|_|", "  |"],
    "5": [" _ ", "|_ ", " _|"],
    "6": [" _ ", "|_ ", "|_|"],
    "7": [" _ ", "  |", "  |"],
    "8": [" _ ", "|_|", "|_|"],
    "9": [" _ ", "|_|", " _|"],
    ":": ["   ", " . ", " . "],
}


def clock_art(frame, seconds, box, color=CYAN):
    time = f"{seconds // 60:02}:{seconds % 60:02}"
    lines = [" ".join(DIGITS[c][row] for c in time) for row in range(3)]
    illustration(frame, lines, Rect(box.x, box.y, box.w, 3), color)


def palette(kind):
    return ("#c1d4c9", "#718b80", "#354b43")


def paper_mount(frame, area, box, kind):
    frame_border(frame, box, paper=True)
