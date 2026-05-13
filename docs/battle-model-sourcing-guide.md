# Battle Model Sourcing Guide (Free + Paid)

Last updated: 2026-05-13.

## Goals
- Keep runtime light enough for mobile/web.
- Avoid licensing traps for commercial release.
- Maintain animation consistency with our turn-based combat event model.

## Recommended free sources (start here)
1. **Quaternius** (best current fit)
   - Good for stylized low-poly RPG characters and props.
   - Commercial-friendly with straightforward terms.
   - Purchase/Download: https://quaternius.com/ (many packs are free; paid bundles available).
2. **KayKit (Kenney/Kay Lousberg style packs if licensed correctly)**
   - Great readability on small screens.
   - Ensure we only use packs with explicit commercial permission for redistribution inside games.
3. **Kenney assets**
   - Excellent free baseline for props/UI/world set dressing.
   - Purchase/Download: https://kenney.nl/assets

## Recommended paid sources (production polish)
1. **Synty Store / Polygon packs**
   - Strong consistency, production-ready libraries.
   - Best when we need a full environment + character ecosystem quickly.
   - Purchase: https://syntystore.com/
2. **Unity Asset Store (for source files even if engine differs)**
   - Use as raw mesh/animation source, then export to glTF pipeline.
   - Purchase: https://assetstore.unity.com/
3. **FAB (Epic/Sketchfab ecosystem)**
   - Very broad catalog; quality varies, license screening is critical.
   - Purchase: https://www.fab.com/

## Licensing checklist (must pass before import)
- Commercial use explicitly allowed.
- Redistribution inside shipped game binaries allowed.
- No viral/share-alike terms that infect proprietary code/assets.
- Attribution requirements documented in `docs/ART_NEEDS.md`.
- Source receipt URL + invoice stored in internal asset ledger.

## Technical import standards
- Preferred format: **glTF/GLB**.
- Character triangle budget target: **5k–25k tris** for gameplay view.
- Texture budget target: **1k** default, **2k** for hero showcase only.
- Animation naming normalized (`Idle`, `Run`, `Hurt`, `Death`, `Attack`, class-specific specials).
- Draco compress before committing to repo.

## Free vs paid strategy
- **Free-first for prototyping**: Quaternius + Kenney to validate gameplay readability and animation timing.
- **Paid for launch polish**: selectively replace hero roster and key environments with Synty/FAB assets while retaining rig compatibility.
- Prioritize spending on:
  1. Hero silhouettes (combat readability)
  2. Bosses
  3. Signature stage biomes

## Recommendation for hero-proto now
- Keep Quaternius as the primary baseline for battle heroes.
- Use paid packs only for high-visibility content (bosses, endgame arenas, marketing screenshots).
- Do not mix too many visual styles in the same battle scene.
