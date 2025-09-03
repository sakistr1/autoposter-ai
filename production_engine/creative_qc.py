# production_engine/creative_qc.py
import os, json, base64, subprocess, tempfile, textwrap
from typing import Any, Dict, List, Optional

OPENAI_MODEL = os.getenv("OPENAI_CREATIVE_QC_MODEL", "gpt-4o-mini")  # vision+json friendly
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

def _extract_contact_sheet(video_path: str, out_jpg: str) -> Optional[str]:
    """Βγάζει ένα contact-sheet (3 frames) για context στο LLM. Επιστρέφει path ή None."""
    try:
        # 3 frames διάσπαρτα στο timeline, tile=3x1
        cmd = [
            "ffmpeg","-y","-i", video_path,
            "-frames:v","3","-vf","select='not(mod(n, max(n/3,1)))',tile=3x1,scale=900:-1",
            out_jpg
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return out_jpg
    except Exception:
        return None

def _b64(path: str) -> str:
    with open(path,"rb") as f: return base64.b64encode(f.read()).decode("utf-8")

def build_messages(product: Dict[str, Any], images: List[str], preview_video: Optional[str], brand: Dict[str, Any]) -> List[Dict[str, Any]]:
    sys_msg = textwrap.dedent("""
    Είσαι Creative Quality Controller για social ads. Αξιολόγησε οπτικά (σύνθεση/αντίθεση/ταιριαστότητα),
    συμμόρφωση σε 4:5 / 9:16, καταλληλότητα asset (να δείχνει προϊόν), ευκρίνεια, υπερβολικά “busy” κτλ.
    Δώσε ΠΑΝΤΑ καθαρό JSON στη γλώσσα-σχήμα που σου δίνω: ΚΑΜΙΑ άλλη έξοδος.
    Προτίμηση: product-centric, καθαρό φόντο, δυνατό CTA, ισορροπημένο Ken Burns.
    """).strip()

    user_context = {
        "product": {
            "id": product.get("id"),
            "title": product.get("title"),
            "price": product.get("price"),
            "short_copy": product.get("short_copy", "")
        },
        "brand": {
            "colors": brand.get("colors", []),
            "logo_required": brand.get("logo_required", False),
            "tone": brand.get("tone", "clean-minimal")
        },
        "images": images,           # absolute/relative URLs που βλέπει ο άνθρωπος/σύστημα
        "preview_video": preview_video
    }

    messages = [
        {"role":"system","content":sys_msg},
        {"role":"user","content":f"SCHEMA:\n{json.dumps(_schema(), ensure_ascii=False)}"},
        {"role":"user","content":f"CONTEXT:\n{json.dumps(user_context, ensure_ascii=False)}"},
    ]
    return messages

def _schema() -> Dict[str, Any]:
    return {
      "verdict":"approve|revise|reject",
      "priority":"low|medium|high",
      "issues":[{"id":"composition|color|text|asset_mismatch|low_quality|brand","severity":"low|med|high","msg":"..."}],
      "instructions":[{"op":"rerender|reorder_images|replace_image|kenburns|contrast|saturation|add_overlay|bgm|crop|resize|speed|cta_copy","params":{}}],
      "alt_copy":{"headline":"","subline":"","cta":"","hashtags":[]},
      "assets":{"keep":[],"replace":[{"slot":1,"reason":"","hint":""}]}
    }

def _infer_image_inputs(images: List[str], contact_sheet_b64: Optional[str]) -> List[Dict[str, Any]]:
    content: List[Dict[str, Any]] = []
    # κείμενο: οδηγία να επιστρέψει ΜΟΝΟ JSON
    content.append({"type":"text","text":"Απάντησε ΜΟΝΟ με το JSON του SCHEMA."})
    if contact_sheet_b64:
        content.append({"type":"image","image_url":{"url":f"data:image/jpeg;base64,{contact_sheet_b64}"}})
    for url in images[:4]:
        # Αν είναι http/https, το API θα το διαβάσει από εκεί. Αλλιώς μπορείς να περάσεις data URI με base64.
        if url.startswith("http"):
            content.append({"type":"image_url","image_url": {"url": url}})
        else:
            pass
    return content

def run_creative_qc(product: Dict[str,Any], images: List[str], preview_video_path: Optional[str], brand: Dict[str,Any]) -> Dict[str,Any]:
    """Επιστρέφει το JSON του LLM ή safe fallback."""
    # contact-sheet (προαιρετικό αλλά βοηθά πολύ το vision)
    contact_b64 = None
    if preview_video_path:
        tmp = tempfile.NamedTemporaryFile(prefix="cs_", suffix=".jpg", delete=False).name
        if _extract_contact_sheet(preview_video_path, tmp):
            contact_b64 = _b64(tmp)

    messages = build_messages(product, images, preview_video_path, brand)
    # Παράθυρο με multimodal content
    if contact_b64 or images:
        messages.append({"role":"user","content": _infer_image_inputs(images, contact_b64)})

    try:
        # OpenAI client (python SDK)
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)

        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.3,
            response_format={"type":"json_object"},
            max_tokens=700
        )
        raw = resp.choices[0].message.content
        data = json.loads(raw)
        return {"ok": True, "data": data, "raw": raw}
    except Exception as e:
        # safe fallback – approve με χαμηλή προτεραιότητα ώστε να μην μπλοκάρουμε ροή
        return {
            "ok": False,
            "error": str(e),
            "data": {
              "verdict":"approve","priority":"low",
              "issues":[], "instructions":[],
              "alt_copy":{"headline":"","subline":"","cta":"","hashtags":[]},
              "assets":{"keep":images,"replace":[]}
            }
        }
