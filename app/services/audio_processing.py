from __future__ import annotations

import audioop
from dataclasses import dataclass
from io import BytesIO
import wave

from fastapi import HTTPException


@dataclass
class ComputedAudioMetrics:
    duration_seconds: float
    sample_rate_hz: int
    channel_count: int
    rms_amplitude: float
    peak_amplitude: float
    normalized_rms: float
    normalized_peak: float


def _max_possible_amplitude(sample_width: int) -> int:
    return (2 ** (8 * sample_width - 1)) - 1


def compute_wav_metrics(payload: bytes) -> ComputedAudioMetrics:
    try:
        with wave.open(BytesIO(payload), "rb") as wav_file:
            frame_count = wav_file.getnframes()
            sample_rate = wav_file.getframerate()
            channel_count = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            compression_type = wav_file.getcomptype()
            frames = wav_file.readframes(frame_count)
    except wave.Error as exc:
        raise HTTPException(
            status_code=422,
            detail="Invalid WAV payload. Use standard PCM WAV audio.",
        ) from exc

    if compression_type != "NONE":
        raise HTTPException(
            status_code=422,
            detail="Only uncompressed PCM WAV audio is supported in the MVP.",
        )

    if sample_width not in {1, 2, 4}:
        raise HTTPException(
            status_code=422,
            detail="Unsupported WAV sample width. Use 8, 16, or 32-bit PCM WAV audio.",
        )

    if frame_count == 0 or sample_rate == 0 or len(frames) == 0:
        raise HTTPException(status_code=400, detail="Audio upload is empty.")

    max_possible = _max_possible_amplitude(sample_width)
    rms_amplitude = float(audioop.rms(frames, sample_width))
    peak_amplitude = float(audioop.max(frames, sample_width))

    return ComputedAudioMetrics(
        duration_seconds=frame_count / sample_rate,
        sample_rate_hz=sample_rate,
        channel_count=channel_count,
        rms_amplitude=rms_amplitude,
        peak_amplitude=peak_amplitude,
        normalized_rms=round(rms_amplitude / max_possible, 6),
        normalized_peak=round(peak_amplitude / max_possible, 6),
    )
