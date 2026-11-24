"""Carry a single browser URL to the running desktop application."""

import ctypes
import hashlib
import json
import os
import struct
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from downloads import download_url
from media_profiles import DownloadProfile


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


class RequestError(ValueError):
    """A browser request failed validation."""


@dataclass(frozen=True)
class BrowserDownload:
    url: str
    profile: DownloadProfile | None = None

    def as_message(self) -> dict:
        message = {"action": "download", "url": self.url}
        if self.profile is not None:
            message["profile"] = {"format": self.profile.format_id, "quality": self.profile.quality}
        return message


def parse_download_request(request: dict) -> BrowserDownload:
    keys = set(request)
    url = request.get("url")
    if request.get("action") != "download" or not isinstance(url, str):
        raise RequestError("invalid_url")
    if any(ord(character) <= 32 or ord(character) == 127 for character in url):
        raise RequestError("invalid_url")
    try:
        address = download_url(url) if len(url.encode("utf-8")) <= 8192 else None
    except UnicodeEncodeError as error:
        raise RequestError("invalid_url") from error
    if address is None:
        raise RequestError("invalid_url")
    if keys == {"action", "url"}:
        return BrowserDownload(address)
    profile = request.get("profile")
    if keys != {"action", "url", "profile"} or not isinstance(profile, dict) or set(profile) != {"format", "quality"}:
        raise RequestError("invalid_profile")
    format_id, quality = profile["format"], profile["quality"]
    if not isinstance(format_id, str) or not isinstance(quality, str):
        raise RequestError("invalid_profile")
    chosen = DownloadProfile(format_id, quality)
    if chosen != DownloadProfile.from_setting(format_id, quality):
        raise RequestError("invalid_profile")
    return BrowserDownload(address, chosen)


def socket_name() -> str:
    if sys.platform == "win32":
        from ctypes import wintypes

        session = wintypes.DWORD()
        if not ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(session)):
            raise OSError("Could not determine the Windows session")
        identity = session.value
    else:
        identity = os.getuid()
    user = hashlib.sha256(os.path.normcase(str(Path.home())).encode("utf-8")).hexdigest()[:24]
    return f"HizliIndir.Browser.{identity}.{user}"


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
            request = parse_download_request(decode_message(bytes(socket.read(size))))
        except RequestError as error:
            result = str(error)
        except ValueError:
            result = "invalid_url"
        else:
            try:
                result = self._submit(request.url, profile=request.profile)
            except Exception:
                result = "desktop_unavailable"
        socket.write(encode_message({"status": result}))
        socket.disconnectFromServer()


def connect_to_desktop() -> QLocalSocket | None:
    socket = QLocalSocket()
    socket.connectToServer(socket_name())
    if socket.waitForConnected(250):
        return socket
    socket.abort()
    return None


def desktop_response(socket: QLocalSocket, request: BrowserDownload) -> dict:
    packet = encode_message(request.as_message())
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
