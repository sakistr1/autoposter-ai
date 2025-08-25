(() => {
  const API_BASE = (window.API_BASE || window.location.origin).replace(/\/+$/, "");

  // ---- token helpers ----
  function getToken() {
    const keys = ["token", "access_token", "jwt", "JWT"];
    for (const k of keys) {
      const v = localStorage.getItem(k);
      if (v) return v;
    }
    try {
      const auth = JSON.parse(localStorage.getItem("auth") || "{}");
      if (auth && auth.access_token) return auth.access_token;
    } catch (_) {}
    return null;
  }

  async function postJSON(path, payload) {
    const token = getToken();
    if (!token) throw new Error("Λείπει JWT token στο localStorage (token/access_token). Κάνε login από /auth.html.");

    const res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`
      },
      body: JSON.stringify(payload),
      credentials: "same-origin"
    });

    const text = await res.text();
    let data = {};
    try { data = text ? JSON.parse(text) : {}; } catch (e) {
      throw new Error(`Μη έγκυρο JSON από ${path}: ${text.slice(0, 300)}`);
    }
    if (!res.ok) {
      const msg = data?.detail || data?.message || `HTTP ${res.status}`;
      throw new Error(`${path} απέτυχε: ${msg}`);
    }
    return data;
  }

  // ---- DOM helpers ----
  function $(sel) { return document.querySelector(sel); }
  function $$ (sel) { return Array.from(document.querySelectorAll(sel)); }

  function findButtonByText(words) {
    const btns = $$('button, a[role="button"], input[type="button"], input[type="submit"]');
    return btns.find(b => {
      const t = (b.value || b.textContent || "").toLowerCase();
      return words.some(w => t.includes(w));
    }) || null;
  }

  function ensureStatusBox() {
    let box = $('[data-role="preview-status"]');
    if (box) return box;
    box = document.createElement('div');
    box.dataset.role = "preview-status";
    box.style.minHeight = "20px";
    box.style.opacity = ".9";
    box.style.margin = "8px 0";
    document.body.appendChild(box);
    return box;
  }

  function setStatus(msg, isError=false) {
    const box = ensureStatusBox();
    box.textContent = msg;
    box.style.color = isError ? "#ef4444" : "";
  }

  function ensurePreviewImage() {
    let img = $('[data-role="preview-img"]');
    if (img) return img;
    img = document.createElement('img');
    img.dataset.role = "preview-img";
    img.alt = "Preview";
    img.style.maxWidth = "100%";
    img.style.height = "auto";
    // Βάλ’ το κοντά στο πρώτο κουμπί render/commit που θα βρούμε
    const anchor = $('[data-action="render-preview"]') || $('[data-action="commit-preview"]') || document.body;
    (anchor.parentElement || document.body).appendChild(img);
    return img;
    }

  function valByNameOrId(name) {
    const sel = [
      `[name="${name}"]`,
      `#${name}`,
      `[data-${name}]`,
      `[data-${name.replace(/_/g,'-')}]`
    ];
    for (const s of sel) {
      const el = document.querySelector(s);
      if (el) {
        if (el.dataset && (el.dataset[name] || el.dataset[name.replace(/-/g,'_')])) {
          return el.dataset[name] || el.dataset[name.replace(/-/g,'_')];
        }
        if ("value" in el) return el.value;
        if (el.textContent) return el.textContent.trim();
      }
    }
    return null;
  }

  function collectPayload() {
    const payload = {
      platform:        valByNameOrId("platform")        || "instagram",
      style:           valByNameOrId("style")           || "normal",
      title:           valByNameOrId("title")           || "Demo Προϊόν",
      price:           valByNameOrId("price")           || "9.99",
      old_price:       valByNameOrId("old_price")       || "",
      image_url:       valByNameOrId("image_url")       || localStorage.getItem("LAST_IMAGE_URL") || "",
      brand_logo_url:  valByNameOrId("brand_logo_url")  || localStorage.getItem("LAST_LOGO_URL")  || "",
      purchase_url:    valByNameOrId("purchase_url")    || "",
      cta_label:       valByNameOrId("cta_label")       || "Αγόρασε τώρα"
    };
    return payload;
  }

  // ---- actions ----
  async function doRender() {
    setStatus("Αποστολή render…");
    const payload = collectPayload();
    if (!payload.image_url) {
      throw new Error("Λείπει image_url. Ανέβασε εικόνα ή βάλε URL (π.χ. από /upload_product_images).");
    }
    const data = await postJSON("/previews/render", payload);

    const previewId  = data.preview_id;
    const previewUrl = data.preview_url;
    if (!previewId || !previewUrl) throw new Error("Το /previews/render δεν επέστρεψε preview_id/preview_url.");

    localStorage.setItem("LAST_PREVIEW_ID", previewId);
    localStorage.setItem("LAST_PREVIEW_URL", previewUrl);

    const img = ensurePreviewImage();
    img.src = `${previewUrl}?t=${Date.now()}`;

    setStatus("OK: δημιουργήθηκε preview.");
  }

  async function doCommit() {
    setStatus("Commit…");
    const previewId  = localStorage.getItem("LAST_PREVIEW_ID");
    const previewUrl = localStorage.getItem("LAST_PREVIEW_URL");
    if (!previewId || !previewUrl) throw new Error("Δεν υπάρχει stored preview (τρέξε πρώτα Render).");

    await postJSON("/previews/commit", { preview_id: previewId, preview_url: previewUrl });
    setStatus("OK: έγινε commit.");
  }

  // ---- wiring (χωρίς να αλλάξουμε layout) ----
  function wire() {
    // 1) Προτιμά data-action hooks
    let renderBtn = $('[data-action="render-preview"]');
    let commitBtn = $('[data-action="commit-preview"]');

    // 2) Fallback: βρες κουμπιά με κείμενο (Ελληνικά/Αγγλικά)
    if (!renderBtn) renderBtn = findButtonByText(["προεπισκ", "preview", "render", "δημιουργία"]);
    if (!commitBtn) commitBtn = findButtonByText(["commit", "οριστικ", "αποθήκ", "save"]);

    if (renderBtn) {
      renderBtn.addEventListener("click", (e) => { e.preventDefault(); doRender().catch(err => setStatus(err.message || String(err), true)); });
    }
    if (commitBtn) {
      commitBtn.addEventListener("click", (e) => { e.preventDefault(); doCommit().catch(err => setStatus(err.message || String(err), true)); });
    }

    // Αν δεν βρέθηκαν, μην κρασάρεις — απλά άφησε το αρχείο φορτωμένο.
    if (!renderBtn) console.warn("Hotfix: δεν βρέθηκε κουμπί Render (πρόσθεσε data-action=\"render-preview\" αν θέλεις explicit).");
    if (!commitBtn) console.warn("Hotfix: δεν βρέθηκε κουμπί Commit (πρόσθεσε data-action=\"commit-preview\" αν θέλεις explicit).");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wire);
  } else {
    wire();
  }
})();
