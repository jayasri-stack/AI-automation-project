"""Free, locally rendered 2D village animation for machines without video APIs."""

from __future__ import annotations

import hashlib
import math
import random
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

from story_video_automation.config import get_settings

WIDTH, HEIGHT = 540, 960
FPS = 12


def _background(prompt: str, seed: int) -> Image.Image:
    evening = any(word in prompt.lower() for word in ("evening", "sunset", "night", "lamp"))
    if evening:
        top, bottom = (62, 76, 105), (217, 145, 103)
        field, hill = (82, 102, 67), (67, 83, 57)
    else:
        top, bottom = (126, 179, 197), (245, 202, 146)
        field, hill = (131, 147, 77), (92, 119, 68)
    image = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(image)
    for y in range(0, 601, 6):
        t = y / 600
        color = tuple(round(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
        draw.rectangle((0, y, WIDTH, y + 6), fill=color)
    # Sun, distant hills and layered fields establish a warm, nostalgic village setting.
    sun_x = 420 if seed % 2 else 120
    draw.ellipse((sun_x - 43, 120, sun_x + 43, 206), fill=(255, 224, 156))
    draw.polygon([(0, 535), (85, 430), (174, 530), (285, 405), (420, 540), (540, 445), (540, 700), (0, 700)], fill=hill)
    draw.rectangle((0, 590, WIDTH, HEIGHT), fill=field)
    for y, color in ((650, (151, 157, 81)), (760, (171, 156, 86)), (870, (191, 161, 101))):
        draw.polygon([(0, y), (WIDTH, y - 46), (WIDTH, y + 46), (0, y + 92)], fill=color)
    # Traditional tiled mud home with a shaded doorway and a little window.
    draw.rectangle((53, 485, 251, 660), fill=(191, 139, 87))
    draw.polygon([(32, 500), (146, 405), (270, 500), (247, 521), (145, 446), (58, 522)], fill=(101, 65, 47))
    draw.rectangle((132, 563, 178, 660), fill=(70, 48, 39))
    draw.rectangle((77, 535, 112, 574), fill=(91, 113, 106), outline=(237, 207, 159), width=5)
    # Broad village tree and textured canopy.
    draw.polygon([(385, 640), (413, 640), (405, 462), (430, 395), (418, 385), (384, 456)], fill=(96, 66, 43))
    canopy = [(375, 500, 475, 590), (335, 450, 438, 548), (405, 430, 520, 535), (360, 390, 455, 485)]
    greens = [(63, 100, 55), (77, 112, 61), (91, 124, 67), (68, 105, 60)]
    for box, color in zip(canopy, greens):
        draw.ellipse(box, fill=color)
    # Winding footpath, front edge, and a few crops.
    draw.polygon([(152, 660), (223, 660), (365, HEIGHT), (15, HEIGHT)], fill=(196, 153, 103))
    for x in range(20, WIDTH, 42):
        draw.line((x, 770, x + 8, 724), fill=(209, 187, 112), width=3)
        draw.ellipse((x - 4, 716, x + 10, 730), fill=(220, 190, 107))
    lower = prompt.lower()
    if any(word in lower for word in ("river", "pond", "lake", "water")):
        draw.polygon([(0, 720), (160, 695), (285, 735), (230, 780), (88, 756), (0, 785)], fill=(74, 145, 161))
        for x in range(18, 240, 45):
            draw.line((x, 738, x + 30, 733), fill=(185, 218, 204), width=3)
    if any(word in lower for word in ("market", "festival", "fair")):
        for x, color in ((310, (169, 88, 63)), (405, (82, 103, 73))):
            draw.rectangle((x, 547, x + 82, 632), fill=(143, 99, 65))
            draw.polygon([(x - 8, 553), (x + 38, 506), (x + 91, 553)], fill=color)
    if "school" in lower:
        draw.rectangle((295, 525, 390, 625), fill=(208, 174, 119))
        draw.polygon([(281, 532), (342, 478), (404, 532)], fill=(112, 76, 55))
        draw.rectangle((330, 564, 353, 625), fill=(74, 55, 43))
    return image


def _person(draw: ImageDraw.ImageDraw, x: float, foot_y: int, phase: float, woman: bool) -> None:
    bob = round(math.sin(phase * 2) * 3)
    head_y = foot_y - 112 + bob
    skin = (143, 91, 59)
    cloth = (157, 77, 55) if woman else (82, 113, 91)
    # Simple, readable illustrated villagers with moving steps and swinging arms.
    draw.ellipse((x - 17, head_y - 20, x + 17, head_y + 15), fill=skin)
    draw.ellipse((x - 21, head_y - 27, x + 20, head_y - 10), fill=(64, 48, 37))
    draw.polygon([(x - 20, head_y + 16), (x + 20, head_y + 16), (x + 29, foot_y - 38), (x - 29, foot_y - 38)], fill=cloth)
    stride = math.sin(phase * 2) * 11
    draw.line((x - 12, foot_y - 45, x - 13 + stride, foot_y - 5), fill=skin, width=8)
    draw.line((x + 12, foot_y - 45, x + 12 - stride, foot_y - 5), fill=skin, width=8)
    arm = math.sin(phase * 2) * 9
    draw.line((x - 15, head_y + 28, x - 31, head_y + 60 + arm), fill=skin, width=7)
    draw.line((x + 15, head_y + 28, x + 31, head_y + 60 - arm), fill=skin, width=7)
    if woman:
        draw.line((x + 20, head_y + 20, x + 31, foot_y - 12), fill=(226, 184, 116), width=5)


def render_local_animated_scene(prompt: str, destination: Path, duration: int = 6) -> Path:
    """Render a small vintage village illustration with moving villagers and scenery."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    seed = int.from_bytes(hashlib.sha256(prompt.encode("utf-8")).digest()[:4], "big")
    rng = random.Random(seed)
    background = _background(prompt, seed)
    frame_count = max(36, duration * FPS)
    settings = get_settings()
    with tempfile.TemporaryDirectory(prefix="village_frames_", dir=destination.parent) as frame_dir:
        frame_root = Path(frame_dir)
        for frame_no in range(frame_count):
            phase = frame_no / FPS
            image = background.copy()
            draw = ImageDraw.Draw(image)
            # Slow clouds, birds and cookfire smoke provide ambient motion.
            cloud_x = int((frame_no * 1.3 + seed % 180) % (WIDTH + 150)) - 100
            for dx, dy, radius in ((0, 0, 25), (28, -7, 29), (57, 1, 22)):
                draw.ellipse((cloud_x + dx, 235 + dy, cloud_x + dx + radius * 2, 235 + dy + radius), fill=(255, 235, 205))
            for bird_x in (70, 300, 460):
                bx = (bird_x + frame_no * 2) % WIDTH
                draw.arc((bx, 340, bx + 18, 355), 200, 330, fill=(61, 73, 65), width=2)
                draw.arc((bx + 15, 340, bx + 34, 355), 210, 340, fill=(61, 73, 65), width=2)
            for puff in range(4):
                rise = (frame_no * 2 + puff * 22) % 90
                smoke_x = 139 + math.sin(phase + puff) * 9
                smoke_y = 414 - rise
                draw.ellipse((smoke_x - 9, smoke_y - 9, smoke_x + 9, smoke_y + 9), fill=(220, 213, 194))
            # Two villagers walk gently along the path; their steps and arms are animated.
            travel = math.sin(phase * 1.3) * 22
            _person(draw, 205 + travel, 828, phase, woman=False)
            _person(draw, 285 - travel * 0.45, 868, phase + 1.4, woman=True)
            if any(word in prompt.lower() for word in ("cow", "bullock", "cattle")):
                cx = 385 + math.sin(phase) * 7
                draw.ellipse((cx - 42, 778, cx + 35, 826), fill=(225, 211, 180))
                draw.ellipse((cx + 21, 764, cx + 48, 795), fill=(216, 198, 162))
                draw.line((cx + 27, 768, cx + 19, 753), fill=(90, 73, 53), width=4)
                draw.line((cx + 39, 769, cx + 48, 754), fill=(90, 73, 53), width=4)
                for leg_x in (cx - 26, cx + 17):
                    draw.line((leg_x, 818, leg_x, 849 + round(math.sin(phase * 2) * 4)), fill=(93, 71, 54), width=5)
            # Fine grain adds a subtle vintage-film feel without covering the illustration.
            for _ in range(45):
                x, y = rng.randrange(WIDTH), rng.randrange(HEIGHT)
                shade = rng.choice((224, 240, 255))
                draw.point((x, y), fill=(shade, shade - 8, shade - 22))
            image.save(frame_root / f"frame_{frame_no:04}.png", optimize=True)

        command = [
            settings.ffmpeg_path, "-y", "-framerate", str(FPS),
            "-i", str(frame_root / "frame_%04d.png"), "-frames:v", str(frame_count),
            "-vf", "scale=720:1280:flags=lanczos,fps=24,format=yuv420p", "-r", "24",
            "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
            "-movflags", "+faststart", str(destination),
        ]
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
        except FileNotFoundError as exc:
            raise RuntimeError(
                "FFmpeg was not found. Install FFmpeg and add its bin folder to PATH, "
                "or set FFMPEG_PATH in .env."
            ) from exc
    if result.returncode != 0 or not destination.is_file() or destination.stat().st_size == 0:
        raise RuntimeError(f"Local animated scene render failed: {(result.stderr or '')[-2000:]}")
    return destination
