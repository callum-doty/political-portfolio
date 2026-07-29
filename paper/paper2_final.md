---
title: "An Operational Architecture for Sequential Campaign Spending Under Commitment Constraints"
subtitle: "Dynamic Political Capital Allocation for the 2026 U.S. House Elections"
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
  - \fancyhead[L]{\small\slshape An Operational Architecture for Sequential Campaign Spending}
  - \fancyhead[R]{\small\thepage}
  - \renewcommand{\headrulewidth}{0.3pt}
  - \usepackage[format=plain,labelfont=bf,font=small]{caption}
---

\begin{abstract}
\noindent
The companion paper to this one ("Paper I") develops a static valuation model for campaign spending -- one dollar's marginal contribution to expected seats, at one point in time, against one fixed budget -- and finds that observed committee spending is inconsistent with equalized marginal returns among funded races. Real committees do not allocate money once: they raise and commit capital continuously over a two-year cycle, observe new information on a rolling basis, and cannot recover money already spent. This paper takes Paper I's valuation model and optimizer as a fixed subroutine and asks a different question: how should a committee convert a static valuation model into a sequential decision system? We make four contributions. First, we extend the static marginal-seat-gain estimate to a time-indexed quantity that updates as new information arrives, via a stated (not derived) exponential-smoothing state-update rule, robust across the smoothing constants we test. Second, we formalize the split between a committee's already-committed, irreversible capital $L_t$ and its deployable capital $F_t = B_t - L_t$, and show the sequential allocation problem is Paper I's optimizer re-solved over $F_t$ at each reporting period -- a rolling static re-optimization under irreversible commitments, which we distinguish carefully from true model-predictive control, since our procedure plans no multi-period trajectory and prices no explicit cost of forgoing future flexibility within its own objective. Third, we introduce a research/operational mode distinction for the commitment ledger, since committed-but-undisbursed spending is not observable in public FEC data. Fourth, we identify -- without solving -- an asset this rolling procedure has no language for: capital retained rather than committed has option value, analogous to the early-exercise premium in American-style financial options, because retaining it preserves the ability to react to information that has not yet arrived. We state this formally and derive its qualitative implication under a fixed information-arrival process: shortening the remaining decision horizon can only weakly reduce the continuation value of waiting, so it should converge toward zero as Election Day approaches, though along any single realized path new information can cause the estimated value to rise before that final convergence. A one-step-ahead historical replay of the 2022 and 2024 cycles shows this rolling procedure recommends deploying capital far earlier than DCCC's actual, heavily back-loaded pacing -- DCCC does not reach even 25\% of its eventual cycle spending until roughly the final four weeks of a 38-period, ten-month cycle in both years, while the model recommends near-full deployment from the first period -- a pattern that is, by construction, close to a structural consequence of an objective with positive marginal returns and no reward for patience, and one we show is insensitive to the smoothing constant across the range we test. A cross-sectional association between this timing gap and race-level volatility is directionally consistent with an option-value account in a simple bivariate comparison, but does not survive the same sign once partisan lean and incumbency are controlled for, so we report it as suggestive rather than as confirmatory evidence. Applied to the live, in-progress 2026 cycle, the same architecture recommends deploying a majority of deployable capital into non-competitive seats at roughly three months from Election Day. This paper deliberately stops at naming and measuring the resulting gap; a companion paper takes the unsolved problem of pricing retained flexibility as its entire subject.
\end{abstract}

\vspace{0.5em}
\noindent\textbf{Keywords:} sequential decision-making, rollout policies, approximate dynamic programming, campaign finance, real options, capital budgeting, commitment constraints

\newpage

# Introduction

## Motivation

Paper I treats campaign spending as a one-shot capital-allocation problem: a fixed budget, a fixed set of estimated parameters, a single optimization solved once. Real congressional campaign committees do not operate this way. They raise money continuously over a two-year cycle; they commit money continuously, and irreversibly, the moment a television reservation is booked or a field office lease is signed; and they observe new information continuously -- a primary result, a fundraising quarter, a redistricting ruling, a candidate's health scare, a shift in the generic ballot -- each of which changes the estimated value of the next dollar in one or more races. A static allocation computed in March is not the allocation a static solve would recommend in September, even holding the underlying valuation model completely fixed. The practical question a sitting committee faces is not *where should the full-cycle budget have gone* but *given everything currently known, and given capital already irreversibly committed, how should the remaining, uncommitted budget be deployed right now?*

This is a sequential decision problem, and it is a different kind of problem than the one Paper I solves, not merely a repeated version of it. Answering it requires three things a one-shot optimization does not provide: a mechanism for updating race-level valuation estimates as information arrives; an explicit accounting of committed versus deployable capital, since a sequential optimizer must never be permitted to reallocate money that no longer exists to reallocate; and a recognition that deployable capital retained rather than spent has value beyond its face amount, because retaining it preserves the option to respond to information that has not yet arrived.

## Research Gap

It is tempting to assume a "dynamic" version of Paper I's problem is solved simply by re-running its optimizer at regular intervals: recompute the state, re-solve the static problem, repeat. Section 4 of this paper implements exactly that kind of rolling procedure, because it reuses Paper I's machinery without modification -- but it is important to be precise about what that procedure does and does not solve, since the gap between the two is this paper's reason for existing.

A static allocation problem takes a fixed budget and a fixed, known set of parameters and produces a single vector of numbers: a plan, solved once. A sequential allocation problem differs in two structural respects a repeated static solve does not, by itself, resolve. First, **decisions are irreversible and therefore path-dependent**: capital committed at period $t$ is permanently removed from the feasible set at every subsequent period, so the sequential problem's state depends on the entire history of prior decisions, not merely on newly observed information. Re-solving the static problem over deployable capital each period correctly respects this for the *constraint* -- it never reallocates money already committed -- but says nothing about whether the *sequence* of commitments that produced today's committed capital was itself a good sequence. Second, **the model's parameters are not fixed quantities to be estimated once, but stochastic processes that resolve over time**: the value a committee's model would assign to a race's expected margin in October is not knowable in March, and a March solve has no way to express -- let alone act on -- the fact that some races' estimates are far more likely to move materially than others.

Both points lead to the same conclusion: what a sequential decision problem actually calls for is not a single allocation vector but a *policy*, chosen with explicit regard for how today's decision constrains and interacts with tomorrow's -- the formal subject matter of dynamic programming and stochastic control. The rolling re-optimization procedure this paper develops is a myopic *approximation* to that object, not a solution to it, and we return explicitly to what that approximation leaves on the table rather than presenting it as more than it is.

## Overview of the Proposed Architecture

The architecture developed here has four moving parts. First, a campaign's state -- expected margins, uncertainty, cash position, spending to date -- is re-estimated at each reporting period rather than once, using a stated smoothing rule that prevents raw period-to-period polling noise from being fed directly into the optimizer. Second, total campaign budget is split into capital already irreversibly committed and capital still deployable; only the latter is ever a decision variable, and the split is tracked explicitly rather than assumed away. Third, at each reporting period, Paper I's unmodified optimizer is re-solved over deployable capital, with committed capital folded into each race's spending floor exactly as candidate-committee spending already is in Paper I. We are deliberately precise about naming this: it is a rolling static re-optimization under irreversible commitments, not full model-predictive control, since it plans no multi-period trajectory at each step and carries no internal model of how today's decision constrains tomorrow's beyond the capital-account bookkeeping itself. Fourth, and this is the paper's central conceptual contribution, we identify a structural blind spot this rolling procedure has no mechanism to correct: it implicitly assumes all currently deployable capital should be spent now, up to the period's constraints, with nothing rewarding the alternative of waiting. We formalize why waiting can have positive value -- an exact analogy to the early-exercise premium in American-style financial options -- derive its qualitative time-decay implication, and demonstrate empirically that the resulting gap between model and observed behavior is real and, by the structure of the objective itself, close to unsurprising -- without solving for the gap's exact price. A companion paper takes that unsolved pricing problem as its entire subject.

## Contributions

This paper makes four explicit contributions.

1. **Extends Paper I's static marginal seat gain to a time-indexed sequential quantity**, $\text{MSG}_i(t)$, updated at each reporting period via a stated exponential-smoothing state-update rule that is reproducible, explicitly flagged as an untested modeling choice rather than a derived one, and shown empirically not to drive the paper's headline results across the range of smoothing constants tested (Section 8.1).
2. **Formalizes the split between committed and deployable capital**, $B_t = L_t + F_t$, and introduces a research/operational mode distinction for estimating $L_t$: research mode approximates it from public commitment proxies (preserving Paper I's public-data-only reproducibility at the cost of approximation), while operational mode uses a committee's internal ledger directly (exact, but not a publicly reproducible research artifact).
3. **Shows the sequential allocation problem is Paper I's optimizer re-solved over deployable capital at each period, and states precisely what kind of procedure this is and is not.** It is a rolling static re-optimization under irreversible commitments, requiring no new solver, objective, or constraint structure; we distinguish it explicitly from true model-predictive control, which would plan a multi-period trajectory at each step, and from the full multi-period dynamic program it approximates only myopically.
4. **Identifies and formalizes, via a real-options analogy, an asset this rolling procedure has no language for**: capital retained rather than committed preserves option value. We derive the qualitative implication that, holding the information-arrival process fixed, a shorter remaining horizon cannot increase the value of waiting -- so it should converge toward zero as Election Day approaches -- and show the rolling procedure's blind spot to this has a measurable empirical signature: a one-step-ahead historical replay against the 2022 and 2024 cycles shows DCCC's actual spending is heavily back-loaded relative to what a patience-blind optimizer recommends, a pattern that is, by the objective's own construction, close to structural rather than a surprising discovery, and one we confirm is stable across alternative smoothing constants. A live 2026 application shows the same architecture recommending a majority of deployable capital toward non-competitive seats roughly three months from Election Day.

## Paper Roadmap

Section 2 relates this paper to the campaign finance, dynamic-programming, and real-options literatures and states what no existing work combines. Section 3 formalizes the sequential allocation problem: notation, decision variables, constraints, and the period-$t$ objective. Section 4 develops the theoretical core -- the campaign state vector, the committed/deployable capital split, the state-update operator, the rolling re-optimization procedure, the real-options analogy for uncommitted capital, and its time-decay implication. Section 5 describes the data this architecture consumes, beyond what Paper I already uses. Section 6 details calibration of the architecture's own parameters (the smoothing constant, the committed-capital estimator, the 2026 budget projection). Section 7 specifies the rolling re-optimization algorithm and computational environment. Section 8 reports empirical results: a historical one-step-ahead replay of the 2022 and 2024 cycles, and a live 2026 application. Section 9 discusses interpretation and generalizability. Section 10 states limitations. Section 11 concludes.

\newpage

# Related Literature

## Campaign Finance and Sequential Spending

Paper I situates this research program relative to the campaign finance literature's focus on average and marginal treatment effects; that discussion is not repeated here. The sequential dimension this paper adds is comparatively unstudied in that literature directly. Section 8.1 reports this paper's own directly-computed evidence that DCCC's actual spending is heavily back-loaded within a cycle; we rely on that internally-generated finding rather than an appeal to an uncited external "well-documented pattern," and offer it as a stylized fact this paper's architecture gives a candidate theoretical mechanism for, rather than a settled empirical regularity this paper merely cites.

## Dynamic Programming, Model Predictive Control, and Rollout Policies

The formal structure of re-solving a constrained optimization repeatedly as a system evolves is the subject matter of dynamic programming (Bellman 1957; Bertsekas 2017). Its engineering form, model predictive control, has a precise technical meaning worth stating exactly, because this paper's procedure does not meet it: MPC solves a finite-horizon optimization over a *trajectory* of future controls at each time step, using an explicit model of how the state evolves under each candidate control sequence, implements only the first-period control, and re-solves at the next step (Garcia, Prett, and Morari 1989; Rawlings, Mayne, and Diehl 2017). The trajectory-planning step is what lets true MPC price the consequence a present decision has for future feasible sets, even though it re-solves at every period.

**This paper's procedure (Section 4.4) does not do that.** At each reporting period, it solves Paper I's *single-period* static optimizer once, against that period's deployable capital, with no internal model of how today's allocation decision constrains or interacts with subsequent periods beyond the capital-account bookkeeping identity itself. This is more precisely described, in the terminology of approximate dynamic programming, as a **rollout policy**: a base heuristic (here, Paper I's one-shot optimizer) applied greedily at each stage of a sequential decision problem, using the true current state but no lookahead simulation of future stages (Bertsekas 2019; Powell 2011). Rollout policies are a standard and often effective way to obtain a tractable, implementable policy from a static optimizer without solving the full dynamic program -- and are known, precisely because they embed no explicit reward for preserving future flexibility, to be systematically biased toward whatever the base heuristic prefers when patience would in fact be optimal. That is exactly the diagnosis Sections 4.6--4.7 develop for this application, and exactly the terminology error this paper corrects relative to an earlier draft that described the same procedure as "receding-horizon" and "MPC-style": those terms imply a multi-period lookahead this procedure does not perform, and the front-loading result reported in Section 8.1 is, as a consequence, closer to a structural property of a rollout policy built on a patience-blind base heuristic than to a surprising empirical discovery.

The broader sequential-resource-allocation literature this connects to includes the multi-armed bandit and dynamic-allocation-index framework (Gittins 1979), which formalizes optimal sequential allocation of a scarce resource across competing, uncertain-return activities under exactly the kind of information-arrival structure this paper's campaign-spending problem exhibits, though without the irreversible-commitment feature central to Section 4.2 here.

## Real Options and Optimal Stopping

The value flexibility contributes to the present decision is precisely the subject of real-options theory (McDonald and Siegel 1986; Dixit and Pindyck 1994), which extends financial option-pricing logic to irreversible investment decisions under uncertainty: a firm holding the right, but not the obligation, to commit capital to a project should value that right using the same machinery that prices a financial option, because committing capital forecloses the ability to wait for better information in exactly the way exercising an option forecloses continued optionality. Longstaff and Schwartz (2001) develop the regression-based Monte Carlo method for pricing American-style options with early-exercise features -- simulating forward paths of the underlying state and estimating continuation values by regression, proceeding by backward induction -- that a companion paper applies directly to the campaign-capital-commitment problem this paper identifies but does not solve.

## Research Gap

No existing work combines a campaign-spending valuation model with an explicit sequential commitment architecture, correctly characterized as a rollout policy rather than full model-predictive control, and a real-options treatment of the value of not yet committing capital. The rollout, approximate-dynamic-programming, and real-options literatures supply the mathematical machinery and its precise limitations; they do not supply a calibrated political-spending application. The campaign finance literature supplies suggestive empirical regularities; it does not supply the theoretical mechanism this paper's architecture proposes for them. This paper's contribution is to build the architectural bridge between Paper I's valuation model and that machinery -- precisely enough to identify the missing asset and demonstrate its empirical cost, and precisely enough to name what kind of approximation the resulting policy actually is -- without itself solving the pricing problem, which requires specifying a state-transition law this paper deliberately leaves generic (Section 4.3) and a companion paper specifies and solves.

\newpage

# Problem Formulation

## Notation

Table 1 defines every symbol introduced by this paper beyond those already defined in Paper I (the spending response surface, $\mu_i$, $\sigma_i$, $\text{MSG}_i$, the persuasion ceiling, and the risk-neutral optimizer are all inherited unchanged and are not redefined here).

**Table 1: Additional Notation**

| Symbol | Meaning |
|---|---|
| $t$ | reporting period index |
| $\mathbf X_t$ | campaign state vector at period $t$ (Section 4.1) |
| $\mu_{i,t}, \sigma_{i,t}$ | smoothed, period-$t$ expected margin and uncertainty for race $i$ |
| $B_t$ | total campaign budget at period $t$ |
| $L_t$ ($L_{i,t}$) | capital already irreversibly committed, in total (per race $i$) |
| $F_t$ | deployable capital at period $t$, $F_t = B_t - L_t$ |
| $\text{party}_{i,t}$ | party dollars allocated to race $i$ at period $t$ (period-$t$ decision variable) |
| $f$ | state-transition operator, $\mathbf X_{t+1} = f(\mathbf X_t, \text{information}_t)$ |
| $\lambda$ | exponential-smoothing constant in the baseline state-update rule (Section 4.3) |
| $\Theta(t)$ | the value of waiting: $V_t^{\text{wait}} - V_t^{\text{deploy-now}}$ (defined but not solved here; Section 4.6, 4.7) |
| $T$ | Election Day |

## Decision Variables

At each reporting period $t$, the decision variable is the vector $\mathbf{\text{party}}_t = (\text{party}_{1,t},\dots,\text{party}_{N,t})$, party dollars allocated to each race for that period. Unlike Paper I's single, full-cycle decision, this vector is chosen repeatedly, once per reporting period, against a shrinking and constrained pool of remaining capital.

## Constraints

At period $t$, the allocation is subject to a deployable-capital budget constraint and the same per-race concentration cap Paper I uses:

$$\sum_{i=1}^N \text{party}_{i,t} \le F_t, \qquad 0 \le \text{party}_{i,t} \le \kappa F_t \quad \forall i$$

Each race's total spend at period $t$ is $D_{i,t} = \text{cand\_floor}_{i,t} + L_{i,t} + \text{party}_{i,t}$: the candidate-committee floor (as in Paper I), plus capital already committed to that specific race, plus the current period's party allocation. $L_{i,t}$ enters as a fixed floor, exactly as candidate-committee spending does in Paper I -- it is never itself a decision variable, since by definition it can no longer be reallocated.

## Objective Function

The period-$t$ objective is Paper I's expected-seats (optionally risk-adjusted) objective, evaluated at period-$t$ state:

$$\mathbb E[\text{Seats}]_t = \sum_{i=1}^N \Phi\!\left(\frac{\mu_{i,t}(D_{i,t})}{\sigma_{i,t}}\right)$$

with the identical risk-adjustment term from Paper I's Section 3.4 (corrected there to $\gamma\,\mathbf 1'\Sigma(\mathbf x)\mathbf 1$) available but not the focus of this paper's headline results, which use $\gamma=0$ throughout, consistent with Paper I.

## Optimization Problem

The complete period-$t$ optimization problem is:

$$
\begin{aligned}
\max_{\mathbf{\text{party}}_t} \quad & \sum_{i=1}^N \Phi\!\left(\frac{\mu_{i,t}(D_{i,t})}{\sigma_{i,t}}\right) - \gamma\, \mathbf 1'\Sigma_t(\mathbf{\text{party}}_t)\,\mathbf 1 \\
\text{s.t.} \quad & \sum_{i=1}^N \text{party}_{i,t} \le F_t \\
& 0 \le \text{party}_{i,t} \le \kappa F_t \quad \forall i \\
& D_{i,t} = \text{cand\_floor}_{i,t} + L_{i,t} + \text{party}_{i,t}
\end{aligned}
$$

This is, mechanically, the identical problem Paper I solves once, with two substitutions: the budget constraint uses deployable capital $F_t$ rather than the full-cycle budget, and each race's already-committed capital $L_{i,t}$ is added to the spending floor exactly as candidate-committee spending is. Section 4 develops what changes on the left-hand side (the state) between periods, and Section 4.6--4.7 states precisely what this formulation, solved repeatedly, still does not price.

\newpage

# Theoretical Framework

This section develops the paper's conceptual core: the campaign state vector and how it is permitted to evolve, the committed/deployable capital identity, the state-update operator (both as a general object and as a concrete, reproducible baseline instantiation), the rolling re-optimization this makes possible, and the real-options analogy that identifies -- without solving -- what this rollout policy necessarily leaves unpriced.

## Campaign State

Define the campaign state at reporting period $t$ as

$$\mathbf X_t = \big\{\, \mu_{i,t},\ \sigma_{i,t},\ G_t,\ \text{CashOnHand}_{i,t},\ \text{CookRating}_{i,t},\ \text{incumb}_i,\ \text{PVI}_i,\ \text{RecentSpend}_{i,t},\ \dots \,\big\}$$

for each race $i$. Several components are already present in Paper I's static specification (PVI, incumbency, the generic-ballot factor); what is new is that they are now indexed by $t$ and permitted to change between periods as new information is observed. The decision at each period is an allocation of deployable capital, $\text{party}_{i,t}$, and the transition between periods is governed by an update operator, $\mathbf X_{t+1} = f(\mathbf X_t, \text{information}_t)$, deliberately left generic here (Section 4.3 develops a specific, concrete instantiation for the empirical work of Section 8). A companion paper (Paper III) subsequently gives this state vector a fully precise, six-component definition and specifies a transition law for its stochastic components; this paper's contribution does not depend on committing to that specification, only on establishing that some such specification is what a genuinely dynamic treatment would require.

## Committed and Deployable Capital

The object that actually changes the optimizer's feasible set between periods is not the state $\mathbf X_t$ but the budget constraint. Total campaign budget at period $t$ splits into committed and deployable capital:

$$B_t = L_t + F_t$$

where $L_t$ is capital already irreversibly committed -- booked television time, signed leases, executed contracts, money that cannot be clawed back and reassigned to a different race -- and $F_t$ is capital available for allocation at period $t$. The capital account evolves independently of the electoral state:

$$F_{t+1} = F_t - \text{new\_commitments}_t + \text{new\_fundraising}_t$$

The sequential optimizer of Section 3.5 solves only over $F_t$; $L_t$ enters as a fixed floor added to each race's total spend, never as a decision variable.

**Research mode versus operational mode.** Paper I's empirical credibility rests on a load-bearing claim: every quantity in the framework can be estimated from public data. $L_t$ threatens this claim if treated carelessly, since FEC bulk disbursement data report money only *after* it has been spent, while a committee's reserved-but-unaired advertising commitments are not disclosed publicly at the time the reservation is made. We therefore explicitly separate the decision architecture from its data source. In **research mode**, $L_t$ is approximated from publicly observable commitment proxies -- in the empirical work below, realized (already-disbursed) coordinated and independent-expenditure spending, a conservative lower bound on true committed capital, since it necessarily misses reservations booked but not yet aired or paid. In **operational mode**, $L_t$ is supplied directly by a committee's internal accounting ledger -- exact, but not a publicly reproducible research artifact. This distinction separates the optimization architecture, a single well-defined object, from the provenance of one of its inputs, a deployment choice a practitioner can make either way without the paper's core claims changing.

## The State-Update Operator

Section 4.1 leaves $f$ fully generic as a theoretical object; an empirical implementation must commit to something concrete. A naive instantiation -- simply re-running Paper I's estimation pipeline on the latest polling, FEC, and Cook-rating snapshot at every period -- feeds raw period-to-period noise directly into $\mu_{i,t}$. Real polling and fundraising signals are noisy at the weekly-to-biweekly frequency this architecture operates at, and an optimizer reacting to every single-poll bounce would recommend allocations that thrash from period to period in a way no practitioner would follow. The baseline $f$ used throughout Section 8 instead smooths the raw re-estimate:

$$\hat\mu_{i,t} = \lambda\,\hat\mu_{i,t-1} + (1-\lambda)\,\mu_{i,t}^{\text{raw}}$$

where $\mu_{i,t}^{\text{raw}}$ is Paper I's pipeline re-estimated on the period-$t$ data snapshot and $\lambda\in(0,1)$ is a smoothing constant; $\sigma_{i,t}$ is smoothed identically. We use $\lambda=0.7$ (Appendix B.1 derives its implied half-life, $\ln(0.5)/\ln(0.7)\approx1.94$ periods), a starting value explicitly flagged in Section 10 as a stated, untested modeling choice rather than a derived one. This is deliberately the simplest possible filter -- an exponential moving average with no explicit treatment of estimation uncertainty -- chosen so that Section 8 has something concrete and reproducible to run, not because it is the theoretically preferred choice. A Bayesian update or a formal Kalman or particle filter would replace this EMA with an update that also carries an explicit posterior variance for $\mu_{i,t}$, which this rollout policy does not currently use; this is the natural next refinement, not a requirement for this paper's contribution.

## Rolling Static Re-Optimization Over Deployable Capital

The rollout procedure this architecture implements is:

**Algorithm 1: Rolling Static Re-Optimization Under Irreversible Commitments**

\footnotesize
```
for each reporting period t:
    observe new information
    update X_t -> X_{t+1}                          (Section 4.3)
    update capital account:
        F_{t+1} = F_t - new_commitments_t + new_fundraising_t
    recompute mu, sigma, MSG from updated state
    solve the SINGLE-PERIOD optimizer (Section 3.5) over F_{t+1},
        with L_{t+1} folded into each race's floor
        [no lookahead: this step plans no future period]
    output: recommended allocation of F_{t+1}
```
\normalsize

**On terminology.** At each period, the full *current* single-period problem is re-solved from the current state, and the resulting allocation is executed before the next observation arrives -- but nothing in this loop plans a multi-period trajectory or prices the consequence today's decision has for what will be feasible or optimal next period. This is precisely a **rollout policy** in the sense of Section 2.2: Paper I's static optimizer is the base heuristic, applied greedily using the true current state at every stage. We avoid the terms "receding-horizon" and "model-predictive control" for this procedure, despite their surface similarity, because both terms denote a finite-horizon *trajectory* optimization at each step (Section 2.2), which this algorithm does not perform. The distinction is not pedantic: it is the direct explanation for Section 4.6--4.7's finding that this procedure has no mechanism to reward patience, and for why Section 8.1's front-loading result should be read as close to a structural consequence of the algorithm above rather than a surprising empirical discovery. We emphasize that this is *not* equivalent to solving a single multi-period dynamic program over the whole cycle -- it is a sequence of single-period re-solves, myopic by construction. Section 4.6 identifies precisely what this myopia discards.

## The Real-Options Analogy

This rollout policy implicitly assumes all currently deployable capital should be deployed now, to the extent the budget constraint and cap allow. But if a race's polling is volatile and a new fundraising or polling report is due in two weeks, spending the marginal dollar today forecloses the ability to spend it more efficiently once that report resolves some of the uncertainty in $\mu_i$. Deployable capital retained rather than committed preserves the ability to respond to information that has not yet arrived, and the static, myopic re-solve of Section 4.4 has no mechanism for valuing this: it treats $F_t$ as something to be spent down to the constraint boundary each period, with no term rewarding patience.

Paper I already introduces a finance analogy for open-seat races: higher structural volatility simultaneously raises a race's baseline win probability and lowers its marginal seat gain per dollar, in direct analogy to how higher implied volatility raises an option's price while lowering its delta. Uncommitted campaign capital extends this analogy in a different dimension. Committing capital to a race is analogous to *exercising* an option: it converts flexible, redeployable capital into a fixed position, forfeiting the ability to wait for resolving information.

**Table 2: The Real-Options Correspondence**

| Finance | Campaign allocation |
|---|---|
| Cash / uninvested capital | Uncommitted (deployable) budget, $F_t$ |
| Exercise decision | Commit spending to a race |
| Underlying uncertainty | Polling, fundraising, candidate events |
| Expiration | Election Day |
| Early-exercise decision | Spend now vs. retain flexibility |

Under this analogy, the rollout policy of Section 4.4 is not merely deciding *where* to spend; implicitly, by spending down $F_t$ each period, it is also deciding -- without being asked to -- *when* to give up flexibility. That is a materially different decision than the one the static architecture is designed to make well.

## Time Decay of Option Value

The real-options analogy is incomplete without its time dimension. An election cycle has a hard, known expiration date $T$ (Election Day). Standard option pricing decomposes an option's value into intrinsic value and time value, and the latter -- conventionally denoted $\Theta$ -- decays toward zero as expiration approaches: with less time left for the underlying to move, the value of retaining the right to wait shrinks. The same logic applies directly to uncommitted campaign capital. Early in a cycle, a large amount of information has yet to arrive -- primary results, several fundraising quarters, multiple rounds of polling, redistricting rulings, retirements -- and capital retained at that point preserves the ability to respond to nearly all of it. Late in the cycle, almost all of the information that will arrive before Election Day already has, and progressively less time remains to act on it even where it could. The option value of a dollar held uncommitted therefore strictly decreases as $t\to T$, and is exhausted entirely at Election Day, when capital not yet spent has permanently forfeited its only opportunity to affect the outcome.

This yields a direct, qualitative implication the rollout architecture does not generate on its own. Holding the campaign's information-arrival process fixed, shortening the remaining decision horizon can only weakly reduce the opportunity set for using retained flexibility, so the continuation value of waiting should not increase as Election Day approaches, and must reach zero once it arrives. This is a weaker and more defensible claim than saying option value strictly decreases along the realized path: new information -- an unexpected retirement, a scandal, a court-ordered redistricting ruling, a race becoming newly competitive -- can cause the *estimated* value of waiting to rise before that final convergence, even though the horizon-driven component of the opportunity set is shrinking throughout. Section 8.1 reports this paper's own directly-computed evidence that DCCC's real spending is heavily back-loaded within a cycle, consistent with a mechanism along these lines, though establishing the mechanism precisely is a companion paper's task, not this section's. We do not derive a functional form for $\Theta(t)$ in this paper; we note only that any future formalization of the stopping problem below must impose $\Theta(t)\to0$ as $t\to T$ as a boundary condition, holding the information process fixed.

**Implication for the rollout policy.** Algorithm 1 has no $\Theta$ term. At each period it treats all of $F_t$ as capital to be deployed immediately, up to the concentration cap, because nothing in its objective rewards holding capital back. Combined with the decay logic above, this predicts a specific and testable failure mode: absent any modeled cost of forgoing flexibility, the greedy solve should recommend deploying capital considerably earlier in the cycle, and more broadly across marginally-plausible races, than a $\Theta$-respecting rational actor would -- and, in particular, earlier and more broadly than DCCC's actual historical spending pattern, which is a matter of public record. Section 8.1 treats the *gap* between the greedy model's recommended deployment schedule and DCCC's actual schedule as an empirical object of interest in its own right: a revealed-preference estimate of the option value a committee implicitly assigns to retained flexibility, which the static model has no mechanism to price directly.

## A Stated Limitation, Not a Solved Problem

We do not solve the option-value problem in this paper. Doing so requires a stochastic control formulation -- an explicit model of how the campaign state evolves over time and an optimal-stopping or continuation-value calculation, in the tradition of regression-based methods for American option pricing (Longstaff and Schwartz 2001) -- that would change the nature of this paper's contribution from an operational architecture to a stochastic control paper. We state the limitation precisely instead:

> The sequential optimizer of Section 3.5 assumes all currently deployable capital should be allocated immediately, subject to the period's constraints. In practice, retaining a portion of deployable capital uncommitted preserves flexibility in the presence of future information arrivals, and this flexibility has positive option value analogous to the early-exercise problem in American-style financial options. Quantifying this option value requires a stochastic control formulation and is a direction for future work.

A companion paper takes exactly this formulation as its subject: it specifies the state-transition law this paper leaves generic, and solves the resulting stopping problem by the regression-based Monte Carlo method named above. This paper's architecture and four contributions above do not depend on that companion paper's specific result; the open question stated above is deliberately left open here and answered elsewhere.

Short of solving for the option value explicitly, the architectural implication is that Algorithm 1's output should be understood as a recommended allocation of $F_t$ *conditional on choosing to deploy it now*, with an explicit reserve step available as a discretionary override:

$$\text{update state} \to \text{estimate } F_t \to \text{optimize deployment (Alg.\ 1)} \to \text{reserve optionality (discretionary)} \to \text{allocate remainder}$$

This is a meaningful extension over Paper I even without a solved stopping rule: it makes explicit, for the first time in this research program, that a dollar not yet committed is not simply a dollar with zero contribution to expected seats -- it is a claim on future flexibility with its own value, distinct from the value of the marginal dollar spent.

## Two Different Assets

This motivates a distinction that did not need to exist in Paper I. Paper I values the marginal campaign *dollar* -- what one additional dollar of spending, deployed now, contributes to expected seats. This paper's architecture, even without solving the stopping problem above, makes explicit that a second asset exists: the marginal dollar of *flexibility* -- the value of a dollar not yet committed, held against the possibility that better information will make a future allocation more efficient than today's. One asset is spent; the other is preserved. Paper I has no language for the second asset because a one-shot allocation problem has no "later" for flexibility to matter. A sequential problem does. Identifying this second asset -- without yet pricing it -- is this paper's clearest point of intellectual departure from Paper I, and the object Paper III's contribution prices.

\newpage

# Data

## Data Sources

This paper inherits every public data source Paper I uses (FEC bulk filings, MIT Election Data and Science Lab results, Cook PVI, generic-ballot polling averages) without modification, and adds three sources specific to the sequential architecture: dated (per-filing-period) FEC candidate-committee reports, used both to reconstruct historical state at multiple points within a cycle and, in research mode, as an input to the committed-capital estimator; date-bucketed independent-expenditure and coordinated-expenditure records (FEC Schedule E and F, resolved to specific filing dates rather than cycle-cumulative totals); and live generic-ballot and district-level polling (VoteHub), used to construct the live 2026 state.

## Coverage

The historical one-step-ahead replay (Section 8.1) covers the 2022 and 2024 cycles, reconstructing campaign state at biweekly reporting periods from January through early November of each cycle -- 38 periods per cycle. The live application (Section 8.2) covers a single reporting period against the in-progress 2026 cycle, re-run as fresh data becomes available; the run reported here reflects a live snapshot as of the most recent full data refresh in the underlying pipeline.

## Feature Engineering

At each reporting period, race-level state is reconstructed from data actually available as of that date -- cumulative candidate-committee and coordinated spend, date-bucketed independent expenditures, the generic-ballot average as of that date -- and passed through Paper I's unmodified estimation pipeline to produce a raw $\mu_i^{\text{raw}},\sigma_i^{\text{raw}}$ pair, which Section 4.3's EMA then smooths against the prior period's estimate.

## Cleaning

Dated independent-expenditure reconstruction requires amendment resolution (a filing later amended can appear more than once against the same committee and coverage window; the latest FEC image number is kept) and filtering of implausible transaction amounts and duplicated transaction IDs, both of which are documented data-quality issues in the raw FEC comprehensive IE export that a cycle-cumulative analysis (Paper I's) does not surface but a date-bucketed reconstruction does.

## Final Dataset

**Table 3: Sequential Architecture Dataset Summary**

| Quantity | Value |
|---|---|
| Historical replay cycles | 2022, 2024 |
| Reporting periods per cycle | 38 (biweekly, January -- early November) |
| Reporting cadence | Biweekly (14-day grid) |
| Live application cycle | 2026 (in progress) |
| Additional data sources beyond Paper I | Dated candidate periodic reports; date-bucketed IE/coordinated spend; live polling |

\newpage

# Parameter Estimation \& Calibration

This section documents where every parameter specific to the sequential architecture (as opposed to the inherited valuation model) comes from.

## State-Update Smoothing

The EMA smoothing constant $\lambda=0.7$ (Section 4.3) is a stated starting value, not fit against any validation target in this paper. Its implied half-life is $\ln(0.5)/\ln(0.7)\approx1.94$ reporting periods (Appendix B.1), meaning a single period's raw re-estimate retains roughly half its influence on the smoothed state after about two biweekly periods (four weeks). Section 8.1 tests $\lambda\in\{0.5,0.9\}$ against this baseline directly on the 2024 and 2022 historical replays and finds every headline statistic unchanged to full precision, so the specific value of $\lambda$ is not doing unstated work in this paper's results, though no explicit uncertainty-carrying filter (a formal Kalman or particle filter, which would additionally carry a posterior variance forward) is tested against the EMA functional form itself; Section 10 flags this narrower gap explicitly.

## Committed Capital Estimation

In research mode, $L_t$ is estimated by `RealizedSpendCommitmentSource`: real, disbursed coordinated expenditure (FEC Schedule F) plus date-bucketed independent expenditure (FEC Schedule E) spend by DCCC-aligned committees, summed through the reporting date. This is a conservative lower bound on true committed capital, since television and digital reservations are frequently booked well before the corresponding disbursement is filed with the FEC. An `AdReservationProxySource`, which would estimate $L_t$ from commercial ad-tracking data (booked-but-unaired reservations, reported at the time of booking rather than disbursement), remains an unimplemented stub in this paper's empirical work -- no affordable public feed for this data was identified. The gap between either proxy and a committee's true internal ledger is itself unmeasured.

## 2026 Budget Projection

$B_t$ is precisely one of three financial objects it could plausibly denote, and we state which: it is a **historical-comparable-cycle estimate** -- the average of the 2018 and 2022 midterm cycles' final, realized, cycle-end party-controlled budgets, each independently inflated to 2026-equivalent dollars via BLS CPI-U (series CUUR0000SA0). It is *not* a projection of the committee's current cash on hand plus its expected future receipts for the remainder of the 2026 cycle, and it is *not* a measure of currently-accessible liquid resources at the time the pipeline is run; this paper does not attempt to build either of those two live, forward-looking financial measures. $B_t$ therefore answers "what did comparable recent midterm cycles' committees ultimately have to spend, in today's dollars," not "what does this committee actually have or expect to have right now" -- a real limitation of the live application (Section 6.3, Section 10.1), stated precisely rather than left to the reader to infer from context.

## Calibration Summary

**Table 4: Sequential Architecture Calibration Summary**

| Parameter | Value | Source |
|---|---|---|
| $\lambda$ (EMA smoothing constant) | 0.7 | Stated starting value (Section 6.1) |
| Implied half-life | 1.94 periods | Derived (Appendix B.1) |
| Reporting cadence | 14 days (biweekly) | `dynamic/periods.py` |
| $L_t$ estimator (research mode) | `RealizedSpendCommitmentSource` | Real, disbursed spend; conservative lower bound |
| $B_{2026}$ | 2018/2022 CPI-inflated average | `backtest.model.budget.estimate_budget_2026()` |
| Concentration cap $\kappa$ | 0.15 | Inherited from Paper I |
| Risk aversion $\gamma$ | 0.0 (risk-neutral) | Inherited from Paper I |

\newpage

# Optimization Algorithm

## Rollout Strategy

The sequential optimizer inherits Paper I's SLSQP-based nonlinear solve entirely; no new solver is introduced. What changes is that the solve is invoked once per reporting period rather than once per cycle, each time as a single-period problem against the current period's deployable capital $F_t$ and with committed capital $L_{i,t}$ folded into each race's floor -- with no lookahead to future periods, per Section 4.4's terminology.

## Algorithm

Algorithm 1 (Section 4.4) gives the top-level rolling re-optimization loop. Each period's inner solve is Paper I's Algorithm 1 (its Section 7.2) applied with `party_budget = F_t` and `floors = cand_floor + L_t`, with no other modification.

## Computational Complexity

Each period's inner solve has the identical per-call complexity as Paper I's optimizer ($O(N)$ per SLSQP iteration; Paper I Section 7.3). The rolling loop multiplies this by the number of reporting periods -- 38 for the historical replay, a single call for a live snapshot -- so a full historical-cycle replay completes in well under an hour on commodity hardware, dominated by state reconstruction (data loading and cleaning at each period) rather than by the optimization itself.

## Computational Environment

The sequential architecture is implemented as a thin layer (`src/backtest/dynamic/`) over Paper I's unmodified estimation and optimization code, using the identical Python/NumPy/SciPy stack. `dynamic/horizon.py`'s `run_receding_horizon()` orchestrates the period loop; `dynamic/ledger.py` implements the committed-capital estimators; `dynamic/updates.py` implements the EMA state updater; `dynamic/periods.py` generates the reporting-period grid. As in Paper I, every configuration parameter (the smoothing constant, reporting cadence, commitment-mode selection) is centralized in `config.yaml` rather than hard-coded.

\newpage

# Empirical Results

## Internal Validation

Before interpreting either empirical result below, it is worth noting a check reported in full by Paper III but directly relevant to whether this paper's sequential framing is doing real work at all: re-solving the optimizer against real historical state snapshots from the 2022 and 2024 held-out cycles at different points in the cycle, holding the total party budget fixed and identical at each snapshot so that only the *information* available differs, shows substantial turnover in the top twenty targeted races between a 60-day-out and a 14-day-out snapshot (Jaccard overlap 0.54 and 0.67 respectively across the two cycles) -- real, substantial change, not a rounding effect. The optimal allocation is demonstrably state-dependent: adaptive reallocation is a meaningful decision problem in this domain, which is the necessary condition for a sequential architecture to be worth building in the first place.

## Historical Replay: One-Step-Ahead Evaluation, 2022 and 2024

**Design: one-step-ahead evaluation, not a closed-loop autoregressive simulation.** A naive design would reconstruct campaign state at each historical reporting date, feed it to the policy, treat the optimizer's recommendation as that period's actual spending decision, and roll forward autoregressively -- with each subsequent period's state built partly from the model's own prior recommendations rather than from the historical record. This design is invalid and is not used here. Historical polling, fundraising, and Cook-rating data available as of any date $t+1$ are themselves a function of what DCCC actually spent through date $t$, not of what this model would have recommended spending; feeding a hypothetical spending path back into subsequent state reconstruction would optimize against a state variable contaminated by a counterfactual that never happened, and the contamination would compound across periods. We therefore evaluate the architecture one step at a time: at each historical reporting date, campaign state is reconstructed from data actually available as of that date -- never from the model's own hypothetical past decisions -- and the rollout policy's single-period recommendation is compared against DCCC's actual single-period allocation for that same period, holding the state fixed at its true historical value. This design can show whether, by how much, and at which points in the cycle the model's period-by-period recommendation diverges from DCCC's actual behavior; it cannot show whether following the model's advice across many consecutive periods would have compounded into a better final outcome, since that would require knowing how polling, fundraising, and opponent response would actually have evolved under a different spending history. We treat this as an honest and necessary scope reduction, restated in Section 10.

**Definitions.** `scripts/run_dynamic_backtest.py` executes this design across 38 one-step-ahead reporting periods in each of the 2022 and 2024 cycles. For race $i$ at period $t$, the per-observation quantities recorded are $\text{Model}_{i,t}$, the party spend the rollout policy would recommend for race $i$ if $F_t$ were deployed now, and $\text{Actual}^{\Delta}_{i,t}$, DCCC's real, period-over-period *incremental* party spend for that race (its cumulative real spend at $t$ minus at $t-1$). The per-observation gap is

$$\text{Gap}_{i,t} = \text{Model}_{i,t} - \text{Actual}^{\Delta}_{i,t}$$

a comparison of a *level* (what the rollout policy would recommend spending in total, right now, on this race) against an *increment* (what DCCC actually added that period) -- not a comparison of two cumulative totals. This distinction matters for how the aggregate statistic should be read, addressed directly below.

**Table 5: Definition and Summary of the Timing-Gap Statistic, 2022 and 2024**

| Quantity | 2024 | 2022 |
|---|---|---|
| Periods | 38 | 38 |
| Naive bivariate correlation, $\sum_t\text{Gap}_{i,t}$ vs. $\sigma_i$ | $-0.809$ | $-0.693$ |
| Average per-period aggregate gap $\sum_i\text{Gap}_{i,t}$ | \$361.8M | \$255.1M |
| Median per-period aggregate gap | \$370.0M | \$263.9M |
| Maximum per-period aggregate gap | \$370.9M | \$264.2M |
| Minimum per-period aggregate gap | \$235.2M | \$137.0M |
| $\sum_t\sum_i\text{Gap}_{i,t}$ (integrated, dollar-*periods*, not dollars) | \$13.39B | \$9.44B |

**On units.** The last row above is the sum previously reported in this paper as a single "\$13.39B/\$9.44B total deployment gap." That framing was imprecise and is corrected here: because $\text{Model}_{i,t}$ is close to the *same* near-total-deployment level at nearly every period (the rollout policy, having no patience, recommends deploying close to the entirety of $F_t$ from period 1 onward, so $\sum_i\text{Model}_{i,t}$ is roughly constant across $t$; Table 5's max and median rows are nearly identical), summing $\text{Gap}_{i,t}$ across all 38 periods adds a similarly large quantity to itself 38 times. The result is an integrated, area-under-the-curve statistic with units of dollar-*periods*, not a dollar amount, and it should not be read as "\$13.39 billion more was recommended than was spent." The *average per-period* gap (\$361.8M and \$255.1M, roughly 78--79\% of each cycle's total party budget) is the more interpretable summary: at a typical reporting period, the rollout policy recommends a level of total deployment on the order of the entire remaining party budget, against DCCC's much smaller actual period-over-period increment.

**A cleaner, complementary statistic: deployment-timing quantiles.** Because the level-vs-increment comparison above is itself an artifact of the rollout policy's own patience-blindness (it is comparing "what I'd want spent in total, now" against "what actually changed"), a more direct measure of *DCCC's own pacing* is when its real cumulative spending reaches successive shares of its eventual cycle total, independent of anything the model recommends:

**Table 6: DCCC's Real Deployment-Timing Quantiles**

| Cycle | Reaches 25\% of eventual total | Reaches 50\% | Reaches 75\% |
|---|---|---|---|
| 2024 | Period 34/37 (2024-09-19) | Period 35/37 (2024-10-03) | Period 36/37 (2024-10-17) |
| 2022 | Period 34/37 (2022-09-20) | Period 35/37 (2022-10-04) | Period 36/37 (2022-10-18) |

DCCC's real spending is extremely back-loaded in both cycles -- it does not reach even a quarter of its eventual cycle total until the final four of 37 reporting periods (roughly six weeks before Election Day), with three-quarters not reached until roughly two weeks out. The rollout policy, by contrast, recommends a level close to full deployment from the very first period. This is a directly interpretable, dollar-denominated comparison of pacing, not an integrated area statistic, and it is this paper's primary evidence for the claim that real committee behavior is far more patient than the architecture in Sections 3--4 recommends on its own -- evidence generated by this paper's own data, not an appeal to an external, uncited claim about "well-documented" industry practice.

**Sensitivity to the smoothing constant.** Re-running the 2024 and 2022 replays at $\lambda\in\{0.5,0.9\}$ in place of the baseline $\lambda=0.7$ reproduces every figure in Table 5 and Table 6 to full precision in both cycles: the aggregate gap total, the per-period average, and the naive correlation are unchanged across this range. This is consistent with the mechanism Section 9.1 describes -- the rollout policy's recommendation is driven by the budget constraint and concentration cap binding for most races, not by fine differences in the smoothed $\mu_{i,t}$ ranking -- and directly addresses whether $\lambda=0.7$ is doing unstated work in producing this section's headline finding: it is not.

**The volatility correlation does not survive controls in the expected direction.** The naive bivariate correlation between each race's summed gap and its static volatility $\sigma_i$ (Table 5) is negative and often cited as consistent with an option-value account -- races with more remaining uncertainty show a *larger* gap. This statistic is confounded, and does not hold up as stated. Regressing each race's average per-period gap on $\sigma_i$ together with absolute PVI, incumbency, and open-seat status (a cross-sectional multivariate specification, $n=53$ and $n=61$) reverses the sign on $\sigma_i$: the partial association is *positive* and significant in 2024 ($+\$29.9$M per point of $\sigma_i$, $p<0.001$, $R^2=0.83$), consistent with the option-value account's predicted direction once incumbency's confound is removed, but not significant in 2022 ($+\$13.1$M, $p=0.34$, $R^2=0.51$). The naive negative correlation is substantially explained by incumbent races simultaneously having lower $\sigma_i$ (Paper I's $\sigma_i$ model) and larger raw spending gaps for reasons apparently unrelated to volatility. We report this fully rather than retaining only the more favorable naive statistic: the evidence for a genuine volatility-gap relationship is, at best, mixed across the two cycles once confounds are addressed, and should be read as suggestive rather than as confirmatory of the option-value account.

## Live Application: The 2026 Cycle

The architecture in Sections 3--4 is designed to run prospectively as well as retrospectively. Operating it against the live, in-progress 2026 cycle -- ingesting FEC filings, generic-ballot updates, and Cook rating revisions as they are released, and re-solving the deployable-capital optimization at each reporting period -- turns the paper from a retrospective methodological exercise into an operational demonstration. Unlike the historical replay, a live deployment's recommendations, if followed, become part of the actual historical record subsequent data reflects, rather than a hypothetical alternative history competing with what was actually observed -- live application is the only setting in which this architecture's recommendations could, in principle, be evaluated against real, uncontaminated outcomes.

**Result, as of 2026-07-28.** This section's figures are a dated snapshot and will become stale as filings and polling continue; re-running the pipeline against a later data snapshot is expected to change the specific numbers below without changing the qualitative pattern this section documents. Run against the live 2026 universe (434 races) with an estimated budget $B_t=\$394.3$M -- a historical-comparable-cycle estimate, defined precisely in Section 6.3 as the CPI-inflated average of the 2018 and 2022 midterm party-controlled budgets, *not* a projection of current cash on hand plus expected future receipts, and not a measure of currently-accessible liquid resources -- a live generic-ballot point estimate, and $L_t$ from `RealizedSpendCommitmentSource`, the unmodified rollout policy recommends deploying the entirety of deployable capital $F_t$ immediately, concentrated disproportionately in non-competitive (Likely R and Safe R) seats -- a majority of $F_t$, at roughly three months from Election Day. This matches, qualitatively, the pattern the historical replay above establishes: a rollout policy built on a patience-blind base heuristic recommends earlier and broader deployment than DCCC's own real pacing (Table 6), and, by the mechanism of Section 9.1, does so largely because nothing in its objective prices the alternative.

We do not read this as evidence against the architecture's mathematical core; it is close to a structural consequence of the algorithm in Section 4.4, applied to an objective with positive marginal returns and no patience term, and Section 10.4 states plainly that this section's figure should not be read as a deployment recommendation as-is. A companion paper takes the resulting, unpriced gap -- named but deliberately not solved here -- as its entire subject.

\newpage

# Discussion

## Why the Rollout Policy Front-Loads

The mechanism behind both empirical results in Section 8 is structural, not incidental, and this is worth stating plainly rather than presenting the front-loading finding as a surprising discovery. Algorithm 1's objective rewards only the current period's contribution to expected seats; nothing in it prices the cost of foreclosing a future, better-informed reallocation. Because every race's marginal seat gain is (weakly) positive at every spending level below saturation (Paper I Section 4), the rollout policy always prefers spending now to not spending, for any positive $\text{MSG}_i$, regardless of how much of a race's uncertainty remains genuinely unresolved. A $\Theta$-aware policy would instead weigh a race's *current* marginal seat gain against the option value of waiting for that race's uncertainty to resolve further -- a comparison Algorithm 1 has no mechanism to make, by construction, not by omission.

## What the Historical Timing Gap Does and Does Not Show

Section 8.1's deployment-timing comparison (Table 6) is direct, dollar-denominated evidence that DCCC's real pacing is far more patient than the rollout policy recommends; this is the paper's more defensible empirical claim. The volatility correlation is weaker evidence than an earlier version of this section presented: the naive bivariate statistic does not survive controlling for incumbency and partisan lean in the expected direction, and even the corrected, theory-consistent partial association is significant in only one of the two cycles tested. An alternative, non-option-value explanation for the raw timing gap -- that DCCC's pacing reflects fundraising cadence, organizational capacity constraints, or strategic considerations unrelated to the value of waiting for information -- remains a live possibility this paper's design does not rule out. We report the deployment-timing pattern as a real, robust, and economically large empirical fact, and the volatility correlation as suggestive at best, rather than treating either as dispositive proof of the option-value mechanism Section 4.5--4.7 proposes.

## Strategic Implications

For a campaign committee, this architecture's practical output, on its own, is a systematically over-aggressive recommendation: fund everything with positive marginal seat gain, now, as broadly as the budget allows. Section 8.2's live result shows concretely why this should not be followed as-is at this stage of a cycle, and Table 6's deployment-timing quantiles show real committees do not, in fact, spend this way. The operational lesson is not that the rollout architecture is wrong, but that it is an incomplete decision system without an explicit patience term, exactly as Section 4.7 states -- a practitioner should treat Algorithm 1's output as an upper bound on how much to deploy immediately, pending the discretionary reserve step Section 4.7 describes or a formal patience term of the kind a companion paper develops.

## Generalizability

The committed-versus-deployable capital split, the rollout procedure built on top of a fixed valuation model, and the real-options treatment of unspent capital are not specific to campaign finance. Any capital-allocation setting with irreversible commitments, a hard deadline, and resolving uncertainty between now and that deadline -- venture capital deployment schedules, disaster-relief resource staging, seasonal inventory commitment -- shares this structure, and the same architectural separation (a fixed one-shot valuation model, re-solved sequentially over a shrinking deployable pool, with an explicit and separately-priced value of waiting) generalizes directly.

\newpage

# Limitations

## Data

$L_t$ is an approximation in research mode: the ad-reservation commitment proxy remains an unimplemented stub, and `RealizedSpendCommitmentSource` captures only money already disbursed, a conservative lower bound that misses reservations booked but not yet aired or paid. The gap between either proxy and a committee's true internal ledger is unmeasured; if systematically biased, the resulting $F_t$, and the entire downstream optimization, inherits that bias. The live 2026 application additionally carries the approximations already inherited from Paper I's live-cycle universe construction (PVI proxy years, unresolved mid-decade redistricting, algorithmically-derived rather than proprietary Cook ratings) and a budget figure that is a historical-comparable-cycle estimate rather than a live fundraising-pace projection.

## Modeling

The state-update smoothing constant ($\lambda=0.7$) is a stated modeling choice; Section 8.1 tests it against $\lambda\in\{0.5,0.9\}$ and finds the headline results unchanged, but no explicit uncertainty-carrying filter (Kalman, particle) is validated against the EMA baseline in this paper. The rolling re-optimization procedure is not shown to be dynamically consistent with the true multi-period dynamic program it approximates, even setting aside the option-value question -- a sequence of myopic re-solves is not guaranteed to match that program's solution, and this paper does not attempt that comparison.

## Computational

Each period's inner solve inherits every computational limitation already stated in Paper I (no formal global-optimality certificate for the SLSQP solve). The rolling loop's complexity scales linearly with the number of reporting periods, which is not a binding constraint at the cadence and universe size used here but would need revisiting at substantially finer time resolution or a larger combined race universe.

## Practical Deployment

The one-step-ahead historical design (Section 8.1) cannot validate multi-period counterfactual outcomes: it can show that the model's recommendation diverges from DCCC's actual behavior, but not that following the model across many consecutive periods would have produced a better realized outcome, since the polling and fundraising path that would actually have resulted from a different spending history is unobserved. Only a live, followed deployment evaluates this architecture's multi-period recommendations against real, uncontaminated outcomes, and none has yet been run to completion at the time of this paper. Finally, and most centrally, this paper's own architecture is, by its own account, incomplete without the $\Theta$ term Section 4.7 identifies and Paper III subsequently prices -- a practitioner following this paper's Algorithm 1 alone, without that correction, would be following a policy this paper's own empirical results show diverges systematically from both a patience-respecting ideal and real committees' observed behavior.

\newpage

# Conclusion

Paper I asks what a campaign dollar is worth. This paper asks a related but distinct question: given that a committee cannot spend all its dollars at once, cannot un-spend a dollar once committed, and cannot know today what it will learn tomorrow, how should it operate Paper I's valuation model as a live decision system rather than a one-time calculation? The answer proposed here is architectural rather than mathematical: separate committed from deployable capital; re-solve Paper I's existing optimizer over deployable capital at each reporting period as new information updates the campaign state, correctly understood as a rollout policy rather than full model-predictive control; and, short of solving it, make explicit that capital retained rather than spent is itself a valuable, and -- within this paper alone -- unpriced, asset. A historical replay of the 2022 and 2024 cycles shows DCCC's real spending is heavily back-loaded within a cycle, in a way this rollout policy, by the structure of its own objective, has no mechanism to recommend on its own; a cross-sectional association between the resulting timing gap and race-level volatility is directionally consistent with an option-value account but does not survive controlling for incumbency and partisan lean in one of the two cycles tested, and we report it as suggestive rather than confirmatory. A live 2026 application shows the same qualitative pattern concretely, recommending broad deployment into non-competitive seats roughly three months from Election Day.

This paper's contribution is the architecture and the diagnosis, not a solution: naming the unpriced asset, distinguishing it precisely from the machinery (true model-predictive control) it superficially resembles, and demonstrating that the resulting gap between a patience-blind policy and real committee behavior is real, large, and robust to the one modeling choice (the smoothing constant) most likely to be suspected of driving it. Pricing that asset -- specifying how the campaign's state actually evolves and solving the resulting optimal-stopping problem -- is left, deliberately, as the open question a companion paper takes up.

\newpage

# Data Availability

All data used in this paper are drawn from public sources, identical to those documented in Paper I's Data Availability statement, with the addition of dated FEC candidate periodic reports (FEC API `/committee/{id}/reports/` endpoint) and live polling data (VoteHub API), both likewise public and free to access with a registered API key.

# Code Availability

**Repository:** `https://github.com/callum-doty/political-portfolio`
**Entry point:** `src/backtest/dynamic/horizon.py::run_receding_horizon()` (sequential architecture); `scripts/run_dynamic_backtest.py` (historical one-step-ahead replay); `scripts/plot_2026_live_allocation.py` (live 2026 application)

# Conflict of Interest

The authors declare no conflict of interest. This research was not funded by, and the authors hold no financial relationship with, any political campaign, party committee, or campaign consulting firm.

\newpage

# References

Bellman, R. (1957). *Dynamic Programming*. Princeton University Press.

Bertsekas, D. P. (2017). *Dynamic Programming and Optimal Control*, Vol. I, 4th ed. Athena Scientific.

Bertsekas, D. P. (2019). *Reinforcement Learning and Optimal Control*. Athena Scientific.

Dixit, A. K., and Pindyck, R. S. (1994). *Investment Under Uncertainty*. Princeton University Press.

Garcia, C. E., Prett, D. M., and Morari, M. (1989). Model predictive control: Theory and practice -- a survey. *Automatica*, 25(3), 335--348.

Gittins, J. C. (1979). Bandit processes and dynamic allocation indices. *Journal of the Royal Statistical Society: Series B*, 41(2), 148--177.

Longstaff, F. A., and Schwartz, E. S. (2001). Valuing American options by simulation: A simple least-squares approach. *The Review of Financial Studies*, 14(1), 113--147.

McDonald, R., and Siegel, D. (1986). The value of waiting to invest. *The Quarterly Journal of Economics*, 101(4), 707--727.

Powell, W. B. (2011). *Approximate Dynamic Programming: Solving the Curses of Dimensionality*, 2nd ed. Wiley.

Rawlings, J. B., Mayne, D. Q., and Diehl, M. (2017). *Model Predictive Control: Theory, Computation, and Design*, 2nd ed. Nob Hill Publishing.

Machine-readable BibTeX entries are provided as `references.bib` in the replication repository, combined with Paper I's and Paper III's reference lists.

\newpage

# Appendix A: Notation Reference Table

See Table 1 (Section 3.1) for symbols specific to this paper. All symbols inherited from Paper I (the spending response surface, $\mu_i$, $\sigma_i$, $\text{MSG}_i$, $\Phi$, $\varphi$, the persuasion ceiling $C_i$, and the optimizer's $\gamma$, $\kappa$) retain their Paper I definitions unchanged.

# Appendix B: Derivations

## B.1 EMA Half-Life

The exponential moving average $\hat\mu_t=\lambda\hat\mu_{t-1}+(1-\lambda)\mu_t^{\text{raw}}$ unrolls, by repeated substitution, to $\hat\mu_t=(1-\lambda)\sum_{k\ge0}\lambda^k\mu_{t-k}^{\text{raw}}$, a geometrically-weighted sum of all past raw estimates. The half-life $h$ -- the number of periods after which a given raw observation's weight has decayed to half its initial value -- solves $\lambda^h=0.5$, giving $h=\ln(0.5)/\ln(\lambda)$. At $\lambda=0.7$: $h=\ln(0.5)/\ln(0.7)\approx 1.94$ reporting periods.

## B.2 The Capital Account Identity

$B_t=L_t+F_t$ splits total budget into irreversibly committed and deployable capital by construction; the period-$t$ optimizer (Section 3.5) is re-solved over $F_t$ only, with $L_t$ folded into each race's spending floor -- the same floor mechanism Paper I already uses for candidate-committee spending, not a new constraint type. The capital account updates as $F_{t+1}=F_t-\text{new\_commitments}_t+\text{new\_fundraising}_t$, a deterministic bookkeeping identity independent of the electoral state $\mathbf X_t$.

# Appendix C: Reproducibility Checklist

- [x] All data sources are public and cited (Section 5.1) or documented as requiring a free, registered API key
- [x] Complete architecture code is version-controlled and publicly available (Code Availability)
- [x] The rolling re-optimization procedure requires no new solver, objective, or constraint structure beyond Paper I's (Section 7.1)
- [x] The procedure is explicitly distinguished from true model-predictive control and correctly characterized as a rollout policy (Section 2.2, 4.4)
- [x] The historical replay's one-step-ahead design is stated explicitly, with its scope limitation (Section 8.1)
- [x] The state-update smoothing constant is tested against two alternative values, not presented as derived, and shown not to drive the headline results (Section 6.1, 8.1)
- [x] The timing-gap statistic's units are defined explicitly (model level vs. actual increment), and the previously-reported integrated dollar-period total is relabeled and supplemented with directly interpretable per-period and deployment-quantile statistics (Section 8.1)
- [x] The volatility correlation is reported both as a naive bivariate statistic and under a controlled multivariate specification, including the sign reversal the controls produce (Section 8.1)
- [x] The live 2026 result carries an explicit as-of date and is flagged as expected to become stale (Section 8.2)
- [ ] The committed-capital estimator's approximation error relative to a true internal ledger is unmeasured (Section 10.1; flagged as open)
- [ ] A formal comparison of the rollout policy against the true multi-period dynamic program's solution is not attempted (Section 10.2; flagged as open)
- [ ] A live deployment's multi-period recommendations have not yet been evaluated against real, uncontaminated outcomes (Section 10.4; flagged as open)
