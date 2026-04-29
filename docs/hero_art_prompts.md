# Hero art prompts — remaining 31 characters

Copy-paste these into fresh ChatGPT sessions, one character per session (context drift is the enemy — new chat for each one).

## Shared style lock (paste FIRST in every new session)

```
I need a trading-card style character portrait, matching the style of the 5 cards you generated earlier for "hero-proto" (Ticket Gremlin, Jaded Intern, The Sysadmin, The Consultant, The Founder). Same format:

- Portrait trading card, approximately 1050x1498
- Rarity banner at top (color matches rarity tier)
- Full detailed comic-book illustration of the character with environmental props
- Rarity-colored card border frame
- Character name in a banner at bottom
- Faction + Role labels with icons below the name
- One-line flavor text at the very bottom
- Bold ink linework, rich painterly color, slightly oversaturated
- Satirical corporate-IT world

Rarity color treatments:
- COMMON: grey/silver border, muted palette, modest environmental detail
- UNCOMMON: green border, slightly enriched scene
- RARE: purple border, richer colors + more props
- EPIC: gold border + smoky atmosphere, dense environment
- LEGENDARY: ornate gold border with glow, heavily detailed environment, aggressive framing
- MYTH: iridescent/prismatic holographic border with red/gold/blue color-shift effect — supernatural, otherworldly

Factions (use consistent iconography across the set):
- HELPDESK: headset icon, cool blue accents
- DEVOPS: gear/cog icon, green accents
- LEGACY: floppy disk or mainframe icon, purple accents
- EXECUTIVE: briefcase icon, gold accents
- ROGUE_IT: skull-in-sunglasses icon, red-orange accents

OUTPUT: Single PNG, full trading card, single character centered, satirical but recognizable.

Do NOT: make it anime, cute, chibi, child-like, Disney, or overly cartoony.

Ready for the character brief.
```

Then paste ONE of the following character briefs. Download the resulting PNG as `<hero_code>.png` and drop in `app/static/heroes/cards/` — the auto-crop will produce the matching bust.

---

## COMMON tier (grey/silver frames)

### printer_whisperer
```
CHARACTER: "Printer Whisperer" — COMMON / HELPDESK / SUP

A middle-aged helpdesk worker with a defeated-but-tender expression, holding a stethoscope to the side of a large office printer that's smoking slightly. Wrinkled button-down shirt rolled to the elbows, glasses fogged from the printer's steam. Background: toner cartridges stacked, paper jam warning light, a torn "Out of Service" sign. Gentle resignation — they've accepted that machines need love too.

Flavor text: "PC load letter. Every time."
```

### overnight_janitor
```


CHARACTER: "Overnight Janitor" — COMMON / LEGACY / DEF

A large tired man in grey coveralls, holding a mop in one hand and an enormous coffee mug in the other. Heavy dark circles under the eyes, stubble, hair slightly greasy. Background: empty fluorescent-lit office at 3AM, chairs on desks, a single CRT monitor glowing in the distance. Silent night-shift dignity.

Flavor text: "The servers are loud. The office is not."
```

### devops_apprentice
```
CHARACTER: "DevOps Apprentice" — COMMON / DEVOPS / ATK

A young engineer in a hoodie covered in vendor stickers (AWS, Kubernetes, Docker), clutching a laptop with a terminal full of red error text. Wide-eyed and slightly panicked but determined. Background: a cluttered standing desk with energy drinks and a whiteboard showing a deployment pipeline.

Flavor text: "It works on my machine."
```

### forgotten_contractor
```
CHARACTER: "Forgotten Contractor" — COMMON / ROGUE_IT / ATK

A slim person in an ill-fitting polo shirt with a visitor badge that says "CONTRACTOR — DAY 847". Stubble, eyes slightly haunted, holding a battered laptop with their own personal stickers on it. Background: a cubicle nobody's claimed, with someone else's wedding photo still on the partition. Liminal employment energy.

Flavor text: "I don't know whose team I'm on anymore."
```

### frontline_l1_tech
```
CHARACTER: "Frontline L1 Tech" — COMMON / HELPDESK / DEF

Young person in a corporate polo with a headset and microphone, forcibly cheerful smile while eye-twitching slightly. Holding up a "Have you tried turning it off and on again?" script card. Background: rows of identical cubicles, a "DAYS SINCE LAST OUTAGE: 0" counter on the wall.

Flavor text: "Happy to help. I guess."
```

### office_coffee_hoarder
```
CHARACTER: "Office Coffee Hoarder" — COMMON / ROGUE_IT / SUP

A mid-40s employee in a wrinkled blazer, protectively cradling a pyramid of stacked coffee mugs. Squinting suspiciously at the viewer. One mug says "WORLD'S OKAYEST BOSS", another "WRITTEN BY AI", a third "I ♥ SPREADSHEETS". Background: an office breakroom with an empty coffee pot and a sticky note that says "WHO TOOK MY CREAMER".

Flavor text: "Every pod is mine. Every pod."
```

---

## UNCOMMON tier (green frames)

### sre_on_call
```
CHARACTER: "SRE On-Call" — UNCOMMON / DEVOPS / SUP

A tired engineer in a grey hoodie, holding a thick binder labeled "RUNBOOK" in one hand and a pager buzzing angrily on their belt. Dark circles so pronounced they're almost bruises. Headphones around the neck. Background: multiple monitors showing Grafana dashboards all red, a cot in the corner with a pillow.

Flavor text: "It's fine. Everything's fine."
```

### compliance_officer
```
CHARACTER: "Compliance Officer" — UNCOMMON / EXECUTIVE / DEF

A prim middle-aged person in a perfectly-pressed button-down and cardigan, glasses on a chain, pointing accusatorily at a highlighted line in a massive three-ring binder labeled "POLICY". Pursed lips, eyebrow raised in disapproval. Background: a bulletin board covered in printed memos about proper password rotation and data-classification rules.

Flavor text: "Per policy, this violates policy."
```

### security_auditor
```
CHARACTER: "Security Auditor" — UNCOMMON / EXECUTIVE / ATK

A sharp-featured person in a black polo with a visitor badge, holding a clipboard with red ❌s all over it. Suspicious, unblinking gaze. A penetration-testing laptop hangs from a shoulder strap. Background: a server rack with some cables labeled "DO NOT UNPLUG" and one that's obviously unplugged.

Flavor text: "Your password is 'password1'. Obviously."
```

### helpdesk_veteran
```
CHARACTER: "Helpdesk Veteran" — UNCOMMON / HELPDESK / DEF

A grizzled older helpdesk worker with grey hair and a thick beard, arms crossed, ancient corporate polo with a MS-DOS-era logo. Deep laugh lines and deep scowl lines. A headset draped around the neck that's clearly decades old. Background: a wall covered in yellowing "User Appreciation Week" certificates, a framed ticket from 1997.

Flavor text: "I've seen things. Ticket #4. Ticket #5. All of them."
```

### build_engineer
```
CHARACTER: "Build Engineer" — UNCOMMON / DEVOPS / ATK

A sharp-eyed engineer gripping a laptop showing a beautiful green build pipeline, knuckles white from clutching it. Slightly manic grin. T-shirt says "IT BUILDS". Background: a CI/CD pipeline diagram on a whiteboard, stacks of monitors showing successful deploys, a small shrine with incense.

Flavor text: "GREEN. STAY GREEN. I BEG YOU."
```

### database_archaeologist
```
CHARACTER: "Database Archaeologist" — UNCOMMON / LEGACY / SUP

A scholarly figure in a vintage suit vest with a magnifying glass inspecting a printout of COBOL or SQL code. Tweed, wire-rim glasses, an expression of reverent curiosity. Background: dusty rows of binders labeled "SCHEMA V1.0 THROUGH V47.3", an ancient monochrome terminal softly glowing.

Flavor text: "This query has been running since 2003."
```

### agile_coach
```
CHARACTER: "Agile Coach" — UNCOMMON / EXECUTIVE / SUP

An enthusiastic mid-30s person in a bright polo, sleeves rolled up, pointing at a wall covered in sticky notes arranged in a Kanban board. Too-energetic smile. Carrying a coffee that says "VELOCITY" on the side. Background: a conference room with a big "STANDUP AT 9:30 SHARP" sign, a retrospective whiteboard with "WHAT WENT WELL / WHAT DIDN'T".

Flavor text: "Let's put a pin in that and circle back."
```

---

## RARE tier (purple frames)

### root_access_janitor
```
CHARACTER: "Root-Access Janitor" — RARE / ROGUE_IT / ATK

A janitor in dark coveralls with a terminal window literally welded into the chest of their outfit, green text scrolling. Holding a mop in one hand and a keyring of master keys + USB drives in the other. Knowing smirk. Background: a "SERVER ROOM - AUTHORIZED PERSONNEL ONLY" sign, the janitor clearly both authorized and unauthorized.

Flavor text: "Wait till you see what my mop can do."
```

### vp_of_vibes
```
CHARACTER: "VP of Vibes" — RARE / EXECUTIVE / SUP

A tanned person in a designer hoodie and expensive sneakers, wearing sunglasses indoors. Vague confident gesture with one hand, like they're explaining "synergy". Perfectly styled hair. Background: a modern open office with a stocked kegerator and a large screen showing a motivational quote nobody will read.

Flavor text: "Let's circle back on the vertical."
```

### keymaster_gary
```
CHARACTER: "Keymaster (Gary)" — RARE / HELPDESK / ATK

A middle-aged helpdesk veteran named Gary with a HUGE ring of keycards hanging from his belt, covering half his torso. Slight gold-tooth smile, uniform hat, wearing a faded polo that says "KEYMASTER". Background: locked server room door, a sign-in sheet nobody's used in years.

Flavor text: "I AM the Keymaster."
```

### rogue_dba
```
CHARACTER: "Rogue DBA" — RARE / ROGUE_IT / SUP

A shadowy figure in a black hoodie pulled low, lit only by terminal glow from below. Typing at a keyboard with a faint manic grin visible. A coffee that says "DROP TABLE users;" sits nearby. Background: a dark server room with one single red LED.

Flavor text: "TRUNCATE everything."
```

### oncall_warrior
```
CHARACTER: "On-Call Warrior" — RARE / DEVOPS / DEF

A warrior-stanced engineer holding a pager shield in one hand and a fire-extinguisher sword in the other. Armor made of keyboard keys and sticky notes. Determined, war-weary expression, helmet marked "PRIMARY". Background: a battlefield of fallen monitors and scorched server racks, dawn light breaking over a ruined data center.

Flavor text: "Third page tonight. I'm not even mad."
```

### cert_collector
```
CHARACTER: "Cert Collector" — RARE / HELPDESK / DEF

A confident mid-career person with a vest covered in certification patches (Cisco, AWS, CompTIA, VMware). Holding up a certification card like a trophy. Practiced LinkedIn-photo smile. Background: a wall of framed certificates, a bookshelf full of "EXAM GUIDE" textbooks.

Flavor text: "Ask me about my 47 certifications."
```

### blue_team_lead
```
CHARACTER: "Blue Team Lead" — RARE / DEVOPS / DEF

A focused security lead with tactical glasses, a headset, holding a tablet showing a network topology map with several nodes glowing red. Wearing a tactical polo with a unit patch. Calm under pressure. Background: a SOC (security operations center) with multiple engineers at monitors, a big screen showing an incident timeline.

Flavor text: "They're in. Contain. Eradicate. Recover."
```

---

## EPIC tier (gold frames, smoky atmosphere)

### the_post_mortem
```
CHARACTER: "The Post-Mortem" — EPIC / DEVOPS / SUP

A senior engineer standing in front of a whiteboard that's been filled with "FIVE WHYS" diagrams, timelines, and cause-effect arrows. Hair wild from running their hands through it. An expression of exhausted wisdom. A half-drunk coffee and a half-eaten bagel on a nearby stool. Background: an empty conference room at 10PM, other whiteboards faintly visible.

Flavor text: "Blameless. Mostly."
```

### midnight_pager
```
CHARACTER: "People Under the Stairs" — EPIC / Blond we think / Mother Rage ATK

A wild-eyed female engineer in pajamas and a bathrobe, standing in the front yard with a twisted ice tea in one hand, and a milwaukee beer in the other hand. A look of primal rage. Background: Sunny beach setting, with a raging river in the background. Kid and Dog building a sand castle. Friend zone friend helping building the sand castle.

Flavor text: "I was DREAMING. Of THIS."
```

### retired_mainframe_guru
```
CHARACTER: "Retired Mainframe Guru" — EPIC / LEGACY / SUP

An ancient sage with a long white beard, wire-rim glasses, wearing a vintage IBM engineer's short-sleeve dress shirt with a pocket protector. Arms raised in incantation over a green-screen terminal displaying COBOL code. Mystical runes (punch card holes) glowing around them.

Flavor text: "The old magic still works."
```

### shadow_it_operator
```
CHARACTER: "Shadow IT Operator" — EPIC / ROGUE_IT / ATK

A sleek figure in all black with a laptop covered in unauthorized stickers, working from a coffee shop table. AirPods, a burner phone, and an expression of quiet satisfaction. Background: visible Slack notifications, "What's this AWS account?" from their manager. A second monitor they definitely didn't get approved.

Flavor text: "IT approved? IT optional."
```

### tape_library_ghost
```
CHARACTER: "Tape Library Ghost" — EPIC / LEGACY / DEF

A spectral figure with semi-transparent flowing lab coat, holding aloft a glowing LTO tape like a relic. Eyes that are just faint blue lights. Wispy hair. Background: rows of old tape library racks extending into fog, a forgotten 1980s mainframe glowing dim blue.

Flavor text: "The backups remember what the cloud forgot."
```

---

## LEGENDARY tier (ornate gold frames, heavy detail)

### chaos_monkey
```
CHARACTER: "Chaos Monkey" — LEGENDARY / DEVOPS / ATK

An anthropomorphized monkey in a Netflix-style red jumpsuit, mid-leap, holding a massive "KILL -9" sword. Deranged grin, tail whipping behind. Explosions and falling servers visible in the background. Cyber-punk lighting. The chaos is gleeful.

Flavor text: "Random kill -9. No regrets."
```

### the_board_member
```
CHARACTER: "The Board Member" — LEGENDARY / EXECUTIVE / SUP

An imposing silver-haired executive in a bespoke three-piece suit, sitting at the head of a massive mahogany boardroom table. Golden fountain pen poised over a document marked "RESTRUCTURE". Piercing calm expression. A Rolex visible. Background: a wall-to-wall window showing a city skyline at golden hour, portraits of past board members watching silently.

Flavor text: "We'll sunset the division. Q3."
```

---

## LEGENDARY — Raid Bosses (ornate gold + monster scale)

### raidboss_legacy_colossus
```
CHARACTER: "Legacy Colossus" — LEGENDARY / LEGACY / DEF — RAID BOSS

A monumental stone-and-steel behemoth made of stacked mainframe units, punch-card armor, and tangled ethernet cables like veins. Glowing green terminal screens for eyes. Towering over a tiny human figure in the foreground for scale. Background: a vast underground server cathedral, cable-stalactites hanging from the ceiling.

Flavor text: "Thirty years of accumulated tech debt, given form."

CRITICAL: this is a RAID BOSS — it should feel enormous and mythic, not like a regular hero. Frame accordingly.
```

### raidboss_c_suite_hydra
```
CHARACTER: "C-Suite Hydra" — LEGENDARY / EXECUTIVE / ATK — RAID BOSS

A multi-headed corporate hydra: each head wears a different expensive suit (CEO, CFO, CTO, COO, CMO). Each head is giving a different powerpoint presentation. Golden scales forged from quarterly reports. Background: a corporate lobby with polished marble and a "Q4 ALL-HANDS" banner torn across it.

Flavor text: "Cut one department. Two more take its place."

CRITICAL: this is a RAID BOSS. Massive scale, 5 heads minimum, framed as a monster.
```

### raidboss_chaos_dragon
```
CHARACTER: "Chaos Dragon" — LEGENDARY / DEVOPS / ATK — RAID BOSS

A massive dragon with scales made of fragmented deployment-pipeline logos, smoke and embers pouring from its mouth with Slack notifications visible in the smoke ("P1: PROD IS DOWN"). Eyes like glowing red alert icons. Wings composed of Kubernetes cluster diagrams. Background: a city skyline of server farms on fire, cables dangling like severed power lines.

Flavor text: "PROD. IS. DOWN."

CRITICAL: RAID BOSS — dragon scale, monster framing, not a humanoid.
```

---

## MYTH tier (iridescent prismatic frames with red/gold/blue color-shift)

### tbfam
```
CHARACTER: "GemGem" — MYTH / EXECUTIVE / ATK

"The Shark" — a mythic CEO figure, half dog half, sharply dressed in an impossibly tailored obsidian-black suit with subtle prismatic threads catching the light. Piercing eyes that shift between smokey red, liquid gold, and electric blue — clearly not mortal. Fins on the side, razor sharp teeth, shark tail with fur on it, shark body with fur on it. 

Pose: The dog shark is in a field littered with balls off all sizes.  Latent fury.

Rarity frame: IRIDESCENT PRISMATIC, holographic border that shifts between red, gold, and blue depending on viewing angle. More ornate than LEGENDARY — this is a tier above. Maybe subtle geometric mandala patterns in the border.

Flavor text: "Ball BALL Ball"

CRITICAL: This is the FIRST MYTH-tier hero. The frame must feel distinct from LEGENDARY — supernatural, otherworldly, limited-edition. Do not default to gold-on-dark; lean into the prismatic/holographic treatment.
```

---

## Workflow reminders

1. New ChatGPT chat per character.
2. Paste **shared style lock** → wait for acknowledgment.
3. Paste ONE character brief.
4. Download the result PNG.
5. Rename to `<hero_code>.png` matching exactly (e.g. `sre_on_call.png`).
6. Drop into `app/static/heroes/cards/`.
7. Post the path back in chat — I'll auto-crop the bust and commit.

If ChatGPT drifts in style across characters, go back to the first card (Jaded Intern / the Ticket Gremlin COMMON) and re-paste it as a reference with the next brief.
