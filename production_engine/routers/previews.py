# production_engine/routers/previews.py
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime, timezone
import shutil
import os
import time
import mimetypes
from typing import List, Optional, Any, Dict
from uuid import uuid4
from urllib.request import urlopen, Request as URLRequest
import logging

# logger για ελαφρύ debug
logger = logging.getLogger(__name__)

# Optional deps
try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:  # pragma: no cover
    Image = None
    ImageDraw = None
    ImageFont = None

try:
    # moviepy 2.x
    from moviepy.editor import (
        ImageClip,
        concatenate_videoclips,
        VideoFileClip,
        AudioFileClip,
    )
    from moviepy.audio.fx.all import audio_loop
except Exception:  # pragma: no cover
    ImageClip = None

try:
    # optional, for auto music bed
    from music_bed import set_music_bed as _set_music_bed
except Exception:  # pragma: no cover
    _set_music_bed = None

# ΝΕΟ (optional): Pillow renderer (πίσω από flag)
try:
    from production_engine.services.pillow_renderer import render as pillow_render
except Exception:  # pragma: no cover
    pillow_render = None

from database import get_db
from token_module import get_current_user
from models.user import User

# image check analyzer
from production_engine.services.image_check import analyze_image

# Prefix: /previews/...
router = APIRouter(prefix="/previews", tags=["previews"])

# -------------------- Utils --------------------

DEF_EXTS = {".png", ".jpg", ".jpeg", ".webp"}

STATIC_DIR = Path("static")
GENERATED_DIR = STATIC_DIR / "generated"
UPLOAD_TMP = STATIC_DIR / "uploads" / "tmp"


def _ensure_dir(d: Path) -> None:
    d.mkdir(parents=True, exist_ok=True)


def _safe_ext_from_path(path: str, default: str = ".png") -> str:
    ext = (Path(path).suffix or "").lower()
    return ext if ext in DEF_EXTS else default


def _safe_ext_from_ct(content_type: Optional[str], default: str = ".png") -> str:
    if not content_type:
        return default
    guess = mimetypes.guess_extension(content_type.split(";")[0].strip()) or default
    guess = guess.lower()
    if guess == ".jpe":
        guess = ".jpg"
    return guess if guess in DEF_EXTS else default


def _is_http(url: str) -> bool:
    return url.startswith("http://") or url.startswith("https://")


def _to_local_path_under_static(url_or_path: str) -> Path:
    p = (url_or_path or "").strip()
    if _is_http(p):
        p = urlparse(p).path
    p = p.lstrip("/")
    if not p.startswith("static/"):
        raise HTTPException(status_code=400, detail="Path must be under /static")
    return Path(p)


def _download_to_tmp(url: str, default_ext: str = ".jpg") -> Path:
    _ensure_dir(UPLOAD_TMP)
    ext = _safe_ext_from_path(urlparse(url).path, default=default_ext)
    req = URLRequest(url, headers={"User-Agent": "autoposter-fetch/1.0"})
    try:
        with urlopen(req, timeout=10) as resp:
            ctype = resp.headers.get("Content-Type")
            if ext not in DEF_EXTS:
                ext = _safe_ext_from_ct(ctype, default=default_ext)
            fname = f"fetch_{int(time.time()*1000)}_{uuid4().hex}{ext}"
            dest = UPLOAD_TMP / fname
            with dest.open("wb") as f:
                shutil.copyfileobj(resp, f)
    except Exception as e:  # pragma: no cover
        raise HTTPException(status_code=502, detail=f"Failed to fetch URL: {e}")
    return dest


def _materialize_image_to_local(image_url: Optional[str] = None) -> Path:
    """
    Returns a local Path for the image.
    - If /static/... (or full URL that points to /static/...), return Path.
    - If external http(s), download into static/uploads/tmp/ and return Path.
    """
    if not image_url:
        raise HTTPException(status_code=400, detail="image_url is required")

    image_url = image_url.strip()

    # /static/...
    if image_url.startswith("/static/") or (_is_http(image_url) and urlparse(image_url).path.startswith("/static/")):
        local = _to_local_path_under_static(image_url)
        if not local.exists():
            raise HTTPException(status_code=404, detail="image_url not found on server")
        return local

    # External URL
    if _is_http(image_url):
        return _download_to_tmp(image_url, default_ext=".jpg")

    raise HTTPException(status_code=400, detail="image_url must be http(s) or /static path")


def _materialize_audio_to_local(audio_url: str) -> Optional[Path]:
    if not audio_url:
        return None
    audio_url = audio_url.strip()
    if audio_url.startswith("/static/") or (_is_http(audio_url) and urlparse(audio_url).path.startswith("/static/")):
        local = _to_local_path_under_static(audio_url)
        if not local.exists():
            raise HTTPException(status_code=404, detail="audio_url not found on server")
        return local
    if _is_http(audio_url):
        # allow external audio fetch
        return _download_to_tmp(audio_url, default_ext=".mp3")
    return None


def _ext_from(src: Path, default: str = ".png") -> str:
    ext = (src.suffix or "").lower()
    return ext if ext in DEF_EXTS else default


def _save_as_webp(src: Path, dst: Path, quality: int = 90) -> None:
    if Image is None:  # fallback: simple copy
        shutil.copy2(src, dst)
        return
    try:
        with Image.open(src) as im:
            if im.mode in ("RGBA", "P"):
                im = im.convert("RGB")
            _ensure_dir(dst.parent)
            im.save(dst, format="WEBP", quality=90, method=6)
    except Exception:
        shutil.copy2(src, dst)


def _make_contact_sheet(paths: List[Path], dst: Path, thumb: int = 512, cols: int = 3) -> None:
    if Image is None:
        shutil.copy2(paths[0], dst)
        return
    cols = max(1, min(cols, 5))
    rows = (len(paths) + cols - 1) // cols
    thumbs: List[Image.Image] = []
    for p in paths:
        with Image.open(p) as im:
            im = im.convert("RGB")
            im.thumbnail((thumb, thumb))
            thumbs.append(im.copy())
    w = cols * thumbs[0].width
    h = rows * thumbs[0].height
    sheet = Image.new("RGB", (w, h), color=(18, 18, 18))
    for i, t in enumerate(thumbs):
        r, c = divmod(i, cols)
        sheet.paste(t, (c * t.width, r * t.height))
    _ensure_dir(dst.parent)
    sheet.save(dst, format="WEBP", quality=85, method=6)


# -------------------- Schemas --------------------

class _Base(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class OverlayIn(BaseModel):
    title: Optional[str] = None
    price: Optional[str] = None
    footer: Optional[str] = None


class PreviewIn(_Base):
    platform: Optional[str] = Field(default="instagram")
    style: Optional[str] = None
    mode: Optional[str] = None

    # Τιμές
    new_price: Optional[str] = None
    price: Optional[str] = None
    old_price: Optional[str] = None

    # Template
    ratio: Optional[str] = None
    template: Optional[str] = None

    title: Optional[str] = None
    image_url: Optional[str] = None   # προαιρετικό για carousel/video
    brand_logo_url: Optional[str] = None
    purchase_url: Optional[str] = None
    cta_label: Optional[str] = None

    # Overlay (προαιρετικό)
    overlay: Optional[OverlayIn] = None

    # Carousel/Video
    images: Optional[List[Any]] = None  # strings ή objects {image:"..."}

    # Video params (MVP)
    fps: Optional[int] = 30
    duration: Optional[float] = None
    duration_sec: Optional[float] = None
    audio_url: Optional[str] = None
    music_bucket: Optional[str] = None

    # ΝΕΟ: flag για Pillow renderer (off by default — δεν αλλάζει τίποτα αν δεν ζητηθεί)
    use_renderer: Optional[bool] = False

    # ΝΕΟ: optional mapping (όταν ο καλών θέλει ρητά text-keys όπως title/price/old_price/cta/discount_badge)
    mapping: Optional[Dict[str, Any]] = None


class CommitIn(_Base):
    preview_id: Optional[str] = None
    preview_url: Optional[str] = None


# -------------------- Internal helpers --------------------

BUCKET_BY_PLATFORM = {
    "instagram": "ig_tiktok",
    "tiktok": "ig_tiktok",
    "facebook": "facebook",
    "linkedin": "linkedin",
}


def _infer_mode(body: PreviewIn) -> str:
    extra = {}
    try:
        extra = getattr(body, "model_extra", {}) or {}
    except Exception:
        extra = {}
    raw = (body.style or body.mode or extra.get("node") or "normal").lower().strip()
    if raw in ("image", "img", "picture", "photo"):
        return "normal"
    return raw


def _coerce_images_list(images_field: Optional[List[Any]], fallback: Optional[str]) -> List[str]:
    if not images_field:
        return [fallback] if fallback else []
    urls: List[str] = []
    for it in images_field:
        if isinstance(it, str):
            if it.strip():
                urls.append(it.strip())
        elif isinstance(it, dict):
            u = (it.get("image") or it.get("url") or it.get("path") or "").strip()
            if u:
                urls.append(u)
    return urls or ([fallback] if fallback else [])


def _images_list(body: PreviewIn) -> List[Path]:
    raw = None
    try:
        raw = getattr(body, "model_extra", {}).get("images", None)
    except Exception:
        raw = None
    raw = raw if raw is not None else body.images
    urls = _coerce_images_list(raw, getattr(body, "image_url", None))
    return [_materialize_image_to_local(u) for u in urls]


def _video_poster(mp4_path: Path) -> Optional[Path]:
    try:
        if ImageClip is None:
            return None
        clip = VideoFileClip(str(mp4_path))
        t = min(1.0, max(0.0), (clip.duration or 0) / 2.0)
        poster = mp4_path.with_suffix(".jpg").with_name(mp4_path.stem + ".jpg")
        clip.save_frame(str(poster), t=t)
        clip.close()
        return poster
    except Exception:
        return None


def _apply_overlay_to_image(dst_path: Path, overlay: OverlayIn) -> bool:
    if Image is None or ImageDraw is None:
        return False
    try:
        with Image.open(dst_path) as im:
            im = im.convert("RGBA")
            w, h = im.size

            band_h = max(120, int(h * 0.22))
            band_y = h - band_h

            band = Image.new("RGBA", (w, band_h), (0, 0, 0, 160))
            im.alpha_composite(band, (0, band_y))

            draw = ImageDraw.Draw(im)

            try:
                font_big = ImageFont.load_default()
                font_med = ImageFont.load_default()
                font_small = ImageFont.load_default()
            except Exception:
                font_big = font_med = font_small = None

            title = (overlay.title or "").strip()
            price = (overlay.price or "").strip()
            footer = (overlay.footer or "").strip()

            pad = int(w * 0.04)
            y = band_y + pad

            if title:
                draw.text((pad, y), title[:80], fill=(255, 255, 255, 255), font=font_big, align="left")
                y += int(band_h * 0.35)

            if price:
                draw.text((pad, y), price[:32], fill=(34, 197, 94, 255), font=font_med, align="left")
                y += int(band_h * 0.25)

            if footer:
                draw.text((pad, band_y + band_h - pad - 12), footer[:120], fill=(229, 231, 235, 255), font=font_small, align="left")

            out = im.convert("RGB")
            if dst_path.suffix.lower() == ".webp":
                out.save(dst_path, format="WEBP", quality=90, method=6)
            elif dst_path.suffix.lower() in (".jpg", ".jpeg"):
                out.save(dst_path, format="JPEG", quality=90)
            else:
                out.save(dst_path)
        return True
    except Exception:
        return False


# -------------------- Endpoints --------------------

@router.post("/render")
def render_preview(
    body: PreviewIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Modes:
      - normal  : copy single image -> prev_<ts>.<ext> (+ optional overlay)
                  (ΑΝ use_renderer=true ΚΑΙ υπάρχει pillow_renderer: τότε κάνει render overlay/cta/price)
      - carousel: images[] -> prev_<ts>_frame001..N.webp + prev_<ts>_sheet.webp
      - video   : images (or single) -> prev_<ts>.mp4 (+ poster .jpg)
    """
    mode = _infer_mode(body)
    _ensure_dir(GENERATED_DIR)
    ts_ms = int(time.time() * 1000)

    # ---- NORMAL ----
    if mode == "normal":
        if not body.image_url:
            raise HTTPException(status_code=422, detail="image_url is required for normal mode")

        # Αν ζητήθηκε ρητά ο Pillow renderer και είναι διαθέσιμος,
        # ΔΕΝ αλλάζουμε τα defaults όταν είναι False ή λείπει.
        if bool(body.use_renderer) and pillow_render is not None:
            try:
                # mapping προτεραιότητα: body.mapping -> model_extra.mapping -> derive από επιμέρους πεδία
                mp = None
                try:
                    extra = getattr(body, "model_extra", {}) or {}
                except Exception:
                    extra = {}
                mp = (body.mapping or extra.get("mapping") or {
                    "title": (body.title or "").strip(),
                    "price": (body.new_price or body.price or "").strip(),
                    "old_price": (body.old_price or "").strip(),
                    # μπορεί να έρθει από extra στη συνέχεια· αλλιώς παραλείπεται
                    "discount_badge": (extra.get("discount_badge") or ""),
                    "cta": (body.cta_label or "Δες περισσότερα").strip(),
                })
                rr = pillow_render(
                    image_url=body.image_url,
                    mapping=mp,
                    ratio=(body.ratio or "4:5"),
                    watermark=False,  # το κρατάμε off μέχρι να ζητηθεί ρητά
                    quality=90,
                )
                dst = Path(rr.out_path)
                rel_url = "/" + str(dst).replace(os.sep, "/")
                base = str(request.base_url).rstrip("/")
                abs_url = f"{base}{rel_url}"

                # image_check στο ΤΟΠΙΚΟ αρχείο που μόλις φτιάξαμε
                ic_echo = None
                try:
                    ic_echo = analyze_image(str(dst))
                except Exception as e:
                    logger.warning("IC(renderer) analyze failed src=%s err=%s", dst, e)
                    ic_echo = None

                _mode_in = (body.style or body.mode or "normal") or "normal"
                _mode_out = "normal" if str(_mode_in).lower().strip() in {"image", "img", "picture", "photo"} else _mode_in
                _new_price = body.new_price or body.price

                return {
                    "preview_id": f"prev_{ts_ms}",
                    "preview_url": rel_url,
                    "url": rel_url,
                    "absolute_url": abs_url,
                    "mode": _mode_out,
                    "new_price": _new_price,
                    "old_price": body.old_price,
                    "template": body.template,
                    "ratio": body.ratio,
                    "overlay": None,  # το overlay το υλοποιεί ο renderer
                    "overlay_applied": bool(rr.overlay_applied),
                    "image_check": ic_echo,
                    "meta": {"width": rr.width, "height": rr.height},
                }
            except HTTPException:
                raise
            except Exception as e:
                # Σε αποτυχία renderer, πέφτουμε στο παλιό μονοπάτι (copy) για να ΜΗΝ σπάσει τίποτα.
                logger.warning("Pillow renderer failed; falling back to copy-only. err=%s", e)

        # ---- default path (copy-only), ακριβώς όπως πριν ----
        # materialize για να έχουμε σωστό local path
        src = _materialize_image_to_local(body.image_url)
        ext = _ext_from(src, default=".png")
        out_name = f"prev_{ts_ms}{ext}"
        dst = GENERATED_DIR / out_name
        try:
            shutil.copy2(src, dst)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Preview copy failed: {e}")

        overlay_applied = False
        overlay_echo = None
        if body.overlay:
            overlay_echo = body.overlay.model_dump()
            overlay_applied = _apply_overlay_to_image(dst, body.overlay)

        # image_check με ΤΟΠΙΚΟ path (ΟΧΙ /static/ url)
        ic_echo = None
        try:
            ic_echo = getattr(body, "image_check", None) or (getattr(body, "model_extra", {}) or {}).get("image_check")
        except Exception:
            ic_echo = None
        ic_src = str(src)  # <-- κρίσιμο: local fs path
        if ic_echo is None:
            try:
                ic_echo = analyze_image(ic_src)
            except Exception as e:
                logger.warning("IC(normal) analyze failed src=%s err=%s", ic_src, e)
                ic_echo = None
        logger.info("IC(normal) src=%s ic=%s", ic_src, ic_echo)

        rel_url = "/" + str(dst).replace(os.sep, "/")
        base = str(request.base_url).rstrip("/")
        abs_url = f"{base}{rel_url}"
        _mode_in = (body.style or body.mode or "normal") or "normal"
        _mode_out = "normal" if str(_mode_in).lower().strip() in {"image", "img", "picture", "photo"} else _mode_in
        _new_price = body.new_price or body.price
        return {
            "preview_id": f"prev_{ts_ms}",
            "preview_url": rel_url,
            "url": rel_url,
            "absolute_url": abs_url,
            "mode": _mode_out,
            "new_price": _new_price,
            "old_price": body.old_price,
            "template": body.template,
            "ratio": body.ratio,
            "overlay": overlay_echo,
            "overlay_applied": bool(overlay_applied),
            "image_check": ic_echo,
        }

    # ---- CAROUSEL ----
    if mode == "carousel":
        paths = _images_list(body)
        if not paths:
            raise HTTPException(status_code=422, detail="images are required for carousel")

        ic_echo = None
        try:
            ic_echo = getattr(body, "image_check", None) or (getattr(body, "model_extra", {}) or {}).get("image_check")
        except Exception:
            ic_echo = None

        # πάρε το πρώτο raw url, ΚΑΙ materialize για local path
        raw_imgs = None
        try:
            raw_imgs = getattr(body, "model_extra", {}).get("images", None)
        except Exception:
            raw_imgs = None
        urls = _coerce_images_list(raw_imgs if raw_imgs is not None else body.images, getattr(body, "image_url", None))
        first_src = None
        if urls:
            try:
                first_src = str(_materialize_image_to_local(urls[0]))  # local file path
            except Exception as e:
                logger.warning("IC(carousel) materialize failed url=%s err=%s", urls[0], e)
                first_src = None

        if ic_echo is None and first_src:
            try:
                ic_echo = analyze_image(first_src)
            except Exception as e:
                logger.warning("IC(carousel) analyze failed src=%s err=%s", first_src, e)
                ic_echo = None
        logger.info("IC(carousel) first_src=%s ic=%s", first_src, ic_echo)

        # frames
        frame_paths: List[Path] = []
        frame_urls: List[str] = []
        for idx, p in enumerate(paths, start=1):
            out = GENERATED_DIR / f"prev_{ts_ms}_frame{idx:03d}.webp"
            _save_as_webp(p, out)
            frame_paths.append(out)
            frame_urls.append("/" + str(out).replace(os.sep, "/"))

        sheet = GENERATED_DIR / f"prev_{ts_ms}_sheet.webp"
        try:
            _make_contact_sheet(frame_paths, sheet)
        except Exception:
            shutil.copy2(frame_paths[0], sheet)

        rel_url = "/" + str(sheet).replace(os.sep, "/")
        base = str(request.base_url).rstrip("/")
        abs_url = f"{base}{rel_url}"
        return {
            "preview_id": f"prev_{ts_ms}",
            "preview_url": rel_url,
            "url": rel_url,
            "absolute_url": abs_url,
            "mode": "carousel",
            "frames": frame_urls,
            "count": len(frame_urls),
            "image_check": ic_echo,
        }

    # ---- VIDEO ----
    if mode == "video":
        if ImageClip is None:
            raise HTTPException(status_code=500, detail="moviepy not available on server")
        fps = int(body.fps or 30)
        paths = _images_list(body)
        if not paths:
            raise HTTPException(status_code=422, detail="image(s) required for video")

        ic_echo = None
        try:
            ic_echo = getattr(body, "image_check", None) or (getattr(body, "model_extra", {}) or {}).get("image_check")
        except Exception:
            ic_echo = None

        raw_imgs = None
        try:
            raw_imgs = getattr(body, "model_extra", {}).get("images", None)
        except Exception:
            raw_imgs = None
        urls = _coerce_images_list(raw_imgs if raw_imgs is not None else body.images, getattr(body, "image_url", None))
        first_src = None
        if urls:
            try:
                first_src = str(_materialize_image_to_local(urls[0]))  # local file path
            except Exception as e:
                logger.warning("IC(video) materialize failed url=%s err=%s", urls[0], e)
                first_src = None

        if ic_echo is None and first_src:
            try:
                ic_echo = analyze_image(first_src)
            except Exception as e:
                logger.warning("IC(video) analyze failed src=%s err=%s", first_src, e)
                ic_echo = None
        logger.info("IC(video) first_src=%s ic=%s", first_src, ic_echo)

        # duration logic
        if body.duration_sec and body.duration_sec > 0:
            total = float(body.duration_sec)
        elif body.duration and body.duration > 0:
            total = float(body.duration)
        elif len(paths) > 1:
            total = min(15.0, 3.0 * len(paths))
        else:
            total = 12.0
        seg = max(0.5, total / max(1, len(paths)))

        clips = [ImageClip(str(p)).set_duration(seg) for p in paths]
        video = concatenate_videoclips(clips, method="compose").set_fps(fps)

        added_audio = False
        if body.audio_url:
            a_loc = _materialize_audio_to_local(body.audio_url)
            if a_loc and a_loc.exists():
                try:
                    a_clip = AudioFileClip(str(a_loc))
                    bed = audio_loop(a_clip, duration=video.duration)
                    video = video.set_audio(bed)
                    added_audio = True
                except Exception:
                    pass
        if not added_audio and _set_music_bed is not None:
            try:
                bucket = body.music_bucket or BUCKET_BY_PLATFORM.get((body.platform or "").lower(), "ambient")
                video = _set_music_bed(video, bucket=bucket)
            except Exception:
                pass

        mp4 = GENERATED_DIR / f"prev_{ts_ms}.mp4"
        poster = mp4.with_suffix(".jpg")
        try:
            video.write_videofile(str(mp4), fps=fps, audio_codec="aac", audio_bitrate="192k")
        finally:
            try:
                for c in clips:
                    c.close()
                video.close()
            except Exception:
                pass

        _ = _video_poster(mp4)
        rel_url = "/" + str(mp4).replace(os.sep, "/")
        base = str(request.base_url).rstrip("/")
        abs_url = f"{base}{rel_url}"
        return {
            "preview_id": f"prev_{ts_ms}",
            "preview_url": rel_url,
            "url": rel_url,
            "absolute_url": abs_url,
            "mode": "video",
            "fps": fps,
            "duration": total,
            "poster_url": "/" + str(poster).replace(os.sep, "/") if poster.exists() else None,
            "image_check": ic_echo,
        }

    raise HTTPException(status_code=422, detail=f"Unsupported mode: {mode}")


@router.post("/commit")
def commit_preview(
    body: CommitIn,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    wait: bool = Query(False, description="Περίμενε να υπάρξει το αρχείο πριν το commit"),
    timeout: int = Query(60, ge=1, le=300),
):
    """
    Debit 1 credit και αντιγραφή preview -> post_*.
    """
    credits = int(getattr(current_user, "credits", 0) or 0)
    if credits < 1:
        raise HTTPException(status_code=402, detail="Insufficient credits")

    src: Optional[Path] = None
    if body.preview_url:
        src = _to_local_path_under_static(body.preview_url)
    elif body.preview_id:
        _ensure_dir(GENERATED_DIR)
        candidates = sorted(
            [p for p in GENERATED_DIR.glob(f"{body.preview_id}*.*") if p.is_file() and p.name.startswith("prev_")],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            candidates = sorted(
                [p for p in GENERATED_DIR.glob("prev_*.*") if p.is_file()],
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        if candidates:
            src = candidates[0]
    else:
        raise HTTPException(status_code=422, detail="preview_url or preview_id is required")

    if wait:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if src and src.exists():
                break
            time.sleep(1)

    if not src or not src.exists():
        raise HTTPException(status_code=404, detail="Preview file not found")

    ts_ms = int(time.time() * 1000)

    name = src.name
    if name.startswith("prev_") and name.endswith(".mp4"):
        dst = GENERATED_DIR / f"post_{ts_ms}.mp4"
        shutil.copy2(src, dst)
        poster_prev = src.with_suffix(".jpg")
        if poster_prev.exists():
            shutil.copy2(poster_prev, GENERATED_DIR / f"post_{ts_ms}.jpg")
        rel_url = "/" + str(dst).replace(os.sep, "/")
        base = str(request.base_url).rstrip("/")
        abs_url = f"{base}{rel_url}"

        current_user.credits = credits - 1
        db.add(current_user); db.commit(); db.refresh(current_user)

        return {
            "ok": True,
            "preview_id": body.preview_id,
            "committed_url": rel_url,
            "absolute_url": abs_url,
            "remaining_credits": int(current_user.credits),
            "extra": {"poster": f"/static/generated/post_{ts_ms}.jpg" if (GENERATED_DIR / f"post_{ts_ms}.jpg").exists() else None}
        }

    if "_sheet." in name or "_frame" in name:
        base_prefix = name.split("_sheet")[0].split("_frame")[0]
        frames = sorted(GENERATED_DIR.glob(f"{base_prefix}_frame*.webp"))
        if not frames and "_frame" in name:
            frames = [src]
        if not frames:
            raise HTTPException(status_code=404, detail="No carousel frames found")
        out_urls: List[str] = []
        for f in frames:
            idx_part = f.stem.split("_frame")[-1]
            dst = GENERATED_DIR / f"post_{ts_ms}_frame{idx_part}.webp"
            shutil.copy2(f, dst)
            out_urls.append("/" + str(dst).replace(os.sep, "/"))
        rel_url = out_urls[0]
        base = str(request.base_url).rstrip("/")
        abs_url = f"{base}{rel_url}"

        current_user.credits = credits - 1
        db.add(current_user); db.commit(); db.refresh(current_user)

        return {
            "ok": True,
            "preview_id": body.preview_id,
            "committed_url": rel_url,
            "absolute_url": abs_url,
            "remaining_credits": int(current_user.credits),
            "frames": out_urls,
        }

    ext = src.suffix or ".png"
    if ext.lower() not in DEF_EXTS:
        ext = ".png"
    dst = GENERATED_DIR / f"post_{ts_ms}{ext}"
    shutil.copy2(src, dst)
    rel_url = "/" + str(dst).replace(os.sep, "/")
    base = str(request.base_url).rstrip("/")
    abs_url = f"{base}{rel_url}"

    current_user.credits = credits - 1
    db.add(current_user); db.commit(); db.refresh(current_user)

    return {
        "ok": True,
        "preview_id": body.preview_id,
        "committed_url": rel_url,
        "absolute_url": abs_url,
        "remaining_credits": int(current_user.credits),
    }


@router.get("/committed")
def list_committed(
    request: Request,
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
):
    base = str(request.base_url).rstrip("/")
    _ensure_dir(GENERATED_DIR)

    post_files: List[Path] = sorted(
        [p for p in GENERATED_DIR.glob("post_*.*") if p.is_file() and not p.name.endswith(".jpg")],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    files = post_files or sorted(
        [p for p in GENERATED_DIR.glob("prev_*.*") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    total = len(files)
    slice_files = files[offset: offset + limit]

    items, images, committed = [], [], []
    for p in slice_files:
        rel = "/" + str(p).replace(os.sep, "/")
        abs_url = f"{base}{rel}"
        ts = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat().replace("+00:00", "Z")
        items.append({"url": rel, "absolute_url": abs_url, "created_at": ts})
        images.append(abs_url)
        committed.append({"url": abs_url, "created_at": ts})

    return {
        "items": items,
        "images": images,
        "results": images,
        "committed": committed,
        "limit": limit,
        "offset": offset,
        "count": total,
    }
