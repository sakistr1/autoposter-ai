import os, pytest, httpx

BASE = os.getenv("BASE", "http://127.0.0.1:8000")
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    pytest.skip("Set TOKEN env var: TOKEN='Bearer <jwt>'", allow_module_level=True)

def H():
    return {"Authorization": TOKEN, "Content-Type": "application/json"}

def _del(pid: str):
    if pid and pid != "prev_null":
        httpx.post(f"{BASE}/previews/delete", headers=H(), json={"preview_id": pid}, timeout=90)

def test_health_ok():
    r = httpx.get(f"{BASE}/health", timeout=30)
    assert r.status_code == 200, f"status={r.status_code} body={r.text}"

def test_normal_requires_image_url():
    r = httpx.post(f"{BASE}/previews/render", headers=H(),
                   json={"mode":"Κανονικό","ratio":"4:5"}, timeout=120)
    assert r.status_code == 422, f"status={r.status_code} body={r.text}"

def test_bad_ratio_rejected():
    r = httpx.post(f"{BASE}/previews/render", headers=H(),
                   json={"mode":"Κανονικό","ratio":"16:9","image_url":"static/demo/laptop.jpg"}, timeout=120)
    assert r.status_code == 422, f"status={r.status_code} body={r.text}"

def test_normal_ok_commit_and_regenerate():
    r = httpx.post(f"{BASE}/previews/render", headers=H(),
                   json={"mode":"Κανονικό","ratio":"4:5","image_url":"static/demo/laptop.jpg"}, timeout=240)
    assert r.status_code == 200, f"status={r.status_code} body={r.text}"
    data = r.json(); assert "preview_id" in data, f"body={r.text}"
    pid = data["preview_id"]

    c = httpx.post(f"{BASE}/previews/commit", headers=H(), json={"preview_id": pid}, timeout=120)
    assert c.status_code == 200, f"status={c.status_code} body={c.text}"

    g = httpx.post(f"{BASE}/previews/regenerate", headers=H(),
                   json={"preview_id": pid, "max_passes": 1}, timeout=240)
    assert g.status_code == 200, f"status={g.status_code} body={g.text}"

    _del(pid)

def test_video_needs_two_images():
    r = httpx.post(f"{BASE}/previews/render", headers=H(),
                   json={"mode":"video","ratio":"9:16","images":["static/demo/laptop.jpg"]}, timeout=180)
    assert r.status_code == 422, f"status={r.status_code} body={r.text}"

def test_video_ok_and_delete():
    r = httpx.post(f"{BASE}/previews/render", headers=H(),
                   json={"mode":"video","ratio":"9:16",
                         "images":["static/demo/img_9_16.jpg","static/demo/laptop.jpg"]}, timeout=360)
    assert r.status_code == 200, f"status={r.status_code} body={r.text}"
    data = r.json(); assert "preview_id" in data, f"body={r.text}"
    _del(data["preview_id"])

def test_carousel_needs_two_images():
    r = httpx.post(f"{BASE}/previews/render", headers=H(),
                   json={"mode":"carousel","ratio":"1:1","images":["static/demo/img_1_1.jpg"]}, timeout=180)
    assert r.status_code == 422, f"status={r.status_code} body={r.text}"

def test_carousel_ok_and_delete():
    r = httpx.post(f"{BASE}/previews/render", headers=H(),
                   json={"mode":"carousel","ratio":"1:1",
                         "images":["static/demo/img_1_1.jpg","static/demo/shoes3.jpg"]}, timeout=360)
    assert r.status_code == 200, f"status={r.status_code} body={r.text}"
    data = r.json(); assert "preview_id" in data, f"body={r.text}"
    _del(data["preview_id"])
