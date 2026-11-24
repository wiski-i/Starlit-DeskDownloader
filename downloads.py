"""Resolve one download, report progress, and publish a completed local file."""

import errno
import ipaddress
import os
import re
import shutil
import sys
import time
from pathlib import Path
from queue import Empty, Queue
from tempfile import TemporaryDirectory
from threading import Event
from urllib.parse import urlsplit

from PySide6.QtCore import QThread, Signal

from media_convert import ConvertError, convert_media
from media_profiles import DownloadProfile

ROOT = Path(__file__).resolve().parent
MAX_CHOICES = 25


def download_url(value: str) -> str | None:
    """Accept a single HTTP(S) URL without embedded credentials."""
    value = value.strip()
    if (not value or "\\" in value or "\ufeff" in value
            or any(character.isspace() or ord(character) < 32 or ord(character) == 127 for character in value)
            or not re.match(r"^https?://[^/?#]+", value, re.IGNORECASE)):
        return None
    try:
        address = urlsplit(value)
        if (address.scheme in ("http", "https") and address.hostname
                and not any(character in address.netloc for character in "@%<>^`{|}")
                and not address.netloc.endswith(":")):
            if address.netloc.startswith("["):
                ipaddress.IPv6Address(address.hostname)
            port = address.port
            if port is None or port > 0:
                return value
    except ValueError:
        pass
    return None


def _is_social_video_page(url: str) -> bool:
    address = urlsplit(url)
    host = (address.hostname or "").removeprefix("www.").removeprefix("mobile.").removeprefix("m.")
    if host in {"twitter.com", "x.com"}:
        return bool(re.search(r"/(?:status(?:es)?|broadcasts|spaces)/[^/]+", address.path))
    if host in {"instagram.com", "instagr.am"}:
        return bool(re.match(r"/(?:[^/]+/)?(?:p|reels?|tv|share)/[^/]+", address.path))
    return False


def ffmpeg_binary() -> str | None:
    """Find the bundled FFmpeg, a configured installation, or the Python wheel."""
    bundle = ROOT / "tools" / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
    if bundle.is_file():
        return str(bundle)
    configured = os.environ.get("VIDEOINDIR_FFMPEG") or shutil.which("ffmpeg")
    if configured and Path(configured).is_file():
        return configured
    try:
        from imageio_ffmpeg import get_ffmpeg_exe

        return get_ffmpeg_exe()
    except (ImportError, RuntimeError):
        return None


def _js_runtimes() -> dict:
    for name in ("deno", "node"):
        executable = shutil.which(name)
        if executable:
            return {name: {"path": executable}}
    return {}


def _publish(source: Path, folder: Path) -> Path:
    """Publish without overwriting; copy fallback is visible while being written."""
    for index in range(1, 10000):
        name = source.name if index == 1 else f"{source.stem} ({index}){source.suffix}"
        target = folder / name
        try:
            os.link(source, target)
        except FileExistsError:
            continue
        except OSError as error:
            if (error.errno not in {errno.EPERM, errno.EOPNOTSUPP, errno.EXDEV, errno.ENOSYS}
                    and getattr(error, "winerror", None) not in {1, 50, 1314}):
                raise
            try:
                output = target.open("xb")
            except FileExistsError:
                continue
            try:
                with output, source.open("rb") as input_file:
                    shutil.copyfileobj(input_file, output)
            except BaseException:
                target.unlink(missing_ok=True)
                raise
        source.unlink()
        return target
    raise FileExistsError(source.name)


class Cancelled(Exception):
    """An explicit cancellation at a safe point in the download."""


class DownloadProblem(Exception):
    """An error key suitable for showing in the interface."""


class QuietLogger:
    """Silence engine output so it works in a console-free Windows executable."""

    def debug(self, message: str) -> None:
        pass

    def warning(self, message: str) -> None:
        pass

    def error(self, message: str) -> None:
        pass


class DownloadJob(QThread):
    title_changed = Signal(str)
    choices_found = Signal(list)
    progress_changed = Signal(int, float, int)
    processing = Signal()
    saved = Signal(str)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, url: str, folder: Path, parent=None, *, profile: DownloadProfile = DownloadProfile()) -> None:
        super().__init__(parent)
        self.url = url
        self.folder = folder
        self.profile = profile
        self._stop = Event()
        self._selection: Queue[int] = Queue(maxsize=1)
        self._progress: dict[str, float] = {}
        self._parts = 1
        self._last_update = 0.0
        self._files: list[Path] = []

    def cancel(self) -> None:
        self._stop.set()

    def select(self, index: int) -> None:
        if self._selection.empty():
            self._selection.put_nowait(index)

    def _check_cancellation(self) -> None:
        if self._stop.is_set():
            raise Cancelled

    def _download_progress(self, progress: dict) -> None:
        self._check_cancellation()
        state = progress.get("status")
        info = progress.get("info_dict", {})
        parts = info.get("requested_formats") or ()
        self._parts = max(self._parts, len(parts))
        part = str(info.get("format_id") or progress.get("filename", "video"))
        if state == "finished":
            self._progress[part] = 1.0
        elif state == "downloading":
            total = progress.get("total_bytes") or progress.get("total_bytes_estimate")
            if total:
                ratio = min(1.0, progress.get("downloaded_bytes", 0) / total)
                self._progress[part] = max(self._progress.get(part, 0.0), ratio)
        now = time.monotonic()
        if now - self._last_update >= 0.10 or state == "finished":
            percentage = min(99, int(100 * sum(self._progress.values()) / self._parts))
            self.progress_changed.emit(
                percentage if self._progress else -1,
                progress.get("speed") or 0.0,
                progress.get("eta") if progress.get("eta") is not None else -1,
            )
            self._last_update = now

    def _postprocess(self, progress: dict) -> None:
        self._check_cancellation()
        if progress.get("status") == "started":
            self.processing.emit()

    def _options(self, stage: Path) -> dict:
        ffmpeg = ffmpeg_binary()
        selector = "bv*+ba/b" if ffmpeg else "b"
        if self.profile.output.group == "audio":
            selector = "ba/b"
        options = {
            "logger": QuietLogger(),
            "quiet": True,
            "noprogress": True,
            "no_color": True,
            "noplaylist": True,
            "extract_flat": "in_playlist",
            "playlistend": MAX_CHOICES + 1,
            "windowsfilenames": True,
            "outtmpl": str(stage / "%(title).180B [%(id).22B].%(ext)s"),
            "socket_timeout": 8,
            "retries": 2,
            "fragment_retries": 2,
            "skip_unavailable_fragments": False,
            "format": selector,
            "ffmpeg_location": ffmpeg,
            "js_runtimes": _js_runtimes(),
            "progress_hooks": [self._download_progress],
            "postprocessor_hooks": [self._postprocess],
            "post_hooks": [lambda path: self._files.append(Path(path))],
        }
        if self.profile.resolution is not None:
            options["format_sort"] = [f"res:{self.profile.resolution}"]
            options["format_sort_force"] = True
        return options

    def _pick_video(self, info: dict) -> dict:
        if "entries" not in info:
            return info
        entries = [entry for entry in info["entries"] if entry and (
            entry.get("url") or entry.get("webpage_url") or entry.get("formats"))][:MAX_CHOICES]
        if len(entries) <= 1:
            if entries:
                return entries[0]
            raise DownloadProblem("unsupported")
        self.choices_found.emit([str(entry.get("title") or "") for entry in entries])
        while True:
            self._check_cancellation()
            try:
                index = self._selection.get(timeout=0.1)
            except Empty:
                continue
            if 0 <= index < len(entries):
                return entries[index]

    def _download(self, stage: Path) -> Path:
        # The tray and direct file transfers have no need for the video engine.
        from yt_dlp import YoutubeDL
        from yt_dlp.networking.exceptions import RequestError
        from yt_dlp.utils import DownloadError

        try:
            with YoutubeDL(self._options(stage)) as engine:
                self._check_cancellation()
                info = engine.extract_info(self.url, download=False)
                self._check_cancellation()
                if not info:
                    raise DownloadProblem("unsupported")
                selected = self._pick_video(info)
                self._check_cancellation()
                self.title_changed.emit(str(selected.get("title") or ""))
                if selected.get("_type") in ("url", "url_transparent"):
                    selected = engine.process_ie_result(selected, download=False)
                if not selected or "entries" in selected:
                    raise DownloadProblem("unsupported")
                if selected.get("vcodec") == "none" and self.profile.output.group != "audio":
                    raise DownloadProblem("media_stream_missing" if self.profile.output.video else "unsupported")
                self.title_changed.emit(str(selected.get("title") or ""))
                self._parts = len(selected.get("requested_formats") or ()) or 1
                engine.process_ie_result(selected, download=True)
                self._check_cancellation()
        except (DownloadError, RequestError) as error:
            raise DownloadProblem(_video_error_key(str(error), isinstance(error, RequestError))) from error
        if len(self._files) != 1 or not self._files[0].is_file():
            raise DownloadProblem("engine_error")
        return self._files[0]

    def run(self) -> None:
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            with TemporaryDirectory(prefix=".hizliindir-", dir=self.folder) as directory:
                stage = Path(directory)
                direct = None
                if not _is_social_video_page(self.url):
                    from direct_files import download_direct

                    direct = download_direct(
                        self.url, stage, self._check_cancellation, self.title_changed.emit, self.progress_changed.emit,
                    )
                convert = self.profile.format_id != "original" and (direct is None or direct.is_media)
                ffmpeg = ffmpeg_binary() if convert else None
                if convert and not ffmpeg:
                    raise DownloadProblem("converter_missing")
                if direct is None:
                    source = self._download(stage)
                else:
                    source = direct.path
                if ffmpeg:
                    self.processing.emit()
                    source = convert_media(source, self.profile, ffmpeg, self._check_cancellation)
                self._check_cancellation()
                # Publishing is the commit point. Cancellation after the move keeps the file.
                target = _publish(source, self.folder)
            self.saved.emit(str(target))
        except Cancelled:
            self.cancelled.emit()
        except Exception as error:
            if self._stop.is_set():
                self.cancelled.emit()
            else:
                self.failed.emit(_error_key(error))


def _error_key(error: Exception) -> str:
    if isinstance(error, (DownloadProblem, ConvertError)):
        return str(error)
    from direct_files import DirectDownloadError

    if isinstance(error, DirectDownloadError):
        return "network"
    if isinstance(error, OSError):
        return "write_error"
    if not getattr(sys, "frozen", False) and sys.stderr is not None:
        print(f"Download failed ({type(error).__name__}).", file=sys.stderr)
    return "engine_error"


def _video_error_key(message: str, request_failed: bool) -> str:
    message = message.lower()
    if re.search(r"http error 429|too many requests|rate[- ]limit exceeded", message):
        return "rate_limited"
    if re.search(r"drm|forbidden|sign in|private video|login required|http error (401|403)", message):
        return "protected"
    if re.search(r"unsupported url|no video|no formats|no downloadable", message):
        return "unsupported"
    if re.search(r"ffmpeg|ffprobe|merg(?:e|ing)", message):
        return "merge_error"
    if re.search(r"permission denied|no space|unable to open for writing", message):
        return "write_error"
    if request_failed or re.search(r"timed out|connection|http error|name resolution", message):
        return "network"
    return "engine_error"
