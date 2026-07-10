# Formal Derivation and Computational Verification of the Political Capital Allocation Framework

*Every number below was pulled from a file in this repository as of this session; file paths are given so each claim is independently checkable.*

---

## 0. Main Result

**Claim.** The framework defines a mapping

$$\mathcal D \ \xrightarrow{\text{causal estimation}}\ \hat\beta_{RC} \ \xrightarrow{\text{OLS}}\ (\alpha,\beta_2,\beta_3) \ \xrightarrow{}\ (\mu_i,\sigma_i) \ \xrightarrow{\text{chain rule}}\ \text{MSG}_i \ \xrightarrow{\text{KKT}}\ s_i^*$$

where $\mathcal D$ is the public data described in Section 1. **Exactly one arrow in this chain is not mechanically forced by the arrow before it**: the first, $\mathcal D\to\hat\beta_{RC}$, which requires an untestable causal-identification assumption (Section 4). Every arrow after it — the OLS fit, the margin-to-probability conversion, the MSG gradient, the portfolio optimum — is a deterministic function of what came before, provably so given the stated model form. Paper II extends the last arrow, $s^*_i\to s^*_{i,t}$, to a sequence re-solved each period over deployable capital only (Section 9 of Part I), and identifies but does not close one further gap: the mapping has no term pricing the value of *not yet* committing capital (Section 10).

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

**[OPEN]** Solving this requires specifying the state-transition $f$'s stochastic structure, deliberately left generic. No closed form for $\Theta(t)$ is derived or claimed anywhere in this project — Part IV §23 shows what its *absence* produces empirically.

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

217+ tests across 15 files (`tests/`), covering margin prediction, win-probability/MSG computation, the optimizer, σ-model ordering, PVI construction, the dynamic (Paper II) ledger/state/EMA/horizon modules, and comparison/benchmark logic. All passing as of this session.

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

**Allocator comparison** (`outputs/allocator_comparison_table.csv`):

| Strategy | Expected seats | Gain vs. DCCC |
|---|---|---|
| DCCC observed | 215.18 | — |
| Null (equal-weight) | 219.01 | +3.83 |
| Cook-implied | 217.71 | +2.53 |
| Model optimizer | 220.52 | +5.34 |

Both zero-information and forecast-based benchmarks beat DCCC's actual allocation.

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

**65.5%** of $F_t$ (Likely R + Safe R) goes to seats outside any conventional "competitive" definition. Verified as a genuine model output, not a code defect (a brief [VERIFICATION] step within this empirical finding): hand-computed $\mu,\sigma,P(\text{win})$ for individual recipients (e.g. TN-07, PVI −10.1, $\mu/\sigma=-2.32$, $P(\text{win})=1.0\%$) exactly reproduce the optimizer's inputs. The mechanism is §I.10's missing $\Theta$: with near-zero floor spending everywhere this early in the cycle (where the log-ratio gradient is steepest) and nothing in the objective penalizing breadth, the optimizer has both the incentive and the room to spread broadly. Chart: `outputs/allocation_2026_live.png`.

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
| A10 | $F_t$ deployed immediately, no patience value | I.10 | Falsified as a good approximation by IV.23 |
| A11 | 2026 Cook ratings algorithmic, not sourced | §1, IV.23 | Known limitation |
| A12 | PVI proxy years (2016/2020) reused across cycles | §1, IV.23 | Known limitation |

---

## 25. Conclusion

The Main Result's chain is mechanically sound end to end (Part I), correctly estimated on real data (Part II), and verified to be correctly implemented in code (Part III) — including one real bug found and fixed this session, whose correction was itself checked against the underlying math rather than assumed. What the verified chain reports about the world (Part IV) is that DCCC capital allocation is inconsistent with the framework's efficiency condition, that this replicates and strengthens out of sample, and that the live 2026 run — while a genuine result, not a demonstration — surfaces the practical cost of the one piece the framework admits it has not solved: without a $\Theta$ term, the architecture cannot distinguish "worth funding" from "worth funding *now*," and at $F_t=\$393$M against near-zero floor spending sixteen months from Election Day, that missing distinction is worth roughly two-thirds of the deployable budget.

Every claim in Part IV rests on Part I §I.3's identification assumption. That assumption is stated, not proven, and cannot be proven from observational data — which is exactly why it is the one arrow in the Main Result not labeled [MATH].
