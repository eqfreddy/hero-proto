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

  // Native back button → browser history back, exit only at root.
  const app = c.Plugins?.App
  if (app?.addListener) {
    app.addListener('backButton', ({ canGoBack }: { canGoBack: boolean }) => {
      if (canGoBack && window.history.length > 1) {
        window.history.back()
      } else {
        app.exitApp?.().catch(() => {})
      }
    })
  }
}
