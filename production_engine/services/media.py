from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import qrcode
import io, math, shutil, time
from moviepy.editor import ImageClip, concatenate_videoclips, AudioFileClip

BASE = Path("static")
PREV = BASE / "previews"
COMM = BASE / "committed"

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def new_preview_id():
    return f"prv_{time.strftime('%Y%m%d_%H%M%S')}"

def ratio_to_size(ratio: str):
    # δίνουμε τυπικές διαστάσεις βάσει ratio (portrait για IG 4:5)
    if ratio == "4:5":   return (1080, 1350)
    if ratio == "9:16":  return (1080, 1920)
    return (1080, 1080)

def load_img(rel_path: str) -> Image.Image:
    p = Path(rel_path.lstrip("/"))
    return Image.open(p).convert("RGBA")

def paste_center(base: Image.Image, overlay: Image.Image):
    bw, bh = base.size
    ow, oh = overlay.size
    scale = min(bw/ow, bh/oh)
    overlay = overlay.resize((int(ow*scale), int(oh*scale)), Image.LANCZOS)
    ox = (bw - overlay.width)//2
    oy = (bh - overlay.height)//2
    base.alpha_composite(overlay, (ox, oy))
    return base

def draw_qr_overlay(img: Image.Image, final_url: str):
    qr = qrcode.QRCode(version=2, box_size=6, border=2)
    qr.add_data(final_url); qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
    # κάτω δεξιά
    pad = 24
    qr_size = min(img.width//4, img.height//4)
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

def render_image(ratio: str, product_image_url: str, title: str = None,
                 qr_url: str | None = None, ai_bg=False, ai_bg_prompt=None, outdir: Path = None):
    W, H = ratio_to_size(ratio)
    canvas = Image.new("RGBA", (W, H), (245, 247, 250, 255))
    prod = load_img(product_image_url)
    # AI background (βασικό stub: ακόμα flatten χρώμα — θα αντικατασταθεί με αληθινό generator)
    if ai_bg:
        canvas = Image.new("RGBA", (W, H), (240, 240, 255, 255))
    paste_center(canvas, prod)
    if qr_url:
        draw_qr_overlay(canvas, qr_url)
    preview = outdir / "preview.jpg"
    export_jpg(canvas, preview)
    return {"preview": preview}

def render_carousel(ratio: str, images: list[str], qr_url: str | None, ai_bg: bool, ai_bg_prompt, outdir: Path):
    W, H = ratio_to_size(ratio)
    frames = []
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

    # sheet προεπισκόπησης (2xN grid)
    cols = 2
    rows = math.ceil(len(frames) / cols)
    sheet = Image.new("RGBA", (cols*W + (cols-1)*20, rows*H + (rows-1)*20), (255,255,255,255))
    for idx, fr in enumerate(frames):
        im = Image.open(fr).convert("RGBA")
        r = idx // cols; c = idx % cols
        x = c*(W+20); y = r*(H+20)
        sheet.alpha_composite(im, (x,y))
    preview = outdir / "preview.jpg"
    export_jpg(sheet, preview, quality=88)
    return {"preview": preview, "frames": frames}

def render_video(ratio: str, images: list[str], fps: int, duration: float, music: str | None, qr_url: str | None, ai_bg: bool, ai_bg_prompt, outdir: Path):
    W, H = ratio_to_size(ratio)
    # πρώτα φτιάχνουμε ενδιάμεσα frames (ίδια με carousel)
    tmp = render_carousel(ratio, images, qr_url, ai_bg, ai_bg_prompt, outdir)
    frame_files = tmp["frames"]
    # clips ομοιόχρονα
    per_frame = max(0.3, duration / max(1, len(frame_files)))
    clips = [ImageClip(str(f)).set_duration(per_frame).resize((W,H)) for f in frame_files]
    video = concatenate_videoclips(clips, method="compose")
    if music:
        try:
            audio = AudioFileClip(music).volumex(0.85)
            video = video.set_audio(audio)
        except Exception:
            pass
    mp4 = outdir / "out.mp4"
    ensure_dir(outdir)
    video.write_videofile(str(mp4), fps=fps, codec="libx264", audio_codec="aac", threads=2, verbose=False, logger=None)
    # poster
    poster = outdir / "preview.jpg"
    Image.open(frame_files[0]).save(poster, "JPEG", quality=90)
    return {"preview": poster, "frames": frame_files, "video": mp4}
