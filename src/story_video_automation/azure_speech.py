"""Telugu narration synthesis through Azure Speech."""

from __future__ import annotations

import os
from pathlib import Path

from story_video_automation.config import get_settings
from story_video_automation.options import Options


def synthesize_narration(text: str, destination: Path, language: str = "te") -> Path:
    """Synthesize one Telugu or English scene to a PCM WAV file."""
    settings = get_settings()
    if not settings.azure_speech_key or not settings.azure_speech_region:
        raise RuntimeError("Set AZURE_SPEECH_KEY and AZURE_SPEECH_REGION for narration")
    if not text.strip():
        raise ValueError("Narration text is empty")
    if language not in {"te", "en"}:
        raise ValueError("language must be 'te' or 'en'")
    try:
        import azure.cognitiveservices.speech as speechsdk
    except ImportError as exc:
        raise RuntimeError('Install the "speech" extra to use Azure Speech') from exc

    destination.parent.mkdir(parents=True, exist_ok=True)
    speech_config = speechsdk.SpeechConfig(
        subscription=settings.azure_speech_key,
        region=settings.azure_speech_region,
    )
    speech_config.speech_synthesis_voice_name = (
        Options.from_env().telugu_voice
        if language == "te"
        else os.getenv("AZURE_ENGLISH_VOICE", "en-US-AriaNeural")
    )
    speech_config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Riff24Khz16BitMonoPcm
    )
    audio_config = speechsdk.audio.AudioOutputConfig(filename=str(destination))
    synthesizer = speechsdk.SpeechSynthesizer(
        speech_config=speech_config,
        audio_config=audio_config,
    )
    result = synthesizer.speak_text_async(text.strip()).get()
    if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
        details = result.cancellation_details
        reason = getattr(details, "reason", "unknown")
        message = getattr(details, "error_details", "")
        raise RuntimeError(f"Azure Speech synthesis failed ({reason}): {message}")
    if not destination.is_file() or destination.stat().st_size == 0:
        raise RuntimeError("Azure Speech returned an empty audio file")
    return destination


def synthesize_telugu(text: str, destination: Path) -> Path:
    """Backward-compatible Telugu-only helper."""
    return synthesize_narration(text, destination, language="te")
