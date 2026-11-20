"""Stage-specific key sequences for the live demonstration and each student's puzzle."""


from wcwidth import wcswidth

from . import maze
from .layout import fit
from .terminal import WHITE, YELLOW

TITLES = {
    "name": "첫 벽돌에 이름 새기기",
    "paddle": "벽돌 깨기",
    "jumps": "벽을 타고 균열로 이동",
    "words": "벽돌 사이 건너기",
    "search": "숨은 균열 찾기",
    "visual": "철거할 벽돌 고르기",
    "clone": "철거 표시 복사하기",
    "change": "출구 열기",
    "draw": "마지막 벽에 벽화 그리기",
    "gallery": "완성된 벽화",
}

RECIPES = {
    "name": [("i", "닉네임", "Enter")],
    "paddle": [("h", "j", "k", "l"), ("h", "j", "k", "l")],
    "words": [("2w",), ("2e",), ("4b",)],
    "search": [("f", "*"), (";",), ("/crack", "Enter"), ("n",)],
    "visual": [("v", "2l"), ("v", "3l"), ("Ctrl-v", "4l", "2j", "r#")],
    "clone": [
        ("v2l", "y", "8l", "v2l", "p"),
        ("v2l", "y", "6j", "8l", "v2l", "p"),
        ("u",),
    ],
    "change": [("dw",), ("ciw", "open", "Esc", "w.", "w.")],
    "draw": [("p 색상", "v 선택", "Space 칠하기")],
    "gallery": [("v",)],
}


def next_step(kind, game):
    """Guide the demonstrated path; leave alternative native Vim solutions available."""
    if game.awaiting_next:
        return "Enter  다음 문제"
    if game.complete:
        return "저장됨" if kind == "name" else "Space  다시 풀기"
    if kind == "name":
        return "닉네임 입력 → Enter" if game.snapshot["mode"] == "i" else "i  이름 입력"
    if kind == "paddle":
        return "h ←   j ↓   k ↑   l →"
    if (game.stage > 0 and not game.hint_requested) or (game.stage == 0 and game.hint_requested):
        return "?  힌트"
    if kind == "jumps":
        if game.move_count:
            return f"{game.move_count}칸 · 방향 선택"
        return "다음 키  " + maze.hint(game.spec.rows, tuple(game.snapshot["cursor"]), game.spec.expected)
    steps = RECIPES[kind][game.stage]
    typed = game.keys.replace(" Esc ", "Esc").replace(" Ctrl-v ", "Ctrl-v").replace(" Enter ", "Enter")
    if not "".join(steps).startswith(typed):
        return "Ctrl-L  재시작"
    for step in steps:
        if typed.startswith(step):
            typed = typed[len(step):]
        else:
            return "다음 키  " + step[len(typed):]
    return "목표 확인 · Ctrl-L 다시 시작"


def chapter(frame, area, kind, game):
    title = TITLES[kind]
    if game is not None and kind != "draw":
        action = next_step(kind, game)
    else:
        action = "  ".join(RECIPES[kind][0])
    if wcswidth(title) + wcswidth(action) + 3 > area.w:
        frame.text(area.y, area.x, fit(action, area.w), YELLOW)
        return
    frame.text(area.y, area.x, title, WHITE)
    frame.text(area.y, area.x + wcswidth(title) + 3, action, YELLOW)
