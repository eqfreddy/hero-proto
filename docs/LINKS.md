# hero-proto — Quick Links

Dev server: `uv run uvicorn app.main:app --host 127.0.0.1 --port 8000`
Base URL (local): `http://localhost:8000`

---

## Game (SPA)

| Page | URL |
|---|---|
| Landing / register | http://localhost:8000/ |
| Sign in / register / forgot pw | http://localhost:8000/app/login |
| Dashboard | http://localhost:8000/app/me |
| Hero roster | http://localhost:8000/app/roster |
| Summon | http://localhost:8000/app/summon |
| Campaign stages | http://localhost:8000/app/stages |
| Story / alignment fork | http://localhost:8000/app/story |
| Arena | http://localhost:8000/app/arena |
| Guild | http://localhost:8000/app/guild |
| Raids | http://localhost:8000/app/raids |
| Daily quests | http://localhost:8000/app/daily |
| Shop | http://localhost:8000/app/shop |
| Crafting | http://localhost:8000/app/crafting |
| Achievements | http://localhost:8000/app/achievements |
| Active event | http://localhost:8000/app/event |
| Friends / DMs | http://localhost:8000/app/friends |
| Account / security / sessions | http://localhost:8000/app/account |
| Battle setup | http://localhost:8000/app/battle/setup |

---

## Admin

| Page | URL |
|---|---|
| Admin panel (vanilla-JS UI) | http://localhost:8000/app/admin |
| API docs (Swagger) | http://localhost:8000/docs |
| API docs (ReDoc) | http://localhost:8000/redoc |

### Admin API endpoints (all require `is_admin=true` JWT)

| Endpoint | Purpose |
|---|---|
| `GET /admin/accounts` | List all accounts |
| `GET /admin/accounts/{id}` | Account detail |
| `POST /admin/accounts/{id}/grant` | Grant currency / items |
| `POST /admin/accounts/{id}/ban` | Ban account |
| `POST /admin/accounts/{id}/unban` | Unban account |
| `POST /admin/accounts/{id}/promote` | Promote to admin |
| `POST /admin/accounts/{id}/demote` | Demote from admin |
| `POST /admin/liveops` | Create LiveOps event |
| `DELETE /admin/liveops/{id}` | Delete LiveOps event |
| `GET /admin/stats` | Server-wide stats (DAU, revenue, hero counts) |
| `GET /admin/audit` | Audit log |
| `GET /admin/purchases` | All purchases |
| `POST /admin/purchases/{id}/refund` | Refund a purchase |
| `GET /admin/analytics/overview` | Analytics overview |
| `GET /admin/announcements` | List announcements |
| `POST /admin/announcements` | Create announcement |

---

## Ops / monitoring

| Page | URL |
|---|---|
| Health check | http://localhost:8000/healthz |
| Worker status | http://localhost:8000/worker/status |
| Prometheus metrics | http://localhost:8000/metrics |
| Public status board | http://localhost:8000/status |

---

## Marketing / legal

| Page | URL |
|---|---|
| About | http://localhost:8000/about |
| FAQ | http://localhost:8000/faq |
| Support | http://localhost:8000/support |
| Privacy policy | http://localhost:8000/privacy |
| Terms of service | http://localhost:8000/terms |
| Press kit | http://localhost:8000/press |
| Roadmap | http://localhost:8000/roadmap |
| Changelog | http://localhost:8000/changelog |
| Dev blog | http://localhost:8000/devblog |

---

## Key API routes (player-facing)

| Route | Purpose |
|---|---|
| `POST /auth/register` | Register (always 200, enumeration-safe) |
| `POST /auth/login` | Login → access + refresh token |
| `POST /auth/refresh` | Rotate refresh token |
| `GET /me` | Current account state (gems, energy, faction, XP…) |
| `GET /heroes/mine` | Owned hero instances |
| `GET /story` | Story chapters + stage unlock state |
| `POST /story/alignment` | Level-50 alignment fork choice |
| `POST /battles` | Run a battle |
| `POST /battles/preview` | Win-probability preview (5-sim) |
| `GET /arena/opponents` | Matchmade opponent list |
| `GET /summon/banner` | Current summon banner |
| `POST /summon/pull` | Gacha pull (x1 or x10) |
| `GET /liveops/active` | Active LiveOps event |
| `GET /liveops/scheduled` | Upcoming events |
| `GET /notifications` | Bell notifications |
| `GET /me/sessions` | Active login sessions |
| `DELETE /me` | GDPR account deletion |
| `GET /me/export` | GDPR data export |

---

## Battle viewer (vanilla-JS, standalone)

| Page | URL |
|---|---|
| Phaser replay viewer | http://localhost:8000/app/static/battle-phaser.html |
| Pixi / DragonBones prototype | http://localhost:8000/app/static/battle-pixi.html |
| DragonBones demo | http://localhost:8000/app/static/dragonbones-demo/index.html |
