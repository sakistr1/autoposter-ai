#!/usr/bin/env python3
import json, os, sys, argparse, urllib.request, urllib.error

def http_get(url, token):
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def pick_image(p):
    for k in ("image", "image_url", "thumbnail", "thumb", "featured_image"):
        v = p.get(k)
        if isinstance(v, str) and v.strip():
            return v
    for k in ("images", "gallery"):
        v = p.get(k)
        if isinstance(v, list) and v:
            first = v[0]
            if isinstance(first, str):
                return first
            if isinstance(first, dict):
                for kk in ("url", "src", "image", "image_url"):
                    if first.get(kk):
                        return first[kk]
    return None

def pick_price(p, currency):
    v = p.get("price")
    if v is None:
        return ""
    s = str(v).strip()
    if any(sym in s for sym in ["€", "$", "£"]):
        return s
    return f"{currency}{s}" if currency else s

def load_products(base, token, limit):
    url = f"{base.rstrip('/')}/me/products"
    data = http_get(url, token)
    items = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        for key in ("items", "data", "results"):
            if isinstance(data.get(key), list):
                items = data[key]
                break
    return items[:limit] if limit else items

def main():
    ap = argparse.ArgumentParser(description="Build bulk.json from /me/products")
    ap.add_argument("--base", default=os.getenv("BASE", "http://127.0.0.1:8000"))
    ap.add_argument("--token", default=os.getenv("TOKEN"))
    ap.add_argument("--template", default="image_left")
    ap.add_argument("--ratios", nargs="+", default=["1:1", "4:5"])
    ap.add_argument("--brand-color", default="#0fbf91")
    ap.add_argument("--cta", default="Δες το")
    ap.add_argument("--currency", default="€")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--out", default="bulk.json")
    args = ap.parse_args()

    if not args.token:
        print("ERROR: set --token or export TOKEN", file=sys.stderr)
        sys.exit(1)

    try:
        prods = load_products(args.base, args.token, args.limit)
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode()}", file=sys.stderr)
        sys.exit(2)

    items = []
    for p in prods:
        name = p.get("name") or p.get("title") or "Untitled"
        img = pick_image(p)
        if not img:
            continue
        price = pick_price(p, args.currency)
        items.append({
            "title": name,
            "price": price,
            "cta": args.cta,
            "image_url": img
        })

    out = {
        "defaults": {
            "template_id": args.template,
            "brand_color": args.brand_color,
            "ratios": args.ratios
        },
        "items": items
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"OK: wrote {args.out} with {len(items)} items")

if __name__ == "__main__":
    main()
