"""Carry a single browser URL to the running desktop application."""

import ctypes
import hashlib
import json
import os
import struct
import time
from ctypes import wintypes
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from downloads import download_url


HEADER = struct.Struct("<I")
MAX_MESSAGE = 16384


def encode_message(message: dict) -> bytes:
    data = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(data) > MAX_MESSAGE:
        raise ValueError("Message too large")
    return HEADER.pack(len(data)) + data


def message_size(header: bytes) -> int:
    if len(header) != HEADER.size:
        raise ValueError("Incomplete message header")
    size, = HEADER.unpack(header)
    if not 0 < size <= MAX_MESSAGE:
        raise ValueError("Invalid message size")
    return size


def decode_message(data: bytes) -> dict:
    try:
        result = json.loads(data)
    except RecursionError as error:
        raise ValueError("JSON nesting is too deep") from error
    if not isinstance(result, dict):
        raise ValueError("Expected a JSON object")
    return result


def request_url(request: dict) -> str | None:
    url = request.get("url")
    if set(request) != {"action", "url"} or request["action"] != "download" or not isinstance(url, str):
        return None
    try:
        return download_url(url) if len(url.encode("utf-8")) <= 8192 else None
    except UnicodeEncodeError:
        return None


def socket_name() -> str:
    session = wintypes.DWORD()
    if not ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(session)):
        raise OSError("Could not determine the Windows session")
    user = hashlib.sha256(os.path.normcase(str(Path.home())).encode("utf-8")).hexdigest()[:24]
    return f"HizliIndir.Browser.{session.value}.{user}"


class BrowserBridge(QLocalServer):
    def __init__(self, submit, parent=None) -> None:
        super().__init__(parent)
        self._submit = submit
        self.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.newConnection.connect(self._accept)

    def _accept(self) -> None:
        while self.hasPendingConnections():
            socket = self.nextPendingConnection()
            socket.setReadBufferSize(HEADER.size + MAX_MESSAGE)
            timer = QTimer(socket, singleShot=True, interval=2000)
            timer.timeout.connect(socket.abort)
            socket.disconnected.connect(socket.deleteLater)
            socket.readyRead.connect(lambda peer=socket: self._receive(peer))
            timer.start()
            self._receive(socket)

    def _receive(self, socket: QLocalSocket) -> None:
        available = socket.bytesAvailable()
        if available < HEADER.size:
            return
        try:
            size = message_size(bytes(socket.peek(HEADER.size)))
            if available < HEADER.size + size:
                return
            socket.read(HEADER.size)
            url = request_url(decode_message(bytes(socket.read(size))))
        except ValueError:
            url = None
        result = self._submit(url) if url is not None else "invalid_url"
        socket.write(encode_message({"status": result}))
        socket.disconnectFromServer()


def connect_to_desktop() -> QLocalSocket | None:
    socket = QLocalSocket()
    socket.connectToServer(socket_name())
    if socket.waitForConnected(250):
        return socket
    socket.abort()
    return None


def desktop_response(socket: QLocalSocket, url: str) -> dict:
    packet = encode_message({"action": "download", "url": url})
    if socket.write(packet) != len(packet):
        raise OSError("Could not write to the desktop application")
    socket.flush()

    def read_until(size: int) -> bytes:
        deadline = time.monotonic() + 2.0
        while socket.bytesAvailable() < size:
            remaining = int((deadline - time.monotonic()) * 1000)
            if remaining <= 0 or not socket.waitForReadyRead(remaining):
                if socket.bytesAvailable() < size:
                    raise OSError("No reply from the desktop application")
        return bytes(socket.read(size))

    size = message_size(read_until(HEADER.size))
    return decode_message(read_until(size))
