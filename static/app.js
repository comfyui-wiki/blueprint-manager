// ── State ──────────────────────────────────────────────────────────────────
let blueprints = [];
let allCategories = [];
let currentFilter = 'all';  // 'all' | 'uncategorized' | 'recent' | 'group:X' | 'X/Y'
let currentView = 'grid';
let sortOrder = 'name';     // 'name' | 'mtime_desc'
let scopeFilter = 'all';   // 'all' | 'recent_only'
let bulkMode = false;
let selectedSet = new Set();
let expandedGroups = new Set();

// ── API ────────────────────────────────────────────────────────────────────
async function api(method, path, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch('/api' + path, opts);
  return r.json();
}

// ── Recent imports ─────────────────────────────────────────────────────────
function recentImportCount() {
  return blueprints.filter(b => b.recent_import).length;
}

function isRecentImport(bp) {
  return !!bp.recent_import;
}

async function clearImportMarks() {
  await api('POST', '/clear-recent-imports');
  if (currentFilter === 'recent') currentFilter = 'all';
  scopeFilter = 'all';
  const sel = document.getElementById('scopeSelect');
  if (sel) sel.value = 'all';
  toast('Recent import marks cleared');
  await loadData();
}

function updateImportMarksButton() {
  const n = recentImportCount();
  const btn = document.getElementById('clearImportMarksBtn');
  if (!btn) return;
  btn.style.display = n ? 'inline-flex' : 'none';
  btn.textContent = 'Clear recent marks (' + n + ')';
}

// ── Load ───────────────────────────────────────────────────────────────────
async function loadData() {
  blueprints = await api('GET', '/blueprints');
  allCategories = await api('GET', '/categories');
  updateImportMarksButton();
  renderSidebar();
  renderContent();
}

function setScopeFilter(v) {
  scopeFilter = v;
  renderContent();
}

// ── Sidebar ────────────────────────────────────────────────────────────────
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

  const recentCount = recentImportCount();
  let html = '';

  html += `<div class="cat-item ${currentFilter==='all'?'active':''}" onclick="filterBy('all')">
    All blueprints <span class="count">${total}</span></div>`;

  if (recentCount > 0)
    html += `<div class="cat-item ${currentFilter==='recent'?'active':''}" onclick="filterBy('recent')"
      style="color:var(--green)">✦ Recent imports <span class="count">${recentCount}</span></div>`;

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
      <span>${hasSubs ? `<span class="arrow ${isExpanded?'open':''}">▶</span>` : ''}${esc(top)}</span>
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
  const key = 'group:' + top;
  if (currentFilter === key) {
    if (expandedGroups.has(top)) expandedGroups.delete(top);
    else expandedGroups.add(top);
  } else {
    currentFilter = key;
    expandedGroups.add(top);
  }
  renderSidebar();
  renderContent();
}

function filterBy(cat) {
  currentFilter = cat;
  renderSidebar();
  renderContent();
}

// ── Content ────────────────────────────────────────────────────────────────
function renderContent() {
  const q = document.getElementById('searchInput').value.toLowerCase();
  const baseList = scopeFilter === 'recent_only'
    ? blueprints.filter(b => b.recent_import)
    : blueprints;

  let filtered = [];
  baseList.forEach(bp => {
    const matchName = bp.filename.toLowerCase().includes(q);
    const sgs = bp.subgraphs.filter(sg => {
      const matchQ = matchName || sg.name.toLowerCase().includes(q) || (sg.category||'').toLowerCase().includes(q);
      if (!matchQ) return false;
      if (currentFilter === 'all') return true;
      if (currentFilter === 'recent') return isRecentImport(bp);
      if (currentFilter === 'uncategorized') return !sg.category;
      if (currentFilter.startsWith('group:')) {
        return sg.category && sg.category.split('/')[0] === currentFilter.slice(6);
      }
      return sg.category === currentFilter;
    });
    if (sgs.length > 0) {
      // In grid + uncategorized view, show all subgraphs so categorised siblings aren't hidden
      const showAll = currentView === 'grid' && currentFilter === 'uncategorized';
      filtered.push({ ...bp, subgraphs: showAll ? bp.subgraphs : sgs });
    }
  });

  filtered.sort((a, b) => {
    if (sortOrder === 'mtime_desc') {
      const diff = (b.mtime ?? 0) - (a.mtime ?? 0);
      if (diff !== 0) return diff;
    }
    return a.filename.localeCompare(b.filename);
  });

  if (currentView === 'grid') renderGrid(filtered);
  else renderTable(filtered);
}

function setSort(v) { sortOrder = v; renderContent(); }
function setView(v) {
  currentView = v;
  document.querySelectorAll('.view-toggle .btn').forEach(b => b.classList.toggle('active', b.dataset.view === v));
  renderContent();
}

// ── Grid / Table ───────────────────────────────────────────────────────────
// ── Action dropdown helper ─────────────────────────────────────────────────
function moreMenu(fn) {
  const f = escAttr(fn);
  return `<div class="more-menu">
    <button class="btn more-trigger" onclick="toggleMoreMenu(this)" title="More actions">⋯</button>
    <div class="more-dropdown">
      <button class="dropdown-item" onclick="downloadBlueprint('${f}')">↓ Download</button>
      <button class="dropdown-item" onclick="openRename('${f}')">Rename</button>
      <button class="dropdown-item" onclick="openReplace('${f}')">Replace file…</button>
      <button class="dropdown-item" onclick="openValidate('${f}')">Validate schema</button>
      <div class="dropdown-divider"></div>
      <button class="dropdown-item danger" onclick="openDelete('${f}')">Delete</button>
    </div>
  </div>`;
}

function toggleMoreMenu(btn) {
  const menu = btn.closest('.more-menu');
  const isOpen = menu.classList.contains('open');
  document.querySelectorAll('.more-menu.open').forEach(m => m.classList.remove('open'));
  if (!isOpen) {
    menu.classList.add('open');
    const close = (e) => {
      if (!menu.contains(e.target)) { menu.classList.remove('open'); document.removeEventListener('click', close); }
    };
    setTimeout(() => document.addEventListener('click', close), 0);
  }
}

function renderGrid(items) {
  let html = '<div class="bp-grid">';
  items.forEach(bp => {
    const hasMissing = bp.subgraphs.some(s => !s.category);
    const isNew = isRecentImport(bp);
    html += `<div class="bp-card ${hasMissing?'no-cat':''} ${isNew?'session-new':''}">`;
    if (bulkMode)
      html += `<input type="checkbox" class="checkbox" style="position:absolute;top:12px;right:12px"
        ${selectedSet.has(bp.filename)?'checked':''}
        onchange="toggleSelect('${escAttr(bp.filename)}', this.checked)">`;
    html += `<div class="bp-name">${esc(bp.filename.replace('.json',''))}`;
    if (isNew) html += ` <span class="badge new-import">New</span>`;
    html += `</div>`;
    bp.subgraphs.forEach(sg => {
      const catColor = sg.category ? categoryColor(sg.category) : 'var(--orange)';
      html += `<div class="bp-category">
        <span class="dot" style="background:${catColor}"></span>
        ${sg.category ? formatCategory(sg.category) : '<span class="badge warn">No category</span>'}
        ${bp.subgraphs.length > 1 ? `<span style="color:var(--text2);font-size:11px">(${esc(sg.name)})</span>` : ''}
      </div>`;
    });
    html += `<div class="bp-actions">
      <button class="btn" onclick="openView('${escAttr(bp.filename)}')">View / Edit</button>
      <button class="btn" onclick="openEdit('${escAttr(bp.filename)}')">Category</button>
      ${moreMenu(bp.filename)}
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
      const isNew = isRecentImport(bp);
      html += `<td>${i===0 ? esc(bp.filename.replace('.json','')) +
        (isNew ? ' <span class="badge new-import">New</span>' : '') : ''}</td>
        <td>${esc(sg.name)}</td><td>`;
      if (sg.category) {
        const c = categoryColor(sg.category);
        html += `<span class="dot" style="background:${c};vertical-align:middle;display:inline-block;
          width:8px;height:8px;border-radius:50%;margin-right:6px"></span>`;
        html += `<span class="editable" onclick="openEdit('${escAttr(bp.filename)}')">${formatCategory(sg.category)}</span>`;
      } else {
        html += `<span class="badge warn">No category</span>`;
      }
      html += `</td><td>
        <div style="display:flex;gap:4px;align-items:center">
          <button class="btn" onclick="openView('${escAttr(bp.filename)}')">View / Edit</button>
          <button class="btn" onclick="openEdit('${escAttr(bp.filename)}')">Category</button>
          ${moreMenu(bp.filename)}
        </div>
      </td></tr>`;
    });
  });
  html += '</tbody></table>';
  document.getElementById('content').innerHTML = html;
}

// ── Modals ─────────────────────────────────────────────────────────────────
function showModal(html) {
  const el = document.getElementById('modalOverlay');
  el.innerHTML = html;
  el.style.display = 'flex';
}
function closeModal() { document.getElementById('modalOverlay').style.display = 'none'; }

// Edit category
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
    if (val !== sg.category)
      await api('PUT', '/blueprints/' + encodeURIComponent(filename) + '/category', { sg_index: sg.index, category: val });
  }
  closeModal();
  toast('Category updated');
  await loadData();
}

// Rename
function openRename(filename) {
  showModal(`<div class="modal"><h3>Rename Blueprint</h3>
    <label>Current name</label>
    <input type="text" value="${escAttr(filename)}" disabled>
    <label>New name</label>
    <input type="text" id="renameInput" value="${escAttr(filename)}">
    <div class="modal-actions">
      <button class="btn" onclick="closeModal()">Cancel</button>
      <button class="btn primary" onclick="saveRename('${escAttr(filename)}')">Rename</button>
    </div></div>`);
}

async function saveRename(oldName) {
  const newName = document.getElementById('renameInput').value.trim();
  if (!newName || newName === oldName) { closeModal(); return; }
  const r = await api('PUT', '/blueprints/' + encodeURIComponent(oldName) + '/rename', { new_name: newName });
  if (r.ok) { toast('Renamed'); closeModal(); await loadData(); }
  else toast(r.error || 'Rename failed', true);
}

// Delete
function openDelete(filename) {
  showModal(`<div class="modal"><h3>Delete blueprint</h3>
    <p style="font-size:13px;color:var(--text2);margin-bottom:12px">
      This will permanently delete the file from your blueprints folder.</p>
    <p style="font-size:14px;font-weight:600;margin-bottom:16px">${esc(filename)}</p>
    <div class="modal-actions">
      <button class="btn" onclick="closeModal()">Cancel</button>
      <button class="btn danger" onclick="confirmDelete('${escAttr(filename)}')">Delete</button>
    </div></div>`);
}

async function confirmDelete(filename) {
  const r = await api('DELETE', '/blueprints/' + encodeURIComponent(filename));
  if (r.ok) { closeModal(); selectedSet.delete(filename); toast('Deleted'); await loadData(); }
  else toast(r.error || 'Delete failed', true);
}

// ── Bulk mode ──────────────────────────────────────────────────────────────
function bulkSetCategory() {
  bulkMode = true; selectedSet.clear();
  document.getElementById('bulkBar').style.display = 'flex';
  renderContent();
}
function exitBulk() {
  bulkMode = false; selectedSet.clear();
  document.getElementById('bulkBar').style.display = 'none';
  renderContent();
}
function toggleSelect(filename, checked) {
  if (checked) selectedSet.add(filename); else selectedSet.delete(filename);
  document.getElementById('bulkCount').textContent = selectedSet.size + ' selected';
}
function toggleSelectAll() {
  const checked = document.getElementById('selectAllCb').checked;
  if (checked) blueprints.forEach(bp => selectedSet.add(bp.filename)); else selectedSet.clear();
  document.getElementById('bulkCount').textContent = selectedSet.size + ' selected';
  renderContent();
}
function bulkApplyCategory() {
  if (selectedSet.size === 0) { toast('Select blueprints first', true); return; }
  showModal(`<div class="modal"><h3>Bulk Set Category</h3>
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
    </div></div>`);
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
      const apply = target === 'all' ||
        (target === 'primary' && sg.index === 0) ||
        (target === 'uncategorized' && !sg.category);
      if (apply) {
        await api('PUT', '/blueprints/' + encodeURIComponent(filename) + '/category', { sg_index: sg.index, category: cat });
        count++;
      }
    }
  }
  closeModal(); exitBulk();
  toast(`Updated ${count} subgraph(s)`);
  await loadData();
}

// ── Toast ──────────────────────────────────────────────────────────────────
function toast(msg, isError) {
  const el = document.createElement('div');
  el.className = 'toast' + (isError ? ' error' : '');
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3000);
}

// ── Utils ──────────────────────────────────────────────────────────────────
function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
function escAttr(s) { return s.replace(/&/g,'&amp;').replace(/'/g,'&#39;').replace(/"/g,'&quot;'); }
function formatCategory(cat) {
  const parts = cat.split('/');
  if (parts.length === 1) return esc(cat);
  return `<span style="color:var(--text2)">${esc(parts[0])}</span>
    <span style="color:var(--text2)">›</span> ${esc(parts.slice(1).join(' › '))}`;
}

const CAT_COLORS = {};
const PALETTE = ['#58a6ff','#3fb950','#d29922','#bc8cff','#f85149','#79c0ff','#56d364',
                 '#e3b341','#d2a8ff','#ff7b72','#a5d6ff','#7ee787','#f0e68c','#d8b4fe','#ffa198'];
function categoryColor(cat) {
  const top = cat.split('/')[0];
  if (!CAT_COLORS[top]) CAT_COLORS[top] = PALETTE[Object.keys(CAT_COLORS).length % PALETTE.length];
  return CAT_COLORS[top];
}

// ── Category picker (two-level dropdowns) ──────────────────────────────────
function buildCatTree() {
  const tree = {};
  allCategories.forEach(c => {
    const parts = c.split('/');
    const top = parts[0], sub = parts.slice(1).join('/') || null;
    if (!tree[top]) tree[top] = [];
    if (sub && !tree[top].includes(sub)) tree[top].push(sub);
  });
  for (const k in tree) tree[k].sort();
  return tree;
}

function catPickerHTML(id, currentValue) {
  const tree = buildCatTree();
  const parts = (currentValue || '').split('/');
  const curTop = parts[0] || '', curSub = parts.slice(1).join('/') || '';
  const tops = Object.keys(tree).sort();

  let html = `<div class="cat-picker" style="display:flex;gap:6px;align-items:center">
    <select id="${id}_top" onchange="onCatTopChange('${id}')" style="flex:1">
      <option value="">— Select —</option>`;
  tops.forEach(t => { html += `<option value="${escAttr(t)}" ${t===curTop?'selected':''}>${esc(t)}</option>`; });
  html += `<option value="__new__">＋ New parent…</option></select>
    <span style="color:var(--text2)">›</span>
    <select id="${id}_sub" style="flex:1">
      <option value="">— Select —</option>`;
  if (curTop && tree[curTop])
    tree[curTop].forEach(s => { html += `<option value="${escAttr(s)}" ${s===curSub?'selected':''}>${esc(s)}</option>`; });
  html += `<option value="__new__">＋ New sub…</option></select></div>
    <input type="text" id="${id}_newTop" placeholder="New parent category" style="display:none;margin-top:4px">
    <input type="text" id="${id}_newSub" placeholder="New sub-category" style="display:none;margin-top:4px">`;
  return html;
}

function onCatTopChange(id) {
  const tree = buildCatTree();
  const topSel = document.getElementById(id + '_top');
  const subSel = document.getElementById(id + '_sub');
  const newTopInput = document.getElementById(id + '_newTop');
  const newSubInput = document.getElementById(id + '_newSub');
  if (topSel.value === '__new__') {
    newTopInput.style.display = 'block'; newTopInput.focus();
    subSel.innerHTML = '<option value="">— Select —</option><option value="__new__">＋ New sub…</option>';
  } else {
    newTopInput.style.display = 'none'; newTopInput.value = '';
    const subs = tree[topSel.value] || [];
    let opts = '<option value="">— Select —</option>';
    subs.forEach(s => { opts += `<option value="${escAttr(s)}">${esc(s)}</option>`; });
    opts += '<option value="__new__">＋ New sub…</option>';
    subSel.innerHTML = opts;
  }
  newSubInput.style.display = 'none'; newSubInput.value = '';
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
  const top = topSel.value === '__new__' ? newTopInput.value.trim() : topSel.value;
  const sub = subSel.value === '__new__' ? newSubInput.value.trim() : subSel.value;
  if (!top) return '';
  return sub ? top + '/' + sub : top;
}

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

// ── Search ─────────────────────────────────────────────────────────────────
document.getElementById('searchInput').addEventListener('input', () => renderContent());

// ── Drag & Drop import ─────────────────────────────────────────────────────
let dragCounter = 0;
document.addEventListener('dragenter', e => {
  e.preventDefault(); dragCounter++;
  document.getElementById('dropOverlay').style.display = 'flex';
});
document.addEventListener('dragleave', e => {
  e.preventDefault(); dragCounter--;
  if (dragCounter <= 0) { dragCounter = 0; document.getElementById('dropOverlay').style.display = 'none'; }
});
document.addEventListener('dragover', e => e.preventDefault());
document.addEventListener('drop', e => {
  e.preventDefault(); dragCounter = 0;
  document.getElementById('dropOverlay').style.display = 'none';
  const files = [...e.dataTransfer.files].filter(f => f.name.endsWith('.json'));
  if (files.length) handleFileSelect(files);
  else toast('No .json files found', true);
});

// ── Import ─────────────────────────────────────────────────────────────────
let pendingImports = [];

function openImport() { document.getElementById('fileInput').click(); }

function handleFileSelect(fileList) {
  const files = [...fileList].filter(f => f.name.endsWith('.json'));
  if (!files.length) { toast('No .json files selected', true); return; }
  pendingImports = files.map(f => ({ file: f, name: f.name }));

  let html = `<div class="modal" style="width:640px"><h3>Import ${files.length} Blueprint(s)</h3>
    <p style="font-size:13px;color:var(--text2);margin-bottom:8px">
      Assign a category before importing, or leave blank.</p>
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
  html += `</div><div class="modal-actions">
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
  const parts = cat.split('/'), top = parts[0], sub = parts.slice(1).join('/') || '';
  pendingImports.forEach((_, i) => {
    const id = 'importCat_' + i;
    const topSel = document.getElementById(id + '_top');
    const subSel = document.getElementById(id + '_sub');
    topSel.value = top; onCatTopChange(id);
    if (sub) {
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
      JSON.parse(text); // validate
      const r = await fetch('/api/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename: p.name, content: text, category: cat }),
      });
      const res = await r.json();
      if (res.ok) ok++; else { fail++; console.error(p.name, res.error); }
    } catch(e) { fail++; console.error(p.name, e); }
  }
  closeModal();
  toast(`Imported ${ok} file(s)` + (fail ? `, ${fail} failed` : ''));
  await loadData();
}

// ── JSON View / Edit modal (powered by Ace Editor) ────────────────────────
let _viewingFilename = null;
let _aceEditor = null;

async function openView(filename) {
  _viewingFilename = filename;
  const r = await api('GET', '/blueprints/' + encodeURIComponent(filename) + '/content');
  if (!r.ok) { toast(r.error || 'Failed to load', true); return; }

  const el = document.getElementById('modalOverlay');
  el.innerHTML = `<div class="json-editor-modal">
    <div class="je-header">
      <h3>${esc(filename)}</h3>
      <button class="btn" onclick="downloadBlueprint('${escAttr(filename)}')">↓ Download</button>
    </div>
    <div id="aceContainer" class="je-ace-container"></div>
    <div class="je-footer">
      <span class="je-error" id="jeError"></span>
      <button class="btn" onclick="jeFormat()">Format JSON</button>
      <button class="btn" onclick="closeModal()">Cancel</button>
      <button class="btn primary" id="jeSaveBtn" onclick="jeSave()">Save</button>
    </div>
  </div>`;
  el.style.display = 'flex';

  // Destroy previous instance if any
  if (_aceEditor) { _aceEditor.destroy(); _aceEditor = null; }

  _aceEditor = ace.edit('aceContainer');
  _aceEditor.setTheme('ace/theme/one_dark');
  _aceEditor.session.setMode('ace/mode/json');
  _aceEditor.setValue(r.content, -1);  // -1 = move cursor to start
  _aceEditor.setOptions({
    fontSize: '13px',
    fontFamily: "'Menlo', 'Monaco', 'Consolas', monospace",
    showPrintMargin: false,
    tabSize: 2,
    useSoftTabs: true,
    wrap: false,
  });

  // Cmd/Ctrl+S to save
  _aceEditor.commands.addCommand({
    name: 'save',
    bindKey: { win: 'Ctrl-S', mac: 'Command-S' },
    exec: jeSave,
  });

  // Live JSON validation
  _aceEditor.session.on('change', () => {
    const errEl = document.getElementById('jeError');
    const saveBtn = document.getElementById('jeSaveBtn');
    if (!errEl) return;
    try {
      JSON.parse(_aceEditor.getValue());
      errEl.textContent = '';
      if (saveBtn) saveBtn.disabled = false;
    } catch(e) {
      errEl.textContent = '✗ ' + e.message;
      if (saveBtn) saveBtn.disabled = true;
    }
  });

  _aceEditor.focus();
}

function jeFormat() {
  if (!_aceEditor) return;
  try {
    const formatted = JSON.stringify(JSON.parse(_aceEditor.getValue()), null, 2);
    _aceEditor.setValue(formatted, -1);
  } catch(e) { toast('Cannot format: invalid JSON', true); }
}

async function jeSave() {
  if (!_aceEditor) return;
  const content = _aceEditor.getValue();
  const r = await api('PUT', '/blueprints/' + encodeURIComponent(_viewingFilename) + '/content', { content });
  if (r.ok) { toast('Saved'); closeModal(); await loadData(); }
  else toast(r.error || 'Save failed', true);
}

// Clean up Ace when modal closes
const _origCloseModal = closeModal;
closeModal = function() {
  if (_aceEditor) { _aceEditor.destroy(); _aceEditor = null; }
  _origCloseModal();
};

// ── Schema validation ──────────────────────────────────────────────────────

/** Render a validation result object into an HTML string for display. */
function renderValidationResult(result) {
  const { ok, error_count, warning_count, issues } = result;

  // Summary pill
  let summary = '';
  if (ok && warning_count === 0) {
    summary = `<div class="val-summary ok">✓ All checks passed</div>`;
  } else {
    const parts = [];
    if (error_count > 0) parts.push(`${error_count} error${error_count > 1 ? 's' : ''}`);
    if (warning_count > 0) parts.push(`${warning_count} warning${warning_count > 1 ? 's' : ''}`);
    summary = `<div class="val-summary ${ok ? 'warn' : 'err'}">${ok ? '⚠' : '✗'} ${parts.join(', ')}</div>`;
  }

  if (!issues || issues.length === 0) return summary;

  const rows = issues.map(i => {
    const icon = i.level === 'error' ? '✗' : '⚠';
    const cls  = i.level === 'error' ? 'val-err' : 'val-warn';
    return `<tr class="${cls}">
      <td style="padding:5px 8px;white-space:nowrap">${icon}</td>
      <td style="padding:5px 8px;font-family:monospace;font-size:11px;color:var(--text2);white-space:nowrap">${esc(i.path)}</td>
      <td style="padding:5px 8px">${esc(i.message)}</td>
    </tr>`;
  }).join('');

  return `${summary}
    <div style="overflow-x:auto;margin-top:12px">
      <table style="width:100%;border-collapse:collapse;font-size:12px">
        <thead><tr style="color:var(--text2)">
          <th style="padding:5px 8px;text-align:left;border-bottom:1px solid var(--border)"></th>
          <th style="padding:5px 8px;text-align:left;border-bottom:1px solid var(--border)">Path</th>
          <th style="padding:5px 8px;text-align:left;border-bottom:1px solid var(--border)">Issue</th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

/** Validate a single blueprint file and show a modal with the results. */
async function openValidate(filename) {
  showModal(`<div class="modal" style="width:640px;max-width:96vw">
    <h3>Schema Validation</h3>
    <p style="font-size:13px;color:var(--text2);margin-bottom:16px">${esc(filename)}</p>
    <div id="valContent" style="font-size:13px">
      <span style="color:var(--text2)">Validating…</span>
    </div>
    <div class="modal-actions" style="margin-top:20px">
      <button class="btn primary" onclick="closeModal()">Close</button>
    </div>
  </div>`);

  const r = await api('GET', '/blueprints/' + encodeURIComponent(filename) + '/validate');
  document.getElementById('valContent').innerHTML = renderValidationResult(r);
}

/** Validate all blueprint files and show a summary modal. */
async function openValidateAll() {
  showModal(`<div class="modal" style="width:760px;max-width:96vw;max-height:85vh">
    <h3>Validate All Blueprints</h3>
    <div id="valAllContent" style="font-size:13px;margin-top:4px">
      <span style="color:var(--text2)">Validating all files…</span>
    </div>
    <div class="modal-actions" style="margin-top:16px">
      <button class="btn primary" onclick="closeModal()">Close</button>
    </div>
  </div>`);

  const results = await api('GET', '/validate-all');
  if (!Array.isArray(results)) {
    document.getElementById('valAllContent').innerHTML =
      `<span style="color:var(--red)">Failed to load validation results.</span>`;
    return;
  }

  const total   = results.length;
  const passed  = results.filter(r => r.ok && r.warning_count === 0).length;
  const warned  = results.filter(r => r.ok && r.warning_count > 0).length;
  const failed  = results.filter(r => !r.ok).length;

  let html = `<div style="display:flex;gap:16px;margin-bottom:16px;flex-wrap:wrap;font-size:13px">
    <span>${total} files checked</span>
    <span style="color:var(--green)">✓ ${passed} passed</span>
    ${warned  ? `<span style="color:var(--orange)">⚠ ${warned} with warnings</span>` : ''}
    ${failed  ? `<span style="color:var(--red)">✗ ${failed} with errors</span>` : ''}
  </div>`;

  // Sort: errors first, then warnings, then clean
  const sorted = [...results].sort((a, b) => {
    const rank = r => (!r.ok ? 0 : r.warning_count > 0 ? 1 : 2);
    return rank(a) - rank(b) || a.filename.localeCompare(b.filename);
  });

  html += `<div style="overflow-y:auto;max-height:52vh">`;
  sorted.forEach(r => {
    const hasIssues = r.error_count > 0 || r.warning_count > 0;
    const statusIcon = !r.ok ? '✗' : r.warning_count > 0 ? '⚠' : '✓';
    const statusColor = !r.ok ? 'var(--red)' : r.warning_count > 0 ? 'var(--orange)' : 'var(--green)';
    const badge = !r.ok
      ? `${r.error_count}E ${r.warning_count}W`
      : r.warning_count > 0 ? `${r.warning_count}W` : '';

    html += `<details class="val-file-row" ${!r.ok ? 'open' : ''}>
      <summary style="display:flex;align-items:center;gap:8px;padding:8px 4px;cursor:pointer;
        border-bottom:1px solid var(--border);list-style:none;user-select:none">
        <span style="color:${statusColor};width:16px;text-align:center">${statusIcon}</span>
        <span style="flex:1;font-size:12px;word-break:break-all">${esc(r.filename)}</span>
        ${badge ? `<span style="font-size:11px;color:${statusColor};white-space:nowrap">${badge}</span>` : ''}
        ${hasIssues ? `<span style="font-size:10px;color:var(--text2)">▼</span>` : ''}
      </summary>`;
    if (hasIssues) {
      html += `<div style="padding:8px 0 4px 24px">${renderValidationResult(r)}</div>`;
    }
    html += `</details>`;
  });
  html += `</div>`;

  document.getElementById('valAllContent').innerHTML = html;
}

// ── Replace file ──────────────────────────────────────────────────────────
let _replaceContent = null;

function openReplace(filename) {
  _replaceContent = null;
  const bp = blueprints.find(b => b.filename === filename);
  if (!bp) return;

  showModal(`<div class="modal" style="width:600px;max-width:96vw">
    <h3>Replace Blueprint</h3>
    <p style="font-size:13px;color:var(--text2);margin-bottom:16px">${esc(filename)}</p>
    <div id="replaceDropZone" class="replace-dropzone"
      onclick="document.getElementById('replaceFileInput').click()">
      <input type="file" id="replaceFileInput" accept=".json" style="display:none"
        onchange="handleReplaceFile(this.files[0],'${escAttr(filename)}')">
      <div style="font-size:28px;margin-bottom:6px;opacity:.6">📂</div>
      <div style="font-size:13px;color:var(--text2)">Click to select a .json file, or drag &amp; drop</div>
    </div>
    <div id="replaceValidation" style="margin-top:16px"></div>
    <div class="modal-actions">
      <button class="btn" onclick="closeModal()">Cancel</button>
      <button class="btn primary" id="replaceConfirmBtn" disabled
        onclick="confirmReplace('${escAttr(filename)}')">Replace</button>
    </div>
  </div>`);

  const dz = document.getElementById('replaceDropZone');
  dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('dragover'); });
  dz.addEventListener('dragleave', () => dz.classList.remove('dragover'));
  dz.addEventListener('drop', e => {
    e.preventDefault(); dz.classList.remove('dragover');
    const f = [...e.dataTransfer.files].find(f => f.name.endsWith('.json'));
    if (f) handleReplaceFile(f, filename);
    else toast('Please drop a .json file', true);
  });
}

async function handleReplaceFile(file, filename) {
  const bp = blueprints.find(b => b.filename === filename);
  if (!file || !bp) return;

  let text, newData;
  try {
    text = await file.text();
    newData = JSON.parse(text);
  } catch(e) {
    document.getElementById('replaceValidation').innerHTML =
      `<div style="padding:12px;background:rgba(248,81,73,.08);border-radius:var(--radius);
        color:var(--red);font-size:13px">✗ Invalid JSON — ${esc(e.message)}</div>`;
    document.getElementById('replaceConfirmBtn').disabled = true;
    return;
  }

  _replaceContent = text;
  const newSgs = newData?.definitions?.subgraphs ?? [];
  const oldSgs = bp.subgraphs;
  const sameCount = newSgs.length === oldSgs.length;

  let html = `<div style="font-size:13px">`;

  // Summary row
  html += `<div style="display:flex;gap:16px;margin-bottom:14px;flex-wrap:wrap">
    <span style="color:var(--green)">✓ Valid JSON</span>
    <span>Subgraphs: <b>${oldSgs.length}</b> → <b>${newSgs.length}</b>
      ${sameCount
        ? '<span style="color:var(--green)">✓ same count</span>'
        : '<span style="color:var(--orange)">⚠ count changed</span>'}
    </span>
  </div>`;

  // Comparison table
  if (newSgs.length > 0 || oldSgs.length > 0) {
    html += `<div style="overflow-x:auto;margin-bottom:14px">
    <table style="width:100%;border-collapse:collapse;font-size:12px">
      <thead><tr style="color:var(--text2)">
        <th style="padding:5px 8px;text-align:left;border-bottom:1px solid var(--border)">#</th>
        <th style="padding:5px 8px;text-align:left;border-bottom:1px solid var(--border)">Current name</th>
        <th style="padding:5px 8px;text-align:left;border-bottom:1px solid var(--border)">New name</th>
        <th style="padding:5px 8px;text-align:left;border-bottom:1px solid var(--border)">Current category</th>
        <th style="padding:5px 8px;text-align:left;border-bottom:1px solid var(--border)">ID</th>
      </tr></thead><tbody>`;
    const maxLen = Math.max(oldSgs.length, newSgs.length);
    for (let i = 0; i < maxLen; i++) {
      const o = oldSgs[i], n = newSgs[i];
      const nameMatch = o && n && o.name === n.name;
      const idMatch = o && n && o.id === n.id;
      html += `<tr>
        <td style="padding:5px 8px;color:var(--text2);border-bottom:1px solid var(--border)">${i}</td>
        <td style="padding:5px 8px;border-bottom:1px solid var(--border)">${o ? esc(o.name) : '<span style="color:var(--text2)">—</span>'}</td>
        <td style="padding:5px 8px;border-bottom:1px solid var(--border);${!nameMatch&&o&&n?'color:var(--orange)':''}">${n ? esc(n.name) : '<span style="color:var(--text2)">—</span>'}</td>
        <td style="padding:5px 8px;border-bottom:1px solid var(--border);color:var(--text2)">${o?.category ? esc(o.category) : '—'}</td>
        <td style="padding:5px 8px;border-bottom:1px solid var(--border)">${idMatch ? '<span style="color:var(--green)">✓ match</span>' : (o&&n ? '<span style="color:var(--orange)">≠</span>' : '<span style="color:var(--text2)">—</span>')}</td>
      </tr>`;
    }
    html += `</tbody></table></div>`;
  }

  // Preserve categories toggle
  html += `<label style="display:flex;align-items:center;gap:8px;cursor:pointer;
    padding:10px;background:var(--surface2);border-radius:var(--radius)">
    <input type="checkbox" id="preserveCatsCheck" checked style="accent-color:var(--accent)">
    <span><b>Preserve existing category assignments</b><br>
    <span style="font-size:11px;color:var(--text2)">
      Match by subgraph ID first, then by position. Unmatched subgraphs keep the new file's categories.
    </span></span>
  </label>`;

  html += `</div>`;
  document.getElementById('replaceValidation').innerHTML = html;
  document.getElementById('replaceConfirmBtn').disabled = false;
}

async function confirmReplace(filename) {
  if (!_replaceContent) return;
  const preserve = document.getElementById('preserveCatsCheck')?.checked ?? true;
  const r = await api('PUT', '/blueprints/' + encodeURIComponent(filename) + '/replace', {
    content: _replaceContent,
    preserve_categories: preserve,
  });
  if (r.ok) { toast('Replaced successfully'); closeModal(); await loadData(); }
  else toast(r.error || 'Replace failed', true);
}

// ── Download ───────────────────────────────────────────────────────────────
async function downloadBlueprint(filename) {
  const r = await api('GET', '/blueprints/' + encodeURIComponent(filename) + '/content');
  if (!r.ok) { toast(r.error || 'Failed to load', true); return; }
  const blob = new Blob([r.content], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// ── Init ───────────────────────────────────────────────────────────────────
loadData();
