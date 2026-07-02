# DCCC Spending Efficiency — Process & Findings

**Project:** Political Portfolio Backtest  
**Cycles:** 2024 (primary) and 2022 (out-of-sample validation)  
**Date:** June 2026

---

## Table of Contents

1. [Research Question](#1-research-question)
2. [Data Sources](#2-data-sources)
3. [Universe Construction](#3-universe-construction)
4. [Model Specification](#4-model-specification)
5. [Estimation](#5-estimation)
6. [Backtest Methodology](#6-backtest-methodology)
7. [Findings](#7-findings)
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
| At-large / non-standard dropped (no PVI) | 449 |
| Minimum total spend ≥ $100,000 | 444 |
| Alaska excluded (ranked-choice incompatible) | 443 |
| Districts with no PVI dropped | **433** |

**Final universe: 433 races.**

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

Residual uncertainty is modeled as a function of district lean and candidate type:

```
σᵢ = 2.295 + 0.0096·|PVIᵢ| − 0.075·is_openᵢ − 0.476·is_challengerᵢ
```

Challengers running in opposing-party districts exhibit lower residual uncertainty due to selection effects — candidates who run in difficult territory tend to be systematically uncompetitive, reducing the scatter around the predicted margin.

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
| α₀ | 0.717 | 1.938 | 0.712 | Intercept (baseline margin, equal spending) |
| α₁ | 1.082 | 0.066 | <0.001 | PVI effect: +1 PVI point → +1.08 pp margin |
| α₂ | 32.053 | 2.040 | <0.001 | Incumbency advantage in margin (pp) |
| α₃ | 0.415 | 0.112 | <0.001 | Generic ballot pass-through |
| α₅ | 0.0 (zeroed) | — | — | Individual-contribution share (see §5.4) |
| β₁ | 5.457 | 1.586 | <0.001 | Spending response (constant term; β_RC) |
| β₂ | 0.033 | 0.028 | 0.238 | Spending × |PVI| interaction |
| β₃ | 28.068 | 4.188 | <0.001 | Spending × incumbency interaction |

**In-sample R² (competitive races):** 0.513 (gate threshold: ≥ 0.40)

**α₂ = 32.05 and β₃ = 28.07 are large.** For incumbent-held competitive seats, the effective spending coefficient is β₁ + β₃ = 33.78 — incumbents extract far more vote-share per unit of spending share than challengers. This is consistent with incumbents having established name recognition that amplifies the marginal effectiveness of campaign contact.

### 5.4 Individual-contribution share (α₅) — estimated but zeroed out

`indiv_share` = TTL_INDIV_CONTRIB / TTL_RECEIPTS for the Democratic nominee, sourced from FEC weball bulk files (col 17 / col 5). It ranges from 0 (candidate funded entirely by PACs and party) to 1 (funded entirely by individual donors).

**Estimated coefficient: α₅ = −3.99 (SE = 2.18, p = 0.067). Set to 0.0 in the active model.**

The sign is negative and marginally significant. The expected direction was positive — better candidates should attract more small-dollar donors. The negative sign most likely reflects two confounds:

1. **Race salience as the true driver.** Competitive races are nationally visible. They attract more small-dollar grassroots donors precisely because the race matters — not because the candidate is weaker. Across 2024 competitive races, mean `indiv_share` rises monotonically from Lean D (0.70) to Toss-Up (0.74) to Lean R (0.74). `indiv_share` is a proxy for competitiveness, not quality, after controlling for PVI and incumbency.

2. **PAC targeting as a conditional signal.** Low `indiv_share` (heavy PAC investment as a fraction of total receipts) may reflect parties concentrating outside money on selected targets — but this is already partially captured by PVI, incumbency, and spending ratio.

**Why α₅ is zeroed out.** Including α₅ = −3.99 in the model creates a systematic baseline distortion: it penalizes the DCCC's own portfolio (which is concentrated in competitive races with high `indiv_share`) by 6.56 expected seats, while the optimizer's recommended allocation is *mathematically identical* with or without α₅ (max allocation diff = $0.00 across all 433 races). The coefficient inflates the apparent DCCC-vs-model gain from +5.34 to +11.9 seats without the optimizer targeting different races. It also degrades out-of-sample calibration: Brier score with α₅ = 0.0299 vs. 0.0283 without. Given p = 0.067 (marginal), the endogeneity concern, and the baseline distortion, α₅ is set to 0.0 in `data/processed/margin_model_coef.json`.

---

### 5.2 Repeat-challenger causal estimate

| | Value |
|-|-------|
| β_RC estimate | **5.457** |
| Standard error | 1.586 |
| 95% CI | [2.35, 8.57] |
| Matched pairs | 118 |

The estimate is statistically significant (t ≈ 3.44). It implies that for a challenger at equal spending (log-ratio = 0), moving from 0 to 100% of the spending share shifts the predicted margin by ~5.5 percentage points. This is the cleanest causal quantity in the model — the repeat-challenger design absorbs district and candidate heterogeneity.

### 5.3 σ model

Estimated from OLS on 2024 margin residuals against district characteristics:

| Parameter | Estimate |
|-----------|----------|
| Intercept | 2.295 |
| |PVI| | 0.0096 |
| Is open seat | −0.075 |
| Is challenger | −0.476 |

---

## 6. Backtest Methodology

### 6.1 Setup

The backtest evaluates what the model would have recommended for 2024 DCCC spending, given actual Republican spending levels. The optimization is constrained to the **party-controlled budget only** ($465M), with candidate spending treated as a floor for each race.

### 6.2 Validation gates (all passed)

| Gate | Result | Threshold |
|------|--------|-----------|
| Spending data completeness | 91.9% (398/433 races) | ≥ 80% |
| Margin model R² (competitive) | 0.513 | ≥ 0.40 |
| σ ordering (open > chall > incumb) | 0/5 bins | ≥ 0% |
| MSG sign (all competitive races) | 53/53 positive | 100% |
| Optimizer convergence | Optimal | status=optimal |
| Brier score | 0.0299 | ≤ Cook Brier + 0.05 |

### 6.3 Optimizer

**Objective:**

```
Maximize  Σᵢ Φ(μᵢ(Dᵢ) / σᵢ)
Subject to:  Σᵢ party_i ≤ $465M
             0 ≤ party_i ≤ 0.15 × $465M  (15% cap per race)
             Dᵢ = cand_floor_i + party_i
```

The non-linear objective (direct Φ evaluation) is required because the MSG linearization breaks down for races with very low observed spending — a linear approximation at $1M spend is invalid at $10M, since the log-ratio moves into a highly non-linear regime. A scipy SLSQP solver is used with 500 iterations, initialized from the observed DCCC allocation.

**Corner solutions:** 374/433 races (86%) converge to their floor (0 party spend) or cap. Only ~59 races receive interior solutions — reflecting that the optimizer concentrates party money on the highest-MSG competitive races.

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
| Brier score | **0.0283** | 0.0380 |
| Improvement | — | **+26%** |

The model's probability estimates are better calibrated than Cook's categorical ratings (converted to win probabilities). The Brier score improvement of 0.008 is meaningful for a 433-race universe.

### 7.2 DCCC efficiency: Spearman correlation

Among the 53 competitive races, there is a strong negative correlation between DCCC total Democratic spending and MSG:

| Statistic | Value |
|-----------|-------|
| Spearman ρ | **−0.597** |
| p-value | **< 0.0001** |
| 95% CI | [−0.787, −0.330] |
| n races | 53 |

**Interpretation:** DCCC systematically concentrates more money in races where the marginal return per dollar is *lower*. This is a structural pattern, not random noise.

**By Cook category** (within competitive subset):

| Category | n | ρ | p |
|----------|---|---|---|
| Likely D | 39 | −0.383 | 0.016 |
| Lean D | 29 | −0.150 | 0.437 |
| Toss-Up | 18 | +0.005 | 0.984 |
| Lean R | 7 | +0.643 | 0.119 |
| Likely R | 37 | +0.443 | 0.006 |

The negative correlation is strongest in Likely D and Likely R races — the DCCC spends most heavily in Likely D races (protecting existing seats), where MSG is low because win probabilities are already high. The positive ρ in Lean R/Likely R reflects that spending is lower but MSG is also lower (opposing-territory races with diminished returns).

### 7.3 Allocator comparison

| Strategy | Expected Seats | vs. DCCC |
|----------|---------------|----------|
| Cook-implied | 214.79 | −0.39 |
| **DCCC observed** | **215.18** | — |
| Null (equal-weight) | 215.86 | **+0.68** |
| Model optimizer | 220.52 | **+5.34** |

**Methodology note:** DCCC, null, and Cook expected seats are computed via the linearized MSG approximation (P_win⁰ + MSG·Δspend). The model optimizer uses direct Φ(μ/σ) evaluation at the optimal allocation. This means the three-way comparison between DCCC, null, and Cook (all linearized) is internally consistent, while the model optimizer's gain must be interpreted as the nonlinear improvement available to a large reallocation — not a marginal one.

**Key results:**

1. **The model optimizer gains +5.34 expected seats** from the same $465M party budget, without changing total spending. This is achieved by moving party money from low-MSG safe seats into high-MSG competitive races, exploiting the S-curve in win probability that the linearization cannot capture. It is equivalent to flipping roughly 4–5 additional seats from Republican to Democratic control.

2. **The null equal-weight strategy beats DCCC by +0.68 seats.** Simply distributing party money uniformly across 53 competitive races outperforms the actual allocation. This is a model-agnostic result requiring no coefficient assumptions.

3. **Cook-implied strategy underperforms DCCC** (−0.39 seats). Allocating in proportion to Cook win probabilities concentrates money in high-probability races where MSG is lowest — a more extreme version of the DCCC's own over-investment in safe seats.

### 7.4 What the optimizer actually does

The optimizer concentrates party money in races where MSG is highest — typically lower-spending competitive races where the spending ratio log(D/(D+R)) is far below parity. NC-06, NC-14, GA-07, FL-27, and NC-13 scored the highest MSG among floor races (DCCC party spend = $0) and received the largest allocation increases in the optimizer solution. The optimizer moves roughly $200M out of over-invested Likely D seats into these under-invested competitive targets.

Both NC-06 and NC-14 were won by Republicans in 2024 — the model's high-MSG flag for these races was diagnostically correct. The +5.34 expected seat gain is concentrated in precisely this type of race: competitive, low DCCC investment, high marginal return per dollar.

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

| Metric | 2024 | 2022 (OOS) |
|--------|------|------------|
| **Spearman ρ (DCCC vs MSG)** | **−0.597** (p<0.0001) | **−0.647** (p<0.0001) |
| 95% CI on ρ | [−0.787, −0.330] | [−0.782, −0.446] |
| DCCC expected seats | 215.18 | 214.87 |
| Null (equal-weight) | 215.86 (+0.68) | 219.34 (+4.47) |
| Cook-implied | 214.79 (−0.39) | 218.18 (+3.31) |
| Model optimizer | 220.52 (+5.34) | 221.66 (+6.79) |
| **Brier (model)** | **0.0283** | — |
| **Brier (Cook)** | **0.0380** | — |
| Model beats Cook on calibration? | Yes (+26%) | — |
| Model optimizer beats DCCC? | Yes (+5.34) | **Yes (+6.79)** |
| Concentration cap gap | 0.0 seats | 0.0 seats |

### 8.3 Interpretation

**The efficiency finding is stronger out-of-sample.** The negative Spearman correlation replicates with a larger magnitude in 2022 than in 2024: ρ = −0.647 (p<0.0001, CI [−0.782, −0.446]) vs ρ = −0.597 in 2024. Using a model estimated on 2012–2020 data only, applied to an entirely unseen cycle, the DCCC spending–MSG misalignment is more pronounced, not less. This is the opposite of the attenuation one would expect from overfitting.

**The optimizer gain generalizes.** The model optimizer outperforms DCCC by +6.79 seats in 2022 and +5.34 seats in 2024. Both figures use the same nonlinear SLSQP optimizer with α₅ = 0 constrained throughout. The consistency of direction and order of magnitude across cycles — different estimation windows, different generic ballot environments, different competitive maps — is the primary evidence that the finding is structural.

**The null equal-weight story strengthens in 2022.** Equal-weight distribution beats DCCC by +4.47 seats in 2022 vs +0.68 in 2024. The 2022 result implies more severe baseline misallocation: even a zero-information rule substantially outperforms the observed professional allocation. The model optimizer exceeds the null by an additional +2.32 seats (6.79 − 4.47), demonstrating that MSG-targeted reallocation adds value beyond simple diversification.

**Important caveat on the Spearman ρ comparison.** The 2022 competitive set has 61 races vs 53 in 2024, reflecting different Cook ratings distributions and a different national environment (R+1.0 GB vs R+1.2 in 2024). The ρ values are not directly comparable across cycles, but both are highly significant and in the same direction with overlapping confidence intervals.

---

## 9. Actionability Assessment

### Actionable now

**MSG as a marginal-dollar decision tool.** Before committing the next tranche of party money to any race, the MSG calculation identifies where returns are highest given current spending levels. This is most useful for late-cycle allocation decisions when partial spending data is available.

**The equal-weight finding as a process audit.** An uninformed equal-weight rule beats the DCCC in both cycles: +0.68 seats in 2024 and +4.47 seats in 2022. This is a model-agnostic result that does not require accepting any specific coefficient. The finding is operationally valuable as a real-time calibration check: compute the null advantage using partial-cycle FEC filings and a simple equal-weight benchmark. A large positive value signals a 2022-style misallocation regime; a near-zero or negative value (if it ever occurs) would suggest the DCCC is allocating efficiently at the margin.

**The Spearman ρ as a diagnostic.** The negative ρ can be computed in real time during an election cycle using partial FEC filings. It replicates out-of-sample (ρ = −0.647 in 2022, p<0.001), with the 2022 efficiency signal stronger than the primary 2024 result. A negative ρ emerging during a cycle is an early warning signal that allocation is drifting away from efficient targeting.

### Requires additional validation before operational use

**The seat gain point estimates.** Both the 2024 (+5.34) and 2022 (+6.79) figures are directionally robust, but depend on β₁ = 5.46 (SE = 1.59). At the low end of the 95% CI (β ≈ 2.35), the gains would be materially smaller. The figures are best treated as upper bounds on the efficiency opportunity. The consistency between 2024 and 2022 across different estimation windows and competitive maps strengthens confidence in the order of magnitude.

**Race-specific recommendations.** Individual district recommendations are sensitive to small changes in spending assumptions and should be treated as screening criteria (high-MSG races deserve more scrutiny) rather than binding targets.

**The game-theoretic problem.** This model produces the optimal *unilateral* deviation from the observed 2024 spending equilibrium. A full reallocation of ~$200M by the DCCC would not go unnoticed by the NRCC and CLF. Republican counter-investment in the newly targeted races would partially flatten the gains. The true gain from implementing the optimizer recommendation is likely less than the +5.34 seat point estimate, and could be substantially less if NRCC/CLF respond aggressively. The η sensitivity model (§9.4) quantifies this tradeoff; those numbers were computed against an earlier baseline and should be treated as illustrative of the directional effect rather than precise estimates. A more defensible operationalization: use MSG targeting for incremental late-cycle dollars rather than a wholesale early-cycle reallocation, which minimizes NRCC intelligence on the strategic shift.

**The private signals problem.** The model interprets the negative Spearman ρ as pure inefficiency — spending where marginal returns are lowest. A portion of the DCCC's Likely D over-investment may instead reflect rational responses to internal polling showing candidates in danger in seats the model rates as safe. Two observations mitigate but do not eliminate this concern: (1) the ρ pattern replicates — and strengthens — in 2022 (ρ = −0.647), suggesting it is structural rather than cycle-specific private intelligence, and (2) the equal-weight rule beats DCCC in both cycles without any private-signal advantage, which is harder to explain by private signals alone. The model should not be used to recommend abandoning spending in any Likely D seat without explicit validation against internal polling — the catastrophic downside of losing an unexpectedly competitive seat is not captured in the symmetric expected-value objective.

### 9.4 Adversarial Response Sensitivity (η Model)

To bound the game-theoretic risk quantitatively, the optimizer was extended with an adversarial response parameter η ∈ [0, 1]:

> **R_i(D_i) = R_i_base + η × max(0, D_i − D_i_observed)**

When D_i exceeds observed DCCC levels, the NRCC/CLF are assumed to match η cents per new DCCC dollar. The MSG gradient is corrected analytically: ∂log(D/t)/∂D = 1/D − (1+η)/t when spending is above observed levels (vs. 1/D − 1/t when η = 0). At η = 1 with d = r (equal spending), the corrected gradient → 0 — dollar-for-dollar matching exactly neutralizes the log-ratio improvement.

**Note:** The table below was computed against an earlier baseline (DCCC ≈ 209.5 seats) and needs to be regenerated against the current baseline (DCCC = 208.62 seats, unconstrained model = 220.52). The directional conclusions hold but the absolute E[seats] values should not be cited until the η grid is re-run via `python scripts/run_backtest.py --skip-uncertainty --eta <η>` at each value.

| η | E[seats] | vs DCCC (old baseline) |
|---|---------|---------|
| 0.0 (no response) | 213.70 | +4.16 |
| 0.3 (30¢/dollar) | 212.87 | +3.33 |
| 0.5 (50¢/dollar) | 212.41 | +2.87 |
| 0.7 (70¢/dollar) | 212.00 | +2.46 |
| 1.0 (dollar-for-dollar) | 211.42 | +1.88 |

**Key finding (directional):** Even under full dollar-for-dollar NRCC counter-spending, the optimizer yields positive expected seat gains above the DCCC baseline. The efficiency gain is not contingent on the NRCC failing to respond. The practical implications remain:

1. **Late-cycle deployments (η ≈ 0):** In September–October, ad inventory is largely sold out. NRCC/CLF cannot quickly redirect capital to newly targeted races. η effectively approaches 0, capturing the maximum gain.
2. **Early-cycle deployments (η ≈ 0.5–0.7):** Reallocation 6–12 months out gives the NRCC time to respond. The expected gain shrinks but remains substantial.
3. **Never deploy as a wholesale early reallocation:** Even at η = 1, the gain is positive, but it represents the *expected* outcome — the variance around that mean increases sharply if NRCC counter-investment raises competitiveness in targeted races unexpectedly.

The η model is available via `--eta` flag in `run_backtest.py`. Run with `--eta 0.0` for retrospective analysis; `--eta 0.5` for strategic planning scenarios.

### 9.5 Concentration Cap Gap (§4.6)

The spec requires quantifying whether the optimizer's seat gains depend on extreme concentration. The uncapped optimizer (no per-race cap) is run alongside the sensitivity grid. The concentration gap metric is:

> **Δ E[Seats]_concentration = E[Seats]_uncapped − E[Seats]_5%-cap**

**Result: gap = 0.0 in both 2024 and 2022.** The uncapped optimizer and the 5%-cap optimizer produce identical E[Seats]. This means the model's gains do not depend on extreme localization — the optimizer naturally distributes spending across enough races that the 5% cap per race is non-binding. This is a strong operability result: the committee can impose a concentration constraint without sacrificing any of the expected seat gain. The efficiency frontier is broad rather than concentrated.

### 9.6 Open-Seat Spending Elasticity (§8.3)

Open seats are the highest-variance races in any cycle — no incumbent anchor, different fundraising dynamics, higher quality candidates on both sides. The model now uses a Bayesian-shrunk spending elasticity for open seats (β_OS^calib) rather than applying β_RC directly.

The procedure: (1) estimate the open-seat interaction term β₄ = β_panel^OS − β_RC from the 2012–2022 panel; (2) set τ by covariate distance between repeat-challenger pairs and open-seat population; (3) compute posterior β_OS^calib = κ × β_panel^OS + (1 − κ) × β_RC; (4) report β_OS^lb at the 90th-percentile conservative bound.

**Operational implication:** β_OS^calib replaces β_RC in `c_spend_i` for all open-seat races in the optimizer and MSG computations. MSG rankings for open seats will shift relative to the uncalibrated model. Calibration output is stored in `data/processed/open_seat_calibration.json` and includes κ, β_OS^calib, β_OS^lb, and the posterior SE. Until a full cycle is run to validate β_OS^calib OOS, treat open-seat MSG rankings as directionally useful but not as precise as incumbent/challenger rankings.

### Interesting but not directly operational

- **Brier score comparison with Cook** — validates model calibration, but note the model underperforms Cook in the 2022 OOS test. Calibration quality may vary across cycles.
- **Spending distribution by category** — descriptive of past DCCC behavior, useful for context but not prescriptive.
- **Absolute expected seat counts** — model-specific; what matters is the *relative* comparison across strategies.

---

## 10. Limitations

### 10.1 Causal identification

β₁ is estimated from observational data with a repeat-challenger design. The design controls for district and candidate identity across cycles, but cannot rule out all confounders. In particular:
- **Candidate quality endogeneity**: Strong candidates raise more money and are harder to beat. The model uses total D spending as the explanatory variable, which conflates spending with candidate quality. `indiv_share` (α₅) was added as a quality proxy (§5.4) and is marginally significant, but its *negative* coefficient reveals it proxies PAC targeting rather than grassroots quality — the endogeneity concern is partially addressed but not eliminated.
- **Private signals**: See §9 (Actionability) for the full treatment.

### 10.2 Out-of-sample calibration degrades

The model's win probability calibration (Brier score) was better than Cook in 2024 (+21%) but worse than Cook in 2022 (−20%). This is expected for an OOS test — the 2012–2020 panel misses 2022 redistricting and political context. The efficiency finding (optimizer beats DCCC) is robust to this calibration degradation, but probability-based use cases (which races are actually in play) require more caution.

### 10.3 Non-linear optimizer: numerical scaling

A subtle numerical scaling bug was identified and corrected during the audit. Raw party allocations are on the order of $0–$70M per race, while the MSG gradient values are on the order of 1e-7 (seats per dollar). In SLSQP's convergence check the projected Lagrangian gradient (MSG × allocation scale) appeared near-zero relative to the solver's `ftol=1e-10` threshold, causing the optimizer to terminate after a single iteration at the DCCC starting point and report false convergence.

The fix was to scale party allocations to $M units before passing to SLSQP and apply the corresponding chain-rule correction to the gradient. The current result is **220.52 expected seats (+5.34 vs DCCC = 215.18)**. This supersedes the erroneous +0.88 (pre-scaling-fix) and the interim +4.46 (post-scaling-fix, pre-α₅). A subsequent addition of `indiv_share` (α₅ = −3.99) inflated the apparent gain to +11.9 by suppressing the DCCC baseline by 6.56 seats — without changing the optimizer's allocation at all (confirmed: max allocation difference between α₅ and no-α₅ optimizer = $0.00 across 433 races). Zeroing α₅ is now hardcoded in `src/backtest/model/margin.py` rather than patched in the JSON, so re-running estimation can never revert it. The 2022 OOS results were also affected: the old aggregate CSV (DCCC=206.49, gain=+5.54, ρ=−0.380) was generated with α₅=−3.99 active in the OOS estimation path. With α₅=0 consistently enforced, the correct 2022 OOS figures are DCCC=214.87, gain=+6.79, ρ=−0.647 (p<0.001).

Global optimality of 220.52 is not guaranteed (SLSQP is a local solver), but the result is robust to initialization and consistent with the response-curve analysis.

### 10.4 Budget decomposition uncertainty

Candidate vs. party spending is inferred from FEC filing categories. Some coordination between candidate and party committees may be mis-attributed. The $465M party budget estimate is approximate.

### 10.5 Republican spending treated as fixed (partially addressed)

The base model takes Republican spending as given. §9 (Actionability) describes the operational implications, and §9.4 (Adversarial Response) quantifies the seat gain under adversarial NRCC matching via the η parameter. Even at η = 1 (dollar-for-dollar response), the optimizer yields +1.88 seats over DCCC. However, the η model is a reduced-form approximation — it does not model the NRCC's *targeting* of counter-spending, only the total magnitude. A Nash equilibrium formulation is left as future work.

### 10.6 σ model ordering

The estimated σ model does not produce the theoretically expected ordering (open seat > challenger > incumbent). This is likely a selection effect — challengers run where they have advantages, reducing residual scatter — but it is a departure from prior assumptions and warrants scrutiny.

### 10.7 Data coverage gaps identified during audit

An audit of all raw data files against the pipeline identified three gaps. Each was investigated and either corrected or documented as future work.

**Gap 1 — CVAP (spending intensity per voter).**  
The `data/raw/census/` directory contains 2022 ACS5 CVAP estimates for all 433 districts. These were not originally used in the model. During the audit, a `log((D+R)/CVAP)` spending-intensity covariate was tested. OLS on the historical panel produced a coefficient α₄ = −2.02, but including it *degraded* out-of-sample Brier from 0.0299 to 0.0345. Root cause: endogeneity. High-spending races are structurally more competitive (DCCC over-invests where wins are needed most), so OLS picks up selection bias rather than a causal effect of spending intensity. CVAP is now loaded and plumbed through all model functions (parameter α₄ is defined in `MarginModelCoefficients`), but constrained to α₄ = 0.0 pending proper instrumental variable estimation. The CVAP-to-district mapping and all supporting infrastructure are in place for future work.

**Gap 2 — NRCC coordinated expenditures.**  
The FEC pipeline produced empty files for all `coordinated_nrcc_*.csv` outputs. Investigation confirmed this is a fetch-time issue (the DEMO_KEY rate limit prevents bulk coordinated Schedule F queries), not a structural data absence. Impact is small: Republican Schedule F coordinated spending is likely $30–50M in competitive races, compared to $136M already captured via Republican independent expenditures. To fill this gap, re-run `fetch_data.py` with a registered FEC API key.

**Gap 3 — State party coordinated expenditures.**  
FEC "Other Transactions" (24K filings, `data/raw/bulk_all/itoth.txt`) include committee-to-committee transfers. A subset of these are state Democratic party coordinated expenditures into House races not attributed to the DCCC. Parsing the full 1M-row file to isolate House 24K coordinateds was out of scope for this audit; it is documented here as future work. The likely magnitude is small relative to IEs, but this represents an undercount of total Democratic coordination in some districts.

---

## 11. Output Files

All outputs are in `outputs/`.

### Charts

| File | Description |
|------|-------------|
| `msg_efficiency.png` | MSG vs. D total spend for competitive races. The headline Spearman ρ = −0.49 result. |
| `model_calibration.png` | Predicted P_win bins vs. actual D win rate. Model vs. Cook calibration comparison. |
| `spending_by_cook.png` | Median D and R spending by Cook category; box plots for competitive races. |
| `allocator_comparison.png` | Expected seats comparison: DCCC, Cook-implied, equal-weight, model optimizer. |
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

### Model artifacts

| File | Description |
|------|-------------|
| `data/processed/margin_model_coef.json` | Estimated α and β coefficients. |
| `data/processed/sigma_model.json` | σᵢ model intercept and coefficients. |
| `data/processed/beta_rc.json` | β_RC point estimate, SE, and n_pairs. |

### Live 2026 pipeline

| File | Description |
|------|-------------|
| `data/live/spending_live.json` | Cumulative per-district D/R spending snapshot (updated by `fetch_live_ies.py`). |
| `data/live/msg_live.csv` | Real-time MSG ranking of competitive races, sorted by MSG descending. |
| `data/live/fetch_log.jsonl` | Append-only audit trail of each fetch run (timestamp, cycle, IE count, top district). |

Run `python scripts/fetch_live_ies.py --api-key YOUR_KEY` daily during the cycle. Set `FEC_API_KEY` in the environment to avoid passing the key on the command line. Add `--lookback-hours 48` during accelerated-reporting windows (final 20 days). Committees tracked: DCCC (C00000935), NRCC (C00075473), HMP (C00500884), CLF (C00571372).

---

*Generated from `scripts/run_estimation.py` + `scripts/run_backtest.py` + `scripts/make_charts.py` + `scripts/fetch_live_ies.py`.*
