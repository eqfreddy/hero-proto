# keldev-finish-brain — open questions (Kel to answer later)

Cutoff file for the System Integrity / Crash / "Deleted" / Burnout brainstorm.
Full design draft: `battlebuttonsets.md`.

**Resolved 2026-05-28** (folded into the design doc): weakness axis = pure Faction
(no universal heroes), crash = flavored debuffs from the start, Deleted bonus = all four
(Burnout shed + loot + style stat + faster anim), finisher = inside the turn clock w/
auto-resolve. All balance numbers got starting defaults in `battlebuttonsets.md` §6.

What's left below is creative / art / a couple of confirms. Answer inline; none of it
blocks writing the implementation plan, so we *can* proceed and slot these in at build time.

---

## Creative vetoes (brand voice = deadpan, dry, occasionally morbid)
1. **"DELETED" callout** — text treatment + SFX. Draft: glitchy monospace / CRT flicker, dry
   sound (recycle-bin "empty" chime, or an `rm -rf` keystroke clack). Veto / redirect?
2. **Recycle-bin art** — what is the bin? Draft options: Windows-trash parody, a literal
   `rm -rf` terminal prompt, a server-rack shredder, a trash chute. Pick a lane?
3. **Crash VFX** — what a Crashed enemy looks like. Draft: bluescreen / glitch flicker /
   sparks. Battle3D reaction treatment?

## Confirms (I picked a default; override if you disagree)
4. **Burnout persistence** — defaulted to battle-scoped reset. OK, or carry a little fatigue
   between stages as a meta layer?
5. **Bin spawn area** — defaulted to "random within a safe zone" (off edges + action bar).
   OK, or truly anywhere (harder)?
6. **Arena timing** — defaulted to interactive-battles-first, arena inherits later. Any reason
   to bring arena forward given a client-side finisher in PvP (fairness)? Leaning: keep arena
   on the auto-resolve path so there's no client-trust surface.

---

*Next step once you're ready: writing-plans skill → implementation plan.
Build agents (from the roadmap): feature-dev:code-explorer → system-architect →
backend-developer → frontend-engineer → qa-engineer + test-runner.*
