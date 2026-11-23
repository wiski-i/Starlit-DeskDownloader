"""Convert a staged media file, without publishing partial or cancelled output."""

import os
import subprocess
from pathlib import Path
from tempfile import TemporaryFile, mkdtemp
from typing import Callable

from media_profiles import DownloadProfile


MEDIA_SUFFIXES = frozenset({
    ".3g2", ".3gp", ".aac", ".aif", ".aiff", ".avi", ".flac", ".flv", ".m4a", ".m4v",
    ".mka", ".mkv", ".mov", ".mp3", ".mp4", ".mpeg", ".mpg", ".ogg", ".ogv",
    ".opus", ".ts", ".wav", ".webm", ".wma", ".wmv",
})
INPUT_FORMATS = (
    "mov,matroska,webm,avi,flv,mp3,wav,flac,ogg,aac,mpegts,asf,mpeg,"
    "mpegvideo,aiff"
)


class ConvertError(Exception):
    """An error with a message key suitable for the app."""


def _audio_args(profile: DownloadProfile) -> list[str]:
    if profile.format_id == "wav":
        return ["-c:a", f"pcm_s{profile.quality}le"]
    if profile.format_id == "flac":
        return ["-c:a", "flac", "-compression_level", profile.quality]
    return ["-c:a", profile.output.audio, "-b:a", f"{profile.quality}k"]


def _video_args(profile: DownloadProfile) -> list[str]:
    scheme = profile.output
    args = ["-c:v", scheme.video, "-pix_fmt", "yuv420p", "-c:a", scheme.audio, "-b:a", "160k"]
    if scheme.video == "libx264":
        args += ["-preset", "fast", "-crf", "20"]
    elif scheme.video == "libvpx-vp9":
        args += ["-deadline", "good", "-cpu-used", "3", "-crf", "30", "-b:v", "0"]
    else:
        args += ["-q:v", "5"]
    if profile.format_id == "3gp":
        args += ["-ac", "1", "-ar", "22050", "-b:a", "48k"]
    elif profile.format_id in ("flv", "avi"):
        args += ["-ar", "44100", "-ac", "2"]

    # Treat the shorter dimension as the resolution for portrait videos too.
    # Round down for encoders that need even dimensions, without upscaling.
    cap = profile.resolution
    if cap is not None:
        w = f"max(2,trunc(min(iw,{cap})/2)*2)"
        h = f"max(2,trunc(min(ih,{cap})/2)*2)"
        args += ["-vf", f"scale=w='if(gte(iw,ih),-2,{w})':h='if(gte(iw,ih),{h},-2)'"]
    else:
        args += ["-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2"]
    if profile.format_id in ("mp4", "mov"):
        args += ["-movflags", "+faststart"]
    return args


def _run_ffmpeg(command: list[str], check_cancel: Callable[[], None]) -> tuple[bool, str]:
    check_cancel()
    with TemporaryFile() as errors:
        with subprocess.Popen(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=errors,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ) as process:
            try:
                while True:
                    try:
                        success = process.wait(timeout=0.1) == 0
                        break
                    except subprocess.TimeoutExpired:
                        check_cancel()
            finally:
                if process.poll() is None:
                    process.kill()
        errors.seek(max(0, errors.seek(0, os.SEEK_END) - 8192))
        return success, errors.read().decode("utf-8", errors="replace")


def convert_media(source: Path, profile: DownloadProfile, ffmpeg: str, check_cancel: Callable[[], None]) -> Path:
    target = Path(mkdtemp(prefix="output-", dir=source.parent)) / f"{source.stem}.{profile.format_id}"
    args = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
        "-protocol_whitelist", "file", "-format_whitelist", INPUT_FORMATS, "-i", str(source),
    ]
    outfile = ["-f", profile.output.muxer, str(target)]
    if profile.output.video:
        args += ["-map", "0:V:0", "-map", "0:a:0?"]
        if profile.quality == "best":
            success, _ = _run_ffmpeg([*args, "-c", "copy", *outfile], check_cancel)
            if success and target.is_file() and target.stat().st_size:
                return target
        encoding = _video_args(profile)
    else:
        args += ["-map", "0:a:0"]
        encoding = _audio_args(profile)

    success, errors = _run_ffmpeg([*args, *encoding, *outfile], check_cancel)
    if not success or not target.is_file() or not target.stat().st_size:
        if "matches no streams" in errors.lower():
            raise ConvertError("media_stream_missing")
        if any(problem in errors.lower() for problem in ("permission denied", "no space left", "disk full")):
            raise ConvertError("write_error")
        raise ConvertError("conversion_error")
    return target
