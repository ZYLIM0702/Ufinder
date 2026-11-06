"use strict";
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const when = (t) => (t ? new Date(t * 1000).toLocaleString() : "");

async function api(path, opts = {}) {
  const res = await fetch(path, { credentials: "same-origin", ...opts });
  if (res.status === 401) { showLogin(); throw new Error("login"); }
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText);
  return res.json();
}
const post = (path, body, method = "POST") => api(path, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

function showLogin() { $("login").hidden = false; $("app").hidden = true; }
async function boot() {
  try {
    const me = await api("/api/me");
    $("login").hidden = true; $("app").hidden = false;
    $("who").textContent = me.user;
    $("roots").textContent = me.roots.map((r) => r.name).join(", ");
    route();
  } catch (e) { showLogin(); }
}
$("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try { await post("/api/login", { user: $("user").value, password: $("pass").value }); boot(); }
  catch (err) { $("login-error").textContent = err.message; }
});

const loaders = { graph: () => loadGraph(state.center), missing: loadMissing, changes: loadChanges, access: loadAccess, status: loadStatus };
const state = { center: null, image: null };
function show(page) {
  document.querySelectorAll(".page").forEach((p) => (p.hidden = p.id !== `page-${page}`));
  document.querySelectorAll("#nav button").forEach((b) => b.classList.toggle("on", b.dataset.page === page));
  if (loaders[page]) loaders[page]();
}
$("nav").addEventListener("click", (e) => { if (e.target.dataset.page) { state.center = null; location.hash = e.target.dataset.page; show(e.target.dataset.page); } });
function route() {
  const [page, arg] = decodeURIComponent(location.hash.slice(1)).split("=");
  if (page === "q") { show("search"); $("q").value = arg; runSearch(); }
  else if (page === "file") { state.center = Number(arg); show("graph"); }
  else show(page || "search");
}

// ---- search ------------------------------------------------------------------

const ICON = { photo: "photo", document: "doc", recording: "audio", video: "video", file: "file" };
function card(r) {
  const where = (x) => (x.locator && !["image", "image text"].includes(x.locator) ? " · " + esc(x.locator) : "");
  const chips = (r.reasons || []).map((x) => `<span class="chip ${esc(x.signal)}" title="${esc(x.snippet || "")}">${esc(x.label)}${where(x)}</span>`).join("");
  const seen = new Set();
  const snips = (r.reasons || []).filter((x) => {
    if (!x.snippet || x.signal === "name") return false;
    const key = x.snippet.slice(0, 80);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  }).slice(0, 2).map((x) => `<div class="snippet"><small>${esc(x.label)}:</small> ${esc(x.snippet)}</div>`).join("");
  const thumb = r.has_thumb
    ? `<img class="thumb" loading="lazy" src="/v1/files/${r.file_id}/thumb" alt="">`
    : `<div class="thumb">${esc(ICON[r.type] || "file")}</div>`;
  return `<article class="card">${thumb}<div>
    <h3>${esc(r.name)}</h3><div class="path">${esc(r.path)}${r.copies > 1 ? ` · ${r.copies} copies` : ""}</div>
    <div class="chips">${chips}</div>${snips}
    <div class="actions"><a href="#file=${r.file_id}">Show connections</a></div></div></article>`;
}
async function runSearch() {
  const q = $("q").value.trim();
  if (!q && !state.image) return;
  $("meta").textContent = "Searching...";
  try {
    let data;
    if (state.image) {
      const form = new FormData();
      form.append("file", state.image); form.append("q", q); form.append("limit", "20");
      data = await api("/v1/search/file", { method: "POST", body: form });
    } else data = await post("/v1/search", { q, limit: 20 });
    $("meta").innerHTML = `<b>${data.count}</b> results and <b>${(data.connected || []).length}</b> connected files in ${data.took_ms} ms. No LLM used.`;
    const linked = (data.connected || []).length
      ? `<h3 class="section">Connected files</h3><p class="sub">No direct match. Linked to the results above by evidence.</p>` + data.connected.map(card).join("") : "";
    $("results").innerHTML = (data.results.map(card).join("") || `<div class="sub">No results in the folders you can read.</div>`) + linked;
  } catch (e) { $("meta").textContent = e.message; }
}
$("search-form").addEventListener("submit", (e) => { e.preventDefault(); location.hash = ""; runSearch(); });
document.querySelectorAll("[data-try]").forEach((a) => a.addEventListener("click", () => { $("q").value = a.textContent; setImage(null); runSearch(); }));
function setImage(file) {
  state.image = file;
  const box = $("query-image");
  box.hidden = !file;
  box.innerHTML = file ? `<img src="${URL.createObjectURL(file)}" alt=""> Searching by this image` : "";
}
$("file").addEventListener("change", (e) => { setImage(e.target.files[0]); runSearch(); });
const bar = $("search-form");
["dragover", "dragenter"].forEach((n) => bar.addEventListener(n, (e) => { e.preventDefault(); bar.classList.add("drag"); }));
["dragleave", "drop"].forEach((n) => bar.addEventListener(n, () => bar.classList.remove("drag")));
bar.addEventListener("drop", (e) => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) { setImage(f); runSearch(); } });

// ---- graph: a small force layout, no libraries, because this box is offline -------

const COLORS = { image: "#ff6fa8", text: "#62b0ff", audio: "#ffc24a", video: "#b57bff", entity: "#2bf0ad", ghost: "#ff8a5c", other: "#8391ad" };
const NAMES = { image: "Photo", text: "Document", audio: "Recording", video: "Video", entity: "Shared topic", ghost: "Missing file" };
const EDGE = { same_hash: "#2bf0ad", version_of: "#62b0ff", links_to: "#e8eefb", mentions: "#b57bff", has_entity: "#2bf0ad", same_event: "#ff6fa8", similar_to: "#51608a", wants: "#ff8a5c" };
$("legend").innerHTML = Object.entries(NAMES).map(([k, v]) => `<span><i style="background:${COLORS[k]}"></i>${v}</span>`).join("");

const g = { nodes: [], edges: [], byId: {}, raf: 0, scale: 1, ox: 0, oy: 0, hover: null, drag: null };
const canvas = $("canvas"), ctx = canvas.getContext("2d");

function fit() {
  const r = canvas.getBoundingClientRect(), d = devicePixelRatio || 1;
  canvas.width = r.width * d; canvas.height = r.height * d;
  ctx.setTransform(d, 0, 0, d, 0, 0);
  g.w = r.width; g.h = r.height;
}
async function loadGraph(center) {
  fit();
  const url = center ? `/v1/graph?center=${center}&depth=${$("depth").value}` : "/v1/graph?limit=260";
  const data = await api(url);
  const degree = {};
  data.edges.forEach((e) => { degree[e.src] = (degree[e.src] || 0) + 1; degree[e.dst] = (degree[e.dst] || 0) + 1; });
  const prior = g.byId;
  g.nodes = data.nodes.map((n, i) => {
    const a = i * 2.39996, r = 16 * Math.sqrt(i + 1);
    const old = prior[n.id];
    return { ...n, x: old ? old.x : g.w / 2 + r * Math.cos(a), y: old ? old.y : g.h / 2 + r * Math.sin(a), vx: 0, vy: 0, deg: degree[n.id] || 0, center: n.file_id === center };
  });
  g.byId = Object.fromEntries(g.nodes.map((n) => [n.id, n]));
  g.edges = data.edges.filter((e) => g.byId[e.src] && g.byId[e.dst]).map((e) => ({ ...e, a: g.byId[e.src], b: g.byId[e.dst] }));
  const main = g.nodes.find((n) => n.center);
  $("graph-title").textContent = main ? main.label : "File graph";
  g.alpha = 1;
  cancelAnimationFrame(g.raf);
  tick();
}
function step() {
  const ns = g.nodes, n = ns.length, a = g.alpha;
  for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) {
    const p = ns[i], q = ns[j];
    let dx = q.x - p.x, dy = q.y - p.y, d2 = dx * dx + dy * dy + 0.01;
    if (d2 > 160000) continue;
    const f = ((n < 70 ? 9000 : 2100) / d2) * a;
    dx *= f; dy *= f; p.vx -= dx * 0.02; p.vy -= dy * 0.02; q.vx += dx * 0.02; q.vy += dy * 0.02;
  }
  for (const e of g.edges) {
    const dx = e.b.x - e.a.x, dy = e.b.y - e.a.y, d = Math.hypot(dx, dy) || 1;
    const wide = g.nodes.length < 70 ? 2.1 : 1;
    const want = (e.type === "same_event" ? 34 : e.type === "similar_to" ? 90 : 58) * wide;
    const f = ((d - want) / d) * 0.06 * a;
    e.a.vx += dx * f; e.a.vy += dy * f; e.b.vx -= dx * f; e.b.vy -= dy * f;
  }
  for (const p of ns) {
    p.vx += (g.w / 2 - p.x) * 0.0035 * a; p.vy += (g.h / 2 - p.y) * 0.0048 * a;
    if (p === g.drag) continue;
    p.x += p.vx; p.y += p.vy; p.vx *= 0.82; p.vy *= 0.82;
  }
}
function size(n) { return n.center ? 13 : n.group === "entity" ? 5 + Math.min(n.deg, 16) * 0.75 : n.group === "ghost" ? 8 : 4.5 + Math.min(n.deg, 10) * 0.45; }
function draw() {
  ctx.clearRect(0, 0, g.w, g.h);
  ctx.lineWidth = 1;
  for (const e of g.edges) {
    const lit = g.hover && (e.a === g.hover || e.b === g.hover);
    ctx.strokeStyle = EDGE[e.type] || "#51608a";
    ctx.globalAlpha = g.hover ? (lit ? 0.95 : 0.08) : e.type === "similar_to" ? 0.22 : 0.42;
    ctx.setLineDash(e.type === "wants" ? [4, 4] : []);
    ctx.beginPath(); ctx.moveTo(e.a.x, e.a.y); ctx.lineTo(e.b.x, e.b.y); ctx.stroke();
  }
  ctx.setLineDash([]);
  for (const n of g.nodes) {
    const near = g.hover && (n === g.hover || g.edges.some((e) => (e.a === g.hover && e.b === n) || (e.b === g.hover && e.a === n)));
    ctx.globalAlpha = g.hover && !near ? 0.18 : 1;
    const c = COLORS[n.group] || COLORS.other, r = size(n);
    ctx.shadowColor = c; ctx.shadowBlur = n.group === "entity" || n.center ? 16 : 7;
    ctx.fillStyle = n.group === "ghost" ? "#070c1c" : c;
    ctx.strokeStyle = c; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.arc(n.x, n.y, r, 0, 7);
    ctx.fill();
    if (n.group === "ghost") { ctx.setLineDash([3, 3]); ctx.stroke(); ctx.setLineDash([]); }
    ctx.shadowBlur = 0;
    if (n.group === "entity" || n.group === "ghost" || n.center || near || g.nodes.length < 60) {
      ctx.fillStyle = "#e8eefb"; ctx.font = `${n.group === "entity" ? 600 : 400} 12px Avenir Next, system-ui`;
      ctx.fillText(n.label.length > 28 ? n.label.slice(0, 27) + "…" : n.label, n.x + r + 4, n.y + 4);
    }
  }
  ctx.globalAlpha = 1;
}
function tick() {
  if (g.alpha > 0.015) { step(); step(); g.alpha *= 0.985; }
  draw();
  g.raf = requestAnimationFrame(tick);
}
const at = (e) => {
  const r = canvas.getBoundingClientRect(), x = e.clientX - r.left, y = e.clientY - r.top;
  return { x, y, n: g.nodes.find((n) => Math.hypot(n.x - x, n.y - y) < size(n) + 4) || null };
};
canvas.addEventListener("mousemove", (e) => {
  const { x, y, n } = at(e);
  if (g.drag) { g.drag.x = x; g.drag.y = y; g.alpha = Math.max(g.alpha, 0.12); return; }
  g.hover = n;
  const tip = $("tip");
  tip.hidden = !n;
  if (n) { tip.textContent = `${NAMES[n.group] || "File"}: ${n.label}`; tip.style.left = `${Math.min(x + 12, g.w - 220)}px`; tip.style.top = `${y + 12}px`; }
});
canvas.addEventListener("mousedown", (e) => { g.drag = at(e).n; });
addEventListener("mouseup", () => { g.drag = null; });
canvas.addEventListener("dblclick", (e) => { const { n } = at(e); if (n && n.file_id) { state.center = n.file_id; location.hash = `file=${n.file_id}`; } });
$("depth").addEventListener("input", () => { if (state.center) loadGraph(state.center); });
$("graph-all").addEventListener("click", () => { state.center = null; location.hash = "graph"; loadGraph(null); });
addEventListener("hashchange", () => { if (!$("app").hidden) route(); });
addEventListener("resize", () => { if (!$("page-graph").hidden) fit(); });

// ---- other pages ----------------------------------------------------------------

async function loadMissing() {
  const d = await api("/v1/ghosts");
  $("missing").innerHTML = d.missing.map((m) => `<div class="ghost-item"><b>${esc(m.name)}</b><small>Mentioned in ${m.referenced_by.map(esc).join(", ")}</small></div>`).join("") || `<div class="sub">Nothing is missing.</div>`;
}
async function loadChanges() {
  const d = await api("/v1/changes?since=0&limit=500");
  $("changes").innerHTML = d.events.slice(-120).reverse().map((e) => `<div class="tr"><span class="tag">${esc(e.type)}</span><span class="grow">${esc(e.path || e.detail || "")}</span><small>${when(e.ts)}</small></div>`).join("");
}
const TIER = ["IDs only", "Paths and types", "Redacted snippets", "Full text"];
async function loadAccess() {
  const [keys, audit, models] = await Promise.all([api("/v1/keys"), api("/v1/audit?limit=30"), api("/v1/models")]);
  $("keys").innerHTML = keys.keys.map((k) => `<div class="tr"><span class="tag">${k.revoked ? "revoked" : "active"}</span><span class="grow">${esc(k.name)} <small>${TIER[k.max_tier]}, ${k.daily_results} results a day</small></span><small>expires ${when(k.expires)}</small>${k.revoked ? "" : `<a data-revoke="${esc(k.key_id)}">Revoke</a>`}</div>`).join("") || `<div class="sub">No keys yet.</div>`;
  const base = location.origin;
  $("connect").textContent = `MCP (Claude, Codex, any MCP client)
  URL:     ${base}/mcp
  Header:  Authorization: Bearer YOUR_KEY

REST and n8n HTTP Request node
  POST ${base}/v1/search   {"q": "lease renewal"}

OpenAI-compatible embeddings for LAN tools
  base_url = ${base}/v1`;
  const ext = models.external;
  $("models").innerHTML = `<div class="tr"><span class="tag">local</span><span class="grow">${esc(models.local.id)} <small>${models.local.dim} dimensions. Stays on the NAS.</small></span></div>` +
    (ext ? `<div class="tr"><span class="tag" style="color:var(--amber)">external</span><span class="grow">${esc(ext.model)} <small>${esc(ext.base_url)}. Folders: ${models.folders_opted_in.map(esc).join(", ") || "none"}</small></span></div>`
      : `<div class="tr"><span class="tag" style="color:var(--mute)">external</span><span class="grow"><small>None connected. No file content can leave the NAS.</small></span></div>`);
  $("audit").innerHTML = `<div class="sub">Chain check: ${audit.chain.ok ? "intact" : "BROKEN"}, ${audit.chain.rows} rows</div>` +
    audit.rows.map((r) => `<div class="tr"><span class="tag">${esc(r.outcome)}</span><span class="grow">${esc(r.actor)} ${esc(r.tool)} <small>${r.n_results} results${r.key_id ? ", key " + esc(r.key_id) : ""}</small></span><small>${when(r.ts)}</small></div>`).join("");
}
$("keys").addEventListener("click", async (e) => {
  const id = e.target.dataset.revoke;
  if (id) { await api(`/v1/keys/${id}`, { method: "DELETE" }); loadAccess(); }
});
$("key-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const r = await post("/v1/keys", { name: $("key-name").value, max_tier: Number($("key-tier").value) });
  const box = $("key-new");
  box.hidden = false;
  box.textContent = `Copy this now. It will not be shown again.\n\n${r.token}`;
  loadAccess();
});
async function loadStatus() {
  const s = await api("/v1/status");
  const stat = (v, l) => `<div class="stat"><b>${esc(v)}</b><span>${esc(l)}</span></div>`;
  const edges = s.graph.edges || {};
  const total = Object.values(s.files).reduce((a, b) => a + b, 0), done = Object.values(s.indexed).reduce((a, b) => a + b, 0);
  $("status").innerHTML = stat(`${done} / ${total}`, "files indexed") +
    Object.entries(s.files).map(([k, v]) => stat(`${s.indexed[k] || 0} / ${v}`, NAMES[k] || k)).join("") +
    Object.entries(edges).map(([k, v]) => stat(v, `${k.replace("_", " ")} links`)).join("") +
    stat(s.graph.ghosts ?? 0, "missing files") + stat(s.model.local, `model, ${s.model.dim} dimensions`);
}
boot();
