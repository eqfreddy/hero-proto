// Capacitor native bootstrap. No-op in the browser.
// Capacitor injects window.Capacitor when running inside the wrap, so we
// avoid importing @capacitor/* npm packages here (the frontend bundle is
// shared between web + native and we don't want to pull in deadweight).

type Cap = {
  isNativePlatform?: () => boolean
  getPlatform?: () => string
  Plugins?: Record<string, any>
}

function cap(): Cap | null {
  return (typeof window !== 'undefined' && (window as any).Capacitor) || null
}

export function isNative(): boolean {
  const c = cap()
  return !!c?.isNativePlatform?.()
}

export function platform(): string {
  return cap()?.getPlatform?.() ?? 'web'
}

export function initNativeChrome(): void {
  const c = cap()
  if (!c?.isNativePlatform?.()) return

  // Status bar — dark style (light icons over our void bg), don't overlay
  // the web view so the safe-area inset is honoured by the topnav padding.
  const sb = c.Plugins?.StatusBar
  if (sb) {
    sb.setStyle?.({ style: 'DARK' }).catch(() => {})
    sb.setBackgroundColor?.({ color: '#04060c' }).catch(() => {})
    sb.setOverlaysWebView?.({ overlay: false }).catch(() => {})
  }

  // Native back button — smart:
  //   - at lobby root → exit the app (matches native Android UX)
  //   - elsewhere → React Router history back
  // Capacitor's own `canGoBack` reflects raw webview history which sticks
  // around after login redirects, so reading `location.pathname` is more
  // reliable for the "am I at root?" check.
  const app = c.Plugins?.App
  if (app?.addListener) {
    app.addListener('backButton', () => {
      const path = window.location.pathname
      const atRoot = path === '/' || path === '/app' || path === '/app/' || path === '/app/me'
      if (atRoot) {
        app.exitApp?.().catch(() => {})
      } else if (window.history.length > 1) {
        window.history.back()
      } else {
        app.exitApp?.().catch(() => {})
      }
    })
  }
}
