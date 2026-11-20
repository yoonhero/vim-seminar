"""Sans-serif letter proportions expressed entirely with ASCII cells."""

import json
from functools import lru_cache
from pathlib import Path

from .terminal import WHITE

WORDS = {
    "cover": "Be Vim",
    "name": "Insert",
    "paddle": "Move",
    "jumps": "Jump",
    "words": "Words",
    "search": "Find",
    "visual": "Select",
    "clone": "Copy",
    "change": "Change",
    "draw": "Draw",
    "gallery": "Gallery",
    "end": "Done",
}


@lru_cache(maxsize=1)
def alphabet():
    return json.loads(
        (Path(__file__).parent / "assets" / "sans-titles.json").read_text()
    )


def title_asset(word, width, height):
    for size in sorted(alphabet()[word], key=int, reverse=True):
        art = alphabet()[word][size]
        if len(art["lines"]) <= height and max(map(len, art["lines"])) <= width:
            return art
    line = word[:width]
    return {"lines": [line], "coverage": [[255] * len(line)]}


def lines(word, width, height):
    return title_asset(word, width, height)["lines"]


@lru_cache(maxsize=256)
def ink(coverage):
    strength = min(1, .4 + coverage / 255 * .75)
    return "#" + "".join(
        f"{round(int(WHITE[i:i + 2], 16) * strength):02x}" for i in (1, 3, 5)
    )


def heading(frame, area, word):
    art = title_asset(word, area.w, area.h)
    for row, line in enumerate(art["lines"]):
        for col, char in enumerate(line):
            if char != " ":
                frame.text(area.y + row, area.x + col, char, ink(art["coverage"][row][col]))
    return max(map(len, art["lines"])), len(art["lines"])
