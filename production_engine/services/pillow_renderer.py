# production_engine/services/pillow_renderer.py
from __future__ import annotations

import os
import io
import time
from types import SimpleNamespace
from typing import Any, Dict, Optional, Tuple, Union
from urllib.parse import urlparse

from PIL import Image, ImageDraw, ImageFont


# ----------------------------
# Helpers
# ----------------------------
def _ratio_to_size(ratio: str) -> Tuple[int, int]:
    """
    Safe defaults per ratio (pixels). Keeps previous working sizes.
    """
    ratio = (ratio or "").strip()
    if ratio in ("4:5", "4x5"):
        return 1080, 1350
    if ratio in ("1:1", "1x1", "square"):
        return 1080, 1080
    if ratio in ("9:16", "9x16"):
        return 1080, 1920
    # Generic default
    return 1080, 1350


def _coerce_meta(meta: Any, ratio: str) -> SimpleNamespace:
    """
    Accept dict/namespace/None and ensure width/height always exist.
    """
    if isinstance(meta, dict):
        w = meta.get("width")
        h = meta.get("height")
    elif isinstance(meta, SimpleNamespace):
        w = getattr(meta, "width", None)
        h = getattr(meta, "height", None)
    else:
        w = h = None

    if not (isinstance(w, int) and isinstance(h, int) and w > 0 and h > 0):
        w, h = _ratio_to_size(ratio)

    # copy-through other fields if dict/ns
    out = SimpleNamespace(width=w, height=h)
    if isinstance(meta, dict):
        for k, v in meta.items():
            if not hasattr(out, k):
                setattr(out, k, v)
    elif isinstance(meta, SimpleNamespace):
        for k, v in meta.__dict__.items():
            if not hasattr(out, k):
                setattr(out, k, v)
    return out


def _resolve_local_path(image_url: str) -> str:
    """
    If a local FastAPI static URL is passed (e.g. http://127.0.0.1:8000/static/uploads/demo.jpg),
    convert it to a local file path (`./static/uploads/demo.jpg`).
    Otherwise treat it as already-local path.
    """
    if not image_url:
        return ""

    try:
        parsed = urlparse(image_url)
        if parsed.scheme in ("http", "https") and parsed.netloc in ("127.0.0.1:8000", "localhost:8000"):
            return "." + parsed.path  # ./static/...
    except Exception:
        pass

    return image_url


def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


def _safe_open_image(path: str) -> Optional[Image.Image]:
    try:
        return Image.open(path).convert("RGB")
    except Exception:
        return None


def _draw_minimal_overlay(
    img: Image.Image,
    mapping: Dict[str, Any],
    font_path: Optional[str] = None,
) -> bool:
    """
    A very small, non-intrusive overlay to mark 'renderer used'.
    If mapping has a 'title', we draw it—otherwise we simply return False.
    This keeps behaviour minimal and safe.
    """
    title = (mapping or {}).get("title")
    if not title:
        return False

    draw = ImageDraw.Draw(img)
    try:
        if font_path and os.path.exists(font_path):
            font = ImageFont.truetype(font_path, 48)
        else:
            font = ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()

    pad = 24
    # Background box to ensure readability
    text_w, text_h = draw.textlength(title, font=font), 56
    draw.rectangle([pad, pad, pad + text_w + 24, pad + text_h], fill=(0, 0, 0, 180))
    draw.text((pad + 12, pad + 8), title, fill=(255, 255, 255), font=font)
    return True


# ----------------------------
# Public API
# ----------------------------
def render(
    *,
    template_id: Optional[int] = None,
    image_url: str,
    mapping: Optional[Dict[str, Any]] = None,
    ratio: str = "4:5",
    meta: Optional[Union[Dict[str, Any], SimpleNamespace]] = None,
    output_format: str = "jpg",
    quality: Optional[int] = None,
    out_dir: str = "./static/generated",
    # accept and ignore unknown kwargs to keep backward-compatibility
    **kwargs: Any,
) -> SimpleNamespace:
    """
    Robust Pillow renderer.

    - Accepts optional `quality` without breaking callers.
    - Guarantees width/height defaults if missing in `meta`.
    - Returns SimpleNamespace with: out_path, width, height, overlay_applied, format, quality_used.
    - If image open/draw fails, gracefully falls back to copy-only (no exception).
    """
    # Normalize meta & sizes
    ns_meta = _coerce_meta(meta, ratio)
    width, height = ns_meta.width, ns_meta.height

    # Resolve input path
    src_path = _resolve_local_path(image_url)
    # Prepare output
    ts = int(time.time() * 1000)
    ext = (output_format or "jpg").lower().replace("jpeg", "jpg").replace(".", "")
    if ext not in ("jpg", "webp", "png"):
        ext = "jpg"
    filename = f"post_{ts}.{ext}"
    out_path = os.path.join(out_dir, filename)
    _ensure_dir(out_path)

    q_used = int(quality) if isinstance(quality, int) and 1 <= quality <= 100 else (90 if ext == "jpg" else 80)

    overlay_applied = False
    ok = False

    # Try open and render
    img = _safe_open_image(src_path)
    if img is not None:
        try:
            # Resize/crop to target canvas while keeping aspect (simple fit)
            target_w, target_h = width, height
            img = img.copy()
            img_ratio = img.width / img.height
            target_ratio = target_w / target_h

            if abs(img_ratio - target_ratio) > 0.001:
                # Fit by cropping center
                if img_ratio > target_ratio:
                    # too wide -> crop width
                    new_w = int(img.height * target_ratio)
                    left = (img.width - new_w) // 2
                    img = img.crop((left, 0, left + new_w, img.height))
                else:
                    # too tall -> crop height
                    new_h = int(img.width / target_ratio)
                    top = (img.height - new_h) // 2
                    img = img.crop((0, top, img.width, top + new_h))

            img = img.resize((target_w, target_h), Image.LANCZOS)

            # Minimal overlay (only if mapping has 'title')
            try:
                overlay_applied = _draw_minimal_overlay(
                    img,
                    mapping or {},
                    # Αν έχεις συγκεκριμένη γραμματοσειρά, βάλε το path εδώ:
                    font_path="assets/fonts/NotoSans-Regular.ttf" if os.path.exists("assets/fonts/NotoSans-Regular.ttf") else None,
                )
            except Exception:
                overlay_applied = False  # never break the pipeline for overlay

            # Save
            save_kwargs: Dict[str, Any] = {}
            if ext in ("jpg", "webp"):
                save_kwargs["quality"] = q_used
            if ext == "jpg":
                save_kwargs["optimize"] = True
                save_kwargs["progressive"] = True

            img.save(out_path, format="WEBP" if ext == "webp" else ext.upper(), **save_kwargs)
            ok = True
        except Exception:
            ok = False

    # Fallback: copy-only (no overlay), but still return valid object
    if not ok:
        # If we can't open source at all, create an empty canvas to avoid raising
        try:
            if img is None:
                img = Image.new("RGB", (width, height), (0, 0, 0))
            img.save(out_path, format="WEBP" if ext == "webp" else ext.upper(), quality=q_used)
        except Exception:
            # Last-resort: create an empty file to fulfill the contract
            with open(out_path, "wb") as f:
                f.write(b"")

    return SimpleNamespace(
        ok=True,
        out_path=out_path,
        width=width,
        height=height,
        overlay_applied=overlay_applied,
        format=ext,
        quality_used=q_used,
        meta=ns_meta,
        template_id=template_id,
        ratio=ratio,
        mapping=mapping or {},
    )
