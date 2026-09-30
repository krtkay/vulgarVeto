"""
audio_utils.py
==============
Optional audio helpers for VulgarVeto.

These are deliberately dependency-light so the core (text) app keeps working even
if the audio extras aren't installed:

* Transcription uses ``SpeechRecognition`` against Google's free web endpoint and
  reads WAV/AIFF/FLAC **natively** (Python's ``wave`` module) - so there is no
  ``pydub`` / ``ffmpeg`` requirement, which keeps Streamlit Cloud deploys light.
* Text-to-speech uses ``gTTS`` and returns MP3 bytes.

All heavy imports are done lazily inside the functions, and both features degrade
gracefully (see :func:`speech_to_text_available` / :func:`tts_available`).
"""

from __future__ import annotations

import io
from typing import Callable, List, Optional


def speech_to_text_available() -> bool:
    try:
        import speech_recognition  # noqa: F401
        return True
    except Exception:
        return False


def tts_available() -> bool:
    try:
        import gtts  # noqa: F401
        return True
    except Exception:
        return False


def transcribe_wav(
    audio_bytes: bytes,
    *,
    chunk_seconds: int = 15,
    language: str = "en-US",
    progress: Optional[Callable[[float], None]] = None,
) -> str:
    """
    Transcribe PCM WAV/AIFF/FLAC bytes to text, chunk by chunk.

    Chunking is done with the recognizer's own ``offset``/``duration`` (no pydub),
    which keeps each request small enough for the free Google endpoint.

    Raises
    ------
    RuntimeError
        If SpeechRecognition isn't installed, the audio can't be read, or the
        recognition service is unreachable.
    """
    try:
        import speech_recognition as sr
    except Exception as exc:  # pragma: no cover - only when extra missing
        raise RuntimeError(
            "SpeechRecognition is not installed. Run `pip install SpeechRecognition`."
        ) from exc

    recognizer = sr.Recognizer()

    try:
        with sr.AudioFile(io.BytesIO(audio_bytes)) as source:
            duration = float(source.DURATION or 0.0)
    except Exception as exc:
        raise RuntimeError(
            "Could not read the audio. Please upload uncompressed PCM WAV "
            "(mono/stereo, 8-48 kHz)."
        ) from exc

    if duration <= 0:
        return ""

    parts: List[str] = []
    offset = 0.0
    while offset < duration:
        with sr.AudioFile(io.BytesIO(audio_bytes)) as source:
            audio = recognizer.record(source, offset=offset, duration=chunk_seconds)
        try:
            text = recognizer.recognize_google(audio, language=language)
        except sr.UnknownValueError:
            text = ""  # this chunk had no recognizable speech
        except sr.RequestError as exc:
            raise RuntimeError(
                f"Speech recognition service unavailable: {exc}"
            ) from exc
        if text:
            parts.append(text)
        offset += chunk_seconds
        if progress:
            progress(min(offset / duration, 1.0))

    return " ".join(parts).strip()


def text_to_speech(text: str, *, lang: str = "en") -> io.BytesIO:
    """Synthesize ``text`` to MP3 bytes via gTTS. Returns a seek-0 BytesIO."""
    try:
        from gtts import gTTS
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "gTTS is not installed. Run `pip install gTTS`."
        ) from exc

    buf = io.BytesIO()
    gTTS(text=text or " ", lang=lang, slow=False).write_to_fp(buf)
    buf.seek(0)
    return buf
