"""Fixed-step continuous breakout, independent of SSH and redraw cadence."""

import math
from dataclasses import dataclass, field


@dataclass
class Arena:
    stage: int = 0
    hits: int = 0
    stage_hits: int = 0
    misses: int = 0
    depth: float = 13.0
    paddle: float = 20.0
    target: float = 20.0
    x: float = 20.0
    y: float = 11.0
    vx: float = 10.0
    vy: float = -5.0
    started: bool = False
    wave: int = 1
    serve_delay: float = 0.0
    accumulator: float = 0.0
    bricks: list = field(default_factory=list)

    def __post_init__(self):
        self.setup()

    def setup(self):
        self.stage_hits = 0
        self.depth = 13.0 if self.stage == 0 else 3.0
        if self.stage == 0:
            self.paddle = self.target = 20.0
            self.x = 20.0
            self.y = 11.0
            self.vx = 10.0
            self.vy = -5.0
            self.bricks = [
                (x, y, 3.0, 0.75)
                for y in (2.0, 4.0, 6.0)
                for x in (6.0, 12.0, 18.0, 24.0, 30.0)
            ]
        else:
            self.paddle = self.target = 8.0
            self.x = 5.0
            self.y = 8.0
            self.vx = 15.0
            self.vy = -3.0
            self.bricks = [
                (x, y, 1.5, 1.5)
                for x in (28.0, 32.0, 36.0)
                for y in (2.0, 5.0, 8.0, 11.0)
            ]

        self.keystone = self.bricks[len(self.bricks) // 2]

    def key(self, k):
        if k == " ":
            self.started = True
            return
        keys = "hl" if self.stage == 0 else "kj"
        cross_keys = "kj" if self.stage == 0 else "hl"
        if k in cross_keys:
            self.started = True
            low, high = (9, 15) if self.stage == 0 else (1, 9)
            self.depth = max(
                low, min(high, self.depth + (-1 if k == cross_keys[0] else 1))
            )
        elif k in keys:
            self.started = True
            self.target += (-1 if k == keys[0] else 1) * (
                2.0 if self.stage == 0 else 0.85
            )
            low, high = (4.0, 35.0) if self.stage == 0 else (2.0, 13.0)
            self.target = max(low, min(high, self.target))

    def step(self, dt):
        self.accumulator += min(0.25, dt)
        while self.accumulator >= 1 / 120:
            self.accumulator -= 1 / 120
            self._step(1 / 120)

    def _step(self, dt):
        old_paddle = self.paddle
        self.paddle += (self.target - self.paddle) * (1 - math.exp(-18 * dt))
        if not self.started:
            return
        if self.serve_delay > 0:
            self.serve_delay -= dt
            if self.stage == 0:
                self.x, self.y = self.paddle, self.depth - 1
            else:
                self.x, self.y = self.depth + 1, self.paddle
            return

        # Sweep the ball centre against the contact planes. Consume the remaining
        # time after each bounce so a wall never steals part of the trajectory.
        remaining = dt
        contacts = []

        def plane(t, nx, ny, kind):
            if 0 <= t <= remaining:
                contacts.append((t, nx, ny, kind, None))

        for _ in range(4):
            contacts.clear()

            if self.vx < 0:
                plane(
                    (0.5 - self.x) / self.vx,
                    1,
                    0,
                    "wall" if self.stage == 0 else "miss",
                )
            elif self.vx > 0:
                plane((39 - self.x) / self.vx, -1, 0, "wall")
            if self.vy < 0:
                plane((0.5 - self.y) / self.vy, 0, 1, "wall")
            elif self.vy > 0:
                plane(
                    (15.5 - self.y) / self.vy,
                    0,
                    -1,
                    "miss" if self.stage == 0 else "wall",
                )

            if self.stage == 0 and self.vy > 0:
                t = (self.depth - self.y) / self.vy
                if abs(self.x + self.vx * t - self.paddle) <= 4:
                    plane(t, 0, -1, "paddle")
            elif self.stage == 1 and self.vx < 0:
                t = (self.depth - self.x) / self.vx
                if abs(self.y + self.vy * t - self.paddle) <= 2:
                    plane(t, 1, 0, "paddle")
            for brick in self.bricks:
                bx, by, w, h = brick
                # Include the visible radius in each axis (cells are twice as tall).
                left, right = bx - 0.25, bx + w + 0.25
                top, bottom = by - 0.125, by + h + 0.125
                if self.vx:
                    t = ((left if self.vx > 0 else right) - self.x) / self.vx
                    if (
                        0 <= t <= remaining
                        and top - 1e-9 <= self.y + self.vy * t <= bottom + 1e-9
                    ):
                        contacts.append((t, 1, 0, "brick", brick))
                if self.vy:
                    t = ((top if self.vy > 0 else bottom) - self.y) / self.vy
                    if (
                        0 <= t <= remaining
                        and left - 1e-9 <= self.x + self.vx * t <= right + 1e-9
                    ):
                        contacts.append((t, 0, 1, "brick", brick))

            t = min((hit[0] for hit in contacts), default=remaining)
            self.x += self.vx * t
            self.y += self.vy * t
            remaining -= t
            if not contacts:
                break
            hits = [hit for hit in contacts if abs(hit[0] - t) < 1e-9]
            if any(hit[3] == "miss" for hit in hits):
                self.misses += 1
                self.serve()
                return
            if any(hit[3] == "paddle" for hit in hits):
                horizontal = self.stage == 0
                offset = (
                    (self.x - self.paddle) / 4
                    if horizontal
                    else (self.y - self.paddle) / 2
                )
                motion = max(-1, min(1, (self.paddle - old_paddle) / dt / 30))
                angle = math.radians(max(-67, min(67, 58 * offset + 9 * motion)))
                speed = math.hypot(self.vx, 2 * self.vy)
                tangent, normal = speed * math.sin(angle), speed * math.cos(angle)
                self.vx, self.vy = (
                    (tangent, -normal / 2) if horizontal else (normal, tangent / 2)
                )
            else:
                if any(hit[1] for hit in hits):
                    self.vx *= -1
                if any(hit[2] for hit in hits):
                    self.vy *= -1
            broken = {hit[4] for hit in hits if hit[4] is not None}
            if self.keystone in broken:
                axis = 1 if self.stage == 0 else 0
                broken.update(brick for brick in self.bricks if brick[axis] == self.keystone[axis])
            for brick in broken:
                self.bricks.remove(brick)
                self.hits += 1
                self.stage_hits += 1
            if not self.bricks:
                self.wave += 1
                self.stage = 1 - self.stage
                self.setup()
                self.serve()
                return

    def serve(self):
        self.serve_delay = 0.65
        if self.stage == 0:
            self.x, self.y = self.paddle, self.depth - 1
            self.vx, self.vy = (10 if self.misses % 2 == 0 else -10), -5
        else:
            self.x, self.y = self.depth + 1, self.paddle
            self.vx, self.vy = 15, (3 if self.misses % 2 else -3)

    def picture(self, width=40, height=16):
        sx, sy = width / 40, height / 16
        grid = [[" "] * width for _ in range(height)]
        for x, y, w, h in self.bricks:
            for row in range(
                int(y * sy), min(height, max(int(y * sy) + 1, math.ceil((y + h) * sy)))
            ):
                for col in range(
                    int(x * sx),
                    min(width, max(int(x * sx) + 1, math.ceil((x + w) * sx))),
                ):
                    grid[row][col] = "*" if (x, y, w, h) == self.keystone else "█"
        if self.stage == 0:
            for x in range(
                max(0, int((self.paddle - 4) * sx)),
                min(width, int((self.paddle + 4) * sx)),
            ):
                grid[min(height - 1, int(self.depth * sy))][x] = "━"
        else:
            for y in range(
                max(0, int((self.paddle - 2) * sy)),
                min(height, math.ceil((self.paddle + 2) * sy)),
            ):
                grid[y][min(width - 1, int(self.depth * sx))] = "┃"
        # Braille provides 2x4 sub-cell positions; three dots make the ball legible.
        points = {}
        bits = ((0, 3), (1, 4), (2, 5), (6, 7))
        bx, by = int(self.x * sx * 2), int(self.y * sy * 4)
        for dx, dy in ((1, 0), (0, 1), (1, 1), (2, 1), (0, 2), (1, 2), (2, 2), (1, 3)):
            mx, my = bx + dx, by + dy
            cx, cy = mx // 2, my // 4
            if 0 <= cx < width and 0 <= cy < height:
                points[(cy, cx)] = points.get((cy, cx), 0) | (1 << bits[my % 4][mx % 2])
        for (y, x), v in points.items():
            grid[y][x] = chr(0x2800 + v)
        return ["".join(row) for row in grid]
