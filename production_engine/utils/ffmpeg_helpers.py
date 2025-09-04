import subprocess
from pathlib import Path
from typing import Optional, Sequence

def run(cmd: Sequence[str]) -> None:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {p.stderr.strip()}")

def ensure_dir(path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)

def poster_from_video(input_video: str | Path, output_image: str | Path, width: int = 1080) -> str:
    """Βγάζει ΜΟΝΟ 1 frame (poster) από βίντεο, χωρίς name collisions."""
    output_image = str(output_image)
    ensure_dir(output_image)
    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_video),
        "-vf", f"thumbnail,scale={width}:-1",
        "-frames:v", "1",
        "-update", "1",   # ασφαλές με image2 για ίδιο filename
        output_image,
    ]
    run(cmd)
    return output_image

def sprite_from_video(input_video: str | Path, output_image: str | Path,
                      fps: float = 3.0, cols: int = 3, width: int = 540) -> str:
    """Φτιάχνει sheet με 1 τελικό frame (tile)."""
    output_image = str(output_image)
    ensure_dir(output_image)
    vf = f"fps={fps},scale={width}:-1:flags=bicubic,tile={cols}x1:padding=2:color=black"
    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_video),
        "-vf", vf,
        "-frames:v", "1",
        "-update", "1",
        "-vcodec", "libwebp" if str(output_image).lower().endswith(".webp") else "mjpeg",
        output_image,
    ]
    run(cmd)
    return output_image
