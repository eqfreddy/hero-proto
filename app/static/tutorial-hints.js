// Tutorial onboarding tooltips. Addresses the playtest gripe:
// "needs popup hints during tutorial showing where to click."
//
// Reads window.heroNextStep (set inline by the /me partial when a
// next_step is active) and pulses a small tooltip with an arrow that
// points at the relevant top-nav tab. Per-step dismissal is sticky
// (stored under heroproto_hint_dismissed_<key>) so we don't nag
// returning players who already know the layout.
//
// Public API:
//   window.tutorialHint.show(opts)
//     opts: { key, anchorSel, title, body, side?: 'bottom'|'top'|'right'|'left' }
//   window.tutorialHint.dismiss(key)
//   window.tutorialHint.refreshFromState()
//     — reads window.heroNextStep and shows the matching hint.

(function () {
  const ID = 'hp-tut-hint';
  const STYLE_ID = 'hp-tut-hint-style';
  const DISMISS_PREFIX = 'heroproto_hint_dismissed_';

  // step key → which top-nav tab to point at + tooltip copy.
  const STEP_MAP = {
    tutorial: {
      anchorSel: '[data-tab="stages"]',
      side: 'bottom',
      title: '⚔️ Start the tutorial here',
      body: 'Click <strong>Stages</strong> to find the tutorial battle. We pre-pick the team — just hit Battle.',
    },
    summon: {
      anchorSel: '[data-tab="summon"]',
      side: 'bottom',
      title: '🎰 Pull your first hero',
      body: 'Click <strong>Summon</strong> to open the gacha. You have a free summon token waiting.',
    },
    first_battle: {
      anchorSel: '[data-tab="stages"]',
      side: 'bottom',
      title: '⚔️ Run your first campaign stage',
      body: 'Tutorial\'s done. Click <strong>Stages</strong> and pick anything — your starter team can handle it.',
    },
  };

  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const css = document.createElement('style');
    css.id = STYLE_ID;
    css.textContent = `
      #${ID} {
        position: fixed; z-index: 9100;
        max-width: 280px;
        background: linear-gradient(135deg, #4ea1ff, #2a6dc7);
        color: #fff;
        border-radius: 8px;
        padding: 12px 14px;
        box-shadow: 0 8px 28px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.15);
        font: 13px/1.5 system-ui, -apple-system, sans-serif;
        opacity: 0; transform: translateY(-6px);
        transition: opacity 220ms ease, transform 220ms ease;
        pointer-events: auto;
      }
      #${ID}.show { opacity: 1; transform: translateY(0); }
      #${ID} .hp-tut-title { font-weight: 700; font-size: 13px; margin-bottom: 4px; }
      #${ID} .hp-tut-body { font-size: 12px; opacity: 0.95; }
      #${ID} .hp-tut-actions { display: flex; gap: 6px; margin-top: 10px; align-items: center; }
      #${ID} button {
        background: rgba(255,255,255,0.95); color: #2a6dc7;
        border: none; padding: 4px 12px; border-radius: 4px;
        font: 600 12px/1 system-ui; cursor: pointer;
      }
      #${ID} button.ghost {
        background: transparent; color: rgba(255,255,255,0.85);
        font-weight: 500;
      }
      #${ID} button:hover { filter: brightness(1.05); }
      #${ID} .hp-tut-arrow {
        position: absolute;
        width: 0; height: 0;
        border: 8px solid transparent;
      }
      #${ID}.side-bottom .hp-tut-arrow { top: -16px; left: 24px; border-bottom-color: #4ea1ff; border-top-width: 0; }
      #${ID}.side-top    .hp-tut-arrow { bottom: -16px; left: 24px; border-top-color: #2a6dc7; border-bottom-width: 0; }
      #${ID}.side-left   .hp-tut-arrow { right: -16px; top: 16px; border-left-color: #2a6dc7; border-right-width: 0; }
      #${ID}.side-right  .hp-tut-arrow { left: -16px; top: 16px; border-right-color: #4ea1ff; border-left-width: 0; }
      /* Pulsing ring on the anchor — drawn via JS-positioned div so we
         don't have to touch the anchor's own classes. */
      .hp-tut-pulse {
        position: fixed; z-index: 9090;
        border: 2px solid #4ea1ff; border-radius: 6px;
        pointer-events: none;
        animation: hp-tut-pulse 1.6s ease-in-out infinite;
      }
      @keyframes hp-tut-pulse {
        0%, 100% { box-shadow: 0 0 0 0 rgba(78, 161, 255, 0.55); transform: scale(1); }
        50%      { box-shadow: 0 0 0 8px rgba(78, 161, 255, 0); transform: scale(1.04); }
      }
    `;
    document.head.appendChild(css);
  }

  let _currentKey = null;
  let _pulseEl = null;

  function dismiss(key) {
    try { localStorage.setItem(DISMISS_PREFIX + key, '1'); } catch (_) {}
    const el = document.getElementById(ID);
    if (el) { el.classList.remove('show'); setTimeout(() => el.remove(), 220); }
    if (_pulseEl) { _pulseEl.remove(); _pulseEl = null; }
    _currentKey = null;
  }

  function isDismissed(key) {
    try { return localStorage.getItem(DISMISS_PREFIX + key) === '1'; } catch (_) { return false; }
  }

  function position(el, anchor, side) {
    const r = anchor.getBoundingClientRect();
    let x, y;
    if (side === 'bottom') { x = r.left; y = r.bottom + 12; }
    else if (side === 'top') { x = r.left; y = r.top - el.offsetHeight - 12; }
    else if (side === 'right') { x = r.right + 12; y = r.top; }
    else if (side === 'left') { x = r.left - el.offsetWidth - 12; y = r.top; }
    // Clamp to viewport.
    x = Math.min(Math.max(8, x), window.innerWidth - el.offsetWidth - 8);
    y = Math.min(Math.max(8, y), window.innerHeight - el.offsetHeight - 8);
    el.style.left = x + 'px';
    el.style.top = y + 'px';

    // Pulse ring.
    if (!_pulseEl) {
      _pulseEl = document.createElement('div');
      _pulseEl.className = 'hp-tut-pulse';
      document.body.appendChild(_pulseEl);
    }
    _pulseEl.style.left = (r.left - 4) + 'px';
    _pulseEl.style.top = (r.top - 4) + 'px';
    _pulseEl.style.width = (r.width + 8) + 'px';
    _pulseEl.style.height = (r.height + 8) + 'px';
  }

  function show(opts) {
    if (!opts || !opts.key) return;
    if (isDismissed(opts.key)) return;
    if (_currentKey === opts.key && document.getElementById(ID)) return;

    ensureStyle();
    let el = document.getElementById(ID);
    if (el) el.remove();
    if (_pulseEl) { _pulseEl.remove(); _pulseEl = null; }

    const anchor = document.querySelector(opts.anchorSel);
    if (!anchor) return; // anchor not on screen yet — try again next refresh.

    el = document.createElement('div');
    el.id = ID;
    el.className = 'side-' + (opts.side || 'bottom');
    el.innerHTML = `
      <div class="hp-tut-arrow"></div>
      <div class="hp-tut-title">${opts.title}</div>
      <div class="hp-tut-body">${opts.body}</div>
      <div class="hp-tut-actions">
        <button type="button" data-action="go">Take me there</button>
        <button type="button" class="ghost" data-action="dismiss">Got it, hide</button>
      </div>
    `;
    document.body.appendChild(el);
    position(el, anchor, opts.side || 'bottom');
    requestAnimationFrame(() => el.classList.add('show'));

    el.querySelector('[data-action="go"]').addEventListener('click', () => {
      try { anchor.click(); } catch (_) {}
      dismiss(opts.key);
    });
    el.querySelector('[data-action="dismiss"]').addEventListener('click', () => dismiss(opts.key));
    _currentKey = opts.key;

    // Reposition on resize so the arrow stays anchored.
    const reposition = () => {
      if (document.getElementById(ID) && document.querySelector(opts.anchorSel)) {
        position(document.getElementById(ID), document.querySelector(opts.anchorSel), opts.side || 'bottom');
      }
    };
    window.addEventListener('resize', reposition);
  }

  function refreshFromState() {
    const ns = window.heroNextStep;
    if (!ns || !ns.key) {
      // No next-step → clear any active hint.
      if (_currentKey) {
        const el = document.getElementById(ID);
        if (el) { el.classList.remove('show'); setTimeout(() => el.remove(), 220); }
        if (_pulseEl) { _pulseEl.remove(); _pulseEl = null; }
        _currentKey = null;
      }
      return;
    }
    const cfg = STEP_MAP[ns.key];
    if (!cfg) return;
    show({ key: ns.key, ...cfg });
  }

  // Hook HTMX so we re-evaluate every time a partial swaps. /me sets
  // window.heroNextStep inline; navigating to other tabs preserves the
  // hint (it points at a top-nav tab, not at a tab-internal element).
  if (typeof document !== 'undefined') {
    document.body && document.body.addEventListener('htmx:afterRequest', () => {
      // Slight delay so any inline script in the swapped partial has
      // time to set window.heroNextStep before we read.
      setTimeout(refreshFromState, 30);
    });
  }

  window.tutorialHint = { show, dismiss, refreshFromState, isDismissed };
})();
