"""Shared-time free-swimming glyph fish, bow waves and historical tail vortices.

Only ASCII cells and ANSI colors are emitted. The trajectories are continuous
curves in two dimensions, with no left/right teleport or visible reset.
"""

import math
from functools import lru_cache
from typing import NamedTuple

NAMES = ("유영", "물결", "잔상")
CREAM = ("#789086", "#b8c3ac", "#dadbc3", "#f0ead6")
WATER = ("#203536", "#375753", "#659086")
TOKENS = "rice:vim:hjkl:"


class Fish(NamedTuple):
    size: float
    phase: float
    period: float
    depth: float


FISH = (
    Fish(0.045, 2.7, 39, 0.65),
    Fish(0.055, 4.4, 34, 0.75),
    Fish(0.065, 1.2, 43, 0.85),
    Fish(0.075, 5.6, 31, 0.9),
    Fish(0.105, 1.65, 37, 1.0),
)


def pose(fish, t, width, height):
    a = math.tau * t / fish.period + fish.phase
    b = 1.7 * a + fish.phase
    c = 2.3 * a - fish.phase
    x = 0.50 + 0.24 * math.cos(a) + 0.07 * math.sin(b)
    y = 0.52 + 0.23 * math.sin(a) + 0.045 * math.cos(c)
    dx = -0.24 * math.sin(a) + 0.119 * math.cos(b)
    dy = 0.23 * math.cos(a) - 0.1035 * math.sin(c)
    angle = math.atan2(dy * height * 2, dx * width)
    return x * width, y * height, angle, math.hypot(dx, dy)


@lru_cache(maxsize=48)
def shade(width, height, tick, effect, dim):
    t = tick / 12
    cells = {}

    def put(x, y, char, fg, bg="#000000"):
        x, y = round(x), round(y)
        if 0 <= x < width and 0 <= y < height:
            cells[(x, y)] = (x, y, char, fg, bg)

    actors = []
    for fish in FISH:
        x, y, angle, speed = pose(fish, t, width, height)
        rx = max(3.5, fish.size * width)
        ry = max(1.5, rx * 0.42)
        actors.append((fish, x, y, angle, speed, rx, ry))
    # Thin packets of water bend around each fish's occupied volume.
    bands = 4 if dim else 7 if effect == 1 else 6
    for band in range(bands):
        previous = None
        for x in range(width):
            y = height * (
                0.10
                + band * (0.8 / (bands - 1))
                + (0.03 if effect == 1 else 0.015)
                * math.sin(x / width * 8 - t * 0.65 + band)
            )
            pressure = 0.0
            for _, cx, cy, _, _, rx, ry in actors:
                dx = (x - cx) / rx
                dy = (y - cy) * 2 / ry
                if abs(dx) < 2.6 and abs(dy) < 3:
                    force = math.exp(-dx * dx * 0.7 - dy * dy * 0.21)
                    y += math.copysign(ry * 0.46 * force, dy or 1)
                    pressure = max(pressure, force)
            if previous is not None and (x - t * 5 + band * 7) % 19 < 8:
                slope = y - previous
                ch = (
                    ("\\" if slope > 0 else "/")
                    if abs(slope) > 0.24
                    else ("~" if x % 4 else ".")
                )
                put(x, y, ch, WATER[1 if pressure > 0.35 and not dim else 0])
            previous = y
    # Water is painted first, so fish remain the foreground and occlude wakes.
    for fish, cx, cy, angle, speed, rx, ry in actors:
        cs, sn = math.cos(angle), math.sin(angle)

        for side in (-1, 1):
            for k in range(12):
                u = k / 11
                uu, qq = 1.20 - 1.50 * u, side * (0.12 + 1.1 * math.sin(u * 1.52))
                px, py = (
                    cx + uu * rx * cs - qq * ry * sn,
                    cy + (uu * rx * sn + qq * ry * cs) / 2,
                )
                if k % 3 != 1:
                    put(px, py, "~" if u > 0.3 else "/", WATER[0 if dim else 2])
        spacing = 0.68 + fish.phase * 0.015
        newest = math.floor((t + fish.phase) / spacing)
        for n in range(9 if effect == 2 else 6):
            birth = (newest - n) * spacing - fish.phase
            age = t - birth
            if not 0 <= age <= 4.8:
                continue
            hx, hy, ha, _ = pose(fish, birth, width, height)
            side = 1 if (newest - n) % 2 == 0 else -1
            tx = hx - rx * 1.3 * math.cos(ha) + age * 0.25 * math.cos(ha)
            ty = hy - rx * 0.65 * math.sin(ha) + side * ry * (0.10 + age * 0.035)
            radius = 0.40 + age * 0.42
            for j in range(9):
                a = side * (j / 8 * math.tau * 0.8 + age * 0.6)
                r = radius * (0.30 + j / 13)
                put(
                    tx + math.cos(a) * r * 1.8,
                    ty + math.sin(a) * r,
                    "." if age > 2.5 else "~",
                    WATER[0 if dim or age > 2.5 else 1],
                )
    for fish, cx, cy, angle, speed, rx, ry in actors:
        cs, sn = math.cos(angle), math.sin(angle)
        beat = t * math.tau / (1.9 + fish.phase * 0.04) + fish.phase
        swing = (0.20 + speed * 0.18) * math.sin(beat - 3.1)
        reach = math.ceil(rx * 1.8 + ry)
        for y in range(
            max(0, int(cy - reach / 2)), min(height, int(cy + reach / 2) + 1)
        ):
            for x in range(max(0, int(cx - reach)), min(width, int(cx + reach) + 1)):
                dx = x + 0.5 - cx
                dy = (y + 0.5 - cy) * 2
                u = (dx * cs + dy * sn) / rx
                q = (-dx * sn + dy * cs) / ry - 0.065 * math.sin(u * 2.8 + beat) * max(
                    0, 1 - u
                ) ** 1.4
                edge = max(0, 1 - u * u) ** 0.62 - abs(q)
                body = abs(u) < 1 and edge >= 0
                tail_u = (-u - 0.88) / 0.64
                tail = (
                    0 < tail_u < 1
                    and 0.28 * tail_u < abs(q - swing * tail_u) < 0.12 + 0.64 * tail_u
                )
                if not (body or tail):
                    continue
                char = "/" if q < 0 else "\\"
                fg = CREAM[0 if dim else 2]
                bg = "#000000"
                if body:
                    tx = math.floor((u + 1) * rx)
                    ty = math.floor((q + 1) * ry / 2)
                    char = TOKENS[(tx + ty * 3) % len(TOKENS)]
                    level = 3 if q < -0.2 else 1 if q > 0.46 else 2
                    fg, bg = "#334138", CREAM[level]
                    if edge < 0.14:
                        char = "."
                        fg, bg = CREAM[2], "#000000"
                    if (
                        -0.72 < u < 0.32
                        and abs(q - 0.04 - 0.11 * math.sin((u + 0.7) * 2.1)) < 0.09
                    ):
                        char = ":"
                        fg, bg = CREAM[1], "#31453b"
                    if 0.36 < u < 0.46 and -0.25 < q < 0.35:
                        char = ")"
                    if dim:
                        fg, bg = CREAM[0], "#000000"
                put(x, y, char, fg, bg)
        ex = cx + 0.63 * rx * cs + 0.18 * ry * sn
        ey = cy + (0.63 * rx * sn - 0.18 * ry * cs) / 2
        put(ex, ey, "o", CREAM[2] if dim else "#20302a", "#000000" if dim else CREAM[3])
    return tuple(cells.values())


def paint(frame, area, t, effect, protect=None, dim=False):
    if area.w < 8 or area.h < 5:
        return
    for col, row, char, fg, bg in shade(area.w, area.h, int(t * 12), effect, dim):
        x, y = area.x + col, area.y + row
        if (
            protect
            and protect.x - 2 <= x < protect.x + protect.w + 2
            and protect.y - 1 <= y < protect.y + protect.h + 1
        ):
            continue
        frame.text(y, x, char, fg, bg)
