# Hero voice bark script v1 — ElevenLabs paste-in

**Purpose:** ~100 short voice lines for the 33 base hero templates + the 3 myth/raid tier. Drop straight into ElevenLabs (Turbo v2.5 or v2, your call).

**Voice direction (suggested default):**
- 2 base voices shared across most heroes — one masculine/gravelly ("sysadmin"), one feminine/wry ("ops").
- 4 distinct voices for personality outliers (marked `[VOICE: ...]`).
- All lines: dry delivery, conversational, NOT shouty. Think Overwatch barks crossed with BOFH stories — sysadmins muttering through gritted teeth, not anime power-ups.
- 2–6 words max per line. Punchy. No exposition.

**Three lines per hero:**
- **DEPLOY** — said on entering battle (also usable when summoned from gacha)
- **ATTACK** — basic attack bark
- **SPECIAL** — ability call (named after the actual mechanic)

---

## COMMON (5 heroes)

### Ticket Gremlin — `ticket_gremlin` [ATK]
- DEPLOY: "Ticket open. Reluctantly."
- ATTACK: "Have you tried turning it off."
- SPECIAL: "Reopening this. Indefinitely."

### Printer Whisperer — `printer_whisperer` [SUP]
- DEPLOY: "It's just out of toner."
- ATTACK: "Paper jam. Your problem."
- SPECIAL: "PEBKAC pep-talk."  *(matches "PEBKAC Pep-Talk")*

### Overnight Janitor — `overnight_janitor` [DEF]
- DEPLOY: "Shift starts. Lights out."
- ATTACK: "Mop's heavier than it looks."
- SPECIAL: "Mop stance."

### DevOps Apprentice — `devops_apprentice` [ATK]
- DEPLOY: "First on-call. Probably fine."
- ATTACK: "Ran the playbook."
- SPECIAL: "Reading the docs. Live."

### Forgotten Contractor — `forgotten_contractor` [ATK]
- DEPLOY: "Badge still works. Somehow."
- ATTACK: "Contract was for six months."
- SPECIAL: "I never left."

### Frontline L1 Tech — `frontline_l1_tech` [DEF]
- DEPLOY: "Queue's at forty."
- ATTACK: "Escalating to L2."
- SPECIAL: "Triage protocol."

### Office Coffee Hoarder — `office_coffee_hoarder` [SUP]
- DEPLOY: "The good pot's mine."
- ATTACK: "Cold brew. Cold blooded."
- SPECIAL: "Fresh brew." *(matches "Fresh Brew")*

---

## UNCOMMON (7 heroes)

### Jaded Intern — `jaded_intern` [ATK]
- DEPLOY: "Whatever. I'm not paid."
- ATTACK: "Per my last email."
- SPECIAL: "Passive-aggressive note." *(matches)*

### SRE on Call — `sre_on_call` [SUP]
- DEPLOY: "Paged. Again."
- ATTACK: "Rollback's already running."
- SPECIAL: "Following the runbook."

### Compliance Officer — `compliance_officer` [DEF]
- DEPLOY: "I'll need that in writing."
- ATTACK: "Section four, paragraph nine."
- SPECIAL: "Cite the policy."

### Security Auditor — `security_auditor` [ATK]
- DEPLOY: "Authorized. Allegedly."
- ATTACK: "Vulnerability filed."
- SPECIAL: "Mass pentest."

### Helpdesk Veteran — `helpdesk_veteran` [DEF]
- DEPLOY: "Twenty years. Same questions."
- ATTACK: "Restart fixes everything."
- SPECIAL: "It's been working fine."

### Build Engineer — `build_engineer` [ATK]
- DEPLOY: "CI's green. For now."
- ATTACK: "Pushed. Praying."
- SPECIAL: "Green build."

### Database Archaeologist — `database_archaeologist` [SUP]
- DEPLOY: "These tables go deep."
- ATTACK: "Found another orphan row."
- SPECIAL: "Forgotten query."

### Agile Coach — `agile_coach` [SUP] *[VOICE: corporate-positive, slightly too cheerful]*
- DEPLOY: "Let's circle back to this."
- ATTACK: "How might we... attack?"
- SPECIAL: "Sprint retro."

---

## RARE (8 heroes)

### The Sysadmin — `the_sysadmin` [DEF] *[VOICE: gravel, world-weary]*
- DEPLOY: "I told them this would happen."
- ATTACK: "Pipe to dev null."
- SPECIAL: "sudo bang bang."  *(say "sudo !!" phonetically — "sudo bang bang" is BOFH canon)*

### Root-Access Janitor — `root_access_janitor` [ATK]
- DEPLOY: "Same mop. Bigger keys."
- ATTACK: "Cleaning house."
- SPECIAL: "Mop of regrets."

### VP of Vibes — `vp_of_vibes` [SUP] *[VOICE: corporate-positive]*
- DEPLOY: "Energy's a strategy."
- ATTACK: "Aligning incentives."
- SPECIAL: "All-hands hype."

### Keymaster Gary — `keymaster_gary` [ATK] *[VOICE: deadpan-flat, Disco Elysium dry]*
- DEPLOY: "I have the keys."
- ATTACK: "You don't have a key."
- SPECIAL: "I am the keymaster."  *(deadpan — NOT shouty)*

### Rogue DBA — `rogue_dba` [SUP]
- DEPLOY: "Production. No backup."
- ATTACK: "WHERE clause forgotten."
- SPECIAL: "DROP table enemies."  *(spell out — "drop, table, enemies")*

### Oncall Warrior — `oncall_warrior` [DEF]
- DEPLOY: "Pager's already buzzing."
- ATTACK: "Holding the line."
- SPECIAL: "Hold the pager."

### Cert Collector — `cert_collector` [DEF]
- DEPLOY: "I have fourteen certs."
- ATTACK: "Per the framework."
- SPECIAL: "Hyper-V. vSphere. K8s."  *(staccato, one beat each)*

### Blue Team Lead — `blue_team_lead` [DEF]
- DEPLOY: "Incident channel's open."
- ATTACK: "Logged and tagged."
- SPECIAL: "Incident commander."

---

## EPIC (7 heroes)

### The Post-Mortem — `the_post_mortem` [SUP] *[VOICE: clinical, calm]*
- DEPLOY: "We've been here before."
- ATTACK: "Documenting causes."
- SPECIAL: "Five whys."

### Midnight Pager — `midnight_pager` [ATK]
- DEPLOY: "It's 3 AM. Of course."
- ATTACK: "Already escalating."
- SPECIAL: "3 AM escalation."

### The Consultant — `the_consultant` [DEF] *[VOICE: smooth corporate, mid-Atlantic]*
- DEPLOY: "Bill the hour. Then start."
- ATTACK: "Quarterly synergies."
- SPECIAL: "Deliverables deck."

### Retired Mainframe Guru — `retired_mainframe_guru` [SUP] *[VOICE: older, raspy]*
- DEPLOY: "Saw this in seventy-eight."
- ATTACK: "Punch card energy."
- SPECIAL: "COBOL incantation."

### Shadow IT Operator — `shadow_it_operator` [ATK] *[VOICE: low, conspiratorial]*
- DEPLOY: "Don't tell procurement."
- ATTACK: "Unsanctioned. Effective."
- SPECIAL: "Unapproved tool."

### Tape Library Ghost — `tape_library_ghost` [DEF] *[VOICE: ethereal-flat]*
- DEPLOY: "Mounted from oh-three."
- ATTACK: "Restore in progress."
- SPECIAL: "Backup from 2003."

### The Whistleblower — `the_whistleblower` [SUP] *[VOICE: hushed, urgent]*
- DEPLOY: "Records are with my lawyer."
- ATTACK: "On the record now."
- SPECIAL: "Leak the memo."

### The Successor — `the_successor` [ATK]
- DEPLOY: "Founder's gone. I'm here."
- ATTACK: "Restructuring assets."
- SPECIAL: "Hostile takeover."

---

## LEGENDARY (4 heroes)

### The Founder — `the_founder` [ATK] *[VOICE: smooth corporate, mid-Atlantic, slightly menacing]*
- DEPLOY: "I built this. I'll un-build you."
- ATTACK: "Acquiring."
- SPECIAL: "Hostile takeover."

### Chaos Monkey — `chaos_monkey` [ATK] *[VOICE: gleeful, slightly unhinged]*
- DEPLOY: "Production looks lonely."
- ATTACK: "Kill nine. No reason."
- SPECIAL: "Random kill dash nine."

### The Board Member — `the_board_member` [SUP] *[VOICE: corporate, cold]*
- DEPLOY: "I sit on three other boards."
- ATTACK: "Strategic alignment."
- SPECIAL: "Strategic restructure."

---

## MYTH (3 heroes — flagship event tier)

### TBFAM — `tbfam` [ATK] *[VOICE: confident, almost mocking]*
- DEPLOY: "Everything on the desk. Now."
- ATTACK: "All of it. Mine."
- SPECIAL: "Everything on the desk."

### Applecrumb — `applecrumb` [SUP] *[VOICE: warm, ironic]*
- DEPLOY: "Family office is in session."
- ATTACK: "It's not personal. It's family."
- SPECIAL: "Family office meeting."

### The On-Call Martyr — `on_call_martyr` [DEF] *[VOICE: tired, resigned, heroic only by accident]*
- DEPLOY: "It's always me. Fine."
- ATTACK: "I'll take it."
- SPECIAL: "Emergency change window."

---

## RAID BOSSES (3 — separate voice direction, deeper / more menacing)

### Legacy Colossus — `raidboss_legacy_colossus` [DEF] *[VOICE: slow, monolithic]*
- INTRO: "Twenty years of technical debt. You first."
- ATTACK: "Compatibility maintained."
- SPECIAL: "Bureaucratic inertia."

### C-Suite Hydra — `raidboss_c_suite_hydra` [ATK] *[VOICE: corporate, multiple takes for layered effect]*
- INTRO: "We've decided to restructure. You."
- ATTACK: "Synergy realized."
- SPECIAL: "Mandatory re-org."

### Chaos Dragon — `raidboss_chaos_dragon` [ATK] *[VOICE: low growl, ominous]*
- INTRO: "Everything is degraded. Including you."
- ATTACK: "Cascade."
- SPECIAL: "Cascading outage."

---

## SYSTEM / NARRATOR (5 utility lines)

*[VOICE: one unifying narrator — calm, mission-control flat]*

- BATTLE_START: "Engagement initiated."
- VICTORY: "Engagement resolved. Clean."
- DEFEAT: "Engagement lost. Records preserved."
- MYTH_PULL: "Anomaly detected. Mythic-tier asset acquired."
- FACTION_LOCKED: "Alignment confirmed. There's no going back."

---

## Tally

- 33 base heroes × 3 lines = 99
- 3 raid bosses × 3 lines = 9
- 5 system/narrator lines = 5
- **Total: 113 lines** (close to the 100 target — feel free to trim system + bosses if credit-tight)

**Character estimate:** ~40 chars avg × 113 = ~4,500 characters. At v2 (2 credits/char) that's ~9,000 credits. At Turbo (1 credit/char) ~4,500.

Plenty of headroom in your 52k budget for alternate takes, longer narrator monologues, or to bump quality to v3 if it's out.

## Output naming

Save the resulting mp3s as `app/static/voice/<template_code>_<event>.mp3`, e.g.:
- `app/static/voice/ticket_gremlin_deploy.mp3`
- `app/static/voice/ticket_gremlin_attack.mp3`
- `app/static/voice/ticket_gremlin_special.mp3`

That matches the BGM path pattern (`app/static/bgm/...`) and the frontend wiring will be a simple lookup keyed on `template_code` + event type.
> [Pasted text #8 +20 lines] > [Pasted text #8 +20 lines] > [Pasted text #8 +20 lines] 

NODE_ENV=production
  PORT=3000
  DB_PATH=/var/lib/mongoose/msp.db
  MASTER_KEY=HEnZms3qKUAuPFKvWVGms7+24JA8hTQ0bXahDDrF0rk=
  JWT_SECRET=9b23276ee959e68e72c5a1c4fe02c80bdaff351f015f7f024018361400f1a8ec
  ENROLLMENT_TOKEN=91aa8b9236cb7631bd8dbb3176980316794cd231a9999cf3ced63fd7cc9eb01b
  
  Steweredress1!Steweredress1!
  
   Two layers, both need to allow them:

  1. Cloudflare Access (lets them past the front door)

  CF Zero Trust → Access → Applications → mongoose-admin → Edit → Policies tab → add their email to the Allow list. Save.

  2. Mongoose user account (lets them into the app)

  Login as admin in the UI → Settings → "+ Add User" → username, password, role: tech (or admin if they need user-management).

  Then they:
  - Open https://app.mongoose.support/app
  - CF emails them a one-time PIN → enter it
  - Mongoose login screen → use the credentials you set

  If you want to skip the PIN-every-session pattern, switch the CF Access policy from "One-time PIN" to a real IdP (Google / Microsoft / GitHub) — they sign in once with their existing
  identity and CF remembers them.
  
  1. Zero Trust → Access → Applications
  2. Click mongoose-admin (the app you created)
  3. Policies tab (top)
  4. Click your existing Allow policy (probably named something like "admin-only")
  5. Under Configure rules → in the Include section there's an Emails field with your email
  6. Add the other tech's email — comma-separated, or hit "+ Add include" for a new row
  7. Save
  
  Step 1 — Studio (do this for the bark script)
  1. Top nav → Studio (or "Projects" depending on version)
  2. New project → paste each hero block from the bark md as a separate
  paragraph
  3. Pick voice from Voice Library — search "narrator" or "gravel" — assign to
  all lines
  4. For the 6 outlier voices I flagged in the script ([VOICE: ...]), create
  separate mini-projects with different voices
  5. Render → batch-download zip

  That alone burns ~9-15k credits depending on quality tier.

  Step 2 — Sound Effects (separate page)
  1. Top nav → Sound Effects
  2. Prompt one at a time, 4-second clips. Burn through this list:
    - "8-bit gacha pull whoosh ending in chime"
    - "epic mythic rarity reveal fanfare 3 seconds"
    - "legendary tier reveal chime"
    - "epic tier reveal sting"
    - "rare tier subtle chime"
    - "common tier soft ding"
    - "critical hit splash impact"
    - "metallic sword swing"
    - "magic zap"
    - "heavy armor block thud"
    - "heroic victory fanfare 3 seconds"
    - "defeated sigh dramatic"
    - "button click ui sci-fi"

  Step 2 — Sound Effects (separate page)
  1. Top nav → Sound Effects
  2. Prompt one at a time, 4-second clips. Burn through this list:
    - "8-bit gacha pull whoosh ending in chime"
    - "epic mythic rarity reveal fanfare 3 seconds"
    - "legendary tier reveal chime"
    - "epic tier reveal sting"
    - "rare tier subtle chime"
    - "common tier soft ding"
    - "critical hit splash impact"
    - "metallic sword swing"
    - "magic zap"
    - "heavy armor block thud"
    - "heroic victory fanfare 3 seconds"
    - "defeated sigh dramatic"
    - "button click ui sci-fi"
    - "level up chime ascending"
    - "milestone unlocked sting"
    - "gear equip metallic clack"
    - "10-pull gacha crescendo 4 seconds"
    - "kernel panic alarm 2 seconds"
    - "data corruption glitch effect"
    - "boss intro ominous drone"
    - "shield activate energy hum"
    - "healing chime warm"
    - "buff applied positive sting"
    - "debuff applied negative sting"
    - "stun impact reverb"
    - "poison tick squelch"
    - "revive resurrection chime epic"
    - "freeze ice crack"
    - "fire dot crackle"
    - "menu open swoosh sci-fi"

  30 SFX × 100-ish credits each = ~3k credits.

  Step 3 — Ignore everything else

  Skip: Voice Design (custom voice creation — premium, slow), Conversational AI (overkill), Music (we're already covered), Dubbing (not relevant).

  Total burn: ~15-20k credits in maybe 90 min. Still leaves ~30k for alt takes / longer narrator monologues if you've got patience.

  Want me to draft the SFX list as a copy-paste block formatted for ElevenLabs?