"""Build a review board from actual app frames, without touching the live room."""

import asyncio
import base64
import html
import json
import time
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw, ImageFont
from render_preview import save

from be_vim.render import make_frame
from be_vim.room import Room
from be_vim.slides import DRAWING_PROMPT, RICE, SLIDES

OUT = Path("previews/slide-comparison")
DEMO = {
    "name": "iDEMO\x1b\r",
    "paddle": "l",
    "jumps": "3j",
    "words": "2w",
    "search": "f*",
    "visual": "v2l",
    "clone": "v2ly8lv2lp",
    "change": "dw",
}
PRACTICE = {
    "name": "iALICE\x1b\r",
    "paddle": "hh",
    "jumps": "j",
    "words": "w",
    "search": "f",
    "visual": "v",
    "clone": "v2ly",
    "change": "d",
}


async def keys(room, person, sequence):
    for c in sequence:
        await room.handle(
            person, {"\x1b": "Escape", "\r": "Enter", "\x16": "ControlV"}.get(c, c)
        )


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    room = Room(SimpleNamespace(duration=120, freeze=30, keyword=DRAWING_PROMPT))
    await room.setup()
    cards = []
    try:
        room.shader_paused = True
        room.shader_elapsed = 6
        alice = await room.add_player()
        bob = await room.add_player()
        bob.name = "BOB"
        recorded = max(Path("previews/full-flow/rounds").glob("*/results.json"))
        results = json.loads(recorded.read_text())
        snapshots = [
            json.loads(
                (recorded.parent / Path(r["file"]).with_suffix(".json")).read_text()
            )
            for r in results
        ]
        for i, slide in enumerate(SLIDES):
            await room.goto(i - room.slide)
            shared = slide.kind in ("cover", "gallery", "end")
            if slide.kind in DEMO:
                await keys(room, room.presenter, DEMO[slide.kind])
                if slide.kind == "paddle":
                    room.presenter.current.arena.step(0.2)
            if slide.kind == "draw":
                await room.presenter.editor.activate("draw", RICE, reset=True)
                await room.presenter.current.update(0)
            if slide.kind == "gallery":
                room.round_phase = "done"
                room.roster = [alice.id, bob.id]
                room.final = dict(zip(room.roster, [r["score"] for r in results]))
                room.live = dict(room.final)
                room.frozen = dict(room.final)
                room.final_art = dict(zip(room.roster, snapshots))
                room.revealed = list(room.roster)
                room.focus = alice.id
                room.votes = {alice.id: bob.id, bob.id: alice.id}
            left = OUT / f"{i + 1:02}-demo.png"
            right = OUT / f"{i + 1:02}-practice.png"
            save(make_frame(room, room.presenter, 140, 44), left)
            if not shared:
                if slide.kind == "draw":
                    # A preview of ALICE's own canvas; scores/art are from the saved neural run.
                    await alice.editor.activate(
                        "draw", snapshots[0]["lines"], reset=True
                    )
                    await alice.current.update(0)
                    room.roster = [alice.id, bob.id]
                    room.live = dict(zip(room.roster, [r["score"] for r in results]))
                    room.round_phase = "running"
                    room.started = time.monotonic() - 45
                else:
                    await keys(room, alice, PRACTICE[slide.kind])
                    if slide.kind == "paddle":
                        alice.current.arena.step(0.12)
            save(make_frame(room, alice, 140, 44), right)
            if slide.kind == "draw":
                room.round_phase = "done"
            label_left = "공통 화면" if shared else "발표자 개인 화면"
            label_right = "공통 화면 · 동일" if shared else "실습 · 참가자 개인 화면"
            cards.append(
                {
                    "number": i + 1,
                    "title": slide.title,
                    "left": left,
                    "right": right,
                    "shared": shared,
                    "label_left": label_left,
                    "label_right": label_right,
                }
            )
    finally:
        await room.close()
    font = ImageFont.truetype("/System/Library/Fonts/AppleSDGothicNeo.ttc", 25)
    small = ImageFont.truetype("/System/Library/Fonts/AppleSDGothicNeo.ttc", 18)
    # 12 slide pairs: two pairs per row, six rows. Full resolution is available in HTML.
    width = 1600
    thumbw = 376
    thumbh = 236
    rowh = 320
    sheet = Image.new("RGB", (width, 90 + 6 * rowh + 25), "#101210")
    d = ImageDraw.Draw(sheet)
    d.text((24, 15), "Be Vim / 전체 슬라이드 비교 · 140 × 44", font=font, fill="#e8e3d9")
    d.text(
        (24, 49),
        "각 카드 왼쪽: 발표자   /   오른쪽: 개인 실습   ·   01·11·12는 공통 화면",
        font=small,
        fill="#abb2a6",
    )
    for n, c in enumerate(cards):
        x = 24 + (n % 2) * 788
        y = 95 + (n // 2) * rowh
        d.text(
            (x, y),
            f"{c['number']:02}  {c['title']}" + ("  [공통]" if c["shared"] else ""),
            font=small,
            fill="#e8e3d9",
        )
        for offset, key in [(0, "left"), (388, "right")]:
            thumb = Image.open(c[key]).resize(
                (thumbw, thumbh), Image.Resampling.LANCZOS
            )
            sheet.paste(thumb, (x + offset, y + 40))
            d.text(
                (x + offset, y + 285),
                "공통" if c["shared"] else ("발표자" if key == "left" else "실습"),
                font=small,
                fill="#78aba5",
            )
    sheet.save(OUT / "overview.png")

    def embed(path):
        return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()

    sections = []
    for c in cards:
        panels = "".join(
            f'<figure><figcaption>{c[label]}</figcaption><button class="shot" aria-label="{c[label]} 확대"><img src="{embed(c[path])}" alt="{html.escape(c["title"])} — {c[label]}"></button></figure>'
            for path, label in [("left", "label_left"), ("right", "label_right")]
        )
        sections.append(
            f'<section id="slide-{c["number"]}"><h2><span>{c["number"]:02}</span> {html.escape(c["title"])}</h2><div class="pair">{panels}</div></section>'
        )
    nav = "".join(f'<a href="#slide-{c["number"]}">{c["number"]:02}</a>' for c in cards)
    page = (
        """<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Be Vim — 발표자 / 실습 비교</title>
<style>*{box-sizing:border-box}body{margin:0;background:#101210;color:#e8e3d9;font:15px/1.6 system-ui,sans-serif}main{max-width:1600px;margin:auto;padding:40px 24px}h1{font-size:30px;font-weight:550}p{color:#abb2a6;max-width:850px}nav{position:sticky;top:0;background:#101210ed;display:flex;gap:8px;padding:12px 0;z-index:2;flex-wrap:wrap}a{color:#aed0bd;text-decoration:none;padding:4px 10px;border:1px solid #3d453b;border-radius:4px}section{margin:36px 0 64px;scroll-margin-top:75px}h2{font-weight:500;font-size:21px}h2 span{color:#78aba5;margin-right:12px}.pair{display:grid;grid-template-columns:1fr 1fr;gap:20px}figure{margin:0}figcaption{color:#abb2a6;margin-bottom:10px}.shot{display:block;padding:0;background:#000;border:1px solid #333b32;width:100%;cursor:zoom-in}img{display:block;width:100%;height:auto}dialog{max-width:98vw;max-height:96vh;width:1260px;padding:12px;background:#101210;color:#eee;border:1px solid #687562}dialog::backdrop{background:#000d}dialog button{padding:8px 16px;float:right;cursor:pointer}dialog img{clear:both;min-width:900px}dialog .scroll{overflow:auto;max-height:85vh}button:focus-visible,a:focus-visible{outline:2px solid #78aba5;outline-offset:4px}@media(max-width:700px){.pair{grid-template-columns:1fr}main{padding:20px 12px}h1{font-size:24px}}</style>
<main><h1>너도 이제, Be Vim</h1><p>140 × 44 터미널, 동일한 유영 시점에서 비교합니다. 왼쪽은 발표자의 게임 화면, 오른쪽은 내 게임을 조작하는 화면입니다. 그림을 누르면 원본 크기로 확대됩니다.</p><p>표지·작품 공개·마무리는 공동 화면이며 별도 실습 모드가 없습니다. 화면은 실제 앱 렌더러로 구성한 대표 진행 상태입니다. 그림·점수는 저장된 AI 검증 기록을 사용했습니다. 실행 중인 서버에는 영향을 주지 않습니다.</p><nav>"""
        + nav
        + "</nav>"
        + "".join(sections)
        + """</main><dialog><button id="close">닫기 · Esc</button><div class="scroll"><img id="zoom" alt="확대 화면"></div></dialog><script>const dialog=document.querySelector('dialog');document.querySelectorAll('.shot').forEach(b=>b.addEventListener('click',()=>{const i=b.querySelector('img');document.querySelector('#zoom').src=i.src;document.querySelector('#zoom').alt=i.alt;dialog.showModal()}));document.querySelector('#close').onclick=()=>dialog.close();dialog.onclick=e=>{if(e.target===dialog)dialog.close()};</script></html>"""
    )
    (OUT / "index.html").write_text(page)
    print("Created 24 full-resolution frames, overview.png and standalone index.html")


if __name__ == "__main__":
    asyncio.run(main())
