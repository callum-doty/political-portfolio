# Political Portfolio: Dynamic Campaign Capital Allocation

A three-paper research program that treats U.S. House campaign spending as a
constrained capital allocation problem: estimate how much a marginal dollar
is actually worth in each race, test whether the DCCC allocated its 2022/2024
budgets efficiently, and derive when — not just where — that money should be
deployed.

This repository is the entire empirical pipeline behind all three papers:
data ingestion, estimation, optimization, validation, and the sequential
decision layer, plus the drafts and a full dated audit trail of every
correction made along the way.

> **Numbers in this README are illustrative, not authoritative.** This
> project has an unusually aggressive self-correction history — headline
> figures have moved multiple times as real bugs were found and fixed (see
> [FINDINGS.md](FINDINGS.md)'s changelog-style entries). **[FINDINGS.md](FINDINGS.md)
> is the single current source of truth for results.** Treat anything below
> as "what the model was designed to show," not "the final number."

---

## The framework, in one picture

```
Historical Data (FEC, MIT elections, Cook PVI, Census CVAP)
      │
      ▼
Estimate μ(D), σ          ← margin response surface + heteroskedastic uncertainty
      │
      ▼
Persuasion Ceiling         ← regularizes the response surface against
      │                        unbounded extrapolation at near-zero floors
      ▼
Win Probability Φ(μ/σ)
      │
      ▼
Immediate Reward           ← Expected Seats = Σ Φ(μᵢ/σᵢ)
      │
      ▼
Bellman Equation V(Xₜ)     ← sequential, receding-horizon allocation
      │
      ▼
Θ = V_wait − V_deploy       ← Longstaff–Schwartz value of retained flexibility
      │
      ▼
Optimal Dynamic Spending Policy
```

Three layers, each answering a different question, each depending on the
correctness of the one beneath it:

| Layer | Question | Paper | Core code |
|---|---|---|---|
| **1. Calibrated response model** | How much does a marginal dollar move a race's win probability? | Paper I ([`docs/paper1_draft.md`](docs/paper1_draft.md)) | `src/backtest/estimation/`, `src/backtest/model/` |
| **2. Static allocation optimizer** | Given that model, how should a fixed budget be spread across races *right now*? | Paper I | `src/backtest/optimizer/` |
| **3. Dynamic decision layer** | Given that optimizer, *when* should capital actually be committed over a multi-month cycle? | Papers II & III ([`docs/paper2_draft.md`](docs/paper2_draft.md), [`docs/paper3_draft.md`](docs/paper3_draft.md)) | `src/backtest/dynamic/`, `scripts/solve_bellman_lsm*.py` |

Layer 1 asks whether the model is *right*. Layer 2 asks what the model
*implies* at one point in time. Layer 3 asks whether *now* is even the right
time to act on that implication. Keeping them separate is what makes each
piece independently testable — Paper I's static optimizer is unaffected by
anything in Paper III, and Paper III's Θ can be re-derived without
re-deriving the underlying valuation model at all.

---

## Repository layout

```
config.yaml                  # every model/pipeline parameter — nothing is hardcoded
pyproject.toml                # dependencies, pytest/ruff config

src/backtest/
  types.py                    # shared dataclasses (RaceRecord, ModelOutputs, SigmaModel, ...)
  config.py                   # typed accessors over config.yaml
  data/                       # loaders: FEC, MIT elections, Cook PVI, Census CVAP, incumbency
    fec.py, elections.py, pvi.py, cook.py, census.py, incumbency.py, universe.py
  estimation/                 # historical-panel estimation (2012–2022)
    beta_rc.py                #   β_RC — repeat-challenger spending elasticity (Levitt 1994 design)
    open_seat.py              #   Bayesian shrinkage of β_RC → open-seat elasticity
    sigma.py                  #   heteroskedastic σᵢ model + Duan smearing retransformation
  model/                      # the spending response surface (Layer 1)
    margin.py                 #   μᵢ(D) — fitted expected margin
    win_prob.py                #   P_win = Φ(μ/σ), marginal seat gain (MSG)
    ceiling.py                  #   persuasion ceiling — regularizes μ against unbounded extrapolation
    budget.py                    #   BUDGET_2026 — CPI-inflated live-cycle party budget
  optimizer/
    allocator.py               # LP (γ>0) + nonlinear SLSQP (γ=0) portfolio optimizers (Layer 2)
  comparison/                  # DCCC-vs-model efficiency tests
    efficiency.py, benchmark.py, uncertainty.py
  validation/
    gates.py                   # 6 gates that must pass before interpreting any result
  outputs/
    tables.py, charts.py       # per-race CSV, efficiency-frontier PNG
  dynamic/                    # Layer 3 — Paper II/III sequential architecture
    state.py                   #   X_t — time-indexed campaign state
    updates.py                  #   f(X_t) — EMA state-update operator
    ledger.py                    #   B_t = L_t + F_t — committed vs. deployable capital
    horizon.py                    #   receding-horizon (MPC-style) optimizer loop
    simulate.py                    #   one-step-ahead historical replay harness (never closed-loop)
    periods.py                      #   reporting-period calendar (biweekly / FEC-quarterly)
    timing.py                        #   deployment-timing diagnostic vs. DCCC's actual behavior

scripts/                      # pipeline entry points + one-off analysis/figure scripts
tests/                        # 341 tests, synthetic fixtures, no disk I/O required
docs/                         # paper drafts + derivations + data catalog + audit log
data/                         # raw + processed (see Data below)
outputs/                      # generated tables, figures, JSON results
FINDINGS.md                   # living results log — start here for current numbers
```

---

## Setup

Requires Python ≥3.11.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

`pip install -e ".[dev]"` installs the package (`backtest`, from `src/`) plus
`pytest`, `ruff`, `black`, and Jupyter. Core runtime dependencies: `pandas`,
`numpy`, `scipy`, `statsmodels`, `cvxpy`, `matplotlib`, `seaborn`, `pyyaml`.

---

## Data

`data/raw/` and `data/processed/` are committed to this repository
intentionally (see `.gitignore`'s comment) — so that any drift between the
estimation artifacts and FINDINGS.md's reported numbers is visible via
`git diff` rather than silently going stale. The one exception is
`data/raw/all_committee_transactions/`, which holds multi-GB FEC bulk files
that exceed GitHub's size limits; that directory is local-only and
regenerated via `fetch_data.py`.

If you're starting from a clean checkout with only `data/raw/` populated (or
need to refresh it), sources are:

| Source | Content | Fetch |
|---|---|---|
| FEC | Candidate disbursements, committee IEs, coordinated expenditures | `scripts/fetch_data.py` (needs a free [FEC API key](https://api.open.fec.gov/developers)) |
| Census | CVAP (citizen voting-age population) | `scripts/fetch_data.py` (needs a free [Census API key](https://api.census.gov/data/key_signup.html)) |
| MIT Election Lab | Historical House results | Manual download — [Harvard Dataverse](https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/IG0UN2), place at `data/raw/mit_elections/1976-2024-house.tab` |
| Cook Political Report | PVI + race ratings | Manual download (proprietary), place at `data/raw/cook_pvi/` |

```bash
python scripts/fetch_data.py --fec-api-key YOUR_KEY --census-api-key YOUR_KEY
# No registered key yet? candidate-committee-only data still works:
python scripts/fetch_data.py --skip-party-spend
```

Full schema-level documentation of every raw and processed file lives in
[`docs/data_catalog.md`](docs/data_catalog.md).

---

## Running the pipeline

### 1. Estimation (Layer 1) — fit the response model on 2012–2022

```bash
python scripts/run_estimation.py
```

Writes `beta_rc.json`, `margin_model_coef.json`, `sigma_model.json`,
`open_seat_calibration.json` to `data/processed/`. For the 2022
out-of-sample validation, refit on data through 2020 only:

```bash
python scripts/run_estimation.py --panel-end-cycle 2020
# writes to data/processed_oos_2020/
```

### 2. Static backtest (Layers 1–2) — the headline efficiency test

```bash
python scripts/run_backtest.py --cycle 2024
python scripts/run_backtest.py --cycle 2022 --processed-dir data/processed_oos_2020
```

Runs validation gates, the LP/nonlinear optimizer across a (γ, cap) grid,
β_RC uncertainty propagation (K=1000 draws), the Spearman efficiency test,
and writes per-race/aggregate tables + an efficiency-frontier chart to
`outputs/`. Useful flags: `--skip-uncertainty` (fast iteration), `--eta`
(adversarial NRCC-response sensitivity).

### 3. Dynamic backtest (Layer 3) — one-step-ahead historical replay

```bash
python scripts/run_dynamic_backtest.py --cycle 2024
```

Re-runs Paper I's pipeline period-by-period against real historical spend
snapshots only (never a closed-loop rollout — see `dynamic/simulate.py`'s
docstring for why that distinction is load-bearing), and compares the
sequential recommendation against DCCC's actual deployment timing.

### 4. Θ — the value of waiting (Paper III)

```bash
python scripts/solve_bellman_lsm.py                       # binary deploy-now vs. hold, live 2026 state
python scripts/solve_bellman_lsm_continuous_phi.py         # continuous deployment-fraction generalization
python scripts/solve_bellman_lsm_1yr_counterfactual.py     # horizon-sensitivity counterfactual
```

Longstaff–Schwartz backward induction over simulated campaign paths (opponent
reaction η, national-environment drift, idiosyncratic noise, candidate
spend "trickle"), against three η-calibration scenarios. Output:
`outputs/theta_schedule*.json`.

### 5. Live 2026 cycle

```bash
python scripts/fetch_polling.py            # generic ballot, diagnostic only
python scripts/fetch_live_ies.py           # real-time FEC IE ingestion
python scripts/plot_2026_live_allocation.py
```

---

## Testing

```bash
python3 -m pytest tests/ -v            # all 341 tests
python3 -m pytest tests/test_model.py  # one file
python3 -m pytest -k "TestGate"        # by keyword
```

All tests run against synthetic fixtures — no disk I/O, no dependency on
`data/raw/` being populated. Coverage spans every module in `src/backtest/`:
estimation, the margin/ceiling/win-prob model, the LP and nonlinear
optimizers, all 6 validation gates, the comparison/efficiency tests, and the
full `dynamic/` sequential-decision package (state updates, the capital
ledger, the receding-horizon loop, and the Bellman LSM solver).

---

## Design conventions

- **Nothing is hardcoded.** Every model and pipeline parameter lives in
  [`config.yaml`](config.yaml), read through typed accessors in
  `src/backtest/config.py`.
- **Historical panel (2012–2022) is fit once and frozen** before touching
  2024/2026 data — β_RC, σᵢ, and the margin-model coefficients are
  out-of-sample by construction with respect to the cycle being evaluated.
- **`dynamic/` depends on the static pipeline, never the reverse** — the
  sequential architecture re-uses Paper I's `compute_outputs_batch` and
  `optimize_nonlinear` unmodified rather than re-deriving them.
- **Validation gates, not outcome checks.** `validation/gates.py`'s 6 gates
  test model integrity (data completeness, R², σ ordering, MSG sign,
  optimizer convergence, Brier calibration) — passing them means the model
  is well-formed, not that its conclusions are correct.
- **Corrections are recorded, not silently overwritten.** `FINDINGS.md` and
  `docs/theta_followup_plan.md` keep a dated log of every bug found and
  fixed, with before/after numbers — treat them as the audit trail, not just
  a results summary.

---

## Documentation map

| Document | Contents |
|---|---|
| [`FINDINGS.md`](FINDINGS.md) | **Current results, dated correction log — start here.** |
| [`docs/paper1_draft.md`](docs/paper1_draft.md) | Paper I: static marginal-seat-gain model + DCCC efficiency test |
| [`docs/paper2_draft.md`](docs/paper2_draft.md) | Paper II: sequential/receding-horizon allocation architecture |
| [`docs/paper3_draft.md`](docs/paper3_draft.md) | Paper III: state-transition model + the Θ (value-of-waiting) result |
| [`docs/theta_followup_plan.md`](docs/theta_followup_plan.md) | Detailed Θ implementation log and every correction to it |
| [`docs/full_derivation.md`](docs/full_derivation.md) | Complete mathematical derivation, section-by-section |
| [`docs/data_catalog.md`](docs/data_catalog.md) | Every raw/processed data file: schema, source, known gaps |

---

## Status

Both the static (Paper I) and dynamic (Paper II/III) layers are implemented,
tested, and reproducible end-to-end from the committed data. All 341 tests
pass. Known open items and scope boundaries are tracked in
`docs/theta_followup_plan.md` §12.5 and flagged inline throughout the code
where an estimate is applied outside the scope it was calibrated for.
