"""Live Vim cells embedded in the seminar's original field-guide engravings."""

import math
from functools import lru_cache

from .layout import fit

CREAM = "#e8ddbb"
SAGE = "#a5b59e"
SHADE = "#687b70"
VERMILION = "#fa8458"
LABELS = {
    "name": "쌀 한 톨",
    "words": "회유 경로",
    "clone": "가자미",
    "visual": "참다랑어",
    "change": "오징어",
    "search": "불가사리",
    "jumps": "수직 잠수",
}


def sample(kind, x, y):
    if kind in ("visual", "words", "clone"):
        if kind == "words":
            x = ((x + 1) * 3 % 2) - 1
            y = y * 2 + 0.23 * math.sin(6 * x)
        flat = kind == "clone"
        u, q = (x - 0.06) / 0.7, (y + 0.1 * math.sin(x * 4)) / (0.95 if flat else 0.73)
        tail = -0.99 < x < -0.55 and abs(y) < (-x - 0.54) * 1.7
        body = u * u + q * q < 1
        fin = -0.3 < x < 0.16 and -0.95 < y < -0.54 and y > -0.95 + abs(x + 0.12) * 1.3
        if body and (
            (x - 0.48) ** 2 + (y + 0.12) ** 2 < 0.011
            or flat
            and (x - 0.31) ** 2 + (y + 0.34) ** 2 < 0.009
        ):
            return "o", VERMILION
        if body and abs(x - (0.33 - 0.10 * y * y)) < 0.027:
            return ")", SHADE
        return body or tail or fin
    if kind == "search":
        return math.hypot(x, y) < 0.52 + 0.35 * math.cos(5 * math.atan2(y, x) - 1.5)
    if kind == "name":
        return ((x + 0.32 * y) / 0.8) ** 2 + ((y - 0.27 * x) / 0.57) ** 2 < 1
    if kind == "jumps":
        return (
            (x / 0.66) ** 2 + ((y + 0.07) / 0.43) ** 2 < 1
            or abs(x + 0.17) < 0.035
            and -0.79 < y < -0.36
            or -0.19 < x < 0.07
            and -0.83 < y < -0.74
            or -0.9 < x < -0.61
            and abs(y) < 0.29
        )
    if kind == "change":
        return (x / 0.38) ** 2 + ((y + 0.34) / 0.66) ** 2 < 1 or (
            0.23 < y < 1
            and abs(math.sin(20 * x + 3 * y)) > 0.65
            and abs(x) < 0.38 + 0.21 * y
        )
    raise ValueError(kind)


@lru_cache(maxsize=128)
def engraving(kind, width, height):
    points = []
    for row in range(height):
        for col in range(width):
            x = 2 * (col + 0.5) / width - 1
            y = 2 * (row + 0.5) / height - 1
            mark = sample(kind, x, y)
            if mark:
                grain = ".,:;=+|/"[int(col * 0.32 - row * 1.5) % 8]
                ch, color = (
                    mark
                    if isinstance(mark, tuple)
                    else (grain, CREAM if y < 0 else SAGE if y < 0.48 else SHADE)
                )
                points.append((col, row, ch, color))
    return points


def board(frame, area, scene, focus, kind):
    """Project the live Vim grid onto the specimen, including its single real cursor."""
    from .layout import LESSON_ROWS

    fy, fx = scene.get("cursor") or focus or (8, 0)
    cursor = scene.get("cursor")
    selected = set(scene.get("selected", ()))
    targets = set(scene.get("target", ()))
    width = min(60, area.w)
    height = min(16, area.h)
    left = area.x + (area.w - width) // 2
    top = area.y + (area.h - height) // 2
    cols = min(40, width)
    first, end = LESSON_ROWS.get(kind, (0, 16))
    origin_y = max(0, min(16 - height, fy - height // 2))
    origin_x = max(0, min(40 - cols, fx - cols // 2))
    for dx, dy, ch, color in engraving(kind, width, height):
        if kind == "clone":
            dx = width - 1 - dx
            if ch == "o":
                ch, color = ".", SAGE
        frame.text(top + dy, left + dx, ch, color)
    if kind == "jumps" and area.w >= 42:
        # Widen map tiles, not Vim steps. Keep the whole tunnel in view when it fits.
        used = [col for line in scene["lines"] for col, ch in enumerate(line) if ch.strip()]
        if used:
            pitch = 3 if area.w >= (max(used)-min(used)+1)*3 else 2
            cols = min(40, area.w // pitch)
            origin_x = max(0, min(min(used), (min(used)+max(used)+1-cols)//2))
            origin_x = max(0, min(40-cols, min(fx, max(origin_x, fx-cols+1))))
            map_x = area.x + (area.w-cols*pitch)//2
            for row in range(origin_y, origin_y+height):
                for col in range(origin_x, origin_x+cols):
                    ch = scene["lines"][row][col]
                    if ch == " ":
                        continue
                    token, fg, bg = {
                        "#": ("─"*pitch, "#668078", "#24322d"),
                        ".": ("·".center(pitch), "#9caaa1", "#101716"),
                        "*": (" * ".center(pitch)[:pitch], "#19150c", "#f2d479"),
                    }[ch]
                    if (row,col) in scene.get("trail", ()) and ch == ".":
                        token, fg = ":".center(pitch), "#b1e5df"
                    if cursor and (row,col) == tuple(cursor):
                        token, fg, bg = ("[@]" if pitch == 3 else "@ "), "#131713", VERMILION
                    frame.text(top+row-origin_y, map_x+(col-origin_x)*pitch, token, fg, bg)
            return origin_x > min(used) or origin_x+cols <= max(used) or height < 16
    x = left + (width - cols) // 2
    for row in range(origin_y, origin_y + height):
        line = scene["lines"][row]
        nonempty = [i for i, c in enumerate(line) if c.strip()]
        bounds = (nonempty[0], nonempty[-1]) if nonempty else (1, 0)
        for col in range(origin_x, origin_x + cols):
            pos = (row, col)
            ch = line[col] if col < len(line) else " "
            fg, bg = CREAM, "#000000"
            if kind == "jumps":
                if ch == " ":
                    continue
                fg, bg = {"#": ("#75928b", "#293632"), ".": ("#9caaa1", "#101716"),
                          "*": ("#111710", "#f2d479")}[ch]
                if pos in scene.get("trail", ()) and ch == ".":
                    ch, fg = ":", "#a6dfd5"
                if cursor and pos == tuple(cursor):
                    ch, fg, bg = "@", "#131713", VERMILION
                frame.text(top + row - origin_y, x + col - origin_x, ch, fg, bg)
                continue
            if pos in targets:
                fg, bg = VERMILION, "#241c17"
            if pos in selected:
                fg, bg = CREAM, "#285b4d"
            if cursor and pos == tuple(cursor):
                fg, bg = "#171c19", VERMILION
            # Only real buffer text and actionable cells interrupt the engraving.
            if ch != " " or bg != "#000000" or bounds[0] <= col <= bounds[1]:
                frame.text(top + row - origin_y, x + col - origin_x, ch, fg, bg)
    if left - area.x >= 11:
        frame.text(
            top + height // 2, area.x, fit(LABELS[kind], left - area.x - 1), SAGE
        )
    return cols < 40 or height < end - first
