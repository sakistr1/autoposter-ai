import json, sys, sqlite3, argparse
p=argparse.ArgumentParser()
p.add_argument("--db", default="production_engine/engine.db")
p.add_argument("--base", required=True, help="π.χ. http://127.0.0.1:8000")
p.add_argument("--dry-run", action="store_true")
a=p.parse_args()

def to_abs(u, base):
    u=str(u or "")
    if u.startswith("http://") or u.startswith("https://"): return u
    if u.startswith("/"): return base.rstrip("/") + u
    return base.rstrip("/") + "/" + u

con=sqlite3.connect(a.db)
cur=con.cursor()
rows=list(cur.execute("SELECT id, urls_json FROM committed_posts ORDER BY id"))
changed=0
for _id, uj in rows:
    try:
        arr=json.loads(uj or "[]")
    except Exception:
        arr=[]
    arr2=[to_abs(u, a.base) for u in arr]
    if arr2!=arr:
        changed+=1
        if not a.dry_run:
            cur.execute("UPDATE committed_posts SET urls_json=? WHERE id=?", (json.dumps(arr2), _id))
if not a.dry_run:
    con.commit()
print(f"rows={len(rows)} changed={changed} dry_run={a.dry_run}")
