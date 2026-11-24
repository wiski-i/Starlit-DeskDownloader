"""Chrome Native Messaging entry point with binary standard input and output."""

import json
import os
import shlex
import subprocess
import sys
import tempfile
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
            name = "HizliIndir.exe" if sys.platform == "win32" else "HizliIndir"
            command = [str(Path(sys.executable).with_name(name))]
        else:
            command = [sys.executable, str(Path(__file__).with_name("app.py"))]
        options = {"creationflags": subprocess.DETACHED_PROCESS} if sys.platform == "win32" else {"start_new_session": True}
        subprocess.Popen(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            **options, env={**os.environ, "PYINSTALLER_RESET_ENVIRONMENT": "1"},
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


def register_browser_host() -> Path:
    """Register this installation for Chrome on macOS; repeat after moving it."""
    if sys.platform != "darwin":
        raise OSError("Browser host registration is only available on macOS")
    directory = Path.home() / "Library/Application Support/Google/Chrome/NativeMessagingHosts"
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / "com.starlit.deskdownloader.json"
    origins = ["chrome-extension://jnhpcainmeohhdljgolpbgkhoodcfape/"]
    if manifest_path.exists():
        try:
            previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as error:
            raise FileExistsError(f"Existing host manifest was not replaced: {manifest_path}") from error
        if not isinstance(previous, dict) or previous.get("name") != "com.starlit.deskdownloader" or previous.get("allowed_origins") != origins or previous.get("type") != "stdio":
            raise FileExistsError(f"Existing host manifest was not replaced: {manifest_path}")
    if getattr(sys, "frozen", False):
        host_path = Path(sys.executable).resolve()
    else:
        host_path = directory / "com.starlit.deskdownloader.sh"
        marker = "#!/bin/sh\n# Hızlı İndir Native Messaging launcher\n"
        if host_path.exists() and not host_path.read_text(encoding="utf-8").startswith(marker):
            raise FileExistsError(f"Existing launcher was not replaced: {host_path}")
        _write_registration(host_path, marker + "exec " + shlex.join([sys.executable, str(Path(__file__).resolve())]) + "\n", executable=True)
    manifest = {"name": "com.starlit.deskdownloader", "description": "Hızlı İndir browser bridge", "path": str(host_path), "type": "stdio", "allowed_origins": origins}
    _write_registration(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return manifest_path


def _write_registration(path: Path, contents: str, executable: bool = False) -> None:
    """Keep an interrupted registration from leaving a partial manifest or script."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(contents)
        if executable:
            temporary.chmod(0o700)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> None:
    if sys.argv[1:] == ["--register-browser-host"]:
        print(register_browser_host())
        return
    application = QCoreApplication([sys.argv[0]])
    if sys.platform == "win32":
        import msvcrt

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
