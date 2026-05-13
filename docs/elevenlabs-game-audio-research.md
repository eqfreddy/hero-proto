# ElevenLabs for hero-proto — Game Audio Research

> Research date: 2026-05-12. Live URLs were blocked at fetch time; report compiled from training knowledge. **Verify pricing/credit numbers at https://elevenlabs.io/pricing before subscribing** — these change frequently.

## TL;DR — Go here, type this

| Need | URL | Tier you need |
|---|---|---|
| Music (combat loops, themes) | **https://elevenlabs.io/app/music** | Creator ($22/mo) minimum for commercial license |
| Sound effects (swings, magic, UI) | **https://elevenlabs.io/app/sound-effects** | Creator ($22/mo) sweet spot |
| Voice (NPC barks, narrator) | https://elevenlabs.io/app/speech/text-to-speech | any paid tier |

**Recommendation for hero-proto: Creator tier ($22/mo, ~100k credits).** It unlocks full commercial rights with no attribution required and gives enough credits for an indie game's audio bed. Bump to Pro ($99) only if you're generating dozens of music tracks/month.

---

## 1. Music Generation — "Eleven Music"

- **Model name:** Eleven Music (launched mid-2025, sometimes called "ElevenLabs Music" in UI)
- **Max length:** up to ~5 minutes per generation; can stitch longer
- **Looping:** No native "seamless loop" toggle yet — you prompt for loop-friendly structure ("4-bar repeating ostinato, no fade out, ends on downbeat") and trim in Audacity/Reaper. Community workaround: prompt "loopable, no intro, no outro, constant tempo."
- **Genres/styles:** Very broad — orchestral, cinematic, chiptune, lo-fi, synthwave, metal, ambient, jazz, EDM. Works well for game music; orchestral combat themes and ambient exploration are strong suits.
- **Cost:** ~2,000 credits per minute of music generated (rough — verify). On Creator (100k credits) that's ~50 minutes/month of music.
- **Where to prompt:** Web UI at `/app/music`. Big prompt box, optional reference clip upload, duration slider. Also available via API (`/v1/music/compose`).
- **Vocals:** Can generate with or without lyrics; for game use, prompt "instrumental only."

## 2. Sound Effects — "Eleven SFX"

- **Model name:** Sound Effects (text-to-SFX, launched late 2024)
- **Max duration:** 22 seconds per clip (auto-detect length, or set manually)
- **Where to prompt:** `/app/sound-effects`. Prompt box, duration slider, "prompt influence" slider (low = creative, high = literal).
- **Cost:** ~40 credits per second of SFX (roughly 1 credit ≈ 1 character of TTS). A 2-second sword swing ≈ 80 credits. Creator's 100k credits = ~40 minutes of SFX or hundreds of one-shots.
- **Quality:**
  - **Strong:** percussive impacts (sword clang, punch, footsteps), magic whooshes, ambient beds (cave drip, forest, tavern), monster roars, UI clicks/blips
  - **Weaker:** highly musical SFX (music boxes, melodic chimes) — sometimes drift off-key; tonal magic spells may need 3-5 rerolls
  - Each prompt returns **3 variations** by default — pick the best, the others are still billed
- **Format:** 44.1kHz MP3 download; PCM/WAV on higher tiers

## 3. Voice (quick note)

- Text-to-Speech at `/app/speech/text-to-speech`. Pick from library voices or clone (Pro+ needed for instant voice clone with commercial rights).
- For NPC barks: generate short lines per voice, name them by character. Use Eleven v3 model (most expressive, best for stylized characters).
- Costs ~1 credit/char. A 20-word NPC line ≈ 100 credits.
- Voice Library has thousands of community voices — fantasy narrator, gravelly orc, etc. are pre-built.

## 4. Pricing Tiers (verify at /pricing)

| Tier | ~Price | ~Credits/mo | Commercial use | Notes |
|---|---|---|---|---|
| Free | $0 | 10k | **No** — attribution required | Watermark concerns: none on audio, but ToS forbids commercial release |
| Starter | $5 | 30k | Yes (limited) | Tight for game dev |
| **Creator** | **$22** | **100k** | **Yes, full** | **Sweet spot for hero-proto** |
| Pro | $99 | 500k | Yes, full | If you're scoring 20+ tracks |
| Scale | $330 | 2M | Yes | Overkill |
| Business | $1320+ | 11M | Yes | Studios only |

Annual billing knocks ~20% off. Credits roll over partially on paid tiers.

## 5. Commercial Use / Licensing

- **Paid tiers (Starter and up):** Full commercial rights. Ship on Steam, App Store, Play Store, consoles. **No attribution required.**
- **Free tier:** Attribution required ("Created with ElevenLabs") and **no commercial use** — do not use Free-tier output in a paid or monetized game.
- You **own** the generated output on paid tiers; ElevenLabs retains a license to the underlying model (you can't claim ownership of the model itself).
- No revenue share, no per-stream royalty. One flat sub.

## 6. Where to put a prompt — concrete workflow

1. Log in → top-left dropdown → **"Music"** or **"Sound Effects"**
2. Paste prompt → set duration → click **Generate** (returns 3 variations for SFX, 1-2 for music)
3. Star the keepers → download MP3/WAV → drop into `/frontend/public/audio/` (or wherever hero-proto serves audio)
4. For loops: open in Audacity → find a zero-crossing near the end of a musical phrase → trim → export

## 7. Recommended starter prompts

**Combat music (loopable, 60-90s):**
- `"Heroic orchestral battle theme, 140bpm, driving timpani and brass ostinato, soaring strings, no intro no outro, loopable, instrumental, fantasy MMORPG combat"`
- `"Dark synthwave boss fight, 128bpm, aggressive analog bass, distorted lead, four-on-the-floor kick, loopable, no fade"`
- `"Anime gacha hero collector battle theme, fast melodic strings, electric guitar accents, 150bpm, hopeful and energetic, loopable"`

**Victory fanfare (5-10s, one-shot):**
- `"Triumphant 6-second orchestral victory sting, brass fanfare resolving to major chord, ending with cymbal swell"`
- `"Cheerful 4-second jingle, harp glissando into bright woodwinds, JRPG victory feel"`

**Sword/melee swing+hit:**
- `"Sharp metallic sword swing followed by a meaty impact and faint metal ring, 1 second"`
- `"Heavy two-handed greatsword cleave hitting armored target, deep clang and grunt"`

**Magic spell cast:**
- `"Crystalline magic spell charge-up rising in pitch then bright sparkle release, 2 seconds, fantasy RPG"`
- `"Dark necromancy spell, low whoosh with bone rattle and ghostly whisper, 1.5 seconds"`

**UI click / menu confirm:**
- `"Crisp digital UI confirm click, soft synth blip, gentle reverb tail, 200ms, mobile game menu"`
- `"Subtle wood-and-paper menu open sound, parchment unfurl, 400ms"`

## 8. Gotchas

- **Credits burn fast on rerolls** — SFX gives 3 variations per click, all billed. Budget 5-10 generations per final asset.
- **No seamless-loop button.** Plan to trim manually. Music sometimes adds 1-2s of silence/fade.
- **Tonal SFX inconsistency** — music boxes, melodic chimes, harmonic magic can drift off pitch. Reroll or use library SFX (Freesound) as backup.
- **No daily caps** on paid tiers, just monthly credit budget. Free tier has both monthly and concurrent limits.
- **Credit accounting:** music = duration-based; SFX = duration-based; TTS = character-based. Don't assume parity.
- **Mono output by default** for SFX; music is stereo.
- **No "regenerate this section"** — every gen is from scratch. Save seeds/prompts in a sheet so you can reproduce a style.
- **Audio is downloaded as MP3 (lossy);** WAV on Pro+. For final game ship, prefer Pro export → encode to OGG yourself.

---

**Next step for hero-proto:** Sign up for Creator, spend a couple hours in `/app/sound-effects` generating the combat SFX set (swing, hit, crit, miss, heal, victory, level-up, gacha pull, UI click x3 variants). Then one combat-theme music gen + one menu/town ambient. Drop into `frontend/public/audio/`, wire into the battle3d hooks.
