"""Check desktop download jobs against deterministic local video sources."""

import subprocess
import time
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from zipfile import ZipFile

from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer

from downloads import DownloadJob, _is_social_video_page, download_url, ffmpeg_binary
from windows import DEFAULT_SHORTCUT, Shortcut


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, message, *args):
        pass

    def do_GET(self):
        if self.path == "/slow.bin":
            chunk = b"x" * 4096
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(chunk) * 32))
            self.end_headers()
            try:
                for _ in range(32):
                    self.wfile.write(chunk)
                    time.sleep(0.15)
            except ConnectionError:
                pass
            return
        if self.path == "/partial":
            data = b"part"
            self.send_response(206)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Content-Range", "bytes 0-3/128")
            self.end_headers()
            self.wfile.write(data)
            return
        if self.path == "/document":
            data = b"%PDF-1.7\nfixture"
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if self.path == "/attachment":
            data = b"sample attachment"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Disposition", "attachment; filename*=UTF-8''%C3%B6rnek.txt")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        super().do_GET()


class DownloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ffmpeg = ffmpeg_binary()
        if not cls.ffmpeg:
            raise unittest.SkipTest("FFmpeg is required for the video fixtures.")
        cls.application = QCoreApplication.instance() or QCoreApplication([])
        fixtures = TemporaryDirectory()
        cls.addClassCleanup(fixtures.cleanup)
        cls.fixtures = Path(fixtures.name)
        subprocess.run([
            cls.ffmpeg, "-v", "error", "-f", "lavfi", "-i", "color=c=purple:s=160x90:r=10",
            "-f", "lavfi", "-i", "sine=frequency=440", "-t", "2",
            "-c:v", "libx264", "-c:a", "aac", str(cls.fixtures / "sample.mp4"),
        ], check=True)
        subprocess.run([
            cls.ffmpeg, "-v", "error", "-i", "sample.mp4", "-map", "0:v",
            "-map", "0:a", "-c", "copy", "-f", "dash", "-adaptation_sets", "id=0,streams=v id=1,streams=a",
            "split.mpd",
        ], check=True, cwd=cls.fixtures)
        (cls.fixtures / "two.html").write_text(
            '<html><title>Test videos</title><video src="sample.mp4?first"></video>'
            '<video src="sample.mp4?second"></video></html>', encoding="utf-8",
        )
        with ZipFile(cls.fixtures / "sample.zip", "w") as archive:
            archive.writestr("file.txt", "zip payload")
        handler = partial(QuietHandler, directory=cls.fixtures)
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = Thread(target=cls.server.serve_forever, daemon=True)
        thread.start()
        cls.addClassCleanup(cls.server.server_close)
        cls.addClassCleanup(cls.server.shutdown)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    def setUp(self):
        output = TemporaryDirectory()
        self.addCleanup(output.cleanup)
        self.output = Path(output.name)

    def run_job(self, filename, *, selection=None, cancel=False, cancel_after_ms=None):
        job = DownloadJob(f"{self.base}/{filename}", self.output)
        results = {"saved": [], "failed": [], "cancelled": [], "choices": []}
        job.saved.connect(results["saved"].append)
        job.failed.connect(results["failed"].append)
        job.cancelled.connect(lambda: results["cancelled"].append(True))

        def choose(titles):
            results["choices"].extend(titles)
            if cancel:
                job.cancel()
            elif selection is not None:
                job.select(selection)

        job.choices_found.connect(choose)
        loop = QEventLoop()
        job.finished.connect(loop.quit)
        timeout = QTimer(singleShot=True, interval=20000)
        timeout.timeout.connect(loop.quit)
        timeout.start()
        if cancel_after_ms is not None:
            QTimer.singleShot(cancel_after_ms, job.cancel)
        job.start()
        loop.exec()
        if job.isRunning():
            job.cancel()
            job.wait()
            self.fail("Download job did not finish.")
        self.assertFalse(list(self.output.glob(".hizliindir-*")), results)
        return results

    def test_direct_download_keeps_an_existing_file(self):
        first = self.run_job("sample.mp4")
        self.assertEqual(len(first["saved"]), 1, first)
        original = Path(first["saved"][0])
        original.write_bytes(b"existing file")
        second = self.run_job("sample.mp4")
        self.assertEqual(len(second["saved"]), 1, second)
        self.assertEqual(original.read_bytes(), b"existing file")
        self.assertEqual(Path(second["saved"][0]).read_bytes(), (self.fixtures / "sample.mp4").read_bytes())

    def test_split_video_and_audio_are_merged(self):
        result = self.run_job("split.mpd")
        self.assertEqual(len(result["saved"]), 1, result)
        subprocess.run([
            self.ffmpeg, "-v", "error", "-i", result["saved"][0], "-map", "0:v:0", "-map", "0:a:0",
            "-f", "null", "-",
        ], check=True)

    def test_multi_video_page_lets_the_user_choose_one(self):
        result = self.run_job("two.html", selection=1)
        self.assertEqual(len(result["choices"]), 2, result)
        self.assertEqual(len(result["saved"]), 1, result)

    def test_multi_video_page_can_be_cancelled(self):
        result = self.run_job("two.html", cancel=True)
        self.assertEqual(result["cancelled"], [True], result)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_direct_zip_keeps_its_type_and_contents(self):
        result = self.run_job("sample.zip")
        self.assertEqual(len(result["saved"]), 1, result)
        saved = Path(result["saved"][0])
        self.assertEqual(saved.name, "sample.zip")
        with ZipFile(saved) as archive:
            self.assertEqual(archive.read("file.txt"), b"zip payload")

    def test_attachment_uses_server_filename(self):
        result = self.run_job("attachment")
        self.assertEqual(len(result["saved"]), 1, result)
        saved = Path(result["saved"][0])
        self.assertEqual(saved.name, "\u00f6rnek.txt")
        self.assertEqual(saved.read_bytes(), b"sample attachment")

    def test_extensionless_pdf_gets_a_pdf_extension(self):
        result = self.run_job("document")
        self.assertEqual(len(result["saved"]), 1, result)
        saved = Path(result["saved"][0])
        self.assertEqual(saved.name, "document.pdf")
        self.assertEqual(saved.read_bytes(), b"%PDF-1.7\nfixture")

    def test_partial_response_is_not_saved_as_a_complete_file(self):
        result = self.run_job("partial")
        self.assertEqual(result["failed"], ["network"], result)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_slow_direct_transfer_can_be_cancelled_between_network_reads(self):
        started = time.monotonic()
        result = self.run_job("slow.bin", cancel_after_ms=200)
        self.assertEqual(result["cancelled"], [True], result)
        self.assertLess(time.monotonic() - started, 3)
        self.assertEqual(list(self.output.iterdir()), [])


class UrlTests(unittest.TestCase):
    def test_social_posts_go_to_the_video_engine(self):
        for address in (
            "https://x.com/example/status/123",
            "https://mobile.twitter.com/example/status/123/video/1",
            "https://www.instagram.com/reel/abc/",
            "https://www.instagram.com/example/p/abc/",
        ):
            with self.subTest(address=address):
                self.assertTrue(_is_social_video_page(address))

    def test_direct_media_and_unrelated_hosts_keep_the_file_path(self):
        for address in (
            "https://video.twimg.com/video.mp4",
            "https://www.instagram.com/favicon.ico",
            "https://x.com.example.org/status/123",
        ):
            with self.subTest(address=address):
                self.assertFalse(_is_social_video_page(address))

    def test_accepts_one_web_url(self):
        address = "https://example.com/video.mp4?name=%C3%B6"
        self.assertEqual(download_url(f"\n{address}\n"), address)

    def test_rejects_non_web_urls_or_embedded_credentials(self):
        for address in ("file:///C:/file", "https://u:p@example.com/video", "https://invalid:xx/a", "https://a\nhttps://b"):
            with self.subTest(address=address):
                self.assertIsNone(download_url(address))


class ShortcutTests(unittest.TestCase):
    def test_supported_combinations_map_to_windows_hotkeys(self):
        self.assertEqual(Shortcut.parse(DEFAULT_SHORTCUT.portable), DEFAULT_SHORTCUT)
        self.assertEqual(Shortcut.parse("Ctrl+Alt+B"), Shortcut("Ctrl+Alt+B", 0x4003, 0x42))

    def test_rejects_unmodified_reserved_and_multi_step_keys(self):
        for value in ("A", "Shift+A", "Meta+D", "Ctrl+F12", "Ctrl+B, Ctrl+C"):
            with self.subTest(value=value):
                self.assertIsNone(Shortcut.parse(value))
