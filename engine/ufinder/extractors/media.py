"""Image, audio and video extractors. OCR and speech run on the NAS."""
from __future__ import annotations

import io
import json
import os
import subprocess
import tempfile
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from PIL import ExifTags, Image, ImageOps

from . import Extracted, Piece, Plugin, register

MAX_SIDE = 1024
THUMB_SIDE = 420
MAX_FRAMES = 12
WHISPER_MODEL = os.environ.get("UFINDER_WHISPER_MODEL", "base")
OCR_MIN_SCORE = 0.5


@lru_cache(maxsize=1)
def _ocr():
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


@lru_cache(maxsize=1)
def _whisper():
    from faster_whisper import WhisperModel

    root = os.environ.get("UFINDER_WHISPER_DIR")
    source = os.path.join(root, WHISPER_MODEL) if root else WHISPER_MODEL
    return WhisperModel(source, device="cpu", compute_type="int8", cpu_threads=4)


def ocr_image(img: Image.Image) -> str:
    import numpy as np

    arr = np.array(img.convert("RGB"))[:, :, ::-1]
    result, _ = _ocr()(arr)
    if not result:
        return ""
    return " ".join(t for _box, t, score in result if float(score) >= OCR_MIN_SCORE)


def _jpeg(img: Image.Image, side: int, quality: int = 85) -> bytes:
    im = img.copy()
    im.thumbnail((side, side))
    buf = io.BytesIO()
    im.convert("RGB").save(buf, "JPEG", quality=quality)
    return buf.getvalue()


def _exif(img: Image.Image) -> dict:
    out = {}
    exif = img.getexif()
    if not exif:
        return out
    tags = {ExifTags.TAGS.get(k, k): v for k, v in exif.items()}
    tags.update({ExifTags.TAGS.get(k, k): v for k, v in exif.get_ifd(0x8769).items()})
    if tags.get("Model"):
        out["camera"] = str(tags["Model"]).strip()
    stamp = tags.get("DateTimeOriginal") or tags.get("DateTime")
    if stamp:
        try:
            out["taken"] = datetime.strptime(str(stamp), "%Y:%m:%d %H:%M:%S").timestamp()
        except ValueError:
            pass
    return out


def _image(path: Path) -> Extracted:
    from .documents import find_refs

    with Image.open(path) as raw:
        img = ImageOps.exif_transpose(raw).convert("RGB")
        props = _exif(raw)
    props.update({"width": img.width, "height": img.height})
    pieces = [Piece("image", locator="image", image=_jpeg(img, MAX_SIDE))]
    text = ocr_image(img)
    refs = []
    if text:
        pieces.append(Piece("ocr", text, "image text"))
        refs = find_refs(text)
    return Extracted(pieces, props, refs, _jpeg(img, THUMB_SIDE, 78))


def _clock(seconds: float) -> str:
    return f"{int(seconds // 60):02d}:{int(seconds % 60):02d}"


def _pcm(path: Path):
    """Decode with FFmpeg, which is already here, to 16 kHz mono samples."""
    import numpy as np

    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
        capture_output=True, timeout=3600, check=True,
    )
    return np.frombuffer(out.stdout, dtype=np.float32)


def _transcribe(path: Path) -> tuple[list[Piece], str, str]:
    segments, info = _whisper().transcribe(_pcm(path), vad_filter=True, beam_size=1)
    pieces, buf, start, full = [], [], None, []
    for seg in segments:
        start = seg.start if start is None else start
        buf.append(seg.text.strip())
        full.append(seg.text.strip())
        if sum(len(x) for x in buf) > 500:
            pieces.append(Piece("transcript", " ".join(buf), _clock(start)))
            buf, start = [], None
    if buf:
        pieces.append(Piece("transcript", " ".join(buf), _clock(start or 0)))
    return pieces, " ".join(full), info.language


def _duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, timeout=60,
    )
    try:
        return float(json.loads(out.stdout)["format"]["duration"])
    except (KeyError, ValueError, json.JSONDecodeError):
        return 0.0


def _has_audio(path: Path) -> bool:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, timeout=60,
    )
    return "audio" in out.stdout


def _audio(path: Path) -> Extracted:
    from .documents import find_refs

    pieces, text, lang = _transcribe(path)
    return Extracted(pieces, {"duration": _duration(path), "language": lang}, find_refs(text))


def _video(path: Path) -> Extracted:
    from .documents import find_refs

    duration = _duration(path)
    pieces: list[Piece] = []
    thumb = None
    step = max(duration / MAX_FRAMES, 2.0)
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(path), "-vf", f"fps=1/{step:.3f}", "-frames:v", str(MAX_FRAMES),
             os.path.join(tmp, "f%03d.jpg")],
            capture_output=True, timeout=600,
        )
        seen_text: set[str] = set()
        for i, f in enumerate(sorted(Path(tmp).glob("f*.jpg"))):
            with Image.open(f) as im:
                img = im.convert("RGB")
            stamp = _clock(i * step)
            pieces.append(Piece("frame", locator=stamp, image=_jpeg(img, 768)))
            if thumb is None:
                thumb = _jpeg(img, THUMB_SIDE, 78)
            text = ocr_image(img)
            if text and text not in seen_text:
                seen_text.add(text)
                pieces.append(Piece("ocr", text, stamp))
    transcript, lang = [], ""
    if _has_audio(path):
        transcript, _text, lang = _transcribe(path)  # a real failure must surface, not vanish
    pieces += transcript
    refs = find_refs(" ".join(p.text for p in pieces if p.text))
    return Extracted(pieces, {"duration": duration, "language": lang}, refs, thumb)


register(Plugin("image", 1, "image", (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"), _image))
register(Plugin("audio", 1, "audio", (".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aiff"), _audio))
register(Plugin("video", 3, "video", (".mp4", ".mov", ".mkv", ".webm", ".avi"), _video))
