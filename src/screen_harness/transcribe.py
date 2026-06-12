"""Transcription pipeline contracts and local MVP provider."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .admin import ffprobe_binary
from .metadata import update_ai_metadata, write_text_atomic
from .timeline import local_now


@dataclass(frozen=True)
class TranscriptSegment:
    start: float
    end: float
    text: str

    def to_dict(self) -> dict:
        return {"start": round(self.start, 3), "end": round(self.end, 3), "text": self.text}


@dataclass(frozen=True)
class AudioExtractionResult:
    raw_video: Path
    audio_path: Path
    audio_stream_found: bool
    extracted: bool
    reason: str | None = None
    command: list[str] | None = None
    output: str | None = None


@dataclass(frozen=True)
class TranscriptionOutputs:
    transcript_srt: Path
    transcript_json: Path
    audio: Path | None
    segment_count: int


@dataclass(frozen=True)
class ProviderTranscript:
    source: Path | None
    segments: list[TranscriptSegment]


class TranscriptionProvider(Protocol):
    name: str
    model: str

    def transcribe(self, recording_dir: Path, audio: AudioExtractionResult) -> ProviderTranscript:
        ...


class ManualTranscriptProvider:
    name = "manual"
    model = "manual-transcript-v1"

    def transcribe(self, recording_dir: Path, audio: AudioExtractionResult) -> ProviderTranscript:
        source = _manual_transcript_path(recording_dir)
        if source is None:
            return ProviderTranscript(source=None, segments=[])
        return ProviderTranscript(source=source, segments=parse_manual_transcript(source.read_text()))


PROVIDERS: dict[str, TranscriptionProvider] = {
    "manual": ManualTranscriptProvider(),
}


_TIME_RE = r"(?P<start>(?:\d{1,2}:)?\d{1,2}:\d{2}(?:[,.]\d{1,3})?|\d+(?:[,.]\d+)?)"
_TIMED_LINE = re.compile(
    rf"^\s*\[?{_TIME_RE}\s*(?:-->|-)\s*(?P<end>(?:\d{{1,2}}:)?\d{{1,2}}:\d{{2}}(?:[,.]\d{{1,3}})?|\d+(?:[,.]\d+)?)\]?\s*(?P<text>.+?)\s*$"
)


def extract_audio(recording_dir: Path, *, ffmpeg_path: str | None = None) -> AudioExtractionResult:
    recording_dir = Path(recording_dir)
    raw = recording_dir / "raw.mp4"
    audio = recording_dir / "audio.wav"
    if not raw.exists():
        return AudioExtractionResult(raw_video=raw, audio_path=audio, audio_stream_found=False, extracted=False, reason="raw.mp4 missing")

    probe = _probe_audio(raw)
    if not probe[0]:
        return AudioExtractionResult(raw_video=raw, audio_path=audio, audio_stream_found=False, extracted=False, reason=probe[1])

    binary = ffmpeg_path or shutil.which("ffmpeg") or "ffmpeg"
    command = [binary, "-y", "-i", str(raw), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(audio)]
    try:
        result = subprocess.run(command, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except OSError as exc:
        return AudioExtractionResult(
            raw_video=raw,
            audio_path=audio,
            audio_stream_found=True,
            extracted=False,
            reason=str(exc),
            command=command,
        )
    return AudioExtractionResult(
        raw_video=raw,
        audio_path=audio,
        audio_stream_found=True,
        extracted=result.returncode == 0,
        reason=None if result.returncode == 0 else f"ffmpeg exited {result.returncode}",
        command=command,
        output=result.stdout,
    )


def transcribe_recording(recording_dir: Path, *, provider_name: str = "manual") -> TranscriptionOutputs:
    recording_dir = Path(recording_dir)
    provider = PROVIDERS.get(provider_name)
    if provider is None:
        raise ValueError(f"unknown transcription provider: {provider_name}")

    audio = extract_audio(recording_dir)
    provider_result = provider.transcribe(recording_dir, audio)
    transcript_srt = recording_dir / "transcript.srt"
    transcript_json = recording_dir / "transcript.json"
    write_text_atomic(transcript_srt, srt_text(provider_result.segments))

    payload = {
        "recording_id": recording_dir.name,
        "created_at": local_now().isoformat(),
        "provider": provider.name,
        "model": provider.model,
        "source": _relative(provider_result.source, recording_dir),
        "audio": _relative(audio.audio_path, recording_dir) if audio.extracted else None,
        "audio_extraction": _audio_payload(audio, recording_dir),
        "segments": [segment.to_dict() for segment in provider_result.segments],
    }
    write_text_atomic(transcript_json, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    update_ai_metadata(
        recording_dir,
        "transcription",
        {
            "provider": provider.name,
            "model": provider.model,
            "source_inputs": [item for item in [payload["source"], "raw.mp4"] if item],
            "outputs": ["transcript.srt", "transcript.json"] + (["audio.wav"] if audio.extracted else []),
            "segment_count": len(provider_result.segments),
            "audio_stream_found": audio.audio_stream_found,
            "audio_extracted": audio.extracted,
        },
    )
    return TranscriptionOutputs(
        transcript_srt=transcript_srt,
        transcript_json=transcript_json,
        audio=audio.audio_path if audio.extracted else None,
        segment_count=len(provider_result.segments),
    )


def parse_manual_transcript(text: str) -> list[TranscriptSegment]:
    segments: list[TranscriptSegment] = []
    cursor = 0.0
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _TIMED_LINE.match(line)
        if match:
            start = parse_time(match.group("start"))
            end = parse_time(match.group("end"))
            caption = match.group("text").strip()
        else:
            start = cursor
            end = start + 4.0
            caption = line
        if caption:
            if end <= start:
                end = start + 1.0
            segments.append(TranscriptSegment(start=start, end=end, text=caption))
            cursor = max(cursor, end)
    return segments


def srt_text(segments: list[TranscriptSegment]) -> str:
    blocks = []
    for index, segment in enumerate(segments, start=1):
        blocks.append(f"{index}\n{format_srt_time(segment.start)} --> {format_srt_time(segment.end)}\n{segment.text}\n")
    return "\n".join(blocks)


def format_srt_time(seconds: float) -> str:
    milliseconds = int(round(float(seconds) * 1000))
    h, rem = divmod(milliseconds, 3600 * 1000)
    m, rem = divmod(rem, 60 * 1000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def parse_time(value: str) -> float:
    value = value.strip().replace(",", ".")
    if ":" not in value:
        return float(value)
    parts = [float(part) for part in value.split(":")]
    if len(parts) == 2:
        minutes, seconds = parts
        return minutes * 60 + seconds
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return hours * 3600 + minutes * 60 + seconds
    raise ValueError(f"unsupported time value: {value}")


def _probe_audio(raw: Path) -> tuple[bool, str | None]:
    try:
        result = subprocess.run(
            [
                ffprobe_binary(),
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=codec_type",
                "-of",
                "json",
                str(raw),
            ],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except OSError as exc:
        return False, str(exc)
    if result.returncode != 0:
        return False, f"ffprobe exited {result.returncode}"
    try:
        streams = json.loads(result.stdout).get("streams", [])
    except json.JSONDecodeError:
        return False, "ffprobe returned invalid json"
    return bool(streams), None if streams else "no audio stream"


def _manual_transcript_path(recording_dir: Path) -> Path | None:
    for name in ("manual_transcript.txt", "transcript.txt"):
        path = recording_dir / name
        if path.exists():
            return path
    return None


def _audio_payload(audio: AudioExtractionResult, recording_dir: Path) -> dict:
    return {
        "raw_video": _relative(audio.raw_video, recording_dir),
        "audio": _relative(audio.audio_path, recording_dir) if audio.extracted else None,
        "audio_stream_found": audio.audio_stream_found,
        "extracted": audio.extracted,
        "reason": audio.reason,
        "command": audio.command,
    }


def _relative(path: Path | None, root: Path) -> str | None:
    if path is None:
        return None
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
