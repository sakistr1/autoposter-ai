from pathlib import Path
from PIL import Image
import qrcode
import math
import time
import logging
from typing import Optional, List

# opencv
import cv2
import numpy as np

log = logging.getLogger("uvicorn.error")

BASE = Path("static")
PREV = BASE / "previews"
COMM = BASE / "committed"


# ---------------------- helpers ----------------------
def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def ratio_to_size(ratio: str) -> tuple[int, int]:
    if ratio == "4:5":
        return (1080, 1350)
    if ratio == "9:16":
        return (1080, 1920)
    return (1080, 1080)


def load_img(rel_path: str) -> Image.Image:
    p = Path(rel_path.lstrip("/"))
    return Image.open(p).convert("RGBA")


def paste_center(base: Image.Image, overlay: Image.Image):
    bw, bh = base.size
    ow, oh = overlay.size
    scale = min(bw / ow, bh / oh)
    overlay = overlay.resize((int(ow * scale), int(oh * scale)), Image.LANCZOS)
    ox = (bw - overlay.width) // 2
    oy = (bh - overlay.height) // 2
    base.alpha_composite(overlay, (ox, oy))
    return base


def draw_qr_overlay(img: Image.Image, final_url: str):
    qr = qrcode.QRCode(version=2, box_size=6, border=2)
    qr.add_data(final_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
    pad = 24
    qr_size = min(img.width // 4, img.height // 4)
    qr_img = qr_img.resize((qr_size, qr_size), Image.NEAREST)
    x = img.width - qr_size - pad
    y = img.height - qr_size - pad
    img.alpha_composite(qr_img, (x, y))
    return img


def export_jpg(im: Image.Image, out: Path, quality=92):
    ensure_dir(out.parent)
    rgb = im.convert("RGB")
    rgb.save(out, "JPEG", quality=quality, optimize=True, progressive=True)
    return out


# ---------------------- renderers ----------------------
def render_image(ratio: str, product_image_url: str, title=None, qr_url=None, ai_bg=False, ai_bg_prompt=None, outdir: Path | None = None):
    W, H = ratio_to_size(ratio)
    canvas = Image.new("RGBA", (W, H), (245, 247, 250, 255))
    prod = load_img(product_image_url)
    if ai_bg:
        canvas = Image.new("RGBA", (W, H), (240, 240, 255, 255))
    paste_center(canvas, prod)
    if qr_url:
        draw_qr_overlay(canvas, qr_url)
    preview = outdir / "preview.jpg"
    export_jpg(canvas, preview)
    return {"preview": preview}


def render_carousel(ratio: str, images: List[str], qr_url: Optional[str], ai_bg: bool, ai_bg_prompt, outdir: Path):
    W, H = ratio_to_size(ratio)
    frames: List[Path] = []
    for i, rel in enumerate(images, 1):
        base = Image.new("RGBA", (W, H), (245, 247, 250, 255))
        if ai_bg:
            base = Image.new("RGBA", (W, H), (240, 240, 255, 255))
        prod = load_img(rel)
        paste_center(base, prod)
        if qr_url:
            draw_qr_overlay(base, qr_url)
        out = outdir / f"frame_{i:04d}.jpg"
        export_jpg(base, out)
        frames.append(out)

    preview = outdir / "preview.jpg"
    export_jpg(Image.open(frames[0]), preview, quality=88)
    return {"preview": preview, "frames": frames}


def render_video(ratio: str, images: List[str], fps: int, duration: float, music: Optional[str], qr_url: Optional[str], ai_bg: bool, ai_bg_prompt, outdir: Path):
    """
    OpenCV-only video writer. Σταθερό σε όλα τα VM.
    """
    W, H = ratio_to_size(ratio)

    # 1) Frames
    tmp = render_carousel(ratio, images, qr_url, ai_bg, ai_bg_prompt, outdir)
    frame_files: List[Path] = tmp["frames"]

    # 2) Output path
    ts = int(time.time() * 1000)
    mp4 = outdir / f"prev_{ts}.mp4"

    # 3) OpenCV writer
    ensure_dir(mp4.parent)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    vw = cv2.VideoWriter(str(mp4), fourcc, int(fps or 30), (W, H))

    per_frame = max(0.3, duration / max(1, len(frame_files)))
    repeat = max(1, int(round(per_frame * fps)))

    for f in frame_files:
        im = Image.open(f).convert("RGB").resize((W, H), Image.LANCZOS)
        bgr = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)
        for _ in range(repeat):
            vw.write(bgr)

    vw.release()

    # 4) Poster
    poster = outdir / "preview.jpg"
    Image.open(frame_files[0]).convert("RGB").save(poster, "JPEG", quality=90)

    if not mp4.exists() or mp4.stat().st_size == 0:
        log.error("VIDEO ENCODE (OpenCV) failed: %s", mp4)
        return {"preview": poster, "frames": frame_files, "video": None}

    return {"preview": poster, "frames": frame_files, "video": mp4}
