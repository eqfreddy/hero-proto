import { Component, type ReactNode } from 'react'
import { createBrowserRouter, RouterProvider, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Shell } from './components/Layout/Shell'
import { Login } from './routes/Login'
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
import { AchievementsRoute } from './routes/Achievements'
import { EventRoute } from './routes/Event'
import { CraftingRoute } from './routes/Crafting'
import { AccountRoute } from './routes/Account'
import BattleSetupRoute from './routes/battle/BattleSetupRoute'
import BattleReplayRoute from './routes/battle/BattleReplayRoute'
import BattlePlayRoute from './routes/battle/BattlePlayRoute'

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
      { path: 'crafting', element: <CraftingRoute /> },
      { path: 'stages', element: <StagesRoute /> },
      { path: 'daily', element: <DailyRoute /> },
      { path: 'story', element: <StoryRoute /> },
      { path: 'friends', element: <FriendsLayout />, children: [
        { index: true, element: <FriendsList /> },
        { path: 'messages', element: <MessagesRoute /> },
      ]},
      { path: 'achievements', element: <AchievementsRoute /> },
      { path: 'arena', element: <ArenaRoute /> },
      { path: 'guild', element: <GuildRoute />, children: [
        { index: true, element: <GuildOverview /> },
        { path: 'members', element: <GuildMembers /> },
        { path: 'chat', element: <GuildChat /> },
        { path: 'raids', element: <GuildRaids /> },
      ]},
      { path: 'raids', element: <RaidsTabRoute /> },
      { path: 'shop', element: <ShopRoute /> },
      { path: 'account', element: <AccountRoute /> },
      { path: 'event', element: <EventRoute /> },
    ],
  },
  {
    path: '/battle',
    children: [
      { path: 'setup', element: <BattleSetupRoute /> },
      { path: ':id/watch', element: <BattleReplayRoute /> },
      { path: ':id/play', element: <BattlePlayRoute /> },
      { path: ':id/replay', element: <BattleReplayRoute /> },
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
