"""Cross-platform desktop services and native boundary regression tests."""
import ctypes
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent


class PlatformTests(unittest.TestCase):
    def test_unix_dispatch_imports_without_loading_windows_api(self):
        self.run_gui('''
from PySide6.QtCore import QCoreApplication
from PySide6 import QtGui, QtNetwork
from pathlib import Path
import sys
sys.platform = 'linux'
from desktop import BrowserCapture, DEFAULT_SHORTCUT
assert 'windows' not in sys.modules
app = QCoreApplication([])
capture = BrowserCapture(Path('missing'), app)
assert not capture.start(DEFAULT_SHORTCUT)
capture.stop()
''')

    def run_gui(self, script):
        result = subprocess.run([sys.executable, "-c", script], cwd=ROOT,
                                env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_gui_can_create_window_in_fresh_application(self):
        self.run_gui('''
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSettings
from app import VideoWindow
from unix_desktop import BrowserCapture
from pathlib import Path
app = QApplication([])
capture = BrowserCapture(Path("unused"), app)
window = VideoWindow(app, QSettings("StarlitTests", "Offscreen"), capture)
assert window.minimumWidth() > 0
window.tray.hide()
window.deleteLater()
capture.stop()
''')

    def test_single_instance_notifies_primary_and_releases_lock(self):
        self.run_gui('''
from PySide6.QtCore import QCoreApplication, QStandardPaths
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch
from unix_desktop import AppInstance
app = QCoreApplication([])
with TemporaryDirectory() as folder, patch.object(QStandardPaths, "writableLocation", return_value=folder), patch("unix_desktop.Path.home", return_value=Path(folder)):
    first = AppInstance(app)
    notifications = []
    first.reopen_requested.connect(lambda: notifications.append(True))
    try:
        assert not first.is_secondary
        second = AppInstance(app)
        assert second.is_secondary
        second.close()
        for _ in range(10): app.processEvents()
        assert notifications == [True], notifications
    finally:
        first.close()
    third = AppInstance(app)
    assert not third.is_secondary
    third.close()
''')

    def test_linux_capture_is_explicitly_unavailable(self):
        self.run_gui('''
from PySide6.QtCore import QCoreApplication
from pathlib import Path
from unittest.mock import patch
import unix_desktop
from shortcuts import DEFAULT_SHORTCUT
app = QCoreApplication([])
with patch.object(unix_desktop.sys, "platform", "linux"):
    capture = unix_desktop.BrowserCapture(Path("nonexistent"), app)
    assert capture.start(DEFAULT_SHORTCUT) is False
    assert capture.set_shortcut(DEFAULT_SHORTCUT) is False
    capture.stop()
''')

    def test_mac_hotkey_is_not_loaded_on_other_platforms(self):
        import mac_hotkey
        with patch.object(mac_hotkey.sys, "platform", "linux"), patch.object(ctypes, "CDLL", side_effect=AssertionError):
            from shortcuts import DEFAULT_SHORTCUT
            hotkey = mac_hotkey.MacHotkey(lambda: None)
            self.assertFalse(hotkey.set_shortcut(DEFAULT_SHORTCUT))
            hotkey.close()

    def test_shortcut_parser_preserves_existing_combinations(self):
        from shortcuts import Shortcut, DEFAULT_SHORTCUT
        self.assertEqual(Shortcut.parse("Ctrl+Shift+F9"), DEFAULT_SHORTCUT)
        for value in ("F9", "Meta+F9", "Ctrl+F12", "Ctrl+F9, Ctrl+F10", "Shift+A"):
            self.assertIsNone(Shortcut.parse(value), value)
        self.assertEqual(Shortcut.parse("Alt+A").virtual_key, 65)

    def test_capture_uses_real_process_output_and_rejects_errors(self):
        self.run_gui('''
from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer
from pathlib import Path
import sys
from unix_desktop import BrowserCapture
app = QCoreApplication([])
capture = BrowserCapture(Path("unused"), app)
for code, expected in [("print('https://example.com/video')", 'https://example.com/video'),
                       ("print('javascript:alert(1)')", ''),
                       ("import sys; print('https://example.com'); sys.exit(1)", ''),
                       ("import time; time.sleep(10)", '')]:
    loop = QEventLoop()
    results = []
    def receive(value):
        results.append(value)
        loop.quit()
    capture.captured.connect(receive)
    capture._process.start(sys.executable, ['-c', code])
    capture._timer.start(100 if 'sleep' in code else 3500)
    QTimer.singleShot(5000, loop.quit)
    loop.exec()
    capture.captured.disconnect(receive)
    assert results == [expected], results
capture.stop()
''')

    def test_carbon_callback_filters_id_and_failed_replacement_keeps_binding(self):
        import mac_hotkey
        from shortcuts import Shortcut, DEFAULT_SHORTCUT
        events = []
        class Function:
            def __init__(self, call): self.call = call
            def __call__(self, *args): return self.call(*args)
        class Carbon:
            def __init__(self):
                self.fail = False
                self.incoming = (mac_hotkey.SIGNATURE, 1)
                self.GetApplicationEventTarget = Function(lambda: 10)
                self.InstallEventHandler = Function(self.install)
                self.RegisterEventHotKey = Function(self.register)
                self.UnregisterEventHotKey = Function(lambda ref: events.append(('unregister', ref.value)) or 0)
                self.RemoveEventHandler = Function(lambda ref: events.append(('remove', ref.value)) or 0)
                self.GetEventParameter = Function(self.parameter)
            def install(self, target, callback, count, spec, data, out):
                self.callback = callback
                ctypes.cast(out, ctypes.POINTER(ctypes.c_void_p))[0] = 100
                return 0
            def register(self, key, modifiers, identifier, target, options, out):
                events.append(('register', key, modifiers, identifier.id))
                if self.fail: return -9878
                ctypes.cast(out, ctypes.POINTER(ctypes.c_void_p))[0] = 200 + identifier.id
                return 0
            def parameter(self, event, name, kind, actual, size, actual_size, out):
                assert name == 0x2d2d2d2d and kind == 0x686b6964 and size == 8
                value = ctypes.cast(out, ctypes.POINTER(mac_hotkey.EventHotKeyID)).contents
                value.signature, value.id = self.incoming
                return 0
        carbon = Carbon()
        fired = []
        with patch.object(mac_hotkey.sys, 'platform', 'darwin'), patch.object(ctypes, 'CDLL', return_value=carbon):
            hotkey = mac_hotkey.MacHotkey(lambda: fired.append(True))
            self.assertTrue(hotkey.set_shortcut(DEFAULT_SHORTCUT))
            self.assertEqual(events, [('register', 101, 4608, 1)])
            self.assertEqual(carbon.callback(None, 1, None), 0)
            carbon.incoming = (mac_hotkey.SIGNATURE, 2)
            self.assertEqual(carbon.callback(None, 1, None), -9874)
            carbon.incoming = (123, 1)
            self.assertEqual(carbon.callback(None, 1, None), -9874)
            carbon.fail = True
            self.assertFalse(hotkey.set_shortcut(Shortcut.parse('Alt+A')))
            carbon.incoming = (mac_hotkey.SIGNATURE, 1)
            self.assertEqual(carbon.callback(None, 1, None), 0)
            self.assertEqual(fired, [True, True])
            self.assertNotIn(('unregister', 201), events)
            carbon.fail = False
            self.assertTrue(hotkey.set_shortcut(Shortcut.parse('Alt+A')))
            self.assertEqual(events[-2:], [('register', 0, 2048, 2), ('unregister', 201)])
            hotkey.close()
            hotkey.close()
            self.assertEqual(events[-2:], [('unregister', 202), ('remove', 100)])

    def test_bridge_listen_failure_cleans_up_and_secondary_never_removes_socket(self):
        self.run_gui('''
from unittest.mock import MagicMock, patch
import app
instance = MagicMock(is_secondary=True)
with patch.object(app, 'AppInstance', return_value=instance), patch.object(app.QLocalServer, 'removeServer') as remove:
    assert app.main() == 0
    remove.assert_not_called()
''')
        self.run_gui('''
from unittest.mock import MagicMock, patch
from shortcuts import DEFAULT_SHORTCUT
import app
instance = MagicMock(is_secondary=False)
capture = MagicMock()
window = MagicMock(shortcut=DEFAULT_SHORTCUT)
bridge = MagicMock()
bridge.listen.return_value = False
with patch.object(app, 'AppInstance', return_value=instance), patch.object(app, 'BrowserCapture', return_value=capture), patch.object(app, 'VideoWindow', return_value=window), patch.object(app, 'BrowserBridge', return_value=bridge), patch.object(app, 'socket_name', return_value='fixture'), patch.object(app.QLocalServer, 'removeServer') as remove:
    assert app.main() == 1
    remove.assert_called_once_with('fixture')
    instance.close.assert_called_once()
    capture.stop.assert_called_once()
    bridge.close.assert_called_once()
''')

    def test_smoke_startup_exits_and_releases_primary_instance(self):
        for _ in range(2):
            try:
                result = subprocess.run([sys.executable, 'app.py', '--smoke-test'], cwd=ROOT,
                                        env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'},
                                        capture_output=True, text=True, timeout=5)
            except subprocess.TimeoutExpired:
                self.fail('The GUI smoke check did not exit after startup')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_unix_listen_failure_releases_primary_lock(self):
        self.run_gui('''
from PySide6.QtCore import QCoreApplication, QStandardPaths
from PySide6.QtNetwork import QLocalServer
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch
from unix_desktop import AppInstance
app = QCoreApplication([])
with TemporaryDirectory() as folder, patch.object(QStandardPaths, 'writableLocation', return_value=folder), patch('unix_desktop.Path.home', return_value=Path(folder)):
    with patch.object(QLocalServer, 'listen', return_value=False):
        try:
            AppInstance(app)
        except OSError:
            pass
        else:
            raise AssertionError('listen error ignored')
    instance = AppInstance(app)
    assert not instance.is_secondary
    instance.close()
''')

    def test_unix_shell_paths_and_finder_selection(self):
        import unix_desktop
        with patch.object(unix_desktop.QStandardPaths, 'writableLocation', return_value='/custom/downloads'):
            self.assertEqual(unix_desktop.downloads_folder(), Path('/custom/downloads'))
        with patch.object(unix_desktop.QStandardPaths, 'writableLocation', return_value=''):
            self.assertEqual(unix_desktop.downloads_folder(), Path.home() / 'Downloads')
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'a file.mp4'
            source.write_bytes(b'finished')
            with patch.object(unix_desktop.sys, 'platform', 'darwin'), patch.object(unix_desktop.QProcess, 'startDetached', return_value=(True, 123)) as launch:
                self.assertTrue(unix_desktop.show_file(source))
                launch.assert_called_once_with('/usr/bin/open', ['-R', str(source.resolve())])
            with patch.object(unix_desktop.sys, 'platform', 'linux'), patch.object(unix_desktop.QDesktopServices, 'openUrl', return_value=True) as launch:
                self.assertTrue(unix_desktop.show_file(source))
                self.assertEqual(launch.call_args.args[0].toLocalFile(), str(source.parent.resolve()).replace('\\', '/'))


if __name__ == "__main__":
    unittest.main()
