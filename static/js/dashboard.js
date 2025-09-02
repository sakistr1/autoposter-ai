/**
 * AutoPoster Dashboard Helpers
 * - Token bootstrapping από ?token=... και localStorage
 * - Auto-refresh /token περιοδικά και σε 401 (με 1 retry)
 * - Validation payload πριν το /previews/render
 * - Βοηθοί για shortlinks και commit
 */

const API_BASE = `${location.protocol}//${location.host}`;
const STORAGE_KEY = 'autoposter.bearer';
const ALLOWED_MODES = ['Κανονικό']; // ό,τι άλλο υποστηρίζεις, πρόσθεσέ το εδώ

function qs(sel) { return document.querySelector(sel); }
function qsv(sel) { const el = qs(sel); return el ? el.value?.trim() : ''; }

function setBearer(tok) {
  if (!tok) return;
  localStorage.setItem(STORAGE_KEY, tok);
}
function getBearer() {
  // 1) Αν υπάρχει στο URL, χρησιμοποίησέ το και σώσε το
  const urlTok = new URLSearchParams(location.search).get('token');
  if (urlTok) {
    setBearer(urlTok);
    // καθάρισε το URL (χωρίς reload)
    const clean = new URL(location.href);
    clean.searchParams.delete('token');
    history.replaceState({}, '', clean.toString());
  }
  // 2) Από localStorage
  return localStorage.getItem(STORAGE_KEY) || '';
}

async function refreshToken() {
  // Προϋπόθεση: ο backend σου επιτρέπει POST /token χωρίς body και επιστρέφει {access_token}
  const r = await fetch(`${API_BASE}/token`, { method: 'POST' });
  if (!r.ok) throw new Error(`token refresh failed: HTTP ${r.status}`);
  const j = await r.json();
  if (!j?.access_token) throw new Error('no access_token from /token');
  setBearer(j.access_token);
  return j.access_token;
}

async function apiFetch(path, opts = {}, retry = true) {
  const token = getBearer();
  const headers = new Headers(opts.headers || {});
  headers.set('Authorization', `Bearer ${token}`);
  if (!headers.has('Content-Type') && opts.body) {
    headers.set('Content-Type', 'application/json');
  }
  const r = await fetch(`${API_BASE}${path}`, { ...opts, headers });
  if (r.status === 401 && retry) {
    // πάρε φρέσκο token και ξαναδοκίμασε μία φορά
    await refreshToken();
    return apiFetch(path, opts, false);
  }
  return r;
}

function validateRenderPayload(p) {
  const errors = [];

  // Υποχρεωτικά
  if (!p.type) errors.push('type');
  if (!p.ratio) errors.push('ratio');
  if (!p.platform) errors.push('platform');
  if (!p.mode) errors.push('mode');
  if (!p.title) errors.push('title');
  if (!p.target_url) errors.push('target_url');

  // Επιχειρησιακοί κανόνες
  if (!ALLOWED_MODES.includes(p.mode)) {
    errors.push(`mode(επιτρεπτά: ${ALLOWED_MODES.join(', ')})`);
  }
  if (p.type === 'image') {
    // Για image θέλουμε product_image_url (για να μην ξαναδείς 400)
    if (!p.product_image_url) errors.push('product_image_url');
  }

  return errors;
}

// === Hook UI ===
// Προσαρμόζεις τα selectors παρακάτω στα ids/inputs του dashboard σου.
async function onRenderClick() {
  // Μάζεμα τιμών από UI
  const payload = {
    type: 'image',
    ratio: qsv('#ratio') || '4:5',
    platform: qsv('#platform') || 'instagram',
    mode: qsv('#mode') || 'Κανονικό',
    title: qsv('#title') || 'Shortlink QR Test',
    target_url: qsv('#target_url'),
    qr: qs('#qr')?.checked ?? true,
    product_image_url: qsv('#product_image_url') || '/static/uploads/products/123.jpg'
  };

  // Validation πριν πάμε backend
  const errs = validateRenderPayload(payload);
  if (errs.length) {
    notifyError('Συμπλήρωσε τα πεδία: ' + errs.join(', '));
    return;
  }

  try {
    btnDisable('#btnRender', true);
    const r = await apiFetch('/previews/render', { method: 'POST', body: JSON.stringify(payload) });
    if (!r.ok) {
      const j = await safeJson(r);
      throw new Error(`render failed: HTTP ${r.status} ${JSON.stringify(j)}`);
    }
    const j = await r.json();
    showPreview(j);
  } catch (e) {
    notifyError(e.message || String(e));
  } finally {
    btnDisable('#btnRender', false);
  }
}

async function onCommitClick() {
  try {
    const preview_url = qsv('#last_preview_url');
    if (!preview_url) return notifyError('Δεν υπάρχει preview_url για commit');

    btnDisable('#btnCommit', true);
    const r = await apiFetch('/previews/commit', {
      method: 'POST',
      body: JSON.stringify({ preview_url })
    });
    const j = await r.json();
    if (!r.ok) throw new Error(`commit failed: HTTP ${r.status} ${JSON.stringify(j)}`);
    notifyOK('OK, έγινε commit.');
    await loadHistory();
  } catch (e) {
    notifyError(e.message || String(e));
  } finally {
    btnDisable('#btnCommit', false);
  }
}

async function onShortlinkClick() {
  try {
    const url = qsv('#target_url');
    if (!url) return notifyError('Δώσε target_url');
    btnDisable('#btnShortlink', true);
    const r = await apiFetch('/shortlinks', {
      method: 'POST',
      body: JSON.stringify({ url })
    });
    const j = await r.json();
    if (!r.ok) throw new Error(`shortlink failed: HTTP ${r.status} ${JSON.stringify(j)}`);
    notifyOK(`Shortlink: /go/${j.code}`);
  } catch (e) {
    notifyError(e.message || String(e));
  } finally {
    btnDisable('#btnShortlink', false);
  }
}

function btnDisable(sel, v) { const el = qs(sel); if (el) el.disabled = !!v; }
async function safeJson(r) { try { return await r.json(); } catch { return {}; } }

function showPreview(j) {
  const a = j.absolute_url || (API_BASE + j.preview_url);
  const prev = qs('#preview_img');
  if (prev) prev.src = a;
  const last = qs('#last_preview_url');
  if (last) last.value = j.preview_url || '';
}

async function loadHistory() {
  const r = await apiFetch('/previews/committed?limit=10&offset=0', { method: 'GET' });
  if (!r.ok) return;
  const j = await r.json();
  const box = qs('#history');
  if (!box) return;
  box.innerHTML = (j || []).map(item => {
    const href = item.absolute_url || (API_BASE + item.url);
    return `<li><a href="${href}" target="_blank">${href}</a> — <small>${item.created_at}</small></li>`;
  }).join('');
}

function notifyOK(msg) {
  console.log('[OK]', msg);
  const el = qs('#notice'); if (el) { el.textContent = msg; el.style.color = 'green'; }
}
function notifyError(msg) {
  console.error('[ERR]', msg);
  const el = qs('#notice'); if (el) { el.textContent = msg; el.style.color = 'red'; }
}

async function init() {
  // Αρχικοποίηση token
  getBearer();               // πέρνα από ?token=... και σώστο
  await refreshToken().catch(() => {}); // προσπάθησε να πάρεις φρέσκο

  // Ετήσιο refresh κάθε 10'
  setInterval(() => refreshToken().catch(() => {}), 10 * 60 * 1000);

  // Hooks
  qs('#btnRender')?.addEventListener('click', onRenderClick);
  qs('#btnCommit')?.addEventListener('click', onCommitClick);
  qs('#btnShortlink')?.addEventListener('click', onShortlinkClick);

  // Προφόρτωσε ιστορικό
  loadHistory().catch(() => {});
}

document.addEventListener('DOMContentLoaded', init);
