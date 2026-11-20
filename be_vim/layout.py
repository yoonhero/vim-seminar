"""Constraint-based terminal layout; canonical game coordinates never change."""

from dataclasses import dataclass

from wcwidth import wcswidth, wcwidth

# Stable, contiguous source rows across every stage of each lesson (end exclusive).
LESSON_ROWS = {"search": (6, 13), "visual": (6, 10), "clone": (3, 12)}


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int


@dataclass(frozen=True)
class Layout:
    header: Rect
    title: Rect
    goal: Rect
    stage: Rect
    scoreboard: Rect | None
    board_mode: str
    status: Rect
    feedback: Rect
    hint: Rect | None
    controls: Rect


def measure(width, height, scoreboard=False, kind=None):
    pad = 4 if width >= 100 else 2 if width >= 72 else 1
    inner = min(92 if kind and kind not in {"cover", "end"} else 160, width - 2 * pad)
    pad = (width - inner) // 2
    goal_h = 2 if height >= 44 else 1
    title_y = 2 if height >= 30 else 1
    title_h = (
        7 if height >= 48 and inner >= 90 else 5 if height >= 32 and inner >= 64 else 1
    )
    if kind and kind not in {"cover", "end"}:
        title_h = 1
    title_gap = 1 if height >= 24 else 0
    goal_y = title_y + title_h + title_gap
    top = goal_y + goal_h + (1 if height >= 30 else 0)
    hint_h = 1 if height >= 27 else 0
    body_h = max(1, height - top - 3 - hint_h)
    if kind in {"name", "jumps", "words", "search", "visual", "clone", "change"}:
        body_h = min(body_h, 18)
    # Give a short lesson a balanced position on a tall projector screen.
    if kind in {"name", "paddle", "jumps", "words", "search", "visual", "clone", "change", "draw", "gallery"}:
        if kind == "name":
            body_h = min(body_h, 18)
        if scoreboard and inner >= 70:
            body_h = min(body_h, 18)
        shift = max(0, (height - top - body_h - 3 - hint_h) // 2)
        top += shift
        goal_y += shift
        title_y += shift
    body = Rect(pad, top, inner, body_h)
    board = None
    mode = "none"
    stage = body
    if scoreboard:
        if inner >= 70:
            bw = min(32, max(25, inner // 4))
            gap = 3
            cw = min(42, inner - bw - gap)
            group_x = body.x + (body.w - cw - gap - bw) // 2
            group_h = min(18, body.h)
            stage = Rect(group_x, body.y, cw, group_h)
            board = Rect(group_x + cw + gap, body.y, bw, group_h)
            mode = "side"
        else:
            bh = 5 if body.h >= 23 else 2
            board = Rect(body.x, body.y + body.h - bh, body.w, bh)
            stage = Rect(body.x, body.y, body.w, max(1, body.h - bh - 1))
            mode = "stack"
    bottom = body.y + body.h
    return Layout(
        Rect(pad, 0, inner, 1),
        Rect(pad, title_y, inner, title_h),
        Rect(pad, goal_y, inner, goal_h),
        stage,
        board,
        mode,
        Rect(pad, bottom, inner, 1),
        Rect(pad, bottom + 1, inner, 1),
        Rect(pad, bottom + 2, inner, 1) if hint_h else None,
        Rect(pad, height - 1, inner, 1),
    )


def fit(text, width):
    if width <= 0:
        return ""
    if wcswidth(text) <= width:
        return text
    out = ""
    used = 0
    for c in text:
        n = max(0, wcwidth(c))
        if used + n > width - 1:
            break
        out += c
        used += n
    return out + "…"


def wrap(text, width, lines):
    if width <= 0 or lines <= 0:
        return []
    if lines == 1:
        return [fit(text, width)]
    result, row, used = [], "", 0
    for index, char in enumerate(text):
        size = max(0, wcwidth(char))
        if char == "\n" or used + size > width:
            result.append(row)
            row, used = "", 0
            if len(result) == lines - 1:
                return result + [fit(text[index:].lstrip("\n"), width)]
        if char != "\n":
            row += char
            used += size
    return (result + [row])[:lines]


def viewport(area, logical_w, logical_h, focus=None):
    """Center the full canvas when possible; otherwise pan around the cursor."""
    w = min(logical_w, max(1, area.w - 2))
    h = min(logical_h, max(1, area.h - 2))
    fy, fx = focus or (logical_h // 2, logical_w // 2)
    ox = max(0, min(logical_w - w, fx - w // 2))
    oy = max(0, min(logical_h - h, fy - h // 2))
    return Rect(area.x + (area.w - w) // 2, area.y + (area.h - h) // 2, w, h), (ox, oy)
