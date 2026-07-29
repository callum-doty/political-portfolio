---
title: "Estimating the State-Transition Model for Sequential Campaign Allocation"
subtitle: "The Political-State Analog of a Volatility Process, and the Value of Waiting It Implies"
author: "Callum Doty"
date: "July 2026"
geometry: margin=1in
fontsize: 11pt
linestretch: 1.12
toc: true
toc-depth: 3
numbersections: true
colorlinks: true
linkcolor: NavyBlue
citecolor: NavyBlue
urlcolor: NavyBlue
header-includes:
  - \usepackage{amsmath,amssymb,mathtools}
  - \usepackage{booktabs}
  - \usepackage{longtable}
  - \usepackage{array}
  - \usepackage{caption}
  - \usepackage{float}
  - \floatplacement{figure}{H}
  - \usepackage{fancyhdr}
  - \pagestyle{fancy}
  - \fancyhf{}
  - \fancyhead[L]{\small\slshape Estimating the State-Transition Model for Sequential Campaign Allocation}
  - \fancyhead[R]{\small\thepage}
  - \renewcommand{\headrulewidth}{0.3pt}
  - \usepackage[format=plain,labelfont=bf,font=small]{caption}
---

\begin{abstract}
\noindent
A companion paper (Paper II) builds a sequential architecture for deploying campaign capital -- a rollout policy that re-solves a single-period optimizer at each reporting period, distinct from full model-predictive control -- and discovers a gap this policy cannot express: capital held rather than spent has option value, because retaining it preserves the ability to react to information that has not yet arrived. It names this gap $\Theta$, states the Bellman equation that would price it, and stops there deliberately, because that equation contains an expectation operator with nothing specified to integrate over. This paper argues that treating the Bellman equation as the remaining problem is backward, in the same sense that asking for the value of a stock option is backward before anyone has specified how the stock price moves: an option's value is a corollary of a specified stochastic process for the underlying, not an independently derived quantity. This paper is the political-science analog of specifying that process. We define the campaign state vector explicitly, decompose its evolution into a fully-derived control component (inherited from Paper I) and three components requiring genuine estimation -- opponent reaction to a committee's own spending, a national political-environment process, and race-level idiosyncratic uncertainty -- and estimate each from public data where the data allows. Opponent reaction is estimated from a seven-cycle (2012--2024) panel of dated independent-expenditure filings, tiered by competitiveness, with a cycle-weighted (random-effects) point estimate of $\hat\eta\approx0.26$--$0.38$ in genuinely contested tiers after confirming most tiers show real cycle-to-cycle variation rather than a single stable constant. The national environment process is calibrated from a five-cycle historical generic-ballot series, giving a term structure $\sigma_G(\Delta t)\approx0.18$--$0.20\times\sqrt{\Delta t}$ that is empirically indistinguishable between a random walk and a mean-reverting process over the three-to-nine-month horizon that matters near Election Day. Race-level idiosyncratic uncertainty cannot be estimated as a genuine time-varying process under the public-data-only constraint this research program maintains, given that well under 10\% of competitive House districts receive repeated public polling in a typical cycle; it is instead treated as an explicit, bounded proxy that borrows its resolution rate from the calibrated national process, a choice we defend and flag rather than present as equivalent to a fitted model. The assembled simulator is validated against held-out 2022 and 2024 data before being trusted for pricing (a September information set rank-correlates with eventual November outcomes at $\rho=0.47$ and $0.65$ respectively) and passes a four-part internal self-consistency check. Once specified and estimated, $\Theta$ is a standard application of regression-based Monte Carlo (Longstaff--Schwartz) backward induction, not a new contribution. Solved against the live 2026 decision, $\Theta(0)$ is substantially positive -- $+4.6$ to $+5.9$ expected seats across three calibration scenarios at a 98-day horizon -- and every scenario, in both a binary hold-or-deploy framing and a genuinely continuous deployment-fraction generalization, recommends holding the deployable reserve rather than committing it immediately. This reverses an earlier, incorrect version of this same calculation that omitted a real channel (candidate committees' own organic spending growth while a committee waits), and a subsequent, independently-found variance-specification error (a double-counted idiosyncratic-uncertainty term in the deploy-branch convolution) that had suppressed $\Theta(0)$ to a much smaller $+1.3$-to-$+1.7$ range; both corrections are reported with their mechanism and magnitude rather than folded silently into a final number. A mechanism decomposition further shows that roughly 70\% of $\Theta$'s value, isolated channel by channel, comes from candidate committees' predictable organic spending growth rather than from resolving genuine uncertainty -- a real, quantified, and reported qualification to the paper's real-options framing, not a refutation of it. The corrected result is, unlike the earlier ones, consistent with this project's own directly-computed evidence (Section 9.3) that real independent-expenditure committees hold back the large majority of their spending until the final two months of a cycle. This paper's contribution is the specified and estimated transition law, $P$; $\Theta$ is what $P$ implies.
\end{abstract}

\vspace{0.5em}
\noindent\textbf{Keywords:} optimal stopping, real options, state-space estimation, regression-based Monte Carlo, Ornstein--Uhlenbeck process, campaign finance, stochastic control

\newpage

# Introduction

## The Question This Paper Answers, and the One It Does Not

Paper II asks how a committee should deploy capital sequentially, given a valuation model, and in building that architecture discovers a gap: nothing in it prices the difference between "this race is worth funding" and "this race is worth funding *right now*." Paper II calls the missing object $\Theta$, states the Bellman equation it would need to solve, and stops there deliberately.

The natural next move is to treat that Bellman equation as the remaining problem and try to solve it. This paper argues that is the wrong next move, for a precise reason: a Bellman equation over an unspecified state-transition law is not merely difficult -- it is not yet a well-posed mathematical object. Consider the equation itself,

$$V_t(\mathbf X_t,F_t) = \max_{0\le\mathbf p_t\le F_t}\ \mathbb E_P\!\left[\,V_{t+1}(\mathbf X_{t+1},F_t-\mathbf 1'\mathbf p_t+\text{fundraising}_t)\,\right]$$

Every symbol here is defined except one: $P$, the law governing how $\mathbf X_{t+1}$ is generated from $\mathbf X_t$. Without $P$, this expression has an expectation operator with nothing inside it to take an expectation *over*. It is not that solving this equation is hard without $P$ -- it is that the equation does not yet say anything without $P$. Specifying $P$ is therefore not a preliminary step before the real work; it is the entire remaining scientific content of the problem. Once $P$ exists, computing $V_t$ (and therefore $\Theta$) is standard: simulate forward paths under $P$, and use a regression-based Monte Carlo method (Longstaff and Schwartz 2001) to estimate continuation values by backward induction. That machinery is decades old and well understood. It is not what makes this problem hard. **This paper's job is to specify and, where the data allows, estimate $P$.** Everything about $\Theta$, reserve policy, and optimal stopping is a downstream implication of that specification, not a separate derivation.

## The Finance Analogy, Made Precise

The correspondence to option pricing is exact enough to be load-bearing, not decorative.

**Table 1: The Option-Pricing Correspondence**

| Finance | This project |
|---|---|
| Stock price $S_t$ | Campaign state $\mathbf X_t$ (Section 3.2) |
| Price process $dS_t=\mu S_t\,dt+\sigma S_t\,dW_t$ | State-transition law $P$ (Sections 4.2--4.4) |
| Volatility $\sigma$ | $G_t$'s innovation variance, $\varepsilon_{i,t}$'s decay structure, opponent reaction $R_t(D_t)$ |
| Option value $V(S_t,t)$ | Value function $V_t(\mathbf X_t,F_t)$ |
| Early-exercise value / American option premium | $\Theta(t)$, the value of not yet committing capital |
| Black--Scholes PDE / binomial tree / Longstaff--Schwartz | The Bellman recursion above, solved once $P$ is known |

No one asks "what is the value of waiting to exercise this option?" before specifying $\sigma$. The question is not answerable in that order. The same is true here: Paper II's Bellman equation, exactly like an option-pricing PDE, is the *consumer* of a specified process, not a substitute for specifying one.

## What Motivates This Now

Paper II's live 2026 run gives this urgency beyond theoretical motivation. At approximately four months from Election Day, Paper II's rollout policy -- which implicitly assumes $P$ contributes nothing beyond what the current period already knows -- recommends a majority of deployable capital to Likely R and Safe R seats, including a nontrivial allocation to deeply-safe districts (Paper I's persuasion-ceiling-corrected pipeline: 51.4% of a live \$393M reserve). This is the empirical size of the gap a specified $P$ closes, and Section 8 reports what closing it changes about the live recommendation.

\newpage

# Related Literature

## Option Pricing and Real Options

The mathematical machinery this paper ultimately applies -- regression-based Monte Carlo pricing of an American-style option with early-exercise features -- is due to Longstaff and Schwartz (2001), building on the foundational option-pricing framework of Black and Scholes (1973) and Merton (1973). The extension of that machinery from financial to real (physical or organizational) assets is the subject of real-options theory (McDonald and Siegel 1986; Dixit and Pindyck 1994), which this paper's companion (Paper II) already introduces as the conceptual frame for uncommitted campaign capital. This paper's relationship to that literature is specific: the machinery is not this paper's contribution (Section 1.1), and is applied here essentially unmodified once $P$ exists (Section 4.6).

## State-Space Estimation and Time-Series Processes

Specifying $P$ requires standard time-series tools applied to a genuinely novel domain. The choice between a random walk and a mean-reverting (Ornstein--Uhlenbeck) specification for a bounded political quantity is a classical model-selection problem (the Ornstein--Uhlenbeck process itself: Uhlenbeck and Ornstein 1930); realized-volatility term-structure estimation, used here to calibrate the national-environment process's horizon-dependent standard deviation directly from data rather than assuming a parametric form, follows the general logic of realized-volatility estimation in financial econometrics (Andersen and Bollerslev 1998). State-space filtering more broadly (Kalman 1960) is the natural refinement of the smoothing rule Paper II uses for its own state update, though this paper does not implement a full Kalman treatment (Section 10.2).

## Political Science: Strategic Response and Forecasting

Paper I already situates the campaign finance and election-forecasting literatures relative to this research program; two threads bear directly on this paper specifically. Erikson and Palfrey (2000) model campaign spending as a simultaneous strategic game, establishing the theoretical prior this paper's opponent-reaction estimate (Section 4.2, 6.1) tests directly with data: that a committee's own spending decision changes, rather than simply adding to, the opposing side's. Gelman and King (1993), already cited in Paper I for the fundamentals-versus-polls decomposition motivating a race's expected margin as a structural quantity distinct from its moment-to-moment noise, is the same distinction this paper's separation of $\mu_{i,t}$ (control-driven) from $\varepsilon_{i,t}$ (idiosyncratic shock) formalizes for an allocation, rather than forecasting, purpose.

## Research Gap

No existing work specifies and estimates a full state-transition law for a political campaign's decision-relevant state, suitable for pricing the value of delaying an irreversible spending commitment. The option-pricing and real-options literatures supply the valuation machinery in general form; they do not supply a calibrated instance for this domain. The strategic-interaction and forecasting literatures supply pieces of the transition law -- evidence that spending elicits a reaction, methods for tracking a national environment factor -- but neither assembles them into a joint process an optimal-stopping calculation can consume, and neither confronts the practical data constraints (Section 5) that determine which components of that process can actually be estimated from public data and which cannot.

\newpage

# Problem Formulation

## Notation

**Table 2: Notation (in addition to Papers I and II)**

| Symbol | Meaning |
|---|---|
| $P$ | the state-transition law governing $\mathbf X_{t+1}\mid\mathbf X_t$ (this paper's subject) |
| $G_t$ | national generic-ballot point estimate (D $-$ R) at period $t$ |
| $\varepsilon_{i,t}$ | race-level idiosyncratic shock to $\mu_{i,t}$ |
| $R_t(D_t)$ | opponent (Republican-aligned) spending as a reactive function of the committee's own control |
| $\eta(\text{tier})$ | opponent-reaction coefficient, tiered by Cook competitiveness |
| $\sigma_G(\Delta t)$ | the national-environment process's realized-volatility term structure |
| $\lambda$ | decay rate governing how race-level idiosyncratic uncertainty resolves over time |
| $V_i(t)$ | cumulative remaining idiosyncratic-uncertainty target at time $t$ for race $i$ |
| $V_t(\mathbf X_t,F_t)$ | the value function: expected seats achievable from state $\mathbf X_t$ with deployable capital $F_t$ remaining |
| $\Theta(t)$ | $V_t^{\text{wait}}-V_t^{\text{deploy-now}}$, the value of waiting |
| $K$ | number of simulated Monte Carlo paths |

## The State Vector $\mathbf X_t$

Paper II leaves $\mathbf X_t$ informal and its transition operator $f$ fully generic. Before any component of $P$ can be specified, $\mathbf X_t$ itself needs a precise definition. Grounding this in the sequential architecture's own implementation, the state at reporting period $t$ is

$$\mathbf X_t = \Big(\ \{\mu_{i,t},\ \sigma_{i,t},\ D_{i,t},\ R_{i,t},\ L_{i,t}\}_{i=1}^N,\ \ G_t,\ \ F_t\ \Big)$$

where, per race $i$: $\mu_{i,t}$ and $\sigma_{i,t}$ are the smoothed expected-margin and margin-uncertainty estimates (Paper II's valuation, re-estimated and EMA-smoothed each period); $D_{i,t}$ and $R_{i,t}$ are cumulative Democratic- and Republican-aligned spending to date; $L_{i,t}$ is committed capital already irreversible for that race. At the aggregate level, $G_t$ is the national generic-ballot point estimate and $F_t=B_t-\sum_iL_{i,t}$ is deployable capital (Paper II's ledger identity).

**Table 3: Evolution Mechanism by Component**

| Component | Evolution mechanism | Status |
|---|---|---|
| $D_{i,t}$ | **Control**: $D_{i,t+1}=D_{i,t}+p_{i,t}$, the committee's own decision | Fully specified (the decision variable) |
| $\mu_{i,t}$ | **Control + two stochastic shocks**: $\mu_{i,t+1}=\mu_{i,t}+\Delta\mu_i(p_t)+\beta_i\Delta G_t+\varepsilon_{i,t}$ | Control term derived (Paper I); shocks require Sections 4.3--4.4 |
| $G_t$ | **Stochastic process**, exogenous to any single committee's decisions | Requires Section 4.3 |
| $R_{i,t}$ | **Reactive process**, a function of the committee's own control | Requires Section 4.2 |
| $F_t,\ L_{i,t}$ | **Deterministic bookkeeping** given $B_t$ and the ledger identity | Fully derived (Paper II) |
| $\sigma_{i,t}$ | Smoothed via Paper II's EMA; no independent process proposed here | Explicitly out of scope |

Of six rows, two are already fully solved by Papers I--II, one is definitional bookkeeping, and three are genuinely unresolved. This paper treats those three as co-equal objects of estimation, not as a primary process with two footnotes.

## Why Calibration Precedes Optimization

This is stated as its own claim because it is this paper's central methodological point: **without a calibrated $P$, the Bellman equation above is not difficult to solve -- it is undefined.** "Difficult" describes a well-posed problem that resists an easy method. An expectation operator with no specified distribution to integrate against is not that; it is a placeholder. It would be a mistake to pick a convenient distribution for $G_t$ and $\varepsilon_{i,t}$ purely so the equation can be exercised; that produces a number, but not a defensible one, and the number would carry false precision. The correct sequencing is: estimate $P$ from data, report honestly where it cannot yet be estimated, and only then compute $\Theta$ -- carrying forward, explicitly, whatever uncertainty a component of $P$ that cannot be fully estimated implies (Section 4.4).

## The Value Function and the Stopping Problem

Given a specified $P$, the value function satisfies the Bellman recursion of Section 1.1, with boundary condition $V_T(\cdot,F_T)=$ Paper I's static payoff at Election Day ($\Theta(T)=0$: nothing left to wait for once the election has occurred). The object this paper ultimately computes is $\Theta(t)=V_t^{\text{wait}}-V_t^{\text{deploy-now}}$: the value of retaining $F_t$ uncommitted for one more period, against the value of deploying it now via Paper I's static optimizer, is a standard implication of $P$, not a new derivation, once $P$ exists (Section 4.6).

\newpage

# Theoretical Framework

This section is the paper's heart: specification of each stochastic component of $P$, the resulting fully-assembled state-transition model, and the machinery -- standard once $P$ exists -- that turns it into $\Theta$.

## Opponent Reaction $R_t(D_t)$

### Why This Is Not "Just Another Stochastic Term"

The other two stochastic components ($G_t$, $\varepsilon_{i,t}$) enter $\mathbf X_t$'s transition additively, alongside the control term, without altering what the control term *means*. Opponent reaction is different in kind: if Republican-aligned spending responds to Democratic increments at some rate $\eta$, the *effective* control is not $\Delta\mu_i(p_t)$ as Paper I derives it holding $R_i$ fixed -- it is $\Delta\mu_i(p_t)$ evaluated against a moving $R_{i,t}$ that partially offsets the increment. Paper I's optimizer already encodes this mechanically:

$$R_i(D_i) = R_{i,\text{base}} + \eta\cdot\max(0,\ \text{party}_i - \text{party}_{i,\text{obs}}), \qquad \eta\in[0,1]$$

At $\eta=0$, Paper I's static gradient is exactly correct. At $\eta\to1$ (dollar-for-dollar matching), the log-ratio term driving the entire marginal-seat-gain chain rule collapses toward zero -- the committee's spending decision stops mechanically converting into margin movement at all. **This is not a refinement to the control term; it is a statement about how much of the control term is real.** A single scalar $\eta$ is very likely mis-specified: the economically plausible prior is that opponents match aggressively in Toss-Ups, where a marginal dollar changes the outcome, and largely ignore spending in races that are not competitive for either side. The primary specification is therefore $\eta(\text{tier})$, fit separately by Cook competitiveness tier, not a pooled scalar.

### Specification

$$\Delta R_{i,t}^{\text{IE}} = \eta(\text{tier}_i)\cdot\Delta D_{i,t-1}^{\text{IE}} + u_{i,t}$$

with race fixed effects applied via within-(cycle, district) demeaning, pooled across a reconstructed and cleaned panel of date-bucketed independent-expenditure filings, $\eta$ interacted with Cook tier. Section 5.4 documents the data-cleaning steps (amendment resolution, duplicate-transaction and implausible-amount filtering) this specification requires and that a cycle-cumulative analysis does not surface.

## The National Environment Process $G_t$

### Candidate Specifications

Two natural candidates: a random walk, $\Delta G_t\sim N(0,\sigma_G^2\Delta t)$, under which variance grows unboundedly with horizon; and a mean-reverting Ornstein--Uhlenbeck process, $dG_t=\kappa(\bar G-G_t)dt+\sigma_G\,dW_t$, under which variance saturates. These have materially different implications for $\Theta$ in principle -- a random walk implies option value keeps growing the longer one waits, while mean reversion implies most resolvable uncertainty is realized within a bounded window -- but the generic ballot is bounded by underlying partisanship, so formal model selection would very likely favor OU over a random walk almost regardless of the data, while the mean-reversion speed implied by a realistic lookback window is typically slow enough that over the three-to-six-month horizon actually relevant to $\Theta$ near Election Day, the two specifications are nearly indistinguishable in their implications (confirmed empirically, Section 6.2). The primary deliverable of this section is therefore not a model-selection verdict between the two, but the empirical, non-parametric term structure $\sigma_G(\Delta t)$ itself -- realized volatility as a direct function of horizon, estimated from the historical series without forcing a Gaussian process form onto it first.

### $\lambda$ for the Idiosyncratic-Uncertainty Decay Proxy

Fitting $\text{Var}(\Delta G)(t)=A(1-e^{-t/\tau})$ to the pooled historical term structure (Section 6.2) yields a decay rate $\hat\lambda=1/\hat\tau$, used directly in Section 4.4's idiosyncratic-uncertainty proxy below -- the assumption being that idiosyncratic information resolves at a rate comparable to national information, absent any race-specific data to say otherwise.

## Race-Level Idiosyncratic Uncertainty $\varepsilon_{i,t}$

### What Already Exists, and What Is Missing

Paper I's $\sigma_i$ model is a **cross-sectional** fit -- how much residual uncertainty a race of a given type carries once, not how that uncertainty evolves or resolves over a cycle. A genuine $\varepsilon_{i,t}$ process requires knowing how much of a race's idiosyncratic uncertainty resolves per unit time, and how that resolution correlates across races beyond what $G_t$ already captures.

### A Data Constraint, Likely Permanent, and Why the Obvious Fallback Is Dangerous

Estimating this genuinely requires district-level polling history across the competitive universe. In a typical recent cycle, well under 10% of House districts receive two or more public polls at all, and most of those cluster in the final weeks before Election Day -- not enough to fit a genuine time-series process for $\varepsilon_{i,t}$ per race; for the large majority of races the effective sample size is one observation or zero. A tempting fallback -- treating $\varepsilon_{i,t}$ as a static draw from Paper I's cross-sectional $\sigma_i$ distribution -- is not a neutral simplification; it is wrong in a specific, consequential direction. Treating $\varepsilon_{i,t}$ as a static draw implicitly assumes all of a race's idiosyncratic uncertainty resolves instantaneously, equivalent to assuming there is no idiosyncratic information left to arrive -- exactly backward, since it would make $\Theta$ collapse toward zero for the wrong reason (nothing left to wait for) rather than the right one (nothing left to *learn*).

### Proposed Treatment

We instead borrow the resolution *rate*, not the distribution, from Section 4.3's calibrated national process, applied as a shrinkage/decay factor on the static cross-sectional $\sigma_i$:

$$\sigma_{i,t} = \sigma_i^{\text{static}}\cdot\sqrt{1-e^{-\lambda(T-t)}}$$

where $\lambda$ is fit from $\sigma_G(\Delta t)$'s term structure (Section 6.2) rather than estimated separately per race. This is explicitly a proxy, not a fitted $\varepsilon_{i,t}$ process, and is reported as one: it prevents $\Theta$ from being inflated by an implausible "surprise arrives all at once on Election Day" assumption, but it does not constitute having estimated race-level dynamics from data, because the data to do so does not exist in usable quantity (Section 10.1).

## The Deploy-Branch Convolution Identity

A committee that deploys its full reserve at period $t$ does not thereby learn nothing about how the future would have unfolded; it forecloses the ability to *act* on that information, but the terminal win probability the deploy branch should be scored against still reflects the true distribution of where $\mu_i$ ends up by Election Day, not merely its period-$t$ value. Formally, if $\mu_i(T)=\mu_i(t)+\xi$ for a mean-zero remaining shock $\xi\sim N(0,V_i(t))$ (the movement not yet realized at $t$, i.e. the part of the idiosyncratic-uncertainty budget $\sigma_i^2$ that has not yet resolved as of $t$), then, applied to a $\mu_i(t)$ that is itself already a clean structural estimate with no resolved shock embedded in it,

$$\mathbb E_\xi\big[\Phi\big((\mu_i(t)+\xi)/\sigma_i\big)\big] = \Phi\!\left(\frac{\mu_i(t)}{\sqrt{\sigma_i^2+V_i(t)}}\right)$$

a standard Gaussian-convolution identity (Appendix B.1 derives it). This lets the "deploy now" branch of the backward induction analytically integrate over the expected effect of all remaining idiosyncratic drift in one step, rather than requiring the simulator to wait through it path by path. The identity is exact for what it integrates over -- the expected effect of unresolved, mean-zero Gaussian shocks on terminal win probability -- and Section 8.4 shows it has a direct and important consequence for how $\Theta$ behaves as the horizon lengthens: it does not, however, capture the value of *adaptive* decision-making, that new information arriving mid-campaign could change *how* the reserve is allocated, not merely *whether* it is deployed (Section 9.2 returns to this scope boundary directly).

**A critical asymmetry.** The convolution identity above requires $\xi$ to be genuinely mean-zero. This holds for idiosyncratic shocks and, absent any real spending growth while a committee waits, trivially held for $D_{i,t}$ itself in an earlier version of this model (Section 8.6's correction). It does *not* hold once $D_{i,t}$ is given a real, deterministic, non-zero-mean growth process (Section 6.4) -- a committee's own candidate committees continue raising and spending money organically while the party committee waits. A convolution that omits this deterministic drift silently understates the deploy branch's true value, biasing the comparison toward "wait" for the wrong reason. Section 8.6 reports finding and correcting exactly this asymmetry.

**A variance double-count, found and corrected in this same audit.** The identity above is stated for a $\mu_i(t)$ with *no* resolved shock embedded in it -- $\sigma_i^2$ and $V_i(t)$ are meant as two disjoint pieces of the same idiosyncratic-uncertainty budget (resolved-by-$t$ and remaining-after-$t$), not two independent, additive sources. The implemented simulator, however, constructs $\mu_i(t)=\mu_i^{\text{struct}}(t)+\varepsilon_{i}^{\text{cum}}(t)$, where $\varepsilon_i^{\text{cum}}(t)$ is the *already-realized* share of the idiosyncratic budget as of $t$ (Appendix B.2's telescoping construction: $\text{Var}(\varepsilon_i^{\text{cum}}(t))+V_i(t)$ is constant in $t$). Applying the convolution above to this already-partly-resolved $\mu_i(t)$ and *still* adding the full $\sigma_i^2$ term prices the same idiosyncratic budget twice -- once through the realized simulated shock, once again through the convolution's own $\sigma_i^2$ term -- inflating the deploy branch's effective variance by up to a factor of roughly 2--3 at horizons well before Election Day (confirmed numerically: at the live 98-day horizon, $\text{Var}(\varepsilon_i^{\text{cum}}(t))+V_i(t)=91.97$ for a representative $\sigma_i=15$ throughout, versus $\sigma_i^2+V_i(t)$ ranging from 225 (near $T$) to 317 (at $t=0$) under the uncorrected formula). The corrected convolution, given a $\mu_i(t)$ that already embeds the resolved share, uses $V_i(t)$ alone:

$$\Phi\!\left(\frac{\mu_i(t)+\Delta\mu_i}{\sqrt{V_i(t)}}\right)$$

with the boundary at $t=T$ ($V_i(T)=0$) handled by the same limit that already anchors $\Theta(T)=0$ (Appendix C.1) rather than by re-introducing $\sigma_i$ there. This is a strictly more consequential correction than Section 8.6's trickle-drift fix: it moves the live-horizon $\Theta(0)$ from the $+1.3$--$+1.7$ range reported in earlier drafts of this section to $+4.6$--$+5.9$ (Table 11), because the uncorrected formula suppressed *all* win probabilities toward 0.5 at every period before $T$, muting precisely the late-campaign certainty that "wait, then deploy once things resolve" depends on. Section 8.6 reports both corrections together, in the order they were found.

## From a Calibrated $P$ to $\Theta$: Standard Machinery, One Necessary Adaptation

Once Sections 4.2--4.5 specify $P$, computing $V_t(\mathbf X_t,F_t)$ and therefore $\Theta(t)$ is standard: simulate forward paths of $\mathbf X_t$ under $P$; at each step, regress simulated continuation values on a basis of current-state features (Longstaff and Schwartz 2001); proceed by backward induction from $T$. We state this explicitly so it is not mistaken for this paper's contribution -- the contribution is Sections 4.2--4.5; this section is what those sections are *for*.

**The one adaptation this domain requires: compress the regression basis.** The state vector carries per-race features for $N>400$ races. Regressing simulated continuation values on a per-race feature basis is not merely slow -- at the sample sizes involved ($K\sim10^4$ paths, $\sim15$ time steps, giving $\sim10^5$ observations against a feature matrix with hundreds of columns) it is a data-analytic mistake that would overfit badly and say more about simulation noise than about $\Theta$. The regression basis must instead be a small set of portfolio-level aggregate features, the same design used in basket-option pricing when the same dimensionality problem arises from pricing an option on many underlyings at once:

1. $\mathbb E[\text{Seats}]_t=\sum_i\Phi(\mu_{i,t}/\sigma_{i,t})$ -- the portfolio's current level.
2. $\text{Var}[\text{Seats}]_t=\mathbf 1'\Sigma_t\mathbf 1$ -- the portfolio's current risk (Paper I's covariance model).
3. $\max_i\text{MSG}_{i,t}$ -- the value of the single best marginal dollar available right now.
4. A near-threshold count -- the number of races within a small margin of the majority-determining threshold, a direct proxy for how much of the portfolio's outcome is still genuinely undecided.
5. $G_t$ -- the current national-environment level, entered directly as a fifth feature (never fed into $\mu_i$'s structural formula, per Section 4.3's scope boundary below).

## A Scope Boundary That Must Be Stated Before Estimating Anything

The existing point-in-time state-reconstruction machinery this paper's estimation and validation work reuses documents a constraint this paper must respect: $\alpha_3$, Paper I's margin-model generic-ballot coefficient, was estimated entirely from *between-cycle* variation -- one $GB$ value per historical cycle, identical across every race in that cycle. Its identifying variation has never been within-cycle. Wiring the calibrated $\Delta G$ shock into $\mu_i$ for a within-cycle simulation step would apply $\alpha_3$ to an estimand it was never fit against. **This paper does not make that substitution.** The assembled simulator computes $\Delta G$ (Section 4.3) and $\eta$-driven $R_{i,t}$ movement (Section 4.2), but validates each against real held-out data on its own terms (Section 8.1), and enters $G_t$ into the Longstaff--Schwartz regression basis as an independent feature (item 5 above) rather than folding it into $\mu_i$ under a model specification never estimated to support it. Re-estimating the margin model on a panel with within-cycle $GB$ observations is a prerequisite to that stronger integration, and is left for future work (Section 10.2).

\newpage

# Data

## Data Sources

Beyond every source Papers I and II already use, this paper requires three additional, specifically dated panels. **Dated independent-expenditure filings**, resolved to specific filing dates rather than cycle-cumulative totals (FEC Schedule E, via the comprehensive bulk export), pooled across all seven cycles this repository has usable data for (2012--2024), used to estimate opponent reaction (Section 6.1). **A historical, dated, multi-cycle generic-ballot series** (2018, 2020, 2022, 2024), recovered via a Wayback Machine snapshot of FiveThirtyEight's discontinued live generic-ballot data feed, since no other multi-cycle dated source was available in this repository -- the standard `generic_ballot_by_cycle.csv` carries exactly one static value per cycle, no dates at all, and RealClearPolitics's bulk archive was found to be blocked by bot protection when checked directly. **A dated candidate-committee financial panel** (FEC API `/committee/{id}/reports/` endpoint, per-filing-period Form 3 reports), used to calibrate the candidate-spending trickle rate the deploy-branch convolution correction (Section 4.5) requires; this endpoint returns genuinely dated, per-period filings, unlike the bulk `weball` files this project's other candidate-spending measures use, which report only a single cycle-cumulative total.

## Coverage

Opponent-reaction estimation pools all seven cycles with usable dated IE data (2012--2024, $n=57{,}763$ delta-panel rows in the full extension). The national-environment term structure pools four historical cycles (2018, 2020, 2022, 2024) plus the live 2026 series. The candidate-spending trickle rate is calibrated on the same seven-cycle panel as opponent reaction. Simulator validation (Section 8.1) uses the 2022 and 2024 cycles as held-out targets. The main Longstaff--Schwartz solve (Section 8.3) is run against the live, in-progress 2026 state at a 98-day horizon, and against a 364-day counterfactual horizon holding all other state fixed (Section 8.5).

## Feature Engineering

The opponent-reaction panel is constructed at biweekly reporting periods (matching Paper II's reporting cadence) from January through early November of each cycle, with race fixed effects applied via within-(cycle, district) demeaning rather than a dummy-column matrix, since pooling roughly 800 district-cycle observations across many biweekly periods makes an explicit dummy matrix computationally wasteful for no estimation benefit. The national-environment term structure is computed directly from the recovered daily series at fixed horizons (30 through 450 days) without imposing a parametric form first.

## Cleaning

Two real, checked data-quality issues bear directly on the opponent-reaction estimate and are documented rather than silently absorbed. First, district attribution (`can_office_dis`) is blank in only 0.1--0.3% of House-general independent-expenditure rows in every cycle from 2012 through 2024 -- a specific a priori concern about pre-2018 data that does not hold in this data. Second, and more consequentially, blank expenditure dates (`exp_date`, needed for the date-bucketed reconstruction specifically) are *worse* in the recent cycles this paper's headline estimates rely on most (33.3% in 2022, 28.4% in 2024) than in older cycles (0.0% in 2012), and 2022's raw file separately contains a parsing-artifact corrupted row and a broader issue of duplicated transaction identifiers (26% of all 2022 IE rows share a duplicated `tran_id`). Both were confirmed not to contaminate any figure already reported in Papers I--II, which consume cycle-cumulative rather than date-bucketed totals, but a `tran_id`-deduplication and implausible-amount filtering step is a documented prerequisite specifically for this paper's transaction-level reconstruction.

## Final Dataset

**Table 4: State-Transition Estimation Dataset Summary**

| Quantity | Value |
|---|---|
| Opponent-reaction panel, cycles | 2012--2024 (7 cycles) |
| Opponent-reaction panel, observations | 57,763 (delta-panel rows, full 7-cycle extension) |
| National-environment series, cycles | 2018, 2020, 2022, 2024 (historical) + live 2026 |
| National-environment series, daily rows per cycle | 1,142--1,174 |
| Candidate-spending trickle panel, cycles | 2012--2024 (7 cycles, same extension as opponent reaction) |
| Simulator validation held-out cycles | 2022, 2024 |
| Monte Carlo paths per scenario ($K$) | 2,000 |
| Reporting periods (live horizon) | 7 (biweekly, 98 days to Election Day) |

\newpage

# Parameter Estimation \& Calibration

## Opponent Reaction $\hat\eta(\text{tier})$

The primary, cycle-weighted estimate pools all seven usable cycles via a random-effects (DerSimonian--Laird) meta-analytic combination, which gives each *election* a vote scaled by its own precision, rather than letting whichever cycle happened to generate the most transaction rows dominate a naive transaction-weighted pool.

**Table 5: Opponent-Reaction Estimates by Tier**

| Tier | 2-cycle pool (2022+2024) | 7-cycle naive pool | 7-cycle cycle-weighted (DL) | $I^2$ |
|---|---|---|---|---|
| Toss-Up | 0.475 | 0.422 | **0.277** | 73% |
| Lean D | 0.259 | 0.637 | **0.277** | 75% |
| Lean R | 0.304 | 0.572 | **0.304** | 0% |
| Likely R | 0.405 | 0.562 | **0.363** | 85% |
| Likely D | $-0.165$ | 0.180 | **0.043** | 46% |
| Safe D | 0.648 | 0.371 | **0.380** | 70% |
| Safe R | $-0.144$ | 0.584 | **0.258** | 89% |

$I^2$ -- the share of cross-cycle spread that is real variation rather than sampling noise -- is 70--89% for five of seven tiers, confirming a finding Section 8.1's validation makes precise: most tiers, including Toss-Up and Lean D, show statistically significant cycle-to-cycle variation once tested with adequate power, not a single stable structural constant. **Precision (a small standard error within a given pool) is not the same claim as temporal stability (the same true value across cycles), and most tiers fail the stability test.** The cycle-weighted (DL) column is the best available point estimate -- it does not let a transaction-heavy cycle dominate, and it uses all seven cycles rather than an arbitrary two-of-seven subset -- and gives $\hat\eta\approx0.26$--$0.38$ in genuinely contested tiers (Toss-Up, Lean D, Lean R, Likely R), well short of a naive dollar-for-dollar prior ($\eta\approx1$). Estimates for the Safe tiers and Likely D are retained for completeness but are identified from sparse, lumpy transaction activity (well under 20% of periods show any IE spending at all in these tiers) and should be read with substantially more caution.

![Opponent-reaction estimates by Cook tier, with cross-cycle uncertainty.](figures/eta_reaction_by_tier_fig.png){width=85%}

## The National Environment Process $\sigma_G(\Delta t)$

**Table 6: Generic-Ballot Realized Volatility Term Structure**

| Horizon (days) | Pooled std($\Delta G$), 5 cycles | std/$\sqrt{\text{days}}$, all 5 | std/$\sqrt{\text{days}}$, 4 historical only |
|---|---|---|---|
| 30 | 1.09 | 0.199 | 0.186 |
| 60 | 1.54 | 0.199 | 0.186 |
| 90 | 1.89 | 0.199 | 0.183 |
| 180 | 2.70 | 0.201 | 0.186 |
| 270 | 3.29 | 0.200 | 0.178 |
| 365 | 3.81 | 0.199 | 0.160 |
| 450 | 4.17 | 0.197 | 0.128 |

Pooled across genuinely independent cycles, std/$\sqrt{\text{days}}$ is remarkably stable from 30 through 270 days (0.183--0.201) rather than steadily declining, indicating an apparent mean-reversion signal visible in any single-cycle series is a small-sample artifact rather than a real feature of the process; a visible decline only emerges past roughly 365 days, consistent with Section 4.3's prediction that a random walk is a good approximation over the three-to-nine-month range that matters for $\Theta$ near Election Day, with the random-walk/mean-reversion distinction only mattering at horizons beyond about a year. The working calibration is $\sigma_G(\Delta t)\approx0.18$--$0.20\times\sqrt{\Delta t\text{ (days)}}$ (historical-cycles-only preferred for methodological cleanliness), giving $\sigma_G\approx2.0$ points at the roughly 120-day horizon relevant to the live application. Fitting $\text{Var}(\Delta G)(t)=A(1-e^{-t/\tau})$ to this term structure gives $\hat\lambda=1/\hat\tau=0.00536\,\text{day}^{-1}$ ($\hat\tau=186.5$ days), the decay rate Section 4.4's idiosyncratic-uncertainty proxy uses directly.

![Generic-ballot realized-volatility term structure, pooled across five cycles.](figures/gb_volatility_term_structure_fig.png){width=85%}

## Idiosyncratic Uncertainty Decay

With $\lambda=0.00536\,\text{day}^{-1}$ fixed from Section 6.2, race-level uncertainty resolution follows $\sigma_{i,t}=\sigma_i^{\text{static}}\sqrt{1-e^{-\lambda(T-t)}}$ directly, with no additional free parameters. Figure 3 shows the resulting decay schedule.

![Idiosyncratic uncertainty decay schedule, borrowed rate from the national-environment process.](figures/epsilon_uncertainty_decay_fig.png){width=75%}

## Candidate-Spending Trickle Rate

A per-tier candidate-committee spending trickle rate -- the deterministic drift the deploy-branch convolution correction (Section 4.5) requires -- is calibrated from the seven-cycle dated candidate-financial panel (Section 5.1) using the mean daily disbursement rate within each tier, not the median: the median is exactly \$0.00/day in every tier, an artifact of comparing FEC's quarterly filing cadence against this project's biweekly reporting grid rather than evidence of no real growth. Extending this calibration from the original two-cycle (2022, 2024) panel to the full seven-cycle panel reduced every tier's fitted rate by 16--43% (e.g., Toss-Up: \$12,725/day $\to$ \$7,193/day) -- the same pattern already documented for $\hat\eta$ in Section 6.1 -- and is the calibration used in every result reported in Section 8.

## Calibration Summary

**Table 7: State-Transition Parameter Calibration Summary**

| Parameter | Value | Method |
|---|---|---|
| $\hat\eta$(Toss-Up) | 0.277 | 7-cycle DerSimonian--Laird |
| $\hat\eta$(Lean D) | 0.277 | 7-cycle DerSimonian--Laird |
| $\hat\eta$(Lean R) | 0.304 | 7-cycle DerSimonian--Laird |
| $\hat\eta$(Likely R) | 0.363 | 7-cycle DerSimonian--Laird |
| $\sigma_G(\Delta t)$ | $0.18$--$0.20\times\sqrt{\Delta t}$ | Pooled realized volatility, 5 cycles |
| $\lambda$ (decay rate) | $0.00536\,\text{day}^{-1}$ ($\tau=186.5$ days) | Fit to $\sigma_G$ term structure |
| Candidate trickle rate | tier-specific, e.g. Toss-Up \$7,193/day | 7-cycle mean daily rate |
| $K$ (Monte Carlo paths) | 2,000 | -- |
| Regression basis dimension | 5 features | Section 4.6 |

\newpage

# Optimization Algorithm

## Optimization Strategy

The backward induction is Longstaff--Schwartz regression-based Monte Carlo: simulate $K$ forward paths of $\mathbf X_t$ under the specified $P$; at each step moving backward from $T$, regress simulated continuation values on the five-feature basis of Section 4.6; compare the regression-estimated continuation ("wait") value against the deploy branch's closed-form convolution value (Section 4.5); the chosen action at each simulated state is whichever value is larger.

## Algorithm

**Algorithm 1: Regression-Based Monte Carlo for $\Theta$**

\footnotesize
```
Input:  P (calibrated: eta(tier), sigma_G(dt), lambda, trickle rate),
        live state X_0, K simulated paths, N periods to Election Day
Output: Theta(t) for t = 0,...,N; frac_deploy_now at each period

1.  Simulate K forward paths of X_t under P:
      - D_i,t: control (fixed at 0 further discretionary spend on
        the wait branch) + deterministic candidate trickle drift
      - G_t: standalone zero-drift random walk at sigma_G(dt)
        [never fed into mu_i; Section 4.7's scope boundary]
      - R_i,t: eta(tier) * delta(D_i,t) + residual noise from the
        fitted regression residuals
      - epsilon_i,t: independent increments matched to the
        cumulative decay schedule V_i(t) (Section 4.4)
2.  For t = N (Election Day) down to 0:
      a. Deploy branch: V_deploy(X_t) = closed-form convolution
           (Section 4.5), corrected for trickle drift asymmetry
      b. Wait branch: regress simulated V_{t+1} on the 5-feature
           basis (Section 4.6); V_wait(X_t) = fitted continuation value
      c. Theta(t) = V_wait(X_t) - V_deploy(X_t)
      d. Optimal action: deploy if V_deploy > V_wait, else wait
3.  Report Theta(t), frac_deploy_now (share of the K paths choosing
      "deploy" at each t), and basis R^2 as a diagnostic
```
\normalsize

## Computational Complexity

Each period requires $O(K\cdot N_{\text{races}})$ work to simulate one step forward and $O(K)$ work for the basis regression (five features, independent of the race universe size by construction -- the entire point of Section 4.6's compression). With $K=2{,}000$ paths and 7 reporting periods, a full binary-framing solve completes in minutes on commodity hardware; the continuous deployment-fraction generalization (Section 8.5) multiplies this by the number of grid points (5 or 11), still completing well within an hour.

## Computational Environment

Implemented in Python, reusing Paper I's estimation and optimizer code directly for the deploy branch's within-period allocation (`optimizer.allocator.optimize()`, the fast LP path, used for Monte Carlo tractability -- $K\times N\times(\text{scenarios})$ calls would take days against Paper I's full nonlinear solver). `scripts/solve_bellman_lsm.py` implements the binary hold-or-deploy framing; `scripts/solve_bellman_lsm_continuous_phi.py` implements the continuous deployment-fraction generalization; `scripts/estimate_eta_reaction.py`, `scripts/estimate_gb_volatility.py`, and `scripts/estimate_candidate_spend_trickle.py` implement the three calibration stages of Section 6. As in Papers I--II, a fixed random seed ensures exact reproducibility of every Monte Carlo result reported below.

\newpage

# Empirical Results

## Internal Validation

**Simulator self-consistency (the gate before any result is trusted).** A multi-period simulator built from independently-calibrated components is not automatically trustworthy just because each component was validated on its own; per-step implementation errors can compound silently across many steps. Four checks were run at 5,000 simulated paths per cycle (2022, 2024) before any $\Theta$ figure was computed from the assembled simulator:

**Table 8: Simulator Self-Consistency Checks**

| Check | 2022 | 2024 | Verdict |
|---|---|---|---|
| A: simulated $\sigma_G(\Delta t)$ vs. target, at 28/56/112 days | ratios 1.001/1.002/0.998 | ratios 0.996/0.993/0.990 | Matches |
| B: $\hat\eta$ recovered from simulated paths vs. input | 0.344 vs. input 0.321 (rel. error 7.2%) | 0.159 vs. input 0.175 (rel. error 9.3%) | Matches -- no sign/scale bug |
| C: cumulative $\varepsilon$ variance vs. target (mean/max rel. error) | 1.5%/3.7% | 1.3%/4.2% | Matches (Monte Carlo noise at $K$=5,000) |
| D: simulated margin spread / target remaining uncertainty | 0.98--1.02 | 0.98--1.02 | Matches |

All four pass. This confirms the simulator faithfully implements what Sections 4.2--4.4 calibrated; it does not re-validate the calibration itself, which the next check addresses.

**Validation A: does a September information set correctly rank-order eventual outcomes?** Race state was reconstructed at a real September 1 snapshot for 2022 and 2024, $\mu_{i,\text{Sept}}$ computed via Paper I's unmodified pipeline, and Spearman-correlated against realized November margin, restricted to the competitive set:

**Table 9: Validation A -- September-to-November Rank Correlation**

| Cycle | $n$ | $\rho$ | $p$ |
|---|---|---|---|
| 2022 | 61 | **0.467** | $<0.001$ |
| 2024 | 53 | **0.650** | $<0.001$ |

Both positive and significant: a September information set correctly rank-orders competitive races' eventual outcomes two-plus months out, clearing the bar for the underlying valuation chain any simulated path is built from to be worth simulating at all.

**Validation B: does $\sigma_G(\Delta t)$ match what actually happened?** Comparing the calibrated term structure against realized $|\Delta G|$ over the real September 1 $\to$ Election Day window:

**Table 10: Validation B -- Realized vs. Predicted National-Environment Movement**

| Cycle | $\Delta t$ (days) | Realized $\Delta G$ | Predicted SD | $z$ | Within 2 SD? |
|---|---|---|---|---|---|
| 2018 | 66 | $-0.16$ | 1.49 | $-0.11$ | Yes |
| 2020 | 63 | $-0.08$ | 1.46 | $-0.05$ | Yes |
| 2022 | 68 | $-2.18$ | 1.52 | $-1.44$ | Yes |
| 2024 | 65 | $-1.95$ | 1.48 | $-1.31$ | Yes |

All four realized moves are within 2 standard deviations of the calibration, and all four moved in the same direction (toward Republicans) in the final two months -- suggestive of a real, if variable-strength, late-cycle tendency, but not a reliable, tradeable signal at $n=4$ (mean $z=-0.73$ across all four cycles). $G_t$ is not fed into $\mu_i$'s structural formula regardless (Section 4.7), so this remains an observation about a channel the model does not structurally use, not a calibrated input; Section 10.2 returns to it as a limitation rather than a finding.

![Realized generic-ballot movement, September to Election Day, against the calibrated term structure.](figures/gb_asymmetry_check_fig.png){width=80%}

## A Necessary Condition: Does the Optimal Policy Actually Depend on Information?

Before asking whether *preserving* the ability to reallocate has positive value, a logically prior question must be settled: does new information even change what an optimal allocator wants to do? Re-solving Paper I's optimizer against real historical state snapshots at a 60-day-out and a 14-day-out point in the 2022 and 2024 cycles, holding the total party budget fixed and identical so that only the information available differs, shows roughly one-third to one-half of the top twenty targeted races changing between the two snapshots (Jaccard overlap 0.54 and 0.67 respectively) -- real, substantial turnover. Even before considering the value of sequential decision-making, the allocation policy is demonstrably state-dependent: adaptive reallocation is a meaningful decision problem in this domain, not a theoretical abstraction being modeled for its own sake. This does not, on its own, imply that *waiting* has positive value (Section 8.3 answers that question directly, and the two findings are not in tension, as Section 9.2 discusses).

## Main Result: $\Theta(0)$ at the Live 2026 Decision

Solved against the live 2026 state at a 98-day horizon, across three calibration scenarios -- two single-cycle opponent-reaction brackets (fit on 2022 and 2024 individually, bounding a range of historically plausible reaction strength) and one scenario drawing $(\hat\eta,\text{resid\_std})$ per simulated path from the full seven-cycle empirical distribution:

**Table 11: $\Theta(0)$ at the Live 98-Day Horizon**

| Scenario | $\Theta(0)$ (expected seats) | frac\_deploy\_now |
|---|---|---|
| `eta_fit_2022` | $+4.586$ | 0.0% |
| `eta_fit_2024` | $+5.918$ | 0.0% |
| `eta_bootstrap_all_cycles` | $+5.070$ | 0.0% |

$\Theta(0)$ is substantially positive in every scenario, and holding the deployable reserve is the unanimous recommendation. This is the result of a calculation that has now been through two rounds of correction: an earlier, incorrect version found the opposite sign (missing the candidate-spending trickle channel entirely), and the version immediately prior to this one found a positive but much smaller $\Theta(0)$ ($+1.3$ to $+1.7$) due to a variance-specification double-count in the deploy-branch convolution, corrected in Section 4.5 and reported in full in Section 8.6.

![The binary hold-vs-deploy decision at $t=0$: value of waiting against value of immediate deployment, across scenarios.](figures/theta_binary_decision_motivation_fig.png){width=80%}

## A Comparative-Static Horizon Extension (Not a Historical Counterfactual)

Holding today's actual state exactly fixed and re-running the identical backward induction with only the "days to Election Day" parameter changed from 98 to 364 tests whether the live-horizon result is sensitive to how far $t=0$ sits from Election Day. This is a comparative-static exercise, not a realistic historical counterfactual: it holds the current 98-day state's polling, spending, and generic-ballot levels fixed and varies only the remaining-horizon parameter, which no real point in the 2026 cycle actually satisfies simultaneously (a race 364 days from Election Day would not, in reality, already carry today's spend levels and polling position):

**Table 12: $\Theta(0)$ at the 364-Day Counterfactual Horizon**

| Scenario | $\Theta(0)$ (expected seats) | frac\_deploy\_now |
|---|---|---|
| `eta_fit_2022` | $+3.822$ | 0.0% |
| `eta_fit_2024` | $+4.467$ | 0.0% |
| `eta_bootstrap_all_cycles` | $+4.667$ | 0.1% |

Under the corrected convolution, $\Theta(0)$ is *smaller* at the longer horizon in every scenario -- the opposite direction from what an earlier draft of this section reported. That earlier claim ("hold is favored more, not less, the further out the decision is made") was itself an artifact of the same variance double-count Section 4.5 corrects: the uncorrected formula kept re-adding a full $\sigma_i^2$ at every period regardless of how much time remained, so a longer horizon mechanically accumulated more of that spurious inflation. Once the double-count is removed, a longer horizon still favors hold in absolute terms (0.0--0.1% deploy-now at $t=0$ in both cases) -- the qualitative conclusion is unchanged -- but the corrected mechanism is that most of the option value is concentrated in the *final* few months rather than growing without bound the further out one stands, consistent with $V_i(t)$'s own shape (Section 4.4): remaining idiosyncratic uncertainty is bounded by $\sigma_i^2$ regardless of how far out $t$ is, so extending the horizon past the point where most of that budget is already "in play" adds comparatively little. This is a genuine, reportable change in the mechanism's implication, not a reversal of the paper's headline recommendation.

## Testing the Binary Framing Directly: A Continuous Deployment Fraction

The binary hold-or-deploy framing might be too coarse to express a genuine small-but-nonzero optimal reserve. This is tested directly rather than argued about, generalizing the backward induction to a genuine impulse-control problem over a discrete budget grid ($\{0,0.25,0.5,0.75,1.0\}\times F_0$, later confirmed at an 11-point, 10%-step grid), with unspent capital carried forward as a state variable rather than a one-time choice.

**Table 13: Continuous Deployment-Fraction Generalization, 5-Point Grid**

| Scenario | $V$(hold) | $V$(deploy) | Gap (hold $-$ deploy) | Chosen fraction |
|---|---|---|---|---|
| `eta_fit_2022` | 236.514 | 233.610 | $+2.904$ seats | 100.0% hold |
| `eta_fit_2024` | 237.906 | 233.721 | $+4.185$ seats | 100.0% hold |
| `eta_bootstrap_all_cycles` | 236.454 | 233.310 | $+3.145$ seats | 67.9% hold, 22.5% at 25%, 1.2% at 50%, 8.6% at 75%, 0.0% full deploy |

![Continuous deployment-fraction generalization: value achieved at each grid point, by scenario.](figures/continuous_phi_result_fig.png){width=85%}

The corner holds cleanly in the two single-cycle brackets, now by a wider margin than before correction. `eta_bootstrap_all_cycles` no longer places any mass at all on full immediate deployment (0.0%, versus 18.2% under the uncorrected convolution) and instead spreads its non-hold mass across the interior fractions -- a genuinely different qualitative shape than the near-bimodal (0%/100%) pattern the uncorrected model produced, consistent with the corrected model no longer artificially compressing win probabilities toward 0.5 at intermediate budget levels. "Hold" still wins by a wide margin on average. An 11-point spot-check confirms the 5-point result under the corrected convolution for both single-cycle brackets: `eta_fit_2024` (the representative case shown in the figure above's panels A--B) gives gap $=+4.194$ seats versus $+4.185$ at 5 points ($0.009$-seat difference); `eta_fit_2022` (the bracket with the smallest 5-point gap of the three, i.e. closest to indifference) gives gap $=+2.912$ versus $+2.904$ ($0.008$-seat difference). Both are 100.0% hold at every grid point from 10\% through 90\%, confirming the corner is not a grid-resolution artifact in either case.

## The Correction That Produced This Result

Three corrections, found by checking mechanism rather than trusting output, separate the result reported above from two earlier, materially different findings.

**A missing channel.** An earlier version of the wait branch held candidate-committee spending $D_{i,t}$ fixed while waiting, because no per-filing-date source for candidate spending was believed to exist anywhere in this project's data -- itself later found to be incorrect (Section 5.1's dated candidate-financial panel, recoverable from an FEC API endpoint not previously checked directly). With $D_{i,t}$ fixed, opponent reaction $\hat\eta$ had nothing to react to on the wait branch at all, and the resulting $\Theta(0)$ was negative (deploy favored) in every scenario tested. Once candidate committees' real, dated spending growth is wired in as a genuine drift process, the wait branch legitimately captures value the deploy branch cannot: information about how each race's own fundamentals continue developing while the party committee waits.

**An asymmetric convolution, caught before trusting the first re-run.** The first re-run under the corrected wait branch produced $\Theta(0)$ figures of $+6.8$ to $+8.0$ expected seats -- an order of magnitude beyond anything else in this research line, which prompted checking the mechanism directly rather than reporting the number. The deploy branch's "integrate over future drift in one step" convolution (Section 4.5) is only valid when the future movement it integrates over is mean-zero; with a real, deterministic, non-zero-mean trickle now driving $D_{i,t}$, the deploy branch was silently missing the expected $\mu$ appreciation from the candidate's own future organic spending -- a gain the wait branch picked up automatically (it is fit against simulated future states that already reflect the grown $D$), while the deploy branch's analytical shortcut did not. Adding the trickle's expected drift to the deploy branch's convolution before evaluating it produced the $+1.3$-to-$+1.7$ figures an earlier draft of this section reported.

**A variance double-count, found in an external review of this section.** A reviewer questioned whether Section 4.4's remaining-idiosyncratic-uncertainty proxy $V_i(t)$ and Paper I's static $\sigma_i$ were being combined correctly, or whether $\sigma_i^2$ was implicitly counted twice. Tracing the implementation confirmed the concern precisely: the simulator's $\mu_i(t)$ already embeds the resolved-to-date share of the idiosyncratic budget via $\varepsilon_i^{\text{cum}}(t)$, so the deploy-branch convolution's $\sqrt{\sigma_i^2+V_i(t)}$ term was pricing the same uncertainty a second time (Section 4.5's addendum derives the mechanism and verifies the telescoping identity numerically). Correcting this -- using $\sqrt{V_i(t)}$ alone, since $\mu_i(t)$ already reflects what has resolved -- moved $\Theta(0)$ from the $+1.3$-to-$+1.7$ range to the $+4.6$-to-$+5.9$ range reported in Table 11, the largest single revision in this research line to date. The correction was verified three ways before being trusted: (1) a direct numerical check that $\text{Var}(\varepsilon_i^{\text{cum}}(t))+V_i(t)$ is exactly constant across $t$ (confirming the telescoping identity the fix depends on); (2) the pre-existing simulator self-consistency gate (Table 8) re-run and unchanged, since that gate validates the forward simulator's calibration rather than the deploy-branch convolution where the error lived; and (3) a purpose-built mechanism-decomposition check (Section 8.7) in which a "nothing evolves" benchmark scenario, which should trivially give $\Theta(0)=0$, in fact returned $\Theta(0)=0.000$ only after a related boundary-condition inconsistency in that decomposition's own implementation was also found and fixed -- itself an illustration of the same discipline applied recursively.

Corrections are reported in full, including their magnitude and direction, rather than silently folded into a single "final" number, because the discipline of checking a surprising result's mechanism before publishing it is itself part of this paper's contribution -- the same discipline that, in Paper I, caught a materially different implementation bug in the marginal-seat-gain gradient.

## Mechanism Decomposition: Isolating Information Value from Deterministic Sequencing

A reviewer raised a further, distinct concern: that $\Theta(0)$'s positive sign might reflect predictable candidate-spending growth (a deterministic sequencing/crowd-out effect) rather than genuine information-option value, since the sign flip documented above occurred specifically when the trickle channel was added. This is answered directly by re-solving $\Theta(0)$ five times, at the live 98-day horizon under the `eta_bootstrap_all_cycles` calibration, independently toggling each of the three stochastic-transition-law components off:

**Table 13b: Mechanism Decomposition of $\Theta(0)$**

| Scenario | Trickle | Stochastic shocks | Opponent reaction | $\Theta(0)$ |
|---|---|---|---|---|
| A: static benchmark | Off | Off | Off | $+0.000$ |
| B: deterministic sequencing alone | On | Off | On | $+3.479$ |
| C: pure information alone | Off | On | Off | $+1.461$ |
| D: information + growth | On | On | Off | $+5.800$ |
| E: full model | On | On | On | $+5.070$ |

Scenario A -- nothing evolves over the horizon at all -- gives exactly $\Theta(0)=0$, the sanity check the decomposition machinery must pass before the other four rows can be trusted. Scenarios B and C isolate each channel on its own: **deterministic sequencing value (B, $+3.479$) is larger than pure information value (C, $+1.461$)**, confirming the reviewer's suspicion directly rather than refuting it. Roughly 70% of the two channels' combined single-channel value ($3.479/(3.479+1.461)$) comes from candidate committees' predictable organic spending growth, not from resolving genuine uncertainty. Scenario D (both channels, no opponent reaction) exceeds the sum of B and C, indicating the two channels interact super-additively rather than simply adding; adding opponent reaction (E) then reduces $\Theta(0)$ from D's $+5.800$ to the full model's $+5.070$, since reaction dampens the wait branch's advantage by having $R_{i,t}$ partially offset the trickle it drives.

**The honest claim, and the one this decomposition does not license.** Per the reviewer's own proposed resolution: the defensible claim is that this model estimates a positive value of deferring party deployment under *both* predictable candidate-spending growth *and* resolving uncertainty, with the deterministic channel contributing the larger share in isolation. The stronger claim -- that $\Theta$ specifically prices information-driven flexibility -- is not supported by this decomposition; Scenario C shows genuine information value is real and positive ($+1.461$) but is not, on its own, the dominant driver of the headline result.

## Statistical Rigor: Simulation Noise and Out-of-Sample Policy Evaluation

The headline $\Theta(0)$ figures above are single-seed point estimates with no simulation-noise accounting, and the continuation-value regression is fit and evaluated on the same $K=2{,}000$ paths -- the standard in-sample look-ahead-bias risk in Longstaff--Schwartz applications. Both are addressed directly, on the `eta_bootstrap_all_cycles` calibration:

**Monte Carlo standard error.** Re-solving $\Theta(0)$ at $K=2{,}000$ across 5 independent seeds gives a mean of $+5.120$ with sample SD $0.091$ and standard error $0.041$ expected seats -- simulation noise is under 1\% of the point estimate, not a material source of uncertainty relative to the roughly 3--4$\times$ swings the two corrections above produced.

**Out-of-sample policy evaluation.** Refitting with 30\% of paths held out of every period's continuation-value regression (so a held-out path's own realized future value never informs the regression that decides its stopping choice) gives $\Theta(0)=+4.951$ on the held-out paths versus $+4.957$ in-sample -- a 0.1\% difference. The compressed, five-feature regression basis (Section 4.6) does not appear to be meaningfully overfitting at this sample size.

**$K$-sensitivity.** $\Theta(0)=+5.010$ at $K=2{,}000$ versus $+5.101$ at $K=5{,}000$ (single seed) -- consistent with the multi-seed SE above, and well within the range needed to trust the headline figures at the precision reported.

None of these checks change the qualitative or quantitative conclusion; they establish that, unlike the two corrections in Section 8.6, remaining Monte Carlo and regression-specification uncertainty is small relative to $\Theta(0)$'s magnitude.

\newpage

# Discussion

## Why the Corner Flipped

The mechanism is structural, not a recalibration accident. Once candidate-committee spending is allowed to grow deterministically while a committee waits, and opponent reaction is correctly credited with responding to that growth, the wait branch's simulated future states genuinely differ from -- and, on average, exceed -- what the deploy branch's convolution identity captures for a static $D_{i,t}$. The earlier, "deploy favored" result was not wrong because the option-value logic of Papers II--III is wrong; it was wrong because the model actually tested was missing a real channel through which waiting pays off. This is a direct illustration of Section 3.3's methodological claim: a Bellman equation over an incompletely specified $P$ does not merely give an imprecise answer, it can give the *wrong-signed* one. The subsequent variance-double-count correction (Sections 4.5, 8.6) is a second illustration of the same claim, one level down: even with the transition law's *components* correctly specified, an error in how two of their variance terms combine changed $\Theta(0)$'s *magnitude* by a factor of roughly 3--4, without changing its sign.

## What Remains Structurally Unpriced -- and What the Decomposition Shows Is Already Priced

Even the corrected model has a real, stated scope boundary. The convolution identity (Section 4.5) is exact for what it integrates over -- the expected effect of unresolved shocks on terminal win probability -- but it does not, and structurally cannot, capture the value of *adaptive* decision-making: that new information arriving mid-campaign could change *how* the reserve is allocated, not merely *whether* it is deployed. Deployment in this model is a one-time absorbing decision, computed once, at the moment of deployment. $\Theta(t)$ throughout this paper should therefore be read not as "the value of flexibility" in a fully general sense, but as **the value of flexibility net of what the deploy branch's own analytical widening already captures for free** -- a narrower and more accurate claim.

Section 8.7's mechanism decomposition sharpens this further in a different direction: even within the narrower object $\Theta$ actually measures, a majority of its magnitude in isolation (Scenario B versus Scenario C) is deterministic-sequencing value -- the predictable fact that candidate committees keep spending their own money while the party waits, which a myopic "deploy now and never revisit" benchmark does not credit itself with -- rather than information-option value in the classical real-options sense. This does not make $\Theta$ a less real or less useful quantity for the decision at hand; a committee choosing whether to hold or deploy today should care about the total value of waiting, whatever its source. But it does mean the paper's own framing needs a qualifier: $\Theta$ prices *the value of deferring commitment given both predictable organic growth and resolving uncertainty*, not information value on its own, and the two should not be conflated when this result is cited elsewhere.

## Reconciling with Paper II's Baseline

Paper II's own live run, using the $\Theta$-free rollout architecture, recommends deploying the full reserve immediately, concentrated disproportionately in non-competitive seats. This paper's corrected result recommends the opposite action at the same decision point. The two are not in conflict; they are exactly the comparison this research program is built to make. Paper II identifies and measures the size of a gap; this paper specifies the process that determines which side of that gap the live decision actually falls on, and finds -- once specified, estimated, and corrected -- that it falls on the side Paper II's architecture cannot see.

## A Domain-Intuition Check Against Real Data

A model recommendation this consequential should not be accepted on the strength of internal consistency alone. Real independent-expenditure committees spent only 1.6--4.4% of their eventual full-cycle total by September 1, in both the 2022 and 2024 cycles and both parties -- near-total real-world back-loading, and strong independent evidence that sophisticated political spenders behave nothing like an immediate-deployment strategy, for reasons this model may or may not fully capture (genuine information value, strategic waiting, targeting immaturity early in a cycle, or some mix). The corrected result reported in Section 8.3--8.5 is consistent with this pattern; the earlier, uncorrected result directly contradicted it. This is offered as corroborating evidence, not as a formal test the model was fit to pass.

## Generalizability

The specification-before-optimization discipline this paper insists on -- that an optimal-stopping problem is not well-posed until its underlying stochastic process is specified, and that specifying the process is the actual scientific content of the problem -- generalizes to any domain where a real-options framing is invoked without a calibrated transition law behind it. The three-component decomposition (a reactive/strategic process, an exogenous environmental process, and an idiosyncratic decay process) is likewise a template: any capital-commitment decision with a competitive response, a common macro factor, and unit-specific resolving uncertainty admits the same three-part specification, whether the underlying asset is a campaign, a venture investment, or a real physical option to expand capacity.

\newpage

# Limitations

## Data

Race-level idiosyncratic uncertainty ($\varepsilon_{i,t}$) is a bounded proxy, not a fitted process, for a data reason this paper judges likely permanent under a public-data-only constraint: district-level polling density is too sparse, for the large majority of House races, to support genuine time-series estimation. Opponent reaction is estimated from IE-to-IE reaction and then applied, in the deploy-branch drift correction, to a candidate-committee spending channel it was not originally estimated on -- an untested extension of an existing estimate, flagged explicitly rather than assumed to transfer. Five of seven opponent-reaction tiers show statistically significant cycle-to-cycle variation rather than a single stable constant, so the cycle-weighted point estimates in Table 5 should be read as averages over real historical variation, not as fixed structural parameters.

## Modeling

The random-walk versus mean-reversion choice for $G_t$ is empirically underdetermined at the three-to-nine-month horizon that matters most for this paper's live application; a longer-horizon application would need to resolve this distinction more carefully. The realized late-cycle generic-ballot asymmetry (Section 8.1's Validation B) is directionally consistent across four cycles but not reliable at $n=4$, and is not fed into $\mu_i$'s structural formula regardless, per the scope boundary of Section 4.7. The deploy-branch convolution identity, as discussed in Section 9.2, prices a narrower object than the full value of adaptive flexibility, by construction.

## Computational

The Longstaff--Schwartz regression basis is compressed to five portfolio-level features specifically to avoid overfitting at the sample sizes involved (Section 4.6); this is standard practice for this class of problem but is a genuine information loss relative to a (computationally infeasible) full per-race basis. Section 8.8 directly quantifies remaining Monte Carlo and regression-specification uncertainty: a 5-seed standard error of $0.041$ expected seats (under 1\% of the point estimate), a 0.1\% in-sample-vs.-held-out gap under a 30\%-held-out policy evaluation, and consistency between $K=2{,}000$ and $K=5{,}000$ -- none of these are a material source of uncertainty relative to the corrections reported in Section 8.6. Monte Carlo noise remains visible at the margins of the continuous-framing results (Table 13's `eta_bootstrap_all_cycles` scenario, where non-hold mass is now spread across several interior grid fractions rather than concentrated at one); an 11-point grid spot-check of the corrected continuous-$\phi$ result on both single-cycle brackets (`eta_fit_2022`, `eta_fit_2024`) confirms the 5-point figures directly (differences of $0.008$ and $0.009$ seats respectively, Section 8.5), though the `eta_bootstrap_all_cycles` scenario's own interior-mass distribution -- the one genuinely non-corner result in this research line -- has not itself been re-checked at 11 points and remains the more precision-sensitive of the three.

## Practical Deployment

The corrected model's central finding -- hold the reserve at the live 2026 decision -- is a recommendation about a single, specific decision point, re-derived from the current state each time the pipeline is re-run; it is not a standing policy, and Paper II's own architecture (Section 4.7 of that paper) already anticipates that a $\Theta$-aware recommendation must be recomputed as the state evolves, not applied once and left unrevisited. This paper's Longstaff--Schwartz solve has not itself been folded back into Paper II's rollout loop as a per-period, automatically-applied reserve fraction; doing so, closing the loop between the two papers' architectures fully, is a natural extension this paper does not complete.

\newpage

# Conclusion

Paper I answers what one more campaign dollar is worth today. Paper II asks how to make that decision repeatedly, and discovers it cannot yet answer whether to wait. This paper does not answer that question directly; it answers the prior question that determines whether it is even askable: how does the political state evolve on its own, absent any decision. $\Theta$, reserve policy, and optimal stopping are all corollaries of that answer, in exactly the sense that an option's value is a corollary of a specified stock-price process rather than an independently derived quantity. The scientific contribution of this research line is not "we solved a Bellman equation." It is "we estimated a defensible transition law $P$ for the political state" -- and, honestly, in one component (race-level idiosyncratic uncertainty), "we established that this cannot currently be estimated from public data, and said so plainly."

Having specified and estimated $P$, solved the resulting Bellman equation, and corrected three real errors found by checking mechanism before trusting output -- a missing spending-drift channel, an asymmetric convolution, and a variance double-count found in external review -- the result is unambiguous at the live 2026 decision: $\Theta(0)$ is substantially positive ($+4.6$ to $+5.9$ expected seats) in every calibration scenario tested, in both a binary and a continuous deployment-fraction framing, at both a 98-day horizon and a 364-day comparative-static extension, and holding the deployable reserve dominates deploying it. This reverses what an earlier, incomplete version of this same calculation found, and is the result consistent with, rather than contradicted by, real campaign committees' long-documented practice of holding back the substantial majority of their spending until the campaign's final months. A mechanism decomposition (Section 8.7) further qualifies what this result means: a majority of $\Theta$'s magnitude, isolated channel by channel, traces to predictable candidate-spending growth rather than to information-option value in the classical sense -- a real, quantified refinement of the paper's own claim, offered because the paper's central methodological argument (Section 3.3) demands the same scrutiny be turned on its own numbers that it insists the field turn on unspecified transition laws. Together, the three papers in this research program price the next dollar (Paper I), build the system that deploys it repeatedly (Paper II), and price the alternative of not yet deploying it (this paper) -- and, at the specific decision this program was built to inform, not deploying wins.

\newpage

# Data Availability

All data used in this paper are drawn from public sources: the sources already documented in Papers I and II, plus the FEC API's dated committee-reports endpoint (`/committee/{id}/reports/`), the FEC comprehensive independent-expenditure bulk export, and a Wayback Machine snapshot of FiveThirtyEight's discontinued generic-ballot data feed, whose provenance is documented in the project's data catalog.

# Code Availability

**Repository:** `https://github.com/callum-doty/political-portfolio`
**Entry points:** `scripts/estimate_eta_reaction.py`, `scripts/estimate_gb_volatility.py`, `scripts/estimate_candidate_spend_trickle.py` (calibration); `scripts/solve_bellman_lsm.py` (binary framing, including the mechanism-decomposition toggles and out-of-sample `held_out_frac` option used in Sections 8.7--8.8); `scripts/solve_bellman_lsm_continuous_phi.py` (continuous framing); `scripts/theta_mechanism_decomposition.py` (Section 8.7); `scripts/theta_statistical_rigor.py` (Section 8.8); `scripts/validate_state_simulator.py` (Section 8.1's validation suite); `scripts/simulate_and_validate.py` (Table 8's self-consistency checks); `tests/test_bellman_lsm.py` (automated regression tests covering the corrections of Section 8.6)

# Conflict of Interest

The authors declare no conflict of interest. This research was not funded by, and the authors hold no financial relationship with, any political campaign, party committee, or campaign consulting firm.

\newpage

# References

Andersen, T. G., and Bollerslev, T. (1998). Answering the skeptics: Yes, standard volatility models do provide accurate forecasts. *International Economic Review*, 39(4), 885--905.

Black, F., and Scholes, M. (1973). The pricing of options and corporate liabilities. *Journal of Political Economy*, 81(3), 637--654.

Dixit, A. K., and Pindyck, R. S. (1994). *Investment Under Uncertainty*. Princeton University Press.

Erikson, R. S., and Palfrey, T. R. (2000). Equilibrium in campaign spending games. *American Political Science Review*, 94(3), 595--609.

Gelman, A., and King, G. (1993). Why are American Presidential election campaign polls so variable when votes are so predictable? *British Journal of Political Science*, 23(4), 409--451.

Kalman, R. E. (1960). A new approach to linear filtering and prediction problems. *Journal of Basic Engineering*, 82(1), 35--45.

Longstaff, F. A., and Schwartz, E. S. (2001). Valuing American options by simulation: A simple least-squares approach. *The Review of Financial Studies*, 14(1), 113--147.

McDonald, R., and Siegel, D. (1986). The value of waiting to invest. *The Quarterly Journal of Economics*, 101(4), 707--727.

Merton, R. C. (1973). Theory of rational option pricing. *The Bell Journal of Economics and Management Science*, 4(1), 141--183.

Uhlenbeck, G. E., and Ornstein, L. S. (1930). On the theory of the Brownian motion. *Physical Review*, 36(5), 823--841.

Machine-readable BibTeX entries are provided as `references.bib` in the replication repository, combined with Paper I's and Paper II's reference lists.

\newpage

# Appendix A: Notation Reference Table

See Table 2 (Section 3.1) for symbols specific to this paper. Every symbol inherited from Paper I (the spending response surface, $\mu_i$, $\sigma_i$, $\text{MSG}_i$, $\Phi$, $\varphi$) and Paper II ($\mathbf X_t$'s originally-informal components, $B_t$, $L_t$, $F_t$, $\lambda$'s original EMA usage) retains its prior definition unless explicitly redefined here.

# Appendix B: Derivations

## B.1 The Gaussian Convolution Identity

For $Z\sim N(0,1)$ and constants $a,b$ with $b>0$: $\mathbb E_Z[\Phi(a+bZ)] = \Phi\big(a/\sqrt{1+b^2}\big)$, a standard identity following from writing $\Phi(a+bZ)=P(W\le a+bZ)$ for an independent $W\sim N(0,1)$, so that $\mathbb E_Z[\Phi(a+bZ)] = P(W-bZ\le a) = \Phi\big(a/\sqrt{1+b^2}\big)$ since $W-bZ\sim N(0,1+b^2)$. Applying this with $\mu_i(T)=\mu_i(t)+\xi$, $\xi\sim N(0,V_i(t))$, and $P(\text{win}_i)=\Phi(\mu_i(T)/\sigma_i)$: write $\mu_i(T)/\sigma_i = \mu_i(t)/\sigma_i + (\sqrt{V_i(t)}/\sigma_i)Z$ for $Z\sim N(0,1)$, giving $a=\mu_i(t)/\sigma_i$, $b=\sqrt{V_i(t)}/\sigma_i$, so that $\mathbb E_\xi[\Phi(\mu_i(T)/\sigma_i)] = \Phi\Big(\dfrac{\mu_i(t)/\sigma_i}{\sqrt{1+V_i(t)/\sigma_i^2}}\Big) = \Phi\Big(\dfrac{\mu_i(t)}{\sqrt{\sigma_i^2+V_i(t)}}\Big)$, matching Section 4.5's stated identity exactly.

## B.2 Incremental Decomposition of the Idiosyncratic-Uncertainty Schedule

Section 4.4 gives the *cumulative* remaining-uncertainty target, $V_i(t)=\sigma_i^2(1-e^{-\lambda(T-t)})$. For a period grid $n=0,\dots,N$ (period length $\Delta$, $N=$ Election Day), the per-step increment variance is $v_{i,n}=V_i(n)-V_i(n+1)$. Drawing $\varepsilon_{i,n+1}\sim N(0,v_{i,n})$ independently at each step reproduces the cumulative schedule exactly by telescoping: $\sum_{n=t}^{N-1}v_{i,n}=V_i(t)-V_i(N)=V_i(t)$, since $V_i(N)=0$ (matching $\Theta(T)=0$ at Election Day). This is an independent-increment process matched to a prescribed, shrinking variance schedule, not a Brownian bridge in the strict sense, since nothing conditions on a known terminal value.

## B.3 EMA/OU Term-Structure Fit

Fitting $\text{Var}(\Delta G)(t)=A(1-e^{-t/\tau})$ by nonlinear least squares to the empirical term structure of Table 6 gives $\hat\tau=186.5$ days, $\hat\lambda=1/\hat\tau=0.00536\,\text{day}^{-1}$, used identically in both Section 4.3's national-environment calibration and, by the borrowed-rate logic of Section 4.4, the idiosyncratic-uncertainty proxy -- a single fitted decay rate serving both purposes, not two independently-tuned parameters.

# Appendix C: Proofs

## C.1 $\Theta(T)=0$ (Boundary Condition)

At $t=T$ (Election Day), no further information can arrive before the outcome is realized, so $V_i(T)=0$ for every race (Appendix B.2's telescoping identity), and the deploy-branch convolution (Appendix B.1) reduces to $\Phi(\mu_i(T)/\sigma_i)$ exactly -- the same value the wait branch's continuation regression must converge to as well, since there is no $t=T+1$ to wait for. Hence $\Theta(T)=V_T^{\text{wait}}-V_T^{\text{deploy-now}}=0$ by construction, the boundary condition Section 3.5 states and every backward induction in Section 7 is anchored to.

# Appendix D: Additional Robustness Analyses

## D.1 Leave-One-Cycle-Out Stability Check

Refitting $\hat\eta$ separately on 2022 only and on 2024 only, rather than pooled, shows the three tiers Section 6.1 flags as most reliable on precision grounds (Toss-Up, Lean D, Lean R) keep the same sign in both single-cycle fits, but magnitudes are not stable (Toss-Up: 0.730 fit on 2022 alone vs. 0.341 fit on 2024 alone) -- consistent with the significant cycle-to-cycle variation the full seven-cycle joint test (Table 5's $I^2$ column) later confirms with adequate statistical power. Likely R's single-cycle estimate flips sign between the two fits ($-0.017$ vs. $+0.412$), and this tier's pooled estimate should not be trusted as a stable constant.

## D.2 Necessary-Condition Check Detail

Section 8.2's Jaccard-overlap check compares the top-twenty model-recommended races at a 60-day-out and a 14-day-out historical snapshot, using the true nonlinear optimizer (not the LP path used for Monte Carlo tractability elsewhere in this paper) and holding the total DCCC party budget fixed and identical at both snapshots so that only the information available differs. Overlap of 0.54 (2022) and 0.67 (2024) indicates roughly one-third to one-half of the top twenty races change between the two snapshots -- real, substantial turnover attributable to information arrival alone.

# Appendix E: Sensitivity Analyses

## E.1 LP-vs-Nonlinear Allocator Divergence in the Deploy Branch

The deploy branch's within-period allocation uses Paper I's fast LP solver (`optimize()`, milliseconds per call) rather than the full nonlinear solver (`optimize_nonlinear()`, roughly 19 seconds per call), a deliberate substitution for Monte Carlo tractability given $K\times N\times(\text{scenarios})\approx32{,}000$ total calls. Running both allocators on identical inputs confirms this is a real, understood specification difference, not an approximation error: the LP objective treats each race's marginal seat gain as a fixed constant with no diminishing-returns mechanism, so it degenerates into a greedy knapsack that funds only a handful of the lowest-floor races to the per-race cap and funds every other race, across every tier, at zero -- a materially different allocation pattern than the nonlinear solver's, for reasons having nothing to do with the value of waiting. This was checked directly (not assumed) before the deploy-branch comparisons in Section 8 were reported, since silently attributing an optimizer-specification difference to the $\Theta$ calibration would have been a genuine confound.

## E.2 Sensitivity of $\Theta(0)$ to the Codebase-Wide Corrections in Paper I

An independent audit of the shared codebase (Paper I's persuasion-ceiling fix and an earlier $\sigma_i$-model correction) was checked for its effect on this paper's headline live-horizon result, since the deploy branch's margin computation shares code with Paper I's estimation pipeline. The persuasion ceiling itself does not enter `margin_gradient()`'s computation directly; the only channel by which Paper I's corrections reach this paper's result is the LP-scaling fix to the deploy branch's within-period allocator, which was confirmed not to move Table 11's figures materially (live $\Theta(0)$: 1.328/1.719/1.619 expected seats, essentially unchanged from the pre-audit 7-cycle-trickle figures of 0.997/1.808/1.295 expected seats -- directionally consistent, with the differences attributable to the $\sigma_i$-model correction's uneven effect across scenarios' underlying win-probability curves, not to the ceiling itself). These are the pre-2026-07-28-audit figures; Section 8.6 documents a subsequent variance-specification correction that supersedes them.

# Appendix F: Hyperparameters

**Table F.1: Key Configuration Parameters**

| Parameter | Value | Section |
|---|---|---|
| $K$ (Monte Carlo paths) | 2,000 | 7.1 |
| Reporting cadence | 14 days (biweekly) | 5.3 |
| Live horizon | 98 days | 8.3 |
| Counterfactual horizon | 364 days | 8.4 |
| Regression basis dimension | 5 | 4.6 |
| Continuous-$\phi$ grid | 5-point $\{0,.25,.5,.75,1\}$, spot-checked at 11-point | 8.5 |
| $\lambda$ (decay rate) | 0.00536 day$^{-1}$ | 6.2 |
| Random seed (headline figures) | 20260716 | 7.4 |
| Multi-seed MC error check | 5 independent seeds, $K=2{,}000$ | 8.8 |
| $K$-sensitivity check | 2,000 vs. 5,000 | 8.8 |

# Appendix G: Pseudocode

See Algorithm 1 (Section 7.2) for the complete backward-induction procedure.

# Appendix H: Database Schema

**Table H.1: Key Processed Artifacts**

| File | Contents |
|---|---|
| `data/processed/eta_uncertainty.json` | Bootstrap and random-effects $\hat\eta$ distributions (Section 6.1) |
| `data/processed/gb_dynamics.json` | $\sigma_G$ per-$\sqrt{\text{day}}$, $\lambda$, $\tau$ (single source of truth, Section 6.2) |
| `outputs/theta_schedule.json` | Live-horizon $\Theta(t)$ by scenario and period (Table 11) |
| `outputs/theta_schedule_1yr_counterfactual.json` | 364-day counterfactual results (Table 12) |
| `outputs/theta_schedule_continuous_phi_*.json` | Continuous-framing results by scenario (Table 13) |
| `outputs/simulator_validation_summary.json` | Validations A--C (Tables 9--10) |
| `outputs/simulator_self_consistency.json` | Four-part self-consistency check (Table 8) |
| `outputs/eta_seven_cycle_extension.csv` | Per-cycle $\hat\eta$ fits, leave-one-out (Appendix D.1) |
| `outputs/eta_seven_cycle_joint_test.csv` | Cycle-variation joint significance tests ($I^2$, Table 5) |

# Appendix I: Additional Figures

Figures 1--6 (Sections 6.1, 6.2, 6.3, 8.3, 8.1, 8.5) constitute the complete set of figures generated for this paper; no additional figures beyond those already presented in the main text are included here.

# Appendix J: Additional Tables

**Table J.1: Leave-One-Cycle-Out $\hat\eta$ Fits**

| Tier | Fit on 2022 only | Fit on 2024 only |
|---|---|---|
| Toss-Up | 0.730 | 0.341 |
| Lean R | 0.387 | 0.183 |
| Lean D | 0.294 | 0.237 |
| Likely D | $-0.212$ | $-0.101$ |
| Likely R | $-0.017$ | 0.412 |
| Safe D | 1.070 | 0.318 |
| Safe R | $-0.003$ | $-0.165$ |

# Appendix K: Configuration Files

Relevant excerpt of `config.yaml`'s dynamic-allocation block (full file in the code repository, Code Availability):

```yaml
dynamic:
  ema_lambda: 0.7
  reporting_cadence: "biweekly"
  period_days: 14
  election_day_2026: "2026-11-03"

theta:
  k_paths: 2000
  live_horizon_days: 98
  counterfactual_horizon_days: 364
  regression_basis_features: 5
  continuous_phi_grid: [0.0, 0.25, 0.5, 0.75, 1.0]
```

# Appendix L: Reproducibility Checklist

- [x] All data sources are public and cited, or documented as requiring a free registered API key (Section 5.1)
- [x] Complete calibration and solver code is version-controlled and publicly available (Code Availability)
- [x] Random seeds are fixed for all Monte Carlo procedures (seed 42)
- [x] The simulator passes a four-part self-consistency check before any $\Theta$ figure is trusted (Section 8.1, Table 8)
- [x] The valuation chain underlying every simulated path is validated against real held-out outcomes (Section 8.1, Table 9)
- [x] Two real implementation errors are reported in full, including their direction and magnitude, not silently corrected (Section 8.6)
- [x] The binary hold-or-deploy framing is tested against a genuinely continuous generalization, not assumed adequate (Section 8.5)
- [x] Results are re-verified against the live codebase's independent corrections (Appendix E.2)
- [ ] Race-level idiosyncratic uncertainty remains a proxy, not a fitted process (Section 10.1; flagged as a likely-permanent data constraint)
- [ ] Opponent reaction is applied to a spending channel (candidate-committee trickle) outside the domain it was estimated on (IE-to-IE reaction) (Section 10.1; flagged as untested)
- [ ] The Longstaff--Schwartz solve is not yet folded back into Paper II's rollout loop as an automatically-applied, continuously-updated reserve policy (Section 10.4; flagged as future work)
