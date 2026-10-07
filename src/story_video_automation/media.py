"""FFmpeg scene assembly, voice/music mixing, and burned subtitles."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from story_video_automation.config import get_settings


def _run(arguments: list[str], cwd: Path) -> None:
    try:
        result = subprocess.run(arguments, cwd=cwd, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise RuntimeError(f"FFmpeg tool not found: {arguments[0]}") from exc
    if result.returncode:
        detail = (result.stderr or result.stdout)[-3000:]
        raise RuntimeError(f"Media command failed ({result.returncode}): {detail}")


def _duration(path: Path, ffprobe: str) -> float:
    try:
        result = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration",
             "-of", "json", str(path)],
            capture_output=True, text=True, check=True,
        )
        seconds = float(json.loads(result.stdout)["format"]["duration"])
    except (FileNotFoundError, subprocess.CalledProcessError, KeyError, ValueError) as exc:
        raise RuntimeError(f"Could not read media duration for {path}") from exc
    if seconds <= 0:
        raise RuntimeError(f"Media file has invalid duration: {path}")
    return seconds


def _has_audio(path: Path, ffprobe: str) -> bool:
    result = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "a:0", "-show_entries",
         "stream=codec_type", "-of", "json", str(path)],
        capture_output=True, text=True, check=False,
    )
    if result.returncode:
        raise RuntimeError(f"Could not inspect audio streams for {path}: {result.stderr[-1000:]}")
    return bool(json.loads(result.stdout).get("streams"))


def _timestamp(milliseconds: int) -> str:
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"


def render_video(
    scenes: list[dict[str, Any]],
    output_dir: Path,
    output_path: Path,
    background_music: Path | None = None,
) -> Path:
    """Make normalized scene segments, concatenate them, and burn Telugu/English SRTs."""
    if not scenes:
        raise ValueError("Cannot render a video without scenes")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    settings = get_settings()
    ffmpeg = settings.ffmpeg_path
    ffprobe = str(Path(ffmpeg).with_name("ffprobe.exe" if ffmpeg.lower().endswith(".exe") else "ffprobe"))
    if Path(ffmpeg).name == ffmpeg:
        ffprobe = "ffprobe"

    segment_names: list[str] = []
    subtitles: list[str] = []
    timeline_ms = 0
    for index, scene in enumerate(scenes, start=1):
        video = Path(scene["video_path"])
        audio = Path(scene["audio_path"])
        if not video.is_file() or not audio.is_file():
            raise FileNotFoundError(f"Scene {index} is missing its video or narration audio")
        video_seconds = _duration(video, ffprobe)
        audio_seconds = _duration(audio, ffprobe)
        segment_seconds = max(video_seconds, audio_seconds)
        pad_seconds = max(0.0, audio_seconds - video_seconds)
        segment_name = f"segment_{index:03}.mp4"
        arguments = [ffmpeg, "-y", "-i", str(video.resolve()), "-i", str(audio.resolve())]
        if _has_audio(video, ffprobe):
            arguments.extend([
                "-filter_complex",
                "[0:a:0]volume=0.18[ambient];[1:a:0]volume=1.0[voice];"
                "[voice][ambient]amix=inputs=2:duration=longest:dropout_transition=2,apad[aout]",
                "-map", "0:v:0", "-map", "[aout]",
            ])
        else:
            arguments.extend(["-map", "0:v:0", "-map", "1:a:0"])
        arguments.extend([
            "-vf", f"tpad=stop_mode=clone:stop_duration={pad_seconds:.3f},setsar=1",
            "-af", "apad", "-t", f"{segment_seconds:.3f}",
            "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", segment_name,
        ])
        _run(arguments, output_dir)
        segment_names.append(segment_name)
        start = timeline_ms
        end = start + round(audio_seconds * 1000)
        text = " ".join(str(scene.get("narration", "")).split())
        subtitles.append(f"{index}\n{_timestamp(start)} --> {_timestamp(end)}\n{text}\n")
        timeline_ms += round(segment_seconds * 1000)

    (output_dir / "subtitles.srt").write_text("\n".join(subtitles), encoding="utf-8-sig")
    concat_file = output_dir / "concat.txt"
    concat_file.write_text(
        "".join(f"file '{name}'\n" for name in segment_names), encoding="utf-8"
    )
    joined = output_dir / "joined.mp4"
    _run([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", "concat.txt",
          "-c", "copy", "-movflags", "+faststart", joined.name], output_dir)

    subtitle_filter = (
        "subtitles=filename='subtitles.srt':force_style="
        "'FontName=Arial,FontSize=22,Outline=2,Shadow=1,Alignment=2,MarginV=36'"
    )
    if background_music and background_music.is_file():
        filter_complex = "[1:a]volume=0.12[bed];[0:a][bed]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        _run([
            ffmpeg, "-y", "-i", str(joined.resolve()), "-stream_loop", "-1",
            "-i", str(background_music.resolve()), "-vf", subtitle_filter,
            "-filter_complex", filter_complex, "-map", "0:v:0", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
            str(output_path.resolve()),
        ], output_dir)
    else:
        _run([
            ffmpeg, "-y", "-i", str(joined.resolve()), "-vf", subtitle_filter,
            "-map", "0:v:0", "-map", "0:a:0", "-c:v", "libx264", "-preset", "medium",
            "-crf", "23", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", str(output_path.resolve()),
        ], output_dir)
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RuntimeError("FFmpeg did not produce a finished preview")
    return output_path
