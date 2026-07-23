# Formal Derivation and Computational Verification of the Political Capital Allocation Framework

*Every number below was pulled from a file in this repository as of this session; file paths are given so each claim is independently checkable.*

---

## 0. Main Result

**Claim.** The framework defines a mapping

$$\mathcal D \ \xrightarrow{\text{causal estimation}}\ \hat\beta_{RC} \ \xrightarrow{\text{OLS}}\ (\alpha,\beta_2,\beta_3) \ \xrightarrow{}\ (\mu_i,\sigma_i) \ \xrightarrow{\text{chain rule}}\ \text{MSG}_i \ \xrightarrow{\text{KKT}}\ s_i^*$$

where $\mathcal D$ is the public data described in Section 1. **Exactly one arrow in this chain is not mechanically forced by the arrow before it**: the first, $\mathcal D\to\hat\beta_{RC}$, which requires an untestable causal-identification assumption (Section 4). Every arrow after it — the OLS fit, the margin-to-probability conversion, the MSG gradient, the portfolio optimum — is a deterministic function of what came before, provably so given the stated model form. Paper II extends the last arrow, $s^*_i\to s^*_{i,t}$, to a sequence re-solved each period over deployable capital only (Section 9 of Part I), and identifies but does not close one further gap: the mapping has no term pricing the value of *not yet* committing capital (Section 10).

**Updated 2026-07-22: this gap is no longer open.** Paper III specifies the state-transition law $P$ that Section 10's Bellman equation needs to be a well-posed object at all, and solves it by regression-based Monte Carlo (Longstaff–Schwartz) backward induction against the live 2026 state. **Part V** below covers this extension with the same [MATH]/[ESTIMATION]/[VERIFICATION]/[EMPIRICAL] discipline used throughout this document. The current, multiply-corrected result reverses the framing in the rest of this section: $\Theta(t)$ is not merely "missing" — it has been computed, is substantially *positive* at the live decision, and recommends holding the reserve rather than deploying it, the opposite of what every earlier pass at this calculation found.

This document is the proof of that chain, followed by (a) computational verification that the code implements the chain as derived, and (b) the empirical findings that result from running the verified chain on real data. These are three different kinds of claims and are kept in separate parts below.

### 0.1 Reading guide — four kinds of claims, kept separate

| Tag | What it means | Can it be wrong? |
|---|---|---|
| **[MATH]** | A derivation true by logic/calculus given the stated definitions. No data involved. | Only if the algebra is wrong. |
| **[ESTIMATION]** | A specific numeric value produced by applying a [MATH] method to real data (an OLS coefficient, a posterior mean). | Yes — different data, different specification, or a violated identifying assumption all change it. |
| **[VERIFICATION]** | A check that the *code* correctly implements the [MATH]/[ESTIMATION] steps (unit tests, finite-difference checks, robustness/sensitivity checks). | Yes — this is exactly the category where this project found a real bug this session. |
| **[EMPIRICAL]** | A claim about the world, produced by running verified code on real data (DCCC misallocates capital). Depends on every layer above it, including the untestable assumption at the root of the Main Result. | Yes, and is the least certain category by construction. |

Within any of these, **[ASSUMPTION]** marks a modeling choice that is not derived from data and could reasonably be made differently; **[OPEN]** marks something explicitly unsolved.

---

## 1. Scope and data provenance [ASSUMPTION: public-data-only scope]

**Source:** `docs/data_catalog.md` §1, `config.yaml` §paths

| Domain | Source | Fields used |
|---|---|---|
| Candidate spending | FEC bulk `weball{yy}.txt` | `TTL_DISB`, `CAND_ICI`, party |
| Party coordinated spend | FEC Schedule F | per-committee coordinated expenditures |
| Party/outside independent expenditures | FEC Schedule E (comprehensive + live API for 2026) | date-bucketed IE totals |
| Election outcomes | MIT Election Data & Science Lab | margin, winner, 1976–2024 |
| District partisan lean | Cook PVI | proprietary, manually entered per cycle |
| National environment | Generic ballot polling averages | `data/raw/generic_ballot`; live: `scripts/fetch_polling.py` |
| Population normalization | Census ACS5 CVAP | citizen voting-age population |
| Incumbency | Ballotpedia + FEC `CAND_ICI` | Incumbent/Challenger/Open, **relative to the Democratic candidate** |

The entire framework is restricted to data obtainable without a paid vendor feed — a design choice stated in both papers' abstracts, not a technical necessity. It is why committed capital $L_t$ (Part I §9 below) must be *approximated* rather than read off an internal ledger.

**Universe construction**, actual pipeline log (`scripts/run_backtest.py`, 2024 run):
```
Starting universe: 459 districts → spend filter (>$100,000): 444 → state exclusions [AK]: 443
→ drop 10 races with no PVI → Final universe: 433 races (13 redistricting-flagged, retained)
```
2026 (live): 434 races, same filters, logged 2026-07-08.

---

# Part I — Mathematical Derivation [MATH]

*Every result in this part is provable from the stated model form alone. No data is used; nothing here can be "wrong" except by an algebra error.*

### I.1 Diminishing returns: why $\log(\text{ratio})$ [ASSUMPTION, mechanically consistent]

**[ASSUMPTION]** Following Erikson & Palfrey (2000): outcomes depend on *relative*, not absolute, spending, $\text{ratio}_i=D_i/(D_i+R_i)$. Using $\log(\text{ratio}_i)$ as the regressor is a modeling choice, not a derived fact — but *given* that choice, its derivative with respect to $D_i$ (Part I §6 below) mechanically produces diminishing returns; this is the one place an assumption and a derivation interact directly.

### I.2 OLS via offset regression — the general method [MATH]

Model: $y_{it}=\mathbf x_{it}'\boldsymbol\theta+\beta_1\log(\text{ratio})_{it}+\varepsilon_{it}$, with $\beta_1$ held fixed at an externally-supplied constant (Part I §3) rather than estimated jointly. Move its contribution to the left side:

$$y^*_{it} \equiv y_{it} - \hat\beta_1\log(\text{ratio})_{it} = \mathbf x_{it}'\boldsymbol\theta+\varepsilon_{it}$$

Minimizing $\sum(y^*_{it}-\mathbf x_{it}'\boldsymbol\theta)^2$ is now ordinary least squares in $\boldsymbol\theta$ alone: $\nabla_{\boldsymbol\theta}\text{SSR}=0 \Rightarrow \hat{\boldsymbol\theta}=(X'X)^{-1}X'y^*$, with HC3 robust covariance $\widehat{\text{Var}}(\hat{\boldsymbol\theta})=(X'X)^{-1}X'\hat\Omega X(X'X)^{-1}$, $\hat\Omega=\text{diag}(\hat\varepsilon_i^2/(1-h_{ii})^2)$. This is a general estimator; Part II §11 applies it to the actual panel.

### I.3 Repeat-challenger first-differencing — the general method [MATH + ASSUMPTION]

**[MATH]** With a race-pair fixed effect $\alpha_i$: $\text{Margin}_{it}=\alpha_i+\beta_{RC}\log(\text{ratio})_{it}+\eta_{it}$. First-differencing across a pair's two cycles cancels $\alpha_i$ exactly (constant within the pair):

$$\Delta\text{Margin}_i=\beta_{RC}\Delta\log(\text{ratio})_i+\Delta\eta_i \ \Rightarrow\ \hat\beta_{RC}=\frac{\sum_i\Delta\log(\text{ratio})_i\,\Delta\text{Margin}_i}{\sum_i(\Delta\log(\text{ratio})_i)^2}$$

**[ASSUMPTION, not provable]** This *estimator* is mechanical; that it equals a *causal* effect requires $\text{Cov}(\Delta\log(\text{ratio})_i,\Delta\eta_i)=0$ — cycle-to-cycle competitiveness shocks are uncorrelated with the change in relative spending, conditional on the national environment. No dataset can verify this. **This is the one non-mechanical arrow in the Main Result's chain.**

### I.4 Bayesian shrinkage posterior — full derivation [MATH]

Prior $\beta_{OS}\sim N(\beta_{RC},\tau^2)$; likelihood $\beta_{OS}^{\text{panel}}\mid\beta_{OS}\sim N(\beta_{OS},\sigma_{\text{panel}}^2)$. Completing the square in the log-posterior and setting its derivative to zero:

$$\hat\beta_{OS}=\frac{\beta_{RC}/\tau^2+\beta_{OS}^{\text{panel}}/\sigma_{\text{panel}}^2}{1/\tau^2+1/\sigma_{\text{panel}}^2}, \qquad \text{Var}(\hat\beta_{OS})=\left(\frac1{\tau^2}+\frac1{\sigma_{\text{panel}}^2}\right)^{-1}$$

Exact, given the conjugate-normal assumption — a genuine proof, not an approximation. (**[ASSUMPTION]** $\tau$ itself is not derived by any formula; Part II §13 discusses how it is set.)

### I.5 The MSG chain rule — full derivation [MATH]

With $T_i=D_i+R_i$, $c_i=\beta_1+\beta_2|\text{PVI}_i|+\beta_3\text{Incumb}_i$, and $\mu_i=(\text{const})+c_i\log(\text{ratio}_i)$:

$$\frac{\partial(\text{ratio})}{\partial D_i}=\frac{R_i}{T_i^2}\ (\text{quotient rule}) \ \Rightarrow\ \frac{\partial\log(\text{ratio})}{\partial D_i}=\frac{T_i}{D_i}\cdot\frac{R_i}{T_i^2}=\frac{R_i}{D_iT_i}$$

$$\boxed{\text{MSG}_i=\phi\!\left(\frac{\mu_i}{\sigma_i}\right)\cdot\frac1{\sigma_i}\cdot c_i\cdot\frac{R_i}{D_iT_i}}$$

This formula is unambiguous by the calculus above. Whether the *code* computes it correctly is a separate, empirical question about the implementation — addressed in Part III §17, not here.

### I.6 Portfolio factor loading — structural derivative [MATH, flagged as unused in the implementation]

Differentiating $P(\text{win}_i)=\Phi(\mu_i/\sigma_i)$ with respect to the generic ballot $G$:

$$\beta_i\equiv\frac{\partial P(\text{win}_i)}{\partial G}=\phi\!\left(\frac{\mu_i}{\sigma_i}\right)\cdot\frac{\alpha_3}{\sigma_i}, \qquad \text{Cov}(Y_i,Y_j)=\beta_i\beta_j\sigma_G^2$$

**[ASSUMPTION buried in this derivation]** treats a Bernoulli win/loss outcome as locally linear in $G$ — valid only near a reference $\bar G$. **Flag, unresolved:** this formula is *not* what `estimation/factors.py` actually estimates (Part II §15) — the paper's stated derivation and the codebase's implementation are two different models. This document does not resolve that gap; it is recorded here so the discrepancy is visible rather than silently inconsistent.

### I.7 Static optimizer — KKT conditions [MATH]

$$\text{maximize}\ \sum_iP_i(s_i)-\gamma\,\mathbf s'\Sigma\mathbf s \quad\text{s.t.}\quad \sum_is_i\le B,\ 0\le s_i\le\kappa B$$

Lagrangian $\mathcal L=\sum_iP_i(s_i)-\gamma\mathbf s'\Sigma\mathbf s-\lambda(\sum s_i-B)+\sum\mu_is_i-\sum\nu_i(s_i-\kappa B)$. Stationarity plus complementary slackness on an interior (unconstrained) race gives

$$\text{MSG}_i-\gamma\cdot2(\Sigma\mathbf s)_i=\lambda \quad\text{for all interior-funded races}$$

Races pinned at floor or cap satisfy this with a slack term instead — the formal justification for tracking `n_corner_solutions` (`allocator.py:37`).

### I.8 EMA state update — closed form [MATH]

$\hat\mu_t=\lambda\hat\mu_{t-1}+(1-\lambda)\mu_t^{\text{raw}}$ unrolls to $\hat\mu_t=(1-\lambda)\sum_{k\ge0}\lambda^k\mu_{t-k}^{\text{raw}}$, a geometric weighting. Half-life solves $\lambda^h=0.5\Rightarrow h=\ln(0.5)/\ln(\lambda)$; at $\lambda=0.7$, $h=1.94$ periods.

### I.9 Capital account identity [MATH]

$B_t=L_t+F_t$ — total budget splits into irreversibly committed and deployable capital. Part I §7's optimizer is re-solved every period over $F_t$ only, with $L_t$ folded into each race's spending floor — the same floor mechanism already used for candidate-committee spend, not a new constraint type.

### I.10 The Bellman equation for $\Theta$ — formalized, not solved [MATH, then OPEN]

$$V_t(\mathbf X_t,F_t)=\max_{0\le\mathbf p_t\le F_t}\left[\sum_i\Phi\!\left(\frac{\mu_{i,t}(D_{i,t})}{\sigma_{i,t}}\right)+\mathbb E[V_{t+1}(\mathbf X_{t+1},F_t-\mathbf 1'\mathbf p_t+\text{fundraising}_t)]\right]$$

with boundary condition $V_T(\cdot,F_T)=$ Part I §7's static payoff ($\Theta(T)=0$: nothing left to wait for on Election Day). Paper II's receding-horizon solve is the greedy special case that drops $\mathbb E[V_{t+1}(\cdot)]$ entirely.

**[OPEN as of this section; resolved by Part V, added 2026-07-22]** Solving this requires specifying the state-transition $f$'s stochastic structure, deliberately left generic here. No *closed form* for $\Theta(t)$ has been derived anywhere in this project, and that remains true — but a *computed* $\Theta(t)$, from a specified and estimated $f$ solved by regression-based Monte Carlo, now exists (Part V). Part IV §23 (below) shows what $\Theta$'s absence produced in the specific run analyzed there (2026-07-08); Part V reports what including it changes.

---

# Part II — Statistical Estimation [ESTIMATION]

*Every number in this part is Part I's general method applied to real data. A different data vintage, a different specification, or a violated Part I §I.3 assumption would change these values — that is what distinguishes them from Part I.*

### II.11 Fitted spending response surface

Applying Part I §I.2 to the 2012–2022 panel (`data/processed/margin_model_coef.json`):

| Parameter | Value | Meaning |
|---|---|---|
| $\alpha_0$ | 0.7166 | intercept |
| $\alpha_1$ | 1.0819 | PVI |
| $\alpha_2$ | 32.053 | Democratic-incumbency bonus |
| $\alpha_3$ | 0.4152 | generic ballot |
| $\alpha_4,\alpha_5$ | 0.0 (constrained) | spending-intensity, indiv-contribution share — excluded, see code comments |
| $\beta_1=\beta_{RC}$ | 5.4568 | base spending elasticity (§II.12) |
| $\beta_2$ | 0.0333 | log-ratio × \|PVI\| |
| $\beta_3$ | 28.068 | log-ratio × D-incumbency |
| $\beta_{1,\text{open}}$ | 6.9769 | open-seat override (§II.13) |
| $R^2$ (competitive, \|PVI\|≤10) | 0.492 | |

**[ASSUMPTION]** $\alpha_0$–$\alpha_3$ are descriptive panel associations, not causally identified — only $\beta_1$ inherits Part I §I.3's identification strategy.

### II.12 Repeat-challenger estimate

Applying Part I §I.3's estimator (`data/processed/beta_rc.json`):

$$\hat\beta_{RC}=5.4568 \quad (\text{SE}=1.5857,\ n=118\ \text{pairs})$$

### II.13 Open-seat calibration

Applying Part I §I.4's posterior formula (`data/processed/open_seat_calibration.json`):

| Quantity | Value |
|---|---|
| $\beta_{RC}$ (prior mean) | 5.4568 |
| $\beta_{OS}^{\text{panel}}$ (likelihood) | 7.0471 (SE=0.6818) |
| $\tau$ (prior SD — **[ASSUMPTION]**, set by covariate-overlap judgment, not a formula) | 3.1713 |
| $\kappa$ (posterior weight on panel term) | 0.9558 |
| $\hat\beta_{OS}$ (posterior mean, used for open seats) | 6.9769 |
| $\beta_{OS}^{\text{lb}}$ (Oster-bounded conservative estimate) | 5.8837 |

### II.14 $\sigma_i$ model

OLS on margin residuals conditional on structural predictors (`data/processed/sigma_model.json`):

$$\hat\sigma_i=2.3989+0.00692|\text{PVI}_i|-0.1877\,\text{Open}_i-0.5588\,\text{Challenger}_i+0.00062|GB|$$

**[ASSUMPTION, unaddressed]** Two-stage estimation: $\sigma_i$'s own estimation uncertainty is never propagated into downstream MSG/optimizer quantities (a "generated regressor" problem, present in both papers).

### II.15 Factor covariance — what is actually estimated

**Not** Part I §I.6's structural $\beta_i=\phi(\mu_i/\sigma_i)\alpha_3/\sigma_i$. The code (`estimation/factors.py`) instead fits a 5-factor ridge regression — national generic ballot, 3 Census-region dummies × GB, urbanicity share × GB — via `RidgeCV` on the 2012–2022 panel, with $\text{Cov}=\text{loadings}\times\text{factor\_cov}\times\text{loadings}^T$. This is a legitimate, independently-estimated covariance model; it is simply a different model from the one Part I §I.6 derives, and the two have not been reconciled in the paper text.

---

# Part III — Computational Verification [VERIFICATION]

*This part checks that the code implements Parts I–II correctly. It is where this session found a real, consequential bug.*

### III.16 Unit test suite

298 tests across 17 files (`tests/`; updated 2026-07-22, was 217+ across 15), covering margin prediction, win-probability/MSG computation, the optimizer, σ-model ordering, PVI construction, the dynamic (Paper II) ledger/state/EMA/horizon modules, dated FEC/periodic-report parsing, live polling ingestion, and comparison/benchmark logic (including the bootstrap and permutation additions in §III.21). All passing as of this session.

### III.17 Finite-difference gradient validation — the bug

**Found this session:** `win_prob.py`'s `_marginal_seat_gain()` computed $c_i/T_i$ instead of Part I §I.5's derived $c_i\cdot R_i/(D_iT_i)$ — it was only ever called with $T_i$, never $D_i$ and $R_i$ separately, so it structurally could not implement its own documented formula. The two expressions coincide only at exact parity ($D_i=R_i$); every existing unit test happened to use parity cases, which is why this survived undetected.

**Fix and verification:** `_marginal_seat_gain()` was changed to take $D_i,R_i$ separately (also fixing a second, related bug — it never applied the open-seat $\beta_{1,\text{open}}$ override). A new test, `test_msg_matches_finite_difference_off_parity`, checks the analytic gradient against numerical $dP(\text{win})/dD$ at $D\ne R$:

```
analytic_msg == pytest.approx(numerical_msg, rel=1e-4)   # passes at (D,R) = (6M,2M) and (1M,5M)
```

This is [VERIFICATION] in the strict sense: it does not re-derive the math (Part I already did that) — it checks the *code* now matches the math.

### III.18 Regression tests added this session

`comparison/efficiency.py::spearman_by_cook_category()` and `matched_group_efficiency_test()` were added as reusable, tested functions (10 new tests in `test_comparison.py`) so the by-category and matched-group results in Part IV §21 are reproducible from a single command rather than ad hoc scripts.

### III.19 Robustness: winsorization

Sensitivity check on whether Part IV §21–22's corrected $\rho$ values are driven by a small number of extreme-ratio races. $\log(R_i/D_i)$ winsorized at symmetric percentiles, all races retained, MSG recomputed:

| Cycle | untrimmed | wins. 10/90 | wins. 5/95 | wins. 1/99 |
|---|---|---|---|---|
| 2024 | −0.582 | −0.594 | −0.592 | −0.583 |
| 2022 | −0.750 | −0.757 | −0.753 | −0.750 |

Stable to within 0.01 at every level — the correction in §17 is not an artifact of outliers. (A full-*exclusion* diagnostic initially suggested otherwise for 2022; reconciled as a small-$n$ Spearman-correlation artifact from dropping observations entirely, not a property of the estimator itself.)

### III.20 Out-of-sample re-run as a reproducibility check

The identical pipeline (Parts I–II's methods, unmodified), re-estimated on 2012–2020 only and applied to 2022 districts, executes without error and produces internally consistent output: $n=61$ competitive races, all validation gates pass, $p<0.001$. This section only certifies the *code ran correctly on unseen data* — the scientific interpretation of what the 2022 result means is Part IV §22, not this section.

### III.21 Bootstrap and permutation robustness checks (added 2026-07-22)

Two gaps in how this project characterizes uncertainty were closed this session, both prompted by an external review questioning whether $\hat\beta_{RC}$'s parametric CI and $\rho$'s asymptotic significance were being taken on faith rather than tested directly.

**$\hat\beta_{RC}$'s parametric CI vs. an empirical bootstrap.** Every downstream use of $\hat\beta_{RC}$'s uncertainty (Part II §12, the Monte Carlo propagation in `comparison/uncertainty.py`) draws from the parametric $N(\hat\beta,\text{SE}^2)$ implied by OLS asymptotics — never tested against the actual 118-pair sample, which §IV.21's own analysis (Section 10.1 of `FINDINGS.md`) already shows is compositionally skewed (72% Safe R). `bootstrap_beta_rc()` (`estimation/beta_rc.py`) instead resamples the 118 pairs with replacement and re-estimates $\hat\beta_{RC}$ on each resample. Run against this repository's real panel ($n=1000$ resamples, seed 42, `data/processed/beta_rc_bootstrap.json`):

| | Parametric $N(\hat\beta,\text{SE}^2)$ | Bootstrap (empirical) |
|---|---|---|
| Estimate / mean | 5.4568 | 5.523 |
| SE / std | 1.5857 | 1.513 |
| 95% CI | [2.349, 8.565] | [2.811, 8.616] |
| Skew | 0 (assumed) | +0.197 |

Comparable width, mild right skew (not the dramatic asymmetry the Safe-R-heavy composition might have produced), and a bootstrap lower bound (2.81) meaningfully above the parametric one (2.35) — the low-$\hat\beta_{RC}$ "collapse" scenario used elsewhere in this project's sensitivity discussion is *less* likely under the empirical resampling distribution than the normal approximation implies. Stable across five seeds at $n=10{,}000$ (skew 0.24–0.27 throughout). This is [VERIFICATION] of the estimator's finite-sample behavior, not a new [ESTIMATION] — it does not change $\hat\beta_{RC}$ itself, only how honestly its uncertainty is characterized. `outputs/beta_rc_bootstrap_distribution.png` (`scripts/plot_beta_rc_bootstrap.py`) renders the histogram against the parametric curve directly.

**Permutation tests on the primary efficiency claim.** §IV.21's asymptotic $p$-value for $\rho$ relies on scipy's normal approximation to the Spearman statistic's sampling distribution — untested at the small-$n$ categories in Table 2 (Lean R, $n=7$). `permutation_test_spearman_efficiency()` (`comparison/efficiency.py`) instead randomly reassigns DCCC's observed spending across the 53 competitive races 2000 times, recomputing $\rho$ against the fixed MSG values each time: **0 of 2000 shuffles produced $|\rho|\ge0.582$** (permutation $p=0.0$ vs. asymptotic $p=4.7\times10^{-6}$) — the asymptotic test is not overstating significance here.

A second, more direct test targets a distinct concern: that the optimizer's seat gain over DCCC (§IV.21) reflects mainly the concavity of the win-probability curve — i.e., that almost any reallocation of the same dollars would look like an improvement — rather than genuine MSG-based targeting. `permutation_test_allocation_efficiency()` (`comparison/benchmark.py`) randomly reshuffles DCCC's own per-race **party-dollar** amounts (not each race's own candidate-committee money) across the same 53 races and evaluates $E[\text{Seats}]$ under each shuffle using `optimizer.allocator.nonlinear_expected_seats_at_party_dollars()` — the true $\Phi(\mu/\sigma)$ evaluation over the DCCC-controllable budget only, floors fixed. Both from 2000 shuffles, seed 42:

- DCCC's actual allocation ($E[\text{Seats}]=215.18$) is matched or exceeded by **7.7%** of random reshuffles of its own party dollars (null mean 214.28, 95% CI [213.08, 215.42]) — a sharper finding than either intermediate correction below.
- The model optimizer's true nonlinear allocation ($E[\text{Seats}]=220.52$, matching §IV.21's headline figure exactly) is matched or exceeded by **0%** of reshuffles — the optimizer's advantage is not attributable to reallocation-in-general.

**Correction history (2026-07-22, two rounds, same day).** Round 1: this test originally used the linearized approximation throughout (like the Null/Cook rows) and reported the DCCC-side figure as 100%. A separate investigation into an anomalous 2022 OOS result — the Null allocator appearing to edge out the nonlinear optimizer, `scripts/investigate_null_benchmark_bias.py` — found the linearization bias large enough to matter for this test too; fixing it gave 35.1% (2024) / 87.5% (2022). Round 2, same day: that fix still reshuffled each race's full observed dollar total, including candidate-committee money DCCC never controlled — corrected to reshuffle only the DCCC party-controllable increment, per the explicit instruction that every allocator comparison in this project should use only the DCCC budget. This moved 2024 further down (35.1% → 7.7%) but moved 2022 down less dramatically (87.5% → 72.3%), reversing which cycle shows the sharper DCCC-side finding. The model-side figure (0%) was completely robust through both rounds, in both cycles.

Both are [VERIFICATION]: they test whether the significance claims in §IV.21 survive an assumption-free empirical null, not whether the underlying MSG framework is correct. All three checks are covered by tests in `test_estimation.py::TestBootstrapBetaRC` and `test_comparison.py::TestPermutationSpearmanEfficiency`/`TestPermutationAllocationEfficiency`, and run automatically as part of `run_backtest.py` (saved to `outputs/permutation_tests.json`) and `run_estimation.py` (saved to `data/processed/beta_rc_bootstrap.json`).

---

# Part IV — Empirical Findings [EMPIRICAL]

*Claims about the world, produced by running Part III-verified code on real data. These inherit every assumption in Parts I–II, including the one untestable identification assumption at the root of the Main Result (§I.3).*

### IV.21 2024 primary sample

**Efficiency test** (`outputs/aggregate_summary_baseline.csv`): $\rho=-0.582$ ($p<0.001$, 95% CI $[-0.789,-0.307]$, $n=53$).

**By Cook category** (`outputs/spearman_by_category.csv`):

| Category | n | ρ | p |
|---|---|---|---|
| Likely D | 40 | −0.131 | 0.421 |
| Lean D | 28 | −0.389 | 0.041 |
| Toss-Up | 18 | **−0.932** | <0.001 |
| Lean R | 7 | **−0.929** | 0.003 |
| Likely R | 36 | +0.277 | 0.102 |

Misallocation concentrates at the *most contested* tier, not in safe defensive seats.

**Matched-group test** (partisan-lean-and-category-matched): $\rho=-0.559$ ($p=0.0001$, $n=44$).

**Allocator comparison** (`outputs/allocator_comparison_table.csv`; corrected 2026-07-22, three passes — `compare_allocators()` now evaluates all four rows with the true nonlinear $\Phi(\mu/\sigma)$, and every hypothetical row (Null, Cook, Model) redistributes only the DCCC-controllable party budget, holding every race's own candidate-committee money fixed, per explicit instruction: "All models/methods when compared to each other should only use the DCCC budget, that is the whole point." See Part V's sibling investigation `scripts/investigate_null_benchmark_bias.py`):

| Strategy | Expected seats | Gain vs. DCCC |
|---|---|---|
| DCCC observed | 215.18 | — |
| Cook-implied | 215.45 | +0.27 |
| Null (equal-weight) | 215.89 | +0.71 |
| Model optimizer | 220.52 | +5.34 |

Both zero-information benchmarks still beat DCCC's actual allocation, though narrowly now that every strategy is held to the real budget. The Model's advantage over both (+4.63 over Null, +5.07 over Cook) is nearly as large as its advantage over DCCC itself — a materially different, and now honest, picture. (Superseded, in order: 219.01/+3.83 and 217.71/+2.53 — linearized Null/Cook, inconsistent with the Model row's nonlinear evaluation; then 217.62/+2.44 and 217.04/+1.86 — nonlinear but still scaled to the entire two-party spending pool rather than the DCCC-controllable budget.)

**Charts:** `outputs/efficiency_frontier.png`; `outputs/msg_rank_shift_2024.png` (buggy vs. corrected MSG rank, this session).

### IV.22 2022 out-of-sample: the structural claim

$$\rho=-0.750 \quad (p<0.001,\ 95\%\ \text{CI}\ [-0.837,-0.589],\ n=61)$$

Model optimizer: 221.66 vs. DCCC's 214.87 (+6.79 seats). **This is the empirical claim, not just a code check**: the correlation *strengthens* out-of-sample, the opposite of what sample-specific overfitting would predict — the strongest evidence that DCCC misallocation is structural rather than a 2024 artifact. Chart: `outputs/efficiency_frontier_2022.png`.

### IV.23 Live 2026 application

Run 2026-07-08 (`outputs/allocation_2026_live.csv`). $B_t=\$394.3$M; $GB=D{+}5.02$ (uniform across all 434 districts); $L_t=\$911{,}047$; result $F_t=\$393{,}388{,}953$, expected seats 241.12/434.

**Allocation by Cook category** — the empirical signature of §I.10's unsolved $\Theta$ term:

| Category | n | Recommended | % of $F_t$ |
|---|---|---|---|
| Safe D | 141 | $5.9M | 1.5% |
| Likely D | 40 | $14.4M | 3.7% |
| Lean D | 30 | $20.3M | 5.2% |
| Toss-Up | 15 | $37.0M | 9.4% |
| Lean R | 10 | $58.4M | 14.8% |
| Likely R | 37 | $148.2M | 37.6% |
| Safe R | 161 | $110.1M | 27.9% |

**65.5%** of $F_t$ (Likely R + Safe R) goes to seats outside any conventional "competitive" definition. Verified as a genuine model output, not a code defect (a brief [VERIFICATION] step within this empirical finding): hand-computed $\mu,\sigma,P(\text{win})$ for individual recipients (e.g. TN-07, PVI −10.1, $\mu/\sigma=-2.32$, $P(\text{win})=1.0\%$) exactly reproduce the optimizer's inputs. The mechanism is §I.10's missing $\Theta$: with near-zero floor spending across the universe (where the log-ratio gradient is steepest) and nothing in the objective penalizing breadth, the optimizer has both the incentive and the room to spread broadly. **This is worse than an early-cycle artifact**: as of the run date, Election Day is ~4 months away, not the ~16 an earlier draft of Paper II §7.1 stated (corrected this session — see Paper II §7.1). A Θ-respecting allocator should be concentrating, not exploring, at 4 months out; the 65.5% figure is evidence of the missing patience term's cost precisely because so little runway remains, not despite it. Chart: `outputs/allocation_2026_live.png`.

*Provenance note (added 2026-07-16, Paper III audit): $B_t$, $L_t$, and $F_t$ above are a dated snapshot of the 2026-07-08 run, not values this section should be read as the ongoing source of truth for. $B_t$ is now derived by `backtest.model.budget.estimate_budget_2026()` (data_catalog.md §3.7) rather than a hand-typed literal, and every subsequent run of `scripts/plot_2026_live_allocation.py` writes the current `as_of`, $L_t$, $F_t$, and days-remaining to `data/processed/live_2026_state.json` — that file is what `scripts/solve_bellman_lsm.py` (Paper III) now reads $F_0$/today/Election Day from, not this paragraph.*

---

## 24. Complete assumptions catalog

| # | Assumption | Part/Section | Testable? |
|---|---|---|---|
| A1 | Public-data-only scope | §1 | Design choice |
| A2 | Relative (not absolute) spending drives outcomes | I.1 | Partially |
| A3 | $\alpha_0$–$\alpha_3$ descriptive, not causal | II.11 | No |
| A4 | Repeat-challenger differencing removes all confounding | I.3 | **No — the one untestable link in the Main Result** |
| A5 | $\tau$ set by judgment, not formula | II.13 | No |
| A6 | Margin normally distributed | I.5 | Partially (Brier calibration) |
| A7 | Win outcome locally linear in $G$ | I.6 | No; also superseded by II.15's actual model |
| A8 | $\sigma_i$ estimation uncertainty not propagated | II.14 | Known gap |
| A9 | $\lambda=0.7$ EMA untested | I.8 | Flagged as such in Paper II itself |
| A10 | $F_t$ deployed immediately, no patience value | I.10 | **Superseded 2026-07-22 (Part V).** No longer an assumption this framework makes — $\Theta$ is now computed, not assumed away, and the computed value argues for the opposite of immediate deployment at the live 2026 decision. |
| A11 | 2026 Cook ratings algorithmic, not sourced | §1, IV.23 | Known limitation |
| A12 | PVI proxy years (2016/2020) reused across cycles | §1, IV.23 | Known limitation |

---

## 25. Conclusion

The Main Result's chain is mechanically sound end to end (Part I), correctly estimated on real data (Part II), and verified to be correctly implemented in code (Part III) — including one real bug found and fixed this session, whose correction was itself checked against the underlying math rather than assumed. What the verified chain reports about the world (Part IV) is that DCCC capital allocation is inconsistent with the framework's efficiency condition, that this replicates and strengthens out of sample, and that the live 2026 run — while a genuine result, not a demonstration — surfaces the practical cost of the one piece the framework admits it has not solved: without a $\Theta$ term, the architecture cannot distinguish "worth funding" from "worth funding *now*," and at $F_t=\$393$M against near-zero floor spending only ~4 months from Election Day, that missing distinction is worth roughly two-thirds of the deployable budget.

**Update (2026-07-22): this paragraph describes the framework as it stood before Part V, and is kept as the historical record.** The "one piece the framework admits it has not solved" is no longer unsolved. Part V specifies $P$, solves the Bellman equation above by regression-based Monte Carlo, and reports a current, real result: $\Theta(0)$ is substantially positive at the live 2026 decision, and every tested scenario recommends holding the $393M reserve rather than deploying it — the opposite conclusion from every earlier pass at this same calculation (which, before a fifth correction found and fixed a modeling asymmetry, recommended full deployment). This does not change what Part IV §23 reports the *Θ-free* run actually did (65.5% to non-competitive seats remains a correct description of that specific run) — it changes what the framework recommends once $\Theta$ is no longer missing from it. See Part V for the full result, its correction history, and what remains open.

---

# Part V — Θ: Specified and Solved, Not Merely Formalized [Paper III, added 2026-07-22]

*Source: `docs/paper3_draft.md` and `docs/theta_followup_plan.md`. Part I §I.10 above formalizes the Bellman equation that $\Theta$ answers but deliberately leaves the state-transition law $P$ generic — "[OPEN]," in this document's own tagging. This part reports what filled that gap: $P$ is now specified and estimated from real data, the Bellman equation is solved against it, and the result has been corrected five times as errors were found — the same discipline this document already applied to the MSG gradient bug (Part III §III.17) is applied here to a longer, harder calculation. Every number below is the *current*, most-corrected value; each has a superseded predecessor, reported in the source documents rather than hidden.*

### V.1 The state-transition law $P$ — three components [ESTIMATION]

Part I §I.10's Bellman equation has an expectation operator with nothing specified to integrate over until $P$ — the law governing $\mathbf X_{t+1}\mid\mathbf X_t$ — exists. Paper III's central claim is that specifying $P$, not solving the equation that consumes it, is the actual scientific content of the $\Theta$ problem (the same relationship as a stock's volatility process to the Black–Scholes PDE that prices options on it). Three components, one per stochastic term in $\mu_{i,t+1}=\mu_{i,t}+\Delta\mu_i(p_t)+\beta_i\Delta G_t+\varepsilon_{i,t}$:

- **Opponent reaction, $\hat\eta(\text{tier})$.** Fit from a real, dated 2012–2024 panel of FEC Schedule E independent-expenditure filings (`estimate_eta_reaction.py`), tiered by Cook rating rather than pooled to a single scalar (a single $\eta$ was checked and rejected as mis-specified — contested tiers react very differently from safe ones). Cycle-weighted (random-effects, DerSimonian–Laird) point estimates in contested tiers: Toss-Up 0.277, Lean D 0.277, Lean R 0.304 — roughly a quarter to a third of a dollar-for-dollar match, not the naive $\eta\approx1$ prior. A leave-one-cycle-out check found 5 of 7 tiers vary significantly cycle-to-cycle (precision within a pool $\ne$ temporal stability), so this is reported as a distribution to sample from, not a fixed constant.
- **National environment, $\sigma_G(\Delta t)$.** Fit from a recovered four-cycle (2018–2024) daily generic-ballot series (a discontinued FiveThirtyEight endpoint, recovered via Wayback Machine). $\sigma_G(\Delta t)\approx0.18$–$0.20\times\sqrt{\Delta t\text{ days}}$, stable from 30–270 days — a random walk is a good approximation over the 3–9 month horizon that matters near Election Day; mean reversion only becomes visible past ~1 year. An OU-with-drift fit found no statistically significant drift at the live decision's ~110-day horizon ($p=0.37$), ruling out "the current D+5.02 environment is unusually favorable and should be locked in" as an explanation for anything reported below.
- **Idiosyncratic uncertainty, $\varepsilon_{i,t}$.** The one component **not** estimated as a genuine process — district-level polling density (well under 10% of competitive races receive 2+ public polls in a cycle) makes fitting a real per-race time series infeasible, confirmed by checking a live polling API directly rather than assumed. Treated instead as a bounded proxy borrowing the national process's resolution rate: $\sigma_{i,t}=\sigma_i^{\text{static}}\sqrt{1-e^{-\lambda(T-t)}}$, $\lambda=0.00536\,\text{day}^{-1}$ fit from $\sigma_G(\Delta t)$'s term structure. Reported explicitly as a proxy, not a fitted $\varepsilon_{i,t}$ process, because the data to do the latter does not exist in usable quantity — a documented, likely-permanent scope boundary rather than a gap quietly papered over.

The assembled simulator built from these three components was validated against real, held-out 2022/2024 outcomes before being trusted for anything: a September 1 snapshot's $\mu_{i,\text{Sept}}$ rank-correlates with realized November margin at $\rho=0.457$ (2022) and $0.624$ (2024), both $p<0.001$ — the underlying valuation chain a simulated path is built from is not directionless.

### V.2 Solving for $\Theta$: regression-based Monte Carlo [MATH + VERIFICATION]

Once $P$ exists, computing $V_t$ and $\Theta(t)=V_t^{\text{wait}}-V_t^{\text{deploy-now}}$ is standard machinery (Longstaff–Schwartz): simulate $K{=}2000$ forward paths of $\mathbf X_t$ under $P$; at each period, regress simulated continuation values on a compressed four-to-six-feature portfolio-level basis (per-race features are infeasible at 400+ races — `theta_followup_plan.md` §7.2 shows why directly); proceed by backward induction from Election Day. A four-part self-consistency gate (`scripts/simulate_and_validate.py`, 5,000 paths/cycle) confirmed the assembled simulator reproduces each calibrated input's own target (simulated $\sigma_G$, $\hat\eta$ recovery, cumulative $\varepsilon$ variance, margin spread all matched their targets) before any path was trusted for the backward induction itself.

### V.3 Correction history — five corrections, each changing the numeric result [VERIFICATION]

This calculation was wrong four times before the current result, each time in a way found by checking the mechanism rather than trusting the output — the same standard Part III §III.17 applied to the MSG gradient:

1. **$\hat\eta$ and $G_t$ never actually entered the first run** — passed in and stored for reporting, never multiplied into anything. Fixed by wiring both into the deploy-branch gradient and a fifth regression feature respectively.
2. **A frozen-floor bug** in the continuous-deployment-fraction generalization: repeated LP calls re-used the *original* floor regardless of what a path had already committed, which would have silently produced a flat rather than concave value-of-budget curve.
3. **`beta1_open` inconsistency**: the deploy branch's MSG *gradient* already used the calibrated open-seat elasticity (6.977 vs. 5.457), but the *level* of $\mu_i$ feeding the same backward induction did not, for all 49 Open-seat races (11% of the universe) — found by writing this project's first automated tests for the Bellman/LSM code.
4. **A "permanent" data gap turned out not to be permanent**: candidate-committee spending was assumed to have no per-filing-date source anywhere in this repository, so $D_{i,t}$ was held fixed on the wait branch and $\hat\eta$ had nothing to react to while waiting. Checking the FEC API's `/committee/{id}/reports/` endpoint directly (rather than re-deriving the claim from this project's own prior documentation) found it does carry dated filings — a real dated panel was fetched and calibrated into a spending-trickle rate.
5. **An asymmetric convolution**, found by checking the mechanism of the very first re-run under correction 4 before trusting its output ($\Theta$ jumped to $+6$–$8$ seats, an order of magnitude beyond anything this line had produced): the deploy branch's "integrate over future drift in one step" shortcut is only valid for mean-zero movement, and $D_{i,t}$ was no longer mean-zero once a real, deterministic trickle was added. Fixed by adding the trickle's expected drift to the deploy branch's convolution.

### V.4 The current result [EMPIRICAL]

With all five corrections applied and the trickle calibration extended from a 2-cycle to the full 2012–2024 panel (the same naive-pool-vs-cycle-weighted correction already applied to $\hat\eta$ in Part II; every tier's rate fell 16–43%, shrinking magnitudes without changing direction):

| Scenario | $\Theta(0)$, live (~98 days out) | frac(hold), live | $\Theta(0)$, 1-year counterfactual | frac(hold), 1yr |
|---|---|---|---|---|
| `eta_fit_2022` | **+0.997** | 100% | +2.438 | 100% |
| `eta_fit_2024` | **+1.808** | 100% | +2.925 | 100% |
| `eta_bootstrap_all_cycles` | **+1.295** | 98.9% | +2.957 | 97.2% |

**Every scenario recommends holding the reserve, not deploying it — the first result anywhere in this research line where the corner flips to "wait."** Every earlier pass (before correction 5, and all of corrections 1–4) recommended full deployment, several unanimously across 2,000 simulated paths. The continuous-deployment-fraction generalization (the impulse-control version of the same decision, ruling out "the binary framing is masking a middle option") was re-tested under the same fix and reaches the same conclusion: hold wins by 0.77–1.29 expected seats over full deployment, confirmed at an 11-point grid resolution.

**This new direction is also the one consistent with real committee behavior, not contradicted by it.** A direct check of real dated IE filings (`theta_followup_plan.md` §10) found actual independent-expenditure committees spend only 1.6–4.4% of their eventual full-cycle total by September 1 in both 2022 and 2024 — holding back 95%+ of spending until the final two months. The pre-correction "deploy now" result contradicted this observed pattern; the corrected "hold" result does not.

### V.5 What remains open [OPEN]

- $\hat\eta$ is applied to a candidate-spending trickle it was never estimated on — it was fit on IE-to-IE reaction, not reaction to organic candidate-committee growth. Reported as an untested extension of an existing estimate, not a new one.
- $\varepsilon_{i,t}$ remains the rate-borrowed proxy of §V.1, not a fitted per-race process — the data-density constraint is treated as likely permanent, not a to-do item.
- Part IV §23's "solver-consistent comparison against Paper II's 65.5% baseline" (apply $\Theta(0)$'s decision, then compare the resulting tier-share breakdown) no longer has a natural target: a "hold" recommendation has no allocation to score a tier-share breakdown against. Reframing this comparison for a hold recommendation is an open item, not resolved here.
- The Bellman machinery's own test coverage (`tests/test_bellman_lsm.py`) is what caught correction 3; it did not exist before this research line was well underway, and its late arrival is itself the reason corrections 1–3 took as long as they did to surface.

Every claim in Part IV rests on Part I §I.3's identification assumption. That assumption is stated, not proven, and cannot be proven from observational data — which is exactly why it is the one arrow in the Main Result not labeled [MATH].
