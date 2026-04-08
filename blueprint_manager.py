#!/usr/bin/env python3
"""
Blueprint Manager — Web UI for managing ComfyUI Core subgraph blueprints.

Usage:
    python blueprint_manager.py [--port 8099]

Reads BLUEPRINTS_DIR from .env file in the same directory.
Override with --blueprints flag if needed.
"""

import argparse
import json
import glob
import os
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

# Set at startup from .env or --blueprints
BLUEPRINTS_DIR: str = ""


def load_dotenv():
    """Load key=value pairs from .env file next to this script."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.isfile(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

# ─── helpers ────────────────────────────────────────────────────────────────

def scan_blueprints():
    """Return a list of blueprint info dicts."""
    results = []
    for fpath in sorted(glob.glob(os.path.join(BLUEPRINTS_DIR, "*.json"))):
        fname = os.path.basename(fpath)
        with open(fpath, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                continue
        subgraphs = data.get("definitions", {}).get("subgraphs", [])
        sg_list = []
        for idx, sg in enumerate(subgraphs):
            sg_list.append({
                "index": idx,
                "name": sg.get("name", ""),
                "category": sg.get("category", ""),
                "id": sg.get("id", ""),
            })
        results.append({
            "filename": fname,
            "subgraphs": sg_list,
        })
    return results


def update_category(filename: str, sg_index: int, new_category: str):
    """Update the category of a specific subgraph inside a blueprint file."""
    fpath = os.path.join(BLUEPRINTS_DIR, filename)
    if not os.path.isfile(fpath):
        return False, "File not found"
    with open(fpath, "r", encoding="utf-8") as f:
        data = json.load(f)
    subgraphs = data.get("definitions", {}).get("subgraphs", [])
    if sg_index < 0 or sg_index >= len(subgraphs):
        return False, "Subgraph index out of range"
    subgraphs[sg_index]["category"] = new_category
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return True, "OK"


def get_all_categories():
    """Return sorted unique categories across all blueprints."""
    cats = set()
    for bp in scan_blueprints():
        for sg in bp["subgraphs"]:
            if sg["category"]:
                cats.add(sg["category"])
    return sorted(cats)


def import_blueprint(filename: str, content: str, category: str):
    """Import a blueprint JSON file. Optionally set category on the primary subgraph."""
    if not filename.endswith(".json"):
        return False, "Filename must end with .json"
    fpath = os.path.join(BLUEPRINTS_DIR, filename)
    if os.path.exists(fpath):
        return False, "File already exists"
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return False, "Invalid JSON"
    if category:
        subgraphs = data.get("definitions", {}).get("subgraphs", [])
        if subgraphs:
            subgraphs[0]["category"] = category
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return True, "OK"


def rename_blueprint(old_name: str, new_name: str):
    """Rename a blueprint file."""
    old_path = os.path.join(BLUEPRINTS_DIR, old_name)
    new_path = os.path.join(BLUEPRINTS_DIR, new_name)
    if not os.path.isfile(old_path):
        return False, "Source file not found"
    if os.path.exists(new_path):
        return False, "Target file already exists"
    os.rename(old_path, new_path)
    return True, "OK"


# ─── HTML ───────────────────────────────────────────────────────────────────

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Blueprint Manager</title>
<style>
:root {
  --bg: #0d1117;
  --surface: #161b22;
  --surface2: #21262d;
  --border: #30363d;
  --text: #e6edf3;
  --text2: #8b949e;
  --accent: #58a6ff;
  --accent2: #1f6feb;
  --green: #3fb950;
  --orange: #d29922;
  --red: #f85149;
  --purple: #bc8cff;
  --radius: 8px;
}
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
       background: var(--bg); color: var(--text); display:flex; height:100vh; overflow:hidden; }

/* ── Sidebar ── */
.sidebar { width: 260px; min-width: 260px; background: var(--surface); border-right: 1px solid var(--border);
           display:flex; flex-direction:column; overflow:hidden; }
.sidebar-header { padding:16px; border-bottom:1px solid var(--border); }
.sidebar-header h2 { font-size:14px; color:var(--text2); text-transform:uppercase; letter-spacing:1px; }
.cat-tree { flex:1; overflow-y:auto; padding:8px; }
.cat-item { padding:8px 12px; border-radius:var(--radius); cursor:pointer; font-size:13px;
            display:flex; justify-content:space-between; align-items:center; margin-bottom:2px; }
.cat-item:hover { background: var(--surface2); }
.cat-item.active { background: var(--accent2); color: #fff; }
.cat-item .count { background: var(--surface2); border-radius:10px; padding:2px 8px; font-size:11px; color:var(--text2); }
.cat-item.active .count { background: rgba(255,255,255,0.2); color: #fff; }
.cat-group { margin-top:6px; }
.cat-group-label { padding:8px 12px; border-radius:var(--radius); cursor:pointer; font-size:13px; font-weight:600;
                   display:flex; justify-content:space-between; align-items:center; margin-bottom:2px; }
.cat-group-label:hover { background: var(--surface2); }
.cat-group-label.active { background: var(--accent2); color: #fff; }
.cat-group-label .count { background: var(--surface2); border-radius:10px; padding:2px 8px; font-size:11px; color:var(--text2); }
.cat-group-label.active .count { background: rgba(255,255,255,0.2); color: #fff; }
.cat-group-label .arrow { font-size:10px; margin-right:4px; transition:transform 0.15s; display:inline-block; }
.cat-group-label .arrow.open { transform:rotate(90deg); }
.cat-sub-items { padding-left:12px; }
.cat-sub-items .cat-item { font-size:12px; padding:5px 12px; }
.sidebar-stats { padding:12px 16px; border-top:1px solid var(--border); font-size:12px; color:var(--text2); }

/* ── Main ── */
.main { flex:1; display:flex; flex-direction:column; overflow:hidden; }
.toolbar { padding:12px 20px; border-bottom:1px solid var(--border); display:flex; gap:12px; align-items:center;
           background: var(--surface); flex-wrap: wrap; }
.toolbar input[type=text] { background:var(--surface2); border:1px solid var(--border); color:var(--text);
                            padding:6px 12px; border-radius:var(--radius); font-size:13px; width:260px; }
.toolbar input[type=text]:focus { outline:none; border-color:var(--accent); }
.toolbar select { background:var(--surface2); border:1px solid var(--border); color:var(--text);
                  padding:6px 10px; border-radius:var(--radius); font-size:13px; }
.btn { padding:6px 14px; border-radius:var(--radius); border:1px solid var(--border); background:var(--surface2);
       color:var(--text); cursor:pointer; font-size:13px; display:inline-flex; align-items:center; gap:6px; }
.btn:hover { border-color:var(--accent); }
.btn.primary { background:var(--accent2); border-color:var(--accent2); color:#fff; }
.btn.primary:hover { background:var(--accent); }
.btn.danger { color:var(--red); }
.btn.danger:hover { border-color:var(--red); }

.content { flex:1; overflow-y:auto; padding:20px; }

/* ── View modes ── */
.view-toggle { display:flex; gap:2px; background:var(--surface2); border-radius:var(--radius); padding:2px; }
.view-toggle .btn { border:none; background:transparent; padding:4px 10px; border-radius:6px; font-size:12px; }
.view-toggle .btn.active { background:var(--accent2); color:#fff; }

/* ── Cards ── */
.bp-grid { display:grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap:12px; }
.bp-card { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:16px;
           transition: border-color 0.15s; position:relative; }
.bp-card:hover { border-color:var(--accent); }
.bp-card .bp-name { font-size:14px; font-weight:600; margin-bottom:8px; word-break:break-word; }
.bp-card .bp-category { font-size:12px; color:var(--text2); margin-bottom:4px; display:flex; align-items:center; gap:6px; }
.bp-card .bp-category .dot { width:8px; height:8px; border-radius:50%; display:inline-block; }
.bp-card .bp-subgraphs { font-size:11px; color:var(--text2); }
.bp-card .bp-actions { display:flex; gap:6px; margin-top:10px; }
.bp-card .bp-actions .btn { font-size:11px; padding:3px 8px; }
.bp-card.no-cat { border-left: 3px solid var(--orange); }
.badge { display:inline-block; padding:2px 8px; border-radius:10px; font-size:11px; }
.badge.warn { background:rgba(210,153,34,0.15); color:var(--orange); }
.badge.ok { background:rgba(63,185,80,0.15); color:var(--green); }

/* ── Table view ── */
.bp-table { width:100%; border-collapse:collapse; }
.bp-table th { text-align:left; padding:8px 12px; font-size:12px; color:var(--text2); border-bottom:1px solid var(--border);
               text-transform:uppercase; letter-spacing:0.5px; position:sticky; top:0; background:var(--bg); }
.bp-table td { padding:8px 12px; font-size:13px; border-bottom:1px solid var(--border); }
.bp-table tr:hover td { background:var(--surface); }
.bp-table .editable { cursor:pointer; border-bottom:1px dashed var(--text2); }
.bp-table .editable:hover { color:var(--accent); border-color:var(--accent); }

/* ── Modal ── */
.modal-overlay { position:fixed; inset:0; background:rgba(0,0,0,0.6); display:flex; align-items:center;
                 justify-content:center; z-index:100; }
.modal { background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:24px;
         width:480px; max-width:90vw; max-height:80vh; overflow-y:auto; }
.modal h3 { margin-bottom:16px; font-size:16px; }
.modal label { display:block; font-size:13px; color:var(--text2); margin-bottom:4px; margin-top:12px; }
.modal input[type=text], .modal select { width:100%; background:var(--surface2); border:1px solid var(--border);
  color:var(--text); padding:8px 12px; border-radius:var(--radius); font-size:13px; margin-bottom:4px; }
.modal input[type=text]:focus, .modal select:focus { outline:none; border-color:var(--accent); }
.modal .modal-actions { display:flex; gap:8px; justify-content:flex-end; margin-top:20px; }
.modal .cat-suggestions { display:flex; flex-wrap:wrap; gap:4px; margin-top:4px; }
.modal .cat-suggestions .chip { padding:3px 10px; border-radius:12px; font-size:11px; background:var(--surface2);
  border:1px solid var(--border); cursor:pointer; }
.modal .cat-suggestions .chip:hover { border-color:var(--accent); color:var(--accent); }
.modal .sg-list { margin-top:8px; }
.modal .sg-item { padding:6px 0; border-bottom:1px solid var(--border); font-size:13px; display:flex;
  justify-content:space-between; align-items:center; }
.modal .sg-item:last-child { border:none; }

/* ── Toast ── */
.toast { position:fixed; bottom:20px; right:20px; background:var(--green); color:#fff; padding:10px 20px;
         border-radius:var(--radius); font-size:13px; z-index:200; animation: slideIn 0.3s ease; }
.toast.error { background:var(--red); }
@keyframes slideIn { from { transform:translateY(20px); opacity:0; } to { transform:translateY(0); opacity:1; } }

/* ── Scrollbar ── */
::-webkit-scrollbar { width:8px; }
::-webkit-scrollbar-track { background:transparent; }
::-webkit-scrollbar-thumb { background:var(--surface2); border-radius:4px; }
::-webkit-scrollbar-thumb:hover { background:var(--border); }

.bulk-bar { padding:8px 20px; background:var(--accent2); display:flex; align-items:center; gap:12px; font-size:13px; }
.bulk-bar .btn { background:rgba(255,255,255,0.15); border-color:rgba(255,255,255,0.3); color:#fff; }

.checkbox { width:16px; height:16px; accent-color:var(--accent); cursor:pointer; }

/* ── Drop zone ── */
.drop-overlay { position:fixed; inset:0; background:rgba(31,111,235,0.15); border:3px dashed var(--accent);
  z-index:50; display:flex; align-items:center; justify-content:center; pointer-events:none; }
.drop-overlay span { background:var(--accent2); color:#fff; padding:16px 32px; border-radius:12px;
  font-size:18px; font-weight:600; }
.import-results { max-height:300px; overflow-y:auto; margin-top:12px; }
.import-row { display:flex; align-items:center; gap:8px; padding:6px 0; border-bottom:1px solid var(--border); font-size:13px; }
.import-row:last-child { border:none; }
.import-row .fname { flex:1; word-break:break-all; }
.import-row input[type=text] { width:220px; background:var(--surface2); border:1px solid var(--border);
  color:var(--text); padding:4px 8px; border-radius:var(--radius); font-size:12px; }
.import-row .status { font-size:11px; }
</style>
</head>
<body>

<!-- Sidebar -->
<div class="sidebar">
  <div class="sidebar-header"><h2>Categories</h2></div>
  <div class="cat-tree" id="catTree"></div>
  <div class="sidebar-stats" id="sidebarStats"></div>
</div>

<!-- Main -->
<div class="main">
  <div class="toolbar">
    <input type="text" id="searchInput" placeholder="Search blueprints…">
    <div class="view-toggle">
      <button class="btn active" data-view="grid" onclick="setView('grid')">Grid</button>
      <button class="btn" data-view="table" onclick="setView('table')">Table</button>
    </div>
    <div style="flex:1"></div>
    <button class="btn primary" onclick="openImport()">＋ Import</button>
    <button class="btn" onclick="bulkSetCategory()">Bulk Set Category</button>
    <button class="btn" onclick="loadData()">↻ Refresh</button>
    <input type="file" id="fileInput" multiple accept=".json" style="display:none" onchange="handleFileSelect(this.files)">
  </div>
  <div id="bulkBar" class="bulk-bar" style="display:none">
    <input type="checkbox" class="checkbox" id="selectAllCb" onchange="toggleSelectAll()">
    <span id="bulkCount">0 selected</span>
    <button class="btn" onclick="bulkApplyCategory()">Set Category…</button>
    <div style="flex:1"></div>
    <button class="btn" onclick="exitBulk()">Cancel</button>
  </div>
  <div class="content" id="content"></div>
</div>

<!-- Modal container -->
<div id="modalOverlay" class="modal-overlay" style="display:none" onclick="if(event.target===this)closeModal()"></div>

<!-- Drop overlay -->
<div id="dropOverlay" class="drop-overlay" style="display:none"><span>Drop .json files to import</span></div>

<!-- Toast container -->
<div id="toastContainer"></div>

<script>
// ── State ──
let blueprints = [];
let allCategories = [];
let currentFilter = 'all';  // 'all', 'uncategorized', 'group:TopLevel', or 'TopLevel/Sub'
let currentView = 'grid';
let bulkMode = false;
let selectedSet = new Set();
let expandedGroups = new Set();

// ── API ──
async function api(method, path, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch('/api' + path, opts);
  return r.json();
}

// ── Load ──
async function loadData() {
  blueprints = await api('GET', '/blueprints');
  allCategories = await api('GET', '/categories');
  renderSidebar();
  renderContent();
}

// ── Sidebar ──
function renderSidebar() {
  const tree = {};
  let total = 0, uncatCount = 0;
  blueprints.forEach(bp => {
    bp.subgraphs.forEach(sg => {
      total++;
      if (!sg.category) { uncatCount++; return; }
      const parts = sg.category.split('/');
      const top = parts[0];
      const sub = parts.slice(1).join('/') || null;
      if (!tree[top]) tree[top] = { subs: {}, total: 0 };
      tree[top].total++;
      if (sub) {
        if (!tree[top].subs[sub]) tree[top].subs[sub] = 0;
        tree[top].subs[sub]++;
      }
    });
  });

  let html = '';
  html += `<div class="cat-item ${currentFilter==='all'?'active':''}" onclick="filterBy('all')">
    All blueprints <span class="count">${total}</span></div>`;
  if (uncatCount > 0)
    html += `<div class="cat-item ${currentFilter==='uncategorized'?'active':''}" onclick="filterBy('uncategorized')"
      style="color:var(--orange)">⚠ Uncategorized <span class="count">${uncatCount}</span></div>`;

  Object.keys(tree).sort().forEach(top => {
    const g = tree[top];
    const hasSubs = Object.keys(g.subs).length > 0;
    const isGroupActive = currentFilter === 'group:' + top;
    const isExpanded = expandedGroups.has(top);

    html += `<div class="cat-group">`;
    html += `<div class="cat-group-label ${isGroupActive?'active':''}" onclick="filterByGroup('${escAttr(top)}')">
      <span>${hasSubs ? '<span class="arrow '+(isExpanded?'open':'')+'">▶</span>' : ''}${esc(top)}</span>
      <span class="count">${g.total}</span></div>`;

    if (hasSubs && isExpanded) {
      html += `<div class="cat-sub-items">`;
      Object.keys(g.subs).sort().forEach(sub => {
        const full = top + '/' + sub;
        html += `<div class="cat-item ${currentFilter===full?'active':''}" onclick="filterBy('${escAttr(full)}')">
          ${esc(sub)} <span class="count">${g.subs[sub]}</span></div>`;
      });
      html += `</div>`;
    }
    html += `</div>`;
  });

  document.getElementById('catTree').innerHTML = html;
  document.getElementById('sidebarStats').innerHTML =
    `${blueprints.length} files · ${total} subgraphs · ${allCategories.length} categories`;
}

function filterByGroup(top) {
  const groupKey = 'group:' + top;
  if (currentFilter === groupKey) {
    // clicking active group toggles expand
    if (expandedGroups.has(top)) expandedGroups.delete(top);
    else expandedGroups.add(top);
  } else {
    currentFilter = groupKey;
    expandedGroups.add(top);
  }
  renderSidebar();
  renderContent();
}

// ── Content ──
function renderContent() {
  const q = document.getElementById('searchInput').value.toLowerCase();
  let filtered = [];

  blueprints.forEach(bp => {
    const matchName = bp.filename.toLowerCase().includes(q);
    const sgs = bp.subgraphs.filter(sg => {
      const matchQ = matchName || sg.name.toLowerCase().includes(q) || (sg.category||'').toLowerCase().includes(q);
      if (!matchQ) return false;
      if (currentFilter === 'all') return true;
      if (currentFilter === 'uncategorized') return !sg.category;
      if (currentFilter.startsWith('group:')) {
        const group = currentFilter.slice(6);
        return sg.category && sg.category.split('/')[0] === group;
      }
      return sg.category === currentFilter;
    });
    if (sgs.length > 0) filtered.push({ ...bp, subgraphs: sgs });
  });

  if (currentView === 'grid') renderGrid(filtered);
  else renderTable(filtered);
}

function renderGrid(items) {
  let html = '<div class="bp-grid">';
  items.forEach(bp => {
    const hasMissing = bp.subgraphs.some(s => !s.category);
    html += `<div class="bp-card ${hasMissing?'no-cat':''}">`;
    if (bulkMode)
      html += `<input type="checkbox" class="checkbox" style="position:absolute;top:12px;right:12px"
        ${selectedSet.has(bp.filename)?'checked':''}
        onchange="toggleSelect('${escAttr(bp.filename)}', this.checked)">`;
    html += `<div class="bp-name">${esc(bp.filename.replace('.json',''))}</div>`;
    bp.subgraphs.forEach((sg, i) => {
      const catColor = sg.category ? categoryColor(sg.category) : 'var(--orange)';
      html += `<div class="bp-category">
        <span class="dot" style="background:${catColor}"></span>
        ${sg.category ? formatCategory(sg.category) : '<span class="badge warn">No category</span>'}
        ${bp.subgraphs.length > 1 ? `<span style="color:var(--text2);font-size:11px">(${esc(sg.name)})</span>` : ''}
      </div>`;
    });
    html += `<div class="bp-actions">
      <button class="btn" onclick="openEdit('${escAttr(bp.filename)}')">Edit Category</button>
      <button class="btn" onclick="openRename('${escAttr(bp.filename)}')">Rename</button>
    </div></div>`;
  });
  html += '</div>';
  document.getElementById('content').innerHTML = html;
}

function renderTable(items) {
  let html = `<table class="bp-table"><thead><tr>`;
  if (bulkMode) html += `<th style="width:30px"></th>`;
  html += `<th>Blueprint</th><th>Subgraph</th><th>Category</th><th>Actions</th></tr></thead><tbody>`;
  items.forEach(bp => {
    bp.subgraphs.forEach((sg, i) => {
      html += `<tr>`;
      if (bulkMode)
        html += `<td><input type="checkbox" class="checkbox" ${selectedSet.has(bp.filename)?'checked':''}
          onchange="toggleSelect('${escAttr(bp.filename)}', this.checked)"></td>`;
      html += `<td>${i===0 ? esc(bp.filename.replace('.json','')) : ''}</td>
        <td>${esc(sg.name)}</td>
        <td>`;
      if (sg.category) {
        const c = categoryColor(sg.category);
        html += `<span class="dot" style="background:${c};vertical-align:middle;display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px"></span>`;
        html += `<span class="editable" onclick="openEdit('${escAttr(bp.filename)}')">${formatCategory(sg.category)}</span>`;
      } else {
        html += `<span class="badge warn">No category</span>`;
      }
      html += `</td><td>
        <button class="btn" onclick="openEdit('${escAttr(bp.filename)}')">Edit</button>
        <button class="btn" onclick="openRename('${escAttr(bp.filename)}')">Rename</button>
      </td></tr>`;
    });
  });
  html += '</tbody></table>';
  document.getElementById('content').innerHTML = html;
}

// ── View toggle ──
function setView(v) {
  currentView = v;
  document.querySelectorAll('.view-toggle .btn').forEach(b => b.classList.toggle('active', b.dataset.view === v));
  renderContent();
}

// ── Filter ──
function filterBy(cat) {
  currentFilter = cat;
  renderSidebar();
  renderContent();
}

// ── Modals ──
function openEdit(filename) {
  const bp = blueprints.find(b => b.filename === filename);
  if (!bp) return;

  let html = `<div class="modal"><h3>Edit Category</h3>
    <p style="font-size:13px;color:var(--text2);margin-bottom:12px">${esc(filename)}</p>`;
  bp.subgraphs.forEach((sg, i) => {
    html += `<div class="sg-item" style="flex-direction:column;align-items:stretch">
      <label>${esc(sg.name)} ${!sg.category ? '<span class="badge warn">No category</span>' : ''}</label>
      ${catPickerHTML('cat_' + i, sg.category)}
    </div>`;
  });
  html += `<div class="modal-actions">
    <button class="btn" onclick="closeModal()">Cancel</button>
    <button class="btn primary" onclick="saveEdit('${escAttr(filename)}', ${bp.subgraphs.length})">Save</button>
  </div></div>`;
  showModal(html);
  initCatPickers();
}

async function saveEdit(filename, count) {
  for (let i = 0; i < count; i++) {
    const val = getCatPickerValue('cat_' + i);
    const bp = blueprints.find(b => b.filename === filename);
    const sg = bp.subgraphs[i];
    if (val !== sg.category) {
      await api('PUT', '/blueprints/' + encodeURIComponent(filename) + '/category', {
        sg_index: sg.index, category: val
      });
    }
  }
  closeModal();
  toast('Category updated');
  await loadData();
}

function openRename(filename) {
  let html = `<div class="modal"><h3>Rename Blueprint</h3>
    <label>Current name</label>
    <input type="text" value="${escAttr(filename)}" disabled>
    <label>New name</label>
    <input type="text" id="renameInput" value="${escAttr(filename)}">
    <div class="modal-actions">
      <button class="btn" onclick="closeModal()">Cancel</button>
      <button class="btn primary" onclick="saveRename('${escAttr(filename)}')">Rename</button>
    </div></div>`;
  showModal(html);
}

async function saveRename(oldName) {
  const newName = document.getElementById('renameInput').value.trim();
  if (!newName || newName === oldName) { closeModal(); return; }
  const r = await api('PUT', '/blueprints/' + encodeURIComponent(oldName) + '/rename', { new_name: newName });
  if (r.ok) { toast('Renamed successfully'); closeModal(); await loadData(); }
  else { toast(r.error || 'Rename failed', true); }
}

// ── Bulk mode ──
function bulkSetCategory() {
  bulkMode = true;
  selectedSet.clear();
  document.getElementById('bulkBar').style.display = 'flex';
  renderContent();
}
function exitBulk() {
  bulkMode = false;
  selectedSet.clear();
  document.getElementById('bulkBar').style.display = 'none';
  renderContent();
}
function toggleSelect(filename, checked) {
  if (checked) selectedSet.add(filename);
  else selectedSet.delete(filename);
  document.getElementById('bulkCount').textContent = selectedSet.size + ' selected';
}
function toggleSelectAll() {
  const checked = document.getElementById('selectAllCb').checked;
  if (checked) blueprints.forEach(bp => selectedSet.add(bp.filename));
  else selectedSet.clear();
  document.getElementById('bulkCount').textContent = selectedSet.size + ' selected';
  renderContent();
}
function bulkApplyCategory() {
  if (selectedSet.size === 0) { toast('Select blueprints first', true); return; }
  let html = `<div class="modal"><h3>Bulk Set Category</h3>
    <p style="font-size:13px;color:var(--text2)">${selectedSet.size} blueprint(s) selected</p>
    <label>Category</label>
    ${catPickerHTML('bulkCat', '')}
    <label style="margin-top:12px">Apply to</label>
    <select id="bulkTarget">
      <option value="primary">Primary subgraph only (index 0)</option>
      <option value="uncategorized">Uncategorized subgraphs only</option>
      <option value="all">All subgraphs</option>
    </select>
    <div class="modal-actions">
      <button class="btn" onclick="closeModal()">Cancel</button>
      <button class="btn primary" onclick="saveBulkCategory()">Apply</button>
    </div></div>`;
  showModal(html);
  initCatPickers();
}
async function saveBulkCategory() {
  const cat = getCatPickerValue('bulkCat');
  const target = document.getElementById('bulkTarget').value;
  if (!cat) { toast('Enter a category', true); return; }
  let count = 0;
  for (const filename of selectedSet) {
    const bp = blueprints.find(b => b.filename === filename);
    if (!bp) continue;
    for (const sg of bp.subgraphs) {
      let apply = false;
      if (target === 'primary' && sg.index === 0) apply = true;
      else if (target === 'uncategorized' && !sg.category) apply = true;
      else if (target === 'all') apply = true;
      if (apply) {
        await api('PUT', '/blueprints/' + encodeURIComponent(filename) + '/category', {
          sg_index: sg.index, category: cat
        });
        count++;
      }
    }
  }
  closeModal();
  exitBulk();
  toast(`Updated ${count} subgraph(s)`);
  await loadData();
}

// ── Modal helpers ──
function showModal(html) {
  const el = document.getElementById('modalOverlay');
  el.innerHTML = html;
  el.style.display = 'flex';
}
function closeModal() { document.getElementById('modalOverlay').style.display = 'none'; }

// ── Toast ──
function toast(msg, isError) {
  const el = document.createElement('div');
  el.className = 'toast' + (isError ? ' error' : '');
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3000);
}

// ── Utils ──
function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
function escAttr(s) { return s.replace(/&/g,'&amp;').replace(/'/g,'&#39;').replace(/"/g,'&quot;'); }
function formatCategory(cat) {
  const parts = cat.split('/');
  if (parts.length === 1) return esc(cat);
  return `<span style="color:var(--text2)">${esc(parts[0])}</span> <span style="color:var(--text2)">›</span> ${esc(parts.slice(1).join(' › '))}`;
}

// ── Category picker (two-level dropdowns) ──
function buildCatTree() {
  const tree = {};
  allCategories.forEach(c => {
    const parts = c.split('/');
    const top = parts[0];
    const sub = parts.slice(1).join('/') || null;
    if (!tree[top]) tree[top] = [];
    if (sub && !tree[top].includes(sub)) tree[top].push(sub);
  });
  for (const k in tree) tree[k].sort();
  return tree;
}

function catPickerHTML(id, currentValue) {
  const tree = buildCatTree();
  const parts = (currentValue || '').split('/');
  const curTop = parts[0] || '';
  const curSub = parts.slice(1).join('/') || '';
  const tops = Object.keys(tree).sort();

  let html = `<div class="cat-picker" style="display:flex;gap:6px;align-items:center">`;

  // Parent dropdown
  html += `<select id="${id}_top" onchange="onCatTopChange('${id}')" style="flex:1">`;
  html += `<option value="">— Select —</option>`;
  tops.forEach(t => { html += `<option value="${escAttr(t)}" ${t===curTop?'selected':''}>${esc(t)}</option>`; });
  html += `<option value="__new__">＋ New parent…</option>`;
  html += `</select>`;

  // Sub dropdown
  html += `<span style="color:var(--text2)">›</span>`;
  html += `<select id="${id}_sub" style="flex:1">`;
  html += `<option value="">— Select —</option>`;
  if (curTop && tree[curTop]) {
    tree[curTop].forEach(s => { html += `<option value="${escAttr(s)}" ${s===curSub?'selected':''}>${esc(s)}</option>`; });
  }
  html += `<option value="__new__">＋ New sub…</option>`;
  html += `</select>`;

  html += `</div>`;
  // Hidden inputs for custom new values
  html += `<input type="text" id="${id}_newTop" placeholder="New parent category" style="display:none;margin-top:4px">`;
  html += `<input type="text" id="${id}_newSub" placeholder="New sub-category" style="display:none;margin-top:4px">`;
  return html;
}

function onCatTopChange(id) {
  const tree = buildCatTree();
  const topSel = document.getElementById(id + '_top');
  const subSel = document.getElementById(id + '_sub');
  const newTopInput = document.getElementById(id + '_newTop');
  const newSubInput = document.getElementById(id + '_newSub');

  if (topSel.value === '__new__') {
    newTopInput.style.display = 'block';
    newTopInput.focus();
    subSel.innerHTML = '<option value="">— Select —</option><option value="__new__">＋ New sub…</option>';
  } else {
    newTopInput.style.display = 'none';
    newTopInput.value = '';
    const subs = tree[topSel.value] || [];
    let opts = '<option value="">— Select —</option>';
    subs.forEach(s => { opts += `<option value="${escAttr(s)}">${esc(s)}</option>`; });
    opts += '<option value="__new__">＋ New sub…</option>';
    subSel.innerHTML = opts;
  }
  newSubInput.style.display = 'none';
  newSubInput.value = '';
  subSel.onchange = () => {
    if (subSel.value === '__new__') { newSubInput.style.display = 'block'; newSubInput.focus(); }
    else { newSubInput.style.display = 'none'; newSubInput.value = ''; }
  };
}

function getCatPickerValue(id) {
  const topSel = document.getElementById(id + '_top');
  const subSel = document.getElementById(id + '_sub');
  const newTopInput = document.getElementById(id + '_newTop');
  const newSubInput = document.getElementById(id + '_newSub');

  let top = topSel.value === '__new__' ? newTopInput.value.trim() : topSel.value;
  let sub = subSel.value === '__new__' ? newSubInput.value.trim() : subSel.value;
  if (!top) return '';
  return sub ? top + '/' + sub : top;
}

// Init sub-dropdown change listeners after modal opens
function initCatPickers() {
  document.querySelectorAll('.cat-picker select[id$="_sub"]').forEach(sel => {
    const id = sel.id.replace('_sub', '');
    sel.onchange = () => {
      const newSubInput = document.getElementById(id + '_newSub');
      if (sel.value === '__new__') { newSubInput.style.display = 'block'; newSubInput.focus(); }
      else { newSubInput.style.display = 'none'; newSubInput.value = ''; }
    };
  });
}

const CAT_COLORS = {};
const PALETTE = ['#58a6ff','#3fb950','#d29922','#bc8cff','#f85149','#79c0ff','#56d364','#e3b341','#d2a8ff',
                 '#ff7b72','#a5d6ff','#7ee787','#f0e68c','#d8b4fe','#ffa198'];
function categoryColor(cat) {
  const top = cat.split('/')[0];
  if (!CAT_COLORS[top]) CAT_COLORS[top] = PALETTE[Object.keys(CAT_COLORS).length % PALETTE.length];
  return CAT_COLORS[top];
}

// ── Search ──
document.getElementById('searchInput').addEventListener('input', () => renderContent());

// ── Drag & Drop ──
let dragCounter = 0;
document.addEventListener('dragenter', e => { e.preventDefault(); dragCounter++;
  document.getElementById('dropOverlay').style.display = 'flex'; });
document.addEventListener('dragleave', e => { e.preventDefault(); dragCounter--;
  if (dragCounter <= 0) { dragCounter = 0; document.getElementById('dropOverlay').style.display = 'none'; } });
document.addEventListener('dragover', e => e.preventDefault());
document.addEventListener('drop', e => {
  e.preventDefault(); dragCounter = 0;
  document.getElementById('dropOverlay').style.display = 'none';
  const files = [...e.dataTransfer.files].filter(f => f.name.endsWith('.json'));
  if (files.length) handleFileSelect(files);
  else toast('No .json files found', true);
});

// ── Import ──
let pendingImports = []; // { file, name, category }

function openImport() { document.getElementById('fileInput').click(); }

function handleFileSelect(fileList) {
  const files = [...fileList].filter(f => f.name.endsWith('.json'));
  if (!files.length) { toast('No .json files selected', true); return; }

  pendingImports = files.map(f => ({ file: f, name: f.name, category: '' }));

  let html = `<div class="modal" style="width:640px"><h3>Import ${files.length} Blueprint(s)</h3>
    <p style="font-size:13px;color:var(--text2);margin-bottom:8px">
      Assign a category before importing, or leave blank to import without one.</p>
    <label>Default category for all</label>
    <div style="display:flex;gap:8px;align-items:start;margin-bottom:4px">
      <div style="flex:1">${catPickerHTML('importDefault', '')}</div>
      <button class="btn" style="margin-top:1px" onclick="applyDefaultCat()">Apply to all</button>
    </div>
    <div class="import-results" id="importList">`;
  files.forEach((f, i) => {
    html += `<div class="import-row" style="flex-direction:column;align-items:stretch">
      <span class="fname" style="margin-bottom:4px">${esc(f.name)}</span>
      ${catPickerHTML('importCat_' + i, '')}
    </div>`;
  });
  html += `</div>
    <div class="modal-actions">
      <button class="btn" onclick="closeModal()">Cancel</button>
      <button class="btn primary" onclick="doImport()">Import ${files.length} file(s)</button>
    </div></div>`;
  showModal(html);
  initCatPickers();
  document.getElementById('fileInput').value = '';
}

function applyDefaultCat() {
  const cat = getCatPickerValue('importDefault');
  if (!cat) return;
  const parts = cat.split('/');
  const top = parts[0];
  const sub = parts.slice(1).join('/') || '';
  pendingImports.forEach((_, i) => {
    const id = 'importCat_' + i;
    const topSel = document.getElementById(id + '_top');
    const subSel = document.getElementById(id + '_sub');
    topSel.value = top;
    onCatTopChange(id);
    if (sub) {
      // Try to select existing, or set to __new__ and fill
      const opt = [...subSel.options].find(o => o.value === sub);
      if (opt) subSel.value = sub;
      else { subSel.value = '__new__'; document.getElementById(id + '_newSub').style.display = 'block';
             document.getElementById(id + '_newSub').value = sub; }
    }
  });
}

async function doImport() {
  let ok = 0, fail = 0;
  for (let i = 0; i < pendingImports.length; i++) {
    const p = pendingImports[i];
    const cat = getCatPickerValue('importCat_' + i);
    try {
      const text = await p.file.text();
      JSON.parse(text); // validate JSON
      const r = await fetch('/api/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename: p.name, content: text, category: cat })
      });
      const res = await r.json();
      if (res.ok) ok++; else { fail++; console.error(p.name, res.error); }
    } catch(e) { fail++; console.error(p.name, e); }
  }
  closeModal();
  toast(`Imported ${ok} file(s)` + (fail ? `, ${fail} failed` : ''));
  await loadData();
}

// ── Init ──
loadData();
</script>
</body>
</html>"""


# ─── HTTP handler ───────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, html):
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length else {}

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/":
            self._html(HTML_PAGE)
        elif path == "/api/blueprints":
            self._json(scan_blueprints())
        elif path == "/api/categories":
            self._json(get_all_categories())
        else:
            self.send_error(404)

    def do_POST(self):
        path = self.path.split("?")[0]
        if path == "/api/import":
            body = self._read_body()
            ok, msg = import_blueprint(
                body.get("filename", ""),
                body.get("content", ""),
                body.get("category", ""),
            )
            self._json({"ok": ok, "error": msg}, 200 if ok else 400)
        else:
            self.send_error(404)

    def do_PUT(self):
        path = self.path.split("?")[0]
        if path.startswith("/api/blueprints/") and path.endswith("/category"):
            filename = urllib.parse.unquote(path.split("/")[3])
            body = self._read_body()
            ok, msg = update_category(filename, body.get("sg_index", 0), body.get("category", ""))
            self._json({"ok": ok, "message": msg}, 200 if ok else 400)
        elif path.startswith("/api/blueprints/") and path.endswith("/rename"):
            filename = urllib.parse.unquote(path.split("/")[3])
            body = self._read_body()
            ok, msg = rename_blueprint(filename, body.get("new_name", ""))
            self._json({"ok": ok, "error": msg}, 200 if ok else 400)
        else:
            self.send_error(404)


# ─── Main ───────────────────────────────────────────────────────────────────

def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Blueprint Manager Web UI")
    parser.add_argument("--blueprints", default=os.environ.get("BLUEPRINTS_DIR"),
                        help="Path to the ComfyUI blueprints directory (default: from .env)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8099")),
                        help="Port to serve on (default: 8099)")
    args = parser.parse_args()

    if not args.blueprints:
        parser.error("--blueprints is required (or set BLUEPRINTS_DIR in .env)")

    global BLUEPRINTS_DIR
    BLUEPRINTS_DIR = os.path.abspath(args.blueprints)

    if not os.path.isdir(BLUEPRINTS_DIR):
        print(f"Error: blueprints directory not found: {BLUEPRINTS_DIR}", file=__import__('sys').stderr)
        raise SystemExit(1)

    server = HTTPServer(("0.0.0.0", args.port), Handler)
    print(f"\n  🎨  Blueprint Manager running at http://localhost:{args.port}\n")
    print(f"  Blueprints dir: {BLUEPRINTS_DIR}")
    print(f"  Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()
