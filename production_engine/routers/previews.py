
from __future__ import annotations

from fastapi import Request
from fastapi import HTTPException, Request
import time, json
# production_engine/routers/previews.py

import json, re, time, shutil, sqlite3, typing as t, os, logging, subprocess, tempfile, base64, textwrap
from io import BytesIO
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Body, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from PIL import Image, ImageDraw, ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES = True

logger = logging.getLogger(__name__)
log     = logging.getLogger("uvicorn.error")

# ──────────────────────────────────────────────────────────────────────────────
# Paths / storage
# ──────────────────────────────────────────────────────────────────────────────
STATIC_ROOT   = Path("static").resolve()
GENERATED     = STATIC_ROOT / "generated"
GENERATED.mkdir(parents=True, exist_ok=True)

ENGINE_DB     = Path("production_engine/engine.db")
SHORTLINK_DB  = Path("static/logs/database.db")
CREDITS_DB    = Path("static/logs/credits.db")

IMG_EXT   = ".jpg"
SHEET_EXT = ".webp"
MP4_EXT   = ".mp4"

router = APIRouter(prefix="/previews", tags=["previews"])

# auth dep
from token_module import get_current_user  # παρέχεται ήδη στο project

# optional utils (fallbacks αν λείπουν)
_img_import_ok = False
try:
    from production_engine.utils.img_utils import (  # type: ignore
        load_image_from_url_or_path, save_image_rgb,
        detect_background_type as _detect_bg, image_edge_density as _edge_den, image_sharpness as _sharp
    )
    _img_import_ok = True
except Exception:
    try:
        from utils.img_utils import (  # type: ignore
            load_image_from_url_or_path, save_image_rgb,
            detect_background_type as _detect_bg, image_edge_density as _edge_den, image_sharpness as _sharp
        )
        _img_import_ok = True
    except Exception:
        _img_import_ok = False

_renderer_import_ok = False
try:
    from production_engine.services.pillow_renderer import pillow_render_v2  # type: ignore
    _renderer_import_ok = True
except Exception:
    try:
        from services.pillow_renderer import pillow_render_v2  # type: ignore
        _renderer_import_ok = True
    except Exception:
        _renderer_import_ok = False

# QR optional
_qr_available = True
try:
    import qrcode  # type: ignore
except Exception:
    _qr_available = False

# ──────────────────────────────────────────────────────────────────────────────
# Helper utils
# ──────────────────────────────────────────────────────────────────────────────
def _ts() -> int: return int(time.time() * 1000)

def make_id(prefix: str) -> str: return f"{prefix}_{_ts()}"

def gen_preview_path(prefix: str, ext: str) -> tuple[str, Path]:
    name = f"{prefix}_{_ts()}{ext}"
    return f"/static/generated/{name}", GENERATED / name

def _abs_from_url(url: str) -> Path:
    s = url.lstrip("/")
    if not s.startswith("static/"):
        s = "static/" + s
    return Path(s).resolve()

def _norm_mode(m: t.Optional[str]) -> str:
    s = (m or "").strip().lower()
    return {
        "video":"video","carousel":"carousel","copy":"copy",
        "κανονικό":"normal","κανονικο":"normal",
        "funny":"normal","professional":"normal",
    }.get(s, "normal")

_price_num = re.compile(r"(\d+(?:[.,]\d+)?)")
def _parse_price(s: t.Optional[str]) -> t.Optional[float]:
    if not s: return None
    m = _price_num.search(s.replace(" ", ""))
    try: return float(m.group(1).replace(",", ".")) if m else None
    except Exception: return None

# credits
def _credits_db():
    CREDITS_DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(CREDITS_DB)
    con.execute("CREATE TABLE IF NOT EXISTS users(sub TEXT PRIMARY KEY, credits INTEGER NOT NULL)")
    return con

def _get_sub(user) -> str: return getattr(user,"sub",None) or getattr(user,"email",None) or "demo@local"

def get_credits(user) -> int:
    sub=_get_sub(user); con=_credits_db()
    row=con.execute("SELECT credits FROM users WHERE sub=?", (sub,)).fetchone()
    if not row:
        con.execute("INSERT INTO users(sub,credits) VALUES(?,?)", (sub,200)); con.commit(); con.close(); return 200
    con.close(); return int(row[0])

def charge_credits(user, amount: int):
    if amount <= 0: return
    sub=_get_sub(user); con=_credits_db()
    row=con.execute("SELECT credits FROM users WHERE sub=?", (sub,)).fetchone()
    cur=max(0,(int(row[0]) if row else 200)-amount)
    if row: con.execute("UPDATE users SET credits=? WHERE sub=?", (cur,sub))
    else:   con.execute("INSERT INTO users(sub,credits) VALUES(?,?)", (sub,cur))
    con.commit(); con.close()

def _read_meta(preview_rel_or_id: str) -> dict | None:
    """Διαβάζει meta από static/generated και (fallback) production_engine/static/generated."""
    name = preview_rel_or_id
    if "/" in name: name = Path(name).stem
    p1 = GENERATED / f"{name}.meta.json"
    p2 = Path("production_engine/static/generated") / f"{name}.meta.json"
    for p in (p1, p2):
        if p.exists():
            try: return json.loads(p.read_text())
            except Exception: ...
    return None

# quality helpers with fallbacks
def detect_background_type(im):
    try: return _detect_bg(im)  # type: ignore
    except Exception: return "unknown"

def image_edge_density(im):
    try: return _edge_den(im)  # type: ignore
    except Exception: return None

def image_sharpness(im):
    try: return _sharp(im)  # type: ignore
    except Exception: return None

def build_image_checks(im) -> dict:
    ed=image_edge_density(im); sh=image_sharpness(im)
    suggestions=[]; 
    if ed is not None and ed < 0.7: suggestions.append("καθάρισε φόντο")
    if sh is not None and sh < 4.0: suggestions.append("βάλε υψηλότερη ανάλυση ή πιο καθαρή φωτο")
    q="unknown"
    if sh is not None: q = "low" if sh<3.5 else ("medium" if sh<6.0 else "high")
    return {"category":"product","background":detect_background_type(im),"quality":q,"suggestions":suggestions,"meta":{"edge_density":ed,"sharpness":sh}}

# hardened image loader (fallback)
if not _img_import_ok:
    def load_image_from_url_or_path(src: str) -> Image.Image:
        s=(src or "").strip()
        try:
            if s.startswith("{") and s.endswith("}"):
                o=json.loads(s); s=o.get("image") or o.get("url") or o.get("path") or s
        except Exception: ...
        try:
            p=Path(s.lstrip("/")); 
            if not p.is_absolute():
                p=(Path("static")/p) if not str(p).startswith("static/") else p
            p=p.resolve()
        except Exception:
            p=Path(s.lstrip("/")).resolve()
        if not p.exists(): raise FileNotFoundError(f"Image path not found: {p}")
        # PIL
        try:
            with Image.open(p) as im:
                im.load(); return im.convert("RGB")
        except Exception as e1: last=f"PIL(path)={e1!s}"
        data=p.read_bytes()
        # Parser
        from PIL import ImageFile as _IF
        try:
            parser=_IF.Parser(); parser.feed(data); im=parser.close(); im.load(); return im.convert("RGB")
        except Exception as e2: last+=f"; PIL(Parser)={e2!s}"
        # BytesIO
        try:
            im=Image.open(BytesIO(data)); im.load(); return im.convert("RGB")
        except Exception as e3: last+=f"; PIL(BytesIO)={e3!s}"
        # OpenCV
        try:
            import numpy as _np, cv2 as _cv2  # type: ignore
            arr=_np.frombuffer(data,dtype=_np.uint8); bgr=_cv2.imdecode(arr,_cv2.IMREAD_COLOR)
            if bgr is None: raise RuntimeError("cv2.imdecode returned None")
            rgb=_cv2.cvtColor(bgr,_cv2.COLOR_BGR2RGB); return Image.fromarray(rgb)
        except Exception as e4:
            last+=f"; OpenCV={e4!s}"; raise RuntimeError(f"Failed to open image '{p}': {last}")
    def save_image_rgb(im, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        im.save(path, "JPEG", quality=92)

# ──────────────────────────────────────────────────────────────────────────────
# Ken Burns & video encode (multi-backend) + ffmpeg helpers
# ──────────────────────────────────────────────────────────────────────────────
def _generate_ken_burns_sequence(images: list[Image.Image], fps=30, seconds_per_image=2.0, zoom=1.08, crossfade_sec=0.35) -> list[Image.Image]:
    if not images: return []
    w,h=images[0].size; base=[]
    for im in images:
        if im.mode!="RGB": im=im.convert("RGB")
        if im.size!=(w,h): im=im.resize((w,h), Image.LANCZOS)
        base.append(im)
    frames=[]; n=max(1,int(seconds_per_image*fps)); nfade=max(0,int(crossfade_sec*fps))
    for idx,im in enumerate(base):
        for t in range(n):
            s=1.0 if n==1 else 1.0+(zoom-1.0)*(t/(n-1))
            cw,ch=int(w/s),int(h/s); x0,y0=(w-cw)//2,(h-ch)//2
            crop=im.crop((x0,y0,x0+cw,y0+ch))
            frames.append(crop.resize((w,h),Image.LANCZOS))
        if idx<len(base)-1 and nfade>0:
            next_im=base[idx+1]; last=frames[-1]
            for k in range(nfade):
                a=(k+1)/nfade; frames.append(Image.blend(last,next_im,a))
    return frames

def _build_video_opencv(frames: list[Image.Image], out_path: Path, fps=30) -> Path:
    if not frames: raise RuntimeError("No frames")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    w,h=frames[0].size
    norm=[]
    for im in frames:
        if im.mode!="RGB": im=im.convert("RGB")
        if im.size!=(w,h): im=im.resize((w,h), Image.LANCZOS)
        norm.append(im)
    frames=norm
    import cv2, numpy as np  # type: ignore
    CAP_FFMPEG=getattr(cv2,"CAP_FFMPEG",None)
    attempts=[
        (CAP_FFMPEG,"mp4v",".mp4"), (None,"mp4v",".mp4"),
        (CAP_FFMPEG,"avc1",".mp4"), (None,"avc1",".mp4"),
        (CAP_FFMPEG,"H264",".mp4"), (None,"H264",".mp4"),
        (None,"MJPG",".avi"), (None,"XVID",".avi"),
    ]
    last_err=None
    for api,fourcc_str,ext in attempts:
        tmp=out_path.with_name(out_path.stem+"_tmp"+ext); final=out_path.with_suffix(ext)
        try:
            if tmp.exists(): tmp.unlink()
            fourcc=cv2.VideoWriter_fourcc(*fourcc_str)
            vw=cv2.VideoWriter(str(tmp), api if api is not None else fourcc, float(fps), (w,h), True) if api is not None else cv2.VideoWriter(str(tmp), fourcc, float(fps), (w,h), True)
            if not vw or not vw.isOpened(): raise RuntimeError(f"VideoWriter open failed (api={api}, fourcc={fourcc_str})")
            for im in frames:
                arr=cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR); vw.write(arr)
            vw.release()
            if not tmp.exists() or tmp.stat().st_size==0: raise RuntimeError("Empty file after release")
            os.replace(tmp, final); log.info("VIDEO ENCODE OK api=%s fourcc=%s -> %s", api,fourcc_str,final.name)
            return final
        except Exception as e:
            last_err=e
            try: 
                if 'vw' in locals(): vw.release()
            except Exception: ...
            try:
                if tmp.exists(): tmp.unlink()
            except Exception: ...
            continue
    raise RuntimeError(f"All writer attempts failed: {last_err!s}")

def _transcode_h264_ffmpeg(src: Path) -> Path | None:
    if not shutil.which("ffmpeg"): return None
    out=src.with_name(src.stem+"_h264.mp4")
    cmd=["ffmpeg","-y","-v","error","-i",str(src),"-vf","format=yuv420p","-r","30","-c:v","libx264","-preset","veryfast","-crf","23","-movflags","+faststart","-an",str(out)]
    try:
        subprocess.run(cmd, check=True)
        if out.exists() and out.stat().st_size>0: log.info("TRANSCODE h264 OK -> %s", out.name); return out
    except Exception as e: log.warning("TRANSCODE h264 failed: %s", e)
    return None

def _transcode_webm_ffmpeg(src: Path) -> Path | None:
    if not shutil.which("ffmpeg"): return None
    out=src.with_name(src.stem+"_vp9.webm")
    cmd=["ffmpeg","-y","-v","error","-i",str(src),"-c:v","libvpx-vp9","-b:v","1.6M","-pix_fmt","yuv420p","-an",str(out)]
    try:
        subprocess.run(cmd, check=True)
        if out.exists() and out.stat().st_size>0: log.info("TRANSCODE webm OK -> %s", out.name); return out
    except Exception as e: log.warning("TRANSCODE webm failed: %s", e)
    return None

def _wait_for_file(path: Path, timeout=30.0, poll=0.3) -> bool:
    deadline=time.time()+timeout
    while time.time()<deadline:
        try:
            if path.stat().st_size>0: return True
        except FileNotFoundError: ...
        time.sleep(poll)
    return False

# BGM helpers
def _mux_audio_ffmpeg(video: Path, audio: Path) -> Path | None:
    if not shutil.which("ffmpeg"): return None
    if not audio.exists() or audio.stat().st_size==0: return None
    out=video.with_name(video.stem+"_bgm"+video.suffix)
    cmd=["ffmpeg","-y","-v","error","-i",str(video),"-i",str(audio),"-c:v","copy","-map","0:v:0","-map","1:a:0","-shortest",str(out)]
    try:
        subprocess.run(cmd, check=True)
        if out.exists() and out.stat().st_size>0: log.info("BGM mux OK -> %s", out.name); return out
    except Exception as e: log.warning("BGM mux failed: %s", e)
    return None

def _resolve_bgm(mapping: dict) -> Path | None:
    url=(mapping or {}).get("bgm_url")
    assets=STATIC_ROOT/"assets"; assets.mkdir(parents=True, exist_ok=True)
    default_mp3=assets/"bgm.mp3"
    if url:
        try:
            if url.startswith("http://") or url.startswith("https://"):
                dest=assets/"bgm_dl.mp3"; urllib.request.urlretrieve(url,dest)
                return dest if dest.exists() and dest.stat().st_size>0 else None
            p=_abs_from_url(url); return p if p.exists() and p.stat().st_size>0 else None
        except Exception as e: log.warning("BGM resolve failed: %s", e)
    if default_mp3.exists() and default_mp3.stat().st_size>0: return default_mp3
    return None

# Creative QC (optional – fallback αν δεν υπάρχει OPENAI_API_KEY)
OPENAI_MODEL   = os.getenv("OPENAI_CREATIVE_QC_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

def _creative_schema() -> dict:
    return {
      "verdict":"approve|revise|reject",
      "priority":"low|medium|high",
      "issues":[{"id":"composition|color|text|asset_mismatch|low_quality|brand","severity":"low|med|high","msg":"..."}],
      "instructions":[{"op":"rerender|reorder_images|replace_image|kenburns|contrast|saturation|add_overlay|bgm|crop|resize|speed|cta_copy","params":{}}],
      "alt_copy":{"headline":"","subline":"","cta":"","hashtags":[]},
      "assets":{"keep":[],"replace":[{"slot":1,"reason":"","hint":""}]}
    }

def _path_to_data_url(p: Path) -> str | None:
    try:
        if not p.exists() or p.stat().st_size==0: return None
        ext=p.suffix.lower(); mime="image/jpeg"
        if ext==".png": mime="image/png"
        if ext==".webp": mime="image/webp"
        b=p.read_bytes()
        return f"data:{mime};base64,{base64.b64encode(b).decode('utf-8')}"
    except Exception: return None

def _make_contact_sheet(video_path: Path) -> Path | None:
    try:
        out=Path(tempfile.NamedTemporaryFile(prefix="cs_",suffix=".jpg",delete=False).name)
        cmd=["ffmpeg","-y","-v","error","-i",str(video_path),"-frames:v","1","-vf","select='not(mod(n, max(n/3,1)))',tile=3x1,scale=900:-1",str(out)]
        subprocess.run(cmd, check=True); 
        return out if out.exists() and out.stat().st_size>0 else None
    except Exception: return None

def _build_creative_messages(product: dict, brand: dict, schema: dict, context: dict) -> list[dict]:
    sys_msg=textwrap.dedent("""
    Είσαι Creative Quality Controller για social ads. Αξιολόγησε οπτικά (σύνθεση/αντίθεση/ταιριαστότητα),
    συμμόρφωση σε 4:5 / 9:16, καταλληλότητα asset (να δείχνει προϊόν), ευκρίνεια, υπερβολικά “busy”.
    Επέστρεψε ΑΠΟΚΛΕΙΣΤΙΚΑ JSON που ταιριάζει στο SCHEMA — χωρίς προλόγους.
    Προτίμηση: product-centric, καθαρό φόντο, δυνατό CTA, ισορροπημένος Ken Burns.
    """).strip()
    return [
        {"role":"system","content":sys_msg},
        {"role":"user","content":f"SCHEMA:\n{json.dumps(schema, ensure_ascii=False)}"},
        {"role":"user","content":f"CONTEXT:\n{json.dumps({'product':product,'brand':brand,**context}, ensure_ascii=False)}"},
        {"role":"user","content":"Απάντησε ΜΟΝΟ με JSON σύμφωνα με το SCHEMA."}
    ]

def _run_creative_qc(product: dict, image_paths: list[Path], video_path: Path | None, brand: dict) -> dict:
    if not OPENAI_API_KEY:
        return {"ok": False, "error":"no_api_key", "data":{"verdict":"approve","priority":"low","issues":[],"instructions":[],"alt_copy":{"headline":"","subline":"","cta":"","hashtags":[]},"assets":{"keep":[str(p) for p in image_paths],"replace":[]}}}
    try:
        from openai import OpenAI  # type: ignore
    except Exception:
        return {"ok": False, "error":"openai_sdk_missing", "data":{"verdict":"approve","priority":"low","issues":[],"instructions":[],"alt_copy":{"headline":"","subline":"","cta":"","hashtags":[]},"assets":{"keep":[str(p) for p in image_paths],"replace":[]}}}
    content=[{"type":"text","text":"JSON ONLY."}]
    if video_path:
        cs=_make_contact_sheet(video_path)
        if cs:
            d=_path_to_data_url(cs)
            if d: content.append({"type":"image_url","image_url":{"url":d}})
            try: cs.unlink(missing_ok=True)
            except Exception: ...
    for p in image_paths[:4]:
        d=_path_to_data_url(p)
        if d: content.append({"type":"image_url","image_url":{"url":d}})
    schema=_creative_schema()
    msgs=_build_creative_messages(product, brand, schema, {"has_video":bool(video_path)})
    msgs.append({"role":"user","content":content})
    try:
        client=OpenAI(api_key=OPENAI_API_KEY)
        resp=client.chat.completions.create(model=OPENAI_MODEL, messages=msgs, temperature=0.3, response_format={"type":"json_object"}, max_tokens=800)
        raw=resp.choices[0].message.content; data=json.loads(raw)
        return {"ok": True, "data": data}
    except Exception as e:
        return {"ok": False, "error":str(e), "data":{"verdict":"approve","priority":"low","issues":[],"instructions":[],"alt_copy":{"headline":"","subline":"","cta":"","hashtags":[]},"assets":{"keep":[str(p) for p in image_paths],"replace":[]}}}

# engine DB helpers (committed history + QC)
def _engine_conn() -> sqlite3.Connection:
    ENGINE_DB.parent.mkdir(parents=True, exist_ok=True)
    con=sqlite3.connect(ENGINE_DB)
    con.execute("CREATE TABLE IF NOT EXISTS committed_posts (id INTEGER PRIMARY KEY AUTOINCREMENT,preview_id VARCHAR NOT NULL,urls_json TEXT NOT NULL,created_at DATETIME DEFAULT (strftime('%s','now')))")
    con.execute("CREATE TABLE IF NOT EXISTS creative_qc (id INTEGER PRIMARY KEY AUTOINCREMENT,preview_id TEXT NOT NULL,verdict TEXT NOT NULL,priority TEXT,json TEXT NOT NULL,created_at DATETIME DEFAULT CURRENT_TIMESTAMP)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_creative_qc_preview ON creative_qc(preview_id)")
    return con

def _record_commit(preview_id: str, media_url: str, thumb_url: str, vtype: str = "video") -> None:
    payload={"media_url":media_url,"thumb_url":thumb_url,"type":vtype}
    urls_json=json.dumps(payload, ensure_ascii=False)
    con=_engine_conn(); cur=con.cursor()
    row=con.execute("SELECT id FROM committed_posts WHERE preview_id=? LIMIT 1",(preview_id,)).fetchone()
    if row:
        cur.execute("UPDATE committed_posts SET urls_json=?, created_at=strftime('%s','now') WHERE id=?", (urls_json, row[0]))
    else:
        cur.execute("INSERT INTO committed_posts(preview_id, urls_json, created_at) VALUES(?,?,strftime('%s','now'))", (preview_id, urls_json))
    con.commit(); con.close()

def _select_committed(limit=10, offset=0) -> list[dict]:
    con=_engine_conn(); con.row_factory=sqlite3.Row
    rows=con.execute("SELECT id, preview_id, urls_json, created_at FROM committed_posts ORDER BY created_at DESC LIMIT ? OFFSET ?", (int(limit),int(offset))).fetchall()
    con.close()
    items=[]
    for r in rows:
        media_url=None; thumb_url=None; vtype=None
        try: payload=json.loads(r["urls_json"] or "{}")
        except Exception: payload={}
        if isinstance(payload, dict):
            media_url=payload.get("media_url") or payload.get("url") or payload.get("href")
            thumb_url=payload.get("thumb_url"); vtype=payload.get("type")
        elif isinstance(payload, list) and payload:
            first=payload[0]
            if isinstance(first, dict):
                media_url=first.get("media_url") or first.get("url") or first.get("href")
                thumb_url=first.get("thumb_url"); vtype=first.get("type")
            elif isinstance(first,str): media_url=first
        elif isinstance(payload,str): media_url=payload
        if not vtype:
            vtype="video" if str(media_url or "").lower().endswith((".mp4",".webm",".avi")) else "image"
        abs_media=f"http://127.0.0.1:8000{media_url}" if (media_url and str(media_url).startswith("/static/")) else media_url
        abs_thumb=f"http://127.0.0.1:8000{thumb_url}" if (thumb_url and str(thumb_url).startswith("/static/")) else thumb_url
        items.append({"id":r["id"],"preview_id":r["preview_id"],"type":vtype,"media_url":media_url,"thumb_url":thumb_url,"absolute_url":abs_media,"thumb_absolute_url":abs_thumb,"created_at":int(r["created_at"]) if str(r["created_at"]).isdigit() else r["created_at"]})
    return items

def _save_creative_qc(preview_id: str, qc: dict):
    try:
        con=_engine_conn()
        data=qc.get("data",{}) if isinstance(qc,dict) else {}
        verdict=str(data.get("verdict","approve")) if isinstance(data,dict) else "approve"
        priority=str(data.get("priority","")) if isinstance(data,dict) else ""
        con.execute("INSERT INTO creative_qc(preview_id, verdict, priority, json) VALUES(?,?,?,?)", (preview_id, verdict, priority, json.dumps(qc, ensure_ascii=False)))
        con.commit(); con.close()
    except Exception as e: log.warning("creative_qc save failed: %s", e)

def _latest_qc_verdict(preview_id: str) -> str | None:
    try:
        con=_engine_conn()
        row=con.execute("SELECT verdict FROM creative_qc WHERE preview_id=? ORDER BY id DESC LIMIT 1",(preview_id,)).fetchone()
        con.close(); return row[0] if row else None
    except Exception: return None

# write meta
def _write_meta(preview_rel: str, meta: dict):
    rel=preview_rel.lstrip("/")
    p=Path(rel); meta_path=p.parent/(p.stem+".meta.json")
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False))

# preview PNG helpers (για video)
GEN_DIR = GENERATED
def _gen(p: str) -> Path: return GEN_DIR / p
def _first_existing(pid: str):
    for c in (_gen(f"{pid}.png"), _gen(f"{pid}_h264_bgm.mp4"), _gen(f"{pid}_h264.mp4"), _gen(f"{pid}.mp4"), _gen(f"{pid}_vp9.webm"), _gen(f"{pid}.webm")):
        if c.exists(): return c
    return None
def _ensure_png(pid: str):
    import shlex
    png=_gen(f"{pid}.png")
    if png.exists(): return png
    media=_first_existing(pid)
    if not media or media.suffix==".png": return png if png.exists() else None
    cmd=f'ffmpeg -y -ss 0 -i {shlex.quote(str(media))} -frames:v 1 -vf thumbnail,scale=720:-2 {shlex.quote(str(png))}'
    subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    return png if png.exists() else None
def _resolve_media_url(pid: str):
    c=_first_existing(pid)
    if not c: return None
    return str(PurePosixPath("/generated")/c.name)

# ──────────────────────────────────────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────────────────────────────────────
class MappingV2(BaseModel):
    title: t.Optional[str] = None
    price: t.Optional[str] = None
    old_price: t.Optional[str] = None
    cta: t.Optional[str] = None
    logo_url: t.Optional[str] = None
    discount_badge: t.Optional[bool] = None
    discount_pct: t.Optional[str] = None
    target_url: t.Optional[str] = None
    qr_enabled: t.Optional[bool] = None
    # bgm_url: Optional[str]

class RenderRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    use_renderer: bool = True
    ratio: str = "4:5"
    mode: t.Optional[str] = "normal"
    image_url: t.Optional[str] = None
    product_image_url: t.Optional[str] = None
    brand_logo_url: t.Optional[str] = None
    logo_url: t.Optional[str] = None
    title: t.Optional[str] = None
    price: t.Optional[str] = None
    old_price: t.Optional[str] = None
    new_price: t.Optional[str] = None
    discount_pct: t.Optional[str] = None
    cta_text: t.Optional[str] = None
    target_url: t.Optional[str] = None
    qr: t.Optional[bool] = None
    ai_bg: t.Optional[str] = None
    ai_bg_prompt: t.Optional[str] = None
    extra_images: t.Optional[list[t.Union[str, dict]]] = None
    images: t.Optional[list[t.Union[str, dict]]] = None
    media_urls: t.Optional[list[t.Union[str, dict]]] = None
    mapping: t.Optional[MappingV2 | dict] = None
    meta: t.Optional[t.Union[dict, str]] = None

class CommitRequest(BaseModel):
    preview_id: t.Optional[str] = None
    preview_url: t.Optional[str] = None

class RegenerateRequest(BaseModel):
    preview_id: str
    max_passes: int = 1

class DeletePreviewRequest(BaseModel):
    preview_id: str

# ──────────────────────────────────────────────────────────────────────────────
# Routes – helpers
# ──────────────────────────────────────────────────────────────────────────────
def _collect_images_from_request(req: RenderRequest) -> list[str]:
    collected: list[t.Union[str, dict]] = []
    for key in ("extra_images","images","media_urls"):
        arr=getattr(req,key,None)
        if arr: collected.extend(arr)
    body=None
    if isinstance(req.meta,str):
        try: body=json.loads(req.meta)
        except Exception: body=None
    elif isinstance(req.meta,dict): body=req.meta
    if isinstance(body,dict):
        imgs=body.get("images") or []
        if imgs: collected.extend(imgs)
    if req.image_url:
        try:
            b2=json.loads(req.image_url); imgs2=(b2 or {}).get("images") or []
            if imgs2: collected.extend(imgs2)
        except Exception:
            collected.append(req.image_url)
    urls=[]; seen=set()
    for it in collected:
        url=it.get("image") or it.get("url") or it.get("path") if isinstance(it,dict) else str(it)
        if url and url not in seen:
            seen.add(url); urls.append(url)
    return urls

# ──────────────────────────────────────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────────────────────────────────────
@router.get("/post_{post_id}.jpg", include_in_schema=False)
def get_post_jpg(post_id: str):
    """Serve /previews/post_{id}.jpg (αν θες και /post_{id}.jpg το έχει το posts.py)."""
    path = GENERATED / f"post_{post_id}.jpg"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Not Found")
    return FileResponse(path, media_type="image/jpeg")

@router.post("/render")
def render_preview(req: RenderRequest = Body(...), user=Depends(get_current_user)):
    ratio=req.ratio or "4:5"; mode=_norm_mode(req.mode)
    if not req.image_url and req.product_image_url: req.image_url=req.product_image_url
    if not req.logo_url and req.brand_logo_url: req.logo_url=req.brand_logo_url

    mapping: dict = {}
    if isinstance(req.mapping, MappingV2):
        try: mapping.update(req.mapping.model_dump(exclude_none=True))
        except Exception: mapping.update(req.mapping.dict(exclude_none=True))  # pydantic v1
    elif isinstance(req.mapping, dict): mapping.update(req.mapping)

    if req.title: mapping.setdefault("title", req.title)
    if req.price: mapping.setdefault("price", req.price)
    if req.old_price: mapping.setdefault("old_price", req.old_price)
    if req.cta_text: mapping.setdefault("cta", req.cta_text)
    if req.logo_url: mapping.setdefault("logo_url", req.logo_url)
    if req.target_url: mapping.setdefault("target_url", req.target_url)
    if req.qr is not None: mapping.setdefault("qr_enabled", bool(req.qr))

    if not mapping.get("discount_pct"):
        of=_parse_price(req.old_price); nf=_parse_price(req.new_price)
        if (of and nf) and of>0 and nf<of:
            mapping["discount_pct"]=f"-{int(round((1-(nf/of))*100))}%"
            mapping.setdefault("discount_badge",True)
    else:
        mapping.setdefault("discount_badge",True)

    def _want_qr_and_url()->tuple[bool,str|None]:
        tgt=req.target_url or mapping.get("target_url")
        want=bool(req.qr) or bool(mapping.get("qr_enabled")) or bool(tgt)
        return want,tgt

    # VIDEO
    if mode=="video":
        images=_collect_images_from_request(req)
        if not images or len(images)<2:
            raise HTTPException(422, detail={"error":"insufficient_media","message":"video mode requires at least two images"})
        missing=[]; bad=[]
        for url in images:
            try:
                p=_abs_from_url(url)
                if not p.exists(): missing.append(url); continue
                _=load_image_from_url_or_path(url)
            except Exception: bad.append(url)
        if missing: raise HTTPException(422, detail={"error":"missing_images","missing":missing})
        if bad: raise HTTPException(422, detail={"error":"bad_images","bad":bad})

        frames=[]
        for url in images:
            im=load_image_from_url_or_path(url)
            if req.ai_bg=="remove":
                try:
                    from rembg import remove  # type: ignore
                    out=remove(im)
                    if isinstance(out,Image.Image): im=out.convert("RGBA")
                    else: im=Image.open(BytesIO(out)).convert("RGBA")
                    bg=Image.new("RGB", im.size, (255,255,255)); bg.paste(im, mask=im.split()[-1]); im=bg
                except Exception as e: log.error("AI BG remove failed: %s", e)
            frames.append(im)

        if _renderer_import_ok:
            rendered=[]
            for im0 in frames:
                try: rendered.append(pillow_render_v2(base_image=im0, ratio=ratio, mapping=mapping).image)
                except Exception: rendered.append(im0)
            frames=rendered

        short_url=None
        want_qr,tgt_url=_want_qr_and_url()
        if want_qr and tgt_url:
            short_url=_create_or_get_shortlink(tgt_url)
            w0,h0=frames[0].size; qr_side=int(max(160,min(0.22*min(w0,h0),360)))
            qr_img=_make_qr_pil(short_url, qr_side); margin=int(0.022*min(w0,h0))
            for i in range(len(frames)): _paste_qr_bottom_right(frames[i], qr_img, margin=margin)

        try:
            kb=_generate_ken_burns_sequence(frames, fps=30, seconds_per_image=2.0, zoom=1.08, crossfade_sec=0.35)
            if kb: frames=kb
        except Exception as e: log.warning("Ken Burns generation failed: %s", e)

        poster_rel, poster_abs = gen_preview_path("prev", IMG_EXT)
        base_rel, base_abs = gen_preview_path("prev", MP4_EXT)
        encode_status=None; real_abs=None
        try:
            real_abs=_build_video_opencv(frames, base_abs, fps=30)
        except Exception as e:
            log.error("VIDEO ENCODE: %s", e); encode_status="error"

        video_ok=False; real_rel=base_rel
        if encode_status is None and real_abs is not None:
            video_ok=_wait_for_file(real_abs, timeout=30.0, poll=0.3)
            if not video_ok:
                log.error("VIDEO ENCODE timeout/empty: %s", real_abs); encode_status="timeout"
            else:
                tr=_transcode_h264_ffmpeg(real_abs)
                if tr and tr.exists() and tr.stat().st_size>0: real_abs=tr
                try: _transcode_webm_ffmpeg(real_abs)
                except Exception: ...
                real_rel=f"/static/generated/{real_abs.name}"

        try: frames[0].convert("RGB").save(poster_abs, "JPEG", quality=92)
        except Exception as e: log.error("POSTER SAVE failed: %s", e)

        try:
            if video_ok:
                bgm=_resolve_bgm(mapping)
                if bgm:
                    mixed=_mux_audio_ffmpeg(real_abs, bgm)  # type: ignore[arg-type]
                    if mixed and mixed.exists() and mixed.stat().st_size>0:
                        real_abs=mixed; real_rel=f"/static/generated/{real_abs.name}"
        except Exception as e: log.warning("BGM step failed: %s", e)

        _write_meta(poster_rel, {"type":"video","frames":len(frames),"cost":5,"render_context":{"mode":"video","ratio":ratio,"images":images,"mapping":mapping}})

        product_ctx={"title":mapping.get("title"),"price":mapping.get("price"),"cta":mapping.get("cta"),"discount_pct":mapping.get("discount_pct")}
        brand_ctx={"colors":[],"logo_required":False,"tone":"clean-minimal"}
        image_paths=[_abs_from_url(u) for u in images]
        try: creative_qc=_run_creative_qc(product_ctx, image_paths, real_abs if video_ok else None, brand_ctx)
        except Exception as e: creative_qc={"ok":False,"error":f"creative_qc_failed: {e}"}
        try:
            preview_id=Path(poster_rel).stem
            if creative_qc: _save_creative_qc(preview_id, creative_qc)
        except Exception as e: log.warning("save creative_qc (video) failed: %s", e)

        return {
            "status":"ok","mode":"video","preview_url":poster_rel,"absolute_url":f"http://127.0.0.1:8000{poster_rel}",
            "short_url":short_url,"video_url": (real_rel if video_ok else None),"encode_status": (None if video_ok else (encode_status or "unknown")),
            "creative_qc": creative_qc
        }

    # CAROUSEL
    if mode=="carousel":
        images=_collect_images_from_request(req)
        if not images or len(images)<2: raise HTTPException(422, detail={"error":"insufficient_media","message":"carousel mode requires at least two images"})
        missing=[]
        for url in images:
            try:
                if not _abs_from_url(url).exists(): missing.append(url)
            except Exception: missing.append(url)
        if missing: raise HTTPException(422, detail={"error":"missing_images","missing":missing})
        frames=[load_image_from_url_or_path(u) for u in images]
        if _renderer_import_ok:
            rendered=[]
            for im0 in frames:
                try: rendered.append(pillow_render_v2(base_image=im0, ratio=ratio, mapping=mapping).image)
                except Exception: rendered.append(im0)
            frames=rendered
        short_url=None
        want_qr,tgt_url=_want_qr_and_url()
        if want_qr and tgt_url:
            short_url=_create_or_get_shortlink(tgt_url)
            w0,h0=frames[0].size; qr_side=int(max(160,min(0.22*min(w0,h0),360)))
            qr_img=_make_qr_pil(short_url, qr_side); margin=int(0.022*min(w0,h0))
            for i in range(len(frames)): _paste_qr_bottom_right(frames[i], qr_img, margin=margin)
        sheet_rel, sheet_abs=gen_preview_path("prev", SHEET_EXT)
        first_rel, first_abs=gen_preview_path("prev", SHEET_EXT)
        frames[0].save(first_abs,"WEBP",quality=90); frames[0].save(sheet_abs,"WEBP",quality=90)
        _write_meta(sheet_rel, {"type":"carousel","frames":len(frames),"cost":len(frames),"render_context":{"mode":"carousel","ratio":ratio,"images":images,"mapping":mapping}})
        product_ctx={"title":mapping.get("title"),"price":mapping.get("price"),"cta":mapping.get("cta"),"discount_pct":mapping.get("discount_pct")}
        brand_ctx={"colors":[],"logo_required":False,"tone":"clean-minimal"}
        image_paths=[_abs_from_url(u) for u in images]
        try: creative_qc=_run_creative_qc(product_ctx, image_paths, None, brand_ctx)
        except Exception as e: creative_qc={"ok":False,"error":f"creative_qc_failed: {e}"}
        try:
            preview_id=Path(sheet_rel).stem
            if creative_qc: _save_creative_qc(preview_id, creative_qc)
        except Exception as e: log.warning("save creative_qc (carousel) failed: %s", e)
        return {"status":"ok","mode":"carousel","preview_url":sheet_rel,"absolute_url":f"http://127.0.0.1:8000{sheet_rel}","sheet_url":sheet_rel,"first_frame_url":first_rel,"short_url":short_url,"plan":{"type":"carousel","ratio":ratio,"image_check":{"category":"product","quality":"ok","background":"clean","suggestions":[],"meta":{}}},"creative_qc":creative_qc}

    # IMAGE
    if mode in ("normal","copy"):
        if not req.image_url: raise HTTPException(422, detail={"error":"missing_image_url","message":"image_url is required for normal mode"})
        try: im=load_image_from_url_or_path(req.image_url)
        except Exception:
            rel,abs_p=gen_preview_path("prev", IMG_EXT)
            im=Image.new("RGB",(1080,1350),(0,0,0)); im.save(abs_p,"JPEG",quality=92)
            _write_meta(rel, {"type":"image","frames":1,"cost":1,"render_context":{"mode":mode,"ratio":ratio,"images":[req.image_url] if req.image_url else [],"mapping":{}}})
            return {"status":"ok","preview_id":Path(rel).stem,"preview_url":rel,"url":rel,"absolute_url":f"http://127.0.0.1:8000{rel}","mode":mode,"ratio":ratio,"overlay_applied":False,"logo_applied":False,"discount_badge_applied":False,"cta_applied":False,"qr_applied":False,"slots_used":{},"safe_area":{"x":0,"y":0,"w":im.width,"h":min(im.height,im.width)},"image_check":{"category":None,"background":"unknown","quality":"unknown","suggestions":[],"meta":{}},"meta":{"width":im.width,"height":im.height}}
        if req.ai_bg=="remove":
            try:
                from rembg import remove  # type: ignore
                out=remove(im)
                if isinstance(out,Image.Image): im=out.convert("RGBA")
                else: im=Image.open(BytesIO(out)).convert("RGBA")
                bg=Image.new("RGB",im.size,(255,255,255)); bg.paste(im,mask=im.split()[-1]); im=bg
            except Exception as e: log.error("AI BG remove failed: %s", e)
        overlay_applied=logo_applied=discount_applied=cta_applied=qr_applied=False
        slots_used={}; safe_area={"x":0,"y":0,"w":im.width,"h":min(im.height,im.width)}
        if _renderer_import_ok:
            try:
                r=pillow_render_v2(base_image=im, ratio=ratio, mapping=mapping)
                im=r.image; overlay_applied=True
                logo_applied=bool(getattr(r,"flags",{}).get("logo_applied"))
                discount_applied=bool(getattr(r,"flags",{}).get("discount_badge_applied"))
                cta_applied=bool(getattr(r,"flags",{}).get("cta_applied"))
                slots_used=getattr(r,"slots",{}) or {}
                safe_area=getattr(r,"safe_area",None) or safe_area
            except Exception: overlay_applied=False
        short_url=None
        want_qr,tgt_url=_want_qr_and_url()
        if want_qr and tgt_url:
            short_url=_create_or_get_shortlink(tgt_url)
            w0,h0=im.size; qr_side=int(max(160,min(0.22*min(w0,h0),360)))
            qr_img=_make_qr_pil(short_url, qr_side); margin=int(0.022*min(w0,h0))
            _paste_qr_bottom_right(im, qr_img, margin=margin); qr_applied=True
        rel,abs_p=gen_preview_path("prev", IMG_EXT)
        save_image_rgb(im, abs_p)
        _write_meta(rel, {"type":"image","frames":1,"cost":1,"render_context":{"mode":mode,"ratio":ratio,"images":[req.image_url] if req.image_url else [],"mapping":mapping}})
        product_ctx={"title":mapping.get("title"),"price":mapping.get("price"),"cta":mapping.get("cta"),"discount_pct":mapping.get("discount_pct")}
        brand_ctx={"colors":[],"logo_required":False,"tone":"clean-minimal"}
        try: creative_qc=_run_creative_qc(product_ctx, [Path(abs_p)], None, brand_ctx)
        except Exception as e: creative_qc={"ok":False,"error":f"creative_qc_failed: {e}"}
        try:
            if creative_qc: _save_creative_qc(Path(rel).stem, creative_qc)
        except Exception as e: log.warning("save creative_qc (image) failed: %s", e)
        return {"status":"ok","preview_id":Path(rel).stem,"preview_url":rel,"absolute_url":f"http://127.0.0.1:8000{rel}","mode":mode,"ratio":ratio,"overlay_applied":overlay_applied,"logo_applied":logo_applied,"discount_badge_applied":discount_applied,"cta_applied":cta_applied,"qr_applied":qr_applied,"slots_used":slots_used,"safe_area":safe_area,"image_check":build_image_checks(im),"short_url":short_url,"creative_qc":creative_qc}

    raise HTTPException(400, f"Unsupported mode '{mode}'")

@router.post("/commit-old")
def commit_preview(req: CommitRequest = Body(...), user=Depends(get_current_user)):
    """
    Commit preview -> post. Δέχεται είτε preview_id είτε preview_url.
    Γράφει και στο ιστορικό (SQLite) με ανθεκτικό schema.
    """
    if not req.preview_id and not req.preview_url:
        raise HTTPException(422, "preview_id or preview_url is required")

    if req.preview_id:
        stem = req.preview_id if req.preview_id.startswith("prev_") else f"prev_{req.preview_id}"
    else:
        stem = Path(req.preview_url).stem  # type: ignore[arg-type]
        if not stem.startswith("prev_"): stem = "prev_" + stem

    # QC gate – μπλοκάρει commit αν τελευταίο verdict != approve
    try:
        qc_verdict=_latest_qc_verdict(stem)
        if qc_verdict and qc_verdict!="approve":
            raise HTTPException(409, detail={"error":"qc_blocked","message":"Το post δεν πέρασε τα κριτήρια ποιότητας.","can_regenerate":True,"preview_id":stem})
    except HTTPException: raise
    except Exception: ...

    prev_mp4=GENERATED/f"{stem}.mp4"
    prev_avi=GENERATED/f"{stem}.avi"
    prev_jpg=GENERATED/f"{stem}.jpg"
    prev_webp=GENERATED/f"{stem}.webp"

    thumb_url=f"/static/generated/{stem}.jpg" if prev_jpg.exists() else (f"/static/generated/{stem}.webp" if prev_webp.exists() else None)

    # Video first
    if prev_mp4.exists() or prev_avi.exists():
        src=prev_mp4 if prev_mp4.exists() else prev_avi
        dst=GENERATED/f"post_{stem[5:]}.mp4"
        if not dst.exists():
            shutil.copy2(src, dst)
            meta=_read_meta(stem) or {}
            cost=int(meta.get("cost",5)); charge_credits(user, cost)
        preview_id=stem

        try: _record_commit(preview_id, f"/static/generated/{dst.name}", thumb_url or "")
        except Exception as e: log.warning("commit history write failed: %s", e)

        # ensure preview PNG for dashboard grid
        try: _ensure_png(preview_id)
        except Exception as _e: logger.warning("ensure_png failed: %s", _e)

        return {"status":"ok","ok":True,"preview_id":preview_id,"committed_url":f"/static/generated/{dst.name}","absolute_url":f"http://127.0.0.1:8000/static/generated/{dst.name}","remaining_credits":get_credits(user)}

    # Image
    if prev_jpg.exists() or prev_webp.exists():
        src=prev_jpg if prev_jpg.exists() else prev_webp
        ext=src.suffix.lower()
        dst=GENERATED/f"post_{stem[5:]}{ext}"
        if not dst.exists():
            shutil.copy2(src, dst)
            meta=_read_meta(stem) or {}
            cost=int(meta.get("cost",1)); charge_credits(user, cost)
        preview_id=stem

        try: _record_commit(preview_id, f"/static/generated/{dst.name}", f"/static/generated/{stem}{ext}")
        except Exception as e: log.warning("commit history write failed: %s", e)

        return {"status":"ok","ok":True,"preview_id":preview_id,"committed_url":f"/static/generated/{dst.name}","absolute_url":f"http://127.0.0.1:8000/static/generated/{dst.name}","remaining_credits":get_credits(user)}

    raise HTTPException(404, f"Preview not found for id/url: {req.preview_id or req.preview_url}")

@router.post("/regenerate")
def regenerate_preview(req: RegenerateRequest = Body(...), user=Depends(get_current_user)):
    stem = req.preview_id if req.preview_id and req.preview_id.startswith("prev_") else f"prev_{req.preview_id}"
    meta=_read_meta(stem)
    if not meta or not isinstance(meta,dict):
        raise HTTPException(404, detail={"error":"not_found","message":"render context not found for preview"})
    rc=meta.get("render_context") or {}
    if not rc:
        raise HTTPException(404, detail={"error":"not_found","message":"render_context missing in meta.json"})

    mode=rc.get("mode") or "video"; ratio=rc.get("ratio") or "4:5"
    images=rc.get("images") or []; mapping=rc.get("mapping") or {}

    try:
        import random as _rnd
        if len(images)>1: _rnd.shuffle(images)
    except Exception: ...

    if mapping and isinstance(mapping,dict):
        if mapping.get("discount_pct") and not mapping.get("discount_badge"): mapping["discount_badge"]=True
        if not mapping.get("cta"): mapping["cta"]="Παράγγειλε τώρα"

    rr=RenderRequest(mode=mode, ratio=ratio, extra_images=images, mapping=mapping, image_url=(images[0] if (mode!="video" and images) else None))
    result=render_preview(req=rr, user=user)

    return {"status":"ok","regenerated":True,"preview_url":result.get("preview_url"),"video_url":result.get("video_url"),"mode":result.get("mode"),"creative_qc":result.get("creative_qc")}

@router.get("/committed")
def list_committed(limit: int = Query(10, ge=1, le=100), offset: int = Query(0, ge=0), user=Depends(get_current_user)):
    items=_select_committed(limit=limit, offset=offset)
    return {"status":"ok","items":items,"count":len(items)}

@router.post("/delete")
def delete_preview(req: DeletePreviewRequest = Body(...), user=Depends(get_current_user)):
    pid=(req.preview_id or "").strip()
    if not pid: raise HTTPException(422, detail={"error":"missing_preview_id"})
    stem=pid if pid.startswith("prev_") else f"prev_{pid}"
    deleted=[]
    for base in [GENERATED, Path("production_engine/static/generated")]:
        base=Path(base)
        if not base.exists(): continue
        for pattern in (f"{stem}*", f"*{stem}*"):
            for fp in base.glob(pattern):
                try:
                    os.remove(fp); deleted.append(str(fp))
                except IsADirectoryError:
                    shutil.rmtree(fp, ignore_errors=True)
                except Exception as e:
                    log.warning("delete failed for %s: %s", fp, e)
    return {"ok":True,"preview_id":stem,"deleted_files":deleted,"count":len(deleted)}


# === Fallback commit χωρίς render-context (PIL, όχι OpenCV) ===
class CommitIn(BaseModel):
    preview_id: str

@router.post("/commit-old")
def commit_preview(body: CommitIn, request: Request):
    pid = body.preview_id.strip()
    if not pid.startswith("prev_"):
        raise HTTPException(status_code=400, detail="invalid preview_id")

    gen = Path("static/generated")
    gen.mkdir(parents=True, exist_ok=True)

    # Βρες source preview από δίσκο
    candidates = [gen / f"{pid}.png", gen / f"{pid}.jpg", gen / f"{pid}.jpeg", gen / f"{pid}.webp"]
    src = next((p for p in candidates if p.exists()), None)
    if not src:
        raise HTTPException(status_code=404, detail=f"Preview image not found on disk for id: {pid}")

    post_id = pid.replace("prev_", "", 1)
    dst = gen / f"post_{post_id}.jpg"

    from PIL import Image  # safe import in handler scope too
    im = Image.open(src)
    if im.mode != "RGB":
        im = im.convert("RGB")
    im.save(dst, "JPEG", quality=92, optimize=True)

    meta = {
        "from_preview": pid,
        "src": f"/generated/{src.name}",
        "dst": f"/generated/{dst.name}",
        "created_at": __import__("time").time().__int__(),
    }
    (gen / f"post_{post_id}.meta.json").write_text(__import__("json").dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    url = f"/generated/{dst.name}"
    abs_url = (str(request.base_url).rstrip("/") + url)
    return {"ok": True, "id": post_id, "url": url, "absolute_url": abs_url}


@router.post("/commit-fallback")
def commit_preview_fallback(payload: dict, request: Request):
    """
    Fallback commit: παίρνει preview_id, βρίσκει το αρχείο prev_<ID>.(png|jpg|jpeg|webp)
    και γράφει post_<ID>.jpg στο static/generated, χωρίς render-context.
    """
    from fastapi import HTTPException
    import time, json
    from pathlib import Path as _Path
    from PIL import Image

    pid = str((payload or {}).get("preview_id", "")).strip()
    if not pid.startswith("prev_"):
        raise HTTPException(status_code=400, detail="invalid preview_id")

    gen = _Path("static/generated")
    gen.mkdir(parents=True, exist_ok=True)

    candidates = [
        gen / f"{pid}.png",
        gen / f"{pid}.jpg",
        gen / f"{pid}.jpeg",
        gen / f"{pid}.webp",
    ]
    src = next((p for p in candidates if p.exists()), None)
    if src is None:
        raise HTTPException(status_code=404, detail=f"Preview image not found on disk for id: {pid}")

    post_id = pid[5:]
    dst = gen / f"post_{post_id}.jpg"

    im = Image.open(src)
    if im.mode != "RGB":
        im = im.convert("RGB")
    im.save(dst, "JPEG", quality=92, optimize=True)

    meta = {
        "from_preview": pid,
        "src": f"/generated/{src.name}",
        "dst": f"/generated/{dst.name}",
        "created_at": int(time.time()),
    }
    (gen / f"post_{post_id}.meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    url = f"/generated/{dst.name}"
    abs_url = (str(getattr(request, "base_url", ""))).rstrip("/") + url if request else None
    return {"ok": True, "id": post_id, "url": url, "absolute_url": abs_url}


@router.post("/commit")
def _commit_proxy_to_fallback(payload: dict, request: Request):
    # Router prefix "/previews" => πλήρες path: /previews/commit
    return commit_preview_fallback(payload, request)
