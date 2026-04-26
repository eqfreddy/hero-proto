// Minimal toast helper. Replaces the existing alert() calls throughout
// the partials and static pages. Loads itself into a fixed container at
// the top-center (bug #8: bottom-stacked toasts were missed by users
// clicking near the top of the page), stacks newest-on-top,
// auto-dismisses (errors linger longer than success/info),
// tap-to-dismiss-early.
//
// Public API:
//   window.toast.show(msg, kind = 'info', opts = {})
//   window.toast.error(msg)         // shortcut for show(msg, 'error')
//   window.toast.success(msg)       // shortcut for show(msg, 'success')
//   window.toast.info(msg)          // shortcut for show(msg, 'info')
//   window.toast.fromError(err, fallback)  // formats Pydantic 422 +
//                                            HTTPException detail nicely
//                                            so error toasts don't render
//                                            "[object Object]" (bug #3).
//
// kind ∈ {'info' | 'success' | 'error'}.
// opts: { ttlMs }  — override auto-dismiss in ms.

(function () {
  const ID = 'toast-stack';
  const STYLE_ID = 'toast-style';

  // Inject CSS once. Self-scoped via the container id so it can't fight
  // existing page styles. Designed to read on the dark theme used across
  // /app/* and on the standalone static pages.
  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const css = document.createElement('style');
    css.id = STYLE_ID;
    css.textContent = `
      #${ID} {
        position: fixed;
        left: 50%;
        top: 64px;
        transform: translateX(-50%);
        display: flex;
        flex-direction: column;
        gap: 8px;
        z-index: 10000;
        pointer-events: none;
        max-width: min(92vw, 480px);
      }
      #${ID} .toast {
        pointer-events: auto;
        background: #14181e;
        color: #ddd;
        border: 1px solid #2d3847;
        border-left-width: 4px;
        padding: 10px 14px;
        border-radius: 4px;
        font: 500 13px/1.4 system-ui, -apple-system, sans-serif;
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.45);
        opacity: 0;
        transform: translateY(8px);
        transition: opacity 180ms ease, transform 180ms ease;
        cursor: pointer;
        max-width: 100%;
        word-break: break-word;
      }
      #${ID} .toast.show     { opacity: 1; transform: translateY(0); }
      #${ID} .toast.error    { border-left-color: #ff6b4a; color: #ffb59c; }
      #${ID} .toast.success  { border-left-color: #2ad06a; color: #a8e8c0; }
      #${ID} .toast.info     { border-left-color: #4ea1ff; color: #c8dcff; }
    `;
    document.head.appendChild(css);
  }

  function ensureStack() {
    let stack = document.getElementById(ID);
    if (stack) return stack;
    stack = document.createElement('div');
    stack.id = ID;
    document.body.appendChild(stack);
    return stack;
  }

  // Bug #7 closeout — when a 4xx says "not enough X" (shards/gems/coins/
  // energy/access cards), render the toast with a "Go to Shop" CTA so
  // the player can jump straight to recharging without hunting for the
  // tab. Returns null if the message doesn't look like a currency 409.
  const _LOW_BALANCE_PATTERNS = [
    { re: /\bnot enough (gems?)\b/i, label: '💎 Buy gems' },
    { re: /\bnot enough (shards?|✦)\b/i, label: '✦ Buy shards' },
    { re: /\bnot enough (coins?|🪙)\b/i, label: '🪙 Earn coins' },
    { re: /\bnot enough (access[\s_]cards?|🎫)\b/i, label: '🎫 Buy access cards' },
    { re: /\bnot enough (energy|⚡)\b/i, label: '⚡ Refill energy' },
  ];
  function _detectLowBalance(msg) {
    const text = String(msg || '');
    for (const { re, label } of _LOW_BALANCE_PATTERNS) {
      if (re.test(text)) return { label, isEnergy: /energy/i.test(text) };
    }
    return null;
  }

  function show(msg, kind, opts) {
    if (!msg) return;
    ensureStyle();
    const stack = ensureStack();
    const k = ['error', 'success', 'info'].includes(kind) ? kind : 'info';
    const node = document.createElement('div');
    node.className = `toast ${k}`;
    const text = String(msg);

    // Bug #7 — if this is a currency-related error, attach a Shop CTA.
    const lowBal = (k === 'error' && (!opts || opts.cta !== false)) ? _detectLowBalance(text) : null;
    if (lowBal) {
      node.textContent = '';
      const msgSpan = document.createElement('div');
      msgSpan.textContent = text;
      const cta = document.createElement('button');
      cta.textContent = lowBal.label;
      cta.style.cssText = 'margin-top: 8px; background: rgba(255,255,255,0.95); color: #2a6dc7; border: none; padding: 4px 10px; border-radius: 4px; font: 600 11px/1 system-ui; cursor: pointer; display: block;';
      cta.addEventListener('click', (e) => {
        e.stopPropagation();
        // Energy refill lives on /me; everything else is the Shop tab.
        const sel = lowBal.isEnergy ? '[data-tab="me"]' : '[data-tab="shop"]';
        const tab = document.querySelector(sel);
        if (tab) tab.click();
        node.click();  // dismiss the toast
      });
      node.appendChild(msgSpan);
      node.appendChild(cta);
    } else {
      node.textContent = text;
    }

    // Errors linger 5s — failures need a second look. info/success default 3.5s.
    // Low-balance toasts get an extra second so the CTA is reachable.
    const ttl = (opts && Number.isFinite(opts.ttlMs))
      ? opts.ttlMs
      : (k === 'error' ? (lowBal ? 7000 : 5000) : 3500);
    stack.appendChild(node);
    requestAnimationFrame(() => node.classList.add('show'));
    let dismissed = false;
    const dismiss = () => {
      if (dismissed) return;
      dismissed = true;
      node.classList.remove('show');
      setTimeout(() => { if (node.parentNode) node.parentNode.removeChild(node); }, 220);
    };
    node.addEventListener('click', dismiss);
    setTimeout(dismiss, ttl);
  }

  // Pretty-print FastAPI / Pydantic error responses so a 422 doesn't
  // render as `[object Object]` (bug #3). Accepts either:
  //   - a plain Error instance
  //   - a fetch Response body (already-parsed dict)
  //   - a {detail: string} or {detail: [{loc, msg, type}, ...]} payload
  function formatErrorBody(body) {
    if (!body) return '';
    if (typeof body === 'string') return body;
    if (body.detail !== undefined) {
      const d = body.detail;
      if (typeof d === 'string') return d;
      if (Array.isArray(d)) {
        // Pydantic validation list: [{loc: [..], msg: '...', type: '...'}]
        return d.map(item => {
          if (item && typeof item === 'object') {
            const loc = Array.isArray(item.loc) ? item.loc.filter(p => p !== 'body').join('.') : '';
            const msg = item.msg || item.message || '';
            return loc ? `${loc}: ${msg}` : msg;
          }
          return String(item);
        }).filter(Boolean).join('; ');
      }
      try { return JSON.stringify(d); } catch (e) { return String(d); }
    }
    try { return JSON.stringify(body); } catch (e) { return String(body); }
  }

  function fromError(err, fallback) {
    if (!err) return show(fallback || 'Unknown error', 'error');
    if (err instanceof Error && err.message && err.message !== '[object Object]') {
      return show(err.message, 'error');
    }
    const formatted = formatErrorBody(err);
    return show(formatted || fallback || 'Request failed', 'error');
  }

  window.toast = {
    show,
    error:   (msg, opts) => show(msg, 'error', opts),
    success: (msg, opts) => show(msg, 'success', opts),
    info:    (msg, opts) => show(msg, 'info', opts),
    fromError,
    formatErrorBody,
  };
})();
