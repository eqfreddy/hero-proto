# Sound system

Pure-synthesized SFX via Web Audio API. Zero shipped audio files. Designed so real audio assets can be plugged in later without changing any caller code.

---

## What ships today

`app/static/sound.js` defines a `window.sound` singleton that synthesizes ~20 short sound effects on demand using oscillators + envelopes. Settings (mute, master volume, SFX volume) persist in `localStorage` under the key `heroproto_sound`.

The only place sound is loaded is `templates/base.html` (via `templates/shell.html`'s scripts block). Static landing page (`templates/welcome.html`) doesn't load it — marketing pages stay quiet.

A 🔊 / 🔇 gear icon lives in the header. Clicking it opens a popover with mute toggle, master + SFX volume sliders, and "test by category" buttons (UI / Combat / Gacha / Events).

---

## Public API

```js
window.sound.play('click');          // fire one named SFX
window.sound.test('all');            // walk through every cue
window.sound.test('gacha');          // just the gacha bank

window.sound.setMute(true);
window.sound.setMaster(0.6);         // 0..1
window.sound.setSfx(0.8);            // 0..1

window.sound.muted;                  // bool
window.sound.master;                 // 0..1
window.sound.sfx;                    // 0..1
```

`play(name)` is a no-op if `name` is unknown (logs to console.debug). Safe to call before user interaction — it'll silently buffer until the AudioContext resumes.

---

## Sound bank

| Name | When fired | Character |
|---|---|---|
| `click` | Any `.primary` / `.secondary` button click | Short noise burst (keyboard tap) |
| `tab` | Top-nav tab switch | Soft mid-frequency triangle blip |
| `success` | Generic positive | Two-note ascending arpeggio |
| `error` | Generic negative | Two-note descending square |
| `toast` | Notification surface | Single sine pulse |
| `hit` | Combat hit | Filtered noise burst |
| `crit` | Critical hit | Noise burst + bright square stab |
| `death` | Unit dies | Sawtooth pitch sweep down |
| `victory` | Battle WIN | Major arpeggio (C-E-G-C) |
| `defeat` | Battle LOSS | Minor descending arpeggio |
| `pull_common` | Gacha COMMON result | Single noise tick |
| `pull_uncommon` | UNCOMMON | Two-note rise |
| `pull_rare` | RARE | Three-note arpeggio |
| `pull_epic` | EPIC | Sweep + 3-voice triangle chord |
| `pull_legendary` | LEGENDARY | Full sweep + 5-voice triangle chord |
| `pull_myth` | MYTH | Long sweep + 6-voice ethereal sine chord |
| `pager` | Future raid-ready notification | Square wave double-beep |
| `mailbox` | Inventory mailbox claim | Two-note sine rise |
| `coin_grant` | Crafting / shard exchange / generic reward | Three-note sine sting |
| `quest_claim` | Event quest reward | Three-note triangle sting (brighter than coin_grant) |
| `purchase` | Shop / starter pack / event milestone | Two-note major sting |
| `daily_bonus` | Daily login claim | Four-note triangle arpeggio |

Tweak: edit the `SOUNDS` map in `sound.js`. Each entry is a function returning a Promise — synth helpers (`tone`, `noise`, `arpeggio`, `chord`, `sweep`) sit above the bank for reuse.

---

## Where sound is wired

| Event | Caller | Sound |
|---|---|---|
| Tab switch | `shell.html` nav-button click handler | `tab` |
| Button click | `shell.html` global delegated handler | `click` |
| Tutorial battle outcome | `partials/me.html` startTutorial() | `victory` / `defeat` |
| Daily bonus claim | `partials/me.html` claimDailyBonus() | `daily_bonus` |
| Mailbox item claimed | `partials/me.html` claimMailbox() | `mailbox` |
| x1/x10 summon result | `partials/summon.html` summonFromTab() | `pull_<best_rarity>` |
| Starter pack purchase | `partials/summon.html` buyStarterPack() | `purchase` |
| Stage battle outcome | `partials/stages.html` battleStage() | `victory` / `defeat` |
| Crafting success | `partials/crafting.html` craftRecipe() | `coin_grant` |
| Shard exchange | `partials/shop.html` exchangeShards() | `coin_grant` |
| Event quest claim | `partials/event.html` claimEventQuest() | `quest_claim` |
| Event milestone redeem | `partials/event.html` redeemEventMilestone() | `purchase` |
| Settings volume drag | `shell.html` slider input handler | `click` (preview) |

All call sites use `if (window.sound) window.sound.play(...)` so the system is optional — if `sound.js` fails to load, every game flow keeps working.

---

## Mobile autoplay

iOS Safari (and increasingly desktop Chrome) suspends `AudioContext` until the user has interacted with the page. `setupAutoresume()` in `sound.js` listens for the first `click` / `touchstart` / `keydown` and calls `ctx.resume()` exactly once. From the user's perspective: the first action they take might be silent; everything after plays.

If you're testing on iOS and audio seems dead, tap the screen once before judging.

---

## Replacing synth with real audio files

When you have actual recordings or generated audio:

1. Drop them into `app/static/sound/` (folder doesn't exist yet — create it).
2. Choose a runtime (Howler.js is the standard for web games).
3. Replace each entry in `SOUNDS` with a `loadAndPlay('/app/static/sound/<file>.ogg')` call. Or rebuild the file as a Howler-based version — the public API (`sound.play(name)`) doesn't have to change, so no caller updates needed.

Recommended file layout:

```
app/static/sound/
├── ui.ogg               ← sprite (click, tab, success, error, toast)
├── combat.ogg           ← sprite (hit, crit, death, victory, defeat)
├── gacha.ogg            ← sprite (pull_common .. pull_myth)
├── notifications.ogg    ← sprite (pager, mailbox, coin_grant, quest_claim, purchase, daily_bonus)
└── music/
    ├── menu_loop.ogg
    ├── battle_loop.ogg
    └── raid_loop.ogg
```

Sprite sheets (single file, multiple cues) are good practice — fewer HTTP requests, fewer cache entries. Howler has built-in sprite support.

Audio source ideas:
- **Free CC0**: pixabay.com/sound-effects, freesound.org, opengameart.org
- **AI-generated**: ElevenLabs Sound Effects, Stable Audio, Suno
- **Commission**: Fiverr / Upwork for original score + voice barks

For the corporate-IT theme: search "keyboard click", "pager beep", "printer error", "dial-up handshake", "Slack notification", "1990s PC startup chime".

---

## Tone guideline

Keep SFX *restrained*. The corporate-IT joke lands harder when sounds are sparse and themed. Don't add a sound to every hover state; don't extend the gacha pull buildup past 0.5s. Predatory dopamine engineering is what we're satirizing, not what we're shipping.
