# production_engine/renderer.py
from typing import Dict, Any

def build_context(meta: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    """Επιστρέφει context για Jinja2: πάντα δίνει 'map' έστω {} για να μην σκάει το template."""
    # meta.get('map', {}) = δομή από meta.json (x,y,w,h,fit,align,max_lines)
    m = meta.get("map", {}) or {}
    ctx = dict(payload)  # title, price, image_url, brand_color, cta, logo_url, κτλ.
    ctx["map"] = m
    # απλά helpers/φρουροί
    if "title" in ctx and isinstance(ctx["title"], str):
        maxc = (m.get("title") or {}).get("max_chars")
        if isinstance(maxc, int) and maxc > 0:
            ctx["title"] = ctx["title"][:maxc]
    if "price" in ctx and isinstance(ctx["price"], str):
        maxc = (m.get("price") or {}).get("max_chars")
        if isinstance(maxc, int) and maxc > 0:
            ctx["price"] = ctx["price"][:maxc]
    return ctx
