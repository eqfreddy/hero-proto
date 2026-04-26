// Minimal toast helper. Replaces the existing alert() calls throughout
// the partials and static pages. Loads itself into a fixed container at
// the bottom-center, stacks newest-on-top, auto-dismisses (errors linger
// longer than success/info), tap-to-dismiss-early.
//
// Public API:
//   window.toast.show(msg, kind = 'info', opts = {})
//   window.toast.error(msg)         // shortcut for show(msg, 'error')
//   window.toast.success(msg)       // shortcut for show(msg, 'success')
//   window.toast.info(msg)          // shortcut for show(msg, 'info')
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
        bottom: 28px;
        transform: translateX(-50%);
        display: flex;
        flex-direction: column-reverse;
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

  window.toast = {
    show,
    error:   (msg, opts) => show(msg, 'error', opts),
    success: (msg, opts) => show(msg, 'success', opts),
    info:    (msg, opts) => show(msg, 'info', opts),
  };
})();
