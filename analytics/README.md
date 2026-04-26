# Balance + analytics notebooks

Jupyter notebooks for tuning numbers without touching production. Each notebook
imports from `app/` directly, so changes to `seed.py` / `combat.py` / `gacha.py`
flow through to the next notebook re-run.

## Setup

```bash
# Install the optional analytics dependency group:
uv sync --extra analytics

# Launch Jupyter:
uv run jupyter lab analytics/
```

## Notebooks

| File | Question it answers |
|---|---|
| `gacha_ev.ipynb` | What's the expected value of a pull? Distribution of EPIC+ pulls per 100 players? Where does the pity floor sit? |
| `combat_dps.ipynb` | DPS curves per role at level N. Time-to-kill heatmap by team comp. |
| `arena_convergence.ipynb` | How many matches until a fresh account converges to "true" rating? |
| `stage_difficulty.ipynb` | Win-rate prediction per stage given a representative team. |

## Conventions

- **Read-only against the codebase.** Notebooks import from `app/` but never
  write to a real DB. Use the in-memory simulators or hand-built fixtures.
- **Output goes in the notebook + a PNG to `analytics/output/<slug>.png`** so
  changes are reviewable in PRs without re-running.
- **Tune balance via `app/seed.py`, `app/gacha.py`, `app/combat.py` —
  not the notebooks.** Notebooks observe; they don't drive.
- **Imports are smoke-tested.** `tests/test_balance_notebooks.py` mirrors the
  symbols each notebook imports so a rename in `app/` breaks a fast unit
  test instead of a notebook nobody opens until balance day.

## Re-running

```bash
uv run jupyter nbconvert --to notebook --execute --inplace analytics/gacha_ev.ipynb
uv run jupyter nbconvert --to notebook --execute --inplace analytics/combat_dps.ipynb
uv run jupyter nbconvert --to notebook --execute --inplace analytics/arena_convergence.ipynb
```

Outputs (committed):

- `output/gacha_ev_by_rarity.png` — per-pull probability bar chart from `app.gacha.RATES`
- `output/gacha_first_epic.png` — pulls-to-first-EPIC histogram across 5,000 simulated players
- `output/combat_dps_proxy_lv30.png` — DPS proxy by hero at level 30
- `output/arena_convergence.png` — rating trajectories at 4 true-skill bands
