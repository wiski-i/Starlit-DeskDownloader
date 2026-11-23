"""Chrome Native Messaging entry point with binary standard input and output."""

import msvcrt
import os
import subprocess
import sys
import time
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QSettings

from browser_bridge import (
    HEADER, BrowserDownload, RequestError, connect_to_desktop, decode_message, desktop_response,
    encode_message, message_size, parse_download_request,
)
from media_profiles import browser_profiles


def send_to_desktop(request: BrowserDownload) -> dict:
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
        reply = desktop_response(socket, request)
        # Older desktop processes reject any field besides action and URL.
        if request.profile is not None and reply.get("status") == "invalid_url":
            return {"status": "upgrade_required"}
        return reply
    finally:
        socket.abort()


def read_message() -> dict:
    size = message_size(sys.stdin.buffer.read(HEADER.size))
    data = sys.stdin.buffer.read(size)
    if len(data) != size:
        raise ValueError("Incomplete request")
    return decode_message(data)


def handle_message(message: dict) -> dict:
    if message == {"action": "get_profiles"}:
        return browser_profiles(QSettings("HizliIndir", "HizliIndir"))
    try:
        request = parse_download_request(message)
    except RequestError as error:
        return {"status": str(error)}
    try:
        return send_to_desktop(request)
    except (OSError, ValueError):
        return {"status": "desktop_unavailable"}


def main() -> None:
    application = QCoreApplication([sys.argv[0]])
    msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
    msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    try:
        message = read_message()
    except ValueError:
        reply = {"status": "invalid_url"}
    else:
        reply = handle_message(message)
    sys.stdout.buffer.write(encode_message(reply))
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
