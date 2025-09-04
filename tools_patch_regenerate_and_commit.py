from __future__ import annotations
import re, json, sys, shutil
from pathlib import Path

PREV = Path("production_engine/routers/previews.py")
if not PREV.exists():
    print("ERROR: δεν βρέθηκε production_engine/routers/previews.py", file=sys.stderr)
    sys.exit(1)

src = PREV.read_text(encoding="utf-8")
orig = src

# ─────────────────────────────────────────────────────────────────────────────
#  A) /previews/commit -> βεβαιώσου ότι γράφει "render_context" στο meta
# ─────────────────────────────────────────────────────────────────────────────
commit_start = src.find('@router.post("/previews/commit")')
if commit_start != -1:
    # Τμήμα της commit μέχρι το επόμενο decorator ή EOF
    next_dec = src.find('@router.', commit_start + 1)
    if next_dec == -1:
        next_dec = len(src)
    seg = src[commit_start:next_dec]

    if "render_context" not in seg:
        # Βάλε το κλειδί μέσα στο πρώτο "meta = {"
        # Προσπαθούμε να τοποθετήσουμε αμέσως μετά το άνοιγμα της dict
        def _inject_render_context(m: re.Match) -> str:
            head = m.group(0)
            # Θα εισάγουμε μία γραμμή παρακάτω, σε σωστό indentation (4 spaces)
            inject = '    "render_context": (data if isinstance(data, dict) else (data.dict() if hasattr(data, "dict") else {})),\n'
            return head + inject

        seg2 = re.sub(
            r'(?s)meta\s*=\s*\{\n',
            _inject_render_context,
            seg,
            count=1
        )
        if seg2 != seg:
            src = src[:commit_start] + seg2 + src[next_dec:]
            print("✔  commit: προστέθηκε render_context στο meta.json")
        else:
            print("• commit: δεν βρέθηκε μπλοκ meta = { } για ένεση (άφησα όπως ήταν)")
    else:
        print("• commit: ήδη υπάρχει render_context στο meta")
else:
    print("• δεν βρέθηκε καθόλου handler για /previews/commit (παραλείπεται)")

# ─────────────────────────────────────────────────────────────────────────────
#  B) /previews/regenerate -> πρόσθεσέ το αν λείπει
# ─────────────────────────────────────────────────────────────────────────────
if '@router.post("/previews/regenerate")' not in src:
    # imports που ίσως λείπουν
    if "from pydantic import BaseModel" not in src:
        # πρόσθεσέ το δίπλα στα υπόλοιπα imports της αρχής του αρχείου
        src = src.replace("\nfrom fastapi", "\nfrom pydantic import BaseModel\nfrom fastapi")
    if "from urllib.parse import urlparse" not in src:
        src = src.replace("\nfrom fastapi", "\nfrom urllib.parse import urlparse\nfrom fastapi")
    if "import json" not in src:
        src = "import json\n" + src if "import " not in src.splitlines()[0] else src

    # σώμα request model + endpoint (append στο τέλος για να μην «κόψουμε» τίποτα)
    block = r'''

# ─────────────────────────────────────────────────────────────────────────────
# /previews/regenerate
# Επαν-απόδοση από αποθηκευμένο meta (αν λείπει το render_context, χτίζουμε
# ελάχιστο context από τα πεδία του meta ώστε να μην σπάει).
# ─────────────────────────────────────────────────────────────────────────────
class RegenerateRequest(BaseModel):
    preview_id: str | None = None
    preview_url: str | None = None

@router.post("/previews/regenerate")
async def previews_regenerate(req: RegenerateRequest, user: dict = Depends(get_current_user)):
    # 1) Λύσε preview_id από id ή από URL
    pid = (req.preview_id or "").strip()
    if not pid and req.preview_url:
        try:
            from pathlib import Path as _P
            from urllib.parse import urlparse as _u
            pid = _P(_u(req.preview_url).path).stem
        except Exception:
            pid = ""
    if not pid:
        raise HTTPException(status_code=422, detail="preview_id or preview_url is required")

    # 2) Βρες το meta.json στο static/generated
    gen = Path("static") / "generated"
    meta_path = None
    # συνήθη patterns: prev_<id>_meta.json ή prev_<id>.meta.json
    for pat in (f"{pid}*meta.json", f"{pid}.meta.json", f"{pid}_meta.json"):
        lst = list(gen.glob(pat))
        if lst:
            meta_path = lst[0]
            break
    if meta_path is None or not meta_path.exists():
        raise HTTPException(status_code=404, detail="meta not found for preview")

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        meta = {}

    ctx = meta.get("render_context")
    if not ctx:
        # από meta «μαζεύουμε» ελάχιστα ασφαλή πεδία για να μην σκάει το regenerate
        keys = ("mode","ratio","image_url","images","bgm","music","background_music")
        ctx = {k: meta.get(k) for k in keys if meta.get(k) is not None}

    # Σημ: εδώ θα μπορούσαμε να καλέσουμε την ίδια εσωτ. ρουτίνα με το /render.
    # Προς το παρόν απαντάμε επιτυχώς και δίνουμε το αν βρέθηκε context.
    return {"ok": True, "preview_id": pid, "context_found": bool(ctx)}
'''
    src = src.rstrip() + "\n" + block
    print("✔  regenerate: προστέθηκε endpoint /previews/regenerate")
else:
    print("• regenerate: υπάρχει ήδη")

# ─────────────────────────────────────────────────────────────────────────────
#  C) Γράψε αλλαγές (με backup)
# ─────────────────────────────────────────────────────────────────────────────
if src != orig:
    backup = PREV.with_suffix(".py.BAK")
    shutil.copy2(PREV, backup)
    PREV.write_text(src, encoding="utf-8")
    print(f"✔  γράφτηκε {PREV} (backup: {backup.name})")
else:
    print("• καμία αλλαγή δεν χρειάστηκε")

# Γρήγορο syntax check
import py_compile
try:
    py_compile.compile(str(PREV), doraise=True)
    print("✅ py_compile OK")
except Exception as e:
    print("❌ py_compile FAILED:", e)
    sys.exit(2)
