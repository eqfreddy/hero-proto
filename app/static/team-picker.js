// Portrait-based team picker — replaces the "comma-separated hero IDs"
// input on Stages / Arena / Raids (bug #6). Self-contained modal.
//
// Usage:
//   teamPicker.open({
//     teamSize: 3,                   // max picks (default 3)
//     initial: [12, 5, 88],          // pre-selected hero ids (optional)
//     title: 'Pick team — Stage 1-3',// modal title
//     onConfirm: (heroIds) => {...}, // called when user clicks Use Team
//     showPresets: true,             // include preset CRUD section (default true)
//   });
//
// Reads /heroes/mine + /me/team-presets + /me/last-team. Talks to
// /me/team-presets (POST upsert / DELETE) for preset CRUD.

(function () {
  const MODAL_ID = 'team-picker-modal';
  const STYLE_ID = 'team-picker-style';

  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const css = document.createElement('style');
    css.id = STYLE_ID;
    css.textContent = `
      #${MODAL_ID} {
        position: fixed; inset: 0; z-index: 9000;
        display: none; align-items: flex-start; justify-content: center;
        background: rgba(0, 0, 0, 0.72); padding: 4vh 16px;
        animation: tp-fade 180ms ease;
      }
      #${MODAL_ID}.open { display: flex; }
      @keyframes tp-fade { from { opacity: 0; } to { opacity: 1; } }
      #${MODAL_ID} .tp-sheet {
        background: var(--panel); border: 1px solid var(--border);
        border-radius: 10px; padding: 18px; width: 100%; max-width: 920px;
        max-height: 92vh; overflow-y: auto; position: relative;
      }
      #${MODAL_ID} .tp-close {
        position: absolute; top: 10px; right: 12px;
        background: rgba(255,255,255,0.06); border: 1px solid var(--border);
        color: var(--text); width: 32px; height: 32px; border-radius: 50%;
        font-size: 18px; cursor: pointer;
      }
      #${MODAL_ID} h3 {
        margin: 0 0 12px; font-size: 13px; color: var(--muted);
        text-transform: uppercase; letter-spacing: 0.06em;
      }
      #${MODAL_ID} .tp-selected {
        display: flex; gap: 10px; margin-bottom: 14px;
        padding: 10px; border-radius: 6px;
        background: rgba(78, 161, 255, 0.06);
        border: 1px dashed var(--accent);
        min-height: 88px;
      }
      #${MODAL_ID} .tp-slot {
        flex: 1; min-width: 0; aspect-ratio: 3/4;
        border: 2px dashed var(--border); border-radius: 6px;
        display: flex; align-items: center; justify-content: center;
        color: var(--muted); font-size: 24px; font-weight: 200;
        background: rgba(0, 0, 0, 0.18);
      }
      #${MODAL_ID} .tp-slot.filled {
        border-style: solid; cursor: pointer;
        position: relative; padding: 0; overflow: hidden;
      }
      #${MODAL_ID} .tp-slot.filled img {
        width: 100%; height: 100%; object-fit: cover;
      }
      #${MODAL_ID} .tp-slot.filled .tp-slot-name {
        position: absolute; left: 0; right: 0; bottom: 0;
        background: linear-gradient(180deg, transparent, rgba(0,0,0,0.85));
        color: white; font-size: 10px; padding: 14px 6px 4px; text-align: center;
        font-weight: 600;
      }
      #${MODAL_ID} .tp-slot.filled .tp-slot-x {
        position: absolute; top: 4px; right: 4px;
        background: rgba(0,0,0,0.7); color: white; border: none;
        width: 22px; height: 22px; border-radius: 50%; font-size: 12px;
        cursor: pointer; line-height: 1;
      }
      #${MODAL_ID} .tp-grid {
        display: grid; grid-template-columns: repeat(auto-fill, minmax(80px, 1fr));
        gap: 6px;
      }
      #${MODAL_ID} .tp-card {
        position: relative; aspect-ratio: 3/4; border-radius: 6px;
        border: 2px solid var(--border); cursor: pointer; overflow: hidden;
        background: var(--panel-2);
        transition: transform 120ms ease, border-color 120ms ease;
      }
      #${MODAL_ID} .tp-card:hover { transform: translateY(-2px); }
      #${MODAL_ID} .tp-card.selected {
        border-color: var(--accent);
        box-shadow: 0 0 0 2px var(--accent), 0 0 18px rgba(78, 161, 255, 0.4);
      }
      #${MODAL_ID} .tp-card.disabled {
        opacity: 0.35; cursor: not-allowed; pointer-events: none;
      }
      #${MODAL_ID} .tp-card img { width: 100%; height: 100%; object-fit: cover; }
      #${MODAL_ID} .tp-card .tp-power {
        position: absolute; bottom: 0; left: 0; right: 0;
        background: linear-gradient(180deg, transparent, rgba(0,0,0,0.85));
        color: white; padding: 16px 4px 3px; font-size: 9px; text-align: center;
        font-weight: 700;
      }
      #${MODAL_ID} .tp-card .tp-rarity-tag {
        position: absolute; top: 3px; left: 3px;
        font-size: 8px; font-weight: 700;
        padding: 1px 4px; border-radius: 3px;
        background: rgba(0,0,0,0.7);
      }
      #${MODAL_ID} .tp-card .tp-pick-num {
        position: absolute; top: 3px; right: 3px;
        background: var(--accent); color: var(--bg);
        width: 20px; height: 20px; border-radius: 50%;
        font-size: 11px; font-weight: 700;
        display: flex; align-items: center; justify-content: center;
      }
      #${MODAL_ID} .tp-actions {
        display: flex; gap: 8px; flex-wrap: wrap; margin: 14px 0;
      }
      #${MODAL_ID} .tp-actions button {
        padding: 8px 14px; border-radius: 5px; cursor: pointer;
        font-size: 13px; font-weight: 600; border: 1px solid var(--border);
        background: var(--panel-2); color: var(--text);
      }
      #${MODAL_ID} .tp-actions button.primary {
        background: var(--accent); border-color: var(--accent); color: var(--bg);
      }
      #${MODAL_ID} .tp-actions button:disabled {
        opacity: 0.45; cursor: not-allowed;
      }
      #${MODAL_ID} .tp-presets {
        margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--border);
      }
      #${MODAL_ID} .tp-preset-row {
        display: grid; grid-template-columns: 1fr auto auto auto auto;
        gap: 6px; align-items: center; padding: 6px 0;
        border-bottom: 1px solid rgba(255,255,255,0.04);
      }
      #${MODAL_ID} .tp-preset-row .tp-preset-name {
        font-weight: 600; font-size: 13px;
      }
      #${MODAL_ID} .tp-preset-row .tp-preset-team {
        font-size: 11px; color: var(--muted); grid-column: 1; padding-left: 0;
      }
      #${MODAL_ID} .tp-preset-row button {
        background: transparent; border: 1px solid var(--border);
        color: var(--muted); padding: 3px 8px; border-radius: 3px;
        font-size: 11px; cursor: pointer;
      }
      #${MODAL_ID} .tp-preset-row button:hover { color: var(--text); border-color: var(--accent); }
      #${MODAL_ID} .tp-preset-row button.danger { border-color: var(--bad); color: var(--bad); }
      #${MODAL_ID} .tp-filter {
        display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 10px;
      }
      #${MODAL_ID} .tp-filter button {
        background: var(--panel-2); border: 1px solid var(--border);
        color: var(--muted); padding: 4px 10px; border-radius: 14px;
        font-size: 11px; cursor: pointer; font-weight: 600;
      }
      #${MODAL_ID} .tp-filter button.active {
        background: var(--accent); border-color: var(--accent); color: var(--bg);
      }
    `;
    document.head.appendChild(css);
  }

  function ensureModal() {
    let m = document.getElementById(MODAL_ID);
    if (m) return m;
    m = document.createElement('div');
    m.id = MODAL_ID;
    m.innerHTML = `
      <div class="tp-sheet">
        <button class="tp-close" aria-label="Close">×</button>
        <h3 id="tp-title">Pick team</h3>
        <div class="tp-selected" id="tp-selected"></div>
        <div class="tp-actions">
          <button id="tp-confirm" class="primary">Use team</button>
          <button id="tp-clear">Clear</button>
          <button id="tp-last">🕘 Use last team</button>
          <button id="tp-save">💾 Save as preset</button>
        </div>
        <h3 style="margin-top: 14px;">Your roster</h3>
        <div class="tp-filter" id="tp-filter"></div>
        <div class="tp-grid" id="tp-grid">
          <div style="grid-column: 1 / -1; padding: 24px; text-align: center; color: var(--muted);">Loading roster…</div>
        </div>
        <div class="tp-presets" id="tp-presets"></div>
      </div>
    `;
    document.body.appendChild(m);
    m.addEventListener('click', (e) => { if (e.target === m) close(); });
    m.querySelector('.tp-close').addEventListener('click', close);
    return m;
  }

  let state = null;

  function _hdr() {
    return { authorization: 'Bearer ' + (localStorage.getItem('heroproto_jwt') || '') };
  }

  function close() {
    const m = document.getElementById(MODAL_ID);
    if (m) m.classList.remove('open');
    state = null;
  }

  async function open(opts) {
    ensureStyle();
    const m = ensureModal();
    m.classList.add('open');
    state = {
      teamSize: opts.teamSize || 3,
      onConfirm: opts.onConfirm || (() => {}),
      showPresets: opts.showPresets !== false,
      selected: Array.isArray(opts.initial) ? opts.initial.slice(0, opts.teamSize || 3) : [],
      heroes: [],
      filter: 'all',
    };
    document.getElementById('tp-title').textContent = opts.title || 'Pick team';
    renderSelected();

    // Load roster + presets in parallel.
    const [heroes, presets] = await Promise.all([
      fetch('/heroes/mine', { headers: _hdr() }).then(r => r.ok ? r.json() : []),
      state.showPresets ? fetch('/me/team-presets', { headers: _hdr() }).then(r => r.ok ? r.json() : []) : Promise.resolve([]),
    ]);
    state.heroes = (heroes || []).slice().sort((a, b) => b.power - a.power);
    state.presets = presets || [];
    renderFilter();
    renderGrid();
    renderPresets();
    wireActions();
  }

  function renderSelected() {
    const wrap = document.getElementById('tp-selected');
    if (!wrap) return;
    wrap.innerHTML = '';
    for (let i = 0; i < state.teamSize; i++) {
      const id = state.selected[i];
      const slot = document.createElement('div');
      slot.className = 'tp-slot' + (id ? ' filled' : '');
      const hero = id ? (state.heroes || []).find(h => h.id === id) : null;
      if (hero) {
        const code = hero.template.code;
        slot.innerHTML = `
          <img src="/app/static/heroes/busts/${code}.png" alt="${hero.template.name}" onerror="this.src='/app/static/heroes/cards/${code}.png'; this.onerror=null;" />
          <div class="tp-slot-name">${hero.template.name}</div>
          <button class="tp-slot-x" data-remove="${id}" title="Remove">×</button>
        `;
        slot.querySelector('.tp-slot-x').addEventListener('click', (e) => {
          e.stopPropagation();
          state.selected = state.selected.filter(x => x !== id);
          renderSelected();
          renderGrid();
        });
      } else if (id) {
        // Selected id but hero data not yet loaded.
        slot.textContent = '#' + id;
      } else {
        slot.textContent = '+';
      }
      wrap.appendChild(slot);
    }
    document.getElementById('tp-confirm').disabled = state.selected.length === 0;
    document.getElementById('tp-save').disabled = state.selected.length === 0;
  }

  function renderFilter() {
    const f = document.getElementById('tp-filter');
    const counts = {};
    for (const h of state.heroes) counts[h.template.role] = (counts[h.template.role] || 0) + 1;
    const buttons = [
      ['all', `All (${state.heroes.length})`],
      ['ATK', `⚔ ATK (${counts.ATK || 0})`],
      ['DEF', `🛡 DEF (${counts.DEF || 0})`],
      ['SUP', `✨ SUP (${counts.SUP || 0})`],
    ];
    f.innerHTML = '';
    for (const [val, label] of buttons) {
      const b = document.createElement('button');
      if (state.filter === val) b.classList.add('active');
      b.textContent = label;
      b.addEventListener('click', () => { state.filter = val; renderFilter(); renderGrid(); });
      f.appendChild(b);
    }
  }

  function renderGrid() {
    const grid = document.getElementById('tp-grid');
    grid.innerHTML = '';
    const filtered = state.heroes.filter(h => state.filter === 'all' || h.template.role === state.filter);
    if (!filtered.length) {
      grid.innerHTML = '<div style="grid-column: 1 / -1; padding: 24px; text-align: center; color: var(--muted);">No heroes match.</div>';
      return;
    }
    const full = state.selected.length >= state.teamSize;
    for (const h of filtered) {
      const code = h.template.code;
      const isPicked = state.selected.includes(h.id);
      const pickIdx = state.selected.indexOf(h.id) + 1;
      const card = document.createElement('div');
      card.className = 'tp-card';
      if (isPicked) card.classList.add('selected');
      else if (full) card.classList.add('disabled');
      card.innerHTML = `
        <span class="tp-rarity-tag" style="color: var(--r-${String(h.template.rarity).toLowerCase()});">${h.template.rarity}</span>
        <img src="/app/static/heroes/busts/${code}.png" alt="${h.template.name}" onerror="this.src='/app/static/heroes/cards/${code}.png'; this.onerror=null;" />
        ${isPicked ? `<div class="tp-pick-num">${pickIdx}</div>` : ''}
        <div class="tp-power">${h.template.name.split(' ').slice(0, 2).join(' ')}<br/>${h.power}p · L${h.level}</div>
      `;
      card.addEventListener('click', () => {
        if (isPicked) {
          state.selected = state.selected.filter(x => x !== h.id);
        } else {
          if (state.selected.length >= state.teamSize) return;
          state.selected.push(h.id);
        }
        renderSelected();
        renderGrid();
      });
      grid.appendChild(card);
    }
  }

  function renderPresets() {
    const wrap = document.getElementById('tp-presets');
    if (!wrap) return;
    if (!state.showPresets) { wrap.innerHTML = ''; return; }
    const presets = state.presets || [];
    if (!presets.length) {
      wrap.innerHTML = `
        <h3>Saved presets</h3>
        <div style="color: var(--muted); font-size: 12px;">No presets yet. Pick a team and click 💾 Save as preset.</div>
      `;
      return;
    }
    let html = '<h3>Saved presets</h3>';
    for (const p of presets) {
      html += `
        <div class="tp-preset-row" data-preset="${p.id}">
          <div>
            <div class="tp-preset-name">${escapeHtml(p.name)}</div>
            <div class="tp-preset-team">${p.team.length} hero${p.team.length === 1 ? '' : 'es'}</div>
          </div>
          <button data-action="load">Load</button>
          <button data-action="rename">Rename</button>
          <button data-action="overwrite">Overwrite</button>
          <button data-action="delete" class="danger">Delete</button>
        </div>
      `;
    }
    wrap.innerHTML = html;
    wrap.querySelectorAll('.tp-preset-row').forEach(row => {
      const id = Number(row.dataset.preset);
      row.querySelectorAll('button').forEach(b => {
        b.addEventListener('click', () => onPresetAction(id, b.dataset.action));
      });
    });
  }

  async function onPresetAction(id, action) {
    const preset = state.presets.find(p => p.id === id);
    if (!preset) return;
    if (action === 'load') {
      state.selected = preset.team.slice(0, state.teamSize);
      renderSelected();
      renderGrid();
      return;
    }
    if (action === 'delete') {
      if (!confirm(`Delete preset "${preset.name}"?`)) return;
      const r = await fetch('/me/team-presets/' + id, { method: 'DELETE', headers: _hdr() });
      if (!r.ok) {
        if (window.toast) toast.error('Delete failed.');
        return;
      }
      state.presets = state.presets.filter(p => p.id !== id);
      renderPresets();
      if (window.toast) toast.success('Preset deleted.');
      return;
    }
    if (action === 'rename') {
      const next = prompt('New name:', preset.name);
      if (!next || !next.trim() || next.trim() === preset.name) return;
      // Upsert with new name + same team. Server treats POST as
      // upsert-by-name, so we manually delete the old row first.
      await fetch('/me/team-presets/' + id, { method: 'DELETE', headers: _hdr() });
      const r = await fetch('/me/team-presets', {
        method: 'POST',
        headers: { ..._hdr(), 'content-type': 'application/json' },
        body: JSON.stringify({ name: next.trim(), team: preset.team }),
      });
      if (!r.ok) {
        if (window.toast) toast.error('Rename failed.');
        return;
      }
      const newRow = await r.json();
      state.presets = state.presets.filter(p => p.id !== id).concat([newRow]);
      renderPresets();
      if (window.toast) toast.success('Renamed.');
      return;
    }
    if (action === 'overwrite') {
      if (!state.selected.length) {
        if (window.toast) toast.error('Pick a team first.');
        return;
      }
      const r = await fetch('/me/team-presets', {
        method: 'POST',
        headers: { ..._hdr(), 'content-type': 'application/json' },
        body: JSON.stringify({ name: preset.name, team: state.selected }),
      });
      if (!r.ok) {
        if (window.toast) toast.error('Overwrite failed.');
        return;
      }
      const updated = await r.json();
      state.presets = state.presets.map(p => p.id === id ? updated : p);
      renderPresets();
      if (window.toast) toast.success('Preset updated.');
    }
  }

  function wireActions() {
    document.getElementById('tp-confirm').onclick = () => {
      if (!state.selected.length) return;
      const cb = state.onConfirm;
      const team = state.selected.slice();
      close();
      try { cb(team); } catch (e) { console.error('teamPicker.onConfirm threw:', e); }
    };
    document.getElementById('tp-clear').onclick = () => {
      state.selected = [];
      renderSelected();
      renderGrid();
    };
    document.getElementById('tp-last').onclick = async () => {
      try {
        const r = await fetch('/me/last-team', { headers: _hdr() });
        if (!r.ok) {
          if (window.toast) toast.error('No last team yet.');
          return;
        }
        const body = await r.json();
        const team = (body.team || []).slice(0, state.teamSize);
        state.selected = team;
        renderSelected();
        renderGrid();
      } catch { if (window.toast) toast.error('Last-team fetch failed.'); }
    };
    document.getElementById('tp-save').onclick = async () => {
      if (!state.selected.length) return;
      const name = prompt('Preset name (e.g. Campaign, Arena, Raid):', '');
      if (!name || !name.trim()) return;
      const r = await fetch('/me/team-presets', {
        method: 'POST',
        headers: { ..._hdr(), 'content-type': 'application/json' },
        body: JSON.stringify({ name: name.trim(), team: state.selected }),
      });
      const body = await r.json().catch(() => ({}));
      if (!r.ok) {
        const msg = (window.toast && toast.formatErrorBody) ? toast.formatErrorBody(body) : (body.detail || 'Save failed');
        if (window.toast) toast.error(msg);
        return;
      }
      // Merge into local presets list so the row appears immediately.
      state.presets = state.presets.filter(p => p.id !== body.id).concat([body]);
      renderPresets();
      if (window.toast) toast.success(`Saved preset "${body.name}".`);
    };
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
  }

  window.teamPicker = { open, close };
})();
