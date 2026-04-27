import { Component, type ReactNode } from 'react'
import { createBrowserRouter, RouterProvider, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Shell } from './components/Layout/Shell'
import { Login } from './routes/Login'
import { Stub } from './routes/Stub'

const qc = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30_000 } },
})

const router = createBrowserRouter([
  { path: '/', element: <Navigate to="/app/me" replace /> },
  {
    path: '/app',
    element: <Shell />,
    children: [
      { index: true, element: <Navigate to="/app/me" replace /> },
      { path: 'login', element: <Login /> },
      { path: 'me', element: <Stub name="Me" /> },
      { path: 'roster', children: [
        { index: true, element: <Stub name="Roster" /> },
        { path: ':heroId', element: <Stub name="Hero Detail" /> },
      ]},
      { path: 'summon', element: <Stub name="Summon" /> },
      { path: 'crafting', element: <Stub name="Crafting" /> },
      { path: 'stages', element: <Stub name="Stages" /> },
      { path: 'daily', element: <Stub name="Daily" /> },
      { path: 'story', element: <Stub name="Story" /> },
      { path: 'friends', children: [
        { index: true, element: <Stub name="Friends" /> },
        { path: 'messages', element: <Stub name="Messages" /> },
      ]},
      { path: 'achievements', element: <Stub name="Achievements" /> },
      { path: 'arena', element: <Stub name="Arena" /> },
      { path: 'guild', children: [
        { index: true, element: <Stub name="Guild" /> },
        { path: 'members', element: <Stub name="Guild Members" /> },
        { path: 'chat', element: <Stub name="Guild Chat" /> },
        { path: 'raids', element: <Stub name="Guild Raids" /> },
      ]},
      { path: 'raids', element: <Stub name="Raids" /> },
      { path: 'shop', element: <Stub name="Shop" /> },
      { path: 'account', element: <Stub name="Account" /> },
      { path: 'event', element: <Stub name="Event" /> },
    ],
  },
  {
    path: '/battle',
    children: [
      { path: 'setup', element: <Stub name="Battle Setup" /> },
      { path: ':id/watch', element: <Stub name="Battle Watch" /> },
      { path: ':id/play', element: <Stub name="Battle Play" /> },
      { path: ':id/replay', element: <Stub name="Battle Replay" /> },
    ],
  },
])

class RootErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean }> {
  constructor(props: { children: ReactNode }) {
    super(props)
    this.state = { hasError: false }
  }
  static getDerivedStateFromError() { return { hasError: true } }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 40, textAlign: 'center', color: 'var(--muted)' }}>
          Something went wrong. Please refresh the page.
        </div>
      )
    }
    return this.props.children
  }
}

export default function App() {
  return (
    <RootErrorBoundary>
      <QueryClientProvider client={qc}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </RootErrorBoundary>
  )
}
