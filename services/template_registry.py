from __future__ import annotations
import os
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple
from jinja2 import Environment, BaseLoader, StrictUndefined


def _compute_templates_root() -> Path:
    """
    Βρίσκει αξιόπιστα το assets/templates ανεξάρτητα από το working dir.
    - Αν υπάρχει env TEMPLATES_ROOT → το χρησιμοποιεί.
    - Αλλιώς, ψάχνει ανοδικά από το τρέχον αρχείο μέχρι να βρει assets/templates.
    - Τελευταίο fallback: CWD/assets/templates.
    """
    env = os.getenv("TEMPLATES_ROOT")
    if env:
        return Path(env).expanduser().resolve()

    here = Path(__file__).resolve()
    # Ψάξε προς τα πάνω: <base>/assets/templates
    for base in [here.parent] + list(here.parents):
        cand = base / "assets" / "templates"
        if cand.exists():
            return cand.resolve()

    # Fallback στο CWD
    return (Path.cwd() / "assets" / "templates").resolve()


TEMPLATES_ROOT = _compute_templates_root()

AVG_CHAR_WIDTH = 0.58  # χοντρική προσέγγιση για wrapping


def _split_lines(text: str, max_w: float, font_size: int, max_lines: int) -> List[str]:
    """Πολύ απλό word-wrapping με «πλάτος» χαρακτήρα ~0.58*font_size."""
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
    if used < len(words) and lines:
        last = lines[-1]
        lines[-1] = (last[: max(0, cpl - 1)] + "…").rstrip()
    return lines


class TemplateRegistry:
    """
    Παρέχει:
      - get(id) -> rec {id, folder, meta, j2}
      - validate_and_merge(rec, incoming, ratio) -> (context, warnings)
      - render_svg(rec, context) -> svg string
      - list() / detail(id)
    """
    def __init__(self, root: Path | None = None):
        self.root = (root or TEMPLATES_ROOT).resolve()

    # ---------- FS helpers ----------
    def _folder_of(self, template_id: str) -> Path:
        p = self.root / template_id
        if p.exists():
            return p
        # case-insensitive match
        if self.root.exists():
            for c in self.root.iterdir():
                if c.is_dir() and c.name.lower() == template_id.lower():
                    return c
        raise FileNotFoundError(f"Template folder not found: {template_id} (root={self.root})")

    def _load_meta(self, template_id: str) -> Dict[str, Any]:
        folder = self._folder_of(template_id)
        meta_path = folder / "meta.json"
        if not meta_path.exists():
            raise FileNotFoundError(f"meta.json missing for {template_id} (folder={folder})")
        with meta_path.open("r", encoding="utf-8") as f:
            meta = json.load(f)
        if "id" not in meta:
            meta["id"] = template_id
        return meta

    def _load_j2(self, template_id: str) -> str:
        folder = self._folder_of(template_id)
        j2_path = folder / "template.svg.j2"
        if not j2_path.exists():
            raise FileNotFoundError(f"template.svg.j2 missing for {template_id} (folder={folder})")
        return j2_path.read_text("utf-8")

    # ---------- Public API ----------
    def get(self, template_id: str) -> Dict[str, Any]:
        meta = self._load_meta(template_id)
        j2_src = self._load_j2(template_id)
        return {
            "id": meta.get("id", template_id),
            "folder": str(self._folder_of(template_id)),
            "meta": meta,
            "j2": j2_src,
        }

    def list(self) -> List[Dict[str, Any]]:
        """Επιστρέφει summary λίστας templates. Παίζει με ratios= dict ή list."""
        out: List[Dict[str, Any]] = []
        root = self.root
        if not root.exists():
            return out
        for folder in sorted(root.iterdir()):
            if not folder.is_dir():
                continue
            meta_path = folder / "meta.json"
            if not meta_path.exists():
                continue
            try:
                with meta_path.open("r", encoding="utf-8") as f:
                    meta = json.load(f)
                ratios = meta.get("ratios")
                if isinstance(ratios, dict):
                    ratio_list = list(ratios.keys())
                elif isinstance(ratios, list):
                    ratio_list = ratios
                else:
                    ratio_list = []
                out.append({
                    "id": meta.get("id", folder.name),
                    "name": meta.get("name", folder.name),
                    "ratios": ratio_list,
                    "fields": list((meta.get("fields") or {}).keys()),
                    "thumb": f"/assets/templates/{folder.name}/thumb.png" if (folder / "thumb.png").exists() else None,
                })
            except Exception:
                # Αγνόησε «σπασμένο» template, συνέχισε τα υπόλοιπα
                continue
        return out

    def detail(self, template_id: str) -> Dict[str, Any]:
        return self._load_meta(template_id)

    def validate_and_merge(
        self,
        rec: Dict[str, Any],
        incoming: Dict[str, Any],
        ratio: str | None,
    ) -> Tuple[Dict[str, Any], List[str]]:
        meta = rec["meta"]
        warnings: List[str] = []

        # Fields validation
        fields = meta.get("fields") or {}
        required = [k for k, v in fields.items() if v.get("required")]
        missing = [k for k in required if not incoming.get(k) and not (k == "logo_url" and incoming.get("logo"))]
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        # Map 'logo' -> 'logo_url' αν ο caller έστειλε logo
        if "logo" in incoming and "logo_url" not in incoming:
            incoming["logo_url"] = incoming["logo"]

        # Ratios / canvas
        ratios = meta.get("ratios") or {}
        if isinstance(ratios, list):
            # Παλαιά μορφή (χωρίς διαστάσεις) δεν υποστηρίζεται για mapping -> σήκωσε σφάλμα
            raise ValueError("Template 'ratios' must be a dict with width/height/map per ratio.")
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
            "ratio": ratio,
            "W": W,
            "H": H,
            "brand_color": incoming.get("brand_color") or "#0fbf91",
            # pass-through fields
            "title": incoming.get("title"),
            "price": incoming.get("price"),
            "cta": incoming.get("cta") or incoming.get("cta_text"),
            "image_url": incoming.get("image_url"),
            "logo_url": incoming.get("logo_url"),
            # καλό να υπάρχει διαθέσιμο στο template
            "meta": meta,
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
                # άγνωστο kind, πέρασέ το ωμά
                mapped[key] = spec
        ctx["map"] = mapped

        # Σημ.: στο δικό σου commit δεν κάνεις re-render (με watermark off στο preview).
        return ctx, warnings

    def render_svg(self, rec: Dict[str, Any], context: Dict[str, Any]) -> str:
        # Jinja env με helpers που συχνά ζητάνε τα templates
        env = Environment(
            loader=BaseLoader(),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        env.undefined = StrictUndefined
        env.globals.update(
            enumerate=enumerate,
            range=range,
            len=len,
            int=int,
            float=float,
            max=max,
            min=min,
            str=str,
            zip=zip,
        )

        tpl = env.from_string(rec["j2"])
        ctx = dict(context)
        ctx.setdefault("_preview", False)
        # βεβαιώσου ότι υπάρχει και το meta στο context
        ctx.setdefault("meta", rec.get("meta", {}))
        return tpl.render(**ctx)


# Global singleton
REGISTRY = TemplateRegistry()
