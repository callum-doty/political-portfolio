# Estimating the State Transition Model for Sequential Campaign Allocation

### Third paper in the series — the political-state analog of a volatility model, from which the value of waiting is a derived consequence, not an assumed one

*Draft — Sections 4 (opponent reaction) and 5 (national process) now report real, fitted estimates from real data pulled this session, not just research plans. Section 6 (idiosyncratic uncertainty) remains a proxy treatment rather than a fitted process, for reasons stated in §6.2.*

---

## Abstract

Paper I derives and estimates a static valuation model for campaign spending. Paper II operationalizes that valuation model sequentially, and in doing so discovers something the static model cannot express: capital held rather than spent has option value, because retaining it preserves the ability to react to information that has not yet arrived. Paper II names this gap, formalizes it as an unsolved Bellman equation, and shows its empirical cost — 65.5% of a live $393M 2026 budget recommended to non-competitive seats, roughly four months from Election Day, because nothing in the architecture assigns waiting any value at all.

It is tempting to read that gap as "solve the Bellman equation." This paper argues that framing is backward, in the same sense that "solve for the value of a stock option" is backward before anyone has specified how the stock price moves. An option's value is not an independent object to be derived; it is a corollary of a stochastic process for the underlying asset, $dS_t=\mu S_t\,dt+\sigma S_t\,dW_t$, plugged into a valuation equation whose functional form (Black–Scholes, or a Bellman recursion for American-style exercise) is standard machinery once that process is specified. The genuinely hard, genuinely novel step is specifying and defending the process — not solving the equation that consumes it.

This paper is the political-science analog of specifying $dS_t$. We define the campaign's full state vector $\mathbf X_t$ explicitly, decompose its evolution into a control component (fully derived already, in Paper I) and three stochastic or reactive components that are not derived anywhere in this project — the national environment process $G_t$, race-level idiosyncratic shocks $\varepsilon_{i,t}$, and opponent reaction $R_t(D_t)$ — and treat all three as co-equal objects of estimation, not as a primary process with two footnotes. Two of the three are now real, fitted quantities rather than research plans: opponent reaction is estimated from a real 2022/2024 panel (a tiered $\hat\eta(\text{tier})\approx0.25$–$0.48$ in genuinely contested races), and the national environment process is calibrated from a real, four-cycle historical generic-ballot series recovered this session, giving $\sigma_G(\Delta t)\approx0.18$–$0.20\times\sqrt{\Delta t}$ and showing that a random walk is a good approximation over the 3–9 month horizon that matters for $\Theta$ near Election Day. Race-level idiosyncratic uncertainty remains the hardest component: it is likely not estimable as a genuine time-varying process under the public-data-only constraint both prior papers inherit, and is instead treated as a bounded proxy borrowed from the national process's resolution rate. Only once $\mathbf X_t$'s transition law $P$ is specified does the value of waiting, $\Theta(t)$, cease to be an assumption and become a computable implication of $P$ — at which point solving for it is a standard application of regression-based Monte Carlo methods, not this paper's contribution. **This paper's contribution is $P$. $\Theta$ is what $P$ implies.**

---

## 1. Introduction

### 1.1 The question this paper answers, and the one it does not

Paper II asks how a committee should deploy capital sequentially, given a valuation model. In building that architecture, it discovers a gap: nothing in it prices the difference between "this race is worth funding" and "this race is worth funding *right now*." Paper II calls the missing object $\Theta$, states the Bellman equation it would need to solve, and stops there deliberately.

The natural next move is to treat that Bellman equation as the remaining problem and try to solve it. This paper argues that is the wrong next move, for a precise reason: a Bellman equation over an unspecified state-transition law is not merely difficult — it is not yet a well-posed mathematical object. Consider the equation itself,

$$V_t(\mathbf X_t,F_t) = \max_{0\le\mathbf p_t\le F_t}\ \mathbb E_P\!\left[\,V_{t+1}(\mathbf X_{t+1},F_t-\mathbf 1'\mathbf p_t+\text{fundraising}_t)\,\right]$$

Every symbol here is defined except one: $P$, the law governing how $\mathbf X_{t+1}$ is generated from $\mathbf X_t$. Without $P$, this expression has an expectation operator with nothing inside it to take an expectation *over*. It is not that solving this equation is hard without $P$ — it is that the equation does not yet say anything without $P$. Specifying $P$ is therefore not a preliminary step before the real work; it is the entire remaining scientific content of the problem. Once $P$ exists, computing $V_t$ (and therefore $\Theta$) is standard: simulate forward paths under $P$, and use a regression-based Monte Carlo method (Longstaff–Schwartz or a close relative) to estimate continuation values by backward induction. That machinery is decades old and well understood. It is not what makes this problem hard.

**This paper's job is to specify and, where the data allows, estimate $P$.** Everything about $\Theta$, reserve policy, and optimal stopping is a downstream implication of that specification, not a separate derivation.

### 1.2 The finance analogy, made precise

The correspondence to option pricing is exact enough to be load-bearing, not decorative:

| Finance | This project |
|---|---|
| Stock price $S_t$ | Campaign state $\mathbf X_t$ (defined in Section 2) |
| Price process $dS_t=\mu S_t dt+\sigma S_t dW_t$ | State-transition law $P$ (Sections 4–6) |
| Volatility $\sigma$ | $G_t$'s innovation variance, $\varepsilon_{i,t}$'s covariance structure, opponent reaction $R_t(D_t)$ |
| Option value $V(S_t,t)$ | Value function $V_t(\mathbf X_t,F_t)$ |
| Early-exercise value / American option premium | $\Theta(t)$, the value of not yet committing capital |
| Black–Scholes PDE / binomial tree / Longstaff–Schwartz | The Bellman recursion above, solved once $P$ is known |

No one asks "what is the value of waiting to exercise this option?" before specifying $\sigma$. The question is not answerable in that order. The same is true here, and Paper II's Bellman equation, exactly like an option-pricing PDE, is the *consumer* of a specified process, not a substitute for specifying one.

### 1.3 What motivates this now

Paper II's live 2026 run gives this urgency, not just theoretical motivation. At approximately four months from Election Day, the receding-horizon optimizer — which implicitly assumes $P$ contributes nothing beyond what the current period already knows — recommended 65.5% of $393M in deployable capital to Likely R and Safe R seats, including $5.6M to a district at PVI −17.5. This is the empirical size of the gap a specified $P$ would close.

---

## 2. The state vector $\mathbf X_t$

Paper II leaves $\mathbf X_t$ informal ("§3.1's state vector includes cash-on-hand, Cook rating, generic ballot... ") and its transition operator $f$ fully generic. Before any component of $P$ can be specified, $\mathbf X_t$ itself needs a precise definition — every later equation in this paper is a statement about how one piece of it evolves, and the Bellman equation in Section 1.1 is not rigorous until $\mathbf X_t$ is.

Grounding this in what Paper II's own code already implements (`dynamic/state.py`'s `CampaignState`/`RaceState`), the state at reporting period $t$ is

$$\mathbf X_t = \Big(\ \{\mu_{i,t},\ \sigma_{i,t},\ D_{i,t},\ R_{i,t},\ L_{i,t}\}_{i=1}^N,\ \ G_t,\ \ F_t\ \Big)$$

where, per race $i$: $\mu_{i,t}$ and $\sigma_{i,t}$ are the smoothed expected-margin and margin-uncertainty estimates (Paper I's valuation, re-estimated and EMA-smoothed each period per Paper II §3.3); $D_{i,t}$ and $R_{i,t}$ are cumulative Democratic- and Republican-aligned spending to date; $L_{i,t}$ is committed capital already irreversible for that race. At the aggregate level: $G_t$ is the national generic-ballot point estimate, and $F_t=B_t-\sum_iL_{i,t}$ is deployable capital (Paper II §3.2's ledger identity, already fully derived — nothing new here).

Two fields Paper II's `RaceState` dataclass reserves but leaves as unpopulated stubs — `cash_on_hand_d` and `cook_rating_t` — are omitted from $\mathbf X_t$ above because no process for them is proposed in this paper either; they remain explicitly out of scope, not silently assumed away.

**Each component of $\mathbf X_t$ evolves by exactly one of three mechanisms**, and naming this is what makes the Bellman formulation rigorous rather than notational:

| Component | Evolution mechanism | Status |
|---|---|---|
| $D_{i,t}$ | **Control**: $D_{i,t+1}=D_{i,t}+p_{i,t}$, the committee's own decision | Fully specified (it is the decision variable) |
| $\mu_{i,t}$ | **Control + two stochastic shocks**: $\mu_{i,t+1}=\mu_{i,t}+\Delta\mu_i(p_t)+\beta_i\Delta G_t+\varepsilon_{i,t}$ | Control term derived (Paper I); shocks require Sections 4–5 |
| $G_t$ | **Stochastic process**, exogenous to any single committee's decisions | Requires Section 5 |
| $R_{i,t}$ | **Reactive process**, a function of the *committee's own* control | Requires Section 6 |
| $F_t,\ L_{i,t}$ | **Deterministic bookkeeping** given $B_t$ and the ledger identity | Fully derived (Paper II §3.2) |
| $\sigma_{i,t}$ | Smoothed via Paper II's EMA; no independent process proposed here | Explicitly out of scope |

Of six rows, two are already fully solved by Papers I–II, one is definitional bookkeeping, and three are genuinely unresolved. This paper is about those three, and — departing from an earlier draft's imbalance — treats them as co-equal, not as a primary process ($G_t$) with two footnotes.

---

## 3. Why calibration precedes optimization

This deserves to be stated as its own claim, not buried in a limitations paragraph, because it is the paper's central methodological point: **without a calibrated $P$, the Bellman equation in Section 1.1 is not difficult to solve — it is undefined.** "Difficult" describes a well-posed problem that resists an easy method. An expectation operator with no specified distribution to integrate against is not that; it is a placeholder. Any number produced by "solving" it without a calibrated $P$ would be an artifact of whatever ad hoc distributional choice was smuggled in, not a result.

This has a direct methodological consequence for how this project should proceed: it would be a mistake to pick a convenient distribution for $G_t$ and $\varepsilon_{i,t}$ (a default Gaussian random walk, say) purely so that Section 1.1's equation can be exercised. That produces a number, but not a defensible one, and the number would carry false precision — exactly the failure mode Paper II's own Θ-free live run already illustrates in a different form (a model producing a confident-looking allocation from an under-specified objective). The correct sequencing is: estimate $P$ from data, honestly report where it cannot yet be estimated, and only then compute $\Theta$ — and where a component of $P$ cannot be estimated (Section 5 may be such a case), $\Theta$ should carry that uncertainty forward explicitly (e.g., as a bounded range) rather than resolving it by assumption.

---

## 4. Opponent reaction $R_t(D_t)$

*Elevated here to the first of three co-equal components — not, as in an earlier draft, an appendix to $G_t$ and $\varepsilon_{i,t}$. Operationally it may matter more than either: it does not just add noise to the state, it changes how much control the committee actually has.*

### 4.1 Why this is not "just another stochastic term"

The other two stochastic components ($G_t$, $\varepsilon_{i,t}$) enter $\mathbf X_t$'s transition additively, alongside the control term, without altering what the control term *means*. Opponent reaction is different in kind: if Republican-aligned spending responds to Democratic increments at some rate $\eta$, then the *effective* control is not $\Delta\mu_i(p_t)$ as Paper I derives it holding $R_i$ fixed — it is $\Delta\mu_i(p_t)$ evaluated against a moving $R_{i,t}$ that partially offsets the increment. `allocator.py` already encodes this mechanically (§8 of Paper I, reproduced in Paper II's optimizer calls):

$$R_i(D_i) = R_{i,\text{base}} + \eta\cdot\max(0,\ \text{party}_i - \text{party}_{i,\text{obs}}), \qquad \eta\in[0,1]$$

At $\eta=0$, Paper I's static gradient is exactly correct. At $\eta\to1$ (dollar-for-dollar matching), the log-ratio term that drives the entire MSG chain rule collapses toward zero — the committee's spending decision stops mechanically converting into margin movement at all. **This is not a refinement to the control term; it is a statement about how much of the control term is real.** A calibrated $\eta$ (or a richer reaction function $\eta(\cdot)$) is therefore not an optional addition to this paper's scope — it directly determines whether Paper I's chain-rule gradient, taken at face value in a multi-period setting, over- or under-states the committee's actual leverage.

A single scalar $\eta$ is very likely mis-specified: the economically plausible prior is that opponents match aggressively in Toss-Ups (where a marginal dollar changes the outcome) and largely ignore spending in races that are not competitive for either side. **The primary specification is therefore $\eta(\text{Cook tier})$, not a pooled scalar** — fit separately by competitiveness tier from the start, with a single pooled $\eta$ reported only as a secondary, illustrative average. Fitting the scalar version first and tiering "later" would risk publishing a leverage estimate that is systematically wrong in exactly the races (Toss-Up, Lean) that matter most for the optimizer's marginal decisions.

### 4.2 Current treatment, and a real data-quality obstacle found this session

$\eta$ is currently a hand-set scenario parameter (0, 0.5, or 1.0), chosen to bound a range of assumed opponent behavior, not estimated. The infrastructure to estimate it exists in this repository — `dynamic/simulate.py`'s one-step-ahead historical harness and `fetch_live_ies.py`'s dated FEC Schedule E parsing together mean $(D_{i,t}, R_{i,t})$ can be reconstructed at multiple points within the 2022 and 2024 cycles from data already on disk — but the raw data has a real, checked problem that must be fixed before that reconstruction is trustworthy.

We checked the specific concern that historical Schedule E is poorly attributed to districts pre-2018 (the a priori worry going in). **That specific concern does not hold in this repository's data**: `can_office_dis` (district attribution) is blank in only 0.1–0.3% of House-general IE rows in *every* cycle from 2012 through 2024 — pre-2018 is no worse than recent cycles on this dimension, because every IE row is filed against a specific candidate ID, not a generic national bucket. What we found instead, checking `exp_date` (needed for the date-bucketed reconstruction specifically):

| Cycle | n (House, general) | blank `exp_date` | blank `can_office_dis` |
|---|---|---|---|
| 2012 | 12,835 | 0.0% | 0.2% |
| 2014 | 8,012 | 12.9% | 0.1% |
| 2016 | 5,963 | 17.5% | 0.3% |
| 2018 | 24,073 | 11.7% | 0.1% |
| 2022 | 19,401 | **33.3%** | 0.1% |
| 2024 | 19,881 | **28.4%** | 0.1% |

Missing dates are worse in the *recent* cycles this paper actually needs, not the older ones — the opposite of the a priori concern. Separately, and more seriously: 2022's raw file contains one corrupted row (`Akhlaghy, Nader` / `COMMITTEE 300`, `exp_amo=$10,000,000,000`, with `agg_amo=2024.00` — a value that looks like a year leaked into the wrong field, i.e. a parsing bug, not real spending), duplicated twice, and more broadly **26% of all 2022 IE rows (5,097/19,401) share a duplicated `tran_id`**. We confirmed this does *not* contaminate any number already reported in Papers I/II — the affected district (NY-05)'s actual `d_total`/`r_total` in `race_table_baseline_2022.csv` are sane ($1.76M/$126K), and the table's maximum value anywhere is $29M, so the consolidated pipeline Papers I/II draw from already filters or dedupes this upstream of what gets reported. It is, however, a live blocker for this section's raw, transaction-level reconstruction specifically, which has not been built yet. **A `tran_id`-deduplication and implausible-`exp_amo` filtering step is a prerequisite to §4.3, not an optional data-cleaning nicety.**

### 4.3 Proposed specification

$$\Delta R_{i,t}^{\text{IE}} = \eta(\text{tier}_i)\cdot\Delta D_{i,t-1}^{\text{IE}} + u_{i,t}$$

with race fixed effects applied via within-(cycle, district) demeaning (not dummy columns — pooling ~800 district-cycle observations across biweekly periods makes a dummy matrix wasteful), pooled across the reconstructed and de-duplicated 2022/2024 panel, $\eta$ interacted with Cook tier.

### 4.4 Results — a first estimate, fit this session

Using biweekly reporting periods (`dynamic/periods.py::biweekly_periods`) from January through early November of each cycle, with the §4.2 amendment-resolution and implausible-amount cleaning applied:

| Tier | $n$ | $\hat\eta$ | SE | $p$ | D-side active periods | R-side active periods |
|---|---|---|---|---|---|---|
| Toss-Up | 200 | **0.475** | 0.073 | <0.001 | 67.0% | 72.5% |
| Lean R | 42 | **0.304** | 0.104 | 0.003 | 71.4% | 71.4% |
| Lean D | 241 | **0.259** | 0.070 | <0.001 | 63.9% | 56.0% |
| Likely R | 183 | 0.405 | 0.270 | 0.133 | 28.4% | 55.7% |
| Likely D | 173 | −0.165 | 0.089 | 0.064 | 45.1% | 26.6% |
| Safe D | 206 | 0.648 | 0.257 | 0.012 | 18.4% | 8.7% |
| Safe R | 276 | −0.144 | 0.069 | 0.038 | 11.6% | 20.3% |

Pooled (scalar) estimate for comparison against the current hand-set 0/0.5/1.0 scenarios: $\hat\eta=0.331$ (SE=0.044).

**Read the Toss-Up/Lean D/Lean R rows as the trustworthy result, and the Safe D/Safe R/Likely D rows as likely artifacts, not as a genuine finding that opponents react more in safe seats than contested ones.** The reason is directly visible in the activity-rate columns: Safe D districts show IE spending in only 18.4% of D-side periods and 8.7% of R-side periods (Safe R: 11.6%/20.3%), meaning the within-race demeaned regression for these tiers is identified from a handful of sparse, lumpy transactions per district rather than a stable period-to-period relationship — a small number of idiosyncratic events (a late primary-adjacent ad buy, a single outside-group entry) can dominate the estimate. Toss-Up, Lean D, and Lean R, by contrast, have 56–73% activity rates and produce estimates an order of magnitude more precisely estimated (SE $\approx$0.07–0.10 vs. 0.09–0.27). The reliable finding is that $\hat\eta\approx0.25$–$0.48$ in genuinely contested tiers — real, statistically robust reaction, but well short of the na\"ive dollar-for-dollar prior ($\eta\approx1$) and closer to the current codebase's $\eta=0.5$ scenario than to $\eta=0$ or $\eta=1$.

This is a first specification and should be read as such: it does not address possible simultaneity (both sides may ramp up together as Election Day approaches for reasons unrelated to reacting to each other specifically), it uses one lag at a fixed biweekly resolution rather than testing alternatives, and — per Section 4.1's scope statement — it measures IE-to-IE reaction only, not a full-spending reaction function. Whether $\eta$ additionally varies with how much runway remains before Election Day is a direct extension of this same specification, not yet fit. `scripts/estimate_eta_reaction.py` reproduces this table from the cleaned data; `outputs/eta_reaction_estimates.csv` is the saved output.

---

## 5. The national environment process $G_t$

### 5.1 Candidate specifications

- **Random walk**: $\Delta G_t\sim N(0,\sigma_G^2\Delta t)$ — variance grows unboundedly with horizon.
- **Mean-reverting (Ornstein–Uhlenbeck)**: $dG_t=\kappa(\bar G-G_t)dt+\sigma_G\,dW_t$ — variance saturates.

These have materially different implications for $\Theta$ in principle: a random walk implies option value keeps growing the longer one waits; mean reversion implies most resolvable uncertainty is realized within a bounded window. In practice, this distinction should not be over-indexed on. The generic ballot is bounded by underlying partisanship, so AIC will very likely favor OU over a random walk almost regardless of the data — but the mean-reversion speed $\kappa$ implied by a 12-month lookback is typically slow enough that over the 3–6 month horizon actually relevant to $\Theta$ near Election Day (Paper II §7.1's live run is ~4 months out), RW and OU are nearly indistinguishable in their implications. Formal model selection between them is a secondary exercise, not the primary deliverable of this section.

**The primary deliverable is instead the empirical, non-parametric term structure $\sigma_G(\Delta t)$ itself** — realized volatility as a direct function of horizon, estimated straight from the historical series without forcing a Gaussian process form onto it first. §5.3 now reports this pooled across four real historical cycles plus the live 2026 series, rather than the single-path exercise an earlier draft was limited to.

### 5.2 Data requirement — resolved this session

This required a **historical, dated, multi-cycle** generic-ballot series (2018, 2020, 2022, 2024), comparable to the live 2026 feed this project already ingests. It did not exist in this repository as of the previous draft — `data/raw/rcp/` (RealClearPolitics) is an empty placeholder and blocked by bot protection when checked directly (`data_catalog.md` §1.10), and `generic_ballot_by_cycle.csv` has exactly one static value per cycle, no dates at all — but a real source was found and is now in this repository: FiveThirtyEight's own live generic-ballot data endpoint, discontinued after ABC News shut down 538 in 2023, recovered via a Wayback Machine snapshot (`data/raw/generic_ballot/generic_ballot_historical_538.csv`; provenance in `data_catalog.md` §1.8b). This snapshot retained the full cumulative daily trend estimate for all four cycles: 1,142–1,174 daily rows each, 2017-04 through 2024-11.

### 5.3 Term structure — estimated on real, multi-cycle data

`scripts/estimate_gb_volatility.py` computes realized volatility of $\Delta G$ pooled across all four historical cycles plus the live 2026 series, at the same horizons as the original single-cycle exercise:

| Horizon | $n$ cycles | Pooled std($\Delta G$) | std/√days (all 5) | std/√days (4 historical only) |
|---|---|---|---|---|
| 30 days | 5 | 1.09 | 0.199 | 0.186 |
| 60 days | 5 | 1.54 | 0.199 | 0.186 |
| 90 days | 5 | 1.89 | 0.199 | 0.183 |
| 180 days | 5 | 2.70 | 0.201 | 0.186 |
| 270 days | 5 | 3.29 | 0.200 | 0.178 |
| 365 days | 5 | 3.81 | 0.199 | 0.160 |
| 450 days | 5 | 4.17 | 0.197 | 0.128 |

This changes the qualitative conclusion from the single-cycle exercise, not just its precision. Pooled across genuinely independent cycles, std/√days is **remarkably stable from 30 through 270 days** (0.183–0.201) rather than steadily declining — the apparent mean-reversion signal in the original one-path exercise was a small-sample artifact, not a real feature of the process. A visible decline only emerges past ~365 days (historical-only: 0.160 at 365 days, 0.128 at 450 days), consistent with §5.1's prediction: **a random walk is a good approximation over the 3–9 month range that actually matters for $\Theta$ near Election Day, and the RW/OU distinction only starts to matter at horizons beyond about a year** — this project's live 2026 application is ~4 months out, squarely inside the range where the two specifications barely differ.

**Working number for the calibration**: $\sigma_G(\Delta t)\approx0.18$–$0.20\times\sqrt{\Delta t\text{ (days)}}$, historical-cycles-only preferred for methodological cleanliness (§1.8b's caveat: 538's own aggregation vs. this project's raw-poll smoothing are not identically constructed). At the ~120-day horizon relevant to Paper II's live run, this gives $\sigma_G\approx2.0$ points — a real, cross-cycle-supported number, not a single-path guess. `outputs/gb_volatility_term_structure.csv` and `outputs/gb_volatility_term_structure_historical_only.csv` are the saved results; `outputs/gb_volatility_by_cycle.csv` breaks it down cycle by cycle for inspection.

### 5.4 Validation standard for the assembled simulator

"Does the simulator produce trajectories that look like real ones" is too low a bar once $\hat\eta$, $\hat P_G$, and Section 6's treatment are assembled into the full state-transition simulator of Section 2. The validation metric this project should hold itself to is **rank correlation between simulated $\mu_{i,t}$ and eventual realized margin**, checked at a fixed pre-election horizon (e.g., simulated-as-of-September paths vs. November outcomes, using 2022/2024 as held-out validation cycles). A simulator that cannot rank-order competitive races correctly by that point produces a $\Theta$ that is garbage-in-garbage-out regardless of how carefully Sections 4–6 were individually calibrated — this check belongs before Section 7's Bellman step, not after.

---

## 6. Race-level idiosyncratic uncertainty $\varepsilon_{i,t}$

### 6.1 What already exists, and what's missing

Paper I's $\sigma_i$ model is a **cross-sectional** fit — how much residual uncertainty a race of a given type carries once, not how that uncertainty evolves or resolves over a cycle. Paper I's factor covariance is similarly **static**. A genuine $\varepsilon_{i,t}$ process requires knowing how much of a race's idiosyncratic uncertainty resolves per unit time, and how that resolution correlates across races beyond what $G_t$ already captures (a primary result, a retirement, a redistricting ruling).

### 6.2 Data constraint — likely permanent, and why the obvious fallback is dangerous

This requires **district-level polling history** across the competitive universe. In practice this is worse than "sparse": in a typical recent cycle, a small minority of House districts — well under 10% of the competitive universe — receive two or more public polls at all, and most of those cluster in the final weeks before Election Day. There is not enough data to fit a genuine time-series process for $\varepsilon_{i,t}$ per race; for the large majority of races, the effective sample size for "how does this race's idiosyncratic uncertainty resolve over time" is one observation or zero.

An earlier version of this plan proposed falling back on Paper I's static, cross-sectional $\sigma_i$ as a stand-in for $\varepsilon_{i,t}$'s distribution. **That fallback is not a neutral simplification — it is wrong in a specific, consequential direction.** Treating $\varepsilon_{i,t}$ as a static draw from $\sigma_i$'s cross-sectional distribution implicitly assumes all of a race's idiosyncratic uncertainty resolves instantaneously, which is equivalent to assuming there is no idiosyncratic information left to arrive — exactly backward, since it would make $\Theta$ collapse toward zero for the wrong reason (nothing left to wait for) rather than the right one (nothing left to *learn*).

**Proposed fix**: borrow the resolution *rate*, not the distribution, from Section 5's calibrated national process, and apply it as a shrinkage/decay factor on the static cross-sectional $\sigma_i$:

$$\sigma_{i,t} = \sigma_i^{\text{static}}\cdot\sqrt{1-e^{-\lambda(T-t)}}$$

where $\lambda$ is fit from $\sigma_G(\Delta t)$'s term structure (Section 5.4/5.3) rather than estimated separately per race — the assumption being that idiosyncratic information resolves at a rate comparable to national information, absent any race-specific data to say otherwise. This is explicitly a proxy, not a fitted $\varepsilon_{i,t}$ process, and should be reported as one: it prevents $\Theta$ from being inflated by an implausible "surprise arrives all at once on Election Day" assumption, but it does not constitute having estimated race-level dynamics from data, because the data to do so does not exist in usable quantity. If, after checking, district-level polling density turns out to be higher than assumed here, this section's conclusion should be revisited rather than assumed.

---

## 7. From a calibrated $P$ to $\Theta$ — the easy part

Once Sections 4–6 (or as many as prove tractable) specify $P$, computing $V_t(\mathbf X_t,F_t)$ and therefore $\Theta(t)=V_t^{\text{wait}}-V_t^{\text{deploy-now}}$ is standard: simulate forward paths of $\mathbf X_t$ under $P$; at each step, regress simulated continuation values on a basis of current-state features (a Longstaff–Schwartz-style approach); proceed by backward induction from $T$. This is well-established machinery. **We say this explicitly so that it is not mistaken for this paper's contribution.** The contribution is Sections 4–6; this section is what those sections are *for*, not a fourth research question alongside them.

### 7.1 The one implementation detail that is not optional: compress the regression basis

"Standard machinery" still has a specific failure mode here that must be designed around from the start, not discovered after a slow, overfit first attempt. Section 2's state vector carries $\{\mu_{i,t},\sigma_{i,t},D_{i,t},R_{i,t},L_{i,t}\}$ *per race* — on the order of 400+ races. Regressing simulated continuation values on a per-race feature basis (raw or polynomial) is not merely slow, it is a data-analytic mistake at the sample sizes involved: with $K\sim10^4$ simulated paths and $\sim$15 time steps, the regression has on the order of $10^5$ observations against a feature matrix with hundreds of columns — invertible in principle, but the resulting fit would overfit badly and say more about simulation noise than about $\Theta$.

**The regression basis must be a small set of portfolio-level aggregate features, not per-race features.** A minimal basis of four to six moments is standard practice for exactly this class of problem (basket-option pricing, where the same dimensionality problem arises from pricing an option on many underlyings at once):

1. $\mathbb E[\text{Seats}]_t=\sum_i\Phi(\mu_{i,t}/\sigma_{i,t})$ — the portfolio's current level.
2. $\text{Var}[\text{Seats}]_t=\mathbf s_t'\Sigma\mathbf s_t$ — the portfolio's current risk (Paper I's factor covariance, already available).
3. $\max_i\text{MSG}_{i,t}$ — the value of the single best marginal dollar available right now.
4. A near-threshold count: the number of races within some small margin (e.g., 2 points) of the majority-determining threshold — a direct proxy for how much of the portfolio's outcome is still genuinely undecided.

Regressing $V_{t+1}$ on this basis (with squares/cross-terms if needed) keeps the Longstaff–Schwartz step fast and well-conditioned, and is the specification this paper commits to rather than a per-race alternative that would not run at this state-space size in practice.

---

## 8. Research sequencing

1. **Opponent reaction (§4)** — done this session: real, fitted $\hat\eta(\text{tier})$ estimates (§4.4).
2. **National process $G_t$ (§5)** — done this session: real, cross-cycle-pooled $\sigma_G(\Delta t)$ term structure (§5.3).
3. **Idiosyncratic uncertainty $\varepsilon_{i,t}$ (§6)** — very likely resolved as a bounded, rate-borrowed proxy (§6.2) rather than a fitted process, given the polling-density constraint; $\lambda$ in §6.2's decay formula can now be fit directly from §5.3's term structure rather than assumed.

With (1) and (2) now real, estimated quantities rather than research plans, and (3) reduced to a bounded proxy rather than an open question, Section 7's Bellman step is close to well-posed — the remaining prerequisite is assembling all three into the single simulator of Section 2 (§5.4's validation standard) before it is exercised.

### 8.1 The closing deliverable and its pre-registered success criteria

The empirical payoff of this entire research line is a single comparison: re-run Paper II's live 2026 scenario with $\Theta(t)$ folded into the receding-horizon objective (as a reserve fraction or shadow price on $F_t$; no other change to Paper II's architecture), and compare the resulting Safe R/Likely R allocation share against the 65.5% baseline (Paper II §7.1). We commit to the following interpretation **before** running it, so the result cannot be read post hoc into whatever number comes out:

- **Result < 15%**: the calibration is doing real work — a $\Theta$-aware optimizer concentrates capital sharply relative to the greedy baseline, consistent with the prediction that low-delta, low-volatility safe seats have little to gain from patience while Toss-Ups do.
- **Result 15–30%**: partial effect — directionally consistent with $\Theta$ mattering, but the calibrated $\hat\eta$ or $\hat\sigma_G$ is likely too weak to fully price the option value at stake.
- **Result > 30%**: the $\Theta$ penalty as calibrated is too weak to matter, and the specific reason (undersized $\hat\sigma_G$, undersized $\hat\eta$, or an inadequate $\varepsilon_{i,t}$ proxy) should be diagnosed and reported, not smoothed over.

**This comparison should be published regardless of which band it falls in.** A result showing the greedy solve was already close to optimal — i.e., that waiting does not matter much in practice — is a legitimate, publishable finding about this specific decision problem, not a failed calibration to be hidden. The only unpublishable outcome is not running the comparison at all.

---

## 9. Limitations

This is a scoping document; its principal risk is prescribing steps that prove infeasible once attempted. Section 5.3's volatility exercise is not a finding about generic-ballot dynamics — it demonstrates what one short realized series can and cannot support. Section 6's data constraint may be permanent, in which case the eventual empirical treatment of $\varepsilon_{i,t}$ must report a bounded or worst-case treatment and say so plainly, rather than fitting a process the data cannot actually support.

---

## 10. Conclusion

Paper I answers "what is one more dollar worth today." Paper II answers "how do we make that decision repeatedly," and discovers it cannot yet answer "should we wait." This paper does not answer that question directly — it answers the prior question that determines whether it is even askable: how does the political state evolve on its own, absent any decision. $\Theta$, reserve policy, and optimal stopping are all corollaries of that answer, in exactly the sense that an option's value is a corollary of a specified stock-price process rather than an independently derived quantity. The scientific contribution of this research line is not, and should not be described as, "we solved a Bellman equation." It is "we estimated a defensible transition law $P$ for the political state" — and, honestly, in at least one component (Section 6), possibly "we established that this cannot currently be estimated from public data, and said so."

---

*Draft status: Sections 1–3, 7–10 are conceptually complete. Section 4 (opponent reaction) reports a real, fitted first estimate of $\eta(\text{tier})$ (§4.4), built on a real data-cleaning fix to `load_ie_transactions_dated()` (amendment-chain resolution + implausible-amount filtering, both added to `src/backtest/data/fec.py` with regression tests). Section 5 (national process) reports a real, cross-cycle-pooled $\sigma_G(\Delta t)$ term structure (§5.3), built on a real historical generic-ballot series recovered via the Wayback Machine this session (`data/raw/generic_ballot/generic_ballot_historical_538.csv`, provenance in `data_catalog.md` §1.8b) — §5.2's data blocker is resolved. Section 6 (idiosyncratic uncertainty) remains a proxy treatment, not a fitted process, per §6.2's data-density argument. Both §4.4's and §5.3's estimates should be treated as real first-pass calibrations with stated caveats, not final, peer-reviewed numbers — see each section's own qualifications before using them in §7's Bellman step.*
