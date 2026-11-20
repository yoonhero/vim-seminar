"""Shared presenter state; private games; one authoritative round and reveal clock."""

import asyncio
import copy
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from .editor import Editor
from .games import Game
from .slides import SLIDES

log = logging.getLogger(__name__)


@dataclass
class Person:
    id: str
    name: str
    editor: Editor
    host: bool = False
    named: bool = False
    connected: bool = True
    games: dict = field(default_factory=dict)
    current: Game | None = None
    message: str = ""
    control_menu: bool = False
    review_slide: int | None = None

    async def activate(self, kind):
        self.message = ""
        if kind in ("cover", "gallery", "end"):
            self.current = None
            return
        if kind not in self.games:
            self.games[kind] = Game(kind, self.editor)
        self.current = self.games[kind]
        await self.current.activate()


class Room:
    def __init__(self, args):
        self.args = args
        self.players = {}
        self.presenter = None
        self.slide = 0
        self.lock = asyncio.Lock()
        self.judge = None
        self.judge_error = ""
        self.judge_busy = False
        self.tasks = []
        self.round_phase = "waiting"
        self.started = None
        self.roster = []
        self.live = {}
        self.frozen = None
        self.final = {}
        self.final_art = {}
        self.revealed = []
        self.focus = None
        self.reveal_phase = "idle"
        self.held_order = []
        self.votes = {}
        self.closed = False
        self.shader_effect = 0
        self.shader_paused = False
        self.shader_elapsed = 0.0
        self.shader_since = time.monotonic()

    def shader_time(self):
        return (
            self.shader_elapsed
            if self.shader_paused
            else self.shader_elapsed + time.monotonic() - self.shader_since
        )

    @property
    def kind(self):
        return SLIDES[self.slide].kind

    async def setup(self):
        editor = Editor()
        await editor.start()
        self.presenter = Person(
            "host", "발표자", editor, host=True, named=True, connected=False
        )

    async def add_player(self):
        if len(self.players) >= 30:
            raise ValueError("참가 정원 30명입니다.")
        editor = Editor()
        await editor.start()
        p = Person(uuid.uuid4().hex[:10], f"참가자{len(self.players) + 1:02}", editor)
        self.players[p.id] = p
        await p.activate(self.kind)
        return p

    def page(self, p):
        return self.slide if p.review_slide is None else p.review_slide

    async def navigate(self, p, dest):
        dest = max(0, min(dest, self.slide))
        review = None if dest == self.slide else dest
        if p.review_slide != review:
            await p.activate(SLIDES[dest].kind)
            p.review_slide = review

    async def goto(self, delta):
        if self.round_phase in ("running", "judging"):
            self.presenter.message = "라운드 마감과 채점이 끝나면 이동할 수 있어요."
            return
        self.slide = max(0, min(len(SLIDES) - 1, self.slide + delta))
        self.transitioning = True
        try:
            following = [self.presenter]
            for person in self.players.values():
                if person.review_slide is None or person.review_slide >= self.slide:
                    person.review_slide = None
                    following.append(person)
            await asyncio.gather(*(p.activate(self.kind) for p in following))
        finally:
            self.transitioning = False

    async def handle(self, p, key):
        async with self.lock:
            if p.host:
                if key == "ControlG":
                    p.control_menu = not p.control_menu
                    return
                if p.control_menu:
                    p.control_menu = False
                    key = {
                        "n": "PageDown",
                        "p": "PageUp",
                        "s": "F5",
                        "r": "F6",
                        "e": "F3",
                        "a": "F4",
                    }.get(key, "Escape")
                if key == "PageDown":
                    await self.goto(1)
                    return
                if key == "PageUp":
                    await self.goto(-1)
                    return
                if key == "F3":
                    self.shader_effect = (self.shader_effect + 1) % 3
                    return
                if key == "F4":
                    self.shader_elapsed = self.shader_time()
                    self.shader_since = time.monotonic()
                    self.shader_paused = not self.shader_paused
                    return
                if key == "F5":
                    await self.start_round()
                    return
                if key == "F6":
                    self.begin_reveal()
                    return
            else:
                if key == "ControlG":
                    p.control_menu = not p.control_menu
                    return
                if p.control_menu:
                    p.control_menu = False
                    key = {"p": "PageUp", "n": "PageDown", "l": "Follow"}.get(key)
                    if key is None:
                        return
                if key in ("PageUp", "PageDown", "Follow"):
                    dest = self.slide if key == "Follow" else self.page(p) + (1 if key == "PageDown" else -1)
                    await self.navigate(p, dest)
                    return
                if key in ("F3", "F4", "F5", "F6"):
                    return
            kind = SLIDES[self.page(p)].kind
            if kind == "gallery":
                if p.review_slide is not None:
                    return
                if key == "v" and self.focus and self.focus != p.id:
                    self.votes[p.id] = self.focus
                    p.message = "관객상 투표 완료"
                return
            if kind in ("cover", "end"):
                return
            if kind == "draw":
                if self.round_phase == "running" and self.remaining() <= 0:
                    return
                if self.round_phase in ("judging", "done", "error"):
                    return
                if not p.host and (
                    self.round_phase == "running" and p.id not in self.roster
                ):
                    return
            raw = {
                "Escape": "\x1b",
                "Enter": "\r",
                "Backspace": "\x7f",
                "ControlV": "\x16",
                "ControlL": "\x0c",
                "Tab": "\t",
            }.get(key, key)
            if key in ("Up", "Down", "Left", "Right"):
                if not p.current or (p.current.snapshot and p.current.snapshot["mode"] not in ("n", "v", "V", "\x16")):
                    return
                raw = {"Up": "k", "Down": "j", "Left": "h", "Right": "l"}[key]
            if p.current:
                p.message = ""
                requested = await p.current.key(raw)
                if requested:
                    if any(
                        other.name == requested and other.id != p.id
                        for other in self.players.values()
                    ):
                        p.current.feedback = "다른 참가자가 사용 중인 이름입니다."
                    else:
                        p.name = requested
                        p.named = True
                        p.current.complete = True
                        p.current.feedback = f"{requested} · 이름 저장됨"

    def remaining(self):
        return (
            max(0, self.args.duration - (time.monotonic() - self.started))
            if self.started
            else self.args.duration
        )

    async def start_round(self):
        if self.kind != "draw":
            self.presenter.message = "그림 슬라이드에서 시작하세요."
            return
        if self.round_phase != "waiting":
            self.presenter.message = "이미 시작한 라운드입니다."
            return
        if self.judge is None:
            self.presenter.message = "AI 준비 중: " + (self.judge_error or "모델 로딩")
            return
        self.roster = [p.id for p in self.players.values() if p.connected]
        if not self.roster:
            self.presenter.message = "참가자가 접속해야 시작할 수 있어요."
            return
        for pid in self.roster:
            person = self.players[pid]
            review = person.review_slide
            if review is not None:
                await person.activate("draw")
            await person.current.prepare()
            if review is not None:
                await person.activate(SLIDES[review].kind)
        self.live = {pid: None for pid in self.roster}
        self.frozen = None
        self.final = {}
        self.final_art = {}
        self.revealed = []
        self.votes = {}
        self.started = time.monotonic()
        self.round_phase = "running"
        self.presenter.message = "모두 동시에 시작!"

    def standings(self):
        values = dict(self.frozen if self.frozen is not None else self.live)
        for pid in self.revealed:
            values[pid] = self.final[pid]
        if self.reveal_phase == "score":
            return [(pid, values[pid]) for pid in self.held_order]
        return sorted(
            values.items(),
            key=lambda row: (-(row[1] if row[1] is not None else -1e9), row[0]),
        )

    def begin_reveal(self):
        if self.kind != "gallery" or self.round_phase != "done":
            self.presenter.message = "마감·채점 후 갤러리에서 공개하세요."
            return
        if self.reveal_phase != "idle":
            return
        pending = [
            pid for pid, _ in reversed(self.standings()) if pid not in self.revealed
        ]
        if not pending:
            return
        self.focus = pending[0]
        self.held_order = [pid for pid, _ in self.standings()]
        self.reveal_phase = "focus"
        self.tasks.append(asyncio.create_task(self._reveal()))

    async def _reveal(self):
        await asyncio.sleep(0.45)
        self.revealed.append(self.focus)
        self.reveal_phase = "score"
        await asyncio.sleep(0.7)
        self.reveal_phase = "moving"
        await asyncio.sleep(0.7)
        self.reveal_phase = "idle"

    async def load_judge(self):
        try:
            from .scoring import Judge

            self.judge = await asyncio.to_thread(Judge, self.args.font)
            log.info("AI ready (%s)", self.judge.device)
        except Exception as exc:
            self.judge_error = str(exc)
            log.exception("AI initialization failed")

    async def evaluate(self, final=False):
        try:
            async with self.lock:
                snaps = []
                for pid in self.roster:
                    p = self.players[pid]
                    if p.current and p.current.kind == "draw":
                        p.current.snapshot = await p.editor.snapshot()
                    snaps.append(copy.deepcopy(p.games["draw"].snapshot))
            scores = await asyncio.to_thread(self.judge.score, snaps, self.args.keyword)
            if final:
                self.final = dict(zip(self.roster, scores))
                self.final_art = dict(zip(self.roster, snaps))
                out = Path(self.args.data) / time.strftime("round-%Y%m%d-%H%M%S")
                out.mkdir(parents=True, exist_ok=True)
                for pid, snapshot in self.final_art.items():
                    (out / (pid + ".json")).write_text(
                        json.dumps(snapshot, ensure_ascii=False)
                    )
                    await asyncio.to_thread(
                        self.judge.render(snapshot).save, out / (pid + ".png")
                    )
                (out / "results.json").write_text(
                    json.dumps(
                        [
                            {
                                "name": self.players[pid].name,
                                "score": score,
                                "file": pid + ".png",
                            }
                            for pid, score in self.final.items()
                        ],
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                self.round_phase = "done"
            else:
                self.live = dict(zip(self.roster, scores))
        except Exception as exc:
            self.judge_error = str(exc)
            log.exception("Scoring failed")
            if final:
                self.round_phase = "error"
        finally:
            self.judge_busy = False

    async def physics_loop(self):
        prev = time.monotonic()
        while True:
            await asyncio.sleep(1 / 120)
            now = time.monotonic()
            dt = now - prev
            prev = now
            for p in (self.presenter, *self.players.values()):
                if p.current and p.current.arena:
                    p.current.arena.step(dt)

    async def editor_loop(self):
        prev = time.monotonic()
        while True:
            await asyncio.sleep(0.08)
            now = time.monotonic()
            dt = now - prev
            prev = now
            async with self.lock:
                games = [
                    p.current
                    for p in (self.presenter, *self.players.values())
                    if p.current and not p.current.arena
                ]
                if games:
                    await asyncio.gather(*(g.update(dt) for g in games))

    async def round_loop(self):
        next_score = 0
        while True:
            await asyncio.sleep(0.05)
            now = time.monotonic()
            if self.round_phase == "running":
                if self.remaining() <= self.args.freeze and self.frozen is None:
                    self.frozen = dict(self.live)
                if self.remaining() <= 0:
                    self.round_phase = "judging"
                elif now >= next_score and not self.judge_busy:
                    self.judge_busy = True
                    next_score = now + 5
                    self.tasks.append(asyncio.create_task(self.evaluate()))
            if self.round_phase == "judging" and not self.judge_busy:
                self.judge_busy = True
                self.tasks.append(asyncio.create_task(self.evaluate(final=True)))

    def run(self, load_model=True):
        self.tasks.extend(
            asyncio.create_task(fn())
            for fn in [self.physics_loop, self.editor_loop, self.round_loop]
        )
        if load_model:
            self.tasks.append(asyncio.create_task(self.load_judge()))

    async def close(self):
        self.closed = True
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        await asyncio.gather(
            *(p.editor.close() for p in [self.presenter, *self.players.values()] if p)
        )
