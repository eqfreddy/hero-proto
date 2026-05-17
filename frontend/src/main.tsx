import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { initNativeChrome, isNative } from './native'
import './styles/global.css'

initNativeChrome()

// Service workers don't run on file:// (Capacitor native shell). Unregister
// any that slipped in from a previous PWA install and skip the new one.
if (isNative() && 'serviceWorker' in navigator) {
  navigator.serviceWorker.getRegistrations().then((rs) => {
    rs.forEach((r) => r.unregister().catch(() => {}))
  }).catch(() => {})
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
)
