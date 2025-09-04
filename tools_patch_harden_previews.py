from pathlib import Path
import re, textwrap, sys, py_compile

root = Path.cwd()
schemas_path  = root / "schemas.py"
previews_path = root / "production_engine" / "routers" / "previews.py"

def patch_schemas(txt: str) -> str:
    out = txt

    # (a) Literals για ratio/post_type (αν λείπουν)
    if "AllowedRatio" not in out:
        out = out.replace(
            "# ============================\n# Previews API — STRICT MODELS\n# ============================\n",
            "# ============================\n# Previews API — STRICT MODELS\n# ============================\n"
            "from typing import Literal as _Literal\n\n"
            "AllowedRatio = _Literal['1:1','4:5','9:16']\n"
            "AllowedPostType = _Literal['image','video','carousel']\n\n",
            1
        )

    # (b) Helper _normalize_mode (αν λείπει)
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

    # (c) Πρόσθεσε πεδίο post_type στο RenderRequest αν λείπει
    if re.search(r"class\s+RenderRequest\s*\(BaseModel\):", out) and "post_type" not in out.split("class RenderRequest",1)[1].split("class",1)[0]:
        out = re.sub(
            r"(class\s+RenderRequest\s*\(BaseModel\):\s*\n(?:\s*\"\"\"[\s\S]*?\"\"\"\s*\n)?)(\s*)(ratio:[^\n]+\n\s*mode:[^\n]+\n)",
            r"\1\2\3\2post_type: AllowedPostType | str | None = 'image'\n",
            out, count=1
        )

    # (d) Ενίσχυση validate(): whitelist ratio, image για normal/copy, >=2 media για video/carousel
    # Εισάγεται ΜΕΣΑ στη validate, όχι εκτός.
    m = re.search(r"@classmethod\s*\ndef\s+validate\s*\(cls,\s*value\)\s*:\s*\n", out)
    if m and "ratio must be one of" not in out:
        start = m.end()
        # Βρες το επόμενο 'return obj' ΜΕΣΑ στη validate
        post = out[start:]
        ret = post.find("return obj")
        if ret == -1:
            print("WARN: δεν βρέθηκε 'return obj' μέσα στη validate — δεν αγγίζω.", file=sys.stderr)
        else:
            # κρατάμε το leading indentation της validate
            indent_match = re.search(r"\n([ \t]+)\S", post)
            base_indent = indent_match.group(1) if indent_match else "    "
            logic = textwrap.indent(textwrap.dedent("""
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

                # image required σε normal/copy
                if m in ("normal", "copy"):
                    if not getattr(obj, "image_url", None):
                        raise ValueError("image_url is required for mode=Κανονικό/normal")

                # >=2 media σε video/carousel (από post_type ή mode)
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
            """).strip("\n") + "\n", base_indent)
            post2 = post[:ret] + logic + post[ret:]
            out = out[:start] + post2

    # (e) Μοντέλο DeletePreviewRequest (αν λείπει)
    if "class DeletePreviewRequest(BaseModel):" not in out:
        out += "\n\nclass DeletePreviewRequest(BaseModel):\n    preview_id: str\n"

    return out


def patch_previews(txt: str) -> str:
    s = txt

    # (1) insert checks μέσα στη render_preview: μετά από 'mode = _norm_mode(...)'
    m = re.search(r"def\s+render_preview\s*\([^\)]*\)\s*:\s*\n", s)
    if m and "bad_ratio" not in s:
        # βρες γραμμή με 'mode = _norm_mode(' για να εισάγουμε ακριβώς μετά
        post = s[m.end():]
        mm = re.search(r"^\s*mode\s*=\s*_norm_mode\([^\n]*\)\s*$", post, re.M)
        insert_at = m.end() + (mm.end() if mm else 0)

        # βρες indentation
        ind = "    "  # συνήθως 4 spaces
        inj = textwrap.indent(textwrap.dedent("""
            # strict ratio whitelist (1:1, 4:5, 9:16)
            if (req.ratio or "4:5") not in {"1:1","4:5","9:16"}:
                raise HTTPException(422, detail={"error":"bad_ratio","message":"ratio must be one of 1:1, 4:5, 9:16"})

            # image required σε normal/copy + local file check για τοπικά paths
            if _norm_mode(req.mode) in ("normal","copy"):
                if not req.image_url:
                    raise HTTPException(422, detail={"error":"missing_image_url","message":"image_url is required for mode=Κανονικό/normal"})
                _s = (req.image_url or "").strip().lower()
                if not (_s.startswith("http://") or _s.startswith("https://") or _s.startswith("data:") or _s.startswith("file:")):
                    _p = _abs_from_url(req.image_url)
                    if not _p.exists():
                        raise HTTPException(422, detail={"error":"missing_local_file","message":f"local image_url not found: {req.image_url}"})

            # >=2 media σε video/carousel (early guard)
            try:
                _imgs_all = _collect_images_from_request(req)
            except Exception:
                _imgs_all = (req.images or []) or (req.media_urls or []) or []
            if _norm_mode(req.mode) in ("video","carousel"):
                if not _imgs_all or len(_imgs_all) < 2:
                    raise HTTPException(422, detail={"error":"insufficient_media","message":"video/carousel requires at least two images"})
        """).strip("\n") + "\n", ind)
        s = s[:insert_at] + inj + s[insert_at:]

    # (2) αντικατάσταση παλιών error-strings (αν υπάρχουν) για >=2 media
    s = s.replace(
        'if not images:\n            raise HTTPException(400, "No images for video mode")',
        'if not images or len(images) < 2:\n            raise HTTPException(422, detail={"error":"insufficient_media","message":"video mode requires at least two images"})'
    )
    s = s.replace(
        'if not images:\n            raise HTTPException(400, "No images for carousel mode")',
        'if not images or len(images) < 2:\n            raise HTTPException(422, detail={"error":"insufficient_media","message":"carousel mode requires at least two images"})'
    )

    # (3) πρόσθεσε /previews/delete (αν λείπει)
    if '@router.post("/delete")' not in s:
        delete_ep = textwrap.dedent("""
            
            
            @router.post("/delete")
            def delete_preview(req: DeletePreviewRequest = Body(...), user=Depends(get_current_user)):
                pid = (req.preview_id or "").strip()
                if not pid:
                    raise HTTPException(status_code=422, detail={"error":"missing_preview_id"})
                stem = pid if pid.startswith("prev_") else f"prev_{pid}"
                deleted = []
                for base in [GENERATED, Path("production_engine/static/generated")]:
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
        s = s.rstrip() + "\n\n" + delete_ep

    return s

changed = []

# --- schemas.py ---
if not schemas_path.exists():
    print("ERROR: λείπει το", schemas_path); sys.exit(1)
schemas_src = schemas_path.read_text(encoding="utf-8")
schemas_new = patch_schemas(schemas_src)
if schemas_new != schemas_src:
    schemas_path.write_text(schemas_new, encoding="utf-8")
    changed.append(str(schemas_path))

# --- previews.py ---
if not previews_path.exists():
    print("ERROR: λείπει το", previews_path); sys.exit(1)
prev_src = previews_path.read_text(encoding="utf-8")
prev_new = patch_previews(prev_src)
if prev_new != prev_src:
    previews_path.write_text(prev_new, encoding="utf-8")
    changed.append(str(previews_path))

# compile checks
for fp in [schemas_path, previews_path]:
    py_compile.compile(str(fp), doraise=True)

print("OK. Πειράχτηκαν:", changed if changed else "κανένα (ήδη ενημερωμένα).")
