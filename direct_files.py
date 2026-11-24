"""Stream downloadable HTTP responses into an existing staging directory."""

import mimetypes
import os
import re
import time
from dataclasses import dataclass
from http.client import HTTPException
from pathlib import Path
from typing import Callable
from urllib.error import URLError
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen

from media_convert import MEDIA_SUFFIXES


PAGE_TYPES = {"text/html", "application/xhtml+xml"}
STREAM_TYPES = {
    "application/dash+xml", "application/vnd.apple.mpegurl", "application/x-mpegurl",
    "audio/mpegurl", "audio/x-mpegurl",
}
GENERIC_TYPES = {"application/octet-stream", "binary/octet-stream", "text/plain"}
CHUNK_SIZE = 128 * 1024
SNIFF_BYTES = 1024


class DirectDownloadError(Exception):
    """The connection failed after a direct transfer had started."""


@dataclass(frozen=True)
class DirectDownload:
    path: Path
    is_media: bool


def _file_name(headers, final_url: str, media_type: str) -> str:
    url_name = unquote(urlsplit(final_url).path.rstrip("/").rsplit("/", 1)[-1])
    server_name = headers.get_filename()
    name = server_name or url_name
    name = re.split(r"[/\\]", name)[-1]
    name = re.sub(r'[<>:"|?*\x00-\x1f]', "_", name).strip(" .")
    if not name or name in (".", ".."):
        name = "download" + (mimetypes.guess_extension(media_type) or "")
    elif not server_name and not Path(name).suffix:
        name += mimetypes.guess_extension(media_type) or ""
    is_reserved = getattr(os.path, "isreserved", None)
    reserved = is_reserved(name) if is_reserved else Path(name).is_reserved()
    if reserved:
        name = "_" + name
    suffix = Path(name).suffix[:18]
    # Leave room for a numbered collision suffix within the 255-byte component limit.
    budget = min(200, 240 - len(suffix.encode("utf-8")))
    stem = Path(name).stem[:110].encode("utf-8")[:budget].decode("utf-8", errors="ignore")
    return stem + suffix


def _read(response, size: int) -> bytes:
    try:
        return response.read1(size)
    except (OSError, HTTPException) as error:
        raise DirectDownloadError from error


def _sniff_prefix(response, check_cancel: Callable[[], None]) -> bytearray:
    data = bytearray()
    while len(data) < SNIFF_BYTES:
        check_cancel()
        block = _read(response, SNIFF_BYTES - len(data))
        if not block:
            break
        data.extend(block)
    return data


def download_direct(
    url: str,
    stage: Path,
    check_cancel: Callable[[], None],
    title_changed: Callable[[str], None],
    progress: Callable[[int, float, int], None],
) -> DirectDownload | None:
    """Save a non-page response. Let the video engine handle pages and manifests."""
    request = Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept-Encoding": "identity"})
    try:
        response = urlopen(request, timeout=8)
    except (URLError, OSError, HTTPException):
        return None

    with response:
        check_cancel()
        if response.status == 206:
            raise DirectDownloadError
        final_url = response.geturl()
        if urlsplit(final_url).scheme not in ("http", "https"):
            return None
        headers = response.headers
        media_type = headers.get_content_type()
        attachment = headers.get_content_disposition() == "attachment"
        suffix = Path(urlsplit(final_url).path).suffix.lower()
        if not attachment and (media_type in PAGE_TYPES | STREAM_TYPES or suffix in {".mpd", ".m3u8"}):
            return None

        data = None
        if not attachment and media_type in GENERIC_TYPES:
            data = _sniff_prefix(response, check_cancel)
            prefix = bytes(data).removeprefix(b"\xef\xbb\xbf").lstrip().lower()
            if prefix.startswith((b"<!doctype html", b"<html", b"#extm3u", b"<mpd")) or (
                prefix.startswith(b"<?xml") and b"<mpd" in prefix
            ):
                return None
        check_cancel()
        destination = stage / _file_name(headers, final_url, media_type)
        is_media = (
            media_type.startswith(("audio/", "video/")) or media_type == "application/ogg"
            or (media_type in GENERIC_TYPES and destination.suffix.casefold() in MEDIA_SUFFIXES)
        )
        title_changed(destination.name)
        size_header = headers.get("Content-Length", "")
        total = int(size_header) if size_header.isdecimal() else None
        started = last_update = time.monotonic()
        written = 0
        with destination.open("xb") as output:
            progress(0 if total else -1, 0.0, -1)
            if data is None:
                data = _read(response, CHUNK_SIZE)
            while data:
                check_cancel()
                output.write(data)
                written += len(data)
                now = time.monotonic()
                if now - last_update >= 0.10:
                    speed = written / max(0.01, now - started)
                    percent = min(99, int(100 * written / total)) if total else -1
                    eta = max(0, round((total - written) / speed)) if total and speed else -1
                    progress(percent, speed, eta)
                    last_update = now
                data = _read(response, CHUNK_SIZE)
        if total is not None and written != total:
            raise DirectDownloadError
        return DirectDownload(destination, is_media)
