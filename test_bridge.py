"""Native Messaging framing, request validation and local socket regressions."""
import json
import os
import shlex
import struct
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QEventLoop
from PySide6.QtNetwork import QLocalSocket

import browser_bridge
import native_host
from browser_bridge import BrowserBridge, RequestError, decode_message, encode_message, parse_download_request


class BridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QCoreApplication.instance() or QCoreApplication([])

    def test_unicode_framing_and_invalid_frames(self):
        message = {'action': 'download', 'url': 'https://example.com/çağrı'}
        packet = encode_message(message)
        self.assertEqual(struct.unpack('<I', packet[:4])[0], len(packet[4:]))
        self.assertEqual(decode_message(packet[4:]), message)
        for frame in (b'', b'123', struct.pack('<I', 0), struct.pack('<I', 16385)):
            with self.subTest(frame=frame), self.assertRaises(ValueError):
                browser_bridge.message_size(frame)
        for value in (b'[]', b'null', b'{}extra', b'\xff'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                decode_message(value)

    def test_shared_url_vectors_match_extension(self):
        cases = json.loads((Path(__file__).parent / "tests/url-cases.json").read_text(encoding="utf-8"))
        for entry in cases:
            with self.subTest(url=entry["url"]):
                message = {"action": "download", "url": entry["url"]}
                if entry["accepted"]:
                    self.assertIsNotNone(parse_download_request(message))
                else:
                    with self.assertRaisesRegex(RequestError, "invalid_url"):
                        parse_download_request(message)

    def test_request_url_and_profile_validation(self):
        url = 'https://example.com/çağrı'
        request = parse_download_request({'action': 'download', 'url': url, 'profile': {'format': 'mp4', 'quality': '720'}})
        self.assertEqual(request.url, url)
        self.assertEqual(request.profile.quality, '720')
        for profile in (None, [], {}, {'format': 'mp4', 'quality': 'bogus'}, {'format': 'exe', 'quality': 'best'}, {'format': 'mp4', 'quality': 720}, {'format': 'mp4', 'quality': '720', 'other': 1}):
            with self.subTest(profile=profile), self.assertRaisesRegex(RequestError, 'invalid_profile'):
                parse_download_request({'action': 'download', 'url': url, 'profile': profile})
        for url in ('https:example.com', 'https:///example.com', 'https://@example.com', 'https://example.com:', 'https://example.com/a b', 'https://example.com/\x7f', 'https://exam\tple.com/', 'https://example.com\\evil', 'https://example.com/' + 'a' * 8173):
            with self.subTest(url=url), self.assertRaisesRegex(RequestError, 'invalid_url'):
                parse_download_request({'action': 'download', 'url': url})
        self.assertIsNotNone(parse_download_request({'action': 'download', 'url': 'https://example.com/' + 'a' * 8172}))

    def test_local_callback_exception_returns_reply(self):
        def fail(*args, **kwargs):
            raise RuntimeError('download failed')
        bridge = BrowserBridge(fail)
        name = 'HizliIndir.Test.' + uuid.uuid4().hex
        self.assertTrue(bridge.listen(name))
        peer = QLocalSocket()
        try:
            peer.connectToServer(name)
            self.assertTrue(peer.waitForConnected(1000))
            peer.write(encode_message({'action': 'download', 'url': 'https://example.com/çağrı'}))
            peer.flush()
            deadline = time.monotonic() + 3
            while peer.bytesAvailable() == 0 and time.monotonic() < deadline:
                self.application.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 10)
                time.sleep(0.001)
            packet = bytes(peer.readAll())
            self.assertGreaterEqual(len(packet), 4)
            self.assertEqual(decode_message(packet[4:]), {'status': 'desktop_unavailable'})
        finally:
            peer.abort()
            bridge.close()

    def test_unix_socket_identity_uses_user_and_home(self):
        fake_os = SimpleNamespace(getuid=lambda: 123, path=os.path)
        with patch.object(browser_bridge, 'sys', SimpleNamespace(platform='darwin')), patch.object(browser_bridge, 'os', fake_os):
            first = browser_bridge.socket_name()
            self.assertTrue(first.startswith('HizliIndir.Browser.123.'))
            self.assertEqual(first, browser_bridge.socket_name())

    def test_platform_launch_options_and_frozen_application_path(self):
        for platform, frozen, app_name in (("win32", True, "HizliIndir.exe"), ("darwin", True, "HizliIndir"), ("darwin", False, "app.py")):
            with self.subTest(platform=platform, frozen=frozen):
                calls = []
                peer = SimpleNamespace(abort=lambda: None)
                fake_sys = SimpleNamespace(platform=platform, executable=sys.executable, frozen=frozen)
                with patch.object(native_host.subprocess, "DETACHED_PROCESS", 8, create=True), patch.object(native_host, "sys", fake_sys), patch.object(native_host, "connect_to_desktop", side_effect=[None, peer]), patch.object(native_host.subprocess, "Popen", side_effect=lambda command, **options: calls.append((command, options))), patch.object(native_host, "desktop_response", return_value={"status": "accepted"}), patch.object(native_host.time, "sleep"):
                    result = native_host.send_to_desktop(parse_download_request({"action": "download", "url": "https://example.com"}))
                self.assertEqual(result, {"status": "accepted"})
                command, options = calls[0]
                self.assertEqual(Path(command[-1]).name, app_name)
                self.assertEqual(options["env"]["PYINSTALLER_RESET_ENVIRONMENT"], "1")
                self.assertEqual(options["stdout"], subprocess.DEVNULL)
                if platform == "win32":
                    self.assertEqual(options["creationflags"], 8)
                    self.assertNotIn("start_new_session", options)
                else:
                    self.assertTrue(options["start_new_session"])
                    self.assertNotIn("creationflags", options)

    def test_source_host_real_binary_protocol(self):
        for body in ({'action': 'get_profiles'}, {'action': 'download', 'url': 'https://example.com/çağrı', 'profile': {'format': 'mp4', 'quality': 'invalid'}}):
            packet = encode_message(body)
            result = subprocess.run([sys.executable, 'native_host.py'], input=packet, capture_output=True, timeout=15, cwd=Path(__file__).parent)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
            self.assertGreaterEqual(len(result.stdout), 4)
            length = struct.unpack('<I', result.stdout[:4])[0]
            self.assertEqual(len(result.stdout), length + 4)
            reply = decode_message(result.stdout[4:])
            if body['action'] == 'get_profiles':
                self.assertEqual(reply['status'], 'profiles')
                self.assertEqual(len(reply['formats']), 15)
                self.assertEqual(sum(len(item['qualities']) for item in reply['formats']), 58)
            else:
                self.assertEqual(reply, {'status': 'invalid_profile'})
        for packet in (b'\x00\x00\x00\x00', b'\x01\x00', struct.pack('<I', 5) + b'{}'):
            result = subprocess.run([sys.executable, 'native_host.py'], input=packet, capture_output=True, timeout=15, cwd=Path(__file__).parent)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
            self.assertEqual(decode_message(result.stdout[4:]), {'status': 'invalid_url'})

    def test_macos_registration_source_launcher_and_foreign_manifest(self):
        with tempfile.TemporaryDirectory(prefix="host ' ") as directory:
            with patch.object(native_host, 'sys', SimpleNamespace(platform='darwin', executable=sys.executable, frozen=False)), patch.object(Path, 'home', return_value=Path(directory)):
                manifest_path = native_host.register_browser_host()
                manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
                self.assertEqual(manifest['allowed_origins'], ['chrome-extension://jnhpcainmeohhdljgolpbgkhoodcfape/'])
                launcher = Path(manifest['path'])
                self.assertTrue(launcher.is_absolute())
                command = launcher.read_text(encoding='utf-8').splitlines()[-1]
                self.assertEqual(shlex.split(command), ['exec', sys.executable, str(Path(native_host.__file__).resolve())])
                if os.name != "nt":
                    self.assertTrue(launcher.stat().st_mode & 0o100)
                self.assertEqual(native_host.register_browser_host(), manifest_path)
                manifest_path.write_text('{"name":"some.other.host"}', encoding='utf-8')
                with self.assertRaises(FileExistsError):
                    native_host.register_browser_host()

    def test_macos_registration_frozen_host_path(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = str(Path(directory) / 'HizliIndir.app/Contents/MacOS/HizliIndirBrowserHost')
            with patch.object(native_host, 'sys', SimpleNamespace(platform='darwin', executable=executable, frozen=True)), patch.object(Path, 'home', return_value=Path(directory)):
                manifest = json.loads(native_host.register_browser_host().read_text(encoding='utf-8'))
                self.assertEqual(manifest['path'], str(Path(executable).resolve()))


if __name__ == '__main__':
    unittest.main()
