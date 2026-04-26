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

  function show(msg, kind, opts) {
    if (!msg) return;
    ensureStyle();
    const stack = ensureStack();
    const k = ['error', 'success', 'info'].includes(kind) ? kind : 'info';
    const node = document.createElement('div');
    node.className = `toast ${k}`;
    node.textContent = String(msg);
    // Errors linger 5s — failures need a second look. info/success default 3.5s.
    const ttl = (opts && Number.isFinite(opts.ttlMs)) ? opts.ttlMs : (k === 'error' ? 5000 : 3500);
    stack.appendChild(node);
    // Animate in on next frame so the transition fires.
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
