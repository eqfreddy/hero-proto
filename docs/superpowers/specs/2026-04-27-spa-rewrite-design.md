# SPA Rewrite Design
**Date:** 2026-04-27
**Status:** Approved

## Summary

Replace the HTMX + Jinja2 shell with a React SPA. The existing FastAPI JSON API is untouched — this is a rendering-layer swap only. Unblocks Sprint C (deploy pipeline) and Sprint H (PWA field test).

---

## Stack

| Concern | Choice |
|---|---|
| Framework | React 18 + TypeScript |
| Build | Vite |
| Routing | React Router v6 (nested routes) |
| Server state | TanStack Query (React Query v5) |
| Client state | Zustand |
| Canvas integration | `useRef` + `useEffect` mount/destroy |
| PWA | vite-plugin-pwa (replaces hand-rolled sw.js) |
| Testing | Vitest + React Testing Library + Playwright smoke |

---

## Architecture

### Directory layout

```
hero-proto/
  frontend/                   ← NEW: React SPA
    src/
      routes/                 ← one file per tab/route
      components/             ← shared UI (CurrencyBar, HeroCard, BattleHUD…)
      hooks/                  ← useMe(), useHeroes(), useStages()…
      store/                  ← Zustand: auth.ts, sound.ts, ui.ts
      api/                    ← typed fetch wrappers per resource
      types/                  ← Hero, Stage, Guild… TypeScript interfaces
      styles/
        tokens.css            ← ALL colors as CSS custom properties
      App.tsx                 ← router + shell layout
      main.tsx                ← Vite entry point
    package.json
    vite.config.ts            ← proxy /me, /heroes, /battles… → :8000 in dev
    tsconfig.json
  app/                        ← UNCHANGED: FastAPI backend + JSON API
    static/dist/              ← Vite build output (gitignored)
```

### How FastAPI serves the SPA

`app/routers/ui.py` shrinks to a catch-all that serves `index.html` for all `/app/*` routes. React Router handles client-side routing from there. `StaticFiles` mount serves `/app/static/dist/*`. The placeholder hero SVG endpoint (`/placeholder/hero/{code}.svg`) is kept.

### Dev workflow

- `uvicorn app.main:app` on port 8000
- `cd frontend && npm run dev` on port 5173
- Vite proxies all API calls (`/me`, `/heroes`, `/battles`, etc.) to port 8000
- Hot reload on every save

### Production / Docker

`npm run build` outputs to `app/static/dist/`. The Docker image copies `dist/` in; FastAPI serves everything from one process. No separate static host needed.

---

## Route Map

### App shell routes

```
/                    → redirect → /app/me
/app                 → redirect → /app/me
/app/login
/app/me
/app/summon
/app/stages
/app/daily
/app/story
/app/arena
/app/shop
/app/account
/app/event           ← hidden from nav when no live event
/app/crafting
/app/achievements
```

### Nested routes (sub-menu pattern)

```
/app/roster
  index              → hero grid
  :heroId            → hero detail sheet

/app/guild
  index              → overview / join flow
  members            → member list + management
  chat               → guild chat
  raids              → raid activity

/app/friends
  index              → friends list
  messages           → DM thread
```

Each parent route renders a secondary nav strip + `<Outlet />`. Adding a new sub-tab in the future is one `<Route>` entry and a nav link — no structural changes.

### Battle routes (full-screen, outside /app shell)

```
/battle/setup        ← was battle-setup.html
/battle/:id/watch    ← was battle-phaser.html
/battle/:id/play     ← was battle-interactive.html
/battle/:id/replay   ← was battle-replay.html
```

Battle routes live outside `/app` so they get a full-screen layout without the nav header.

---

## Data Layer

### Zustand stores (`src/store/`)

**`auth.ts`** — `jwt: string | null`, `setJwt()`, `clearJwt()`. Persisted to localStorage. Replaces all `localStorage.getItem('heroproto_jwt')` callsites.

**`sound.ts`** — `muted`, `master`, `sfx` volume levels + setters. Persisted to localStorage. Replaces `window.sound` global and the sound popover wiring in `shell.html`.

**`ui.ts`** — `toasts: Toast[]`, `addToast()`, `dismissToast()`. Replaces `toast.js` global.

### TanStack Query hooks (`src/hooks/`)

| Hook | Refetch interval | Replaces |
|---|---|---|
| `useMe()` | 60s | `refreshWho()` + `htmx:afterRequest` |
| `useHeroes()` | staleTime 5min | roster partial server render |
| `useHero(id)` | staleTime 5min | hero detail overlay |
| `useStages()` | staleTime 10min | stages partial server render |
| `useGuild()` | on focus | guild partial server render |
| `useRaid()` | 30s | raids partial server render |
| `useNotifications()` | 30s | `_bellTimer` setInterval |
| `useActiveEvent()` | 60s | `probeEvent()` + `htmx:afterRequest` |
| `useBattleLog(id)` | disabled | battle-phaser.html fetch |

Shared `useMe()` cache means the currency bar, the "who" pill, and every tab that shows wallet totals all stay in sync from a single fetch.

### TypeScript types (`src/types/`)

One interface per API resource (`Hero`, `HeroTemplate`, `Me`, `Stage`, `Guild`, `Raid`, `Notification`, `BattleLog`, etc.). API fetch wrappers in `src/api/` return typed responses. Catches shape bugs (e.g. `hero['name']` vs `hero['template']['name']`) at compile time.

### Color tokens

All colors defined in `src/styles/tokens.css` as CSS custom properties (`--color-bg`, `--color-accent`, `--rarity-epic`, `--faction-resistance`, etc.). Components reference tokens only — never hardcoded hex values. Color redesign (planned, separate task) means editing one file.

---

## Battle Routes & Canvas Integration

All four battle routes use the same pattern: a React component renders a `canvasRef` div + a `<BattleHUD>` overlay. `useEffect` mounts the Phaser game or Pixi app into the ref div and destroys it on unmount.

```tsx
function WatchRoute() {
  const canvasRef = useRef<HTMLDivElement>(null)
  const { id } = useParams()
  const { data: log } = useBattleLog(id)

  useEffect(() => {
    if (!canvasRef.current || !log) return
    const game = new Phaser.Game({ parent: canvasRef.current, ... })
    return () => game.destroy(true)
  }, [log])

  return (
    <div style={{ position: 'relative', width: '100%', height: '100vh' }}>
      <div ref={canvasRef} />    {/* canvas fills this */}
      <BattleHUD />              {/* React DOM overlay */}
    </div>
  )
}
```

React owns all DOM UI (HP bars, target buttons, speed controls, rewards overlay). The canvas owns animation only.

**Plan B ready:** when DragonBones rigs land, swap what mounts inside `canvasRef` (Phaser → `@pixi/react` or raw Pixi app). The `BattleHUD` overlay is unchanged.

---

## Migration Strategy: Big-Bang

Build the SPA in `frontend/` while the HTMX shell remains live. Cut over when all tabs and battle routes reach feature parity.

### Build sequence

1. **Scaffold** — Vite project, auth store, api layer, routing shell, Vite proxy config. HTMX still live.
2. **Core tabs** — Me, Roster, Stages, Summon, Shop. Build and verify against the live API.
3. **Remaining tabs + battle routes** — Guild, Arena, Raids, Friends, Daily, Story, Achievements, Event, Crafting, Account + all `/battle/*` routes.
4. **Cutover** — `npm run build` → `app/static/dist/`. Swap `ui.py` to SPA catch-all. Delete HTMX layer. Run full test suite. PWA field test (Sprint H).

### Deleted at cutover

- `app/templates/partials/` — all 15 partial templates
- `app/templates/shell.html`, `app/templates/base.html`
- Most of `app/routers/ui.py` (all partial routes; catch-all and placeholder SVG stay)
- `app/static/battle-setup.html`, `battle-phaser.html`, `battle-interactive.html`, `battle-replay.html`
- `app/static/team-picker.js`, `in-app-viewer.js`, `tutorial-hints.js`, `toast.js`, `sound.js`
- `app/static/sw.js` (replaced by vite-plugin-pwa output)
- `app/static/manifest.webmanifest` (replaced by vite-plugin-pwa generated manifest)

### Kept

- All of `app/` backend (routers, models, combat, etc.) — untouched
- `app/templates/email/` — password reset + verify email templates
- `app/static/heroes/` — portrait and bust images
- `app/static/dragonbones-demo/` — Plan B demo
- `app/static/style.css` — referenced only during transition; tokens.css takes over

---

## Testing

**Python test suite (634 tests):** unchanged throughout — the API is untouched.

**Frontend unit/component tests:** Vitest + React Testing Library covering data hooks (`useMe`, `useHeroes`) and shared components (`HeroCard`, `CurrencyBar`, `BattleHUD`).

**E2E smoke test:** Playwright — login → roster renders → stages page renders → battle setup submits → battle log loads. Kept minimal; the Python walkthrough script covers API correctness.

---

## What This Unblocks

- **Sprint C** — Docker build now runs `npm run build` before the image layer; single FastAPI process serves everything.
- **Sprint H** — `vite-plugin-pwa` generates the service worker and manifest automatically; install on Android + iOS is the field test.
- **Plan B battle visuals** — React + canvas ref pattern is the correct foundation for `@pixi/react` + DragonBones HUD work.
- **Color redesign** — `tokens.css` means the palette overhaul is isolated to one file.
