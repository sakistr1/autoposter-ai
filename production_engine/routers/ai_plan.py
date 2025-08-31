# (αν δεν το έχεις ήδη γράψει)
cat > ai_plan.py <<'PY'
import random
def ai_plan(params: dict) -> dict:
    captions = [
        "🔥 Νέο προϊόν σε προσφορά!",
        "✨ Κάνε level-up στο στυλ σου!",
        "⚡ Μην χάσεις αυτή την ευκαιρία!",
        "🎯 Το χρειάζεσαι σήμερα!",
        "💎 Premium ποιότητα, μοναδική τιμή!"
    ]
    caption = random.choice(captions)
    ctas = ["Αγόρασέ το", "Δες περισσότερα", "Κάνε το δικό σου", "Shop Now"]
    mapping = {
        "title": "DEMO AUTO-PLAN",
        "price": "€29,90",
        "old_price": "€39,90",
        "discount_badge": "-25%",
        "cta": random.choice(ctas),
        "title_color": "#ffffff",
        "price_color": "#00d084",
        "cta_bg": "#111827",
        "cta_text": "#ffffff",
        "overlay_rgba": "0,0,0,150"
    }
    preview_payload = {
        "mapping": mapping,
        "use_renderer": True,
        "watermark": True,
        "ratio": params.get("ratio") or "4:5"
    }
    return {"caption": caption, "mapping": mapping, "preview_payload": preview_payload}
PY

# Restart uvicorn
pkill -f "uvicorn main:app" || true
scripts/dev.sh  # ή: uvicorn main:app --reload --host 127.0.0.1 --port 8000
