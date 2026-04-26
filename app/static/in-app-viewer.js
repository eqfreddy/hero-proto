// In-app viewer — full-screen overlay with an iframe + title bar + close.
// Replaces target="_blank" on internal pages so the dashboard behaves
// like a single application (and works inside Capacitor / a PWA, where
// new windows don't make sense).
//
// Public API:
//   window.inApp.open(url, opts)
//     opts:
//       title   — string shown in the overlay title bar
//       width   — "full" (default) | "wide" | "narrow"
//       onClose — function called when the overlay closes
//   window.inApp.close()
//
// Behaviors:
//   - Esc closes
//   - Clicking the dark backdrop closes
//   - Browser back-button closes (history-state push)
//   - Loaded page can call window.parent.inApp.close() to dismiss itself
//   - Body scroll-lock while open
//
// External links (anything off-domain) should keep target="_blank".

(function () {
  const OVERLAY_ID = 'in-app-viewer';
  const STYLE_ID = 'in-app-viewer-style';

  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const css = document.createElement('style');
    css.id = STYLE_ID;
    css.textContent = `
      #${OVERLAY_ID} {
        position: fixed; inset: 0; z-index: 9500;
        display: none; flex-direction: column;
        background: rgba(0, 0, 0, 0.85);
        animation: iav-fade 160ms ease;
      }
      #${OVERLAY_ID}.open { display: flex; }
      @keyframes iav-fade { from { opacity: 0; } to { opacity: 1; } }
      #${OVERLAY_ID} .iav-bar {
        display: flex; align-items: center; gap: 12px;
        padding: 10px 14px;
        background: var(--panel, #14181e);
        border-bottom: 1px solid var(--border, #2d3847);
        color: var(--text, #ddd);
        font-size: 13px;
      }
      #${OVERLAY_ID} .iav-title {
        flex: 1; font-weight: 600;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
      }
      #${OVERLAY_ID} .iav-tools {
        display: flex; gap: 6px; align-items: center;
      }
      #${OVERLAY_ID} .iav-tools button {
        background: rgba(255,255,255,0.06);
        border: 1px solid var(--border, #2d3847);
        color: var(--muted, #8a96a8);
        padding: 4px 9px; border-radius: 4px;
        font-size: 12px; cursor: pointer;
      }
      #${OVERLAY_ID} .iav-tools button:hover {
        color: var(--text, #ddd); border-color: var(--accent, #4ea1ff);
      }
      #${OVERLAY_ID} .iav-close {
        width: 32px; height: 32px; border-radius: 50%;
        background: rgba(255,255,255,0.08);
        border: 1px solid var(--border, #2d3847);
        color: var(--text, #ddd); font-size: 18px;
        cursor: pointer;
        display: flex; align-items: center; justify-content: center;
      }
      #${OVERLAY_ID} .iav-close:hover { background: var(--bad, #ff6b4a); border-color: var(--bad, #ff6b4a); color: #fff; }
      #${OVERLAY_ID} .iav-frame-wrap {
        flex: 1; min-height: 0;
        display: flex; justify-content: center; align-items: stretch;
        background: #000;
      }
      #${OVERLAY_ID} iframe {
        flex: 1;
        width: 100%; height: 100%;
        border: none; background: var(--bg, #0b0d10);
      }
      #${OVERLAY_ID}.width-wide .iav-frame-wrap { padding: 0 6vw; }
      #${OVERLAY_ID}.width-narrow .iav-frame-wrap { padding: 0 14vw; }
      @media (max-width: 720px) {
        #${OVERLAY_ID}.width-wide .iav-frame-wrap,
        #${OVERLAY_ID}.width-narrow .iav-frame-wrap { padding: 0; }
      }
    `;
    document.head.appendChild(css);
  }

  function ensureOverlay() {
    let el = document.getElementById(OVERLAY_ID);
    if (el) return el;
    el = document.createElement('div');
    el.id = OVERLAY_ID;
    el.innerHTML = `
      <div class="iav-bar">
        <div class="iav-title" id="iav-title">Loading…</div>
        <div class="iav-tools">
          <button type="button" data-action="popout" title="Open in a new tab">↗</button>
          <button type="button" data-action="reload" title="Reload">↻</button>
          <button type="button" class="iav-close" data-action="close" aria-label="Close">×</button>
        </div>
      </div>
      <div class="iav-frame-wrap">
        <iframe id="iav-frame" allow="autoplay; fullscreen" referrerpolicy="same-origin"></iframe>
      </div>
    `;
    el.addEventListener('click', (e) => {
      // Click on the dark gap around the iframe-wrap (if any) closes;
      // clicks inside the bar / iframe do not.
      if (e.target === el) close();
    });
    el.querySelector('[data-action="close"]').addEventListener('click', close);
    el.querySelector('[data-action="reload"]').addEventListener('click', () => {
      const iframe = document.getElementById('iav-frame');
      if (iframe && iframe.src) iframe.src = iframe.src;
    });
    el.querySelector('[data-action="popout"]').addEventListener('click', () => {
      const iframe = document.getElementById('iav-frame');
      if (iframe && iframe.src) window.open(iframe.src, '_blank');
    });
    document.body.appendChild(el);
    return el;
  }

  let _onCloseCb = null;
  let _historyPushed = false;

  function open(url, opts) {
    if (!url) return;
    opts = opts || {};
    ensureStyle();
    const el = ensureOverlay();
    el.classList.remove('width-wide', 'width-narrow');
    if (opts.width === 'wide') el.classList.add('width-wide');
    else if (opts.width === 'narrow') el.classList.add('width-narrow');
    document.getElementById('iav-title').textContent = opts.title || url;
    document.getElementById('iav-frame').src = url;
    el.classList.add('open');
    document.body.style.overflow = 'hidden';
    _onCloseCb = typeof opts.onClose === 'function' ? opts.onClose : null;
    // History-back support — pushing a state lets the platform back gesture
    // close the overlay before navigating away from the dashboard.
    try {
      history.pushState({ inAppViewer: true }, '');
      _historyPushed = true;
    } catch (e) { /* private mode etc. */ }
  }

  function close() {
    const el = document.getElementById(OVERLAY_ID);
    if (!el || !el.classList.contains('open')) return;
    el.classList.remove('open');
    const iframe = document.getElementById('iav-frame');
    // about:blank breaks any inflight requests in the embedded page so
    // they don't keep running after dismiss. Then strip the src so the
    // next open starts fresh.
    if (iframe) {
      try { iframe.src = 'about:blank'; } catch (e) {}
    }
    document.body.style.overflow = '';
    if (_historyPushed) {
      // Pop the state we pushed on open (only if we're still on it).
      _historyPushed = false;
      try {
        if (history.state && history.state.inAppViewer) history.back();
      } catch (e) {}
    }
    if (_onCloseCb) {
      try { _onCloseCb(); } catch (e) { console.error(e); }
      _onCloseCb = null;
    }
  }

  // Esc to close.
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      const el = document.getElementById(OVERLAY_ID);
      if (el && el.classList.contains('open')) close();
    }
  });
  // History back closes the overlay before the rest of the app reacts.
  window.addEventListener('popstate', (e) => {
    const el = document.getElementById(OVERLAY_ID);
    if (el && el.classList.contains('open')) {
      _historyPushed = false; // already popped by the browser
      el.classList.remove('open');
      const iframe = document.getElementById('iav-frame');
      if (iframe) { try { iframe.src = 'about:blank'; } catch (_) {} }
      document.body.style.overflow = '';
      if (_onCloseCb) {
        try { _onCloseCb(); } catch (_) {}
        _onCloseCb = null;
      }
    }
  });

  window.inApp = { open, close };
})();
