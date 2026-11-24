"""Regression checks for safe publishing and direct download boundaries."""
import errno
from concurrent.futures import ThreadPoolExecutor
from email.message import Message
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import os

from direct_files import _file_name
from downloads import _publish, download_url, ffmpeg_binary


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.output = self.root / 'saved'
        self.output.mkdir()
        self.source = self.root / 'video.mp4'
        self.source.write_bytes(b'new video')

    def test_racing_publisher_cannot_replace_an_existing_file(self):
        target = self.output / self.source.name
        original_link = os.link
        first = True
        def race_link(source, destination):
            nonlocal first
            if first:
                first = False
                Path(destination).write_bytes(b'other download')
            return original_link(source, destination)
        def posix_rename(source, destination):
            Path(destination).write_bytes(b'other download')
            return source.replace(destination)
        with patch('downloads.os.link', side_effect=race_link), patch.object(Path, 'rename', posix_rename):
            result = _publish(self.source, self.output)
        self.assertEqual(target.read_bytes(), b'other download')
        self.assertEqual(result.name, 'video (2).mp4')
        self.assertEqual(result.read_bytes(), b'new video')
        self.assertFalse(self.source.exists())

    def test_concurrent_publish_keeps_every_payload(self):
        sources = []
        for index in range(12):
            directory = self.root / str(index)
            directory.mkdir()
            source = directory / 'same.mp4'
            source.write_bytes(str(index).encode())
            sources.append(source)
        with ThreadPoolExecutor(max_workers=12) as executor:
            results = list(executor.map(lambda source: _publish(source, self.output), sources))
        self.assertEqual(len(set(results)), 12)
        self.assertEqual({result.read_bytes() for result in results}, {str(i).encode() for i in range(12)})

    def test_exclusive_copy_fallback_preserves_existing_file(self):
        (self.output / 'video.mp4').write_bytes(b'existing')
        with patch('downloads.os.link', side_effect=OSError(errno.EXDEV, 'no hardlinks')), patch.object(Path, 'rename', side_effect=OSError(errno.EXDEV, 'no rename')):
            result = _publish(self.source, self.output)
        self.assertEqual((self.output / 'video.mp4').read_bytes(), b'existing')
        self.assertEqual(result.read_bytes(), b'new video')
        self.assertFalse(self.source.exists())

    def test_windows_unsupported_hardlink_uses_exclusive_copy(self):
        error = OSError(errno.EINVAL, "Windows filesystem does not support links")
        error.winerror = 50
        with patch("downloads.os.link", side_effect=error):
            result = _publish(self.source, self.output)
        self.assertEqual(result.read_bytes(), b"new video")
        self.assertFalse(self.source.exists())

    def test_failed_copy_removes_only_its_partial_destination(self):
        def fail_copy(source, output):
            output.write(b'partial')
            raise OSError(errno.ENOSPC, 'disk full')
        with patch('downloads.os.link', side_effect=OSError(errno.EXDEV, 'no hardlinks')), patch.object(Path, 'rename', side_effect=OSError(errno.EXDEV, 'no rename')), patch('downloads.shutil.copyfileobj', side_effect=fail_copy):
            with self.assertRaises(OSError) as caught:
                _publish(self.source, self.output)
        self.assertEqual(caught.exception.errno, errno.ENOSPC)
        self.assertEqual(list(self.output.iterdir()), [])
        self.assertEqual(self.source.read_bytes(), b'new video')


class BoundaryTests(unittest.TestCase):
    def test_unicode_name_including_suffix_fits_filesystem_and_numbering(self):
        for name in ('\U0001f680' * 110 + '.mp4', '\u754c' * 110 + '.' + '\U0001f680' * 18):
            headers = Message()
            headers.add_header('Content-Disposition', 'attachment', filename=name)
            result = _file_name(headers, 'https://example.com/file', 'application/octet-stream')
            self.assertLessEqual(len(result.encode('utf-8')), 240)
            with TemporaryDirectory() as directory:
                path = Path(directory) / result
                path.write_bytes(b'payload')
                self.assertEqual(path.read_bytes(), b'payload')

    def test_rejects_parser_normalization_and_control_characters(self):
        for address in ('https://example.com\\@evil.com/x', 'https://example.com/\x7f', 'https:///example.com/x', 'https://@example.com/x', 'https://example.com:/x', 'https://example.com:0/x'):
            with self.subTest(address=address):
                self.assertIsNone(download_url(address))

    def test_video_template_limits_utf8_title_and_id_bytes(self):
        from downloads import DownloadJob
        from yt_dlp import YoutubeDL
        with TemporaryDirectory() as directory:
            folder = Path(directory)
            job = DownloadJob("https://example.com/video", folder)
            with YoutubeDL(job._options(folder)) as engine:
                name = Path(engine.prepare_filename({"title": chr(0x1f680) * 105, "id": chr(0x754c) * 22, "ext": "mp4"})).name
            self.assertLessEqual(len(name.encode("utf-8")), 240)
            target = folder / name
            target.write_bytes(b"video")
            self.assertEqual(target.read_bytes(), b"video")

    def test_bundled_ffmpeg_uses_platform_name(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'tools').mkdir()
            for platform, name in (('darwin', 'ffmpeg'), ('linux', 'ffmpeg'), ('win32', 'ffmpeg.exe')):
                with self.subTest(platform=platform):
                    binary = root / 'tools' / name
                    binary.touch()
                    with patch('downloads.ROOT', root), patch('downloads.sys.platform', platform):
                        self.assertEqual(ffmpeg_binary(), str(binary))
                    binary.unlink()
