"""Local server entry point."""

import argparse
import asyncio
import getpass
import logging
import os
from pathlib import Path

import asyncssh

from .room import Room
from .slides import DRAWING_PROMPT
from .transport import Server, session


async def serve(args):
    data = Path(args.data)
    data.mkdir(parents=True, exist_ok=True)
    key = data / "host_key"
    if not key.exists():
        asyncssh.generate_private_key("ssh-ed25519").write_private_key(key)
        key.chmod(0o600)
    room = Room(args)
    await room.setup()
    room.run()
    try:
        async with await asyncssh.create_server(
            lambda: Server(room),
            args.bind,
            args.port,
            server_host_keys=[str(key)],
            process_factory=lambda p: session(p, room),
            encoding="utf-8",
            line_editor=False,
        ):
            print(f"Be Vim listening on {args.bind}:{args.port}", flush=True)
            await asyncio.Future()
    finally:
        await room.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bind", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=2222)
    ap.add_argument("--duration", type=int, default=120)
    ap.add_argument("--freeze", type=int, default=30)
    ap.add_argument("--keyword", default=DRAWING_PROMPT)
    ap.add_argument("--data", default="var")
    ap.add_argument("--font", default="/System/Library/Fonts/Menlo.ttc")
    args = ap.parse_args()
    if args.duration <= 0 or not 0 <= args.freeze <= args.duration:
        ap.error("0 <= freeze <= duration, duration > 0")
    args.host_password = os.environ.get("BE_VIM_HOST_PASSWORD") or getpass.getpass(
        "발표자 비밀번호: "
    )
    if not args.host_password:
        ap.error("발표자 비밀번호는 비워둘 수 없습니다.")
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(serve(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
