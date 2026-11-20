"""Independent per-person game state and objective checks for every lesson."""

import re
from dataclasses import dataclass

from . import maze
from .editor import H, W
from .physics import Arena


def blank():
    return [" " * W for _ in range(H)]


def at(rows, y, text):
    rows[y] = text.ljust(W)
    return rows


@dataclass
class Puzzle:
    rows: list
    cursor: tuple
    goal: str
    target: list
    check: str
    expected: object


def puzzle(kind, stage):
    rows = blank()
    if kind == "jumps":
        route = maze.TUNNELS[stage][0]
        return Puzzle(maze.map_rows(stage), route[0], "@ 나  →  * 균열   ·   점을 따라 이동하세요.",
                      [route[-1]], "cursor", route[-1])
    if kind == "words" and stage == 2:
        text = "base seam gap arch exit"
        rows = at(rows, 8, text)
        ends = [(8, text.index("base")), (8, text.index("exit"))]
        return Puzzle(rows, (8, text.index("arch") + 3),
                      "왼쪽 base 또는 오른쪽 exit의 첫 글자로 빠져나가세요.",
                      ends, "either_cursor", ends)
    if kind == "words":
        text = "base seam gap arch exit"
        rows = at(rows, 8, text)
        word = ["gap", "arch"][stage]
        start = text.index(word)
        pos = start + (len(word) - 1 if stage == 1 else 0)
        return Puzzle(
            rows,
            (8, [0, text.index("gap")][stage]),
            f"{word}의 {'끝' if stage == 1 else '시작'}에 도착하세요. {'e' if stage == 1 else 'w' if stage == 0 else 'b'}",
            [(8, x) for x in range(start, start + len(word))],
            "cursor",
            (8, pos),
        )
    if kind == "search":
        text = "....*........*........*"
        rows = at(rows, 6, text)
        rows = at(rows, 10, "  crack   north")
        rows = at(rows, 12, "  crack   south")
        goals = [(6, 4), (6, 13), (10, 2), (12, 2)]
        starts = [(6, 0), (6, 4), (6, 13), (10, 2)]
        hints = [
            "첫 번째 *에 탐침을 맞추세요.",
            "지금 찾은 방향으로 다음 *까지 이동하세요.",
            "벽면 기록에서 첫 crack을 찾으세요.",
            "같은 기록의 두 번째 crack을 찾으세요.",
        ]
        return Puzzle(
            rows, starts[stage], hints[stage], [goals[stage]], "cursor", goals[stage]
        )
    if kind == "visual" and stage == 1:
        line = "    | SEAM |      | SEAM |"
        rows = at(rows, 9, line)
        starts = [line.index("SEAM"), line.rindex("SEAM")]
        seams = [[(9, x+i) for i in range(4)] for x in starts]
        return Puzzle(rows, seams[0][0], "두 이음새 중 하나를 골라 SEAM 네 글자만 감싸세요.",
                      seams[0] + seams[1], "either_selection", seams)
    if kind == "visual":
        if stage == 0:
            rows = at(rows, 6, "       | VIM |     |     |")
            rows = at(rows, 9, "   |     |     | SEAM |")
            word = "VIM"
            y = 6
            x = rows[y].index(word)
            target = [(y, k) for k in range(x, x + len(word))]
            return Puzzle(
                rows,
                (y, x),
                f"{word}만 정확히 선택하세요.",
                target,
                "selection",
                target,
            )
        for y in range(7, 10):
            rows[y] = " " * 16 + "." * 5 + " " * 19
        target = [(y, x) for y in range(7, 10) for x in range(16, 21)]
        return Puzzle(
            rows, (7, 16), "점으로 표시된 세 줄을 사각형으로 잡아 #로 채우세요.", target, "fill", "#"
        )
    if kind == "clone":
        rows = at(rows, 5, "       [X]     ...")
        if stage == 0:
            return Puzzle(
                rows,
                (5, 7),
                "왼쪽 [X]를 오른쪽 ...에 복사하세요.",
                [(5, x) for x in range(15, 18)],
                "text_at",
                "[X]",
            )
        rows = at(rows, 5, "       [X]     [X]")
        rows = at(rows, 11, "       [X]     ...")
        if stage == 1:
            return Puzzle(
                rows,
                (5, 7),
                "아래층의 ...에도 [X]를 복사하세요.",
                [(11, x) for x in range(15, 18)],
                "text_at",
                "[X]",
            )
        rows = at(rows, 5, "       [X]     [X]")
        return Puzzle(
            rows, (5, 8), "잘못 바뀐 철거 표시를 u로 되돌리세요.", [(5, 8)], "text_at", "X"
        )
    if kind == "change":
        if stage == 0:
            rows = at(rows, 7, "BLOCK exit")
            return Puzzle(
                rows,
                (7, 0),
                "BLOCK을 지워 출구를 여세요. dw",
                [(7, x) for x in range(3)],
                "line",
                (7, "exit"),
            )
        rows = at(rows, 7, "shut shut shut")
        return Puzzle(
            rows,
            (7, 0),
            "첫 문을 open으로 바꾸고 나머지 두 문에도 반복하세요.",
            [(7, x) for x in range(14)],
            "line",
            (7, "open open open"),
        )
    raise ValueError(kind)


STAGES = {"jumps": 3, "words": 3, "search": 4, "visual": 3, "clone": 3, "change": 2}


class Game:
    def __init__(self, kind, editor):
        self.kind = kind
        self.editor = editor
        self.stage = 0
        self.complete = False
        self.feedback = ""
        self.awaiting_next = False
        self.snapshot = None
        self.spec = None
        self.arena = Arena() if kind == "paddle" else None
        self.keys = ""
        self.palette_open = False
        self.hint_requested = False
        self.move_count = ""
        self.trail = set()
        self.cleared = 0
        self.started = False

    async def activate(self):
        if self.arena:
            return
        if not self.started:
            await self.prepare()
            self.started = True
        else:
            await self.editor.activate(self.kind)
        self.snapshot = await self.editor.snapshot()

    async def prepare(self):
        self.move_count = ""
        self.trail.clear()
        self.palette_open = False
        self.hint_requested = False
        if self.kind in STAGES:
            self.spec = puzzle(self.kind, self.stage)
            await self.editor.activate(
                self.kind, self.spec.rows, self.spec.cursor, reset=True
            )
            if self.kind == "clone" and self.stage == 2:
                await self.editor.key("r")
                await self.editor.key("?")
        else:
            await self.editor.activate(self.kind, blank(), (0, 0), reset=True)
        self.snapshot = await self.editor.snapshot()

    async def key(self, key):
        if self.kind == "draw" and not self.snapshot.get("pending"):
            mode = self.snapshot["mode"]
            if self.palette_open:
                self.palette_open = False
                if key in "123456" and len(key) == 1:
                    self.editor.ink = int(key) - 1
                return None
            if mode in ("n", "v", "V", "\x16"):
                if key == "p":
                    self.palette_open = True
                    return None
                if key in (" ", "x"):
                    await self.editor.fill(erase=key == "x")
                    await self.update(0)
                    return None
                if key == "v" and mode == "n":
                    key = "\x16"
        if self.arena:
            self.arena.key(key)
            return None
        if (key == "?" and self.kind in STAGES and self.snapshot["mode"] == "n"
                and not self.snapshot.get("pending") and not self.awaiting_next and not self.complete):
            self.hint_requested = not self.hint_requested
            return None
        if key == "\x0c" and self.kind in STAGES:
            self.awaiting_next = False
            self.complete = False
            self.feedback = ""
            self.keys = ""
            await self.prepare()
            return None
        if self.awaiting_next:
            if key in ("\r", "\n"):
                self.stage += 1
                self.awaiting_next = False
                self.feedback = ""
                self.keys = ""
                await self.prepare()
            return None
        if self.complete and self.kind != "name":
            if key == " ":
                self.stage = 0
                self.keys = ""
                self.feedback = ""
                self.complete = False
                self.feedback = ""
                await self.prepare()
            return None
        if self.kind == "name" and key in ("\r", "\n"):
            self.snapshot = await self.editor.snapshot()
            if self.snapshot["mode"] == "i":
                await self.editor.key("\x1b")
                self.snapshot = await self.editor.snapshot()
            if self.snapshot["mode"] == "n":
                name = self.snapshot["raw_lines"][0].strip()
                if re.fullmatch(r"[\w-]{1,16}", name):
                    return name
                self.feedback = "한글·영문·숫자·_·- 1~16자로 입력하세요."
                return None
        if self.kind == "jumps":
            if key in "0123456789":
                self.move_count = (self.move_count + key)[:3]
                self.feedback = f"{self.move_count}칸 · 방향을 누르세요"
                return None
            if key == "\x1b":
                self.move_count = ""
                self.feedback = ""
                return None
            if key not in maze.MOVES:
                return None
            count = int(self.move_count or "1")
            self.move_count = ""
            start = tuple(self.snapshot["cursor"])
            path = maze.walk(self.spec.rows, start, key, count)
            if not path:
                self.feedback = "막힌 벽 · 다른 방향으로 이동하세요."
                return None
            self.trail.update([start, *path[:-1]])
            for part in (str(len(path)) if len(path) > 1 else "") + key:
                await self.editor.key(part)
            await self.update(0)
            if not self.awaiting_next and not self.complete:
                self.feedback = "벽 앞에서 멈춤" if len(path) < count else ""
            return None
        if self.kind == "words" and key not in "hjklwbe0123456789$^Gg\x1b":
            return None
        self.keys = (
            self.keys
            + {"\x1b": " Esc ", "\r": " Enter ", "\x16": " Ctrl-v ", "\t": " Tab "}.get(
                key, key
            )
        )[-32:]
        self.feedback = ""
        await self.editor.key(key)
        await self.update(0)
        return None

    async def update(self, dt):
        if self.arena:
            self.arena.step(dt)
            return
        self.snapshot = await self.editor.snapshot()
        if self.snapshot.get("pending") or self.kind not in STAGES or self.complete:
            return
        if self.awaiting_next:
            return
        s = self.snapshot
        sp = self.spec
        ok = False
        if sp.check == "cursor":
            ok = tuple(s["cursor"]) == sp.expected and s["mode"] == "n"
        elif sp.check == "either_cursor":
            ok = tuple(s["cursor"]) in sp.expected and s["mode"] == "n"
        elif sp.check == "either_selection":
            ok = s["mode"] == "v" and any(set(s["selected"]) == set(seam) for seam in sp.expected)
        elif sp.check == "selection":
            ok = set(s["selected"]) == set(sp.expected) and s["mode"] == "v"
        elif sp.check == "fill":
            ok = (
                all(s["lines"][y][x] == sp.expected for y, x in sp.target)
                and s["mode"] == "n"
            )
        elif sp.check == "text_at":
            ok = (
                "".join(s["lines"][y][x] for y, x in sp.target) == sp.expected
                and s["mode"] == "n"
            )
        elif sp.check == "line":
            ok = (
                s["lines"][sp.expected[0]].strip() == sp.expected[1]
                and s["mode"] == "n"
            )
        if ok:
            self.cleared = max(self.cleared, self.stage + 1)
            result = {"jumps": "균열 도착", "words": "통로 연결", "search": "균열 발견",
                      "visual": "철거 구역 확보", "clone": "철거 표시 복원",
                      "change": "출구 개방"}[self.kind]
            if self.stage + 1 == STAGES[self.kind]:
                self.complete = True
                self.feedback = result + " · Space 다시 하기"
            else:
                self.awaiting_next = True
                self.feedback = result + " · Enter 다음 문제"

    @property
    def goal(self):
        if self.kind == "name":
            return "벽돌에 새길 이름을 입력하고 Enter로 저장하세요."
        if self.arena:
            return (
                "가로 패들" if self.arena.stage == 0 else "세로 패들"
            ) + f" · 남은 벽돌 {len(self.arena.bricks)}개" + (" · *를 맞히면 한 줄 돌파" if self.arena.keystone in self.arena.bricks else "")
        if self.spec:
            return self.spec.goal
        return ""

    @property
    def progress(self):
        if self.arena:
            return f"{self.arena.wave}판 · 깬 벽돌 {self.arena.hits}개 · 놓친 공 {self.arena.misses}"
        if self.kind in STAGES:
            done = self.stage + int(self.awaiting_next or self.complete)
            progress = f"{done}/{STAGES[self.kind]} 완료"
            if not self.awaiting_next and not self.complete and self.snapshot:
                if self.spec.check in ("selection", "either_selection", "fill"):
                    selected = set(self.snapshot["selected"])
                    candidates = self.spec.expected if self.spec.check == "either_selection" else [self.spec.target]
                    closest = max(candidates, key=lambda path: len(selected.intersection(path)))
                    if selected:
                        matched = len(selected.intersection(closest))
                        extra = len(selected) - matched
                        progress += f" · 선택 {matched}/{len(closest)}"
                        if extra:
                            progress += f" · 범위 밖 {extra}칸"
                elif self.kind == "change" and self.stage == 1:
                    row = self.snapshot["lines"][7]
                    progress += f" · 열린 문 {row.split().count('open')}/3"
            return progress
        return ""

    def scene(self):
        if self.arena:
            return {
                "lines": self.arena.picture(),
                "cursor": None,
                "selected": [],
                "target": [],
                "colors": [[0] * W for _ in range(H)],
                "mode": "PLAY",
                "command": "",
            }
        s = dict(self.snapshot)
        s["target"] = self.spec.target if self.spec else []
        if self.kind == "name":
            grid = blank()
            from wcwidth import wcwidth

            # Project Unicode into terminal cells; wide characters own both columns.
            cells = list("name: ")
            for char in s["raw_lines"][0].rstrip():
                width = wcwidth(char)
                if width > 0:
                    cells.extend([char] + [""] * (width - 1))
            grid[8] = (cells + [" "] * W)[:W]
            s["lines"] = grid
            col = min(W - 1, 6 + s["cursor"][1])
            if grid[8][col] == "":
                col -= 1
            s["cursor"] = (8, col)
        elif self.kind == "jumps":
            s["trail"] = self.trail
        return s
