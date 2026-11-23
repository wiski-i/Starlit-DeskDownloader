"""Output formats and their quality choices for both the UI and download engine."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Quality:
    key: str
    label: str


@dataclass(frozen=True)
class OutputFormat:
    label: str
    group: str
    qualities: tuple[Quality, ...]
    default: str
    muxer: str = ""
    audio: str = ""
    video: str = ""


def _numbered(values: tuple[int, ...], unit: str) -> tuple[Quality, ...]:
    return tuple(Quality(str(value), f"{value}{unit}") for value in values)


BEST = Quality("best", "En iyi mevcut kalite")
VIDEO_QUALITIES = (BEST, *_numbered((480, 720, 1080, 1440, 2160), "p’ye kadar"))
LEGACY_QUALITIES = _numbered((360, 480, 720), "p’ye kadar")
AAC_QUALITIES = _numbered((128, 192, 256), " kbps")

FORMATS = {
    "original": OutputFormat("Orijinal", "", (
        BEST, *_numbered((720, 1080), "p öncelikli"),
    ), "best"),
    "mp4": OutputFormat("MP4", "video", VIDEO_QUALITIES, "1080", "mp4", "aac", "libx264"),
    "mkv": OutputFormat("MKV", "video", VIDEO_QUALITIES, "1080", "matroska", "aac", "libx264"),
    "webm": OutputFormat("WebM", "video", VIDEO_QUALITIES, "1080", "webm", "libopus", "libvpx-vp9"),
    "mov": OutputFormat("MOV", "video", VIDEO_QUALITIES, "1080", "mov", "aac", "libx264"),
    "mp3": OutputFormat("MP3", "audio", _numbered((128, 192, 320), " kbps"), "192", "mp3", "libmp3lame"),
    "m4a": OutputFormat("M4A", "audio", AAC_QUALITIES, "192", "ipod", "aac"),
    "opus": OutputFormat("Opus", "audio", _numbered((64, 96, 128, 160), " kbps"), "128", "opus", "libopus"),
    "wav": OutputFormat("WAV", "audio", _numbered((16, 24, 32), " bit PCM"), "16", "wav"),
    "flac": OutputFormat("FLAC", "audio", (
        Quality("0", "Hızlı sıkıştırma (0)"),
        Quality("5", "Dengeli sıkıştırma (5)"),
        Quality("8", "Yüksek sıkıştırma (8)"),
    ), "5", "flac", "flac"),
    "aac": OutputFormat("AAC", "audio", AAC_QUALITIES, "192", "adts", "aac"),
    "ogg": OutputFormat("Ogg Vorbis", "audio", _numbered((96, 160, 224), " kbps"), "160", "ogg", "libvorbis"),
    "avi": OutputFormat("AVI", "legacy", LEGACY_QUALITIES, "480", "avi", "libmp3lame", "mpeg4"),
    "3gp": OutputFormat("3GP", "legacy", _numbered((144, 240, 360), "p’ye kadar"), "240", "3gp", "aac", "mpeg4"),
    "flv": OutputFormat("FLV", "legacy", LEGACY_QUALITIES, "480", "flv", "libmp3lame", "flv"),
}


@dataclass(frozen=True)
class DownloadProfile:
    format_id: str = "original"
    quality: str = "best"

    @classmethod
    def from_setting(cls, format_id: str, quality: str) -> "DownloadProfile":
        if format_id not in FORMATS:
            return cls()
        output = FORMATS[format_id]
        if not any(entry.key == quality for entry in output.qualities):
            quality = output.default
        return cls(format_id, quality)

    @classmethod
    def read_settings(cls, settings, format_id: str | None = None) -> "DownloadProfile":
        if format_id is None:
            format_id = settings.value("downloadFormat", "original", type=str)
        quality = settings.value(f"downloadQuality/{format_id}", "", type=str)
        return cls.from_setting(format_id, quality)

    def save_settings(self, settings) -> None:
        settings.setValue("downloadFormat", self.format_id)
        settings.setValue(f"downloadQuality/{self.format_id}", self.quality)

    @property
    def output(self) -> OutputFormat:
        return FORMATS[self.format_id]

    @property
    def resolution(self) -> int | None:
        if self.output.group != "audio" and self.quality != "best":
            return int(self.quality)
        return None


def browser_profiles(settings) -> dict:
    """Expose the desktop catalog and defaults without starting a download."""
    selected = DownloadProfile.read_settings(settings)
    return {
        "status": "profiles",
        "selected": {"format": selected.format_id, "quality": selected.quality},
        "formats": [
            {
                "key": key,
                "label": output.label,
                "group": output.group,
                "quality": DownloadProfile.read_settings(settings, key).quality,
                "qualities": [{"key": quality.key, "label": quality.label} for quality in output.qualities],
            }
            for key, output in FORMATS.items()
        ],
    }
