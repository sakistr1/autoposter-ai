from pathlib import Path
import re, textwrap, sys

root = Path.cwd()
schemas_path = root / "schemas.py"
previews_path = root / "production_engine" / "routers" / "previews.py"

def patch_schemas(src: str) -> str:
    out = src

    # 1) Literals για ratio/post_type (αν λείπουν)
    if "AllowedRatio" not in out:
        out = out.replace(
            "# ============================\n# Previews API — STRICT MODELS\n# ============================\n",
            "# ============================\n# Previews API — STRICT MODELS\n# ============================\nfrom typing import Literal as _Literal\n\nAllowedRatio = _Literal['1:1','4:5','9:16']\nAllowedPostType = _Literal['image','video','carousel']\n\n",
            1
        )

    # 2) post_type στο RenderRequest (αν λείπει)
    if re.search(r"class\s+RenderRequest\s*\(BaseModel\):", out):
        out = re.sub(
            r"(class\s+RenderRequest\s*\(BaseModel\):\s*\n(?:\s*\"\"\"[\s\S]*?\"\"\"\s*\n)?)(\s*#\s*βασικά\s*\n)?(\s*ratio:[^\n]+\n\s*mode:[^\n]+\n)",
            r"\1\2\3    post_type: AllowedPostType | str | None = 'image'\n",
            out, count=1
        )

    # 3) Helper _normalize_mode (αν λείπει)
    if "_normalize_mode(" not in out:
        out = out.replace(
            "from datetime import datetime\n",
            "from datetime import datetime\n\n"
            "# ==========================\n"
            "# Helper: mode normalization\n"
            "# ==========================\n"
            "def _normalize_mode(m: Optional[str]) -> str:\n"
            "    s = (m or '').strip().lower()\n"
            "    return {\n"
            "        'κανονικό': 'normal',\n"
            "        'κανονικο': 'normal',\n"
            "        'funny': 'normal',\n"
            "        'professional': 'normal',\n"
            "    }.get(s, s or 'normal')\n\n",
            1
        )

    # 4) Ενίσχυση validate(): whitelist ratio, image_url για normal/copy, >=2 media για video/carousel
    pat = (
        r"(class\s+RenderRequest\s*\(BaseModel\):\s*[\s\S]*?)"
        r"(@classmethod\s*\n\s*def\s+validate\s*\(cls,\s*value\)\s*:[\s\S]*?\n)"
        r"\s*obj\s*=\s*super\(\)\.validate\(value\)[^\n]*\n"
    )
    m = re.search(pat, out)
    if m:
        head = out[:m.end(2)]
        rest = out[m.end(2):]
        logic = textwrap.dedent("""
            obj = super().validate(value)  # BaseModel → αντικείμενο

            # normalize / aliases
            m = _normalize_mode(getattr(obj, "mode", None))
            if not getattr(obj, "image_url", None) and getattr(obj, "product_image_url", None):
                obj.image_url = obj.product_image_url
            if not getattr(obj, "logo_url", None) and getattr(obj, "brand_logo_url", None):
                obj.logo_url = obj.brand_logo_url

            # ratio whitelist
            allowed_ratios = {"1:1","4:5","9:16"}
            r = getattr(obj, "ratio", "4:5") or "4:5"
            if r not in allowed_ratios:
                raise ValueError("ratio must be one of 1:1, 4:5, 9:16")

            # image required in normal/copy
            if m in ("normal", "copy"):
                if not getattr(obj, "image_url", None):
                    raise ValueError("image_url is required for mode=Κανονικό/normal")

            # need >=2 images if post_type or mode is video/carousel
            pt = (getattr(obj, "post_type", None) or "").lower()
            needs_multi = pt in ("video","carousel") or m in ("video","carousel")

            def _count(seq):
                c = 0
                for it in (seq or []):
                    if isinstance(it, str):
                        c += 1
                    elif isinstance(it, dict):
                        if any(k in it for k in ("url","image_url","media_url","path","image")):
                            c += 1
                return c

            if needs_multi:
                total = _count(getattr(obj, "images", None)) \
                        + _count(getattr(obj, "extra_images", None)) \
                        + _count(getattr(obj, "media_urls", None)) \
                        + (1 if getattr(obj, "image_url", None) else 0)
                if total < 2:
                    raise ValueError("post_type=video/carousel requires at least two images/media sources")

            return obj
        """).strip("\n") + "\n"
        out = head + logic + rest.split("return obj", 1)[-1]  # αφαιρούμε παλιό 'return obj' για να μη μείνει έξω από function

    # 5) Model για delete (αν λείπει)
    if "class DeletePreviewRequest(BaseModel):" not in out:
        out += "\n\nclass DeletePreviewRequest(BaseModel):\n    preview_id: str\n"

    return out

def patch_previews(src: str) -> str:
    out = src

    # 1) Στο /render: whitelist ratio + υποχρεωτικό image_url (normal/copy) + local file check
    render_hdr = re.search(r"@router\.post\(\"/render\"\)[\s\S]*?def\s+render_preview\(", out)
    if render_hdr:
        # Βρες το σημείο όπου γίνεται alias image_url/logo_url και κάνε insert αμέσως μετά
        alias_block = re.search(
            r"if\s+not\s+req\.logo_url\s+and\s+req\.brand_logo_url:\s*\n\s*req\.logo_url\s*=\s*req\.brand_logo_url\s*\n",
            out[render_hdr.end():]
        )
        if alias_block:
            ins = render_hdr.end() + alias_block.end()
            inject = textwrap.dedent("""
                # strict ratio whitelist
                if (req.ratio or "4:5") not in {"1:1","4:5","9:16"}:
                    raise HTTPException(422, detail={"error":"bad_ratio","message":"ratio must be one of 1:1, 4:5, 9:16"})

                # if normal/copy, require image_url and ensure local file exists (for local paths)
                if _norm_mode(req.mode) in ("normal","copy"):
                    if not req.image_url:
                        raise HTTPException(422, detail={"error":"missing_image_url","message":"image_url is required for mode=Κανονικό/normal"})
                    s = (req.image_url or "").strip().lower()
                    if not (s.startswith("http://") or s.startswith("https://") or s.startswith("data:") or s.startswith("file:")):
                        p = _abs_from_url(req.image_url)
                        if not p.exists():
                            raise HTTPException(422, detail={"error":"missing_local_file","message":f"local image_url not found: {req.image_url}"})
            """).strip("\n") + "\n"
            out = out[:ins] + inject + out[ins:]

    # 2) Για video/carousel: απαίτηση >=2 media (αν όχι ήδη)
    out = out.replace(
        'if not images:\n            raise HTTPException(400, "No images for video mode")',
        'if not images or len(images) < 2:\n            raise HTTPException(422, detail={"error":"insufficient_media","message":"video mode requires at least two images"})'
    )
    out = out.replace(
        'if not images:\n            raise HTTPException(400, "No images for carousel mode")',
        'if not images or len(images) < 2:\n            raise HTTPException(422, detail={"error":"insufficient_media","message":"carousel mode requires at least two images"})'
    )

    # 3) Endpoint /previews/delete (αν λείπει)
    if '@router.post("/delete")' not in out:
        delete_ep = textwrap.dedent("""
            
            
            @router.post("/delete")
            def delete_preview(req: 'DeletePreviewRequest' = Body(...), user=Depends(get_current_user)):
                pid = (req.preview_id or "").strip()
                if not pid:
                    raise HTTPException(status_code=422, detail={"error":"missing_preview_id"})
                stem = pid if pid.startswith("prev_") else f"prev_{pid}"
                deleted: list[str] = []
                bases = [GENERATED, Path("production_engine/static/generated")]
                for base in bases:
                    base = Path(base)
                    if not base.exists():
                        continue
                    for pattern in (f"{stem}*", f"*{stem}*"):
                        for fp in base.glob(pattern):
                            try:
                                os.remove(fp)
                                deleted.append(str(fp))
                            except IsADirectoryError:
                                shutil.rmtree(fp, ignore_errors=True)
                            except Exception as e:
                                log.warning("delete failed for %s: %s", fp, e)
                return {"ok": True, "preview_id": stem, "deleted_files": deleted, "count": len(deleted)}
        """).rstrip() + "\n"
        out = out.rstrip() + delete_ep

    # 4) Model ορισμός (αν δεν υπάρχει στο previews.py scope)
    if "class DeletePreviewRequest(BaseModel):" not in out:
        out = re.sub(
            r"(class\s+RegenerateRequest\s*\(BaseModel\):[\s\S]*?\n)\n",
            r"\1\nclass DeletePreviewRequest(BaseModel):\n    preview_id: str\n\n",
            out, count=1
        )

    return out

# --- Run patches ---
changed = []
if not schemas_path.exists():
    print("ERROR: Δεν βρέθηκε το schemas.py στο", schemas_path)
    sys.exit(1)
schemas_src = schemas_path.read_text(encoding="utf-8")
schemas_new = patch_schemas(schemas_src)
if schemas_new != schemas_src:
    schemas_path.write_text(schemas_new, encoding="utf-8")
    changed.append(str(schemas_path))

if previews_path.exists():
    previews_src = previews_path.read_text(encoding="utf-8")
    previews_new = patch_previews(previews_src)
    if previews_new != previews_src:
        previews_path.write_text(previews_new, encoding="utf-8")
        changed.append(str(previews_path))
else:
    print("WARNING: Δεν βρέθηκε", previews_path, "- θα πειραχτεί μόνο το schemas.py")

print("OK. Πειράχτηκαν:", changed if changed else "κανένα (ήδη ενημερωμένα).")
