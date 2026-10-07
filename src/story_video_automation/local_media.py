"""Free, local scene-card rendering for machines without paid video generation."""

from __future__ import annotations

import hashlib
import subprocess
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from story_video_automation.config import get_settings


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (r"C:\Windows\Fonts\arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render_local_scene_card(prompt: str, destination: Path, duration: int = 6) -> Path:
    """Create a stylized still-card MP4 locally; no image/video API is called."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    seed = hashlib.sha256(prompt.encode("utf-8")).digest()
    palettes = [((18, 32, 66), (35, 132, 151)),
                ((64, 35, 78), (193, 112, 85)),
                ((23, 62, 49), (116, 157, 105)),
                ((55, 48, 88), (107, 116, 180))]
    top, bottom = palettes[seed[0] % len(palettes)]
    width, height = 720, 1280
    image = Image.new("RGB", (width, height))
    pixels = image.load()
    for y in range(height):
        ratio = y / (height - 1)
        color = tuple(round(top[i] * (1 - ratio) + bottom[i] * ratio) for i in range(3))
        for x in range(width):
            pixels[x, y] = color

    draw = ImageDraw.Draw(image, "RGBA")
    # A few soft shapes give the generated scene card depth while remaining fully offline.
    draw.ellipse((-170, 720, 600, 1490), fill=(7, 20, 39, 125))
    draw.ellipse((310, 810, 960, 1420), fill=(245, 193, 123, 42))
    draw.rounded_rectangle((52, 70, 668, 1195), radius=36,
                           fill=(7, 14, 30, 62), outline=(255, 255, 255, 105), width=2)
    draw.text((92, 128), "STORY SCENE", font=_font(26), fill=(245, 226, 187, 255))

    lines = textwrap.wrap(" ".join(prompt.split()), width=34)[:11]
    y = 245
    for line in lines:
        draw.text((92, y), line, font=_font(35), fill=(255, 255, 255, 255),
                  stroke_width=1, stroke_fill=(10, 20, 37, 180))
        y += 61
    draw.text((92, 1097), "Made locally with FFmpeg", font=_font(20),
              fill=(231, 238, 245, 220))

    still = destination.with_suffix(".png")
    image.save(still)
    settings = get_settings()
    command = [
        settings.ffmpeg_path, "-y", "-loop", "1", "-framerate", "24", "-i", str(still),
        "-t", str(max(3, duration)), "-vf", "scale=720:1280,format=yuv420p", "-r", "24",
        "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "25",
        "-movflags", "+faststart", str(destination),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0 or not destination.is_file() or destination.stat().st_size == 0:
        raise RuntimeError(f"Local FFmpeg scene render failed: {(result.stderr or '')[-2000:]}")
    return destination
