"""The shared deck. Game progress belongs to each person, never to a slide."""

from dataclasses import dataclass

TITLE = "너도 이제, Be Vim"
SUBTITLE = "Vim에서 아직도 못 빠져나오고 계신가요?"
DRAWING_PROMPT = '우리들의 회장 "박성현"을 그리시오'
RICE = [
    "        (  (  (",
    "         )  )  )",
    "       .-.......-.",
    "      / . : . : . \\",
    "     |~~~~~~~~~~~~~|",
    "      \\           /",
    "       \\_________/",
    "          |___|",
]


@dataclass(frozen=True)
class Slide:
    kind: str
    title: str
    hint: str
    seconds: int


SLIDES = [
    Slide("cover", TITLE, "발표 시작 대기", 30),
    Slide("name", "i  이름 입력", "i → 닉네임 입력 → Esc → Enter", 45),
    Slide("paddle", "h j k l  이동", "h 왼쪽 · j 아래 · k 위 · l 오른쪽", 75),
    Slide("jumps", "숫자 + 이동", "hjkl 또는 방향키 · 숫자 + 방향으로 여러 칸 이동", 45),
    Slide("words", "w b e  단어 이동", "w 다음 시작 · b 이전 시작 · e 단어 끝", 45),
    Slide("search", "f /  찾기", "f* → 다음 균열은 ; · /crack Enter → n", 45),
    Slide(
        "visual",
        "v  선택",
        "v로 단어 선택 · Ctrl-v로 사각 선택 · r# 채우기",
        60,
    ),
    Slide(
        "clone",
        "y p  복사와 붙여넣기",
        "v로 선택 → y → 목적지 선택 → p · u 되돌리기",
        60,
    ),
    Slide(
        "change", "d c .  삭제와 수정", "dw 삭제 · ciw 교체 · . 마지막 변경 반복", 45
    ),
    Slide(
        "draw",
        "벽화 그리기",
        "동시에 그리기 · 마지막 30초 점수판 프리즈",
        120,
    ),
    Slide("gallery", "벽화 공개", "발표자 공개 · v로 현재 작품에 관객상 투표", 135),
    Slide("end", "너도 이제, Be Vim.", "Ctrl-C  나가기", 30),
]
