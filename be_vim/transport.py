"""SSH transport and established VT100 key parsing; no gameplay in this layer."""

import asyncio
import logging
import secrets

import asyncssh
from prompt_toolkit.input.vt100_parser import Vt100Parser
from prompt_toolkit.keys import Keys

from .render import make_frame
from .terminal import DiffRenderer

log = logging.getLogger(__name__)
KEYS = {
    Keys.ControlC: "ControlC",
    Keys.ControlG: "ControlG",
    Keys.ControlV: "ControlV",
    Keys.ControlL: "ControlL",
    Keys.ControlM: "Enter",
    Keys.ControlJ: "Enter",
    Keys.ControlH: "Backspace",
    Keys.Backspace: "Backspace",
    Keys.ControlI: "Tab",
    Keys.Escape: "Escape",
    Keys.PageDown: "PageDown",
    Keys.PageUp: "PageUp",
    Keys.F3: "F3",
    Keys.F4: "F4",
    Keys.F5: "F5",
    Keys.F6: "F6",
    Keys.Up: "Up",
    Keys.Down: "Down",
    Keys.Left: "Left",
    Keys.Right: "Right",
}


class Server(asyncssh.SSHServer):
    def __init__(self, room):
        self.room = room

    def begin_auth(self, username):
        return username == "presenter"

    def password_auth_supported(self):
        return True

    def validate_password(self, username, password):
        return username == "presenter" and secrets.compare_digest(
            password, self.room.args.host_password
        )


async def session(process, room):
    if process.command:
        process.exit(1)
        return
    person = None
    tasks = []
    try:
        async with room.lock:
            if process.get_extra_info("username") == "presenter":
                person = room.presenter
                person.connected = True
            else:
                person = await room.add_player()
        process.stdout.write("\x1b[?1049h\x1b[?25l")
        queue = asyncio.Queue(maxsize=2048)

        def on_key(k):
            value = KEYS.get(k.key, k.data if not isinstance(k.key, Keys) else None)
            if k.key == Keys.BracketedPaste:
                for c in k.data[:512]:
                    if not queue.full():
                        queue.put_nowait(c)
            elif value is not None and not queue.full():
                queue.put_nowait(value)

        parser = Vt100Parser(on_key)
        flush = None

        async def read():
            nonlocal flush
            while True:
                try:
                    data = await process.stdin.read(128)
                except asyncssh.TerminalSizeChanged:
                    continue
                if not data:
                    queue.put_nowait(None)
                    return
                if flush:
                    flush.cancel()
                parser.feed(data)
                flush = asyncio.get_running_loop().call_later(0.035, parser.flush)

        async def paint():
            renderer = DiffRenderer()
            while True:
                w, h = process.get_terminal_size()[:2]
                if not getattr(room, "transitioning", False):
                    output = renderer.render(make_frame(room, person, w, h))
                    if output:
                        try:
                            process.stdout.write(output)
                        except (asyncssh.Error, ConnectionError):
                            return
                await asyncio.sleep(1 / 30)

        tasks = [asyncio.create_task(read()), asyncio.create_task(paint())]
        while True:
            key = await queue.get()
            if key is None or key == "ControlC":
                break
            await room.handle(person, key)
    except ValueError as exc:
        process.stdout.write(str(exc) + "\r\n")
    except (asyncssh.Error, ConnectionError):
        log.debug("SSH connection closed")
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if person:
            person.connected = False
            if not person.host and person.id not in room.roster:
                async with room.lock:
                    room.players.pop(person.id, None)
                    await person.editor.close()
        try:
            process.stdout.write("\x1b[0m\x1b[?25h\x1b[?1049l")
            process.exit(0)
        except (asyncssh.Error, ConnectionError):
            log.debug("SSH channel closed")
