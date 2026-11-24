"""Check source UI download/cancel/quit behavior using localhost and offscreen Qt.

Run with the project's Python: python tests/check_desktop_flow.py
This does not test a frozen package, native browser messaging, or OS hotkeys.
"""

import os
from pathlib import Path
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from tempfile import TemporaryDirectory
from threading import Event, Thread
import time

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from app import VideoWindow, text
from desktop import BrowserCapture


PAYLOAD = b"%PDF-1.7\nStarlit local UI fixture\n" + bytes(range(256)) * 1024
SLOW_BLOCK = b"pending-transfer-" * 1024


class FixtureHandler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        path = self.path
        if path == "/fixture.pdf":
            body, name = PAYLOAD, "fixture.pdf"
        elif path in self.server.gates:
            body, name = SLOW_BLOCK * 64, path.rsplit("/", 1)[-1] + ".bin"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Disposition", f'attachment; filename="{name}"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            if path in self.server.gates:
                self.wfile.write(SLOW_BLOCK)
                self.wfile.flush()
                if not self.server.gates[path].wait(10):
                    return
                self.wfile.write(body[len(SLOW_BLOCK):])
            else:
                self.wfile.write(body)
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass


def wait_until(predicate, description, timeout=10):
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            raise AssertionError(f"Timed out: {description}")
        QTest.qWait(10)


def staging_files(folder):
    return [entry for stage in folder.glob(".hizliindir-*") for entry in stage.rglob("*") if entry.is_file()]


def check_flow():
    if getattr(sys, "frozen", False):
        raise RuntimeError("This diagnostic checks source UI only; run with the project's Python")
    application = QApplication([])
    application.setQuitOnLastWindowClosed(False)
    server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
    server.daemon_threads = True
    server.gates = {"/slow/cancel": Event(), "/slow/quit": Event()}
    serving = Thread(target=server.serve_forever, daemon=True)
    serving.start()
    base = f"http://127.0.0.1:{server.server_port}"
    capture = BrowserCapture(ROOT / "browser_address.ps1", application)
    window = None
    temporary = TemporaryDirectory(prefix="starlit-ui-check-")
    try:
        folder = Path(temporary.name) / "downloads"
        folder.mkdir()
        settings = QSettings(str(Path(temporary.name) / "settings.ini"), QSettings.Format.IniFormat)
        settings.setValue("downloadFolder", str(folder))
        settings.setValue("downloadFormat", "original")
        settings.sync()
        window = VideoWindow(application, settings, capture)
        window.tray.hide()
        capture.captured.connect(window.handle_capture)
        window.show()
        QTest.qWait(25)
        failures = []
        saved = []

        def watch_job():
            assert window.job is not None
            window.job.failed.connect(failures.append)
            window.job.saved.connect(saved.append)

        def completed_files():
            return sorted(entry for entry in folder.iterdir() if entry.is_file())

        def assert_clean(expected_count):
            assert not list(folder.glob(".hizliindir-*")), list(folder.iterdir())
            files = completed_files()
            assert len(files) == expected_count, files
            assert all(path.read_bytes() == PAYLOAD for path in files)
            assert failures == [], failures

        # Exercise the actual paste and download buttons with isolated preferences.
        application.clipboard().setText(base + "/fixture.pdf")
        QTest.mouseClick(window.paste_button, Qt.MouseButton.LeftButton)
        assert window.url.text() == base + "/fixture.pdf"
        QTest.mouseClick(window.download_button, Qt.MouseButton.LeftButton)
        watch_job()
        wait_until(lambda: window.job is None, "pasted URL download completion")
        assert window.status.text() == text("done"), window.status.text()
        assert window.download_button.isEnabled()
        assert window.saved_file and window.saved_file.read_bytes() == PAYLOAD
        assert_clean(1)
        print(f"PASS source UI clipboard paste + Download click: {len(PAYLOAD)} exact bytes", flush=True)

        # Deliver a URL through the real capture signal; no OS hotkey is registered.
        capture.captured.emit(base + "/fixture.pdf")
        watch_job()
        wait_until(lambda: window.job is None, "captured URL download completion")
        assert len(saved) == 2, saved
        assert {path.name for path in completed_files()} == {"fixture.pdf", "fixture (2).pdf"}
        assert_clean(2)
        print("PASS source UI capture signal: exact payload and existing file preserved", flush=True)

        def start_slow(path):
            capture.captured.emit(base + path)
            watch_job()
            cancelled = []
            window.job.cancelled.connect(lambda: cancelled.append(True))
            wait_until(lambda: bool(staging_files(folder)) and any(
                file.stat().st_size > 0 for file in staging_files(folder)), "slow staging data")
            assert not window.download_button.isEnabled()
            return cancelled

        cancelled = start_slow("/slow/cancel")
        original_job = window.job
        assert window.submit_browser_url(base + "/fixture.pdf") == "busy"
        assert window.job is original_job
        QTest.mouseClick(window.cancel_button, Qt.MouseButton.LeftButton)
        assert window._canceling and not window.cancel_button.isEnabled()
        QTimer.singleShot(150, server.gates["/slow/cancel"].set)
        wait_until(lambda: window.job is None, "Cancel button worker cleanup")
        assert cancelled == [True], cancelled
        assert window.status.text() == text("canceled")
        assert window.download_button.isEnabled()
        assert_clean(2)
        print("PASS source UI busy browser rejection + Cancel click: worker stopped, staging removed", flush=True)

        cancelled = start_slow("/slow/quit")
        quit_state = []
        confirmation_state = []
        errors = []
        application.aboutToQuit.connect(lambda: quit_state.append((window.job is None, window._quitting)))

        def choose_exit():
            dialog = application.activeModalWidget()
            if not isinstance(dialog, QMessageBox):
                errors.append("Quit confirmation dialog was not displayed")
                server.gates["/slow/quit"].set()
                application.quit()
                return
            button = next(button for button in dialog.buttons()
                          if dialog.buttonRole(button) == QMessageBox.ButtonRole.DestructiveRole)
            QTest.mouseClick(button, Qt.MouseButton.LeftButton)

        def request_quit():
            QTimer.singleShot(25, choose_exit)
            window._request_quit()
            confirmation_state.append((window._quitting, window.job is not None,
                                       bool(window.job and window.job.isRunning()), list(quit_state)))
            QTimer.singleShot(150, server.gates["/slow/quit"].set)

        timeout = QTimer(interval=10000, singleShot=True)
        timeout.timeout.connect(lambda: (errors.append("Quit did not wait/finish within deadline"), application.quit()))
        timeout.start()
        QTimer.singleShot(0, request_quit)
        assert application.exec() == 0
        timeout.stop()
        assert errors == [], errors
        assert confirmation_state == [(True, True, True, [])], confirmation_state
        assert quit_state == [(True, True)], quit_state
        assert cancelled == [True], cancelled
        assert window.job is None
        assert_clean(2)
        print("PASS source UI active-download Quit confirmation: waited for worker, cancelled, removed staging", flush=True)
        print("SOURCE-ONLY desktop flow OK: 4 checks; localhost fixtures; no external internet or OS hotkey test.", flush=True)
    finally:
        for gate in server.gates.values():
            gate.set()
        if window is not None:
            if window.job is not None:
                window.job.cancel()
                window.job.wait(9000)
                application.processEvents()
            window.tray.hide()
            window.hide()
        capture.stop()
        server.shutdown()
        server.server_close()
        serving.join(timeout=2)
        temporary.cleanup()


if __name__ == "__main__":
    check_flow()
