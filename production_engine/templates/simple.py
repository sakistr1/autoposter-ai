from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
def _font(sz):
    try: return ImageFont.truetype(FONT, sz)
    except: return ImageFont.load_default()

def render_frame(base_img, *, title="", price="", discount=None, brand="", logo_path=None):
    img = base_img.convert("RGBA").copy()
    W, H = img.size
    d = ImageDraw.Draw(img, "RGBA")
    panel_h = int(H * 0.22)
    d.rectangle([(0, H - panel_h), (W, H)], fill=(18,18,22,230))
    x, y = 48, H - panel_h + 24
    if title:
        d.text((x, y), title[:60], font=_font(48), fill=(255,255,255,255)); y += 58
    if price:
        d.text((x, y), price, font=_font(44), fill=(255,255,255,255))
    if discount and discount > 0:
        badge = f"-{discount}%"
        tw, th = d.textbbox((0,0), badge, font=_font(36))[2:]
        bx = W - tw - 64
        by = H - panel_h + 24
        d.rounded_rectangle([(bx-12,by-12),(bx+tw+12,by+th+12)], 18, fill=(234,67,53,230))
        d.text((bx,by), badge, font=_font(36), fill=(255,255,255,255))
    if brand:
        d.text((48, 24), brand, font=_font(32), fill=(255,255,255,220))
    return img
