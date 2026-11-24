"""Packaging checks using the exact FFmpeg binary distributed by imageio."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

import imageio_ffmpeg


class PackagingTests(unittest.TestCase):
    def test_third_party_notice_identifies_the_shipped_ffmpeg(self):
        binary = Path(imageio_ffmpeg.get_ffmpeg_exe())
        with TemporaryDirectory() as folder:
            notice = Path(folder) / "THIRD-PARTY.txt"
            process = subprocess.run(
                [sys.executable, "third_party.py", str(binary), str(notice)],
                capture_output=True, text=True, timeout=30,
                cwd=Path(__file__).parent,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            text = notice.read_text(encoding="utf-8")
        self.assertIn(hashlib.sha256(binary.read_bytes()).hexdigest(), text)
        self.assertIn("ffmpeg version", text)
        self.assertIn(imageio_ffmpeg.__version__, text)
        self.assertIn("https://github.com/imageio/imageio-ffmpeg", text)
        self.assertIn("https://ffmpeg.org/legal.html", text)

    def test_custom_ffmpeg_notice_does_not_claim_imageio_distribution(self):
        from third_party import write_notice
        with TemporaryDirectory() as folder:
            binary = Path(folder) / Path(imageio_ffmpeg.get_ffmpeg_exe()).name
            shutil.copy2(imageio_ffmpeg.get_ffmpeg_exe(), binary)
            notice = Path(folder) / "THIRD-PARTY.txt"
            write_notice(binary, notice)
            text = notice.read_text(encoding="utf-8")
        self.assertIn("user-supplied FFmpeg", text)
        self.assertNotIn("Binary distribution: https://github.com/imageio", text)

    def test_mac_artifact_names_require_known_architecture(self):
        from build_macos import artifact_name
        self.assertEqual(artifact_name("0.2.2", "arm64"), "Starlit-DeskDownloader-0.2.2-macos-arm64.dmg")
        self.assertEqual(artifact_name("0.2.2", "x86_64"), "Starlit-DeskDownloader-0.2.2-macos-x64.dmg")
        with self.assertRaises(ValueError):
            artifact_name("0.2.2", "unknown")


if __name__ == "__main__":
    unittest.main()
