"""Responsive presentation views composed from measured terminal regions."""

import math
from collections import Counter

from wcwidth import wcswidth

from .art import (
    clock_art,
    frame_border,
    paper_mount,
)
from .chapter import chapter
from .editor import COLORS, H, W
from .glyph_shader import NAMES as SHADERS
from .glyph_shader import paint as paint_glyphs
from .layout import Rect, fit, measure, viewport, wrap
from .slides import SLIDES, SUBTITLE, TITLE
from .specimen import board as specimen_board
from .terminal import BLACK, CYAN, DIM, GRAY, WHITE, YELLOW, Frame
from .typography import heading
from .typography import lines as heading_lines


def text(f, box, value, color=WHITE, center=False):
    for dy, line in enumerate(wrap(value, box.w, box.h)):
        x = box.x + max(0, (box.w - wcswidth(line)) // 2) if center else box.x
        f.text(box.y + dy, x, line, color)


def status(room):
    if (
        room.final
        and len(room.revealed) == len(room.roster)
        and room.reveal_phase == "idle"
    ):
        return "FINAL"
    if room.kind == "gallery":
        return "REVEAL"
    if room.frozen is not None:
        return "FROZEN"
    return "LIVE"


def draw_scene(f, scene, area, focus=None, paper=False, kind=None, shader=(0, 0)):
    lesson = kind in {"name", "jumps", "words", "search", "visual", "clone", "change"}
    if lesson:
        return specimen_board(f, area, scene, focus, kind)
    box, (ox, oy) = viewport(area, W, H, focus or scene.get("cursor"))
    if not paper:
        paint_glyphs(f, area, *shader, protect=box, dim=True)
    if paper:
        paper_mount(f, area, box, kind)
    selected = set(scene.get("selected", []))
    target = set(scene.get("target", []))
    cursor = scene.get("cursor")
    for yy in range(box.h):
        row = yy + oy
        for xx in range(box.w):
            col = xx + ox
            ch = scene["lines"][row][col]
            bg = "#121210" if paper else BLACK
            fg = COLORS[scene["colors"][row][col]] if scene.get("colors") else WHITE
            if paper and ch == "█":
                bg = fg
            elif paper and not ch.strip() and kind == "draw":
                ch, fg = "·", "#52534d"
            if (row, col) in target:
                fg = CYAN
                bg = "#102020"
            if (row, col) in selected:
                bg = "#225555"
                fg = WHITE
            if paper and (row, col) in selected and ch == "█":
                ch = "▪"
                fg = COLORS[scene["colors"][row][col]]
            if cursor is not None and (row, col) == tuple(cursor):
                if kind == "draw" and ch in ("█", "·", " "):
                    ch = "+"
                bg = CYAN
                fg = BLACK
            if ch != " " or bg != BLACK:
                f.text(box.y + yy, box.x + xx, ch, fg, bg)
    return box.w < W or box.h < H


def cover(f, area, shader):
    # Reserve the diagonal opening below the cover lettering.
    inset = area.w // 30
    x = area.x + inset
    width = area.w - inset * 2
    size = 9 if area.h >= 36 else 7 if area.h >= 20 else 5 if area.h >= 16 else 1
    art = heading_lines("Be Vim", width, size)
    title_y = area.y + (3 if area.h >= 20 else 2)
    water_y = title_y + len(art) + (2 if area.h >= 20 else 1)
    caption_y = area.y + area.h - 2
    water_x = area.x + (round(area.w * .197) if area.w >= 72 else 0)
    water_right = area.x + area.w - (2 if area.w >= 72 else 0)
    paint_glyphs(f, Rect(water_x, water_y, water_right - water_x,
                        max(0, caption_y - water_y)), *shader)
    text(f, Rect(x, area.y, width, 1), "너도 이제,", GRAY)
    heading(f, Rect(x, title_y, width, len(art)), "Be Vim")
    text(f, Rect(x, caption_y, width, 2), SUBTITLE, GRAY)


def draw_arena(f, arena, area, shader):
    # Scale the continuous world, keeping its aspect ratio and collision geometry.
    scale = min(max(1, area.w - 2) / W, max(1, area.h - 2) / H)
    w = max(1, int(W * scale))
    h = max(1, int(H * scale))
    box = Rect(area.x + (area.w - w) // 2, area.y + (area.h - h) // 2, w, h)
    paint_glyphs(f, area, *shader, protect=box, dim=True)
    frame_border(f, box)
    for y, line in enumerate(arena.picture(w, h)):
        for x, ch in enumerate(line):
            if ch != " ":
                f.text(
                    box.y + y,
                    box.x + x,
                    ch,
                    WHITE
                    if 0x2800 <= ord(ch) <= 0x28FF
                    else (
                        "#fa8458" if ch == "*" else "#edb978"
                        if ch == "█" and y % 3 == 0
                        else "#d795a2"
                        if ch == "█"
                        else CYAN
                    ),
                )


def draw_board(f, room, viewer, box, mode):
    label = status(room)
    if mode == "side" and box.h >= 18:
        if room.kind == "draw":
            clock_art(
                f,
                math.ceil(room.remaining()),
                box,
                YELLOW if label == "FROZEN" else WHITE,
            )
        else:
            text(
                f,
                Rect(box.x, box.y + 1, box.w, 1),
                f"{len(room.revealed):02} / {len(room.roster):02}",
                WHITE,
                True,
            )
        text(f, Rect(box.x, box.y + 4, box.w, 1), "-" * box.w, DIM)
        box = Rect(box.x, box.y + 6, box.w, box.h - 6)
    rows = room.standings()
    mine = next(
        ((i + 1, pid, s) for i, (pid, s) in enumerate(rows) if pid == viewer.id), None
    )
    if mode == "stack" and box.h <= 2:
        lead = (
            "아직 점수 없음"
            if not rows
            else "1 " + room.players[rows[0][0]].name + " " + score_text(rows[0][1])
        )
        text(
            f,
            Rect(box.x, box.y, box.w, 1),
            label + " | " + lead,
            YELLOW if label == "FROZEN" else GRAY,
        )
        detail = f"나 {mine[0]}위  {score_text(mine[2])}" if mine else f"{len(rows)}명"
        text(
            f,
            Rect(box.x, box.y + 1, box.w, 1),
            detail + (" | 최종 점수 비공개" if label == "FROZEN" else " | AI 유사도"),
            CYAN,
        )
        return
    text(
        f,
        Rect(box.x, box.y, box.w, 1),
        "순위  /  "
        + {
            "LIVE": "대기" if room.round_phase == "waiting" else "진행 중",
            "FROZEN": "점수 동결",
            "REVEAL": "공개 중",
            "FINAL": "최종",
        }[label],
        YELLOW if label == "FROZEN" else GRAY,
    )
    if not rows and box.h > 2:
        text(f, Rect(box.x, box.y + 2, box.w, 1), "첫 그림을 기다리는 중", GRAY)
    count = max(0, box.h - 2)
    indices = list(range(min(count, len(rows))))
    if mine and mine[0] - 1 not in indices and indices:
        indices[-1] = mine[0] - 1
    for offset, index in enumerate(indices):
        pid, score = rows[index]
        rank = "?" if room.kind == "gallery" and label != "FINAL" else str(index + 1)
        marker = (
            " ?"
            if label == "FROZEN"
            or (room.kind == "gallery" and pid not in room.revealed)
            else ""
        )
        value = score_text(score) + marker
        name_width = max(1, box.w - 4 - wcswidth(value))
        name = fit(room.players[pid].name, name_width)
        name += " " * max(0, name_width - wcswidth(name))
        text(
            f,
            Rect(box.x, box.y + 1 + offset, box.w, 1),
            f"{rank:>2} {name} {value}",
            CYAN if pid == viewer.id or pid == room.focus else GRAY,
        )
    if box.h > 3:
        text(
            f,
            Rect(box.x, box.y + box.h - 1, box.w, 1),
            "마감 후 점수 공개" if label == "FROZEN" else "유사도 점수",
            DIM,
        )


def score_text(value):
    return "--" if value is None else f"{value:.1f}"


def splash(f, room, area, kind):
    if kind == "cover":
        cover(f, area, (room.shader_time(), room.shader_effect))
        return
    size = 7 if area.h >= 24 and area.w >= 70 else 5 if area.h >= 14 else 1
    paint_glyphs(
        f,
        area,
        room.shader_time(),
        room.shader_effect,
        protect=Rect(area.x, area.y, min(area.w, 70), min(area.h, size + 9)),
        dim=True,
    )
    text(f, Rect(area.x, area.y, area.w, 1), TITLE, GRAY)
    heading(f, Rect(area.x, area.y + 2, area.w, size), "Done")
    lines = [(":q", GRAY)]
    if room.final:
        pid = max(room.final, key=room.final.get)
        lines.append(("AI 우승: " + room.players[pid].name, CYAN))
    if room.votes:
        votes = Counter(room.votes.values())
        top = max(votes.values())
        names = sorted(
            room.players[pid].name for pid, count in votes.items() if count == top
        )
        label = "관객상 (공동): " if len(names) > 1 else "관객상: "
        lines.extend(
            (line, CYAN)
            for line in wrap(
                label + ", ".join(names), area.w, max(1, area.h - size - 4)
            )
        )
    if room.final and area.w >= 76 and area.h >= 18:
        winner = max(room.final, key=room.final.get)
        artwork = room.final_art.get(winner)
        if artwork:
            exhibit = Rect(area.x + area.w - 42, area.y, 42, 18)
            draw_scene(f, {**artwork, "cursor": None, "selected": [], "target": []},
                       exhibit, paper=True, kind="gallery")
    for y, (line, color) in enumerate(lines):
        text(f, Rect(area.x, area.y + size + 3 + y, area.w, 1), line, color)


def make_frame(room, viewer, width, height):
    width = max(1, min(500, width))
    height = max(1, min(200, height))
    f = Frame(width, height)
    if width < 24 or height < 12:
        text(
            f,
            Rect(0, 0, width, min(height, 2)),
            "창을 24열 × 12행 이상으로 넓혀주세요.",
            GRAY,
        )
        return f
    page = room.page(viewer)
    kind = SLIDES[page].kind
    board = kind in ("draw", "gallery")
    l = measure(width, height, board, kind)
    slide = SLIDES[page]
    counter = f"{page + 1:02}/{len(SLIDES):02}"
    f.text(l.header.y, l.header.x + l.header.w - len(counter), counter, DIM)
    if kind not in ("cover", "end"):
        game = viewer.current if kind != "gallery" else None
        chapter(f, l.title, kind, game)
    if not viewer.host and room.slide > 0 and not viewer.control_menu:
        nav = (f"복습 · 발표 {room.slide + 1}장 · Ctrl-G l 합류"
               if viewer.review_slide is not None else "Ctrl-G p 이전 장 복습")
        text(f, l.controls, nav, GRAY)
    if viewer.control_menu:
        text(
            f,
            l.controls,
            f"n 다음 / p 이전 / e {SHADERS[room.shader_effect]} / a 정지 / s 시작 / r 공개" if viewer.host else "p 이전 장 / n 다음 장 / l 발표 합류",
            GRAY,
        )
    if kind in ("cover", "end"):
        splash(
            f,
            room,
            Rect(l.title.x, l.title.y, l.title.w, height - l.title.y - 2)
            if kind == "cover"
            else l.stage,
            kind,
        )
        return f
    feedback = ""
    state = ""
    goal = slide.hint
    if kind == "gallery":
        goal = "벽화 공개 · v 관객상 투표"
        if room.focus:
            snapshot = room.final_art[room.focus]
            draw_scene(
                f,
                {**snapshot, "cursor": None, "selected": []},
                l.stage,
                paper=True,
                kind="gallery",
                shader=(room.shader_time(), room.shader_effect),
            )
            goal = "@" + room.players[room.focus].name
            if room.focus in room.revealed:
                state = "점수 " + score_text(room.final[room.focus])
        else:
            text(f, l.stage, "발표자가 F6으로 첫 작품을 공개합니다.", GRAY, True)
        feedback = f"공개 {len(room.revealed)}/{len(room.roster)}"
    else:
        game = viewer.current
        if game and (game.snapshot or game.arena):
            goal = game.goal
            if game.arena:
                draw_arena(
                    f, game.arena, l.stage, (room.shader_time(), room.shader_effect)
                )
                state = game.progress
                if game.arena.serve_delay > 0:
                    feedback = "다음 공 준비"
                elif not game.arena.started:
                    feedback = "Space 또는 이동 키로 공 출발"
            else:
                scene = game.scene()
                focus = scene.get("cursor") or game.snapshot["cursor"]
                panned = draw_scene(
                    f,
                    scene,
                    l.stage,
                    focus,
                    paper=kind == "draw",
                    kind=kind,
                    shader=(room.shader_time(), room.shader_effect),
                )
                mode = {
                    "n": "NORMAL",
                    "i": "INSERT",
                    "R": "REPLACE",
                    "v": "VISUAL",
                    "V": "VISUAL LINE",
                    "\x16": "VISUAL BLOCK",
                    "c": "SEARCH",
                }.get(scene["mode"], scene["mode"])
                state = " · ".join(v for v in (mode, game.progress) if v)
                if panned:
                    state += " · 커서 따라보기"
                feedback = (
                    scene.get("command")
                    or game.feedback
                    or (
                        "입력  " + game.keys
                        if game.keys and kind != "draw"
                        else ""
                    )
                )
            if kind == "draw":
                goal = f"{room.args.keyword} · {math.ceil(room.remaining())}초 · " + {
                    "waiting": "시작 대기",
                    "running": "그리는 중",
                    "judging": "채점 중",
                    "done": "제출 완료",
                    "error": "채점 오류",
                }.get(room.round_phase, room.round_phase)
                state = f"{len(scene['selected'])}칸 선택" if scene['selected'] else "한 칸"
                ink = game.editor.ink
                palette = l.status
                for index, color in enumerate(COLORS):
                    if index * 4 + 3 <= palette.w:
                        f.text(palette.y, palette.x + index * 4,
                               ("[" if index == ink else " ") + str(index+1) +
                               ("]" if index == ink else " "), BLACK, color)
                if palette.w >= 36:
                    f.text(palette.y, palette.x + 25, state, CYAN)
                feedback = ("색 번호 1–6 · Esc 취소" if game.palette_open else
                            "p 색 선택 · Space 칠하기 · v 사각 선택")
    text(f, l.goal, goal, WHITE)
    if kind in ("jumps", "words", "search", "visual", "clone", "change"):
        cleared = sum(g.cleared for g in viewer.games.values())
        state += f" · 누적 돌파 {cleared}"
    if kind != "draw":
        text(f, l.status, state, CYAN)
    text(f, l.feedback, viewer.message or feedback, YELLOW if viewer.message else GRAY)
    if l.hint and slide.hint != goal:
        hint = (
            "hjkl/방향키 이동 · x 지우기 · u 되돌리기 · r 문자"
            if kind == "draw"
            else slide.hint
        )
        text(f, l.hint, hint, WHITE)
    if l.scoreboard:
        draw_board(f, room, viewer, l.scoreboard, l.board_mode)
    return f
