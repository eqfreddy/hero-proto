import { Component, type ReactNode } from 'react'
import { createBrowserRouter, RouterProvider, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Shell } from './components/Layout/Shell'
import { Login } from './routes/Login'
import { Stub } from './routes/Stub'
import { MeRoute } from './routes/Me'
import { RosterRoute } from './routes/Roster'
import { HeroDetailRoute } from './routes/Roster/HeroDetail'
import { StagesRoute } from './routes/Stages'
import { SummonRoute } from './routes/Summon'
import { ShopRoute } from './routes/Shop'
import { GuildRoute, GuildOverview } from './routes/Guild'
import { GuildMembers } from './routes/Guild/Members'
import { GuildChat } from './routes/Guild/Chat'
import { GuildRaids } from './routes/Guild/Raids'
import { FriendsLayout, FriendsList } from './routes/Friends'
import { MessagesRoute } from './routes/Friends/Messages'
import { ArenaRoute } from './routes/Arena'
import { RaidsTabRoute } from './routes/RaidsTab'
import { DailyRoute } from './routes/Daily'
import { StoryRoute } from './routes/Story'

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
      { path: 'me', element: <MeRoute /> },
      { path: 'roster', children: [
        { index: true, element: <RosterRoute /> },
        { path: ':heroId', element: <HeroDetailRoute /> },
      ]},
      { path: 'summon', element: <SummonRoute /> },
      { path: 'crafting', element: <Stub name="Crafting" /> },
      { path: 'stages', element: <StagesRoute /> },
      { path: 'daily', element: <DailyRoute /> },
      { path: 'story', element: <StoryRoute /> },
      { path: 'friends', element: <FriendsLayout />, children: [
        { index: true, element: <FriendsList /> },
        { path: 'messages', element: <MessagesRoute /> },
      ]},
      { path: 'achievements', element: <Stub name="Achievements" /> },
      { path: 'arena', element: <ArenaRoute /> },
      { path: 'guild', element: <GuildRoute />, children: [
        { index: true, element: <GuildOverview /> },
        { path: 'members', element: <GuildMembers /> },
        { path: 'chat', element: <GuildChat /> },
        { path: 'raids', element: <GuildRaids /> },
      ]},
      { path: 'raids', element: <RaidsTabRoute /> },
      { path: 'shop', element: <ShopRoute /> },
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
