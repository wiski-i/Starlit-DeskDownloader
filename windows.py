"""Windows shortcut, foreground browser capture, and shell paths."""

import base64
import ctypes
import hashlib
import os
import uuid
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import (
    QAbstractNativeEventFilter, QObject, QProcess, Qt, QTimer, QUrl, QWinEventNotifier, Signal,
)
from PySide6.QtGui import QColor, QDesktopServices, QKeySequence
from shiboken6 import VoidPtr

from downloads import download_url

HOTKEY_IDS = (0x4310, 0x4311)
WM_HOTKEY = 0x0312
FOLDERID_DOWNLOADS = uuid.UUID("374de290-123f-4565-9164-39c4925e467b")
ERROR_ALREADY_EXISTS = 183
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_BORDER_COLOR = 34
DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36

USER32 = ctypes.WinDLL("user32", use_last_error=True)
USER32.GetForegroundWindow.restype = wintypes.HWND
USER32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
USER32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)
KERNEL32.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
KERNEL32.CreateEventW.restype = wintypes.HANDLE
KERNEL32.SetEvent.argtypes = [wintypes.HANDLE]
KERNEL32.CloseHandle.argtypes = [wintypes.HANDLE]


@dataclass(frozen=True)
class Shortcut:
    portable: str
    modifiers: int
    virtual_key: int

    @classmethod
    def parse(cls, value: str) -> "Shortcut | None":
        sequence = QKeySequence.fromString(value, QKeySequence.SequenceFormat.PortableText)
        if sequence.count() != 1:
            return None
        combination = sequence[0]
        flags = combination.keyboardModifiers()
        allowed = (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier
                   | Qt.KeyboardModifier.ShiftModifier)
        if not flags or flags & ~allowed:
            return None
        ctrl = bool(flags & Qt.KeyboardModifier.ControlModifier)
        alt = bool(flags & Qt.KeyboardModifier.AltModifier)
        shift = bool(flags & Qt.KeyboardModifier.ShiftModifier)
        key = int(combination.key())
        if 0x01000030 <= key <= 0x01000047 and key != int(Qt.Key.Key_F12):
            virtual_key = 0x70 + key - int(Qt.Key.Key_F1)
        elif (ctrl or alt) and (ord("A") <= key <= ord("Z") or ord("0") <= key <= ord("9")):
            virtual_key = key
        else:
            return None
        modifiers = 0x4000 | int(alt) | (int(ctrl) << 1) | (int(shift) << 2)
        return cls(sequence.toString(QKeySequence.SequenceFormat.PortableText), modifiers, virtual_key)


DEFAULT_SHORTCUT = Shortcut("Ctrl+Shift+F9", 0x4006, 0x78)


def downloads_folder() -> Path:
    """Return the current user's Downloads location, including redirected folders."""
    folder_id = (ctypes.c_byte * 16).from_buffer_copy(FOLDERID_DOWNLOADS.bytes_le)
    result = ctypes.c_wchar_p()
    shell32 = ctypes.WinDLL("shell32")
    if shell32.SHGetKnownFolderPath(ctypes.byref(folder_id), 0, None, ctypes.byref(result)) == 0:
        try:
            return Path(result.value)
        finally:
            ole32 = ctypes.WinDLL("ole32")
            ole32.CoTaskMemFree(ctypes.cast(result, ctypes.c_void_p))
    return Path.home() / "Downloads"


def show_file(path: Path) -> bool:
    """Open File Explorer with the finished file selected when possible."""
    if path.is_file():
        shell32 = ctypes.WinDLL("shell32")
        shell32.ILCreateFromPathW.argtypes = [wintypes.LPCWSTR]
        shell32.ILCreateFromPathW.restype = ctypes.c_void_p
        shell32.SHOpenFolderAndSelectItems.argtypes = [ctypes.c_void_p, wintypes.UINT, ctypes.c_void_p, wintypes.DWORD]
        shell32.ILFree.argtypes = [ctypes.c_void_p]
        item = shell32.ILCreateFromPathW(str(path))
        if item:
            try:
                if shell32.SHOpenFolderAndSelectItems(item, 0, None, 0) == 0:
                    return True
            finally:
                shell32.ILFree(item)
    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))


def set_title_bar_colors(handle: int, background: str, foreground: str, border: str) -> None:
    """Match the native window frame to the app colors where Windows supports it."""
    set_attribute = ctypes.WinDLL("dwmapi").DwmSetWindowAttribute
    set_attribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    dark = wintypes.BOOL(True)
    set_attribute(handle, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(dark), ctypes.sizeof(dark))
    for attribute, hex_color in (
        (DWMWA_CAPTION_COLOR, background), (DWMWA_TEXT_COLOR, foreground), (DWMWA_BORDER_COLOR, border),
    ):
        color = QColor(hex_color)
        value = wintypes.DWORD(color.red() | color.green() << 8 | color.blue() << 16)
        set_attribute(handle, attribute, ctypes.byref(value), ctypes.sizeof(value))


class AppInstance(QObject):
    """Notify an already running window through a per-user Windows event."""

    reopen_requested = Signal()

    def __init__(self, application: QObject) -> None:
        super().__init__(application)
        user = hashlib.sha256(os.path.normcase(str(Path.home())).encode("utf-8")).hexdigest()[:24]
        ctypes.set_last_error(0)
        self._handle = KERNEL32.CreateEventW(None, False, False, f"Local\\HizliIndir.Reopen.{user}")
        self.is_secondary = bool(self._handle and ctypes.get_last_error() == ERROR_ALREADY_EXISTS)
        if self.is_secondary:
            KERNEL32.SetEvent(self._handle)
            KERNEL32.CloseHandle(self._handle)
            self._handle = None
        elif self._handle:
            self._notifier = QWinEventNotifier(VoidPtr(self._handle), self)
            self._notifier.activated.connect(self._reopen)

    def _reopen(self) -> None:
        self.reopen_requested.emit()

    def close(self) -> None:
        if self._handle:
            self._notifier.setEnabled(False)
            KERNEL32.CloseHandle(self._handle)
            self._handle = None


class HotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, capture: "BrowserCapture") -> None:
        super().__init__()
        self.capture = capture

    def nativeEventFilter(self, event_type: bytes, message: int) -> tuple[bool, int]:
        if bytes(event_type) in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            event = wintypes.MSG.from_address(int(message))
            if event.message == WM_HOTKEY and event.wParam == self.capture.hotkey_id:
                self.capture.read_foreground()
                return True, 0
        return False, 0


class BrowserCapture(QObject):
    captured = Signal(str)

    def __init__(self, script: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._script = script.read_text(encoding="utf-8-sig")
        self._filter = HotkeyFilter(self)
        self._process = QProcess(self)
        self._process.finished.connect(self._finished)
        self._process.errorOccurred.connect(self._process_error)
        self._timer = QTimer(self, singleShot=True, interval=3500)
        self._timer.timeout.connect(self._process.kill)
        self.hotkey_id: int | None = None
        self._shortcut: Shortcut | None = None

    def start(self, shortcut: Shortcut) -> bool:
        """Register a global shortcut on the application's GUI thread."""
        self.parent().installNativeEventFilter(self._filter)
        return self.set_shortcut(shortcut)

    def set_shortcut(self, shortcut: Shortcut) -> bool:
        """Register the replacement before dropping the existing shortcut."""
        if shortcut == self._shortcut:
            return True
        old_id = self.hotkey_id
        new_id = HOTKEY_IDS[1] if old_id == HOTKEY_IDS[0] else HOTKEY_IDS[0]
        if not USER32.RegisterHotKey(None, new_id, shortcut.modifiers, shortcut.virtual_key):
            return False
        self.hotkey_id = new_id
        self._shortcut = shortcut
        if old_id is not None:
            USER32.UnregisterHotKey(None, old_id)
        return True

    def stop(self) -> None:
        self.parent().removeNativeEventFilter(self._filter)
        if self.hotkey_id is not None:
            USER32.UnregisterHotKey(None, self.hotkey_id)
            self.hotkey_id = None
            self._shortcut = None
        if self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.blockSignals(True)
            self._process.kill()
            self._process.waitForFinished(1000)

    def read_foreground(self) -> None:
        if self._process.state() != QProcess.ProcessState.NotRunning:
            return
        handle = USER32.GetForegroundWindow()
        if not handle:
            self.captured.emit("")
            return
        command = f"$browserHandle = {handle}\n{self._script}"
        encoded = base64.b64encode(command.encode("utf-16-le")).decode("ascii")
        powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        self._process.start(str(powershell), ["-NoProfile", "-NonInteractive", "-EncodedCommand", encoded])
        self._timer.start()

    def _finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        self._timer.stop()
        address = bytes(self._process.readAllStandardOutput()).decode("utf-8", errors="replace").strip()
        if exit_code or exit_status != QProcess.ExitStatus.NormalExit:
            self.captured.emit("")
            return
        if address and "://" not in address:
            domain = address.split("/", 1)[0].split(":", 1)[0]
            if domain == "localhost" or domain.startswith("127."):
                address = f"http://{address}"
            elif "." in domain:
                address = f"https://{address}"
        self.captured.emit(download_url(address) or "")

    def _process_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            self._timer.stop()
            self.captured.emit("")
