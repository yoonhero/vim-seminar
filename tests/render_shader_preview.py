"""Interactive, selectable DOM text. Compact character/style streams, no images."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from be_vim.render import make_frame
from be_vim.room import Room
from be_vim.slides import DRAWING_PROMPT


async def main():
    out = Path("previews/keynote-ssh")
    out.mkdir(parents=True, exist_ok=True)
    room = Room(SimpleNamespace(duration=120, freeze=30, keyword=DRAWING_PROMPT))
    await room.setup()
    try:
        person = await room.add_player()
        room.shader_paused = True
        styles = []
        lookup = {}
        frames = []
        for mode in range(3):
            room.shader_effect = mode
            sequence = []
            for tick in range(240):
                room.shader_elapsed = tick / 12
                f = make_frame(room, person, 140, 44)
                texts = []
                colors = []
                for row in f.rows:
                    chars = []
                    codes = []
                    for c in row:
                        if not c.ch:
                            continue
                        pair = (c.fg, c.bg)
                        if pair not in lookup:
                            lookup[pair] = len(styles)
                            styles.append(pair)
                        chars.append(c.ch)
                        codes.append(chr(65 + lookup[pair]))
                    texts.append("".join(chars))
                    colors.append("".join(codes))
                sequence.append([texts, colors])
            frames.append(sequence)
        data = json.dumps(
            {"styles": styles, "frames": frames}, ensure_ascii=False
        ).replace("</", "<\\/")
        page = (
            """<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Be Vim · 문자 셰이더</title><style>body{margin:0;background:#10100f;color:#eadfc1;font:14px system-ui}main{max-width:1800px;margin:18px auto;padding:0 16px}nav{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:14px}button{background:#24211c;border:1px solid #655b4c;color:#eadfc1;padding:9px 14px;cursor:pointer}button[aria-pressed=true]{border-color:#ee8b45;color:#ee8b45}p,small{color:#bcb09a}pre{margin:0;background:#000;font:clamp(4px,1.05vw,15px)/1.2 Menlo,Consolas,monospace;white-space:pre;user-select:text;overflow:auto}small{margin-left:auto}</style><main><nav><button data-mode="0">유영</button><button data-mode="1">물결</button><button data-mode="2">잔상</button><button id="pause">정지</button><small>140 × 44 문자 · 20초 렌더 미리보기</small></nav><pre id="slide" aria-label="발표 슬라이드"></pre><p>SSH 렌더러가 만든 제목과 물살을 실제 문자로 표시합니다. 자유로운 선회가 20초 동안 재생됩니다. 이미지나 캔버스 요소를 표시하지 않습니다. SSH: F3 효과 · F4 정지/재생 · Ctrl-G 진행.</p></main><script>const data="""
            + data
            + """;let mode=0,tick=0,paused=false;const slide=document.querySelector('#slide');const esc=s=>s.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');function draw(){const [texts,colors]=data.frames[mode][tick];slide.innerHTML=texts.map((row,y)=>{let out='',run='',style=-1;const chars=[...row];const flush=()=>{if(run){const [fg,bg]=data.styles[style];out+=`<span style="color:${fg};background:${bg}">${esc(run)}</span>`;run=''}};chars.forEach((c,x)=>{const next=colors[y].charCodeAt(x)-65;if(next!==style){flush();style=next}run+=c});flush();return out}).join('\\n');document.querySelectorAll('[data-mode]').forEach(b=>b.setAttribute('aria-pressed',+b.dataset.mode===mode))}document.querySelectorAll('[data-mode]').forEach(b=>b.onclick=()=>{mode=+b.dataset.mode;draw()});document.querySelector('#pause').onclick=()=>{if(paused&&tick===239){tick=0;draw()}paused=!paused;document.querySelector('#pause').textContent=paused?'재생':'정지'};setInterval(()=>{if(!paused){if(tick<239){tick++;draw()}else{paused=true;document.querySelector('#pause').textContent='다시 재생'}}},1000/12);draw();</script></html>"""
        )
        (out / "index.html").write_text(page)
        print("Generated 140x44 selectable-text preview; swimming on open")
    finally:
        await room.close()


if __name__ == "__main__":
    asyncio.run(main())
