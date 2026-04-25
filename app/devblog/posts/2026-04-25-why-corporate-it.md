---
title: Why we made a gacha game about corporate IT
date: 2026-04-25
summary: Most gacha games are fantasy. We made one about the people who get paged at 3 AM.
author: hero-proto dev
---

There are roughly 10,000 gacha RPGs. Almost all of them are about elves, mechs, anime swordsmen, or anthropomorphic animals in armor. The genre's tropes are so calcified that "knight in plate mail with a glowing sword" is what your brain renders when someone says *gacha hero*.

We made one about helpdesk veterans, retired mainframe gurus, and consultants holding pitch decks like weapons.

## The actual gameplay isn't a joke

It's a turn-based RPG with status effects, gear sets, signature specials, guild raids, async PvP, and a five-tier rarity system with honest pity. The systems work. We have 320+ tests, Postgres CI, two-factor auth, and account deletion that actually deletes your account.

What's a joke is the *aesthetic*. The Ticket Gremlin chatters with a paper ticket between its teeth. The Sysadmin clutches an ancient mechanical keyboard and won't let you near production. The Founder's flavor text reads "I'm not here to build a company. I'm here to build an empire." None of this is novel as workplace satire — but it's basically untouched in the gacha genre.

## Why the gacha genre needs this

The honest truth: most gacha games are predatory. Hidden rates, FOMO timers on power, banner-exclusive heroes that obsolete the previous meta, "auto-battle" sold as a baseline feature you can't escape. The people who play them know they're being played.

We can't fix the genre. But we can ship one example of how it works without the dark patterns:

- **Visible pity counter**, fixed pull rates, no hidden state.
- **Cosmetic + QoL monetization only.** Path of Exile 2 model. Money buys frames and presets, never raw stat power.
- **Free pulls from the tutorial + daily login.** First summon is essentially free.
- **Account deletion is one click** and actually purges your data.
- **No advertising IDs**, no cross-site tracking, no data sales.

If players notice and like it, great. If they notice and we're slightly more transparent than the predatory ones, also great.

## What's next

Phase 1 just shipped: the new-player flow, the roster grid, the dedicated Summon tab, team presets, the starter pack. Phase 2 is hero detail depth, story chapters, and analytics. Phase 3 is the combat-control overhaul (target selection, mana, animated battle actors via Rive). Phase 4 is mobile store submission via Capacitor.

The world is satire of corporate IT life, but the people in it care about each other. The Sysadmin is grumpy because he's tired, not because he's a villain. The Jaded Intern is dead-eyed because he's been told one too many times that "we're a family here." The Founder is the actual villain, but the kind of villain you laugh at.

Patch notes for everything ship in [/changelog](/changelog), automatically pulled from git. Public roadmap is at [/roadmap](/roadmap).

Try the alpha at [/](/). Star the [GitHub repo](https://github.com/eqfreddy/hero-proto). Tell one IT person you know.
