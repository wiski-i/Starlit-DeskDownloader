"""Chrome Native Messaging entry point with binary standard input and output."""

import msvcrt
import os
import subprocess
import sys
import time
from pathlib import Path

from PySide6.QtCore import QCoreApplication

from browser_bridge import (
    HEADER, connect_to_desktop, decode_message, desktop_response, encode_message, message_size, request_url,
)


def send_to_desktop(url: str) -> dict:
    socket = connect_to_desktop()
    if socket is None:
        if getattr(sys, "frozen", False):
            command = [str(Path(sys.executable).with_name("HizliIndir.exe"))]
        else:
            command = [sys.executable, str(Path(__file__).with_name("app.py"))]
        subprocess.Popen(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.DETACHED_PROCESS, env={**os.environ, "PYINSTALLER_RESET_ENVIRONMENT": "1"},
        )
        deadline = time.monotonic() + 8
        while socket is None and time.monotonic() < deadline:
            time.sleep(0.10)
            socket = connect_to_desktop()
    if socket is None:
        return {"status": "desktop_unavailable"}
    try:
        return desktop_response(socket, url)
    finally:
        socket.abort()


def main() -> None:
    application = QCoreApplication([sys.argv[0]])
    msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
    msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    try:
        size = message_size(sys.stdin.buffer.read(HEADER.size))
        data = sys.stdin.buffer.read(size)
        if len(data) != size:
            raise ValueError("Incomplete request")
        url = request_url(decode_message(data))
    except ValueError:
        url = None
    try:
        reply = send_to_desktop(url) if url is not None else {"status": "invalid_url"}
    except (OSError, ValueError):
        reply = {"status": "desktop_unavailable"}
    sys.stdout.buffer.write(encode_message(reply))
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
