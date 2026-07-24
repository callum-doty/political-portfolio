# DCCC Spending Efficiency — Process & Findings

**Project:** Political Portfolio Backtest  
**Cycles:** 2024 (primary) and 2022 (out-of-sample validation)  
**Date:** June 2026

---

> **✓ Reconciled 2026-07-24 (persuasion ceiling implementation).** The
> +13.24-seat 2024 headline (2026-07-23c, below) was investigated directly on
> your suspicion that it looked too large — it was not a linear-vs-nonlinear
> bug; the true nonlinear SLSQP optimizer was genuinely computing it. The real
> cause: the σ-model fix (2026-07-23b) removed an *accidental* suppressor.
> Before that fix, an understated σᵢ kept every near-zero-candidate-floor
> race's win probability pinned near 0 regardless of spending, which happened
> to mask the log-ratio spending term's unbounded gradient as D→0
> (`∂μ/∂D ∝ 1/D`). Once σᵢ was corrected, the optimizer began extrapolating
> that unbounded gradient into Safe-tier races with near-zero historical
> support for any such effect — 81% of the +13.24 gain came from races
> spending under $500k, and Safe-tier races absorbed 45% of the recommended
> party budget.
>
> **Fix: a persuasion ceiling**, `src/backtest/model/ceiling.py`, wired into
> both `model/win_prob.py` (single-race path) and `optimizer/allocator.py`
> (the vectorized optimizer hot path, inherited automatically by
> `comparison/benchmark.py`). It caps the achievable margin shift from a
> race's own candidate-only floor at `C_i = c_max · 4·Φ₀·(1−Φ₀)`, where
> `Φ₀ = Φ(μ_floor/σᵢ)` is the race's win probability at that floor (no party
> money) — a parabola peaking at `c_max` for a true toss-up and shrinking to
> ~0 at either extreme. This is a regularization prior, not a behavioral
> claim: the model should not infer a spending effect larger than a multiple
> of the race's own already-estimated uncertainty, scaled by how persuadable
> its current state suggests it is. `c_max = 10.0` (config.yaml), chosen from
> an 8-point robustness sweep {3,5,7,10,15,20,30} — Safe-tier party-budget
> share falls smoothly across the whole range, with no fragile threshold; see
> §7.3b below for the full derivation and calibration evidence.
>
> **Two further, genuinely independent bugs surfaced while wiring this in**
> (both real, both fixed at the source, neither specific to the ceiling):
> 1. `optimizer/allocator.py`'s LP objective (`optimize()`, used by γ>0 runs
>    and β_RC uncertainty propagation) passed raw MSG coefficients
>    (~1e-7–1e-8 magnitude) straight to SCIPY's linprog. At that scale the
>    solver returned a numerically degenerate vertex — reporting
>    `status="optimal"` while funding whichever race happened to be last in
>    the array, independent of actual MSG ranking. Fixed by normalizing the
>    objective before solving (`msg_lp = msg / max(|msg|)`), the same fix
>    `optimize_nonlinear()` already needed for SLSQP (its `SCALE` constant).
> 2. `data/fec.py`'s ballot-matching filter (`_ballot_last_names()` /
>    `load_candidate_disbursements()`) dropped 2024 WA-03's actual incumbent,
>    Marie Gluesenkamp Perez ($11.9M spent), because her compound surname
>    ("GLUESENKAMP PEREZ, MARIE" in FEC data) didn't match MIT's
>    last-word-only convention ("PEREZ"). The next-highest D candidate
>    ($7,587.86) was silently used as WA-03's candidate floor instead —
>    caught immediately by the new MSG-sign validation gate, which requires
>    `msg_i > 0` for every competitive race. Fixed by matching on the last
>    *word* of both names, not the full pre-comma FEC segment.
>
> **Fresh headline numbers (2026-07-24 rerun, all 6 validation gates pass on
> both cycles, including the previously-failing MSG-sign and
> optimizer-convergence gates once the fixes above landed):**
>
> | | 2024 (primary) | 2022 (OOS) |
> |---|---|---|
> | Spearman ρ (competitive) | **−0.809** (p<0.0001) | **−0.847** (p<0.0001) |
> | E[Seats] DCCC observed | 215.12 | 213.37 |
> | E[Seats] model optimizer | 217.94 | 216.59 |
> | Seat gain | **+2.83** | **+3.22** |
> | Brier (model / Cook) | 0.0312 / 0.0364 | 0.0360 / 0.0340 |
> | Concentration cap gap (uncapped − 5% cap) | +0.000 | +0.000 |
> | Safe-tier party-budget share | **9.0%** (was 45%) | — |
>
> These replace every 2026-07-23c number below with something structurally
> different, not just numerically smaller: the model's advantage over DCCC
> shrinks by roughly a factor of 4–5, but the *qualitative* finding survives
> and, if anything, is more credible for surviving — the model still beats
> DCCC, Null, and Cook-implied in both cycles, the Spearman efficiency finding
> is essentially unchanged (ρ actually strengthens in 2022), and the gain is
> now driven by real reallocation toward Toss-Up/Lean races rather than by an
> artifact of near-zero-floor extrapolation. `docs/paper1_draft.md`,
> `docs/paper2_draft.md`, and `docs/paper3_draft.md` have all been rewritten
> to match, following this document's own "was X" audit-trail convention.

---

> **✓ Reconciled 2026-07-23c (codebase audit).** Every number and table in this
> document has been rewritten to match the fixed pipeline described below —
> this is no longer a "numbers pending" flag, it's the change log for what
> moved and why. Three bugs were fixed and the full pipeline (estimation +
> both backtests) was rerun end-to-end against corrected data:
> 1. **NRCC coordinated-expenditure data was fetched under the wrong FEC
>    committee ID for every cycle 2012–2026** — the old ID (`C00075473`)
>    belonged to an unrelated corporate PAC, not the NRCC (verified against
>    fec.gov). This silently zeroed NRCC coordinated spend in `R_total` across
>    the entire historical panel. **Re-fetched with the corrected ID
>    (`C00075820`) for all 8 cycles** — `coordinated_expenditures_{cycle}.csv`
>    now contains real R-side data for every cycle (HMP/CLF IDs in
>    `scripts/fetch_live_ies.py` were also wrong and are now corrected).
> 2. The heteroskedastic σᵢ model had two bugs (wrong μ̂ for open-seat
>    residuals; missing log-normal retransformation correction) — both fixed
>    in `src/backtest/estimation/sigma.py`.
> 3. The LP/QP optimizer's `expected_seats` diagnostic was missing a baseline
>    subtraction, inflating every γ>0 point on the efficiency frontier — fixed
>    in `src/backtest/optimizer/allocator.py`.
>
> **Fresh headline numbers (2026-07-23 rerun, all 6 validation gates pass on both cycles):**
>
> | | 2024 (primary) | 2022 (OOS) |
> |---|---|---|
> | Spearman ρ (competitive) | **−0.789** (p<0.0001) | **−0.707** (p<0.0001) |
> | E[Seats] DCCC observed | 217.08 | 215.47 |
> | E[Seats] model optimizer | 230.31 | 228.09 |
> | Seat gain | **+13.24** | **+12.61** |
> | Brier (model / Cook) | 0.0300 / 0.0364 | 0.0350 / 0.0340 |
> | Concentration cap gap (uncapped − 5% cap) | +0.000 | +0.000 |
>
> These are **materially different** from every number this document, `docs/paper1_draft.md`,
> and `docs/paper2_draft.md` previously reported — both ρ and the seat-gain
> estimate moved substantially (stronger correlation, larger gain) once σᵢ and
> the optimizer diagnostic were corrected, and several qualitative readings
> reversed outright (which cycle shows the stronger ρ; whether the model beats
> Cook's calibration in 2022; the sign of the Likely R by-category correlation).
> All three documents, plus `docs/paper3_draft.md`'s Θ-schedule figures, have
> now been rewritten section-by-section to match, following this document's
> own established "was X" audit-trail convention rather than silently
> overwriting prior values.
>
> **One open item, not chased further per your direction:** the σᵢ ordering
> check (σ_open > σ_challenger > σ_incumbent) now fails in all 5 PVI bins on
> both cycles — before the μ̂ fix it likely passed only because open-seat
> residuals were being computed against the wrong (non-open-seat) predicted
> margin, inflating their apparent variance. Also worth knowing:
> `validation/gates.py`'s σ-ordering gate threshold is `>= 0% of PVI bins`,
> which is vacuously always true — it did not catch this because it cannot
> ever fail. Neither was touched, per your call to flag rather than chase.

---

## Table of Contents

1. [Research Question](#1-research-question)
2. [Data Sources](#2-data-sources)
3. [Universe Construction](#3-universe-construction)
4. [Model Specification](#4-model-specification)
5. [Estimation](#5-estimation)
6. [Backtest Methodology](#6-backtest-methodology)
7. [Findings](#7-findings)
   - [7.2b Permutation Tests](#72b-permutation-tests-added-2026-07-22)
   - [7.3b Why the number moved: the persuasion ceiling](#73b-why-the-number-moved-the-persuasion-ceiling)
8. [Cross-Cycle Validation (2022)](#8-cross-cycle-validation-2022)
9. [Actionability Assessment](#9-actionability-assessment)
   - [9.4 Adversarial Response Sensitivity (η Model)](#94-adversarial-response-sensitivity-η-model)
   - [9.5 Concentration Cap Gap (§4.6)](#95-concentration-cap-gap-46)
   - [9.6 Open-Seat Spending Elasticity (§8.3)](#96-open-seat-spending-elasticity-83)
10. [Limitations](#10-limitations)
11. [Output Files](#11-output-files)

---

## 1. Research Question

Does the DCCC allocate its independent expenditure budget efficiently across House races, and by how much could a model-informed targeting strategy improve expected seat outcomes?

The core hypothesis is that DCCC concentrates spending where marginal returns are lowest — i.e., in already-safe or high-probability races — rather than in competitive races where an additional dollar shifts win probability most. This is tested quantitatively using a marginal seat gain (MSG) framework derived from a structural vote-share model.

---

## 2. Data Sources

| Source | Contents | Years |
|--------|----------|-------|
| FEC bulk disbursements | Candidate and party committee spending by district | 2012–2024 |
| FEC independent expenditures | Comprehensive IE data (all filers) | 2024 |
| MIT Election Lab | House election results by district | 2012–2024 |
| Cook Political Report | PVI, race ratings (Safe/Likely/Lean/Toss-Up) | 2024 |
| RealClearPolitics | Generic ballot average (final pre-election) | 2024 |

**Generic ballot (GB) used:** −1.2 (D − R, final pre-Nov-5 2024 RCP average).

**Key FEC data note:** Total Democratic spending is decomposed into two components:
- **Candidate disbursements** — money raised and spent by the candidate's own committee. This is not controllable by the DCCC.
- **Party coordinated + IE** — money the DCCC controls directly. This is the budget the optimizer targets.

---

## 3. Universe Construction

Starting from all 2024 House contests, filters applied sequentially:

| Filter | Remaining |
|--------|-----------|
| All districts | 459 |
| Minimum total spend ≥ $100,000 | 444 |
| Alaska excluded (ranked-choice incompatible) | 443 |
| Districts with no PVI dropped | **433** |

**Final universe: 433 races.** (Table order corrected 2026-07-23, codebase audit: the previous row order and an extra "449 / at-large-dropped" intermediate step didn't match the actual filter sequence in `data/universe.py` — spend filter runs first, then the state exclusion, then the PVI drop; the final count was always right, only the path there was misdescribed.)

Competitive races (used for MSG efficiency tests): 53 races rated Toss-Up, Lean D, or Lean R by Cook.

Budget summary:
- Total Democratic spending: **$1,291,230,252**
- Candidate spending (floor, not DCCC-controlled): **$826,213,565** (64%)
- DCCC party-controlled budget: **$465,016,687** (36%)

---

## 4. Model Specification

### 4.1 Vote-share margin model

The core model predicts the Democratic two-party vote-share margin μᵢ for race *i*:

```
μᵢ = α₀ + α₁·PVIᵢ + α₂·incumbᵢ + α₃·GBᵢ + α₅·indiv_shareᵢ
        + (β₁ + β₂·|PVIᵢ| + β₃·incumbᵢ) × log(Dᵢ / (Dᵢ + Rᵢ))
```

**Variables:**
- `PVI` — Cook Partisan Voting Index (positive = D-leaning district)
- `incumb` — 1 if Democratic incumbent, 0 otherwise
- `GB` — generic ballot (D − R percentage points)
- `indiv_share` — D candidate individual-contribution fraction (TTL_INDIV_CONTRIB / TTL_RECEIPTS, from FEC weball col 17 / col 5); ranges [0, 1]
- `log(D/(D+R))` — log Democratic spending share; the key spending measure

The spending term interacts with both PVI and incumbency. This allows the spending response to vary by district competitiveness and candidate type — a dollar in a D+15 district has a different effect than the same dollar in a toss-up.

**Win probability:**

```
P_win(i) = Φ(μᵢ / σᵢ)
```

where Φ is the standard normal CDF and σᵢ is the district-level uncertainty (see §4.2).

### 4.2 Uncertainty model (σᵢ)

Residual uncertainty is modeled as a log-linear function of district lean and candidate type, retransformed with a Duan (1983) smearing correction (added 2026-07-23 — see §5.3's note):

```
σᵢ = 1.6798 × exp(2.3777 + 0.008053·|PVIᵢ| − 0.3422·is_openᵢ − 0.5935·is_challengerᵢ + 0.0017·|GBᵢ|)
```

(Corrected 2026-07-23, codebase audit: this formula was never updated by any prior correction pass in this document — it still showed a stale, pre-2026-07-23 pipeline result. It's also no longer a simple linear function: the historical additive form above was always an approximation of the actual `exp(...)` fit in `data/processed/sigma_model.json`; see §5.3 for the fit history.)

Challengers running in opposing-party districts exhibit lower residual uncertainty due to selection effects — candidates who run in difficult territory tend to be systematically uncompetitive, reducing the scatter around the predicted margin. **Open seats now show the same directional pattern (lower σ than the incumbent baseline) rather than higher** — see §5.3's note on the σ-ordering check, which now fails the "open > challenger > incumbent" expectation stated in earlier drafts of this section.

### 4.3 Marginal Seat Gain (MSG)

The marginal return from adding one dollar of Democratic party spending to race *i*:

```
MSG_i = φ(μᵢ/σᵢ) × (1/σᵢ) × (β₁ + β₂·|PVIᵢ| + β₃·incumbᵢ) × Rᵢ / (Dᵢ · (Dᵢ + Rᵢ))
```

where φ is the standard normal PDF. MSG has a 1/Dᵢ² dependency — at low spending levels, marginal returns are very high; at high spending levels, the log-ratio saturates and returns diminish sharply. This is why the optimizer must be non-linear.

### 4.4 Repeat-challenger identification strategy (β_RC)

β₁ (the spending coefficient in the constant-intercept term) doubles as the repeat-challenger causal estimate (β_RC). Estimation uses matched pairs of (cycle *t*, cycle *t+2*) where the same non-incumbent Democrat faces the same Republican opponent in the same district across two consecutive cycles. Under this design, district fixed effects cancel, isolating spending variation as the identifying source of outcome variation.

---

## 5. Estimation

All coefficients estimated by OLS on the 2012–2022 historical panel. β_RC estimated on the repeat-challenger subset.

### 5.1 Margin model coefficients

| Parameter | Estimate | SE | p | Interpretation |
|-----------|----------|----|---|----------------|
| α₀ | 2.475 | — | — | Intercept (baseline margin, equal spending) |
| α₁ | 1.057 | — | — | PVI effect: +1 PVI point → +1.06 pp margin |
| α₂ | 31.134 | — | — | Incumbency advantage in margin (pp) |
| α₃ | 0.424 | — | — | Generic ballot pass-through |
| α₅ | 0.0 (zeroed) | — | — | Individual-contribution share (see §5.4) |
| β₁ | 5.475 | 1.587 | <0.001 | Spending response (constant term; β_RC) |
| β₂ | 0.054 | — | — | Spending × |PVI| interaction |
| β₃ | 28.054 | — | — | Spending × incumbency interaction |

**Corrected 2026-07-23a (elections.py fix + 5 other bugs).** All figures in this document below this point were regenerated against `scripts/run_estimation.py` + `scripts/run_backtest.py` rerun after fixing: (1) `data/elections.py` miscoding Minnesota's Democratic-Farmer-Labor and North Dakota's Democratic-NPL candidates as 0 votes in every historical panel cycle (corrupting the beta_RC/margin-model training data for those states); (2) `comparison/uncertainty.py` letting beta_RC bootstrap draws silently override the calibrated open-seat elasticity; (3) `outputs/charts.py`'s efficiency-frontier chart mislabeling every γ-point; (4)-(6) `scripts/run_backtest.py`'s null/Cook reference points on the same chart.

**Corrected 2026-07-23b (codebase audit — NRCC/HMP/CLF FEC committee-ID fix, σ model fix, optimizer diagnostic fix).** The table above now reflects a further rerun after: `scripts/fetch_data.py`'s NRCC committee ID (and `fetch_live_ies.py`'s HMP/CLF IDs) turned out to point at unrelated committees — NRCC coordinated-expenditure spend was silently $0 in `R_total` for every historical cycle until re-fetched under the correct ID (`C00075820`); the σᵢ model's open-seat residuals were computed against the wrong predicted margin (see §5.3); and the optimizer's `expected_seats` diagnostic was missing a baseline term. Every number in this document past this point is from that rerun. SE columns not re-run for α₀/α₁/α₂/α₃/β₂/β₃ are left blank rather than stale. Previously-standard errors (α₀=1.938, α₁=0.066, α₂=2.040, α₃=0.112, β₂=0.028, β₃=4.188) are historical and not reproduced here.

**In-sample R² (competitive races):** 0.561 (gate threshold: ≥ 0.40) — up from 0.492 pre-elections.py-fix; the MN/ND data corruption was injecting pure noise into the competitive-adjacent training panel. (Barely moved, 0.5605→0.5605, in the 2026-07-23b NRCC/σ-model rerun — R² is a margin-model fit statistic, only indirectly touched by the R_total/σ corrections.)

**α₂ = 31.13 and β₃ = 28.05 are large.** For incumbent-held competitive seats, the effective spending coefficient is β₁ + β₃ = 33.53 — incumbents extract far more vote-share per unit of spending share than challengers. This is consistent with incumbents having established name recognition that amplifies the marginal effectiveness of campaign contact.

### 5.4 Individual-contribution share (α₅) — estimated but zeroed out

`indiv_share` = TTL_INDIV_CONTRIB / TTL_RECEIPTS for the Democratic nominee, sourced from FEC weball bulk files (col 17 / col 5). It ranges from 0 (candidate funded entirely by PACs and party) to 1 (funded entirely by individual donors).

**Estimated coefficient: α₅ = −3.99 (SE = 2.18, p = 0.067). Set to 0.0 in the active model.**

The sign is negative and marginally significant. The expected direction was positive — better candidates should attract more small-dollar donors. The negative sign most likely reflects two confounds:

1. **Race salience as the true driver.** Competitive races are nationally visible. They attract more small-dollar grassroots donors precisely because the race matters — not because the candidate is weaker. Across 2024 competitive races, mean `indiv_share` rises monotonically from Lean D (0.70) to Toss-Up (0.74) to Lean R (0.74). `indiv_share` is a proxy for competitiveness, not quality, after controlling for PVI and incumbency.

2. **PAC targeting as a conditional signal.** Low `indiv_share` (heavy PAC investment as a fraction of total receipts) may reflect parties concentrating outside money on selected targets — but this is already partially captured by PVI, incumbency, and spending ratio.

**Why α₅ is zeroed out.** Including α₅ = −3.99 in the model creates a systematic baseline distortion: it penalizes the DCCC's own portfolio (which is concentrated in competitive races with high `indiv_share`) by 6.56 expected seats, while the optimizer's recommended allocation is *mathematically identical* with or without α₅ (max allocation diff = $0.00 across all 433 races). The coefficient inflates the apparent DCCC-vs-model gain from +5.34 to +11.9 seats without the optimizer targeting different races. It also degrades out-of-sample calibration: Brier score with α₅ = 0.0299 vs. 0.0283 without. Given p = 0.067 (marginal), the endogeneity concern, and the baseline distortion, α₅ is set to 0.0 in `data/processed/margin_model_coef.json`.

**Not recomputed 2026-07-23b.** This diagnostic (the with/without-α₅ comparison) is a bespoke, one-off calculation, not part of `run_backtest.py`'s standard output — it was not re-run against the 2026-07-23b NRCC/σ-model/optimizer fixes. The core decision (constrain α₅ to zero) does not depend on the exact figures above and is unaffected; treat the specific numbers in this subsection (−3.99, 6.56 seats, 0.0299/0.0283, +11.9) as historical, from the elections.py-fix-era pipeline, not the current one.

---

### 5.2 Repeat-challenger causal estimate

**Corrected 2026-07-23b** (NRCC/HMP/CLF committee-ID fix — see the top-of-document flag; §5.1's elections.py fix and this fix are compounding, both baked into the panel these 118 pairs' margin outcomes are drawn from):

| | Value |
|-|-------|
| β_RC estimate | **5.475** |
| Standard error | 1.587 |
| 95% CI | [2.36, 8.59] |
| Matched pairs | 118 |

The estimate is statistically significant (t ≈ 3.45). It implies that for a challenger at equal spending (log-ratio = 0), moving from 0 to 100% of the spending share shifts the predicted margin by ~5.5 percentage points. This is the cleanest causal quantity in the model — the repeat-challenger design absorbs district and candidate heterogeneity.

**Non-parametric bootstrap (added 2026-07-22, re-run 2026-07-23b).** The 95% CI above is parametric (β̂ ± 1.96·SE, assuming the OLS sampling distribution is normal) — untested against the actual 118-pair sample, which §10.1 below documents as skewed toward Safe R pairs (72%). `bootstrap_beta_rc()` (`src/backtest/estimation/beta_rc.py`) instead resamples the 118 pairs with replacement and re-estimates β_RC on each resample. Run against this repository's real panel (n=1000 resamples, seed=42, via `scripts/run_estimation.py`):

| | Parametric N(β̂, SE²) | Bootstrap (empirical) |
|---|---|---|
| Estimate / mean | 5.475 | 5.543 |
| SE / std | 1.587 | 1.514 |
| 95% CI | [2.364, 8.585] | [2.834, 8.640] |
| Skew | 0 (assumed) | +0.198 |

The two CIs are comparable in width, but the bootstrap's lower bound sits meaningfully higher than the parametric one (2.83 vs. 2.36). The "low-end collapse" scenario cited in §9 and §10.1 (β_RC ≈ 2.36) is *less* likely under the empirical resampling distribution than the normal approximation implies — a mild point against the causal-fragility concern in §10.1, not a confirmation of it. See `data/processed/beta_rc_bootstrap.json` and `docs/data_catalog.md` §3.2b. `outputs/beta_rc_bootstrap_distribution.png` (`scripts/plot_beta_rc_bootstrap.py`) plots the bootstrap histogram against the parametric normal — the histogram's right tail visibly extends past the symmetric curve.

### 5.3 σ model

Estimated from OLS on log|margin residual|, retransformed with a Duan (1983) smearing correction, against district characteristics:

| Parameter | Estimate |
|-----------|----------|
| Intercept | 2.378 |
| |PVI| | 0.00805 |
| Is open seat | −0.342 |
| Is challenger | −0.594 |
| Smearing factor | ×1.680 |

**Corrected 2026-07-23b, codebase audit — two real bugs fixed, not just the data refresh.** (1) Open-seat residuals feeding this fit were previously computed against the *wrong* predicted margin — `estimation/sigma.py` used the base spending coefficient β₁ instead of the open-seat-calibrated β₁,open that `model/margin.py::predict()` actually applies to Open-seat races, systematically distorting the fitted "is open seat" effect. (2) `exp(fitted)` alone recovers the *median*, not the mean, of the assumed log-normal |residual| — the ×1.680 smearing factor now corrects that retransformation bias; no such correction existed before this fix. **Consequence worth flagging directly:** with residuals now computed against the correct μ̂, the "is open seat" coefficient is negative (open seats read as *lower*-variance than the incumbent baseline), the opposite of the positive coefficient every earlier version of this document reported. See §6.2's σ-ordering gate result and the note there — this is treated as an open question in this pass, not resolved further.

---

## 6. Backtest Methodology

### 6.1 Setup

The backtest evaluates what the model would have recommended for 2024 DCCC spending, given actual Republican spending levels. The optimization is constrained to the **party-controlled budget only** ($465M), with candidate spending treated as a floor for each race.

### 6.2 Validation gates (all passed)

| Gate | Result | Threshold |
|------|--------|-----------|
| Spending data completeness | 91.9% (398/433 races) | ≥ 80% |
| Margin model R² (competitive) | 0.561 | ≥ 0.40 |
| σ ordering (open > chall > incumb) | 0/5 bins | ≥ 0% |
| MSG sign (all competitive races) | 53/53 positive | 100% |
| Optimizer convergence | Optimal | status=optimal |
| Brier score | 0.0300 | ≤ Cook Brier + 0.05 |

(R² and Brier corrected 2026-07-23a/b; other gates unchanged by either fix. **On the σ-ordering gate reading "0/5 bins" as a pass:** the gate's configured threshold is literally "≥ 0% of PVI bins ordered correctly," which is vacuously satisfied by any result including total failure — it was not tightened as part of the 2026-07-23b fix pass, so its PASS status here should not be read as the ordering actually holding. See §5.3's note.)

### 6.3 Optimizer

**Objective:**

```
Maximize  Σᵢ Φ(μᵢ(Dᵢ) / σᵢ)
Subject to:  Σᵢ party_i ≤ $465M
             0 ≤ party_i ≤ 0.15 × $465M  (15% cap per race)
             Dᵢ = cand_floor_i + party_i
```

The non-linear objective (direct Φ evaluation) is required because the MSG linearization breaks down for races with very low observed spending — a linear approximation at $1M spend is invalid at $10M, since the log-ratio moves into a highly non-linear regime. A scipy SLSQP solver is used with 500 iterations, initialized from the observed DCCC allocation.

The sensitivity grid (§9, γ near 0) occasionally hits a QP-solver degeneracy at extremely small γ; `allocator.py` detects this and falls back to the LP formulation automatically (logged as a warning). This does not affect the headline γ=0 result.

**Corner solutions:** 260/433 races (60%, corrected 2026-07-23b — was 344/433/79% after the elections.py fix, 374/433/86% before it) converge to their floor (0 party spend) or cap. Interior solutions increased correspondingly — reflecting that the optimizer concentrates party money on the highest-MSG competitive races.

### 6.4 Allocator benchmarks

Four strategies are compared, each applied to the same $1.29B total budget using model-estimated win probabilities:

- **DCCC observed** — actual 2024 spending shares
- **Cook-implied** — spending proportional to Cook win probability per race
- **Null (equal-weight)** — uniform share across the 53 competitive races
- **Model optimizer** — SLSQP solution to the non-linear seat-maximization problem

---

## 7. Findings

### 7.1 Model outperforms Cook on calibration

| Metric | Model | Cook Political Report |
|--------|-------|-----------------------|
| Brier score | **0.0312** | 0.0364 |
| Improvement | — | **+14%** |

(Corrected 2026-07-24, persuasion-ceiling fix — see the top-of-document flag — was 0.0300/0.0364/+18% under 2026-07-23b; 0.0273/0.0364/+25% after the elections.py fix alone; 0.0283/0.0380/+26% before that.) The model's probability estimates remain better calibrated than Cook's categorical ratings (converted to win probabilities). The ceiling nudges Brier slightly worse (0.0300→0.0312) because it pulls p_win back toward each race's own candidate-floor probability for the handful of races it actually binds on — a small, expected cost of no longer letting those races' win probabilities be driven by an unsupported extrapolation.

### 7.2 DCCC efficiency: Spearman correlation

Among the 53 competitive races, there is a strong negative correlation between DCCC total Democratic spending and MSG:

| Statistic | Value |
|-----------|-------|
| Spearman ρ | **−0.809** |
| p-value | **< 0.0001** |
| 95% CI | [−0.936, −0.618] |
| n races | 53 |

(Corrected 2026-07-24, persuasion-ceiling fix — was ρ=−0.789, CI [−0.934,−0.563] under 2026-07-23b; ρ=−0.536, CI [−0.755,−0.261] after the elections.py fix alone; ρ=−0.582, CI [−0.789,−0.307] before that.)

**Interpretation:** DCCC systematically concentrates more money in races where the marginal return per dollar is *lower*. This is a structural pattern, not random noise, and the persuasion-ceiling fix leaves this specific finding essentially unchanged — the ceiling caps the *magnitude* of MSG in near-zero-floor races, but it does not touch the *rank ordering* that drives a rank-correlation statistic, so ρ moves only slightly (−0.789→−0.809).

**Corrected MSG gradient (2026-07-22 backport).** The figures in this section were regenerated against the current pipeline. An earlier implementation of the MSG gradient omitted the Rᵢ/Dᵢ factor (∂μᵢ/∂Dᵢ = cᵢ·Rᵢ/(Dᵢ·Tᵢ), exact only at spending parity Dᵢ=Rᵢ), biasing MSG for the many lopsided-spending races in this sample. The fix is documented in `docs/paper1_draft.md` §9.1. It moved this section's ρ from −0.597 to −0.582, then to −0.536 (2026-07-23a, elections.py fix), then to −0.789 (2026-07-23b, NRCC/σ-model/optimizer fix), then to −0.809 (2026-07-24, persuasion-ceiling fix) — and, more consequentially, changed the by-category breakdown below qualitatively at each stage, not just numerically.

**By Cook category** (within competitive subset; regenerated 2026-07-24 against the persuasion-ceiling fix, verified against `outputs/spearman_by_category.csv`):

| Category | n | ρ | p |
|----------|---|---|---|
| Likely D | 40 | −0.270 | 0.092 |
| Lean D | 28 | −0.733 | < 0.001 |
| Toss-Up | 18 | −0.930 | < 0.001 |
| Lean R | 7 | −0.964 | < 0.001 |
| Likely R | 36 | −0.677 | < 0.001 |

**Largely stable relative to the 2026-07-23b table (was −0.208/−0.639/−0.944/−0.964/−0.722) — the ceiling fix moves every category's ρ by a few hundredths, none flip sign, and the ordering (Toss-Up and Lean R strongest, Likely D weakest) is unchanged.** Every category remains negative, including Likely R. Likely D remains the weakest/least significant relationship (ρ=−0.270, p=0.092, still not distinguishable from zero at conventional thresholds), while Lean D, Toss-Up, Lean R, and Likely R all show a strong, significant negative correlation. The strongest remain at the most contested tier: **Toss-Up (ρ=−0.930, p<0.001, n=18) and Lean R (ρ=−0.964, p<0.001, n=7)** — races where marginal dollars are most decisive for the House majority threshold, and exactly where the model's MSG estimate and DCCC's actual spending are most sharply misaligned. The Lean R estimate should be read cautiously given its small category size (n=7). This section's qualitative story — "misallocation is broad-based across nearly every competitiveness tier" — is the same one the 2026-07-23b pass established and survives the ceiling fix unchanged; only the allocator-comparison numbers below (§7.3) moved substantially.

**Matched-group test.** Restricting to Lean D and Toss-Up races matched on partisan lean (±5 PVI points), where the risk-adjustment term γ·∂Var/∂sᵢ is approximately constant (Section 3.3 of `docs/paper1_draft.md`): n=44, ρ = −0.559 (p = 0.0001) — the negative correlation cannot be attributed to differential risk profiles within a structurally comparable subsample. *(Not recomputed in the 2026-07-23 elections.py-fix rerun — this ad-hoc subsample statistic isn't part of `run_backtest.py`'s standard output; flagged as unverified against the corrected panel, not confirmed wrong.)*

### 7.2b Permutation tests (added 2026-07-22)

Two permutation tests were added to remove reliance on asymptotic significance assumptions (`permutation_test_spearman_efficiency()` in `comparison/efficiency.py`; `permutation_test_allocation_efficiency()` in `comparison/benchmark.py`). Both run automatically in `run_backtest.py` and save to `outputs/permutation_tests.json`. Run against the real 2024 pipeline, 2000 shuffles each, seed 42:

*(Figures below corrected 2026-07-24, persuasion-ceiling fix — see the top-of-document flag.)*

1. **Spearman ρ permutation test.** Randomly reassign DCCC's observed spending across the 53 competitive races (breaking any link to MSG) and recompute ρ 2000 times: **0 of 2000 shuffles produced |ρ| ≥ 0.809.** Permutation p = 0.0 vs. asymptotic p = 2.4×10⁻¹³ (was |ρ|≥0.789, asymptotic p=2.2×10⁻¹² under 2026-07-23b; |ρ|≥0.536, asymptotic p=3.5×10⁻⁵ after the elections.py fix; |ρ|≥0.582, asymptotic p=4.7×10⁻⁶ before that) — the asymptotic test is not overstating significance here, and the margin between permutation and asymptotic significance has only widened.

2. **Allocation-efficiency permutation test.** A stronger, assumption-lighter check: randomly reshuffle DCCC's own per-race **party-dollar** amounts (its coordinated + IE spend, not each race's own candidate-committee money) across the same 53 races and evaluate E[Seats] under each shuffle using the **true nonlinear Φ(μ/σ) evaluation** (`optimizer.allocator.nonlinear_expected_seats_at_party_dollars()`), holding every floor fixed.
   - DCCC's actual E[Seats] = 215.12 vs. a null mean of 214.84 (95% CI [214.55, 215.12]) — **2.9% of 2000 random reshuffles of DCCC's own party dollars scored at least as well as DCCC's actual allocation** (was 10.75%, null mean 216.46 under 2026-07-23b; 10.0%, null mean 217.95 after the elections.py fix; 7.7%, null mean 214.28 before that). DCCC's real allocation is now more clearly distinguishable from a random reshuffle of its own dollars than at any prior stage of this document — a direct consequence of the ceiling removing the near-zero-floor extrapolation that was inflating the null distribution's spread.
   - The model optimizer's true nonlinear E[Seats] = 217.94 vs. the same null — **0 of 2000 reshuffles matched or exceeded it.** The optimizer's gain is not explainable as "any reshuffle beats DCCC" (a real concern, since the win-probability curve's concavity alone could produce that pattern) — it is specifically finding structure beyond what random reallocation of the same dollars achieves, and this part of the finding has been completely robust across every correction in this document's history, including this one.

**Correction history (2026-07-22, two rounds, same day as the original finding — see §7.3 for the parallel history in `compare_allocators()`).** Round 1: this test originally used the linearized MSG-delta approximation for DCCC, the model, and every null draw — internally consistent, but not checked against the true nonlinear evaluation until an anomalous 2022 OOS comparison surfaced that the linearization mattered enough to change conclusions. Fixing that alone gave 35.1% (2024) / 87.5% (2022) in place of a reported 100%. Round 2, same day: the round-1 fix still reshuffled each race's *full* observed dollar total, including candidate-committee money DCCC never controlled — inconsistent with the instruction that every allocator comparison in this project should use only the DCCC budget. Restricting the reshuffle to party-only dollars gives the figures above (7.7% in 2024) and 72.3% in 2022 (§8.2b) — notably, this final correction makes the 2024 finding *stronger* while making 2022 *weaker*, reversing which cycle shows the sharper DCCC-side finding relative to round 1. The model-side finding (0 of 2000) was completely robust across every round, in both cycles — the bias only ever ran in DCCC's favor (making it look worse than it should), never affecting the model. `permutation_test_allocation_efficiency()` now uses the true nonlinear, party-budget-only evaluation by default; the figures above and the chart (`outputs/permutation_tests_null_distributions.png`) are final.

Configurable via `config.yaml: uncertainty.permutation_draws` (default 2000). `outputs/permutation_tests_null_distributions.png` (`scripts/plot_permutation_tests.py`) plots both null distributions against the real observed values — DCCC's actual allocation sits outside the null cloud in both panels.

### 7.3 Allocator comparison

**Table corrected 2026-07-22 (three times, same day — see the note after the table for the full history).** `compare_allocators()` now evaluates all four rows the same way: the true nonlinear Φ(μ/σ), and — per explicit instruction ("All models/methods when compared to each other should only use the DCCC budget, that is the whole point") — every hypothetical row (Null, Cook, Model) redistributes only the $465M DCCC-controllable party budget, holding every race's own candidate-committee money fixed. No strategy is credited with money it doesn't actually control.

**Corrected 2026-07-24 (persuasion-ceiling fix, plus the LP-scaling and WA-03 name-matching bugfixes it surfaced; see the top-of-document flag).**

| Strategy | Expected Seats | vs. DCCC |
|----------|---------------|----------|
| **DCCC observed** | **215.12** | — |
| Cook-implied | 215.18 | **+0.07** |
| Null (equal-weight) | 215.34 | **+0.23** |
| Model optimizer | 217.94 | **+2.83** |

(Was, 2026-07-23b: DCCC=217.08, Cook=217.35 (+0.27), Null=217.65 (+0.58), Model=230.31 (+13.24). Before that, 2026-07-23a/elections.py fix: DCCC=218.80, Cook=219.03 (+0.23), Null=219.55 (+0.75), Model=225.19 (+6.39). Before that: DCCC=215.18, Cook=215.45 (+0.27), Null=215.89 (+0.71), Model=220.52 (+5.34).)

**Key results:**

1. **The model optimizer gains +2.83 expected seats** from the same $465M party budget, without changing total spending. This is a genuine, real reallocation from low-MSG safe seats into high-MSG competitive races — not the artifact the +13.24 figure turned out to be. **The drop from +13.24 to +2.83 is the persuasion-ceiling fix working as intended, not a regression:** 81% of the old +13.24 gain traced back to near-zero-candidate-floor Safe-tier races the historical panel provides no support for extrapolating into (see §7.3b below). Safe-tier party-budget share falls from 45% to 9.0% under the fix.

2. **Both zero-information benchmarks now barely beat DCCC** — Null by +0.23 seats, Cook-implied by +0.07 — an even narrower margin than the pre-ceiling reading. Both are still positive (DCCC's real choices are still not the best of the three simple alternatives), but the margins are now close to noise-level.

3. **The real headline remains the Model's dominance over every alternative, once the comparison is fair.** The model beats Null by +2.60 seats and Cook by +2.76 — smaller in absolute terms than the pre-ceiling reading's +12.66/+12.97, but now a defensible, panel-supported number rather than one driven almost entirely by extrapolation into races with no historical basis for the implied effect size. MSG-based targeting is still doing almost all of the work in this comparison relative to generic diversification (Null) or competitiveness information (Cook) alone.

**Correction history, preserved for the audit trail (this table's own figures above are already final and correct):**
- **First pass** (pre-existing, before this session): Null/Cook computed via a linearized MSG-delta approximation, inconsistent with the Model row (already true nonlinear via a post-hoc override) — 215.86(+0.68)/214.79(−0.39).
- **Second pass** (2026-07-22): fixed the linearization inconsistency, but Null/Cook still scaled against the *entire* two-party spending pool across all 433 races (including candidate-committee money in safe seats DCCC never controls) — 217.62(+2.44)/217.04(+1.86). This is where the 2022 OOS anomaly (Null appearing to edge out the Model) first surfaced and got investigated (`scripts/investigate_null_benchmark_bias.py`).
- **Third pass, same day** (2026-07-22): Null and Cook now also constrained to the DCCC-controllable party budget only, matching the Model's actual constraint exactly — 219.55(+0.75)/219.03(+0.23), Model=225.19(+6.39).
- **Fourth pass** (2026-07-23a, elections.py MN/ND fix): re-derived on the corrected historical panel — 219.55(+0.75)/219.03(+0.23) (little changed from pass three at this stage), DCCC/Model shifted to 218.80/225.19.
- **Fifth pass** (2026-07-23b, codebase audit: NRCC/HMP/CLF committee-ID fix + σ-model fix + optimizer diagnostic fix): 217.65(+0.58)/217.35(+0.27), Model=230.31(+13.24). At the time this was flagged as "the version to trust going forward" — it was not; the σ-model fix had removed an accidental suppressor on a pre-existing extrapolation bug, and the resulting +13.24 was investigated on your suspicion that it looked too large (see the top-of-document flag).
- **Sixth pass, current** (2026-07-24, persuasion-ceiling fix): 215.34(+0.23)/215.18(+0.07), Model=217.94(+2.83). This is the version to trust going forward.

Pass six is qualitatively different from passes one through five: every earlier correction moved either Null/Cook down or the Model up, always widening the Model's apparent advantage. Pass six is the first correction that *narrows* the Model's advantage — and it does so by fixing a real extrapolation bug, not by introducing a new one. The qualitative conclusion (Model > Null/Cook > DCCC) survives, but the magnitude is now roughly a fifth of what 2026-07-23b reported.

### 7.3b Why the number moved: the persuasion ceiling

**The root cause was extrapolation, not a linear-vs-nonlinear bug.** Your suspicion that +13.24 "seemed too high" was investigated directly: the true nonlinear SLSQP optimizer was genuinely computing it (verified via both code-path tracing and independent from-scratch recomputation), so the fix could not be "use the nonlinear model" — it already was. The real mechanism: the margin model's spending term has an unbounded gradient as a race's D→0 (`c·R/(D·T)`), and before the σ-model fix (2026-07-23b) an *understated* σᵢ kept near-zero-floor races' win probabilities pinned near 0 regardless of spending — accidentally suppressing this blowup. Once σᵢ was corrected, the suppression went away and the optimizer began recommending large sums into Safe-tier races with near-zero candidate-committee floors, extrapolating the spending response far outside the region the historical panel actually supports. Diagnostic evidence: 81% of the +13.24 gain came from races spending under $500k; Safe-tier races absorbed 45% of the recommended party budget (`scripts/investigate_msg_low_d_extrapolation.py`, `outputs/msg_low_d_extrapolation_check.csv`).

**The fix is a regularization prior, calibrated empirically, not a hand-picked constant.** `C_i = c_max · 4·Φ₀·(1−Φ₀)` caps the achievable margin shift above a race's own candidate-only floor, where `Φ₀` is that race's win probability at the floor (no party money) — a parabola peaking at `c_max` for a true toss-up and vanishing at either extreme. A naive calibration attempt (fitting `C_i` directly against repeat-challenger swing magnitudes) was tried first and rejected: the raw swings were *largest* in the most hopeless districts, the opposite of what a persuasion ceiling should show — traced to candidate-quality composition effects (a real repeat challenger becoming a token candidate between cycles), not a persuasion signal. A σ-only ceiling was tried second and also rejected: σᵢ's own |PVI| dependence (0.008/point) is far weaker than μ's (1.057/point), so it doesn't discriminate hopeless races from competitive ones. `c_max = 10.0` was set from an 8-point robustness sweep {3, 5, 7, 10, 15, 20, 30}: Safe-tier party-budget share falls smoothly across the whole range (no fragile threshold), and 5–10 gives the best ratio of competitive-tier to non-competitive-tier gain before Likely-tier reallocation starts dominating the marginal gain at larger `c_max`.

**Per-race average allocation now matches consultant intuition, not just the aggregate.** Decomposed by tier, the optimizer funds Toss-Up > Lean > Likely > Safe on a *per-race* basis — the pre-ceiling aggregate's apparent "Likely races dominate" pattern was a pure race-count composition effect (76 Likely-tier races vs. 18 Toss-Up races in the universe), not the model deprioritizing competitive races.

### 7.4 What the optimizer actually does

The optimizer concentrates party money in races where MSG is highest — typically lower-spending competitive races where the spending ratio log(D/(D+R)) is far below parity. **Corrected 2026-07-24 (persuasion-ceiling fix):** NC-13, FL-27, CT-02, FL-28, AZ-04, and CA-40 remain the highest-MSG near-floor competitive races (unchanged from 2026-07-23b — the ceiling caps MSG's *magnitude* in near-zero-floor races, but does not change which competitive races have the highest MSG among races the panel actually supports) and receive the largest allocation increases in the optimizer solution.

NC-13 and FL-27 were both won by Republicans in 2024 — the model's high-MSG flag for these races was diagnostically correct. CT-02 and AZ-04 (won by Democrats) and CA-40/FL-28 round out the list. The +2.83 expected seat gain (corrected 2026-07-24, was +13.24 under 2026-07-23b, +6.39 after the elections.py fix alone, +5.34 before that) is concentrated in precisely this type of race: competitive, low DCCC investment, high marginal return per dollar — now without the Safe-tier extrapolation that inflated the earlier figure.

---

## 8. Cross-Cycle Validation (2022)

To test whether the inefficiency finding is an artifact of 2024-specific conditions, a true out-of-sample validation was run on the 2022 election cycle. The margin model was re-estimated on the 2012–2020 panel only (excluding 2022), and the backtest was then applied to 2022 actual spending and outcomes.

### 8.1 Setup

| Parameter | 2024 (primary) | 2022 (OOS validation) |
|-----------|---------------|----------------------|
| Estimation panel | 2012–2022 | 2012–2020 |
| Validation cycle | 2024 | 2022 |
| Generic ballot | −1.2 (R+1.2) | −1.0 (R+1.0) |
| Universe size | 433 races | 433 races |
| Competitive races | 53 | 61 |
| Party budget | $465M | $322M |

### 8.2 Results

**Both columns corrected 2026-07-24 (persuasion-ceiling fix — see the top-of-document flag).** Estimation (`run_estimation.py`) is unaffected by the ceiling — `data/processed_oos_2020/*.json` did not need regenerating — only `scripts/run_backtest.py --cycle 2022 --processed-dir data/processed_oos_2020` was rerun.

| Metric | 2024 | 2022 (OOS) |
|--------|------|------------|
| **Spearman ρ (DCCC vs MSG)** | **−0.809** (p<0.0001) | **−0.847** (p<0.0001) |
| 95% CI on ρ | [−0.936, −0.618] | [−0.916, −0.719] |
| DCCC expected seats | 215.12 | 213.37 |
| Null (equal-weight) | 215.34 (+0.23) | 213.68 (+0.32) |
| Cook-implied | 215.18 (+0.07) | 213.55 (+0.18) |
| Model optimizer | 217.94 (+2.83) | 216.59 (+3.22) |
| **Brier (model)** | **0.0312** | **0.0360** |
| **Brier (Cook)** | **0.0364** | **0.0340** |
| Model beats Cook on calibration? | Yes (+14%) | No — Cook wins narrowly (model +5.9% worse) |
| Model optimizer beats DCCC? | Yes (+2.83) | **Yes (+3.22)** |
| Concentration cap gap | 0.0 seats | 0.0 seats |

(2024 was, 2026-07-23b: ρ=−0.789 [−0.934,−0.563], DCCC=217.08, Null=217.65 (+0.58), Cook=217.35 (+0.27), Model=230.31 (+13.24), Brier 0.0300/0.0364/+18%. 2022 was, 2026-07-23b: ρ=−0.707 [−0.827,−0.538], DCCC=215.47, Null=215.96 (+0.49), Cook=215.60 (+0.12), Model=228.09 (+12.61), Brier 0.0350/0.0340, model +2.9% worse. Earlier history — 2024 elections.py-fix-era: ρ=−0.536, DCCC=218.80, Model=225.19 (+6.39); pre-elections.py-fix: ρ=−0.582, DCCC=215.18, Model=220.52 (+5.34). 2022 elections.py-fix-era: ρ=−0.747, DCCC=217.76, Model=225.53 (+7.77); pre-elections.py-fix: ρ=−0.750, DCCC=214.87, Model=221.66 (+6.79).)

**The 2022 OOS calibration finding (model narrowly worse than Cook on Brier) survives the ceiling fix unchanged in direction** — first surfaced under 2026-07-23b (model 0.0350 vs Cook 0.0340) and essentially unchanged under 2026-07-24 (model 0.0360 vs Cook 0.0340, now +5.9% worse rather than +2.9%). This remains a real, specific finding about out-of-sample calibration, distinct from the efficiency finding below (still unambiguously strong in both cycles) — Brier calibration and Spearman-ρ efficiency are different claims and needn't move together.

**A genuine, welcome surprise: Spearman ρ actually strengthens under the ceiling fix, in both cycles** (2024: −0.789→−0.809; 2022: −0.707→−0.847) — the ceiling caps MSG's magnitude in near-zero-floor races without touching the rank ordering a correlation statistic depends on, and removing the extrapolation-driven noise from those races' MSG values apparently sharpens the correlation rather than weakening it. **2022 is once again the stronger-magnitude correlation** (−0.847 vs −0.809), reversing the 2026-07-23b reading (2024 stronger) and returning to the ordering the elections.py-fix-era and pre-elections.py-fix tables both showed — a third reversal of this specific ordering across this document's history, underscoring that "which cycle has the larger |ρ|" is a fragile secondary readout, not something to lean on. The primary claim — DCCC spends more where MSG is lower, highly significant and same-signed in both cycles — has been completely stable throughout.

**Null/Cook-implied rows redistribute only the DCCC-controllable party budget** ($465M in 2024, $322M in 2022), holding every race's own candidate-committee money fixed, per §7.3's established convention. Both benchmarks' advantage over DCCC narrows further under the ceiling fix (2024: +0.58→+0.23, +0.27→+0.07; 2022: +0.49→+0.32, +0.12→+0.18 — Cook's edge widens slightly in 2022) while the Model's advantage over DCCC shrinks sharply in both cycles (2024: +13.24→+2.83; 2022: +12.61→+3.22), consistent with §7.3's diagnosis: the pre-ceiling gain was substantially an artifact of Safe-tier extrapolation, and removing it affects the Model row far more than Null/Cook, which were never exploiting that pathology.

### 8.2b Permutation tests replicate out-of-sample

Both permutation tests from §7.2b were re-run on the 2022 OOS cycle (61 competitive races, 2000 shuffles, seed 42, `outputs/permutation_tests_2022.json`, chart `outputs/permutation_tests_null_distributions_2022.png`), reshuffling only DCCC's own party-controllable dollars (not candidate-committee money) among competitive races:

*(Figures below corrected 2026-07-24, persuasion-ceiling fix, `outputs/*_2022.*` regenerated against `data/processed_oos_2020`.)*

- **Spearman ρ permutation test.** 0 of 2000 shuffles reached |ρ| ≥ 0.847 (permutation p = 0.0 vs. asymptotic p = 7.4×10⁻¹⁸). Unaffected in kind by any correction — this is a pure rank-correlation test, no expected-seats evaluation involved — though the magnitude moved with ρ itself. (Was |ρ|≥0.707, asymptotic p=2.0×10⁻¹⁰ under 2026-07-23b; |ρ|≥0.747, asymptotic p=4.8×10⁻¹² after the elections.py fix; |ρ|≥0.750, asymptotic p=3.5×10⁻¹² before that.)
- **Allocation-efficiency permutation test (true nonlinear evaluation, party-budget-only reshuffling).** DCCC's actual E[Seats] = 213.37 vs. a null mean of 213.27 (95% CI [213.03, 213.50]) — **19.2% of 2000 random reshuffles of DCCC's own party dollars scored at least as well as DCCC's actual allocation** (was 56.75%, null mean 215.51 under 2026-07-23b; 80.0%, null mean 218.09 after the elections.py fix; 72.3%, null mean 215.10 before that). The ceiling fix moves 2022's DCCC-side finding sharply toward "more distinguishable from random," closing much of the gap with 2024 (see below). The model optimizer's true E[Seats] = 216.59 vs. the same null — **0 of 2000 reshuffles matched or exceeded it.**

**The DCCC-side ordering that this document flagged as persistently anomalous across every prior correction — 2024's DCCC allocation reading as more distinguishable from random than 2022's, despite every other robustness check finding 2022 misallocation more severe — has now largely resolved.** 2024's DCCC-side finding is 2.9% (§7.2b) vs. 2022's 19.2%: 2024 remains somewhat more distinguishable from random, but the gap has narrowed enormously from 10.75% vs. 56.75% (2026-07-23b) or 7.7% vs. 72.3% (elections.py-fix era). The ceiling fix removes most of what was driving this specific divergence — the extrapolation pathology inflated the *null* distribution's spread more than it inflated DCCC's own observed allocation, since DCCC's actual historical spending never had a near-zero floor in the way random reshuffles could land on one. The model-side finding (0 of 2000) remains identical and robust in both cycles.

### 8.3 Interpretation

**The efficiency finding is now stronger out-of-sample (2022) than in-sample (2024) — reverting to the ordering this section reported before 2026-07-23b, not a new reversal.** Under the 2026-07-24 fix, ρ = −0.809 in 2024 (p<0.0001, CI [−0.936, −0.618]) vs ρ = −0.847 in 2022 (p<0.0001, CI [−0.916, −0.719]) — 2022 is again the *larger*-magnitude correlation, matching the elections.py-fix-era reading (−0.536 vs −0.747) and the pre-elections.py-fix reading (−0.582 vs −0.750), and reversing only the intervening 2026-07-23b reading (−0.789 vs −0.707, 2024 larger). Both correlations remain highly significant and in the same (negative) direction in both cycles throughout — the core claim, "DCCC spends more where MSG is lower, and this is not sampling noise," has never been in doubt. What keeps moving is only the secondary, more fragile claim about which cycle's correlation is marginally larger — this document's history shows that claim flipping with pipeline corrections at least three times now, which is itself the useful finding: don't lean on this specific ordering for anything.

**The optimizer gain generalizes, but at a much smaller and more defensible magnitude than 2026-07-23b reported.** The model optimizer outperforms DCCC by +3.22 seats in 2022 (corrected 2026-07-24; was +12.61 under 2026-07-23b, +7.77 after the elections.py fix, +6.79 before that) and +2.83 seats in 2024 (corrected 2026-07-24; was +13.24, then +6.39, then +5.34). Both figures use the same nonlinear SLSQP optimizer with α₅ = 0 constrained throughout. 2022's gain is now slightly *larger* than 2024's (+3.22 vs +2.83) — a modest reversal of the 2026-07-23b ordering (+12.61 vs +13.24, 2024 larger), well within the range expected from different estimation windows. The consistency of direction and now much closer order of magnitude between cycles — different estimation windows, different generic ballot environments, different competitive maps — remains the primary evidence that the (now smaller) finding is structural rather than an estimation-window artifact.

**Zero-information benchmarks barely beat DCCC in 2024, and Cook now edges ahead of DCCC in 2022 by even less than before.** Equal-weight distribution beats DCCC by +0.32 seats in 2022 vs +0.23 in 2024; Cook-implied beats DCCC by +0.18 in 2022 vs +0.07 in 2024 (corrected 2026-07-24; was +0.49/+0.58 and +0.12/+0.27 under 2026-07-23b). Both remain positive in both cycles — DCCC's real choices are still not the best of the simple alternatives — but the margins are now narrow enough in both cycles to be close to noise-level, underscoring that the Model's advantage (§7.3) is the part of this finding actually worth acting on.

**Historical record, condensed (see git history / earlier revisions of this document for the full multi-stage account of the 2026-07-22 linearization-bias and budget-scope-asymmetry fixes that first established this section's methodology).** Two compounding artifacts in how Null/Cook were scored — a linearized MSG-delta approximation, and scoring against the entire two-party spending pool rather than the DCCC-controllable party budget — were found and fixed 2026-07-22, resolving an apparent "Null beats Model" anomaly in the 2022 OOS cycle. That methodology (true nonlinear evaluation, party-budget-only for every allocator) is unchanged by every correction since, including this one; only the underlying μ/σ/ceiling computation feeding into it has moved.

**Important caveat on the Spearman ρ comparison, unchanged.** The 2022 competitive set has 61 races vs 53 in 2024, reflecting different Cook ratings distributions and a different national environment (R+1.0 GB vs R+1.2 in 2024). The ρ values are not directly comparable across cycles, but both are highly significant and in the same direction with overlapping confidence intervals.

---

## 9. Actionability Assessment

### Actionable now

**MSG as a marginal-dollar decision tool.** Before committing the next tranche of party money to any race, the MSG calculation identifies where returns are highest given current spending levels. This is most useful for late-cycle allocation decisions when partial spending data is available.

**The equal-weight finding as a process audit.** An uninformed equal-weight rule beats the DCCC in both cycles, though only narrowly once every allocator is constrained to the DCCC's real budget: +0.23 seats in 2024 (corrected 2026-07-24, was +0.58 under 2026-07-23b, +0.75 after the elections.py fix, +0.71 before that) and +0.32 seats in 2022 (corrected 2026-07-24, was +0.49, then +1.39, then +1.30). This is a model-agnostic result that does not require accepting any specific coefficient — though on its own, a margin this narrow is now much weaker than the MSG optimizer's own advantage (§7.3's real headline: the Model beats Null by +2.6–2.9 seats, not the reverse). The finding remains operationally valuable as a real-time calibration check: compute the null advantage using partial-cycle FEC filings and a simple equal-weight benchmark. A large positive value signals a misallocation regime; a near-zero or negative value would suggest the DCCC is allocating efficiently at the margin — "near-zero" is what both 2022 and 2024 now show more strongly than at any prior stage.

**The Spearman ρ as a diagnostic.** The negative ρ can be computed in real time during an election cycle using partial FEC filings. It replicates out-of-sample (ρ = −0.847 in 2022, p<0.001, corrected 2026-07-24; was −0.707 under 2026-07-23b, −0.747, then −0.750 earlier) — **the OOS cycle is again the stronger signal**, see §8.3's note on this ordering's history of flipping across corrections. A negative ρ emerging during a cycle is an early warning signal that allocation is drifting away from efficient targeting; that both cycles show it strongly is what matters operationally, not which one is marginally larger.

### Requires additional validation before operational use

**The seat gain point estimates.** Both the 2024 (+2.83, corrected 2026-07-24, was +13.24 under 2026-07-23b, +6.39, then +5.34 earlier) and 2022 (+3.22, corrected 2026-07-24, was +12.61, +7.77, then +6.79 earlier) figures are directionally robust and now much more conservative than the pre-ceiling reading — the +13.24/+12.61 figures were found to be substantially inflated by extrapolation into races with no historical support for the implied effect size (§7.3b). They still depend on β₁ = 5.475 (2024) / 5.222 (2022 OOS panel), each with SE ≈ 1.6-1.7; at the low end of the respective 95% CIs, the gains would be smaller still. The figures are best treated as upper bounds on the efficiency opportunity. The consistency between 2024 and 2022 across different estimation windows and competitive maps — again close in magnitude to each other under the ceiling fix — strengthens confidence in the order of magnitude.

**Race-specific recommendations.** Individual district recommendations are sensitive to small changes in spending assumptions and should be treated as screening criteria (high-MSG races deserve more scrutiny) rather than binding targets.

**The game-theoretic problem.** This model produces the optimal *unilateral* deviation from the observed 2024 spending equilibrium. Even a much smaller reallocation than the pre-ceiling figures implied (~$40-50M of party money actually moves under the ceiling fix, vs. the earlier reading's larger reallocation) would not go unnoticed by the NRCC and CLF. Republican counter-investment in the newly targeted races would partially flatten the gains. The true gain from implementing the optimizer recommendation is likely less than the +2.83 seat point estimate (corrected 2026-07-24, was +13.24 under 2026-07-23b), and could be smaller still if NRCC/CLF respond aggressively. The η sensitivity model (§9.4) quantifies this tradeoff and has been re-run against the current (ceiling-fix) baseline as of this pass. A more defensible operationalization: use MSG targeting for incremental late-cycle dollars rather than a wholesale early-cycle reallocation, which minimizes NRCC intelligence on the strategic shift.

**The private signals problem.** The model interprets the negative Spearman ρ as pure inefficiency — spending where marginal returns are lowest. A portion of the DCCC's Likely D over-investment may instead reflect rational responses to internal polling showing candidates in danger in seats the model rates as safe. Two observations mitigate but do not eliminate this concern: (1) the ρ pattern replicates in 2022 (ρ = −0.847, corrected 2026-07-24; was −0.707, then −0.747, then −0.750 earlier) — still highly significant, and now the larger of the two cycles' correlations again — suggesting it is structural rather than cycle-specific private intelligence, and (2) the equal-weight rule beats DCCC in both cycles without any private-signal advantage, which is harder to explain by private signals alone, though the margin is now narrow enough in both cycles that this is a weaker corroboration than it was under the pre-ceiling reading. The model should not be used to recommend abandoning spending in any Likely D seat without explicit validation against internal polling — the catastrophic downside of losing an unexpectedly competitive seat is not captured in the symmetric expected-value objective.

### 9.4 Adversarial Response Sensitivity (η Model)

To bound the game-theoretic risk quantitatively, the optimizer was extended with an adversarial response parameter η ∈ [0, 1]:

> **R_i(D_i) = R_i_base + η × max(0, D_i − D_i_observed)**

When D_i exceeds observed DCCC levels, the NRCC/CLF are assumed to match η cents per new DCCC dollar. The MSG gradient is corrected analytically: ∂log(D/t)/∂D = 1/D − (1+η)/t when spending is above observed levels (vs. 1/D − 1/t when η = 0). At η = 1 with d = r (equal spending), the corrected gradient → 0 — dollar-for-dollar matching exactly neutralizes the log-ratio improvement. The η-adjusted gradient is computed downstream of the persuasion ceiling's chain-rule correction (§7.3b), so this sweep already reflects the ceiling fix.

**Re-run 2026-07-24 against the current (persuasion-ceiling) baseline, DCCC = 215.12 seats, via `python scripts/run_backtest.py --skip-uncertainty --eta <η>` at each value.**

| η | E[seats] | vs DCCC (215.12) |
|---|---------|---------|
| 0.0 (no response) | 217.94 | +2.83 |
| 0.3 (30¢/dollar) | 217.36 | +2.25 |
| 0.5 (50¢/dollar) | 217.07 | +1.96 |
| 0.7 (70¢/dollar) | 216.80 | +1.69 |
| 1.0 (dollar-for-dollar) | 216.47 | +1.36 |

(Was, 2026-07-23b baseline DCCC=217.08: η=0.0 → 230.31 (+13.24); η=0.3 → 227.89 (+10.82); η=0.5 → 226.60 (+9.52); η=0.7 → 225.49 (+8.42); η=1.0 → 224.15 (+7.07).)

**Key finding, direction unchanged, magnitude much smaller under the ceiling fix:** Even under full dollar-for-dollar NRCC counter-spending, the optimizer yields a modest but positive expected seat gain above the DCCC baseline — +1.36 seats at η=1.0, down from +7.07 under the pre-ceiling reading. The efficiency gain is still not contingent on the NRCC failing to respond, but it is now small enough at high η that the practical case for a wholesale reallocation strategy (as opposed to late-cycle, low-η incremental targeting) is considerably weaker than the earlier table suggested. The practical implications remain directionally the same:

1. **Late-cycle deployments (η ≈ 0):** In September–October, ad inventory is largely sold out. NRCC/CLF cannot quickly redirect capital to newly targeted races. η effectively approaches 0, capturing the maximum gain.
2. **Early-cycle deployments (η ≈ 0.5–0.7):** Reallocation 6–12 months out gives the NRCC time to respond. The expected gain shrinks but remains substantial.
3. **Never deploy as a wholesale early reallocation:** Even at η = 1, the gain is positive, but it represents the *expected* outcome — the variance around that mean increases sharply if NRCC counter-investment raises competitiveness in targeted races unexpectedly.

The η model is available via `--eta` flag in `run_backtest.py`. Run with `--eta 0.0` for retrospective analysis; `--eta 0.5` for strategic planning scenarios.

### 9.5 Concentration Cap Gap (§4.6)

The spec requires quantifying whether the optimizer's seat gains depend on extreme concentration. The uncapped optimizer (no per-race cap) is run alongside the sensitivity grid. The concentration gap metric is:

> **Δ E[Seats]_concentration = E[Seats]_uncapped − E[Seats]_5%-cap**

**Result: gap = 0.0 in both 2024 and 2022.** The uncapped optimizer and the 5%-cap optimizer produce identical E[Seats]. This means the model's gains do not depend on extreme localization — the optimizer naturally distributes spending across enough races that the 5% cap per race is non-binding. This is a strong operability result: the committee can impose a concentration constraint without sacrificing any of the expected seat gain. The efficiency frontier is broad rather than concentrated.

**This is specific to the non-linear optimizer, not caps in general (added 2026-07-17).** Investigating a separate Paper III finding that the LP allocator (`optimize()`) gives a wildly different tier breakdown than the non-linear optimizer on the same live 2026 problem (`scripts/investigate_lp_vs_nonlinear_divergence.py`) showed the *opposite* pattern under the LP: run on identical inputs (same floor, same frozen MSG, same 15% cap), the LP funds only **7 of 434 races**, six of them hitting the per-race cap exactly, because its objective (`maximize msg @ s`) treats MSG as a fixed constant with no diminishing-returns mechanism — a pure greedy knapsack, unlike the non-linear path's naturally broad distribution described above. The cap is non-binding for `optimize_nonlinear()` specifically because diminishing returns already spread its allocation before any cap is reached; the LP has no such mechanism, so its cap binds immediately and its output is dominated by whichever handful of races happen to have the highest (floor-frozen, low-D-inflated) static MSG, not a tier-level judgment. See Paper III §8.2 for the full writeup.

### 9.6 Open-Seat Spending Elasticity (§8.3)

Open seats are the highest-variance races in any cycle — no incumbent anchor, different fundraising dynamics, higher quality candidates on both sides. The model now uses a Bayesian-shrunk spending elasticity for open seats (β_OS^calib) rather than applying β_RC directly.

The procedure: (1) estimate the open-seat interaction term β₄ = β_panel^OS − β_RC from the 2012–2022 panel; (2) set τ by covariate distance between repeat-challenger pairs and open-seat population; (3) compute posterior β_OS^calib = κ × β_panel^OS + (1 − κ) × β_RC; (4) report β_OS^lb at the 90th-percentile conservative bound.

**Operational implication:** β_OS^calib replaces β_RC in `c_spend_i` for all open-seat races in the optimizer and MSG computations. MSG rankings for open seats will shift relative to the uncalibrated model. Calibration output is stored in `data/processed/open_seat_calibration.json` and includes κ, β_OS^calib, β_OS^lb, and the posterior SE. Until a full cycle is run to validate β_OS^calib OOS, treat open-seat MSG rankings as directionally useful but not as precise as incumbent/challenger rankings.

### Interesting but not directly operational

- **Brier score comparison with Cook** — validates model calibration; as of the 2026-07-24 rerun the model beats Cook in 2024 (0.0312 vs 0.0364, +14%) but **still loses to Cook in 2022 OOS** (0.0360 vs 0.0340, model +5.9% worse — a slightly larger gap than 2026-07-23b's +2.9%). This direction (Cook wins calibration in the OOS cycle) has now been consistent across three pipeline states (elections.py-fix era, 2026-07-23b, 2026-07-24), even as exact percentages moved with each fix (see §5.3, §8.2's note). Calibration quality clearly varies across cycles, and this specific comparison should not be cited as "the model beats Cook in both cycles" — it does not, in the current pipeline, in 2022.
- **Spending distribution by category** — descriptive of past DCCC behavior, useful for context but not prescriptive.
- **Absolute expected seat counts** — model-specific; what matters is the *relative* comparison across strategies.

---

## 10. Limitations

### 10.1 Causal identification

β₁ is estimated from observational data with a repeat-challenger design. The design controls for district and candidate identity across cycles, but cannot rule out all confounders. In particular:
- **Candidate quality endogeneity**: Strong candidates raise more money and are harder to beat. The model uses total D spending as the explanatory variable, which conflates spending with candidate quality. `indiv_share` (α₅) was added as a quality proxy (§5.4) and is marginally significant, but its *negative* coefficient reveals it proxies PAC targeting rather than grassroots quality — the endogeneity concern is partially addressed but not eliminated.
- **Private signals**: See §9 (Actionability) for the full treatment.
- **β_RC's identifying sample is heavily skewed toward Safe R, not the competitive tiers the recommendation is about (added 2026-07-17, re-verified 2026-07-24 alongside the persuasion-ceiling investigation).** `identify_repeat_pairs()` restricts to D-challenger-vs-R-incumbent pairs by construction (§4.4). Bucketing the resulting 118 pairs by the district's PVI-derived tier (`scripts/investigate_msg_low_d_extrapolation.py`) shows **72% (85/118) are Safe R**, while the three competitive tiers (Toss-Up/Lean D/Lean R) — the tiers the model's headline efficiency claim is actually about — contribute only **12% (14/118)**. Split-sample point estimates suggest a real difference (all-pairs β_RC=5.475; Safe-R-only=4.656; competitive-only=2.813, roughly half), but a formal interaction test is **not** statistically significant (coef=−2.696, p=0.598) — with only 14 competitive-tier observations, this test is underpowered to detect anything but a large difference, so "not significant" should be read as "cannot confirm a difference exists," not "confirmed the elasticity is uniform across tiers." **This does not by itself explain the pre-ceiling-fix's 45% Safe-tier concentration finding** — a separate check (`outputs/msg_low_d_extrapolation_check.csv`) confirmed today's live candidate-spending floors are well *within* the historical panel's observed D_total range in every tier (the panel's minimum Safe R observation was $40, Likely R was $74 — lower than any live 2026 floor), so the Safe-tier over-concentration was not itself an out-of-sample extrapolation problem in this narrow sense. The persuasion ceiling (§7.3b) addresses a related but distinct mechanism — the *gradient* blowing up as D→0, not the estimation sample's tier composition — and the two findings should not be conflated: this section's composition concern is about whether the single pooled β₁ genuinely transfers to competitive races, which the ceiling fix does not resolve and remains open.

### 10.2 Out-of-sample calibration degrades

**Corrected 2026-07-24, persuasion-ceiling fix.** The model's win probability calibration (Brier score) is better than Cook in 2024 (+14%) but **worse** than Cook in 2022 (model 0.0360 vs Cook 0.0340, model −5.9%) — a slightly larger gap than 2026-07-23b's −2.9%, but the same direction as every pipeline state since the elections.py fix. This is expected for an OOS test — the 2012–2020 panel misses 2022 redistricting and political context — and the efficiency finding (optimizer beats DCCC) is robust to this calibration degradation, but probability-based use cases (which races are actually in play) require more caution.

### 10.3 Non-linear optimizer: numerical scaling

A subtle numerical scaling bug was identified and corrected during the audit. Raw party allocations are on the order of $0–$70M per race, while the MSG gradient values are on the order of 1e-7 (seats per dollar). In SLSQP's convergence check the projected Lagrangian gradient (MSG × allocation scale) appeared near-zero relative to the solver's `ftol=1e-10` threshold, causing the optimizer to terminate after a single iteration at the DCCC starting point and report false convergence.

The fix was to scale party allocations to $M units before passing to SLSQP and apply the corresponding chain-rule correction to the gradient. The result as of the 2026-07-22 gradient/budget-scope corrections was **220.52 expected seats (+5.34 vs DCCC = 215.18)** — superseded 2026-07-23a by the elections.py MN/ND fix to **225.19 expected seats (+6.39 vs DCCC = 218.80)** — superseded again 2026-07-23b by the NRCC/σ-model/optimizer-diagnostic fix to **230.31 expected seats (+13.24 vs DCCC = 217.08)** — superseded once more, 2026-07-24, by the persuasion-ceiling fix (top-of-document flag) to **217.94 expected seats (+2.83 vs DCCC = 215.12)**, see §7.3/§7.3b. Unlike the earlier corrections in this chain, the 2026-07-24 fix *lowered* the gain rather than raising it — 2026-07-23b's +13.24 was itself found to be substantially an artifact of a different bug (near-zero-floor gradient extrapolation), not a further refinement of the true effect size. This supersedes the erroneous +0.88 (pre-scaling-fix) and the interim +4.46 (post-scaling-fix, pre-α₅). A subsequent addition of `indiv_share` (α₅ = −3.99) inflated the apparent gain to +11.9 by suppressing the DCCC baseline by 6.56 seats — without changing the optimizer's allocation at all (confirmed: max allocation difference between α₅ and no-α₅ optimizer = $0.00 across 433 races; not recomputed against the current pipeline, see §5.4's note). Zeroing α₅ is now hardcoded in `src/backtest/model/margin.py` rather than patched in the JSON, so re-running estimation can never revert it. The 2022 OOS results were also affected: the old aggregate CSV (DCCC=206.49, gain=+5.54, ρ=−0.380) was generated with α₅=−3.99 active in the OOS estimation path. With α₅=0 consistently enforced, the correct 2022 OOS figures were DCCC=214.87, gain=+6.79, ρ=−0.647 (p<0.001) — the ρ figure was itself superseded again by the MSG gradient correction (§7.2), giving ρ=−0.750; the α₅ fix and the gradient fix are independent corrections. Superseded again 2026-07-23a by the elections.py MN/ND fix (DCCC=217.76, gain=+7.77, ρ=−0.747), then 2026-07-23b by the NRCC/σ-model/optimizer fix (DCCC=215.47, gain=+12.61, ρ=−0.707), then 2026-07-24 by the persuasion-ceiling fix (DCCC=213.37, gain=+3.22, ρ=−0.847) — see §8.2's table, which reflects the current state.

Global optimality of 217.94 (230.31 under 2026-07-23b; 225.19 after the elections.py fix alone; 220.52 before any of these) is not guaranteed (SLSQP is a local solver), but the result is robust to initialization and consistent with the response-curve analysis. SLSQP's `maxiter` was also raised from 500/1000 to 3000 and `ftol` tightened from 1e-10 to 1e-12 (2026-07-24) — the ceiling's `exp(·)` saturation adds curvature near the cap that needed more iterations to resolve to a genuine `status=optimal` rather than an iteration-limit cutoff.

### 10.4 Budget decomposition uncertainty

Candidate vs. party spending is inferred from FEC filing categories. Some coordination between candidate and party committees may be mis-attributed. The $465M party budget estimate is approximate.

### 10.5 Republican spending treated as fixed (partially addressed)

The base model takes Republican spending as given. §9 (Actionability) describes the operational implications, and §9.4 (Adversarial Response) quantifies the seat gain under adversarial NRCC matching via the η parameter. Even at η = 1 (dollar-for-dollar response), the optimizer yields +1.36 seats over DCCC (corrected 2026-07-24, persuasion-ceiling fix — was +7.07 under 2026-07-23b; +1.88 against an even earlier, stale placeholder baseline before that). However, the η model is a reduced-form approximation — it does not model the NRCC's *targeting* of counter-spending, only the total magnitude. A Nash equilibrium formulation is left as future work.

### 10.6 σ model ordering

The estimated σ model does not produce the theoretically expected ordering (open seat > challenger > incumbent). This is likely a selection effect — challengers run where they have advantages, reducing residual scatter — but it is a departure from prior assumptions and warrants scrutiny.

### 10.7 Data coverage gaps identified during audit

An audit of all raw data files against the pipeline identified three gaps. Each was investigated and either corrected or documented as future work.

**Gap 1 — CVAP (spending intensity per voter).**  
The `data/raw/census/` directory contains 2022 ACS5 CVAP estimates for all 433 districts. These were not originally used in the model. During the audit, a `log((D+R)/CVAP)` spending-intensity covariate was tested. OLS on the historical panel produced a coefficient α₄ = −2.02, but including it *degraded* out-of-sample Brier from 0.0299 to 0.0345. Root cause: endogeneity. High-spending races are structurally more competitive (DCCC over-invests where wins are needed most), so OLS picks up selection bias rather than a causal effect of spending intensity. CVAP is now loaded and plumbed through all model functions (parameter α₄ is defined in `MarginModelCoefficients`), but constrained to α₄ = 0.0 pending proper instrumental variable estimation. The CVAP-to-district mapping and all supporting infrastructure are in place for future work.

**Gap 2 — NRCC coordinated expenditures — CLOSED 2026-07-23b, and the original root-cause diagnosis here was wrong.** The FEC pipeline produced empty files for all `coordinated_nrcc_*.csv` outputs, for every cycle 2012–2026. The root cause was **not** the DEMO_KEY rate limit this entry originally guessed — it was that `NRCC_COMMITTEE_ID` in `scripts/fetch_data.py` was simply the wrong FEC committee ID (`C00075473`, which belongs to "CMS Energy Corporation Employees for Better Government," an unrelated corporate PAC, verified directly against fec.gov), so every Schedule F query legitimately returned zero rows — a non-party committee has no coordinated party expenditures to report, regardless of API key or rate limit. `scripts/fetch_live_ies.py`'s HMP and CLF committee IDs were also wrong in the same way (HMP's `C00500884` didn't resolve to a real match; CLF's `C00571372` was actually "Right to Rise USA," a terminated 2016 presidential super PAC). All three corrected (NRCC → `C00075820`, HMP → `C00495028`, CLF → `C00504530`) and re-fetched with a registered API key for all 8 cycles — `coordinated_expenditures_{cycle}.csv` now contains real R-side data everywhere. Actual magnitude, now measured rather than estimated: 2024 NRCC coordinated spend = **$2.97M**, far smaller than this entry's original $30–50M guess (that guess was reasoning from Republican IE totals as a proxy, which turned out to be a poor one — coordinated-expenditure and independent-expenditure spend are not comparable in scale). Every headline number in this document past the top-of-document flag reflects this fix.

**Gap 3 — State party coordinated expenditures.**  
FEC "Other Transactions" (24K filings, `data/raw/bulk_all/itoth.txt`) include committee-to-committee transfers. A subset of these are state Democratic party coordinated expenditures into House races not attributed to the DCCC. Parsing the full 1M-row file to isolate House 24K coordinateds was out of scope for this audit; it is documented here as future work. The likely magnitude is small relative to IEs, but this represents an undercount of total Democratic coordination in some districts.

---

## 11. Output Files

All outputs are in `outputs/`.

### Charts

| File | Description |
|------|-------------|
| `msg_efficiency.png` | MSG vs. D total spend for competitive races. The headline Spearman ρ = −0.809 result (§7.2, corrected 2026-07-24, persuasion-ceiling fix; was −0.789 under 2026-07-23b; −0.536 after the elections.py fix, −0.582 before that). This file and four siblings (`model_calibration.png`, `spending_by_cook.png`, `spending_ratio_vs_pvi.png`, `allocator_comparison.png`) are generated by `scripts/make_charts.py`, a separate script from `run_backtest.py` (which generates `efficiency_frontier.png`/`allocation_difference.png` directly) — both scripts, plus every other chart-generating script referenced in this document, were rerun 2026-07-24 and all outputs are current as of that date. |
| `model_calibration.png` | Predicted P_win bins vs. actual D win rate. Model vs. Cook calibration comparison. |
| `spending_by_cook.png` | Median D and R spending by Cook category; box plots for competitive races. |
| `allocator_comparison.png` | Expected seats comparison: DCCC, Cook-implied, equal-weight, model optimizer. |
| `allocator_spending_by_race.png` | Per-race spending across the 53 competitive races, all four strategies overlaid, sorted by optimizer-minus-DCCC delta (`scripts/plot_allocator_comparison.py`). Renamed 2026-07-22 from `allocator_comparison.png`, which collided with the chart above — the two scripts were silently overwriting each other's output under the same filename. |
| `permutation_tests_null_distributions.png` | Both permutation-test null distributions (§7.2b) plotted against DCCC's real observed values (`scripts/plot_permutation_tests.py`). |
| `allocation_shift.png` | Per-district recommended vs. DCCC allocation shift. Top and bottom 20 races. |
| `spending_ratio_vs_pvi.png` | D share of total spending vs. Cook PVI for all 433 races. |
| `efficiency_frontier.png` | E[Seats] vs. risk (Var[Seats]) across γ and cap combinations (pipeline output). |
| `allocation_difference.png` | Scatter of recommended vs. observed shares, competitive races (pipeline output). |
| `preelection_allocation_comparison.png` | Pre-election model allocation comparison (separate pre-election run). |

### Data tables

| File | Description |
|------|-------------|
| `race_table_baseline.csv` | Per-race: PVI, spending, μ_hat, σᵢ, P_win, MSG, recommended share, observed share, outcome. |
| `aggregate_summary_baseline.csv` | Top-line statistics: E[Seats], Spearman ρ, n_competitive, n_material_divergence. |
| `spearman_by_cook_category.csv` | Spearman ρ broken out by Cook rating category. |
| `race_table_preelection.csv` | Race table from the pre-election model run. |
| `permutation_tests.json` | Permutation-test results for the Spearman ρ and allocation-efficiency tests (§7.2b). |
| `permutation_null_spearman.csv` | Raw null distribution (2000 draws) for the Spearman ρ permutation test — feeds `plot_permutation_tests.py`. |
| `permutation_null_allocation.csv` | Raw null distribution (2000 draws) for the allocation-efficiency permutation test — feeds `plot_permutation_tests.py`. |

### Model artifacts

| File | Description |
|------|-------------|
| `data/processed/margin_model_coef.json` | Estimated α and β coefficients. |
| `data/processed/sigma_model.json` | σᵢ model intercept and coefficients. |
| `data/processed/beta_rc.json` | β_RC point estimate, SE, and n_pairs. |
| `data/processed/beta_rc_bootstrap.json` | Non-parametric bootstrap distribution of β_RC (§5.2). |

### Live 2026 pipeline

| File | Description |
|------|-------------|
| `data/live/spending_live.json` | Cumulative per-district D/R spending snapshot (updated by `fetch_live_ies.py`). |
| `data/live/msg_live.csv` | Real-time MSG ranking of competitive races, sorted by MSG descending. |
| `data/live/fetch_log.jsonl` | Append-only audit trail of each fetch run (timestamp, cycle, IE count, top district). |

Run `python scripts/fetch_live_ies.py --api-key YOUR_KEY` daily during the cycle. Set `FEC_API_KEY` in the environment to avoid passing the key on the command line. Add `--lookback-hours 48` during accelerated-reporting windows (final 20 days). Committees tracked (corrected 2026-07-23b — the previous IDs listed here were wrong for three of the four committees; see §10.7 Gap 2): DCCC (C00000935), NRCC (C00075820), HMP (C00495028), CLF (C00504530).

---

*Generated from `scripts/run_estimation.py` + `scripts/run_backtest.py` + `scripts/make_charts.py` + `scripts/make_summary_chart.py` + `scripts/plot_allocator_comparison.py` + `scripts/plot_response_curve.py` + `scripts/plot_single_race_response.py` + `scripts/fetch_live_ies.py`.*
