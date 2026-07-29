---
title: "A Self-Regulating Optimization Framework for Campaign Resource Allocation Under Uncertainty"
subtitle: "Marginal Seat Gain, Endogenous Persuasion Limits, and the Efficiency of Congressional Campaign Spending"
author: "[Author Name]"
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
  - \fancyhead[L]{\small\slshape A Self-Regulating Optimization Framework for Campaign Resource Allocation}
  - \fancyhead[R]{\small\thepage}
  - \renewcommand{\headrulewidth}{0.3pt}
  - \usepackage[format=plain,labelfont=bf,font=small]{caption}
---

\begin{abstract}
\noindent
Congressional campaign committees allocate hundreds of millions of dollars each election cycle largely through polling judgment, strategist intuition, and historical precedent rather than formal optimization. This paper reframes campaign finance as a constrained capital allocation problem and develops a complete pipeline for solving it: a spending response surface identified via a repeat-challenger causal design, a nonlinear margin-to-win-probability conversion, a portfolio risk model built on a common national-environment factor, and a nonlinear optimizer that maximizes expected seats subject to a fixed party budget. We show analytically that the resulting marginal-seat-gain function is finite everywhere -- including as a race's own spending floor $D_i\to0$, where a naive reading of the log-ratio specification's diverging gradient term might suggest otherwise, but where the conversion from margin to win probability decays fast enough to force the limit to zero rather than infinity. The function is instead non-monotonic, with a finite interior peak that can land at an implausible value if a race's real spending floor happens to sit nearby, a finite-sample extrapolation risk rather than a mathematical singularity. We derive this behavior, state the design requirements a correction must satisfy, and introduce an endogenous, bounded, differentiable \emph{persuasion ceiling} $C(\Phi_0) = C_{\max}\cdot 4\Phi_0(1-\Phi_0)$, where $\Phi_0$ is a race's win probability at its own candidate-only spending floor, calibrated by a seven-point robustness sweep. Using exclusively public data (FEC filings, MIT Election Lab results, Cook PVI, 2012--2024) and a Levitt (1994) repeat-challenger identification strategy extended to open seats via Bayesian shrinkage, we estimate the framework on 433 competitive-and-safe U.S. House races and develop a direct test of the framework's own KKT stationarity condition -- that risk-neutral efficient allocation equalizes marginal seat gain among funded races -- rather than relying on a spending-versus-marginal-return correlation that diminishing returns confounds mechanically. Applied to observed 2024 DCCC spending, marginal seat gain among interior-funded races shows a 90th-to-10th-percentile ratio of 25.9-to-1 (coefficient of variation 1.32), against near-exact equalization in the model-optimal allocation, replicating out-of-sample in 2022 (19.9-to-1; CV 1.25). A separate test finds no significant relationship between observed spending and each race's pre-allocation marginal potential in either cycle ($\rho=-0.122$, $p=0.38$, 2024; $\rho=-0.001$, $p=0.995$, 2022) -- the analysis finds no evidence DCCC systematically chose the wrong races at the outset. A model-optimal reallocation of the identical party budget yields an estimated $+2.83$ expected seats in 2024 and $+3.22$ in 2022; decomposing this gain shows 83--91\% is attributable to funding races that received zero party money at all, not to resizing amounts among races already funded. The paper's contribution is therefore threefold: a corrected derivation of marginal-seat-gain's limiting behavior together with an endogenous regularizer suited to the resulting finite-sample extrapolation risk; a KKT-based efficiency diagnostic and a selection-versus-intensity decomposition that together avoid the confound in a simpler correlation test; and a reproducible, publicly replicable empirical finding that DCCC's spending levels are inconsistent with equalized marginal returns, concentrated specifically in unengaged rather than mis-sized opportunities.
\end{abstract}

\vspace{0.5em}
\noindent\textbf{Keywords:} campaign finance, resource allocation, portfolio optimization, marginal treatment effects, election forecasting, constrained optimization, persuasion ceiling, capital budgeting

\newpage

# Introduction

## Motivation

U.S. congressional campaign committees allocate hundreds of millions of dollars every two-year election cycle. The Democratic Congressional Campaign Committee (DCCC) alone controlled roughly \$465 million in coordinated and independent party expenditures across House races in the 2024 cycle, a sum comparable to the market capitalization of a mid-sized public company, deployed across scores of simultaneous, correlated, binary-outcome contests. Despite this scale, allocation decisions remain largely heuristic: informed by polling averages, strategist judgment, historical precedent, and third-party race ratings, but rarely by an explicit model of the marginal return on the next dollar spent in a given district.

This is a striking gap relative to comparable capital-allocation domains. A portfolio manager deploying a nine-figure book of risky assets does so against an explicit model of expected return, volatility, and covariance. A firm allocating capital across competing internal projects uses net-present-value and hurdle-rate methods dating to the 1950s. Campaign finance, by contrast, has no analogous standard practice, even though the underlying decision problem -- allocate a fixed budget across many uncertain, correlated, binary-outcome opportunities to maximize an aggregate payoff -- is formally the same class of problem.

The absence of formal optimization is not for lack of data. Federal Election Commission (FEC) disbursement records, district-level election results, and partisan-lean indices are all public, machine-readable, and available for every cycle since at least 2012. What is missing is not data but a specific quantity: an estimate of the *marginal* seat gain produced by an *additional* dollar in a *specific* race, conditional on that race's current spending level and structural characteristics. Existing research does not estimate this quantity, for reasons developed in Section 2.

## Research Gap

Four adjacent literatures study pieces of this problem without solving it. Election forecasting (Cook Political Report ratings, FiveThirtyEight-style probabilistic models, Bayesian dynamic models such as Sides, Vavreck, and Warshaw 2022) estimates the *probability* of an outcome conditional on the current state of a race, but is not built to answer how that probability would change under a counterfactual spending decision. Campaign finance research (Jacobson 1978, 1990; Levitt 1994; Gerber 1998; Erikson and Palfrey 2000) estimates the *causal effect* of spending on vote share or margin, typically as a population-average treatment effect, but stops short of embedding that effect in a budget-constrained optimization across a portfolio of races. Polling research improves the precision of the state estimate that forecasting models consume, but is once again silent on the allocation question. Causal inference methodology (repeat-challenger designs, instrumental variables, randomized field experiments) supplies the identification strategies an allocation model needs to avoid confounding fundraising strength with electoral strength, but the methodology papers themselves do not extend to a constrained-optimization setting.

None of these literatures asks the question a sitting campaign committee actually faces: *given a fixed budget and a portfolio of competitive races, where should the next dollar go, and can we tell whether the committee's past decisions were efficient?* Answering it requires marginal, not average, treatment effects; it requires a portfolio-level objective that accounts for covariance across correlated races, not race-by-race point estimates; and it requires translating a continuous causal estimate into a constrained-optimization solution with well-defined comparative statics. This is a capital-allocation problem, not a forecasting or causal-inference problem, and it has not been formulated as one.

## Overview of the Proposed Framework

The framework developed in this paper has four moving parts, described here without derivation (Sections 3--4 supply the full formalism).

First, campaign spending affects the *expected vote margin* $\mu_i$ in race $i$, not the win/loss outcome directly. The effect is estimated as a function of the *ratio* of a candidate's spending to total two-party spending in the race, following the equilibrium logic of Erikson and Palfrey (2000): what matters is relative, not absolute, spending.

Second, the margin $\mu_i$ is converted into a win probability through $P_i = \Phi(\mu_i/\sigma_i)$, where $\sigma_i$ is the race's outcome uncertainty and $\Phi$ is the standard normal CDF. This conversion is what makes the problem genuinely nonlinear: the marginal value of a dollar depends on how close a race already is to the 50--50 tipping point, not merely on the size of the margin shift the dollar buys.

Third, because campaign committees care about the *number of seats won*, not any single race in isolation, and because election outcomes move together with the national political environment, the portfolio objective must account for cross-race covariance. A single common factor -- the generic congressional ballot -- links races through their sensitivity to national conditions, exactly as a market factor links otherwise-idiosyncratic stocks in a one-factor asset-pricing model.

Fourth, and this is the paper's central mathematical contribution, the spending-response specification that makes the first three pieces work has an unpriced defect: its gradient is unbounded as a race's own baseline spending approaches zero. Left uncorrected, a constrained optimizer will exploit this defect and recommend implausibly large sums in the safest, least-competitive districts in the data. We derive why this occurs, state what a correction must satisfy mathematically, and supply one: an endogenous, bounded "persuasion ceiling" that caps the achievable margin shift as a smooth function of how close to competitive a race already is.

The complete pipeline -- causal identification, margin and uncertainty estimation, portfolio covariance, the persuasion ceiling, and constrained nonlinear optimization -- is then applied to real FEC and election data to test whether the DCCC's observed 2022 and 2024 allocations are consistent with the efficiency the framework implies.

## Contributions

This paper makes five explicit contributions.

1. **Formulates campaign budgeting as a constrained, portfolio-theoretic capital allocation problem**, with an explicit objective (expected seats, optionally risk-adjusted), decision variables (per-race spending), and constraints (a fixed party budget and per-race caps), rather than treating campaign finance as a forecasting or average-treatment-effect estimation exercise.
2. **Derives the true limiting behavior of marginal seat gain** under the standard log-ratio spending specification as a race's own spending floor approaches zero: the function is finite (not divergent) in this limit, but non-monotonic, with a finite interior peak that can land at an implausible value if a race's real floor sits nearby -- a finite-sample extrapolation risk, not a mathematical singularity -- and introduces an endogenous, bounded, differentiable persuasion-ceiling function, $C(\Phi_0) = C_{\max}\cdot 4\Phi_0(1-\Phi_0)$, that corrects for it without requiring an exogenously imposed spending cap.
3. **Develops a fully reproducible calibration pipeline** using exclusively public data -- FEC bulk filings, MIT Election Data and Science Lab results, and Cook PVI -- with a Levitt (1994) repeat-challenger causal identification strategy, Bayesian shrinkage extrapolation to open seats, non-parametric bootstrap and permutation-based inference, and a seven-point sensitivity sweep for the ceiling's single free parameter.
4. **Introduces a direct test of the framework's own KKT stationarity condition** as an allocation-efficiency diagnostic -- testing whether marginal seat gain is equalized among interior-funded races, as risk-neutral optimality requires -- together with a decomposition that separates the model-implied gain from any reallocation into a "selection" component (funding currently-unfunded races) and an "intensity" component (resizing amounts among already-funded races), avoiding the mechanical diminishing-returns confound in a naive spending-versus-marginal-return correlation.
5. **Demonstrates, empirically and out-of-sample, that observed committee spending is inconsistent with equalized marginal returns among funded races** (a 90th-to-10th-percentile MSG ratio of 19.9--25.9-to-1 across two cycles, against near-exact equalization in the model-optimal allocation), while finding no evidence that initial targeting favored high- or low-potential races (a null pre-allocation correlation in both cycles); the resulting model-implied gain of 2.8--3.2 additional expected seats is shown to be dominated (83--91%) by funding previously unengaged races rather than by resizing existing commitments.

## Paper Roadmap

Section 2 situates the framework relative to the campaign finance, election forecasting, and operations research literatures and states precisely what no existing work combines. Section 3 formalizes the allocation problem: notation, decision variables, constraints, and objective. Section 4 develops the theoretical core -- the baseline probability model, the spending response function, the marginal-value-of-capital derivation, its limiting behavior, and the persuasion ceiling that regularizes the resulting extrapolation risk. Section 5 describes the public data sources and the final analysis dataset. Section 6 details parameter estimation and calibration, including the ceiling's sensitivity sweep and bootstrap inference. Section 7 specifies the optimization algorithm and computational environment. Section 8 reports empirical results: internal validation, a KKT-based primary efficiency test, a pre-allocation targeting test, a gain decomposition, out-of-sample replication, and, for transparency, the originally-proposed correlation test and why it was superseded. Section 9 discusses the political and strategic interpretation of the findings and the framework's generalizability beyond campaign finance. Section 10 states the framework's data, modeling, computational, and deployment limitations. Section 11 concludes.

\newpage

# Related Literature

## Campaign Finance

The campaign finance literature has principally sought to identify the causal effect of spending on vote share, treating spending as a single scalar treatment and outcome as a population-average response. Jacobson (1978, 1990) established that challenger spending exerts a substantially larger effect on vote share than incumbent spending, a finding that shaped both the academic and practitioner consensus that incumbents are comparatively insensitive to marginal spending -- a consensus Ansolabehere and Snyder (2002) probe directly, finding the raw incumbency advantage itself has grown over the postwar period in ways not fully explained by spending alone. Levitt (1994) addressed the central endogeneity concern in this literature -- campaigns spend more where races are competitive, so cross-sectional spending-outcome correlations confound resource allocation with underlying competitiveness -- using a repeat-challenger design that compares the same challenger against the same incumbent across consecutive cycles, differencing out time-invariant matchup characteristics. Gerber (1998) pursued a complementary identification strategy in Senate races using instrumental variables exploiting exogenous variation in seat competitiveness. Green and Gerber (2008) moved to randomized field experiments, estimating the effect of specific voter-contact activities (canvassing, direct mail) rather than aggregate spending, and providing a causal microfoundation for the sign and plausible magnitude of spending effects at the activity level. Erikson and Palfrey (2000) modeled campaign spending as a simultaneous strategic game between two candidates, establishing that the *ratio* of spending, not its absolute level, is the theoretically appropriate unit of analysis because the marginal value of a dollar to one side depends on the other side's spending. Ansolabehere, de Figueiredo, and Snyder (2003) step back from any single race to ask why aggregate political spending is, by the standards of the economic stakes involved, so small in the first place -- a question this paper's framework is silent on but which bears on why formal optimization of the spending that does occur has been comparatively neglected. Stratmann (2005) surveys this broader empirical literature and its identification challenges in detail.

These studies share a common estimand: $\mathbb E[Y(s+\Delta)] - \mathbb E[Y(s)]$ for a representative race, i.e., the *average* causal effect of a spending increment. None estimates the *conditional marginal* effect $\partial \mathbb E[Y]/\partial s_i$ at race $i$'s specific, current spending level -- the object a capital-allocation decision requires, and one that a fixed average-effect estimate cannot supply because it does not vary with a race's existing spending intensity or structural characteristics.

## Election Forecasting

A separate literature forecasts election outcomes conditional on the current information state. Cook Political Report and similar outlets translate district characteristics and qualitative judgment into ordinal race ratings (Safe, Likely, Lean, Toss-Up). Poll-aggregation forecasters, following the general approach popularized by FiveThirtyEight, combine polling averages with historical fundamentals into probabilistic win estimates, typically via ensemble or Bayesian dynamic linear models -- Montgomery, Hollenbach, and Ward (2012) formalize the ensemble-forecasting logic underlying this practice directly. Gelman and King (1993) established the methodological foundation this literature builds on, showing that presidential campaign polls are far more variable than final vote outcomes, and developing the fundamentals-plus-polls decomposition that motivates treating a race's expected margin as a structural quantity separate from its moment-to-moment polling noise -- the same distinction this paper's $\mu_i$/$\sigma_i$ separation (Section 4.1) formalizes for a spending-allocation rather than a forecasting purpose. Sides, Vavreck, and Warshaw (2022) demonstrate the viability of dynamic Bayesian forecasting for congressional and presidential races, producing calibrated, continuously updated win-probability estimates.

Forecasting models of this kind estimate $P(\text{win}_i \mid \text{information to date})$, a state-conditional probability. They are not built to answer a counterfactual spending question: how would $P(\text{win}_i)$ change under a specified change in future spending? Because forecasting models generally do not include a structural spending term with an estimated causal coefficient, they cannot be differentiated with respect to a spending decision, and therefore cannot directly supply a marginal seat gain estimate even though they estimate a closely related quantity (the level of $P_i$) with considerable sophistication.

## Operations Research

The mathematical structure of the allocation problem this paper poses is well studied outside political science, under three related headings. Mean-variance portfolio theory (Markowitz 1952) formalizes the allocation of a fixed budget across assets with uncertain, correlated returns, trading expected return against variance -- a template this paper adapts directly, with expected seats in place of expected return and a covariance matrix induced by a national-environment factor in place of asset covariance; Sharpe (1964) extends this template to an equilibrium asset-pricing model in which a single systematic factor prices every asset's required return, the same one-factor logic Section 4's national-environment covariance structure borrows. Dynamic programming and the Bellman equation (Bellman 1957) formalize sequential decision problems in which a state evolves and decisions must account for future consequences; while the present paper's allocation problem is solved as a single-period static optimization (Section 3), the multi-period extension in which a committee re-allocates continuously as new information arrives over a cycle is a direct application of this framework, developed in a companion paper. Classical resource-allocation and capital-budgeting problems -- the knapsack problem, the general resource-allocation problem of Ibaraki and Katoh (1988), and net-present-value capital budgeting -- formalize the discrete or continuous allocation of a scarce budget across competing projects with heterogeneous, often diminishing, returns, precisely the structure of the spending-response function developed in Section 4. The constrained optimization problem itself (Section 3.5) is a direct descendant of the linear- and nonlinear-programming machinery formalized by Dantzig (1963) and, for the convex risk-averse case, by Boyd and Vandenberghe (2004), whose interior-point and KKT-based methods underlie both the SLSQP solver of Section 7.1 and the proofs of Appendix C.

None of these operations-research frameworks, on its own, specifies where its inputs -- the expected-return function, the transition law, the project-level return curve -- come from in a political context. They supply the mathematical machinery; they do not supply the empirically calibrated inputs a real application requires, and none is built to confront the finite-sample extrapolation risk (Section 4.4) that arises specifically when such machinery is combined with a causally-anchored-but-partial (Section 6.3) political response surface.

## Research Gap

No existing work combines all three components required to solve the campaign-allocation problem: (i) a partially causally anchored, conditional-on-district spending response function, of the kind the campaign finance literature can supply piecewise but has not embedded in an allocation model; (ii) a nonlinear, uncertainty-aware conversion from expected margin to win probability, of the kind forecasting models estimate in isolation but do not differentiate with respect to spending; and (iii) a constrained, portfolio-level optimization layer that accounts for cross-race covariance and a fixed budget, of the kind operations research formalizes abstractly but does not calibrate to political data. This paper's contribution is to build and calibrate the object that sits at the intersection of these three literatures, and, in doing so, to expose and regularize against a finite-sample extrapolation risk -- a marginal-return function with a diverging component ($\partial\mu_i/\partial D_i$) that turns out, once composed with the margin-to-probability conversion, to be finite but non-monotonic, with a spuriously large finite peak -- that arises specifically from combining a partially causal log-ratio spending specification with an unconstrained optimizer, a problem invisible to any of the three literatures taken separately.

\newpage

# Problem Formulation

## Notation

Table 1 defines every symbol used in Sections 3--4. Race-level quantities carry subscript $i \in \{1,\dots,N\}$; where a time or cycle index is needed it is written $t$.

**Table 1: Notation Reference**

| Symbol | Meaning |
|---|---|
| $N$ | number of races in the analysis universe |
| $B$ | total party budget available for allocation |
| $x_i$ (also $s_i$, $p_i$ in code) | party dollars allocated to race $i$ (decision variable) |
| $D_i$ | total Democratic-aligned spending in race $i$ ($D_i = f_i + x_i$, candidate floor plus party allocation) |
| $R_i$ | total Republican-aligned spending in race $i$ |
| $T_i$ | $D_i + R_i$, total two-party spending in race $i$ |
| $f_i$ | race $i$'s candidate-committee spending floor (money already raised by the candidate, not reallocable) |
| $\text{ratio}_i$ | $D_i/T_i$, Democratic share of two-party spending |
| $\mu_i$ | expected Democratic vote margin (percentage points) in race $i$ |
| $\sigma_i$ | standard deviation of the margin distribution in race $i$ |
| $P_i$ | $P(\text{win}_i) = \Phi(\mu_i/\sigma_i)$ |
| $\Phi, \varphi$ | standard normal CDF and PDF |
| $\Phi_0^{(i)}$ | race $i$'s win probability evaluated at its own candidate-only floor ($x_i = 0$) |
| $\text{MSG}_i$ | marginal seat gain, $\partial P_i/\partial x_i$ |
| $\alpha_0,\dots,\alpha_5$ | control-surface coefficients of the margin model (PVI, incumbency, generic ballot, spending intensity, individual-contribution share) |
| $\beta_1 (=\beta_{RC})$ | base spending elasticity, identified via repeat-challenger design |
| $\beta_2, \beta_3$ | interaction coefficients (spending elasticity $\times$ \|PVI\|, spending elasticity $\times$ incumbency) |
| $\beta_1^{OS}$ | open-seat spending elasticity, Bayesian-shrinkage calibrated |
| $c_i$ | $\beta_1 + \beta_2|\text{PVI}_i| + \beta_3\,\text{Incumb}_i$, race-specific spending-elasticity coefficient |
| $G$ | national generic congressional ballot (D $-$ R), the common risk factor |
| $\beta_i$ (factor loading) | sensitivity of race $i$'s outcome to $G$ |
| $\sigma_G^2$ | variance of the national environment factor |
| $\Sigma$ | $N\times N$ factor-implied covariance matrix of race outcomes |
| $\gamma$ | risk-aversion coefficient (portfolio variance penalty) |
| $\lambda$ | shadow price of the budget constraint |
| $\kappa$ (cap fraction) | maximum share of the party budget any single race may receive |
| $C_{\max}$ | persuasion ceiling's single free calibration parameter |
| $C_i$ | race $i$'s ceiling on the achievable margin shift above $\mu_i(\Phi_0^{(i)})$ |
| $\tau$ | prior standard deviation in the open-seat Bayesian shrinkage estimator |
| $\eta$ | adversarial-response coefficient (opposing party's spending reaction to a marginal dollar) |

## Decision Variables

The decision variable is the vector $\mathbf x = (x_1,\dots,x_N)$, party dollars allocated to each race. Each $x_i$ is added on top of race $i$'s own candidate-committee spending floor $f_i$, which is treated as exogenous: it is money the candidate's own committee has already raised and the party committee cannot redirect. Total Democratic-aligned spending in race $i$ is therefore $D_i(x_i) = f_i + x_i$.

## Constraints

The allocation is subject to a fixed total party budget and per-race non-negativity and concentration constraints:

$$\sum_{i=1}^N x_i \le B, \qquad 0 \le x_i \le \kappa B \quad \forall i$$

The upper bound $\kappa B$ is a practical concentration cap (Section 6) preventing the optimizer from placing an implausible share of the entire budget in a single race; in the empirical implementation $\kappa \in \{0.05, 0.10, 0.15\}$ is swept as a sensitivity parameter rather than fixed a priori.

## Objective Function

The primary objective is expected seats won across the portfolio of races:

$$\mathbb E[\text{Seats}] = \sum_{i=1}^N P_i(x_i) = \sum_{i=1}^N \Phi\!\left(\frac{\mu_i(x_i)}{\sigma_i}\right)$$

Because electoral outcomes are not independent -- common national and regional conditions induce covariance across races -- the risk-adjusted objective incorporates portfolio variance. With $Y_i\in\{0,1\}$ the binary outcome of race $i$ and $\text{Seats}=\sum_iY_i$,

$$\text{Var}[\text{Seats}] = \text{Var}\Big(\sum_i Y_i\Big) = \sum_i\sum_j \text{Cov}(Y_i, Y_j) = \mathbf 1'\, \Sigma(\mathbf x) \,\mathbf 1$$

where $\Sigma(\mathbf x)_{ij}=\text{Cov}(Y_i,Y_j)$ is the $N\times N$ *outcome*-covariance matrix (not a spending-covariance matrix), and $\mathbf 1$ is the all-ones vector -- $\text{Var}[\text{Seats}]$ sums every entry of $\Sigma(\mathbf x)$, it does not weight them by dollar amounts. $\Sigma(\mathbf x)$ depends on the allocation $\mathbf x$ only through each race's outcome, via the structural factor loading derived in Appendix B.6, $\beta_i(x_i)=\varphi(\mu_i(x_i)/\sigma_i)\cdot\alpha_3/\sigma_i$: off-diagonal entries are $\Sigma_{ij}(\mathbf x)=\beta_i(x_i)\beta_j(x_j)\sigma_G^2$ for $i\ne j$, with idiosyncratic race-level variance on the diagonal. A campaign committee genuinely concerned with securing a chamber majority faces an objective closer to $P(\text{Seats}\ge T)$ for majority threshold $T=218$, which is approximately $\Phi\!\big((\mathbb E[\text{Seats}]-T)/\text{SD}[\text{Seats}]\big)$ under a normal approximation to the seat-count distribution. This majority-probability objective has different comparative statics than the expected-seats objective -- it rewards *increased* variance when $\mathbb E[\text{Seats}] < T$ and *reduced* variance when $\mathbb E[\text{Seats}] > T$ -- and a committee rationally pursuing it might overweight high-covariance races in a way that would appear as misallocation under the expected-seats objective alone. We adopt the expected-seats objective as the primary criterion, noting that the approximation is most accurate when $\mathbb E[\text{Seats}]$ is near $T$, and return to this distinction when interpreting the efficiency test in Section 8.

**Implementation note.** Every headline result in Section 8 uses the risk-neutral case $\gamma=0$, for which the discussion below is inert. For the risk-averse case ($\gamma>0$), computing $\mathbf 1'\Sigma(\mathbf x)\mathbf 1$ exactly inside a convex solve would require re-deriving $\Sigma$ at every candidate $\mathbf x$, which the current implementation does not do: it instead (i) uses the single-factor placeholder of Section 10.2 rather than the structural loading above, and (ii) evaluates that placeholder once at a fixed baseline allocation and holds it constant during the solve, penalizing $\mathbf d(\mathbf x)'\bar\Sigma\,\mathbf d(\mathbf x)$ -- a dollar-spending-weighted quadratic form in a frozen covariance matrix $\bar\Sigma$ -- as a computational proxy for $\text{Var}[\text{Seats}]$, not as an implementation of the formula above. This is a real gap between the stated objective and the risk-averse solver's implementation, distinct from the single-factor-placeholder gap already noted; because it affects only the $\gamma>0$ sensitivity grid and none of Section 8's reported results, it is flagged here and in Section 10.2 rather than resolved in this paper.

## Optimization Problem

The complete constrained optimization problem is:

$$
\begin{aligned}
\max_{\mathbf x} \quad & \sum_{i=1}^N \Phi\!\left(\frac{\mu_i(x_i)}{\sigma_i}\right) - \gamma\, \mathbf 1'\Sigma(\mathbf x)\,\mathbf 1 \\
\text{s.t.} \quad & \sum_{i=1}^N x_i \le B \\
& 0 \le x_i \le \kappa B \quad \forall i
\end{aligned}
$$

Section 4 derives $\mu_i(x_i)$ and $\sigma_i$ from the estimated spending response surface, Section 7 specifies the nonlinear solution algorithm (risk-neutral, $\gamma=0$, throughout Section 8), and Appendix C derives the Karush--Kuhn--Tucker (KKT) stationarity conditions characterizing an interior optimum.

\newpage

# Theoretical Framework

This section develops the paper's mathematical core: the baseline probability model that converts a vote-margin estimate into a win probability, the spending response function that produces that margin estimate, the marginal-value-of-capital expression obtained by differentiating the two together, a proof that this expression is unbounded as a race's own spending approaches zero, and the endogenous correction -- the persuasion ceiling -- that this pathology requires.

## Baseline Probability Model

Let $\text{Margin}_i \sim N(\mu_i, \sigma_i^2)$ denote the (approximately normal) distribution of the Democratic candidate's vote margin in race $i$, conditional on district characteristics and spending. The probability of a Democratic win is then

$$P_i \equiv P(\text{win}_i) = P(\text{Margin}_i > 0) = \Phi\!\left(\frac{\mu_i}{\sigma_i}\right)$$

Two features of this conversion matter for everything that follows. First, it is nonlinear in $\mu_i$: the same absolute improvement in expected margin produces a larger change in win probability near $\mu_i \approx 0$ (a competitive race) than far from it (a safe race), because the normal density is maximized at its mean. Second, $\sigma_i$ is not a nuisance parameter but an economically meaningful one: races with wider outcome uncertainty require larger margin shifts to produce the same probability change, exactly as higher volatility reduces an option's sensitivity (its delta) to the underlying at a given moneyness -- an analogy developed formally in Section 6.

## Spending Response Function

Following Erikson and Palfrey (2000)'s equilibrium logic that relative, not absolute, spending governs outcomes, the margin model is specified as a function of $\text{ratio}_i = D_i/T_i$, the Democratic share of total two-party spending in the race:

$$
\mu_i = \alpha_0 + \alpha_1\,\text{PVI}_i + \alpha_2\,\text{Incumb}_i + \alpha_3\, G + \underbrace{\big[\beta_1 + \beta_2|\text{PVI}_i| + \beta_3\,\text{Incumb}_i\big]}_{\displaystyle \equiv\, c_i}\,\log(\text{ratio}_i)
$$

The log transformation of the spending ratio is the source of the model's diminishing-returns property: because $\text{ratio}_i \in (0,1)$ is bounded, $\log(\text{ratio}_i) \to -\infty$ only as $\text{ratio}_i \to 0$, and each additional percentage point of spending share produces a smaller change in $\log(\text{ratio}_i)$ as the race's spending approaches parity. The elasticity coefficient $c_i = \beta_1 + \beta_2|\text{PVI}_i| + \beta_3\,\text{Incumb}_i$ lets responsiveness vary with district partisan lean and incumbency status. $\beta_1$ is the base elasticity, identified causally via the repeat-challenger design (Section 6.3); $\beta_2$ and $\beta_3$ are estimated on the full descriptive panel.

## Marginal Value of Capital

The quantity a capital-allocation decision requires is not the level of $P_i$ but its derivative with respect to the party's own spending, $\partial P_i/\partial x_i$ -- the marginal seat gain. Applying the chain rule through $\mu_i \to \text{ratio}_i \to D_i \to x_i$ (full derivation in Appendix B):

$$\frac{\partial\, \text{ratio}_i}{\partial D_i} = \frac{R_i}{T_i^2} \quad\Longrightarrow\quad \frac{\partial \log(\text{ratio}_i)}{\partial D_i} = \frac{T_i}{D_i}\cdot\frac{R_i}{T_i^2} = \frac{R_i}{D_i T_i}$$

so that, since $x_i$ enters only through $D_i = f_i + x_i$ (i.e. $\partial D_i/\partial x_i = 1$):

$$\boxed{\ \text{MSG}_i \;\equiv\; \frac{\partial P_i}{\partial x_i} \;=\; \varphi\!\left(\frac{\mu_i}{\sigma_i}\right)\cdot\frac{1}{\sigma_i}\cdot c_i \cdot \frac{R_i}{D_i T_i}\ }$$

This expression has an intuitive decomposition into two multiplicative factors. The first, $\varphi(\mu_i/\sigma_i)/\sigma_i$, is the density of the margin distribution evaluated at the tipping point -- the "conversion efficiency" of a margin shift into a probability shift, maximized for races near parity. The second, $c_i R_i/(D_i T_i)$, is the marginal effect of an additional dollar on the expected margin itself, and it is the interaction of both factors' behavior as $D_i \to 0$ that drives the limiting behavior characterized next.

## The Limiting Behavior of Marginal Seat Gain

Section 4.3 shows that $\partial\mu_i/\partial D_i = c_iR_i/(D_iT_i)$ diverges as $D_i\to0^+$. It is tempting to conclude that $\text{MSG}_i$, which multiplies this term by the conversion density $\varphi(\mu_i/\sigma_i)/\sigma_i$, diverges with it. It does not: the density term is evaluated at $\mu_i(D_i)$, and $\mu_i(D_i)$ is itself driven to $-\infty$ as $D_i\to0^+$ (since $\log(\text{ratio}_i)=\log(D_i/T_i)\to-\infty$), so the density is not bounded away from zero in this limit -- it vanishes, and it vanishes fast enough to matter.

**Proposition 1.** *Fix opponent spending $R_i>0$ and suppose $c_i>0$ (true of every fitted coefficient in Table 3: $c_i=\beta_1+\beta_2|\text{PVI}_i|+\beta_3\,\text{Incumb}_i\ge\beta_1=5.475>0$ for every race in the estimation universe, since $\beta_1,\beta_2,\beta_3>0$ and $|\text{PVI}_i|,\text{Incumb}_i\ge0$). In the regime $D_i\ll R_i$ relevant to a near-zero spending floor, $\mu_i(D_i)\approx B_i+c_i\log D_i$ for a constant $B_i$ collecting every term not involving $D_i$. Then:*

*(a) $\lim_{D_i\to0^+}\text{MSG}_i(D_i)=0$, not $+\infty$.*

*(b) $\text{MSG}_i$, viewed as a function of $x=\log D_i$, is unimodal: it vanishes in both limits $D_i\to0^+$ and $D_i\to\infty$, and attains a unique finite interior maximum at the spending level $D_i^*$ satisfying*

$$\mu_i(D_i^*) \;=\; -\frac{\sigma_i^2}{c_i}$$

*Proof.* Substitute $x=\log D_i$, so $\mu_i(D_i)\approx B_i+c_ix$. Using $R_i/(D_iT_i)\to1/D_i=e^{-x}$ as $D_i\ll R_i$ (Section 4.3), $\text{MSG}_i\propto\varphi\big((B_i+c_ix)/\sigma_i\big)\cdot e^{-x}$. Taking logs,

$$\log\text{MSG}_i(x) \;=\; \text{const} - x - \frac{(B_i+c_ix)^2}{2\sigma_i^2}$$

an exact downward-opening quadratic in $x$, since the coefficient on $x^2$ is $-c_i^2/(2\sigma_i^2)<0$. A downward parabola in $x$ tends to $-\infty$ as $x\to\pm\infty$; since $x\to-\infty$ as $D_i\to0^+$, this proves (a). Differentiating and setting the result to zero,

$$\frac{d}{dx}\log\text{MSG}_i(x) = -1-\frac{c_i(B_i+c_ix)}{\sigma_i^2}=0 \;\Longrightarrow\; B_i+c_ix^*=-\frac{\sigma_i^2}{c_i}$$

and since $\mu_i(D_i^*)=B_i+c_ix^*$ by definition, this is exactly $\mu_i(D_i^*)=-\sigma_i^2/c_i$; the negative second derivative $-c_i^2/\sigma_i^2<0$ confirms it is a maximum, proving (b). $\blacksquare$

**Corollary (a finite-sample extrapolation risk, not an asymptotic singularity).** Proposition 1 shows the log-ratio specification does not, in fact, imply an unbounded marginal incentive to defund a race toward zero -- the earlier working characterization of this as a mathematical singularity overstates what the model does in the true $D_i\to0$ limit. What it establishes instead is a narrower and more specific concern: $\text{MSG}_i$ is *non-monotonic* in spending, with a finite interior peak at $D_i^*$, and nothing in the specification guarantees that a race's actual observed floor $f_i$ falls safely away from its own $D_i^*$. Because $D_i^*$ depends only on estimated parameters ($\sigma_i$, $c_i$, and the structural intercept), not on any data-driven bound, a race whose real floor happens to sit near $D_i^*$ will show a spuriously large -- though finite -- estimated marginal seat gain, and the model carries no internal signal distinguishing this from a genuine, historically supported effect. In practice this manifested as the optimizer recommending large sums in Safe-tier districts with near-zero candidate-committee floors under an early uncapped specification: 81% of that specification's seat-gain estimate traced to races spending under \$500,000, and Safe-tier races absorbed 45% of the recommended party budget (Section 6.4). The correction this calls for is a regularizer informed by where the historical panel's identifying variation actually lies -- not a device for enforcing boundedness against a divergence that does not occur.

## Design Requirements

A satisfactory correction to the extrapolation risk identified in Proposition 1's corollary must satisfy several properties simultaneously, motivated by what a naive fix would get wrong.

- **Endogenous.** The correction should be a function of the model's own state (each race's estimated competitiveness), not an exogenously imposed constant, so that it adapts automatically to a race's context rather than requiring a separately tuned cap for every race or every cycle.
- **Smooth and differentiable.** The optimizer in Section 7 is gradient-based (SLSQP); any correction that introduces a kink or discontinuity (e.g. a hard spending cap) would break the analytic gradient the optimizer relies on and could introduce spurious local optima.
- **Bounded.** Even though $\text{MSG}_i$ is finite everywhere (Proposition 1), its interior peak at $D_i^*$ can still land at an implausibly large value relative to what the historical panel supports. The correction must cap the achievable margin shift at a small, principled multiple of the race's own estimated uncertainty, so that a floor $f_i$ landing near $D_i^*$ cannot translate into an extrapolated effect size unsupported by data.
- **Symmetric in its economic interpretation.** The correction should bind most weakly for races genuinely near the competitive tipping point -- where a real persuasion effect is most plausible -- and bind most strongly for races far from it in either direction, rather than penalizing all low-spending races uniformly regardless of whether they are competitive.
- **Calibration-friendly.** The correction should introduce as few new free parameters as possible, and those it does introduce should be identifiable from a transparent, reproducible sensitivity analysis rather than fixed by assumption (Section 6.4).

## Alternative Solutions Considered

Two alternative corrections were tested against the design requirements above and rejected.

**Persuadable-multiplier calibration.** A first approach attempted to calibrate the ceiling directly against observed repeat-challenger swing magnitudes -- i.e., to let the historical data itself reveal how large a margin shift is empirically plausible. This was rejected because the raw repeat-challenger swings were *largest* in the most hopeless districts, the opposite of what a persuasion ceiling should imply. Investigation traced this to a composition effect rather than a genuine persuasion signal: in the most lopsided districts, a repeat challenger frequently becomes a token candidate between cycles (reduced fundraising, reduced campaign activity), so the observed "swing" reflects declining challenger effort rather than a large marginal effect of spending.

**Strategic ($\sigma$-only) weighting.** A second approach attempted to scale the ceiling by $\sigma_i$ alone, on the logic that higher-uncertainty races should tolerate a larger achievable margin shift. This was rejected because $\sigma_i$'s own dependence on partisan lean is far weaker than $\mu_i$'s (Section 6.2 coefficient: $0.008$ per PVI point for $\sigma_i$ versus $1.057$ for $\mu_i$), so $\sigma_i$ alone does not discriminate between hopeless and competitive districts with anywhere near the resolution the ceiling requires.

A third, structurally simpler alternative -- an exogenous hard spending cap per race, independent of competitiveness -- was not formally tested but is excluded on design-requirement grounds alone: it is neither endogenous nor differentiable, and would require a separate, ad hoc calibration for every race type.

## Proposed Persuasion Ceiling

Define $\Phi_0^{(i)} \equiv \Phi(\mu_i(0)/\sigma_i)$, race $i$'s win probability evaluated at its own candidate-only spending floor ($x_i = 0$, i.e. $D_i = f_i$) -- the win probability the model assigns *before* any party money is added. The persuasion ceiling caps the achievable margin shift above the floor level $\mu_i(0)$ at

$$C_i \;=\; C_{\max}\cdot 4\,\Phi_0^{(i)}\big(1-\Phi_0^{(i)}\big)$$

and the capped margin is obtained by an exponential-decay saturation toward that ceiling:

$$\mu_i'(x_i) = \mu_i(0) + C_i\left(1 - \exp\!\left[-\frac{\mu_i^{\text{raw}}(x_i)-\mu_i(0)}{C_i}\right]\right)$$

where $\mu_i^{\text{raw}}(x_i)$ is the uncapped margin from Section 4.2. As $\mu_i^{\text{raw}}(x_i) - \mu_i(0) \to \infty$ (i.e., as party spending grows without bound), $\mu_i'(x_i) \to \mu_i(0) + C_i$: the achievable shift saturates at the ceiling rather than diverging. $C_{\max}$ is the framework's single new free parameter, and its calibration is the subject of Section 6.4's sensitivity sweep.

**Lemma (the transform is unclamped on the feasible domain).** *For every race with $c_i>0$ -- every race in the estimation universe, per Proposition 1 -- $\mu_i^{\text{raw}}(x_i) \ge \mu_i(0)$ for all $x_i\ge0$, so the exponent above is never positive-forced-to-zero and the transform requires no $\max(\cdot,0)$ clamp.*

*Proof.* $\partial\mu_i^{\text{raw}}/\partial D_i = c_iR_i/(D_iT_i) > 0$ for every $D_i,R_i,T_i>0$ and $c_i>0$ (Section 4.3), so $\mu_i^{\text{raw}}$ is strictly increasing in $D_i$, hence in $x_i$ (since $D_i=f_i+x_i$ is strictly increasing in $x_i$). Therefore $\mu_i^{\text{raw}}(x_i)\ge\mu_i^{\text{raw}}(0)=\mu_i(0)$ for every $x_i\ge0$. $\blacksquare$

This lemma is what makes $\mu_i'(x_i)$ a genuinely smooth ($C^\infty$) function of $x_i$ on the entire feasible domain $x_i\ge0$, rather than a piecewise function with a kink at $x_i=0$: the reference production implementation (`model/ceiling.py`) retains a $\max(\cdot,0)$ guard defensively, but the lemma shows it never binds under any fitted coefficient vector this framework has produced, and is not needed for the differentiability claim below.

The correction to the marginal seat gain gradient follows by the chain rule applied to the saturating transform:

$$\frac{\partial \mu_i'}{\partial \mu_i^{\text{raw}}} = \exp\!\left[-\frac{\mu_i^{\text{raw}}-\mu_i(0)}{C_i}\right] \;\equiv\; \text{decay}_i \in (0,1]$$

so that the corrected marginal seat gain is simply $\text{MSG}_i' = \text{MSG}_i \times \text{decay}_i$, an analytic multiplicative correction to the uncapped gradient derived in Section 4.3 -- the optimizer's gradient never needs to be re-derived from scratch, only rescaled.

## Properties

**Proposition 2 (Ceiling properties).** *The function $C(\Phi_0) = C_{\max}\cdot 4\Phi_0(1-\Phi_0)$ on $\Phi_0 \in [0,1]$ satisfies: (i) $C(\Phi_0) \ge 0$ for all $\Phi_0 \in [0,1]$, with equality iff $\Phi_0 \in \{0,1\}$; (ii) $C$ is maximized at $\Phi_0 = 1/2$, where $C(1/2) = C_{\max}$; (iii) $C$ is $C^\infty$ (infinitely differentiable) in $\Phi_0$, being a polynomial; (iv) $C_i$ is endogenous, since $\Phi_0^{(i)}$ is itself a function of the fitted model's own state ($\mu_i(0), \sigma_i$) rather than an exogenously fixed constant.*

*Proof.* (i) $4\Phi_0(1-\Phi_0) = 1 - (2\Phi_0-1)^2 \ge 0$ on $[0,1]$ since $(2\Phi_0-1)^2 \le 1$ there, with equality iff $2\Phi_0-1=\pm1$, i.e. $\Phi_0\in\{0,1\}$. (ii) $\frac{d}{d\Phi_0}[4\Phi_0(1-\Phi_0)] = 4-8\Phi_0 = 0 \iff \Phi_0=1/2$, and the second derivative $-8<0$ confirms a maximum, with value $4(1/2)(1/2)=1$, so $C(1/2)=C_{\max}$. (iii) A quadratic polynomial in $\Phi_0$ is entire. (iv) $\Phi_0^{(i)} = \Phi(\mu_i(0)/\sigma_i)$ where $\mu_i(0)$ and $\sigma_i$ are both outputs of the estimated model (Section 6), not inputs chosen by the analyst. $\blacksquare$

Boundedness of the full saturating transform follows immediately: since $C_i \le C_{\max}$ for every race (Proposition 2(i)-(ii)) and $\text{decay}_i \in (0,1]$ by construction, $\mu_i'(x_i) \le \mu_i(0) + C_{\max}$ for every $x_i \ge 0$ -- capping the finite-but-potentially-implausible peak characterized in Proposition 1's corollary at a value the sensitivity sweep of Section 6.4 disciplines, rather than responding to a divergence that Proposition 1 shows does not occur. Differentiability of $\mu_i'$ in $x_i$ follows from the Lemma above (no clamp is active on the feasible domain) composed with the differentiability of $\mu_i^{\text{raw}}$ and of $C_i$ in the model state (Proposition 2(iii)) -- so the corrected objective retains the smooth gradient the SLSQP optimizer of Section 7 requires, satisfying every design requirement of Section 4.5 simultaneously.

## Economic Interpretation

The ceiling is best understood as a regularization prior, not a behavioral claim about voters. It does not assert that persuasion effects are literally bounded by a parabola in $\Phi_0$; it asserts that the model should not be permitted to infer a spending effect *larger than a small multiple of the race's own already-estimated outcome uncertainty*, scaled by how close to a genuine toss-up the race's current state suggests it is. A true toss-up ($\Phi_0=1/2$) is the race type in which even a modest, well-estimated margin shift produces the largest change in win probability (the density argument of Section 4.1) and in which an extrapolation error is most consequential to the optimizer's objective -- a plausibility-and-stakes argument for loosening the ceiling there, not a claim about where the underlying causal identification happens to be strongest. That distinction matters concretely here: the repeat-challenger sample underlying $\beta_{RC}$ (Section 6.3) is in fact heavily skewed toward Safe R matchups (72% of the 118 pairs, Section 6.5), so competitive races are, if anything, comparatively under-represented in the causal anchor itself, even though they are exactly where the ceiling is least restrictive. A race the model already rates as near-certain for either party ($\Phi_0$ near 0 or 1) is the race type in which a large spending effect is least plausible on priors independent of the identification question, and the ceiling shrinks toward zero there by construction. The persuasion ceiling therefore encodes a plausibility-and-stakes intuition in a single differentiable function -- it is deliberately not calibrated to track where the panel's identifying variation is richest, which Section 6.5 shows is not the competitive tier at all.

\newpage

# Data

## Data Sources

The framework is built exclusively from publicly available data, a deliberate design choice ensuring full reproducibility without a paid vendor feed.

**Election outcomes.** MIT Election Data and Science Lab (house results, 1976--2024) supplies district-level vote totals and winners; Daily Kos Elections supplies district-matched results with redistricting crosswalks for 2012--2024, needed because congressional district boundaries change between cycles.

**Campaign finance.** Three distinct FEC-derived channels are used: candidate-committee disbursements (FEC bulk `weball` files, `TTL_DISB`), party coordinated expenditures (FEC Schedule F, fetched per-committee via the FEC API), and independent expenditures (FEC Schedule E comprehensive file, with the live FEC API used for the in-progress 2026 cycle). OpenSecrets race-level summaries provide a cross-check on both-party totals.

**Political environment.** Cook Partisan Voting Index (PVI) supplies district partisan lean; historical generic congressional ballot polling averages supply the national-environment factor $G$ for each cycle; Census American Community Survey 5-year estimates supply citizen voting-age population (CVAP) for per-voter spending normalization; incumbency status is derived from FEC candidate-status codes (`CAND_ICI`) cross-referenced against Ballotpedia, always coded relative to the Democratic candidate (Incumbent, Challenger, or Open).

## Coverage

The historical estimation panel spans the 2012, 2014, 2016, 2018, 2020, and 2022 House election cycles. The primary evaluation sample is the 2024 cycle; the 2022 cycle additionally serves as a fully out-of-sample validation target when estimation is restricted to 2012--2020 only (Section 8). After universe filters (minimum \$100,000 total two-party spending, exclusion of Alaska for ranked-choice-voting incompatibility, and the requirement of a valid Cook PVI value), the 2024 analysis universe contains 433 races; the primary efficiency test (Section 8) is restricted further to the 53 races Cook Political Report rated Lean D, Toss-Up, or Lean R in 2024, and 61 in the analogous 2022 out-of-sample universe. Causal identification of the base spending elasticity $\beta_{RC}$ (Section 6.3) uses 118 repeat-challenger pairs identified across six consecutive-cycle transitions in the 2012--2022 panel.

## Feature Engineering

Three constructed variables drive the model. The **spending ratio** $\text{ratio}_i = D_i/(D_i+R_i)$ is the Democratic share of total two-party spending, motivated by the equilibrium logic of Erikson and Palfrey (2000) that relative spending, not absolute levels, governs outcomes. The **absolute partisan lean** $|\text{PVI}_i|$ enters both the margin and $\sigma_i$ models as a measure of structural competitiveness independent of which party currently holds the seat. **Per-voter spending intensity**, $\log\big((D_i+R_i)/\text{CVAP}_i\big)$, normalizes raw spending totals by district-eligible-voter population, computed but constrained to zero in the primary specification (coefficient $\alpha_4$) due to an endogeneity concern documented in the code: total spending intensity is itself partly a function of how competitive a race is, so including it as a control risks partially absorbing the effect the spending-ratio term is meant to capture. An individual-contribution-share variable ($\alpha_5$) was estimated as a candidate-quality proxy but is likewise constrained to zero in the reported specification (Section 6.6) after diagnostic work indicated it functions as a race-salience proxy that penalizes competitive-race grassroots fundraising rather than measuring candidate quality.

## Cleaning

Race-cycle observations are dropped if total two-party spending is below \$100,000 (too thin to reflect a genuine contest), if a valid Cook PVI value cannot be matched (10 of 443 pre-filter races in 2024), or if the computed spending ratio is degenerate (zero or undefined, i.e. one side reported literally zero spending). Alaska is excluded in every cycle due to ranked-choice voting's incompatibility with the two-party vote-margin framework. District identifiers are harmonized across redistricting cycles via the Daily Kos crosswalk; districts affected by mid-decade redistricting (13 in the 2024 cycle, spanning North Carolina, Louisiana, Alabama, and New York) are flagged for interpretive caution but retained in the universe rather than excluded, since exclusion would non-randomly remove exactly the newly competitive seats the framework is most intended to evaluate. Candidate rosters are deduplicated to one nominee per party per district (the top spender within each party, following standard practice for multi-candidate primary states), with a cross-reference against MIT MEDSL's general-election ballot to exclude large disbursements from candidates who did not appear on the House general-election ballot (e.g. a sitting member who instead ran for Senate).

## Final Dataset

**Table 2: Final Dataset Summary**

| Quantity | Value |
|---|---|
| Historical estimation panel | 2012, 2014, 2016, 2018, 2020, 2022 (6 cycles) |
| Primary evaluation cycle | 2024 |
| Out-of-sample validation cycle | 2022 (estimated on 2012--2020 only) |
| Total races, 2024 universe (post-filter) | 433 |
| Competitive-tier races, 2024 (Lean D / Toss-Up / Lean R) | 53 |
| Competitive-tier races, 2022 OOS (Lean D / Toss-Up / Lean R) | 61 |
| Repeat-challenger pairs (causal identification) | 118 (across 6 cycle transitions) |
| Data sources | FEC (candidate + party + IE), MIT MEDSL, Cook PVI, Census ACS5, Daily Kos, Ballotpedia |
| Spending channels combined | Candidate-committee disbursements, party coordinated expenditures, independent expenditures |

\newpage

# Parameter Estimation \& Calibration

This section answers, for every parameter the framework depends on, the question: where did this number come from?

## Baseline Margins

The margin model's control-surface coefficients ($\alpha_0$--$\alpha_3$) and interaction coefficients ($\beta_2,\beta_3$) are estimated by OLS on the 2012--2022 panel with $\beta_1$ pre-imposed at its repeat-challenger value via offset regression (Appendix B.2): $y^*_{it} = y_{it} - \hat\beta_{RC}\log(\text{ratio})_{it}$ is regressed on the remaining covariates, so that the causally identified elasticity is never contaminated by the endogenous cross-sectional variation the rest of the specification absorbs. Standard errors are HC3 heteroskedasticity-robust throughout.

## Uncertainty ($\sigma_i$)

$\sigma_i$ is estimated from the distribution of $\log|\text{margin residual}|$ conditional on structural predictors (absolute PVI, open-seat status, challenger status, absolute generic ballot), then retransformed with a Duan (1983) smearing correction -- a multiplicative factor that corrects the systematic downward bias introduced by exponentiating a fitted log-scale model, which recovers the conditional median rather than the conditional mean of the residual distribution.

## Spending Elasticity

The base elasticity $\beta_1 = \beta_{RC}$ is identified via the repeat-challenger first-differenced design of Section 6.3 below; the open-seat elasticity $\beta_1^{OS}$ is calibrated via Bayesian shrinkage (Section 6.3).

**Scope of the causal claim.** Only $\beta_{RC}$ carries the repeat-challenger design's identification (Section 6.3); it is the single coefficient in the entire margin specification with a defensible claim to causal identification, resting on an untestable but more-credible-than-cross-sectional assumption. The control-surface coefficients $\alpha_0$--$\alpha_3$ and the interaction terms $\beta_2,\beta_3$ (Table 3) are descriptive associations estimated on the full observational panel, not causally identified effects. The open-seat elasticity $\beta_1^{OS}$ is a *blend*: Section 6.3's posterior weight $\kappa=0.957$ means the reported open-seat estimate is driven overwhelmingly by the observational panel likelihood, with the causally-identified $\beta_{RC}$ contributing only a 4.3% prior-mean shrinkage target. Throughout this paper, "the spending response surface" should therefore be read as a *partially causally anchored* model -- one causally identified parameter disciplining an otherwise observational specification -- not as a fully causally identified conditional response surface.

### Repeat-Challenger Identification

Following Levitt (1994), the primary causal estimate restricts to races in which the same challenger contests the same incumbent across consecutive cycles, estimating the first-differenced specification $\Delta\text{Margin}_i = \beta_{RC}\Delta\log(\text{ratio})_i + \Delta\eta_i$, which cancels any time-invariant pair fixed effect $\alpha_i$ exactly. The identifying assumption -- that, conditional on the national environment, cycle-to-cycle changes in relative spending are uncorrelated with unobserved changes in race-specific competitiveness -- cannot be directly tested, but is more credible than a cross-sectional analogue because candidate quality, incumbency advantage, and district partisan composition are all held fixed within a matched pair.

### Open-Seat Calibration

Open seats lack a repeat-challenger analogue by construction (there is no incumbent to hold fixed across cycles), so the open-seat elasticity is calibrated through a three-part procedure: (i) the repeat-challenger estimate $\beta_{RC}$ serves as a causally anchored prior mean; (ii) the full observational panel's open-seat interaction term supplies a likelihood; (iii) Bayesian shrinkage combines the two, with the shrinkage weight $\kappa$ determined by the relative precision of the prior and the panel likelihood, and an Oster (2019) bounding procedure ($\delta=1$) supplying a conservative lower-bound alternative specification. The full derivation is given in Appendix B.4.

## Persuasion Ceiling

$C_{\max}$, the ceiling's single free parameter, is set by a seven-point sensitivity sweep over $C_{\max} \in \{3, 5, 7, 10, 15, 20, 30\}$ percentage points, evaluating the resulting Safe-tier, Competitive-tier, and Likely-tier party-budget shares and total expected seats at each value (Figure 1; exact values in Appendix E). Every quantity moves smoothly and monotonically across the range -- Safe-tier share from 6.9% to 12.6%, Competitive-tier share from 63.3% down to 55.2%, and expected seats from 215.10 up to 220.57 -- with no discontinuity or fragile threshold anywhere tested. Because the trade-off is smooth rather than exhibiting a sharp local optimum, $C_{\max}=10.0$ is adopted as a moderate point in this range: it keeps Safe-tier party-budget share under 10% while retaining a majority (60.0%) of the party budget in Competitive-tier races, without claiming that this specific value is uniquely optimal by any criterion internal to the sweep itself.

![Persuasion ceiling sensitivity sweep: Cook-tier party-budget shares across $C_{\max} \in \{3,\dots,30\}$ (log scale), against the pre-ceiling uncapped baseline (45% Safe-tier share, dashed line).](figures/persuasion_ceiling_cmax_sweep_fig.png){width=85%}

## Bootstrap

Parametric standard errors on $\beta_{RC}$ rely on a normal approximation to the OLS sampling distribution, untested against the actual composition of the 118-pair repeat-challenger sample, which skews toward Safe R matchups (72% of pairs). A non-parametric bootstrap (1,000 resamples of the 118 pairs with replacement, re-estimating $\beta_{RC}$ on each resample) provides a distribution-free alternative: bootstrap mean $5.543$, standard deviation $1.514$ (close to the parametric SE of $1.587$), skew $+0.198$ (mild, visible as a right tail extending past the symmetric normal approximation in Figure 2), and 95% CI $[2.834, 8.640]$ versus the parametric $[2.364, 8.585]$ -- comparable width, with a meaningfully higher lower bound, indicating the low-end "collapse" scenario used in sensitivity analysis is somewhat less likely under the empirical resampling distribution than the normal approximation implies.

![Non-parametric bootstrap distribution of $\hat\beta_{RC}$ (1,000 resamples) against the parametric normal approximation.](figures/beta_rc_bootstrap_distribution.png){width=80%}

## Calibration Summary

**Table 3: Parameter Calibration Summary**

| Parameter | Estimate | SE / Uncertainty | Method |
|---|---|---|---|
| $\alpha_0$ (intercept) | 2.475 | HC3 | Panel OLS |
| $\alpha_1$ (PVI) | 1.057 | HC3 | Panel OLS |
| $\alpha_2$ (D incumbency) | 31.134 | HC3 | Panel OLS |
| $\alpha_3$ (generic ballot) | 0.424 | HC3 | Panel OLS |
| $\beta_1 = \beta_{RC}$ | 5.475 | SE 1.587 (bootstrap: mean 5.543, SD 1.514) | Repeat-challenger, $n=118$ |
| $\beta_2$ ($\log(\text{ratio})\times|\text{PVI}|$) | 0.054 | HC3 | Panel OLS |
| $\beta_3$ ($\log(\text{ratio})\times$ Incumb.) | 28.054 | HC3 | Panel OLS |
| $\beta_1^{OS}$ (open-seat, calibrated) | 6.995 | Posterior SE 0.656 | Bayesian shrinkage ($\kappa=0.957$) |
| $\beta_1^{OS,\,lb}$ (conservative bound) | 5.919 | -- | Oster (2019), $\delta=1$ |
| $\sigma_i$ model | see Appendix B.5 | Duan-corrected retransformation | Log-linear OLS on \|residual\| |
| $\sigma_G$ (national environment SD) | 2.8 pp | -- | RMS forecast error, 2014--2022 |
| $C_{\max}$ (persuasion ceiling) | 10.0 pp | 7-point sweep, $\{3,\dots,30\}$ | Sensitivity sweep, Fig. 1 |
| $R^2$ (competitive subset, $|PVI| \le 10$) | 0.561 | -- | -- |

\newpage

# Optimization Algorithm

## Optimization Strategy

Two solvers are used depending on the objective's curvature. For the risk-neutral case ($\gamma=0$), the true nonlinear objective $\sum_i\Phi(\mu_i(x_i)/\sigma_i)$ is optimized directly via Sequential Least Squares Quadratic Programming (SLSQP), preserving the diminishing-returns structure of the $\Phi(\cdot)$ conversion rather than linearizing it. A linearized MSG-based LP/QP formulation ($\max\ \text{MSG}\cdot\mathbf x - \gamma\,\mathbf x'\Sigma\mathbf x$, solved via convex quadratic programming) is retained for the risk-penalized case ($\gamma>0$) and for inner-loop uncertainty-propagation draws, where the linear approximation is both adequate (small local perturbations around an already-estimated allocation) and substantially faster. Both solvers respect the same budget and per-race cap constraints of Section 3.5.

## Algorithm

**Algorithm 1: Nonlinear Expected-Seats Maximization**

\footnotesize
```
Input:  races (N), margin-model coefficients, sigma model,
        party budget B, covariance matrix Sigma, risk aversion gamma,
        cap fraction kappa, adversarial response eta
Output: optimal party allocation x* (N,)

1.  Precompute per-race static arrays:
      mu_const_i, c_spend_i, sigma_i, floor_i (= f_i), R_i, cvap_i
2.  Compute persuasion ceiling inputs (Section 4.7):
      mu_floor_i <- margin at x_i = 0 (candidate-only floor)
      Phi0_i     <- Phi(mu_floor_i / sigma_i)
      C_i        <- C_max * 4 * Phi0_i * (1 - Phi0_i)
3.  Initialize x0 <- observed party allocation, clipped to
      [0, kappa*B], rescaled to satisfy sum(x0) <= B
4.  Rescale variables to $M units (numerical conditioning; App. F)
5.  Define objective and analytic gradient:
      f(x)      = -sum_i Phi( mu_i'(x_i) / sigma_i )   [ceiling applied]
      grad f(x) = -MSG'(x)                        [chain-rule corrected]
6.  Solve via SLSQP:
      minimize f(x)
      s.t.     sum(x) <= B,  0 <= x_i <= kappa*B  for all i
      (maxiter = 3000, ftol = 1e-12)
7.  Return x* = max(result.x, 0); compute E[Seats], Var[Seats],
      budget used, and count of corner solutions (x_i at 0 or kappa*B)
```
\normalsize

Full production source: `src/backtest/optimizer/allocator.py::optimize_nonlinear()`.

## Computational Complexity

Each SLSQP iteration evaluates the objective and its analytic gradient in $O(N)$ time (all per-race quantities are precomputed vectorized arrays; no per-race loop occurs inside the hot optimization path), plus $O(N^2)$ for the risk-penalized quadratic term $\mathbf x'\Sigma\mathbf x$ when $\gamma>0$. With $N\approx 433$ races and a maximum of 3,000 SLSQP iterations, a full optimizer run completes in well under one second on commodity hardware for the risk-neutral case; the convex QP solve for $\gamma>0$ scales similarly, bounded by the interior-point solver's iteration count rather than by $N$ directly at this problem size.

## Computational Environment

The pipeline is implemented in Python 3.13, using NumPy and pandas for data manipulation, `statsmodels` for OLS/HC3 estimation, SciPy's `optimize.minimize` (SLSQP) for the nonlinear risk-neutral solve, and `cvxpy` (CLARABEL/SCS/SCIPY backends) for the convex QP risk-penalized solve. All randomized procedures (bootstrap resampling, permutation tests) use a fixed seed (42) for exact reproducibility. The full pipeline -- data ingestion, estimation, optimization, and figure generation -- is orchestrated by `scripts/run_backtest.py` and runs end-to-end on a single consumer laptop in well under ten minutes; no specialized hardware is required. Configuration parameters (Appendix F) are centralized in a single `config.yaml` rather than hard-coded, so every reported number in this paper traces to an explicit, version-controlled input.

\newpage

# Empirical Results

All figures reported in this section reflect the final, corrected pipeline (persuasion ceiling applied, unified floor-margin convention). Every reported statistic is reproducible end-to-end from `scripts/run_backtest.py` against the public data sources of Section 5. The efficiency tests below are presented in order of methodological priority: a primary test that directly evaluates the paper's own KKT stationarity condition (Appendix C.1), a secondary test isolating pre-allocation targeting, a decomposition of the model-implied counterfactual gain, out-of-sample replication of both new tests, and, retained for transparency, the original spending-versus-current-MSG correlation together with an explanation of why it was replaced.

## Internal Validation

Three checks validate that the implementation matches the derivation of Section 4 before any result is interpreted substantively. First, the analytic marginal-seat-gain gradient (Section 4.3) was checked against a finite-difference numerical derivative of the objective; this comparison surfaced and confirmed the fix of a genuine implementation bug in which an earlier gradient routine computed $c_i/T_i$ rather than the derived $c_i R_i/(D_i T_i)$, an error invisible to unit tests built only on spending-parity cases (where the two expressions coincide) but material for the lopsided-spending races that dominate the actual data. Second, a suite of 341 automated tests across 19 files covers margin prediction, the win-probability/MSG chain, the persuasion ceiling's boundedness and endogeneity properties (Proposition 2), the optimizer's constraint satisfaction, and the $\sigma_i$ ordering diagnostic, and passes in full against the reported specification. Third, model calibration -- whether stated win probabilities match realized win frequencies -- is assessed directly against 2024 outcomes (Figure 3).

![Model calibration: predicted win probability against realized win frequency, 2024 competitive races.](figures/model_calibration.png){width=75%}

## Primary Test: Marginal-Return Equalization

Appendix C.1 derives that at a risk-neutral interior optimum, $\text{MSG}_i=\lambda$ (a constant shadow price) for every race receiving strictly-interior party funding -- efficient allocation *equalizes* marginal seat gain among funded races; it does not, on its own, imply any particular correlation between spending levels and MSG. This motivates a direct test of that condition rather than a correlation-based proxy for it.

For each race, "interior-funded" is defined as party spending strictly between zero and the concentration cap $\kappa B$ (Section 3.3), and an empirical shadow price $\hat\lambda$ is estimated as the median MSG among a group's interior-funded races. Table 4 reports the dispersion of MSG around $\hat\lambda$ for DCCC's observed 2024 allocation and for the model-optimal allocation, which by construction should show dispersion at or near zero (bounded only by SLSQP's convergence tolerance).

**Table 4: KKT Dispersion Among Interior-Funded Races, 2024**

| Statistic | DCCC Observed | Model-Optimal |
|---|---|---|
| $n$ interior-funded | 56 | 112 |
| $\hat\lambda$ (median MSG, seats/\$) | $2.34\times10^{-9}$ | $4.02\times10^{-9}$ |
| Coefficient of variation | $1.32$ | $6.3\times10^{-6}$ |
| Median absolute deviation from $\hat\lambda$ | $1.44\times10^{-9}$ | $1.6\times10^{-14}$ |
| Interquartile range | $3.06\times10^{-9}$ | $3.2\times10^{-14}$ |
| $p_{90}/p_{10}$ ratio | $25.9$ | $1.00002$ |
| \% outside $\pm25\%$ of $\hat\lambda$ | $85.7\%$ | $0.0\%$ |

DCCC's interior-funded races show a 90th-to-10th-percentile MSG ratio of nearly 26-to-1, and 86% fall outside a generous $\pm25\%$ band around the implied shadow price; the model-optimal allocation equalizes MSG almost exactly, as the theory requires. This is direct evidence that DCCC's observed allocation violates the necessary first-order condition for a risk-neutral interior optimum -- no assumption about the sign of any correlation is required to reach this conclusion.

A complementary boundary check applies the same logic to races DCCC funded at exactly zero: complementary slackness requires that a race pinned at its lower bound have $\text{MSG}_i\le\lambda$ (no incentive to fund it further). Of 377 races DCCC gave zero party dollars to in 2024, 206 (55%) have model-estimated MSG exceeding $\hat\lambda$ by more than the $25\%$ tolerance band -- a large number that should be read as evidence the boundary condition is violated at scale, not as a precise headcount of 206 specific races each individually mispriced by a well-defined margin; the test is a coarse binary threshold, and Section 8.4 examines the composition of this group directly rather than treating the count alone as dispositive.

To make the dispersion finding concrete, consider a single feasible transfer: moving \$100,000 in party funds from DCCC's lowest-MSG interior-funded race (WA-04, a Safe R seat where the fitted margin $\hat\mu=-40.6$ points and $\hat\sigma=11.0$ place the race so deep in the tail that its estimated marginal seat gain rounds to zero) to its highest-MSG-with-capacity race (GA-07, a Likely D seat closer to the tipping point) increases modeled expected seats by $+0.0396$ -- from a single \$100,000 reallocation out of a \$465 million budget. This is not a hypothetical: WA-04 is a real interior-funded race in the observed data, illustrating concretely what the aggregate dispersion statistic means for an actual dollar.

## Secondary Test: Pre-Allocation Targeting

A separate question from equalization is whether DCCC directed money toward races with higher pre-allocation potential in the first place. Correlating observed spending against MSG evaluated *at that same observed spending level* -- the original test design -- is confounded: diminishing returns mechanically depresses a race's own current-MSG reading the more it has already received, independent of whether the money was well targeted. Section 8.8 revisits this confound directly; here, MSG is instead evaluated at each race's own candidate-only floor ($D_i=f_i$, no party money), a quantity fixed before any party dollar is committed and therefore immune to the confound.

$$\rho_{\text{floor}} = -0.122 \quad (p=0.384,\ n=53)$$

This is a **null result**: no statistically detectable relationship, in either direction, between observed DCCC party spending and each race's pre-allocation marginal potential. It should not be read as evidence that DCCC's initial targeting was reasonable, nor as evidence that it was systematically biased -- a null result establishes neither proposition. The defensible statement is that this analysis finds no evidence that observed party spending was systematically directed toward, or away from, races with greater model-estimated pre-allocation marginal return.

## Model-Implied Counterfactual Gain and Its Decomposition

A model-optimal reallocation of the identical \$465 million party budget, holding every race's own candidate-committee floor fixed, is estimated to yield **+2.83 additional expected seats** relative to DCCC's observed allocation (215.12 $\to$ 217.94). This figure is a model-implied counterfactual: it is generated by the same response surface and objective the optimizer maximizes, and the permutation tests of Section 8.8 establish that it is not achievable by arbitrary reallocation, but it has not been -- and cannot be, from observational data alone -- validated as the number of real seats such a reallocation would actually have produced.

Because the optimizer in this baseline run is free to reallocate across the entire eligible universe rather than being restricted to races DCCC already funded, the +2.83 figure conflates two distinct sources of gain. Re-solving with every race DCCC funded at exactly zero held fixed at zero -- so the optimizer may only rebalance the budget among races already receiving some party money -- isolates an **intensity** component; the remainder is a **selection** component attributable specifically to funding previously-zero-funded races:

**Table 5: Selection-versus-Intensity Decomposition, 2024**

| Allocation | Expected Seats | Gain vs. DCCC |
|---|---|---|
| DCCC observed | 215.12 | -- |
| Already-funded-only reallocation (selection frozen) | 215.38 | $+0.26$ (intensity) |
| Full model-optimal reallocation | 217.94 | $+2.83$ (total) |
| *Selection component (total $-$ intensity)* | -- | $+2.56$ |

Rebalancing amounts among races DCCC was already funding recovers only 9% of the total modeled gain. The remaining 91% comes from the model funding 64 races DCCC gave zero party dollars to. This decomposition directly corrects an earlier, narrower reading of these results: the dominant pattern in the data is not that DCCC misjudged *how much* to give races it had already decided to support, but that a large number of races it did not engage with at all are estimated to have had real marginal value.

This selection-dominated finding was checked against the possibility that it simply reproduces the near-zero-floor extrapolation pathology the persuasion ceiling exists to prevent (Section 4.4's corollary). It does not appear to: of the 64 newly-funded races, 45 (70%) fall in the Likely or Lean or Toss-Up Cook tiers, with realistic multi-million-dollar candidate floors and opponent spending well inside the historical panel's support (the ten largest, by dollars allocated, include VA-10, WI-01, PA-01, CA-40, FL-27, and FL-28 -- competitive-adjacent seats with plausible floors, not artifacts). The remaining 30% (17 of 64) are Safe-tier races, a real presence that should not be minimized: it indicates the persuasion ceiling narrows but does not eliminate the model's willingness to recommend money for uncompetitive seats, and is flagged here rather than smoothed over (Section 10.2 returns to this).

## Baseline Comparisons

Table 6 situates the model-optimal allocation against two additional, MSG-free benchmarks holding the total party budget fixed at DCCC's observed 2024 total: a Cook-implied allocation (proportional to Cook's stated win probabilities) and a null equal-weight allocation across the competitive set. All rows are evaluated under the identical true nonlinear objective $\sum_i\Phi(\mu_i(D_i)/\sigma_i)$.

**Table 6: Expected Seats by Allocation Strategy, 2024 Cycle**

| Strategy | Expected Seats | Gain vs. DCCC |
|---|---|---|
| DCCC observed | 215.12 | -- |
| Cook-implied (proportional to Cook win prob.) | 215.18 | +0.07 |
| Null (equal-weight across competitive set) | 215.34 | +0.23 |
| Model optimizer (MSG-maximizing) | **217.94** | **+2.83** |

![Expected seats by allocation strategy, 2024 cycle.](figures/allocator_comparison.png){width=80%}

![Optimizer-recommended allocation minus observed DCCC allocation, by race, 2024 cycle.](figures/allocation_difference.png){width=85%}

Both MSG-free benchmarks outperform DCCC's actual allocation, though narrowly. Combined with Table 4's dispersion result and Table 5's decomposition, the most defensible reading is that DCCC's allocation is directionally sensible at the margin (it beats a null equal-weight benchmark by only a small amount, not by a large negative margin) but leaves a specific, replicable, and now-decomposed inefficiency on the table.

## Sensitivity Analysis

**Persuasion ceiling ($C_{\max}$).** Section 6.4's seven-point sweep shows the +2.83 figure is not an artifact of the ceiling's calibration: Safe-tier party-budget share declines smoothly from 45% (uncapped) to 9.0% ($C_{\max}=10$) with no discontinuity anywhere in the tested range $\{3,\dots,30\}$ (Figure 1).

**Spending elasticity ($\beta_{RC}$).** The bootstrap distribution of Section 6.5 (95% CI $[2.834,8.640]$) bounds how sensitive the headline seat-gain figure is to sampling uncertainty in the causal anchor; because the KKT dispersion test's qualitative conclusion depends on the *relative* MSG ranking across races rather than the absolute level of $\beta_{RC}$, it is materially more stable across this range than the point estimate of expected-seat gain itself.

**Budget concentration cap ($\kappa$).** The per-race concentration cap is swept over $\kappa\in\{0.05,0.10,0.15\}$ (Appendix F); the reported results use $\kappa=0.15$, the pipeline's baseline regime. The qualitative dispersion and decomposition findings are unaffected across this range; tighter caps modestly reduce the model optimizer's achievable seat gain by preventing full concentration in the very highest-MSG races.

## Out-of-Sample Replication (2022)

The full pipeline -- margin model, $\sigma_i$ model, $\beta_{RC}$, and every diagnostic above -- is re-estimated using exclusively the 2012--2020 panel and applied without modification to the 2022 cycle, which enters no stage of estimation.

**Table 7: Out-of-Sample Replication, 2022 Cycle**

| Metric | 2024 (Primary) | 2022 (OOS) |
|---|---|---|
| Estimation panel | 2012--2022 | 2012--2020 |
| KKT dispersion, DCCC interior (CV) | $1.32$ | $1.25$ |
| KKT dispersion, model-optimal (CV) | $6.3\times10^{-6}$ | $2.6\times10^{-6}$ |
| $p_{90}/p_{10}$, DCCC interior | $25.9$ | $19.9$ |
| \% DCCC interior outside $\pm25\%$ of $\hat\lambda$ | $85.7\%$ | $84.3\%$ |
| Boundary violations (zero-funded, MSG $>\hat\lambda$) | 206 / 377 | 208 / 363 |
| Floor-baseline $\rho_{\text{floor}}$ (targeting test) | $-0.122$ ($p=0.384$) | $-0.001$ ($p=0.995$) |
| Total model-implied gain | $+2.83$ | $+3.22$ |
| ...of which intensity | $+0.26$ (9%) | $+0.53$ (17%) |
| ...of which selection | $+2.56$ (91%) | $+2.69$ (83%) |
| \$100K pairwise transfer, $\Delta\mathbb E[\text{Seats}]$ | $+0.0396$ | $+0.0474$ |
| DCCC expected seats | 215.12 | 213.37 |
| Model optimizer expected seats | 217.94 | 216.59 |
| Brier score (model) | 0.0312 | 0.0360 |
| Brier score (Cook) | 0.0364 | 0.0340 |

Every result replicates directionally and in approximate magnitude: large, comparable KKT dispersion in both cycles against near-perfect model-optimal equalization; a null floor-baseline targeting correlation in both cycles (2022's is closer to exactly zero than 2024's); and a selection-dominated gain decomposition in both cycles, with intensity's share slightly higher in 2022 (17% vs. 9%) but selection dominant in both. This consistency across two structurally different election environments, estimated from entirely non-overlapping data, is the strongest evidence that the KKT-equalization and selection findings are structural rather than artifacts of a single cycle. Win-probability calibration is more mixed: the model improves on Cook's Brier score by 14% in the 2024 primary sample but is 5.9% *worse* than Cook out-of-sample in 2022 -- a specific calibration finding distinct from the efficiency findings above, which are robust in both cycles.

![Rank-rank scatter of spending versus current-MSG rank, retained for transparency and discussed in Section 8.8: observed spending rank vs. estimated MSG rank, competitive races.](figures/efficiency_frontier.png){width=48%}![Out-of-sample version, 2022 cycle.](figures/efficiency_frontier_2022.png){width=48%}

## Superseded Diagnostic: Spending-vs-Current-MSG Correlation

For transparency, and because it illustrates concretely why the primary test was redesigned, this subsection reports the originally-proposed efficiency test: the Spearman rank correlation between observed DCCC spending and MSG evaluated *at that same observed spending level*, across the 53 races Cook Political Report rated Lean D, Toss-Up, or Lean R in 2024.

$$\rho = -0.809 \quad (p<0.001,\ \text{95\% CI } [-0.936,-0.618],\ n=53)$$

A permutation test against an exact empirical null (2,000 random reassignments of DCCC's observed per-race spending, holding MSG fixed) confirms this correlation is not a small-sample artifact: 0 of 2,000 shuffles produced $|\rho|\ge0.809$. The correlation replicates out-of-sample ($\rho=-0.847$, $p<0.001$, $n=61$, 2022) and decomposes by Cook category as shown in Table 8, with every category negative and the strongest relationships in the most contested tiers.

**Table 8: Spearman Correlation by Cook Category, 2024 (superseded diagnostic)**

| Cook Category | $n$ | $\rho$ | $p$-value |
|---|---|---|---|
| Likely D | 40 | $-0.270$ | $0.092$ |
| Lean D | 28 | $-0.733$ | $<0.001$ |
| Toss-Up | 18 | $-0.930$ | $<0.001$ |
| Lean R | 7 | $-0.964$ | $<0.001$ |
| Likely R | 36 | $-0.677$ | $<0.001$ |

**Why this correlation does not, by itself, demonstrate misallocation.** Appendix C.1's KKT condition shows that an efficient risk-neutral allocation *equalizes* MSG among funded races rather than producing any particular sign of correlation between spending and MSG. Because MSG is decreasing in a race's own spending under diminishing returns (Section 4.3), any allocation process -- efficient or not -- that spends more on some races than others will mechanically tend to show lower current-MSG in the more-funded races, simply because they have moved further down their own response curve. A large, robust, out-of-sample-replicating negative $\rho$ is therefore consistent with genuine misallocation, but it is equally consistent with an efficient allocation process operating under ordinary diminishing returns. This is why Sections 8.2--8.4 substitute a test of the paper's own equalization condition (which the correlation sign cannot establish or refute) for this correlation as the paper's primary evidence. The permutation and Cook-category results above are retained because they remain useful robustness evidence for a different, narrower claim -- that DCCC's allocation is statistically distinguishable from a random reshuffle of its own dollars (the allocation-efficiency permutation test below) -- not because the correlation itself demonstrates inefficiency.

**Allocation-efficiency permutation test.** A second permutation test reshuffles DCCC's own party-dollar allocation across the 53 races and evaluates $\mathbb E[\text{Seats}]$ under the true nonlinear objective for each of 2,000 shuffles. DCCC's actual allocation ($\mathbb E[\text{Seats}]=215.12$) is matched or exceeded by only 2.9% of random reshuffles of its own dollars (null mean $214.84$, 95% CI $[214.55,215.12]$); the model optimizer's allocation ($\mathbb E[\text{Seats}]=217.94$) is matched or exceeded by 0 of 2,000 reshuffles. This test's conclusion -- that DCCC's allocation and the model's are both distinguishable from arbitrary reshuffling -- is compatible with the equalization-violation finding above: DCCC's spending is not random, but it is also not equalized at the margin.

![Permutation-test null distributions against observed DCCC and model-optimizer allocations, 2024.](figures/permutation_tests_null_distributions.png){width=85%}

**Winsorization (methodological demonstration, not re-verified against the final specification).** As a check on whether the superseded correlation is driven by a small number of extreme spending-ratio outliers, log-spending-ratios were winsorized at the 10th/90th, 5th/95th, and 1st/99th percentiles within each cycle's competitive set and $\rho$ recomputed under each trimmed specification on an earlier pipeline iteration; both cycles' correlations were stable under winsorization at every trim level tested. This predates the persuasion-ceiling and floor-margin-convention fixes reported elsewhere in this paper and has not been re-executed against the final specification; it is reported here as a methodological demonstration rather than a currently-verified figure (Appendix D).

\newpage

# Discussion

## Why Marginal Returns Are Not Equalized: Two Candidate Mechanisms

Section 8.4's decomposition shows the model-implied gain is dominated by selection (funding races DCCC left at zero) rather than intensity (resizing races already funded). This has a direct bearing on which real-world mechanisms are plausible explanations for the KKT dispersion finding, and it rules out treating them interchangeably.

**Mechanisms consistent with a selection-dominated gap** point to reasons a race might never have been engaged at all, independent of how well-calibrated DCCC's spending was among the races it did contest: capacity and staffing limits on how many races a committee can actively organize around in a single cycle; information timing -- a race's competitiveness may not have been legible to decision-makers at the point budgets were substantially set, which is a static-model limitation this paper shares with any single-period valuation and which a sequential, continuously-updated framework (developed in a companion paper) is explicitly designed to address; local candidate recruitment and self-funding dynamics the model does not observe; and genuine strategic considerations -- protecting incumbents, or pursuing the majority-probability objective of Section 3.4 rather than pure expected seats -- that could rationally leave some model-flagged races unengaged.

**Mechanisms consistent with an intensity gap** -- irreversible media-buy and staffing commitments, organizational resistance to withdrawing support once pledged, minimum-support expectations owed to a candidate -- remain relevant to the smaller (9--17%) intensity component, but do not explain why the larger selection component exists.

These are offered as candidate explanations the data are consistent with, not conclusions the data establish; distinguishing among them would require information (internal committee deliberations, the timing of allocation decisions relative to when a race's competitiveness became apparent) outside the public data this framework is built on (Section 10.1).

## Why Safe Seats Still Receive Some Funding

Every race in the universe, including uncompetitive ones, continues to receive its own candidate-committee spending floor $f_i$ in every allocation strategy compared in Section 8.5 -- that money is raised directly by the candidate's own committee and is not redirected by any strategy under comparison, DCCC's actual behavior included. What changes across strategies is only the *party* allocation layered on top of that floor. The persuasion ceiling of Section 4.7 keeps even the model-optimal strategy's Safe-tier party-budget share small (9.0% at the calibrated $C_{\max}$) but not zero, and Section 8.4's composition check found a genuine, non-trivial minority (30%) of the newly-selected races are Safe-tier -- a real residual the ceiling narrows rather than eliminates, and a specific direction for tightening $C_{\max}$ or its functional form in future work.

## Endogenous Regularization

Section 4's methodological claim is that the persuasion ceiling succeeds where the two rejected alternatives (Section 4.6) failed specifically because it is endogenous to the model's own estimated state rather than fit against an external target. The rejected persuadable-multiplier approach failed because it tried to calibrate against a noisy external signal (repeat-challenger swings) contaminated by an unrelated confound (candidate-quality composition); the rejected $\sigma$-only approach failed because it scaled by a quantity ($\sigma_i$) that does not itself vary enough with competitiveness to do the discriminating work required. The persuasion ceiling instead scales by $\Phi_0^{(i)}$, a quantity computed directly from the same margin and uncertainty model the ceiling is correcting -- the correction and the thing being corrected share the same information set by construction, which is what makes the parabola in Proposition 2 bind hardest for races the model already considers hopeless and loosest for races it considers competitive, on the plausibility-and-stakes logic of Section 4.9 rather than on any claim about where $\beta_{RC}$'s causal identification is concentrated (Section 6.5 shows it is not concentrated in the competitive tier).

## Strategic Implications

For a campaign committee, the framework's practical output is a ranked list of races by estimated marginal seat gain at current spending levels, an explicit flag on which races violate the equalization condition of Section 8.2, and a decomposition (Section 8.4) of how much of any recommended reallocation comes from resizing current commitments versus engaging currently-unfunded races -- the latter being the larger and, given Section 9.1's discussion, the more actionable category to interrogate directly ("why is this race at zero?") rather than the former. Rather than replacing strategist judgment, the framework is best used as a systematic check against it: races flagged by the boundary test (Section 8.2) are exactly the races where a committee should be able to articulate *why* it remains uninvested -- a candidate-quality signal, a capacity constraint, or a timing consideration the static model does not capture -- rather than treating the flag as self-evidently a mistake.

## Generalizability

The mathematical structure developed here -- a constrained budget allocated across many opportunities with heterogeneous, uncertain, diminishing-returns payoffs, correlated through a common environmental factor, and requiring an endogenous regularizer against the finite-but-implausible extrapolation risk characterized in Proposition 1's corollary -- is not specific to congressional elections. The same structure describes marketing budget allocation across channels or customer segments with saturating response curves; nonprofit fundraising-campaign targeting across donor segments; portions of military logistics resource allocation across theaters with correlated risk; public-policy program budgeting across jurisdictions; and healthcare resource allocation across facilities or interventions with diminishing marginal benefit. In each of these domains, a version of the extrapolation risk characterized in Proposition 1 will recur wherever a response function is specified in a form ($\log$-ratio, elasticity, or similar) whose gradient is large near a resource floor of zero even though the function itself is bounded there, and the endogenous-ceiling design requirements of Section 4.5 -- bounded, differentiable, calibration-friendly, and scaled by the model's own estimated state rather than an external constant -- generalize directly. The selection-versus-intensity decomposition of Section 8.4 also generalizes: any setting with a discrete "which opportunities to engage" decision layered on top of a continuous "how much to commit" decision admits the same split, and the finding that selection dominated intensity here is a testable, not assumed, property of any such system.

\newpage

# Limitations

## Data

The framework relies exclusively on public data, which excludes several variables a real committee's internal decision-making likely uses: internal polling (as opposed to public polling averages), qualitative candidate-quality assessments beyond incumbency status, and complete outside-group (non-party Super PAC) spending, which is unevenly disclosed before 2016 and is therefore excluded from the primary spending measure. Committed-but-undisbursed party spending is not observable in public FEC filings at all, a limitation that matters most for the sequential extension of this framework (Section 9.1's companion-paper pointer) rather than for the single-period analysis reported here.

## Modeling

The log-ratio spending specification (Section 4.2) is itself a modeling choice motivated by theoretical priors (Erikson and Palfrey 2000) rather than derived from first principles, and Proposition 1 shows it is precisely this choice that produces the finite-peak extrapolation risk Section 4's remaining subsections regularize against. The portfolio covariance structure (Section 3.4) is, in the current implementation, a flat single-factor placeholder tied to the national generic ballot rather than the fully structural factor loading $\beta_i=\varphi(\mu_i/\sigma_i)\alpha_3/\sigma_i$ derived in Appendix B.6 -- every reported $\text{Var}[\text{Seats}]$ and risk-penalty figure in this paper uses the placeholder, not the structural derivation, and a genuine multi-factor risk model (incorporating regional or urbanicity-based factors beyond the single national ballot) remains a direction for future estimation work. The $\sigma_i$ model's own internal ordering diagnostic -- the expectation that open-seat uncertainty exceeds challenger uncertainty, which in turn exceeds incumbent uncertainty -- fails under the corrected specification in every tested partisan-lean bin, an open question not resolved in this paper (Appendix D). Finally, $\sigma_i$ itself is a generated regressor: its own estimation uncertainty is not propagated into downstream MSG and optimizer quantities, a standard two-stage-estimation limitation present throughout the pipeline.

## Computational

The nonlinear objective, once the persuasion ceiling is applied, is smooth but not globally guaranteed concave; SLSQP is a local solver, and while the optimizer's initialization at a feasible, budget-respecting point near the observed allocation (Section 7.2) makes convergence to a spurious local optimum unlikely in practice -- confirmed by the finite-difference gradient validation of Section 8.1 and by convergence diagnostics (`result.success`) across every reported run -- no formal global-optimality certificate is established. At the current problem scale ($N\approx433$ races), computation time is not a binding constraint (Section 7.3); a much larger allocation problem (e.g., allocating simultaneously across House, Senate, and state-legislative races) would require revisiting the $O(N^2)$ covariance term's scaling.

## Practical Deployment

Several gaps separate this framework from an operational, real-time deployment tool. FEC disbursement reporting occurs on a quarterly cadence with disclosure lags, so any live application necessarily operates on stale spending data relative to a committee's actual, more current internal ledger. The framework as specified here is a single-period, static optimization: it does not account for the sequential nature of real campaign budgeting, in which capital is committed irreversibly over time as new information arrives -- an extension developed in a companion paper on dynamic allocation under commitment constraints. Finally, the framework's recommendations are not self-executing: translating a model-recommended reallocation into an actual media buy or field investment requires human decision-making, operational lead time, and judgment about factors (candidate scandal risk, local coalition dynamics, opponent behavior beyond the reduced-form adversarial-response term $\eta$) the model does not observe.

\newpage

# Conclusion

Political campaigns operate under severe budget constraints and substantial electoral uncertainty, yet the committees allocating hundreds of millions of dollars per cycle do so largely without an explicit model of the marginal return on the next dollar. This paper reframes that decision as a constrained capital-allocation problem, developing a complete pipeline from causally identified spending elasticities through a nonlinear margin-to-probability conversion and a portfolio-level risk model to a constrained optimizer. In doing so it identifies a genuine mathematical property of the natural specification of that pipeline -- marginal seat gain is finite everywhere, including as a race's own spending approaches zero, but non-monotonic, with a finite interior peak that can land at an implausible value if a race's real spending floor happens to sit nearby. We derive this behavior formally, show it is a finite-sample extrapolation risk rather than an asymptotic divergence, state the design requirements a correction must satisfy, and supply one -- an endogenous, bounded, differentiable persuasion ceiling calibrated by transparent sensitivity analysis rather than fixed by assumption.

Applied to public FEC and election data, the evidence does not show that the DCCC systematically identified the wrong races at the outset: a test correlating observed spending against each race's pre-allocation marginal potential returns a null result in both the 2024 primary sample and a fully out-of-sample 2022 replication. It does show that the DCCC's final allocation leaves substantial, replicated differences in marginal return across races receiving discretionary funding -- a direct violation of the paper's own derived condition for a risk-neutral efficient allocation, with a 90th-to-10th-percentile MSG ratio near 20--26-to-1 among funded races in both cycles, against near-exact equalization in the model-optimal allocation. Decomposing the resulting model-implied gain (+2.83 seats in 2024, +3.22 in 2022) shows it is dominated (83--91%) by funding races that received no party money at all, not by resizing amounts among races already funded -- indicating incomplete engagement with plausible opportunities, or constraints on selection not represented in the model, rather than poor calibration of amounts within an already-chosen portfolio.

The paper's contribution is therefore threefold. Mathematically, it derives the true limiting behavior of a marginal-return function built on a log-ratio spending specification, corrects an initially incorrect characterization of that behavior as an unbounded singularity, and supplies an endogenous regularizer suited to the actual (finite-peak, extrapolation-risk) problem this creates -- a solution that generalizes beyond campaign finance to any capital-allocation setting sharing this structure. Methodologically, it develops a direct test of an optimization model's own KKT stationarity condition as an efficiency diagnostic, in place of a spending-versus-marginal-return correlation that is mechanically confounded by diminishing returns, and a decomposition separating gains attributable to which opportunities are engaged from gains attributable to how intensely they are funded. Empirically, it provides campaign committees and researchers a fully reproducible, publicly replicable framework for asking, and answering, a narrower and more defensible question than the paper originally posed: not whether a committee chose the wrong races, but whether its final spending levels are consistent with equalized marginal returns, and how much of any available improvement comes from re-engaging currently-unfunded opportunities versus resizing existing ones. The immediate research agenda this leaves open is to identify which of the candidate mechanisms in Section 9.1 -- capacity constraints, information timing, or strategic considerations outside the model -- actually accounts for the selection gap, a question the public data underlying this framework cannot resolve on its own.

\newpage

# Data Availability

All data used in this paper are drawn from public sources: FEC bulk candidate-committee files and Schedule E/F filings (fec.gov), MIT Election Data and Science Lab House results (electionlab.mit.edu), Daily Kos Elections district crosswalks, Cook Political Report PVI values, Census ACS5 CVAP estimates, and historical generic-ballot polling averages. No proprietary or restricted-access data are used. A processed-data replication package, including the assembled 2012--2024 panel and all intermediate estimation artifacts (Appendix H), is available in the project repository's `data/processed/` directory.

# Code Availability

The complete estimation, calibration, and optimization pipeline is available at:

**Repository:** `https://github.com/callum-doty/political-portfolio`
**Commit:** `78c524e6f1f8e3b569512b2e80677a9ba4693549`
**Entry point:** `scripts/run_backtest.py` (primary pipeline, including the KKT dispersion, boundary, floor-baseline, and pairwise-transfer diagnostics of Section 8); `scripts/run_estimation.py` (parameter estimation stage)
**Bibliography:** `references.bib` (machine-readable BibTeX for every citation in this paper)
**Environment:** Python 3.13.1; NumPy 2.2.1; SciPy 1.17.1; pandas 2.2.3; statsmodels 0.14.6; cvxpy 1.9.2 (full pinned environment in Appendix K / `requirements.txt`)

# Conflict of Interest

The authors declare no conflict of interest. This research was not funded by, and the authors hold no financial relationship with, any political campaign, party committee, or campaign consulting firm.

\newpage

# References

Ansolabehere, S., de Figueiredo, J. M., and Snyder, J. M. (2003). Why is there so little money in U.S. politics? *Journal of Economic Perspectives*, 17(1), 105--130.

Ansolabehere, S., and Snyder, J. M. (2002). The incumbency advantage in U.S. elections: An analysis of state and federal offices, 1942--2000. *Election Law Journal*, 1(3), 315--338.

Bellman, R. (1957). *Dynamic Programming*. Princeton University Press.

Boyd, S., and Vandenberghe, L. (2004). *Convex Optimization*. Cambridge University Press.

Dantzig, G. B. (1963). *Linear Programming and Extensions*. Princeton University Press.

Duan, N. (1983). Smearing estimate: A nonparametric retransformation method. *Journal of the American Statistical Association*, 78(383), 605--610.

Erikson, R. S., and Palfrey, T. R. (2000). Equilibrium in campaign spending games. *American Political Science Review*, 94(3), 595--609.

Gelman, A., and King, G. (1993). Why are American Presidential election campaign polls so variable when votes are so predictable? *British Journal of Political Science*, 23(4), 409--451.

Gerber, A. (1998). Estimating the effect of campaign spending on Senate election outcomes using instrumental variables. *American Political Science Review*, 92(2), 401--411.

Green, D. P., and Gerber, A. S. (2008). *Get Out the Vote: How to Increase Voter Turnout*. Brookings Institution Press.

Ibaraki, T., and Katoh, N. (1988). *Resource Allocation Problems: Algorithmic Approaches*. MIT Press.

Jacobson, G. C. (1978). The effects of campaign spending in congressional elections. *American Political Science Review*, 72(2), 469--491.

Jacobson, G. C. (1990). The effects of campaign spending in House elections: New evidence for old arguments. *American Journal of Political Science*, 34(2), 334--362.

Levitt, S. D. (1994). Using repeat challengers to estimate the effect of campaign spending on election outcomes in the U.S. House. *Journal of Political Economy*, 102(4), 777--798.

Markowitz, H. (1952). Portfolio selection. *The Journal of Finance*, 7(1), 77--91.

Montgomery, J. M., Hollenbach, F. M., and Ward, M. D. (2012). Ensemble predictions of the 2012 US presidential election. *PS: Political Science \& Politics*, 45(4), 651--654.

Oster, E. (2019). Unobservable selection and coefficient stability: Theory and evidence. *Journal of Business and Economic Statistics*, 37(2), 187--204.

Sharpe, W. F. (1964). Capital asset prices: A theory of market equilibrium under conditions of risk. *The Journal of Finance*, 19(3), 425--442.

Sides, J., Vavreck, L., and Warshaw, C. (2022). The Bitter End: The 2020 Presidential Campaign and the Challenge to American Democracy. Princeton University Press.

Stratmann, T. (2005). Some talk: Money in politics. A (partial) review of the literature. *Public Choice*, 124(1--2), 135--156.

Machine-readable BibTeX entries for every reference above are provided as `references.bib` in the replication repository (Code Availability).


\newpage

# Appendix A: Notation Reference Table

See Table 1 (Section 3.1) for the complete symbol reference used throughout the paper. Additional notation introduced in the appendices: $y^*_{it}$ (offset-regressed outcome, Appendix B.1); $\alpha_i$ (repeat-challenger pair fixed effect, Appendix B.2); $\nu_i,\mu_i^{KKT}$ (KKT multipliers on upper/lower bound constraints, Appendix C, not to be confused with the margin $\mu_i$ of the main text -- the KKT lower-bound multiplier is written $\underline\nu_i$ below to avoid collision).

# Appendix B: Detailed Mathematical Derivations

## B.1 OLS via Offset Regression

The margin model constrains $\beta_1$ to its externally identified repeat-challenger value rather than estimating it jointly with the remaining coefficients. Writing the full model as $y_{it} = \mathbf x_{it}'\boldsymbol\theta + \hat\beta_1\log(\text{ratio})_{it} + \varepsilon_{it}$ with $\hat\beta_1$ fixed, define the offset outcome

$$y^*_{it} \equiv y_{it} - \hat\beta_1\log(\text{ratio})_{it} = \mathbf x_{it}'\boldsymbol\theta + \varepsilon_{it}$$

Minimizing $\sum_{it}(y^*_{it} - \mathbf x_{it}'\boldsymbol\theta)^2$ over $\boldsymbol\theta$ alone is ordinary least squares: $\hat{\boldsymbol\theta} = (X'X)^{-1}X'y^*$, with HC3 robust covariance $\widehat{\text{Var}}(\hat{\boldsymbol\theta}) = (X'X)^{-1}X'\hat\Omega X(X'X)^{-1}$, $\hat\Omega = \text{diag}\big(\hat\varepsilon_i^2/(1-h_{ii})^2\big)$, where $h_{ii}$ is the $i$-th leverage (diagonal of the hat matrix). This is the estimator applied to recover $\alpha_0$--$\alpha_3$, $\beta_2$, $\beta_3$ in Section 6.1.

## B.2 Repeat-Challenger First-Differencing

With a race-pair fixed effect $\alpha_i$ absorbing every time-invariant matchup characteristic: $\text{Margin}_{it} = \alpha_i + \beta_{RC}\log(\text{ratio})_{it} + \eta_{it}$. Differencing across a pair's two observed cycles cancels $\alpha_i$ exactly, since it is constant within the pair:

$$\Delta\text{Margin}_i = \beta_{RC}\,\Delta\log(\text{ratio})_i + \Delta\eta_i \quad\Longrightarrow\quad \hat\beta_{RC} = \frac{\sum_i \Delta\log(\text{ratio})_i\,\Delta\text{Margin}_i}{\sum_i \big(\Delta\log(\text{ratio})_i\big)^2}$$

the ordinary least-squares slope of a no-intercept regression of $\Delta\text{Margin}_i$ on $\Delta\log(\text{ratio})_i$. This estimator is mechanically valid regardless of context; that it recovers a *causal* effect additionally requires $\text{Cov}\big(\Delta\log(\text{ratio})_i,\Delta\eta_i\big)=0$ conditional on the national environment -- an identifying assumption, not a derived result (Section 6.3).

## B.3 Bayesian Shrinkage Posterior

With prior $\beta_{OS}\sim N(\beta_{RC},\tau^2)$ and likelihood $\beta_{OS}^{\text{panel}}\mid\beta_{OS}\sim N(\beta_{OS},\sigma_{\text{panel}}^2)$, the log-posterior is, up to an additive constant,

$$-\frac{(\beta_{OS}-\beta_{RC})^2}{2\tau^2} - \frac{(\beta_{OS}^{\text{panel}}-\beta_{OS})^2}{2\sigma_{\text{panel}}^2}$$

Differentiating with respect to $\beta_{OS}$ and setting the result to zero:

$$-\frac{\beta_{OS}-\beta_{RC}}{\tau^2} + \frac{\beta_{OS}^{\text{panel}}-\beta_{OS}}{\sigma_{\text{panel}}^2} = 0 \;\Longrightarrow\; \hat\beta_{OS} = \frac{\beta_{RC}/\tau^2 + \beta_{OS}^{\text{panel}}/\sigma_{\text{panel}}^2}{1/\tau^2+1/\sigma_{\text{panel}}^2}, \quad \text{Var}(\hat\beta_{OS}) = \left(\frac1{\tau^2}+\frac1{\sigma_{\text{panel}}^2}\right)^{-1}$$

the standard precision-weighted conjugate-normal posterior mean, exact given the normality assumption. The shrinkage weight on the panel term is $\kappa = (1/\sigma_{\text{panel}}^2)/(1/\tau^2+1/\sigma_{\text{panel}}^2)$.

## B.4 The MSG Chain Rule (full expansion)

Restated from Section 4.3 with every intermediate step shown. With $\text{ratio}_i = D_i/T_i$, $T_i=D_i+R_i$, quotient-rule differentiation with respect to $D_i$ (treating $R_i$ as fixed, since $x_i$ enters only through $D_i$):

$$\frac{\partial\,\text{ratio}_i}{\partial D_i} = \frac{T_i\cdot 1 - D_i\cdot 1}{T_i^2} = \frac{T_i-D_i}{T_i^2} = \frac{R_i}{T_i^2}$$

Then, using $\partial \log(u)/\partial D_i = (1/u)\cdot\partial u/\partial D_i$ with $u=\text{ratio}_i$:

$$\frac{\partial\log(\text{ratio}_i)}{\partial D_i} = \frac{T_i}{D_i}\cdot\frac{R_i}{T_i^2} = \frac{R_i}{D_i T_i}$$

Since $\mu_i = (\text{const}) + c_i\log(\text{ratio}_i)$ and $P_i=\Phi(\mu_i/\sigma_i)$, the chain rule gives $\partial P_i/\partial\mu_i = \varphi(\mu_i/\sigma_i)/\sigma_i$, and composing:

$$\text{MSG}_i = \frac{\partial P_i}{\partial D_i} = \frac{\partial P_i}{\partial \mu_i}\cdot\frac{\partial \mu_i}{\partial D_i} = \varphi\!\left(\frac{\mu_i}{\sigma_i}\right)\cdot\frac1{\sigma_i}\cdot c_i\cdot\frac{R_i}{D_iT_i}$$

matching Section 4.3's boxed result, since $\partial D_i/\partial x_i = 1$.

## B.5 The $\sigma_i$ Retransformation

$\sigma_i$ is fitted on a log scale: $\log|\text{residual}_i| = \mathbf z_i'\boldsymbol\delta + u_i$. Exponentiating the fitted value alone, $\exp(\mathbf z_i'\hat{\boldsymbol\delta})$, recovers the conditional *median* of $|\text{residual}_i|$ under log-normal $u_i$, not its mean, understating $\sigma_i$ systematically. Duan's (1983) smearing correction multiplies by the empirical mean of $\exp(\hat u_i)$ over the estimation sample, $\widehat{\text{smear}} = \frac1n\sum_i\exp(\hat u_i)$, giving the (still nonparametric, distribution-free) mean-unbiased retransformation $\hat\sigma_i = \widehat{\text{smear}}\times\exp(\mathbf z_i'\hat{\boldsymbol\delta})$, used throughout Section 6.2.

## B.6 Portfolio Factor Loading (structural derivative)

Differentiating $P(\text{win}_i)=\Phi(\mu_i/\sigma_i)$ with respect to the generic ballot $G$, and using $\partial\mu_i/\partial G=\alpha_3$ from the margin specification (Section 4.2):

$$\beta_i \equiv \frac{\partial P(\text{win}_i)}{\partial G} = \varphi\!\left(\frac{\mu_i}{\sigma_i}\right)\cdot\frac{\alpha_3}{\sigma_i}, \qquad \text{Cov}(Y_i,Y_j) = \beta_i\beta_j\sigma_G^2$$

This structural loading is maximized for races near parity ($\mu_i\approx0$) and vanishes for safe seats -- the districts most attractive to the optimizer on MSG grounds are mechanically also the highest-systematic-risk districts under this derivation, the central tension a risk-adjusted ($\gamma>0$) solve must resolve. As noted in Section 10.2, the current implementation uses a single-factor placeholder rather than this fully structural loading; the derivation is retained as the target specification for future estimation work.

# Appendix C: Proofs

## C.1 KKT Stationarity Conditions

For the optimization problem of Section 3.5, $\max_{\mathbf x}\sum_iP_i(x_i) - \gamma\,\mathbf 1'\Sigma(\mathbf x)\mathbf 1$ subject to $\sum_ix_i\le B$ and $0\le x_i\le\kappa B$, form the Lagrangian with multiplier $\lambda\ge0$ on the budget constraint and $\underline\nu_i,\overline\nu_i\ge0$ on the lower and upper bounds:

$$\mathcal L = \sum_iP_i(x_i) - \gamma\,\mathbf 1'\Sigma(\mathbf x)\mathbf 1 - \lambda\Big(\sum_ix_i - B\Big) + \sum_i\underline\nu_i x_i - \sum_i\overline\nu_i(x_i-\kappa B)$$

Stationarity requires $\partial\mathcal L/\partial x_i = 0$ for every $i$. Writing $\partial\big[\mathbf 1'\Sigma(\mathbf x)\mathbf 1\big]/\partial x_i \equiv V_i(\mathbf x)$ for the (generally allocation-dependent) marginal risk contribution of race $i$:

$$\text{MSG}_i - \gamma\,V_i(\mathbf x) - \lambda + \underline\nu_i - \overline\nu_i = 0$$

Complementary slackness ($\underline\nu_ix_i=0$, $\overline\nu_i(x_i-\kappa B)=0$) implies that for any race funded strictly between its bounds ($0<x_i<\kappa B$), both multipliers vanish and stationarity reduces to

$$\text{MSG}_i - \gamma\, V_i(\mathbf x) = \lambda \qquad\text{for all interior-funded races}$$

i.e., risk-adjusted marginal seat gain is equalized across every race not pinned at a boundary, with $\lambda$ interpretable as the shadow price of the budget constraint. In the risk-neutral case $\gamma=0$ used throughout Section 8, this reduces to $\text{MSG}_i=\lambda$ for all interior-funded races regardless of $V_i(\mathbf x)$'s exact form -- the object Table 4's dispersion test evaluates directly. Races pinned at their floor ($x_i=0$) or cap ($x_i=\kappa B$) satisfy the stationarity condition with a nonzero multiplier instead: at $x_i=0$, $\underline\nu_i=\lambda+\gamma V_i-\text{MSG}_i\ge0 \iff \text{MSG}_i\le\lambda+\gamma V_i$, and symmetrically $\text{MSG}_i\ge\lambda+\gamma V_i$ at $x_i=\kappa B$ -- the boundary inequalities Section 8.2's boundary test evaluates (at $\gamma=0$). This also motivates the `n_corner_solutions` diagnostic tracked in the optimizer implementation (Section 7.2, Algorithm 1, step 7).

## C.2 Proof That the Efficiency Test Is Risk-Tolerance-Robust (Section 3.4 claim)

**Claim.** *Among races matched on factor loading $\beta_i$ (equivalently, matched on Cook category and partisan lean, per Appendix B.6's derivation that $\beta_i$ is itself a function of $\mu_i,\sigma_i$), the risk-adjustment term $\gamma\, V_i(\mathbf x)$ in the interior stationarity condition (Appendix C.1) is approximately constant across the matched group, for any fixed but unobserved $\gamma$.*

*Sketch.* Under the structural loading of Appendix B.6, $\Sigma_{ij}(\mathbf x) = \beta_i(x_i)\beta_j(x_j)\sigma_G^2$ for $i\ne j$, so $V_i(\mathbf x) = \partial\big[\mathbf 1'\Sigma(\mathbf x)\mathbf 1\big]/\partial x_i$ is, to leading order, proportional to race $i$'s own loading $\beta_i(x_i)$ times a portfolio-wide scalar common to every race ($2\sigma_G^2\sum_j\beta_j(x_j)$, plus the idiosyncratic-variance term's own derivative). Within a group matched on $\beta_i$, this term varies only through the (small, second-order) variation in $\beta_i$ that survives the matching criterion, so $\gamma\,V_i(\mathbf x)$ is approximately a constant offset within the group for *any* value of $\gamma$, including an unobserved one. The interior stationarity condition therefore reduces, within the matched group, to approximate equalization of raw $\text{MSG}_i$ alone -- which is exactly the quantity Section 8.2's KKT dispersion test evaluates directly (and, within a Cook-category/PVI-matched subgroup, what the superseded correlation test of Section 8.7 was originally intended to approximate) -- making this conclusion robust to $\gamma$ rather than dependent on knowing the committee's true risk tolerance. $\blacksquare$

# Appendix D: Additional Robustness Analyses

## D.1 Winsorization Detail

**Table D.1: Winsorization robustness of Spearman $\rho$ (methodological demonstration; see Section 8.8 caveat -- predates the final gradient specification)**

| Cycle | $n$ | untrimmed | wins. 10/90 | wins. 5/95 | wins. 1/99 |
|---|---|---|---|---|---|
| 2024 | 53 | $-0.582$ | $-0.594$ | $-0.592$ | $-0.583$ |
| 2022 | 61 | $-0.750$ | $-0.757$ | $-0.753$ | $-0.750$ |

Both cycles were stable under winsorization at every trim level tested on the pipeline specification current when this check was run, differing from the untrimmed value by no more than 0.01. As noted in Section 8.8, this check has not been re-executed against the final, fully corrected specification (Table 7) and should be re-verified before being cited as current.

## D.2 Matched-Group Efficiency Test (superseded pipeline snapshot)

Within races matched on Cook category (Lean D, Toss-Up) and partisan lean (within $\pm5$ PVI points, Section 3.3), an earlier pipeline pass found $n=44$, $\rho=-0.559$ ($p=0.0001$). This is an ad hoc subsample statistic not part of the standard pipeline output and, like Appendix D.1, has not been recomputed against the final specification; it is retained here as a historical data point rather than a currently verified figure, and shares the same diminishing-returns confound as the superseded correlation test of Section 8.8 more broadly. The Cook-category decomposition of Table 8 and the KKT dispersion test of Table 4 (both current, final specification) are the recommended references going forward.

## D.3 $\sigma_i$ Ordering Anomaly (open question)

The $\sigma_i$ model's internal ordering diagnostic expects $\sigma_i^{\text{open}} > \sigma_i^{\text{challenger}} > \sigma_i^{\text{incumbent}}$ at matched \|PVI\| -- wider uncertainty for open seats than incumbent-challenger races, reflecting the absence of an incumbent's brand/history anchor. Under the corrected specification (Section 6.2), this ordering fails in every tested PVI bin: incumbent-race $\sigma_i$ reads as the *highest*, not the lowest, of the three categories. Two explanations are both plausible and neither is resolved in this paper: the pre-correction ordering may have been an artifact of a since-fixed bug in how open-seat residuals were computed (inflating their apparent dispersion for an unrelated reason), or the corrected residuals may be revealing a genuine omitted-variable gap in the open-seat specification. This does not affect $\beta_1^{OS}$ or the Bayesian shrinkage procedure (Appendix B.3), which are independent of $\sigma_i$, but it does mean the volatility-shift mechanism motivating the open-seat discussion in Section 9 should be read as illustrative of the general mechanism rather than as a claim about the current fitted $\sigma_i$ values specifically.

# Appendix E: Sensitivity Analyses

## E.1 Persuasion Ceiling $C_{\max}$ Sweep

**Table E.1: Party-budget share by Cook tier and total expected seats across the $C_{\max}$ sweep**

| $C_{\max}$ (pp) | 3 | 5 | 7 | 10 | 15 | 20 | 30 |
|---|---|---|---|---|---|---|---|
| Safe-tier share | 6.9\% | 7.4\% | 8.0\% | **9.0\%** | 10.3\% | 11.2\% | 12.6\% |
| Competitive-tier share | 63.3\% | 62.5\% | 61.4\% | **60.0\%** | 58.3\% | 57.0\% | 55.2\% |
| Likely-tier share | 29.8\% | 30.1\% | 30.6\% | **31.0\%** | 31.5\% | 31.8\% | 32.2\% |
| Expected seats | 215.10 | 216.24 | 217.06 | **217.94** | 218.94 | 219.63 | 220.57 |

Every quantity moves smoothly and monotonically across the tested range, with no discontinuity or fragile threshold. There is no sharply defined local optimum in this table by any single criterion -- Safe-tier share is minimized at the smallest tested $C_{\max}$ and expected seats is maximized at the largest -- so $C_{\max}=10.0$ (bold column) is a moderate choice balancing a Safe-tier share held under 10% against retaining a majority of the party budget in the Competitive tier, not a value selected because the data exhibit a distinct peak there. The pre-ceiling uncapped baseline (Section 4.4's corollary) allocated 45% of the party budget to Safe-tier races, well outside this entire tested range. The full numeric series underlying this table is in `outputs/.persuasion_ceiling_sweep_cache.npz` and plotted in Figure 1.

## E.2 Budget Concentration Cap ($\kappa$) Sweep

Per Section 8.6, $\kappa\in\{0.05,0.10,0.15\}$ is swept; the reported main results use $\kappa=0.15$, the pipeline's baseline regime. The sign and significance of the efficiency tests are unaffected across this range.

## E.3 Risk-Aversion ($\gamma$) Grid

`config.yaml`'s `optimizer.gamma_values` specifies a risk-neutral baseline ($\gamma=0$, the value used throughout Section 8) plus two risk-averse calibration points, set post-estimation so that one standard deviation of portfolio seat-count variance costs 0.5 and 1.0 expected seats respectively -- a QP-solved risk-return frontier complementary to, but not the primary focus of, the risk-neutral efficiency test reported in this paper.

# Appendix F: Hyperparameters

**Table F.1: Key Configuration Parameters (`config.yaml`)**

| Parameter | Value | Section |
|---|---|---|
| `universe.min_total_spend` | \$100,000 | 5.4 |
| `universe.exclude_states` | [AK] | 5.4 |
| `panel.cycles` | [2012, 2014, 2016, 2018, 2020, 2022] | 5.2 |
| `panel.min_repeat_challenger_pairs` | 40 | 6.1 |
| `uncertainty.n_draws` | 1,000 | 6.5 |
| `uncertainty.credible_interval` | 0.83 | -- |
| `uncertainty.beta_rc_bootstrap_draws` | 1,000 | 6.5 |
| `uncertainty.permutation_draws` | 2,000 | 8.2, 8.5 |
| `optimizer.gamma_values` | [0.0, mid, high] | Appendix E.3 |
| `optimizer.cap_regimes` | [0.05, 0.10, 0.15] | 3.3, 8.4 |
| `persuasion_ceiling.c_max` | 10.0 | 6.4 |
| `validation.margin_model_r2_pass` | 0.40 | -- |
| `validation.brier_tolerance` | 0.05 | -- |
| Random seed (bootstrap, permutation) | 42 | 7.4 |

# Appendix G: Pseudocode

## G.1 Bayesian Shrinkage Calibration (complement to Algorithm 1)

\footnotesize
```
Input:  beta_RC, se_RC (repeat-challenger prior mean and SE),
        panel (full 2012-2022 observational panel)
Output: beta_OS_calib, beta_OS_lower_bound

1.  Fit interaction specification on panel:
      Margin ~ controls + beta_panel * log(ratio)
               + delta * log(ratio) * OpenSeat
2.  beta_OS_panel <- beta_panel + delta   [full panel open-seat estimate]
3.  tau <- f(covariate_overlap(repeat_challenger_sample,
             open_seat_population))
      [wider tau for less-overlapping populations; Section 6.3]
4.  kappa <- (1/sigma_panel^2) / (1/tau^2 + 1/sigma_panel^2)
5.  beta_OS_calib <- kappa * beta_OS_panel + (1-kappa) * beta_RC
6.  beta_OS_lower_bound <- oster_bound(beta_OS_calib, delta=1)
      [Oster 2019]
7.  Return beta_OS_calib, beta_OS_lower_bound
```
\normalsize

## G.2 Selection-versus-Intensity Gain Decomposition (Section 8.4)

\footnotesize
```
Input:  races, coef, sigma_model, budget, cov_matrix, party_budget,
        cap_fraction, outputs (MSG at DCCC's observed allocation)
Output: intensity_gain, selection_gain, total_gain

1.  full_result <- optimize_nonlinear(races, ..., fixed_zero_mask=None)
      [unconstrained: may fund any race, Algorithm 1]
2.  zero_mask_i <- (d_total_i - cand_floor_i) <= tol   for each race i
      [races DCCC funded at (approximately) zero party dollars]
3.  constrained_result <- optimize_nonlinear(races, ...,
      fixed_zero_mask=zero_mask)
      [bounds forced to (0,0) for every zero_mask race; Section 7.1]
4.  dccc_seats     <- sum(o.p_win for o in outputs)
5.  intensity_gain <- constrained_result.expected_seats - dccc_seats
6.  selection_gain <- full_result.expected_seats
                       - constrained_result.expected_seats
7.  total_gain     <- full_result.expected_seats - dccc_seats
      [= intensity_gain + selection_gain, by construction]
8.  Return intensity_gain, selection_gain, total_gain
```
\normalsize

# Appendix H: Database Schema

**Table H.1: Key Processed Model Artifacts (`data/processed/`)**

| File | Contents | Produced by |
|---|---|---|
| `margin_model_coef.json` | $\alpha_0$--$\alpha_5$, $\beta_1$--$\beta_3$, $\beta_1^{OS}$, $R^2$ | `estimation/margin.py` |
| `beta_rc.json` | $\hat\beta_{RC}$, SE, $n$ pairs | `estimation/beta_rc.py` |
| `beta_rc_bootstrap.json` | 1,000-draw bootstrap distribution | `scripts/run_estimation.py` |
| `open_seat_calibration.json` | $\beta_{RC}$, $\beta_{OS}^{\text{panel}}$, $\tau$, $\kappa$, $\hat\beta_{OS}$, $\beta_{OS}^{lb}$ | `estimation/open_seat.py` |
| `sigma_model.json` | $\sigma_i$ model coefficients, smearing factor | `estimation/sigma.py` |

**Table H.2: Runtime Output Artifacts (`outputs/`)**

| File | Contents |
|---|---|
| `efficiency_tests_redesigned.json` / `_2022.json` | KKT dispersion, boundary, floor-baseline, transfer, decomposition (Tables 4, 5, 7) |
| `permutation_tests.json` / `_2022.json` | Full permutation-test null distributions and observed statistics (Section 8.8) |
| `allocator_comparison_table.csv` / `_2022.csv` | Table 6 source data |
| `spearman_by_cook_category.csv` / `_2022.csv` | Table 8 source data |
| `.persuasion_ceiling_sweep_cache.npz` | Table E.1 / Figure 1 sweep results |
| `beta_rc_bootstrap_distribution.csv` | Figure 2 source data |

# Appendix I: Additional Figures

![Model-optimal party spending by race, ranked, 2024 cycle.](figures/allocator_spending_by_race.png){width=85%}

![DCCC spending share by Cook rating category, 2024 cycle.](figures/spending_by_cook.png){width=75%}

# Appendix J: Additional Tables

**Table J.1: Allocation-Efficiency Permutation Test Detail**

| Cycle | DCCC $\mathbb E[\text{Seats}]$ | \% shuffles $\ge$ DCCC | Null mean (95\% CI) | Model $\mathbb E[\text{Seats}]$ | \% shuffles $\ge$ Model |
|---|---|---|---|---|---|
| 2024 | 215.12 | 2.9\% | 214.84 [214.55, 215.12] | 217.94 | 0.0\% |
| 2022 | 213.37 | 19.2\% | 213.27 [213.03, 213.50] | 216.59 | 0.0\% |

# Appendix K: Configuration Files

Relevant excerpt of `config.yaml` (full file in the code repository, Section "Code Availability"):

```yaml
universe:
  min_total_spend: 100_000
  exclude_states: ["AK"]
  competitive_ratings: ["Toss-Up", "Lean D", "Lean R"]

panel:
  cycles: [2012, 2014, 2016, 2018, 2020, 2022]
  min_repeat_challenger_pairs: 40

uncertainty:
  n_draws: 1000
  credible_interval: 0.83
  beta_rc_bootstrap_draws: 1000
  permutation_draws: 2000

optimizer:
  # gamma_values[1:] are intentionally null in this file: the mid/high
  # risk-aversion levels are calibrated at runtime from the risk-neutral
  # solve's own portfolio variance (Section 6.6/Appendix E.3), not fixed
  # in advance, so they cannot be literal constants here.
  gamma_values: [0.0, null, null]
  cap_regimes: [0.05, 0.10, 0.15]
  min_allocation: 0.0

persuasion_ceiling:
  c_max: 10.0

validation:
  spending_completeness_min: 0.80
  margin_model_r2_pass: 0.40
  margin_model_r2_stretch: 0.60
  brier_tolerance: 0.05
```

# Appendix L: Reproducibility Checklist

- [x] All data sources are public and cited (Section 5.1)
- [x] Complete estimation code is version-controlled and publicly available (Code Availability)
- [x] Random seeds are fixed for all stochastic procedures (bootstrap, permutation; seed 42)
- [x] Configuration parameters are centralized in a single file, not hard-coded (Appendix F, K)
- [x] Primary KKT dispersion result is computed and reported for both cycles from the same pipeline run that produces every other headline figure (Section 8.2, `outputs/efficiency_tests_redesigned*.json`)
- [x] Primary result replicates out-of-sample on a non-overlapping estimation window (Section 8.7, Table 7)
- [x] Floor-baseline null result and boundary-violation counts are likewise computed identically in both cycles (Section 8.3, 8.7)
- [x] Analytic gradients are validated against finite-difference numerical derivatives (Section 8.1)
- [x] An automated test suite (341 tests, 19 files) covers the estimation and optimization pipeline (Section 8.1); all pass against the code producing the new diagnostics
- [x] Selection-versus-intensity gain decomposition is reproducible via `optimize_nonlinear(..., fixed_zero_mask=...)` (Section 8.4, Appendix G)
- [ ] Winsorization and matched-group robustness checks re-verified against the final specification (Appendix D.1--D.2; flagged as outstanding)
- [ ] $\sigma_i$ ordering anomaly resolved (Appendix D.3; flagged as open)
- [ ] Structural (non-placeholder) portfolio factor model estimated (Section 10.2, Appendix B.6; flagged as future work)
- [ ] Risk-averse ($\gamma>0$) solver's frozen-covariance approximation reconciled with the corrected $\text{Var}[\text{Seats}]=\mathbf 1'\Sigma(\mathbf x)\mathbf 1$ formula (Section 3.4's implementation note; flagged as future work)
