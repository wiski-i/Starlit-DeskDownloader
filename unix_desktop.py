"""Unix desktop paths, per-user instance coordination, and macOS capture."""

import hashlib
from pathlib import Path
import sys
import time

from PySide6.QtCore import QObject, QLockFile, QProcess, QStandardPaths, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from downloads import download_url
from shortcuts import Shortcut


# Compile only the active browser's dictionary; the other browsers may not be installed.
APPLE_SCRIPT = r'''
tell application "System Events" to set frontApp to name of first application process whose frontmost is true
if frontApp is "Safari" then
    return run script "tell application \"Safari\" to return URL of current tab of front window"
else if frontApp is in {"Google Chrome", "Chromium", "Brave Browser", "Microsoft Edge"} then
    return run script ("tell application \"" & frontApp & "\" to return URL of active tab of front window")
end if
return ""
'''


def downloads_folder() -> Path:
    location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
    return Path(location) if location else Path.home() / "Downloads"


def show_file(path: Path) -> bool:
    if sys.platform == "darwin" and path.is_file():
        return QProcess.startDetached("/usr/bin/open", ["-R", str(path.resolve())])[0]
    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent.resolve())))


def set_title_bar_colors(handle: int, background: str, foreground: str, border: str) -> None:
    """The system manages native frame colors on Unix."""


class AppInstance(QObject):
    """Keep the per-user lock until the primary has closed its reopen server."""

    reopen_requested = Signal()

    def __init__(self, application: QObject) -> None:
        super().__init__(application)
        user = hashlib.sha256(str(Path.home()).encode("utf-8")).hexdigest()[:24]
        self._name = f"HizliIndir.Reopen.{user}"
        location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.RuntimeLocation)
        folder = Path(location) if location else Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.TempLocation))
        folder.mkdir(parents=True, exist_ok=True)
        self._lock = QLockFile(str(folder / f"{self._name}.lock"))
        self._lock.setStaleLockTime(0)
        self._server = QLocalServer(self)
        self._server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self._server.newConnection.connect(self._reopen)
        self.is_secondary = not self._lock.tryLock(0)
        if self.is_secondary:
            if self._lock.error() != QLockFile.LockError.LockFailedError:
                raise OSError("Could not lock the desktop application instance")
            # The primary may still be creating its socket after acquiring the lock.
            peer = QLocalSocket()
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                peer.connectToServer(self._name)
                if peer.waitForConnected(100):
                    peer.disconnectFromServer()
                    return
                peer.abort()
                time.sleep(0.05)
            raise OSError("The running desktop application did not respond")
        QLocalServer.removeServer(self._name)
        if not self._server.listen(self._name):
            self._lock.unlock()
            raise OSError(self._server.errorString())

    def _reopen(self) -> None:
        while self._server.hasPendingConnections():
            peer = self._server.nextPendingConnection()
            peer.disconnectFromServer()
            peer.deleteLater()
            self.reopen_requested.emit()

    def close(self) -> None:
        if not self.is_secondary and self._lock.isLocked():
            self._server.close()
            self._lock.unlock()


class BrowserCapture(QObject):
    captured = Signal(str)

    def __init__(self, script: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._hotkey = None
        self._process = QProcess(self)
        self._process.finished.connect(self._finished)
        self._process.errorOccurred.connect(self._process_error)
        self._timer = QTimer(self, singleShot=True, interval=3500)
        self._timer.timeout.connect(self._process.kill)

    def start(self, shortcut: Shortcut) -> bool:
        return self.set_shortcut(shortcut)

    def set_shortcut(self, shortcut: Shortcut) -> bool:
        if sys.platform != "darwin":
            return False
        if self._hotkey is None:
            from mac_hotkey import MacHotkey
            self._hotkey = MacHotkey(self.read_foreground)
        return self._hotkey.set_shortcut(shortcut)

    def stop(self) -> None:
        self._timer.stop()
        if self._hotkey is not None:
            self._hotkey.close()
        if self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.blockSignals(True)
            self._process.kill()
            self._process.waitForFinished(1000)

    def read_foreground(self) -> None:
        if sys.platform != "darwin":
            self.captured.emit("")
            return
        if self._process.state() == QProcess.ProcessState.NotRunning:
            self._process.start("/usr/bin/osascript", ["-e", APPLE_SCRIPT])
            self._timer.start()

    def _finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        self._timer.stop()
        address = bytes(self._process.readAllStandardOutput()).decode("utf-8", errors="replace").strip()
        success = exit_code == 0 and exit_status == QProcess.ExitStatus.NormalExit
        self.captured.emit((download_url(address) or "") if success else "")

    def _process_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            self._timer.stop()
            self.captured.emit("")
