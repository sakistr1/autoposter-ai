from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple
from jinja2 import Environment, BaseLoader, StrictUndefined

TEMPLATES_ROOT = Path("assets/templates")

AVG_CHAR_WIDTH = 0.58  # χοντρική προσέγγιση για wrapping

def _split_lines(text: str, max_w: float, font_size: int, max_lines: int) -> List[str]:
    if not text:
        return []
    cpl = max(int(max_w / (font_size * AVG_CHAR_WIDTH)), 4)
    words = text.split()
    lines: List[str] = []
    cur: List[str] = []
    cur_len = 0
    for w in words:
        add = (1 if cur else 0) + len(w)
        if cur_len + add <= cpl:
            cur.append(w)
            cur_len += add
        else:
            lines.append(" ".join(cur))
            cur = [w]
            cur_len = len(w)
        if len(lines) >= max_lines:
            break
    if cur and len(lines) < max_lines:
        lines.append(" ".join(cur))
    used = sum(len(l.split()) for l in lines)
    if used < len(words):
        last = lines[-1]
        lines[-1] = (last[: max(0, cpl - 1)] + "…").rstrip()
    return lines

class TemplateRegistry:
    """
    Παρέχει:
      - get(id) -> rec {id, folder, meta, j2}
      - validate_and_merge(rec, incoming, ratio) -> (context, warnings)
      - render_svg(rec, context) -> svg string
      - list() / detail(id) (αν τις χρειαστείς για /templates endpoints)
    """
    def __init__(self, root: Path | None = None):
        self.root = root or TEMPLATES_ROOT

    # ---------- FS helpers ----------
    def _folder_of(self, template_id: str) -> Path:
        p = self.root / template_id
        if p.exists():
            return p
        # case-insensitive match
        for c in self.root.iterdir():
            if c.is_dir() and c.name.lower() == template_id.lower():
                return c
        raise FileNotFoundError(f"Template folder not found: {template_id}")

    def _load_meta(self, template_id: str) -> Dict[str, Any]:
        folder = self._folder_of(template_id)
        meta_path = folder / "meta.json"
        if not meta_path.exists():
            raise FileNotFoundError(f"meta.json missing for {template_id}")
        with meta_path.open("r", encoding="utf-8") as f:
            meta = json.load(f)
        if "id" not in meta:
            meta["id"] = template_id
        return meta

    def _load_j2(self, template_id: str) -> str:
        folder = self._folder_of(template_id)
        j2_path = folder / "template.svg.j2"
        if not j2_path.exists():
            raise FileNotFoundError(f"template.svg.j2 missing for {template_id}")
        return j2_path.read_text("utf-8")

    # ---------- Public API ----------
    def get(self, template_id: str) -> Dict[str, Any]:
        meta = self._load_meta(template_id)
        j2_src = self._load_j2(template_id)
        return {"id": meta.get("id", template_id), "folder": str(self._folder_of(template_id)), "meta": meta, "j2": j2_src}

    def list(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        if not self.root.exists():
            return out
        for folder in sorted(self.root.iterdir()):
            if not folder.is_dir():
                continue
            meta_path = folder / "meta.json"
            if not meta_path.exists():
                continue
            try:
                with meta_path.open("r", encoding="utf-8") as f:
                    meta = json.load(f)
                out.append({
                    "id": meta.get("id", folder.name),
                    "name": meta.get("name", folder.name),
                    "ratios": list((meta.get("ratios") or {}).keys()),
                    "fields": list((meta.get("fields") or {}).keys()),
                    "thumb": f"/assets/templates/{folder.name}/thumb.png" if (folder / "thumb.png").exists() else None,
                })
            except Exception:
                continue
        return out

    def detail(self, template_id: str) -> Dict[str, Any]:
        return self._load_meta(template_id)

    def validate_and_merge(self, rec: Dict[str, Any], incoming: Dict[str, Any], ratio: str | None) -> Tuple[Dict[str, Any], List[str]]:
        meta = rec["meta"]
        warnings: List[str] = []

        # Fields
        fields = meta.get("fields") or {}
        required = [k for k, v in fields.items() if v.get("required")]
        missing = [k for k in required if not incoming.get(k) and not (k == "logo_url" and incoming.get("logo"))]
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        # Map 'logo' -> 'logo_url' if δόθηκε έτσι από τον caller
        if "logo" in incoming and "logo_url" not in incoming:
            incoming["logo_url"] = incoming["logo"]

        # Ratio
        ratios = meta.get("ratios") or {}
        if not ratios:
            raise ValueError("Template has no ratios")
        if ratio and ratio not in ratios:
            warnings.append(f"Ratio '{ratio}' not supported, falling back to first available.")
            ratio = None
        if not ratio:
            ratio = next(iter(ratios.keys()))
        r = ratios[ratio]
        W, H = int(r.get("width", 1080)), int(r.get("height", 1080))

        # Build context
        ctx: Dict[str, Any] = {
            "ratio": ratio, "W": W, "H": H,
            "brand_color": incoming.get("brand_color") or "#0fbf91",
            # pass through base fields (if template τα χρησιμοποιεί)
            "title": incoming.get("title"),
            "price": incoming.get("price"),
            "cta": incoming.get("cta") or incoming.get("cta_text"),
            "image_url": incoming.get("image_url"),
            "logo_url": incoming.get("logo_url"),
        }

        # Build map per meta
        mapping = r.get("map") or {}
        mapped: Dict[str, Any] = {}
        for key, spec in mapping.items():
            kind = spec.get("kind")
            if kind == "text":
                fs = int(spec.get("font_size", 36))
                ml = int(spec.get("max_lines", 2))
                text_value = incoming.get(key) or ""
                lines = _split_lines(text_value, float(spec.get("w", 600)), fs, ml) if text_value else []
                mapped[key] = {
                    "x": spec.get("x", 0), "y": spec.get("y", 0),
                    "w": spec.get("w", 0), "h": spec.get("h", 0),
                    "align": spec.get("align", "left"),
                    "color": spec.get("color", "#ffffff"),
                    "font_size": fs,
                    "bold": bool(spec.get("bold")),
                    "lines": lines,
                }
            elif kind == "image":
                mapped[key] = {
                    "x": spec.get("x", 0), "y": spec.get("y", 0),
                    "w": spec.get("w", 0), "h": spec.get("h", 0),
                    "mode": spec.get("mode", "cover"),
                    "href": incoming.get(key) or (incoming.get("logo") if key == "logo_url" else ""),
                    "radius": int(spec.get("radius", 0)),
                }
            else:
                mapped[key] = spec
        ctx["map"] = mapped

        # Σημείωση: Στο δικό σου commit δεν υπάρχει re-render → μην ενεργοποιείς watermark στο preview.
        # Αν αργότερα αλλάξεις commit flow σε re-render clean, μπορείς να περάσεις ctx["_preview"] = True για το preview.
        return ctx, warnings

    def render_svg(self, rec: Dict[str, Any], context: Dict[str, Any]) -> str:
        env = Environment(loader=BaseLoader(), autoescape=False)
        env.undefined = StrictUndefined
        tpl = env.from_string(rec["j2"])
        # watermark off by default (βλέπε σχόλιο παραπάνω)
        context = dict(context)
        context.setdefault("_preview", False)
        return tpl.render(**context)

# Global singleton
REGISTRY = TemplateRegistry()
