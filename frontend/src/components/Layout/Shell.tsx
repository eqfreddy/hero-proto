import { Outlet } from 'react-router-dom'
import { NavBar } from './NavBar'
import { CurrencyBar } from './CurrencyBar'
import { ToastContainer } from '../Toast'

export function Shell() {
  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <NavBar />
      <CurrencyBar />
      <main style={{ padding: 18, maxWidth: 1100, margin: '0 auto', width: '100%', flex: 1 }}>
        <Outlet />
      </main>
      <ToastContainer />
    </div>
  )
}
