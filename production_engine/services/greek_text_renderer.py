import os
from typing import List, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont

FONT_DIR = os.path.join(os.path.dirname(__file__), "..", "assets", "fonts")
SYSTEM_FONT_DIRS = [
    "/usr/share/fonts/truetype/noto",
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/truetype/freefont",
]
DEFAULT_REG = ["NotoSans-Regular.ttf", "DejaVuSans.ttf", "FreeSans.ttf"]
DEFAULT_BOLD = ["NotoSans-Bold.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans.ttf", "FreeSansBold.ttf"]

def _find_font(candidates: List[str]) -> Optional[str]:
    for name in candidates:
        local_path = os.path.join(FONT_DIR, name)
        if os.path.isfile(local_path):
            return local_path
        for base in SYSTEM_FONT_DIRS:
            p = os.path.join(base, name)
            if os.path.isfile(p):
                return p
    return None

def load_font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    names = DEFAULT_BOLD if bold else DEFAULT_REG
    path = _find_font(names)
    if path:
        return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()  # fallback (όχι ιδανικό για ελληνικά)

def _wrap_text_by_width(text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.ImageDraw) -> List[str]:
    lines: List[str] = []
    for paragraph in text.split("\n"):
        if paragraph.strip() == "":
            lines.append("")
            continue
        words = paragraph.split(" ")
        line = ""
        for w in words:
            test = (line + " " + w).strip()
            bbox = draw.textbbox((0, 0), test, font=font)
            if (bbox[2] - bbox[0]) <= max_width:
                line = test
            else:
                if line:
                    lines.append(line)
                    line = w
                else:
                    acc = ""
                    for ch in w:
                        t = acc + ch
                        bb = draw.textbbox((0, 0), t, font=font)
                        if (bb[2] - bb[0]) > max_width and acc:
                            lines.append(acc); acc = ch
                        else:
                            acc = t
                    if acc: line = acc
        if line: lines.append(line)
    return lines

def render_text_block(
    draw: ImageDraw.ImageDraw,
    xy: Tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    *,
    fill=(230, 232, 235),
    max_width: int = 800,
    align: str = "left",      # left | center | right
    line_spacing: float = 1.15,
    stroke_width: int = 2,
    stroke_fill=(10, 10, 10),
) -> int:
    x, y = xy
    lines = _wrap_text_by_width(text, font, max_width, draw)
    bbox_ref = draw.textbbox((0, 0), "Ag", font=font)
    lh = max(1, int((bbox_ref[3] - bbox_ref[1]) * line_spacing))
    for line in lines:
        if align != "left":
            bb = draw.textbbox((0, 0), line, font=font)
            w_px = bb[2] - bb[0]
            x_line = x + (max_width - w_px)//2 if align == "center" else x + (max_width - w_px)
        else:
            x_line = x
        if stroke_width > 0:
            draw.text((x_line, y), line, font=font, fill=fill, stroke_width=stroke_width, stroke_fill=stroke_fill)
        else:
            draw.text((x_line, y), line, font=font, fill=fill)
        y += lh
    return y

def render_image_greek(
    out_path: str,
    *,
    size=(1080, 1350),
    bg=(13, 18, 32),
    title="Τίτλος προϊόντος",
    price="",
    cta="Δες περισσότερα",
    brand_logo_path: Optional[str] = None,
) -> str:
    im = Image.new("RGB", size, bg)
    draw = ImageDraw.Draw(im)
    title_fnt = load_font(60, bold=True)
    price_fnt = load_font(48, bold=True)
    cta_fnt   = load_font(44, bold=True)

    y = 80
    y = render_text_block(draw, (64, y), title, title_fnt, max_width=size[0]-128, align="left", stroke_width=2)
    if price:
        y += 24
        y = render_text_block(draw, (64, y), price, price_fnt, max_width=size[0]-128, align="left",
                              stroke_width=2, fill=(72, 228, 120))
    render_text_block(draw, (64, size[1]-140), cta, cta_fnt, max_width=size[0]-128, align="left",
                      stroke_width=2, fill=(200, 210, 255))

    if brand_logo_path and os.path.isfile(brand_logo_path):
        try:
            logo = Image.open(brand_logo_path).convert("RGBA")
            maxw = 240
            ratio = min(maxw / logo.width, 1.0)
            new_size = (int(logo.width * ratio), int(logo.height * ratio))
            logo = logo.resize(new_size, Image.LANCZOS)
            im.paste(logo, (size[0] - new_size[0] - 64, 64), logo)
        except Exception:
            pass

    im.save(out_path, "PNG", optimize=True)
    return out_path
