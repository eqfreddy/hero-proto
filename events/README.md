# Special events / holidays

Pre-planned LiveOps content for the calendar. Each holiday has a JSON spec describing the announcement, the LiveOps multiplier(s), the limited shop SKU, and (when applicable) the event hero. Ops invokes `scripts/activate_event.py <file>` on the morning of the event; everything goes live at the configured `starts_at` and self-expires at `ends_at`.

---

## Calendar (2026)

Add to your ops calendar. Activate ~24h before the start time so the daily worker tick has settled.

| Date | Event | File | Notes |
|---|---|---|---|
| **2026-07-01** | Canada Day | `2026-07-01_canada_day.json` | DOUBLE_REWARDS + cosmetic pack |
| **2026-07-04** | Summer Slowdown (week-long) | `2026-07-04_summer_slowdown.json` | ⚡ Sparks currency, 5 quests, 5 milestones — subsumes Independence Day |
| 2026-10-31 | Halloween | `2026-10-31_halloween.json` | BONUS_GEAR_DROPS + spooky cosmetic pack |
| 2026-11-27 | Black Friday | `2026-11-27_black_friday.json` | Discount weekend on gem packs (skip for alpha) |
| 2026-12-25 | Christmas | `2026-12-25_christmas.json` | Week-long DOUBLE_REWARDS + advent calendar |
| 2026-12-31 | New Year | `2026-12-31_new_year.json` | 48h DOUBLE_REWARDS + retrospective announcement |
| 2027-02-14 | Valentine's Day | (TBD) | "TBFAM Brought You Flowers" event |

---

## Event spec format

Every event JSON has the same shape:

```json
{
  "id": "canada_day_2026",
  "display_name": "Canada Day 2026",
  "starts_at": "2026-07-01T13:00:00Z",
  "ends_at":   "2026-07-03T13:00:00Z",
  "announcement": {
    "title": "🍁 Happy Canada Day!",
    "body":  "...",
    "priority": 50
  },
  "liveops": [
    { "kind": "DOUBLE_REWARDS", "name": "Canada Day 2x", "payload": {"multiplier": 2.0} }
  ],
  "shop": [
    {
      "sku": "canada_day_2026_pack",
      "title": "Canada Day Pack",
      "description": "Maple-glazed bundle: 1000 gems, 100 shards.",
      "price_cents": 999,
      "kind": "GEM_PACK",
      "per_account_limit": 1,
      "contents": {"gems": 1000, "shards": 100}
    }
  ],
  "event_hero_code": null
}
```

Field semantics:
- `id` — slug used by `activate_event.py` to dedupe re-runs.
- `starts_at` / `ends_at` — UTC ISO timestamps. Worker honors these natively.
- `announcement` — single AdminAnnouncement row pinned for the duration.
- `liveops` — list of LiveOpsEvent rows (DOUBLE_REWARDS, BONUS_GEAR_DROPS, BANNER, etc.).
- `shop` — limited-time ShopProducts. Use `per_account_limit: 1` for one-time bundles. Auto-disabled at `ends_at`.
- `event_hero_code` — optional pointer to a Myth-tier hero seeded for the event (set up separately in `seed.py`).

### Optional: gather-and-spend mechanics

If the event includes a currency-gathering loop (week-long events, summer/winter campaigns, etc.) add these fields:

```json
"currency_name": "Sparks",
"currency_emoji": "⚡",
"drops": {
  "battle_win":   5,
  "summon_pull":  2,
  "arena_attack": 8,
  "raid_attack": 12
},
"quests": [
  {
    "code": "win_10_battles",
    "title": "Win 10 battles",
    "kind": "WIN_BATTLES",
    "goal": 10,
    "currency_reward": 50
  }
],
"milestones": [
  {
    "title": "Warm-up Pack",
    "cost": 100,
    "contents": {"gems": 200, "shards": 20}
  }
]
```

- `drops` — activity → currency-per-activity. Recognized activities: `battle_win`, `summon_pull`, `arena_attack`, `raid_attack`. Each fires once per matching event.
- `quests` — list of objectives. `kind` must be one of: `WIN_BATTLES`, `SUMMON_PULLS`, `ARENA_ATTACKS`, `RAID_ATTACKS`. `currency_reward` is paid out on POST `/events/quests/{code}/claim` once the player hits `goal`.
- `milestones` — ordered list of currency exchanges. Spent via POST `/events/milestones/{idx}/redeem`. `contents` accepts the same kinds as `ShopProduct.contents_json`: `gems`, `shards`, `coins`, `access_cards`, `free_summon_credits`, `hero_template_code`.

Per-account state lives on `Account.event_state_json` (currency balance + quest progress + claimed quests + redeemed milestone indices). Reset implicitly when the event ends — the spec stops being "active" so progress stops accumulating, but the leftover state stays in the column for refund / audit.

---

## Workflow

```bash
# 1. Edit the JSON for the event (timestamps, copy, prices).
# 2. Activate (creates LiveOpsEvent + AdminAnnouncement + ShopProduct rows).
uv run python -m scripts.activate_event events/2026-07-01_canada_day.json

# 3. Verify it shows up live.
uv run python -m scripts.startup_check
curl -s http://your-domain/announcements/active | jq
curl -s http://your-domain/liveops/active | jq
curl -s http://your-domain/shop/products | jq

# 4. Done. The worker handles expiration — anything past ends_at silently
#    stops being "active". Old rows stay in the DB for audit / refund.
```

If you need to deactivate early (event flopped, something broke):
```bash
uv run python -m scripts.activate_event events/<file> --deactivate
```

---

## Tone / writing notes

- Events ride the corporate-IT satire. "Canada Day" → maple-glazed runbook; "Independence Day" → freedom from on-call (just for one day).
- Never tie real political events / national strife into copy. Keep it cheerful + IT-flavored.
- Cosmetic event packs are PoE2-style — currency or cosmetic only. Never a hero with raw stat advantage.
- Announcement priority 50+ = pinned with the "important" pill on /me.

---

## Adding a new event

1. Copy `_template.json` to `<YYYY-MM-DD>_<slug>.json`.
2. Fill in copy + dates + prices.
3. Add a row to the calendar table above.
4. Test in dev: activate against a local server, verify endpoints reflect the changes, deactivate.
5. Schedule the activation in ops calendar 24h before launch.
