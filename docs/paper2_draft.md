# Dynamic Political Capital Allocation for the 2026 U.S. House Elections

### An Operational Architecture for Sequential Campaign Spending Under Commitment Constraints

*Draft — companion paper to "Estimating the Marginal Seat Gain of Campaign Spending"*

---

## Abstract

The companion paper to this one ("Paper I") develops a framework for estimating the marginal seat gain (MSG) of campaign spending and shows that the DCCC's 2022 and 2024 spending allocations are inconsistent with efficient, risk-adjusted deployment of a fixed budget. That framework is static: it values one dollar of spending at one point in time, against one fixed total budget.

Real campaign committees do not allocate money once. They raise and commit capital continuously over a two-year cycle, observe new information — polling, fundraising disclosures, retirements, scandals, generic-ballot movement — on a rolling basis, and cannot recover money already spent. This paper does not propose a new valuation model or a new optimizer. It takes the valuation model and optimizer from Paper I as given and asks a different question: *how should a committee convert a static valuation model into a sequential decision system?*

We make four contributions. First, we extend the static marginal seat gain estimate MSG_i to a time-indexed quantity MSG_i(t) that updates as new information arrives. Second, we formalize the distinction between a committee's total budget B_t, its already-committed (irreversible) capital L_t, and its deployable capital F_t = B_t − L_t, and show that the sequential allocation problem is Paper I's optimizer re-solved over F_t at each reporting period rather than over the full budget once. Third, we introduce a research/operational mode distinction for the commitment ledger: because committed-but-undisbursed spending is not observable in public FEC data, a publicly reproducible implementation must approximate L_t from commitment proxies, while an operational deployment inside an actual committee can use the internal ledger directly. Fourth, we identify — without solving — an intertemporal decision the static model cannot express: uncommitted capital has option value, because retaining flexibility in the face of resolving information is analogous to holding an American option rather than a forward contract. We formalize this analogy but explicitly do not solve the associated optimal-stopping problem, leaving it to future work in stochastic control.

**Update (2026-07-22): "leaving it to future work" no longer describes where this research program stands.** A third, companion paper (`docs/paper3_draft.md`) has since specified the stochastic process this section calls for and solved the resulting stopping problem by regression-based Monte Carlo. Its current result — reported in full in Section 8 below — reverses the practical implication this paper's live run (Section 7.1) originally suggested: rather than deploying broadly across non-competitive seats, a Θ-aware policy recommends holding the reserve back entirely at the live 2026 decision. This paper's own architecture and four contributions above are unchanged by that result; only the "not yet solved" framing is superseded.

The result is a systems paper, not an optimization paper: the mathematical core of Paper I is unchanged, and the contribution is the architecture that lets that core be operated sequentially, under real commitment constraints, with an explicit accounting of what a static solve necessarily discards.

---

## 1. Introduction

Paper I asks whether a fixed pool of campaign spending was allocated efficiently across a portfolio of House races, using a marginal-seat-gain framework analogous to portfolio construction. It answers a retrospective, one-shot question: *given the totality of 2024 spending, was it deployed where the marginal dollar mattered most?*

That question is not the one a sitting campaign committee actually faces. A committee does not receive its full cycle budget on day one and solve a single allocation problem. It raises money continuously, commits money continuously — and irreversibly, once a media buy is booked or a field office is leased — and receives new information continuously: a primary result, a fundraising quarter, a redistricting ruling, a candidate's health scare, a shift in the generic ballot. Every one of these events changes the estimated win probability of one or more races, and therefore changes where the *next* dollar should go. The static allocation recommended in January is not the static allocation that would be recommended in September, even holding the valuation model fixed.

This paper reframes the problem accordingly. The central question is not *where should the budget have gone* but:

> Given everything currently known, and given capital already irreversibly committed, how should a committee deploy its remaining, uncommitted budget right now?

This is a sequential decision problem, not a one-shot optimization. Answering it requires three things Paper I does not provide: a mechanism for updating race-level estimates as information arrives; an explicit accounting of committed versus deployable capital, since the optimizer must never be permitted to reallocate money that no longer exists to reallocate; and a recognition that deployable capital retained rather than spent has value beyond its face amount, because retaining it preserves the option to respond to information that has not yet arrived.

We emphasize at the outset what this paper does *not* claim to contribute. It does not propose a new estimator for the spending response surface, a new covariance model, or a new optimizer — all three are inherited from Paper I unchanged. Nor does it solve a stochastic control problem for optimal capital deployment timing; that is flagged as a well-defined direction for future work, not attempted here. The contribution is architectural: a decision system that consumes the valuation model from Paper I as a subroutine, called repeatedly, against a shrinking and constrained pool of capital, with an explicit place-holder for the value of not yet committing.

### 1.1 Why Sequential Allocation Is a Fundamentally Different Problem

It is tempting to assume that a "dynamic" allocation problem is solved simply by re-running Paper I's optimizer at regular intervals — recompute the state, re-solve the static problem, repeat. Section 4 in fact implements exactly this receding-horizon procedure, because it reuses Paper I's machinery without modification. It is important to be precise, at the outset, about what that procedure is and is not actually solving — the gap between the two is the reason a second paper is needed at all.

A static allocation problem takes a fixed budget and a fixed, known set of parameters (μᵢ, σᵢ) and produces a single vector of numbers: an allocation {sᵢ}. The problem is solved once; the output is a *plan*. A sequential allocation problem differs in two structural respects that merely repeating the static solve does not, by itself, resolve.

**Decisions are irreversible, and therefore path-dependent.** In the static problem, re-solving costs nothing — the full budget is, notionally, back on the table every time. In the true sequential problem, capital committed at period t is permanently removed from the feasible set at every subsequent period (Section 3.2's Lₜ). The sequential problem's state at period t therefore depends on the entire history of decisions made before it, not merely on newly observed information. Re-solving the static problem over Fₜ each period, as Section 4 does, correctly respects this for the *constraint* — it never reallocates money that is already committed — but it says nothing about whether the *sequence* of commitments that produced Lₜ was itself a good sequence. Whether it was correct to commit a given dollar now, rather than in a later period, is a question no static re-solve asks, no matter how frequently it is repeated.

**The parameters are not fixed quantities to be estimated once, but stochastic processes that resolve over time.** Paper I treats μᵢ and σᵢ as fixed, if uncertain, numbers to be estimated. In the sequential setting, the value a committee's model would assign to μᵢ,ₜ in October is not knowable in March; it depends on polling and fundraising outcomes that have not yet occurred. A static solve run in March necessarily optimizes against March's best estimate, not against the distribution of what that estimate might later become, and it therefore has no way to express — let alone act on — the fact that some races' estimates are far more likely to move materially than others'. That distinction is precisely the information a genuinely optimal sequential policy would need to condition on, and is the subject of Section 5.

Both points lead to the same conclusion. The object a sequential decision problem actually calls for is not a single allocation vector but a *policy* — a rule mapping the campaign's state, at any period, to a decision, chosen with explicit regard for how today's decision constrains and interacts with tomorrow's. This is the formal subject matter of dynamic programming and stochastic control. The receding-horizon procedure developed in Section 4 is a myopic *approximation* to that object, not a solution to it. It is, we think, a reasonable and practically implementable approximation — but Sections 5 and 8 return explicitly to what it leaves on the table, rather than presenting it as more than what it is.

### 1.2 Roadmap

Section 1.1 above establishes why sequential allocation cannot be reduced to repeated static allocation. Section 2 summarizes Paper I and states precisely what carries forward unchanged. Section 3 develops the sequential decision problem: the campaign state vector X_t, the split between committed and deployable capital, and the (deliberately generic) state-update operator. Section 4 shows that the sequential optimizer is Paper I's optimizer re-solved over deployable capital each period, not a new solver. Section 5 introduces the real-options analogy for uncommitted capital, its time decay toward Election Day, and states the associated limitation explicitly. Section 6 describes the planned historical simulation — replaying 2022 and 2024 using only information available at each contemporaneous reporting date — as a test of whether the sequential architecture would have recommended a materially different spending trajectory than the one Paper I evaluates retrospectively. Section 7 describes the live 2026 application. Section 8 discusses limitations.

---

## 2. Relation to Paper I

Paper I estimates a spending response surface

```
μᵢ = α₀ + α₁·PVIᵢ + α₂·incumbᵢ + α₃·GBᵢ
   + (β₁ + β₂·|PVIᵢ| + β₃·incumbᵢ) · log(Dᵢ/(Dᵢ+Rᵢ))
```

identified for incumbent-contested races via a repeat-challenger design (Levitt, 1994) and extended to open seats via a Bayesian shrinkage calibration; a district-level uncertainty model σᵢ; a win-probability mapping P(winᵢ) = Φ(μᵢ/σᵢ); a resulting marginal seat gain function MSGᵢ = ∂P(winᵢ)/∂sᵢ; a one-factor covariance model for cross-race correlation induced by the national environment; and a nonlinear (SLSQP) optimizer that allocates a fixed party-controlled budget to maximize expected seats net of a risk penalty, subject to a per-race concentration cap. Paper I finds that observed DCCC allocation is inefficient by this standard: MSG and observed spending are *negatively* rank-correlated among structurally comparable races (ρ = −0.809 in 2024, corrected 2026-07-24 for a persuasion-ceiling fix addressing an unbounded-gradient extrapolation bug — see Paper I §9.1's note; was −0.789 under a 2026-07-23b fix for an FEC committee-ID data bug and two model-estimation bugs, −0.536 after an earlier 2026-07-23a fix for a historical-panel data bug, −0.582 before that), and a model-optimal reallocation of the *same* total budget yields an estimated 2.8 additional expected seats (was 13.2 under 2026-07-23b — found, on investigation, to be substantially an artifact of extrapolation into Safe-tier races with no historical support for the implied effect size; 6.4 and 5.3 at earlier stages). This finding replicates out-of-sample on the 2022 cycle (ρ = −0.847, model gain +3.22; corrected 2026-07-24; was −0.707/+12.61 under 2026-07-23b, −0.747/+7.77, then −0.750/+6.79 earlier) — 2022 is again the larger-magnitude correlation, reverting to the ordering both the earliest and 2026-07-23a versions of this paper reported, after a brief 2026-07-23b-era reversal (see Paper I §11's note).

Everything in the paragraph above is treated in this paper as a fixed subroutine. We do not re-estimate the spending response surface, re-derive the covariance model, or replace the optimizer. What changes is the object the optimizer is asked to solve at each point in time, and the budget it is permitted to allocate.

Formally, Paper I solves once:

```
maximize    Σᵢ Φ(μᵢ(Dᵢ)/σᵢ) − γ·Var[Seats]
subject to  Σᵢ partyᵢ ≤ B
```

This paper solves, at each reporting period t:

```
maximize    Σᵢ Φ(μᵢ,ₜ(Dᵢ,ₜ)/σᵢ,ₜ) − γ·Var[Seats]ₜ
subject to  Σᵢ partyᵢ,ₜ ≤ Fₜ
```

where every quantity now carries a time index, and the right-hand side of the budget constraint is deployable capital Fₜ rather than the full-cycle budget B. Sections 3–4 make precise what changes on the left-hand side (the state) and what changes on the right-hand side (the constraint).

---

## 3. The Sequential Allocation Problem

### 3.1 Campaign state

Define the campaign state at reporting period t as

```
Xₜ = { μᵢ,ₜ, σᵢ,ₜ, GBₜ, CashOnHandᵢ,ₜ, CookRatingᵢ,ₜ,
       incumbᵢ, PVIᵢ, RecentSpendᵢ,ₜ, CandidateQualityᵢ,ₜ, ... }
```

for each race i. Several of these are already present in Paper I's static specification (PVI, incumbency, generic ballot, the σᵢ model's dependence on incumbency and race type); what is new is that they are now indexed by t and are permitted to change between periods as new information is observed.

The decision at each period is an allocation of deployable capital across races, {partyᵢ,ₜ}. The transition between periods is governed by an update operator:

```
Xₜ₊₁ = f(Xₜ, informationₜ)
```

We deliberately leave f generic. Section 3.3 discusses candidate instantiations, but the paper's contribution does not depend on committing to one. A version-1 implementation might do nothing more sophisticated than re-running the Paper I estimation pipeline with the latest FEC disbursement snapshot, an updated generic-ballot average, and revised Cook ratings substituted in. A version-2 implementation might apply an explicit Bayesian update to μᵢ,ₜ given a new polling observation. A version-3 implementation might adopt a formal filtering framework (Kalman, particle) to handle the state's uncertainty explicitly. The architecture in this paper is agnostic to which of these f is; only the existence of *some* update operator matters for what follows.

### 3.2 Committed and deployable capital

The object that actually changes the optimizer's feasible set between periods is not the state Xₜ but the budget constraint. Define total campaign budget at period t as the sum of committed and deployable capital:

```
Bₜ = Lₜ + Fₜ
```

where Lₜ is capital already irreversibly committed (booked television time, signed leases, executed contracts — money that cannot be clawed back and reassigned to a different race) and Fₜ is capital available for allocation at period t. The capital account evolves independently of the electoral state:

```
Fₜ₊₁ = Fₜ − new_commitmentsₜ + new_fundraisingₜ
```

The sequential optimizer in Section 4 solves only over Fₜ. Lₜ enters the problem as a fixed floor — added to each race's total spend Dᵢ,ₜ exactly as candidate-committee spending is treated as a floor in Paper I — but is never itself a decision variable.

**Research mode versus operational mode.** Paper I's empirical credibility rests on a specific, load-bearing claim: every quantity in the framework can be estimated from public data (FEC filings, MIT Election Lab results, Cook PVI, generic-ballot polling averages). Lₜ breaks this claim if treated carelessly. FEC bulk disbursement data report money *after* it has been spent; a committee's reserved-but-unaired advertising commitments are not disclosed publicly at the time the reservation is made. We therefore do not claim that Lₜ can be reconstructed exactly from public data, and we explicitly separate the decision framework from its data source:

- **Research mode.** Lₜ is approximated from publicly observable commitment proxies — for example, booked-but-unaired television reservation data published by commercial ad-tracking services (e.g., AdImpact, Medium Buying/CMAG), which report reservations at the time they are booked rather than when the corresponding disbursement is later filed with the FEC. This mode preserves Paper I's public-data commitment at the cost of Lₜ being an approximation rather than ground truth.
- **Operational mode.** Lₜ is supplied directly by the committee's internal accounting ledger. This mode is exact but is not a publicly reproducible research artifact — it is a decision-support deployment of the framework inside an organization that has the data.

This distinction is itself a contribution: it separates *the optimization architecture*, which is a single well-defined object, from *the provenance of one of its inputs*, which is a deployment choice rather than a modeling choice. A reviewer or practitioner can adopt the architecture in either mode without the paper's core claims changing.

### 3.3 Updating race-level estimates

At each reporting period, new information — an FEC filing, a polling release, a Cook rating revision, a candidate's withdrawal — updates one or more components of Xₜ, which propagates through the fixed Paper I machinery: an updated μᵢ,ₜ changes P(winᵢ,ₜ), which changes MSGᵢ,ₜ, which changes the optimizer's recommended allocation of Fₜ. Section 3.1 leaves f fully generic as a theoretical object; an empirical implementation, however, must commit to something concrete, and the choice matters more than it might first appear.

A naive instantiation of f — simply re-running Paper I's estimation pipeline on the latest polling, FEC, and Cook-rating snapshot at every reporting period — feeds raw period-to-period noise directly into μᵢ,ₜ. Real polling and fundraising signals are noisy at the weekly-to-biweekly frequency this architecture operates at; campaigns do not, and should not, react to every single-poll bounce, and an optimizer that does will recommend allocations that thrash from period to period in a way no practitioner would follow. We therefore define a baseline f for the empirical work in Sections 6–7 that smooths the raw re-estimate rather than passing it through directly:

```
μ̂ᵢ,ₜ = λ · μ̂ᵢ,ₜ₋₁ + (1 − λ) · μᵢ,ₜ^raw
```

where μᵢ,ₜ^raw is Paper I's pipeline re-estimated on the period-t data snapshot and λ ∈ (0, 1) is a smoothing constant (we use λ = 0.7 as a starting value, giving the raw signal roughly a two-to-three-period half-life; Section 8 flags this as a specific, untested modeling choice rather than a derived one). σᵢ,ₜ is smoothed identically. This is deliberately the simplest possible filter — an exponential moving average with no explicit treatment of estimation uncertainty — chosen so that Sections 6–7 have something concrete and reproducible to run, not because it is the theoretically preferred choice. A Bayesian update or a formal Kalman or particle filter would replace this EMA with an update that also carries an explicit posterior variance for μᵢ,ₜ, which the receding-horizon optimizer does not currently use; we view that as the natural next refinement rather than a requirement for this paper's contribution. The distinction between f as a general theoretical object (Section 3.1) and this f_baseline as the specific empirical instantiation used here is maintained throughout: an operational deployment is free to substitute a different f_baseline without changing anything else in the architecture.

---

## 4. Sequential Optimization Over Deployable Capital

The optimization problem solved at each reporting period is

```
maximize     Σᵢ Φ(μᵢ,ₜ(Dᵢ,ₜ)/σᵢ,ₜ) − γ·Var[Seats]ₜ
subject to   Σᵢ partyᵢ,ₜ ≤ Fₜ
             0 ≤ partyᵢ,ₜ ≤ cap · Fₜ
             Dᵢ,ₜ = cand_floorᵢ,ₜ + Lᵢ,ₜ + partyᵢ,ₜ
```

This is, mechanically, the identical SLSQP problem solved in Paper I, with two substitutions: the budget constraint uses deployable capital Fₜ rather than the full-cycle budget, and each race's already-committed capital Lᵢ,ₜ is added to the spending floor exactly as candidate-committee spending is. No new solver, objective, or constraint structure is introduced. The pseudocode for the resulting receding-horizon procedure is:

```
for each reporting period t:
    observe new information
    update Xₜ → Xₜ₊₁         (Section 3.3)
    update capital account: Fₜ₊₁ = Fₜ − new_commitmentsₜ + new_fundraisingₜ
    recompute μ, σ, MSG from updated state
    solve the optimizer over Fₜ₊₁, with Lₜ₊₁ as a fixed floor
    output: recommended allocation of Fₜ₊₁
```

This is a receding-horizon (model-predictive-control-style) procedure: at each period, the full remaining problem is re-solved from the current state, and only the current period's decision is executed before the next observation arrives. We note explicitly that this is *not* equivalent to solving a single multi-period dynamic program over the whole cycle — it is a sequence of static re-solves. Section 5 identifies precisely what this myopic re-solving discards.

---

## 5. Reserving Optionality: The Value of Flexibility

### 5.1 What the receding-horizon solve assumes away

The optimizer in Section 4 implicitly assumes that all currently deployable capital should be deployed now, to the extent the budget constraint and cap allow. But if a race's polling is volatile and a new fundraising or polling report is due in two weeks, spending the marginal dollar today forecloses the ability to spend it more efficiently once that report resolves some of the uncertainty in μᵢ. Deployable capital retained rather than committed preserves the ability to respond to information that has not yet arrived. The static, myopic re-solve in Section 4 has no mechanism for valuing this: it treats Fₜ as something to be spent down to the constraint boundary each period, with no term rewarding patience.

### 5.2 The real-options analogy

Paper I already introduces a finance analogy for open-seat races: higher structural volatility (σᵢ) simultaneously raises a race's baseline win probability and lowers its marginal seat gain per dollar, in direct analogy to how higher implied volatility raises an option's price while lowering its delta. Uncommitted campaign capital extends this analogy naturally, and in a different dimension. Committing capital to a race is analogous to *exercising* an option: it converts flexible, redeployable capital into a fixed position, forfeiting the ability to wait for resolving information. The correspondence is direct:

| Finance | Campaign allocation |
|---|---|
| Cash / uninvested capital | Uncommitted (deployable) budget, Fₜ |
| Exercise decision | Commit spending to a race |
| Underlying uncertainty | Polling, fundraising, candidate events |
| Expiration | Election Day |
| Early-exercise decision | Spend now vs. retain flexibility |

Under this analogy, the sequential optimizer in Section 4 is not merely deciding *where* to spend; implicitly, by spending down Fₜ each period, it is also deciding — without being asked to — *when* to give up flexibility. That is a materially different decision than the one the static architecture is designed to make well.

### 5.3 A stated limitation, not a solved problem

We do not solve this problem in the present paper. Doing so would require a stochastic control formulation — an explicit model of how information resolves over time and an optimal-stopping or continuation-value calculation (in the tradition of, e.g., Longstaff–Schwartz-style regression-based methods for American option pricing) — that would change the nature of the contribution from an operational architecture to a stochastic control paper. We state the limitation precisely instead:

> The sequential optimizer in Section 4 assumes all currently deployable capital should be allocated immediately, subject to the period's constraints. In practice, retaining a portion of deployable capital uncommitted preserves flexibility in the presence of future information arrivals, and this flexibility has positive option value analogous to the early-exercise problem in American-style financial options. Quantifying this option value requires a stochastic control formulation and is left for future work.

**Update (2026-07-22): this future work is now done.** `docs/paper3_draft.md` specifies exactly the stochastic control formulation this section calls for — the state-transition law for opponent reaction, national-environment, and idiosyncratic uncertainty this section leaves generic — and solves it by the Longstaff–Schwartz regression-based method named above, not a different method than the one anticipated here. Its current, five-times-corrected result: the value of waiting (Θ) is substantially positive at the live 2026 decision, and every tested scenario recommends holding the reserve rather than deploying it, consistent with real committees' observed spending patterns (95%+ of independent-expenditure spending arrives in the final two months of a cycle) rather than contradicting them, as an earlier, since-superseded pass at the same calculation did. See Section 8 below for the full result and what remains open even after that resolution.

The architectural implication, short of solving for the option value explicitly, is that the pipeline in Section 4 should be understood as producing a recommended allocation of Fₜ *conditional on choosing to deploy it now*, with an explicit "reserve" step available to the practitioner as a discretionary override rather than a modeled decision:

```
update state
    ↓
estimate deployable capital (Fₜ)
    ↓
optimize deployment (Section 4)
    ↓
reserve optionality (discretionary; not yet modeled)
    ↓
allocate remaining capital
```

This is a meaningful extension over Paper I even without a solved stopping rule: it makes explicit, for the first time in this research program, that a dollar not yet committed is not simply a dollar with zero contribution to expected seats — it is a claim on future flexibility with its own value, distinct from the value of the marginal dollar spent.

### 5.4 Time decay of option value

The real-options analogy in Section 5.2 is incomplete without its time dimension. An election cycle has a hard, known expiration date T (Election Day). Standard option pricing decomposes an option's value into intrinsic value and time value, and the latter — conventionally denoted Θ — decays toward zero as expiration approaches: with less time left for the underlying to move, the value of retaining the right to wait shrinks. The same logic applies directly to uncommitted campaign capital, and the draft above is incomplete for omitting it.

Early in a cycle (say, March of an election year), a large amount of information has yet to arrive — primary results, several fundraising quarters, multiple rounds of polling, redistricting rulings, retirements — and capital retained at that point preserves the ability to respond to nearly all of it. Late in the cycle (say, late October), almost all of the information that will arrive before Election Day already has; there are few remaining reporting periods in which new information could change the optimal allocation, and progressively less time to act on it even where it could. The option value of a dollar held uncommitted therefore strictly decreases as t → T, and it is exhausted entirely at Election Day, when any capital not yet spent has permanently forfeited its only opportunity to affect the outcome.

This yields a direct, qualitative implication that the architecture in Sections 3–4 does not generate on its own: rational spending behavior, under the real-options view, should *accelerate* as the cycle progresses — not because marginal seat gain itself is rising (Paper I gives no reason to expect that), but because the opportunity cost of committing capital now rather than waiting falls toward zero as expiration approaches. This is consistent with the well-documented empirical pattern of late-cycle spending surges in House races, and this framework gives that pattern a specific theoretical mechanism — the shrinking Θ of uncommitted capital — rather than leaving it as an unexplained stylized fact. We do not derive a functional form for Θ(t) here; we note only that any future formalization of Section 5.3's stopping problem must impose Θ(t) → 0 as t → T as a boundary condition.

#### 5.4.1 Implication for the receding-horizon solve

Section 4's receding-horizon optimizer has no Θ term. At each period it treats all of Fₜ as capital to be deployed immediately, up to the concentration cap, because nothing in its objective rewards holding capital back. Combined with Section 5.4's decay logic, this predicts a specific and testable failure mode: absent any modeled cost of forgoing flexibility, the greedy solve should recommend deploying capital considerably earlier in the cycle than a Θ-respecting rational actor would — and, in particular, earlier than DCCC's actual historical spending pattern, which is a matter of public record.

We do not treat this as a defect to be patched before running the Section 6 simulation. Instead, Section 6 treats the *gap* between the greedy model's recommended deployment schedule and DCCC's actual deployment schedule as an empirical object of interest in its own right — a revealed-preference estimate of the option value the committee implicitly assigns to retained flexibility, which the static model has no mechanism to price directly. A large, systematic gap concentrated in high-volatility races would be a striking piece of indirect evidence for the option-value account of Section 5.2–5.4; a small or race-invariant gap would suggest the effect is not first-order and that immediate deployment is a reasonable approximation in practice.

### 5.5 Two different assets

This motivates a philosophical distinction that did not need to exist in Paper I. Paper I values the marginal campaign *dollar* — what one additional dollar of spending, deployed now, contributes to expected seats. This paper's architecture, even without solving the stopping problem in Section 5.3, makes explicit that a second asset exists: the marginal dollar of *flexibility* — the value of a dollar not yet committed, held against the possibility that better information will make a future allocation more efficient than today's. One asset is spent; the other is preserved. Paper I has no language for the second asset because a one-shot allocation problem has no "later" for flexibility to matter. A sequential problem does. We view identifying this second asset — without yet pricing it — as this paper's clearest point of intellectual departure from Paper I.

---

## 6. Simulation: Replaying 2022 and 2024 Sequentially

*[Methodology only; results pending implementation.]*

### 6.1 Baseline instantiation

Running the simulation requires committing to a concrete version of every object Sections 3–5 leave generic. We use the EMA baseline f defined in Section 3.3 (λ = 0.7) to update μᵢ,ₜ and σᵢ,ₜ between reporting periods; committed capital Lₜ from realized disbursed spend in research mode (`RealizedSpendCommitmentSource`, a conservative lower bound — see Section 7.1/8 for why the ad-reservation proxy sketched in Section 3.2 remains an unimplemented stub rather than the operative source here); and the unmodified Section 4 receding-horizon optimizer to produce each period's recommended allocation. No other component of the architecture is modified for the simulation.

### 6.2 Design: one-step-ahead evaluation, not a closed-loop rollout

A naive design would reconstruct the campaign state Xₜ at each historical FEC reporting date, feed it to the receding-horizon optimizer, treat the optimizer's recommendation as the period's actual spending decision, and roll forward autoregressively — with each subsequent period's state built partly from the model's own prior recommendations rather than from the historical record.

This design is invalid, and we do not use it. Historical polling, fundraising, and Cook-rating data available as of any date t+1 are themselves a function of what DCCC actually spent through date t — not of what this model would have recommended spending. If the model recommends front-loaded spending in a race where DCCC in fact held back, the August polling data used to reconstruct the state at the next period reflects the world in which that money was never spent. Feeding that data back into a rollout that has *implicitly* assumed the money was spent optimizes against a state variable that is contaminated by a counterfactual that never happened. Rolled forward across many periods, this contamination compounds, and no property of the resulting trajectory can be read as "what would actually have happened" under the model's advice.

We therefore evaluate the architecture one step at a time rather than as a closed-loop rollout. At each historical reporting date t, we reconstruct Xₜ from data that was actually available as of that date — a snapshot of the real, realized history, never of the model's own hypothetical past decisions — and compare the receding-horizon optimizer's single-period recommendation for period t against DCCC's actual single-period allocation for that same period, holding the state fixed at its true historical value. Every comparison conditions only on real historical information; the model is never asked to act on a state that its own prior recommendations helped produce, because its prior recommendations are never fed back into the state. This is analogous to one-step-ahead (open-loop) backtesting in time-series forecasting, or off-policy evaluation using logged data rather than counterfactual rollouts: it does not require, and does not claim, an accurate simulator of how the world would have responded to the model's decisions — only a comparison of what the model would have recommended, given real history, against what was actually done.

This design choice has a direct consequence for what the simulation can and cannot show. It can show whether, by how much, and at which points in the cycle the model's period-by-period recommendation diverges from DCCC's actual behavior. It cannot show whether following the model's advice over many consecutive periods would have compounded into a better final seat outcome, since that would require knowing how polling, fundraising, and opponent response would actually have evolved under a different spending history — precisely the counterfactual this design does not attempt to construct. We treat this as an honest and necessary scope reduction rather than a limitation to obscure; Section 8 restates it explicitly.

### 6.3 What the comparison is designed to show

The resulting sequence of one-step-ahead recommendations is compared against (a) DCCC's actual period-by-period spending and (b) Paper I's single, full-cycle-budget static recommendation. This comparison is designed to answer three questions. Does the *sum* of the model's one-step-ahead recommendations across the cycle converge to something close to Paper I's static, full-budget recommendation, as it should if the sequential decomposition is a reasonable restatement of the same underlying problem? Does the model's recommended *timing* diverge systematically from DCCC's actual timing — in particular, per Section 5.4.1, do we observe the predicted pattern of the greedy solve recommending earlier deployment than DCCC's actual, presumably more patient, behavior, and does the size of that gap correlate with the volatility of each race's estimated μᵢ,ₜ, as the option-value account in Section 5 would predict? And are there specific historical reporting dates at which the one-step-ahead recommendation diverges sharply from what DCCC actually did, which would be natural case studies for Section 5's flexibility discussion?

We do not report simulation results in this draft; this section specifies the methodology to be implemented as the paper's primary empirical section.

## 7. Live Application: The 2026 Cycle

The architecture in Sections 3–5 is designed to be run prospectively rather than only retrospectively. Operating it against the live 2026 cycle — ingesting FEC filings, generic-ballot updates, and Cook rating revisions as they are released, and re-solving the deployable-capital optimization at each reporting period — turns the paper from a retrospective methodological exercise into an operational demonstration. In research mode (Section 3.2), this can be run and reported using exclusively public data, with Lₜ approximated from realized-spend data (Section 7.1) or, in a committee's own operational mode, from its internal ledger.

Note that the counterfactual-endogeneity problem identified in Section 6.2 is specific to *retrospective* replay and does not recur here: a live deployment's recommendations, if followed, become part of the actual historical record that subsequent polling and fundraising data reflect, rather than a hypothetical alternative history competing with the record that was actually observed. Live application is, in this sense, the only setting in which the architecture's multi-period recommendations can be evaluated against real, uncontaminated outcomes rather than only one step at a time.

### 7.1 First live reporting period (2026-07-08, rerun 2026-07-23 — see note after the Result paragraph)

The architecture was run once against the live, in-progress 2026 cycle, using the unmodified Section 4 optimizer and the following inputs:

- **Race universe**: `build_universe(cycle=2026)`, 434 races. PVI reuses the same `(2016, 2020)` presidential-year pair as the 2022 and 2024 cycles, since this repository has no district-level 2024 presidential results yet; several states have mid-decade 2026 redistricting in progress that is not reflected in this universe.
- **Budget (Bₜ)**: **$394.3M**, derived as the average of the 2018 and 2022 midterm party-controlled budgets ($315.6M and $322.0M respectively, computed the same way as Paper I's headline $465.0M figure for 2024), each inflated to 2026-equivalent dollars using BLS CPI-U (series CUUR0000SA0: 252.038 in November 2018, 297.711 in November 2022, projected to 337.9 in November 2026 by applying the trailing year-over-year rate as of May 2026, +4.25%, to November 2025's 324.122). This is a historical-comparable-cycle estimate, not a live fundraising-pace projection off the committee's actual 2025–2026 receipts, which this paper does not attempt.
- **Generic ballot**: a live point-estimate, **D+5.02**, the 21-day trailing average of raw polls from `scripts/fetch_polling.py` (VoteHub API) as of 2026-07-07. Consistent with Section 3.3's framing, this is used as a single, periodically-refreshed per-cycle constant — structurally the same role every other cycle's static GB value plays in `coef.alpha3` — not a continuously time-varying input.
- **Lₜ**: `RealizedSpendCommitmentSource`, combining real coordinated-expenditure (FEC Schedule F) and independent-expenditure (FEC Schedule E, date-bucketed via the Section 6 dated-IE machinery) spend already disbursed by DCCC-aligned committees. Result: **Lₜ = $911,047** — small relative to the budget, but *not* because the cycle is still far from Election Day: as of the run date (2026-07-08), Election Day (2026-11-03) is approximately **four months** away, not the sixteen an earlier draft of this section stated (that figure appears to have been computed as if the run occurred in July 2025). The small Lₜ instead reflects that this repository's only committed-capital proxy (`RealizedSpendCommitmentSource`) captures money already disbursed, which lags true committed-but-unaired reservations severely late in a cycle when TV bookings run well ahead of disbursement — see the revised discussion in Section 8. With only four months remaining, the low Lₜ is a data-source limitation, not primarily a reflection of how early the cycle is.

**Result**: optimizer status `optimal`; **Fₜ = $393,396,585**; expected seats **235.83** (of 434 modeled races) — corrected 2026-07-24 (persuasion-ceiling fix), from 255.54 (2026-07-23c, codebase audit: NRCC/HMP/CLF FEC committee-ID fix + σ-model fix + optimizer-diagnostic fix), itself from 247.97 (2026-07-23, second pass), itself from an intermediate 241.08, itself corrected from the original run's Fₜ=$393,388,953/241.12. Unlike every correction before it, **the 2026-07-24 move (255.54→235.83) is a decrease, not an increase** — the persuasion ceiling caps exactly the near-zero-floor extrapolation that had been inflating this figure (and Table 5's non-competitive concentration) since the 2026-07-23c σ-model fix removed the accidental suppressor that previously masked it. The 241.12→241.08 move was the ballot-exclusion fix (three candidate committees — Weil/FL-06, Krishnamoorthi/IL-08, Trone/MD-06 — misattributed as 2026 House candidates, inflating their districts' floors); the 241.08→247.97 move was `data/elections.py`'s MN/ND fix changing the underlying margin-model coefficients; the 247.97→255.54 move was from the 2026-07-23c codebase-audit fixes — see the top-of-document flag in `FINDINGS.md` for the fix history. See `docs/full_derivation.md` §IV.23 for the full explanation of the earlier corrections. Budget and Lₜ below are unaffected by any of these fixes. The party-controlled portion of `budget_used` exactly exhausts Fₜ, consistent with positive MSG throughout the competitive pool. Figure 2 (`outputs/allocation_2026_live.png`, generated by `scripts/plot_2026_live_allocation.py`) shows the top 25 races by model-recommended total party spend, decomposed into already-committed (Lₜ, by race) and recommended additional deployment; the underlying table is `outputs/allocation_2026_live.csv`. The single largest individual recommended allocations remain concentrated in Lean R / Toss-Up races with little or no observed spending yet — but reporting only the top rows understates how broadly the budget is actually spread, and the full breakdown by Cook category is a more important result of this run than any individual district:

*Provenance note (added 2026-07-16, Paper III audit): the figures above are a dated snapshot of the 2026-07-08 run, not a value this document should be treated as the ongoing source of truth for. `BUDGET_2026` is no longer a hand-typed literal — it is derived by `backtest.model.budget.estimate_budget_2026()` from the 2018/2022 party-controlled budgets (computed live via `build_universe()`) and the CPI-U inputs in `config.yaml`'s `budget_2026_projection:` block. Every subsequent re-run of `scripts/plot_2026_live_allocation.py` writes the current `as_of` date, Lₜ, Fₜ, and days-remaining-to-Election-Day to `data/processed/live_2026_state.json` — that file, not this paragraph, is what `scripts/solve_bellman_lsm.py` and Paper III now read Fₜ/today/Election Day from.*

Table 5: Recommended Fₜ allocation by Cook category (2026-07-24 run, persuasion-ceiling fix)

Cook Category | n | Recommended | % of Fₜ
Safe D | 141 | $14.3M | 3.6%
Likely D | 40 | $29.1M | 7.4%
Lean D | 30 | $34.6M | 8.8%
Toss-Up | 15 | $54.5M | 13.8%
Lean R | 10 | $59.2M | 15.0%
Likely R | 37 | $142.1M | 36.0%
Safe R | 161 | $60.5M | 15.4%

(Was, 2026-07-23c: Safe D $5.9M/1.5%, Likely D $14.4M/3.7%, Lean D $20.3M/5.2%, Toss-Up $37.0M/9.4%, Lean R $58.4M/14.8%, Likely R $148.2M/37.6%, Safe R $110.1M/27.9%.)

**Corrected 2026-07-24 (persuasion-ceiling fix): the non-competitive concentration this section flagged as a real, named failure mode is substantially reduced, though not eliminated.** Likely R + Safe R combined falls to **51.4% of Fₜ** (was 76.8% under 2026-07-23c, 65.5% before that) — the ceiling caps exactly the mechanism this section diagnosed (near-zero candidate-committee floors giving the log-ratio gradient room to blow up), and Safe R specifically drops from 27.9% to 15.4%. The remaining concentration is now concentrated almost entirely in Likely R (36.0%, barely changed from 37.6%) rather than spread further into Safe R — consistent with the ceiling's design: `C_i` scales with a race's own win probability at its floor, so races that are genuinely more persuadable (even if currently Cook-rated Likely R) retain more headroom than races that are structurally hopeless. This is not full resolution of the concentration concern this section names — Likely R is still a large, arguably surprising share of a "where does the marginal dollar matter most" recommendation — but it is a real, mechanism-consistent improvement, not a cosmetic one. The specific district examples and hand-verification below are from the pre-2026-07-24 run and have not been recomputed; the underlying mechanism they illustrate (near-zero floors driving an inflated gradient) is exactly what the ceiling fix targets, so those specific numbers should now be read as historical evidence for the diagnosis, not as a current description of the optimizer's behavior.

This result reads as more concerning, not less, once the actual remaining horizon is corrected: as of this run, Election Day is approximately four months away, not sixteen (see the corrected budget note above). Section 5.4's Θ-decay argument says option value should be largest early and shrink to zero at T — with only four months left, a Θ-respecting allocator should already be well past the point of broad exploratory spending and into concentrated, high-conviction deployment. A patience-blind model spreading 51.4% of Fₜ into non-competitive seats at four months out (corrected 2026-07-24, persuasion-ceiling fix; was 76.8% under 2026-07-23c, 65.5% before that) remains a real concern even after the ceiling fix substantially reduced it, and is still a materially worse failure than the same behavior would be at sixteen months out, where some exploratory breadth might be defensible while cheap information is still arriving. We do not consider this evidence against the framework's mathematical core — it is precisely the predicted failure mode of a Θ-free receding-horizon solve, now partially but not fully mitigated by the persuasion ceiling — but it means Section 7.1's raw output should not be read as a deployment recommendation as-is, and the case for imposing Section 5.3's discretionary reserve step before following it remains at least as strong as the original draft's "sixteen months" framing implied. **(Update, 2026-07-22: this qualitative call for a discretionary reserve step is now a quantitative one — see Section 8's report of Paper III's Θ result, which recommends reserving the entire deployable budget at this decision point, not a partial hedge.)**

This is a legitimate first application of the architecture, not a demonstration run on synthetic inputs — but it inherits every approximation stated above (PVI proxy years, unresolved mid-decade redistricting, a historical- rather than fundraising-pace-based budget, and Cook ratings that are algorithmically derived rather than sourced from a proprietary feed, since this repository has no 2026 Cook ratings file), and it now inherits a second, empirically-demonstrated one: absent a Θ term, the model's raw recommendation broadly over-spreads into non-competitive territory rather than concentrating where a practitioner would expect. Section 8 restates these as standing limitations of the current live application, not defects introduced by this specific run.

### 7.2 Follow-up (added 2026-07-22): the near-zero-floor mechanism this section already named, now checked directly against real data

Section 7.1's own diagnosis of the original 65.5% result (76.8% under 2026-07-23c, now 51.4% under the 2026-07-24 persuasion-ceiling fix) named "every one of 434 races still has near-zero candidate-committee floor spending" as one of the mechanisms letting the optimizer over-spread capital — the persuasion ceiling, added after this diagnosis, directly caps that mechanism and accounts for most of the improvement. At the time, there was no way to check that directly — this repository had no per-filing-date candidate-committee data. Paper III's Section 12 (`docs/theta_followup_plan.md`) has since built exactly that (a dated candidate-periodic-reports panel, `data_catalog.md` Section 2.7, now covering 2012–2026), which makes it possible to test this section's own diagnosis against real numbers rather than leave it qualitative.

**Confirmed directly**: as of 2026-07-21, nearly every one of the top model-recommended races had `already_committed = $0` in `plot_2026_live_allocation.py`'s own output — the floor genuinely is near zero for dozens of races simultaneously, not a hypothetical. `scripts/plot_allocator_comparison_2026.py` visualizes this directly (`outputs/allocator_comparison_2026_live_competitive.png`, `_all.png`): real, dated spend to date (candidate-committee filings plus coordinated/IE) plotted against the model's target and a trend-line forecast, across both the 55-race competitive universe and the full 434-race universe.

**A naive "seat gain from optimal deployment" estimate computed from this run was not trustworthy under the pre-ceiling pipeline, for the same near-zero-floor mechanism this section names — and the persuasion-ceiling fix (2026-07-24) resolves most of the gap directly.** Comparing the model-optimal expected-seats figure against expected seats if the deployable reserve Fₜ is not spent at all now gives a raw gain of **+9.23 seats** (optimal 239.46 vs. no-further-deployment 230.23, both under the current ceiling-fixed pipeline against the current 434-race live universe and $393.4M Fₜ), down from the pre-ceiling pipeline's **+27.4 seats** (2026-07-23c) — a figure this section already flagged as implausibly large next to Paper I's backtest finding. The gap closed almost entirely because the mechanism `scripts/investigate_msg_low_d_extrapolation.py` diagnosed — the margin model's spending elasticity, disproportionately estimated from Safe-tier low-spend repeat-challenger pairs (85 of 118), amplified rather than averaged across dozens of simultaneously near-zero-floor competitive races — is exactly what the persuasion ceiling caps.

`scripts/solve_2026_optimal_forecast_floors.py` re-solves the same optimizer using floors projected forward to Election Day at the calibrated per-tier candidate-committee trickle rate (Paper III Section 12.7's D-side rate, generalized to both parties here — projecting D forward while leaving R frozen would trade one asymmetry for another) instead of today's near-zero ones. **Corrected 2026-07-24 (persuasion-ceiling fix): this now gives +9.23 seats as well** (239.46 optimal vs. 230.23 no-further-deployment) **— converging with the immediate-floor estimate above, which was not true under either prior pipeline** (2026-07-23c: +27.4 immediate-floor vs. +21.49 forecast-floor; a large, floor-maturity-sensitive gap this section previously flagged as evidence of remaining sensitivity). That the two estimates now agree closely is itself evidence the ceiling fix addressed the right mechanism: forecasting floors forward mattered primarily because it moved races out of the near-zero-floor extrapolation regime, and the ceiling now does that same job directly, regardless of whether floors are measured today or projected forward. The remaining known overestimate sources are unchanged: outside-group (coordinated/IE) spending is held flat rather than projected forward, and this project's own research (`docs/theta_followup_plan.md` Section 10) already found that component to be the most extreme back-loader of all (95%+ arrives in the final two months) — a smooth trend line is a poor model for it specifically. Even the candidate-side forecast uses a smoothed average rate against spending that is known to be lumpy and to accelerate near Election Day, not linear.

**The number that should actually be trusted for "how much does optimal allocation buy" remains Paper I's validated backtest finding — now +2.83 seats (2024) / +3.22 seats (2022 OOS), both corrected 2026-07-24 — but the 2026 live estimate is no longer wildly inconsistent with it the way the pre-ceiling +27.4/+21.49 figures were.** The live 2026 estimate (+9.23) sits above Paper I's backtest range, which remains the more defensible number since it is validated against a completed cycle's real outcomes rather than a live, still-uncertain one — but the two are now within the same order of magnitude, not off by a factor of two or three as before. Both answer a different, more extreme question than Paper I's backtest does — "optimal vs. deploying nothing further," which no real committee would do — rather than "optimal vs. what a real committee actually chose." The live 2026 estimate is directionally consistent (optimal deployment helps) and, post-ceiling-fix, no longer requires the caveat that it is a magnitude this project's own historical validation cannot support.

**A related but distinct follow-up: this section's floor-maturity fix and Paper III's Θ solve are separate corrections that point in the same direction.** This section addresses *how much* optimal deployment is worth (a magnitude question, resolved by projecting floors forward). It does not address *whether* to deploy the reserve at all right now — that is Section 5.3/8's question, and Paper III has since answered it: at the live 2026 decision, Θ(0) is substantially positive and every tested scenario recommends holding the reserve rather than deploying it. The two corrections are complementary, not competing — one says the naive live seat-gain estimate is inflated by an immature floor, the other says the premise of deploying the reserve immediately at all is itself not what a Θ-aware policy would choose. See Section 8 for the full result.

---

## 8. Limitations

This paper inherits every limitation stated in Paper I regarding the underlying valuation model (the small repeat-challenger sample, the divergence between the expected-seats and majority-probability objectives, the financial-only view of campaign resources). It adds several of its own.

**The state-update operator remains only partially specified.** Section 3.1 leaves f generic as a theoretical object, and Section 3.3 commits to a single concrete instantiation — an exponential moving average with λ = 0.7 — for the empirical work in Sections 6–7. That choice was made to keep the simulation reproducible and to avoid feeding raw period-to-period polling noise directly into the optimizer, not because it is derived from data. Neither λ = 0.7 nor the EMA functional form itself is validated against any alternative in this paper; a Bayesian update or Kalman/particle filter, which would also carry an explicit posterior variance into the optimizer, is a natural refinement this paper does not implement.

**Lₜ is an approximation in research mode.** Section 3.2's ad-reservation commitment proxy (`AdReservationProxySource`) remains an unimplemented stub — no affordable public feed for booked-but-unaired reservations was found (Section 7.1 uses `RealizedSpendCommitmentSource` instead, which is real but captures only money already disbursed, a conservative lower bound that misses reservations booked but not yet aired or paid). The gap between either proxy and a committee's true internal commitment ledger is itself unmeasured; if it is systematically biased, the resulting Fₜ, and therefore the entire downstream optimization, inherits that bias.

**The 2026 live application (Section 7.1) carries its own approximations beyond Lₜ.** PVI reuses the 2022/2024 proxy presidential-year pair rather than incorporating 2024 results (not present in this repository); several states' mid-decade 2026 redistricting is not reflected in the race universe at all; the $394.3M budget figure is a historical-comparable-cycle estimate (2018/2022 midterm average, inflation-adjusted) rather than a live projection from the committee's actual fundraising pace; and 2026 Cook ratings are algorithmically derived from PVI and incumbency rather than sourced from a proprietary feed, so they inherit the PVI approximation. None of these block the run — Section 7.1's result is real, not synthetic — but each is a named, specific source of imprecision in that result, not a solved problem.

**The option-value problem is identified, not solved.** Section 5 states a real limitation of the receding-horizon architecture rather than resolving it. Any live or historical deployment of this architecture is, until that work is done, making an implicit assumption — that immediate deployment of all deployable capital is preferable to reserving some of it — that has not been justified.

**Superseded (2026-07-22).** That work is now done: `docs/paper3_draft.md` specifies the state-transition law this section's "until that work is done" refers to, and solves the resulting Bellman equation by regression-based Monte Carlo, corrected five times as errors were found (each correction, and the current result, are logged in `docs/theta_followup_plan.md`). The implicit assumption this paragraph flags as unjustified has now been tested directly, and found **not** to hold: at the live 2026 decision, a Θ-aware policy recommends holding the entire deployable reserve rather than deploying it immediately, in every scenario tested (Θ(0) = +1.328 to +1.719 expected seats, live 98-day horizon — corrected 2026-07-27 to the current, persuasion-ceiling-fixed pipeline figures already reported in Paper III §8.6, which this paragraph had not yet been updated to match; was +1.350 to +1.734 under 2026-07-23c, +0.997 to +1.808 under the 7-cycle-trickle, pre-audit pipeline). A genuinely continuous, sequential version of the same decision (ruling out "the binary framing is masking a middle option") reaches the same conclusion — that specific re-run is still pending against the 2026-07-23c pipeline as of this pass. What remains open after this resolution: the opponent-reaction parameter is applied to a spending channel (candidate-committee organic growth) it was not originally estimated on, and race-level idiosyncratic uncertainty is still a rate-borrowed proxy rather than a fitted process — see Paper III Section 8.6/§V.5 of `docs/full_derivation.md` for the complete, current scope boundary.

**The receding-horizon solve is expected to front-load spending relative to actual practice — and Section 7.1 shows this is not a marginal effect.** Because Section 4 has no Θ term (Section 5.4), the greedy per-period solve should systematically recommend deploying capital earlier in the cycle, and more broadly across marginally-plausible races, than DCCC's actual, presumably more patient, behavior. Section 6.3 turns the historical version of this predicted gap into a diagnostic rather than a defect; Section 7.1's live run turns it into a measured one — 51.4% of the recommended Fₜ went to Safe R/Likely R seats in the first live reporting period (corrected 2026-07-24, persuasion-ceiling fix; was 76.8% under 2026-07-23c, 65.5% before that), not the visibly competitive tier. Until Section 5.3's stopping problem is solved, any practitioner using Section 4's raw output directly should treat it as an upper bound on how much of Fₜ to deploy immediately and how widely to spread it, not as a literal recommendation.

**Superseded (2026-07-22): Section 5.3's stopping problem is now solved (see the note above).** The prediction in this paragraph — that a Θ-aware policy would front-load *less* than the greedy Section 4 solve — is confirmed, and confirmed more starkly than "less broadly" implies: at the live 2026 decision, the Θ-aware policy recommends deploying essentially none of the reserve right now, not merely a smaller or more concentrated slice of it. The 65.5%/76.8%/51.4% figures (pre-fix, 2026-07-23c, and 2026-07-24 respectively) remain a correct description of what the Θ-*free* Section 4 solve actually recommended in each version of that run; it is no longer evidence of a gap this paper could only diagnose, not close.

**The one-step-ahead simulation design cannot validate multi-period counterfactual outcomes.** Section 6.2 evaluates the architecture one reporting period at a time, against real historical state, specifically to avoid feeding the model's own hypothetical past decisions back into its state — a closed-loop rollout using historical polling and fundraising data would optimize against a state variable contaminated by a counterfactual that never occurred. The one-step-ahead design solves that contamination problem, but at a real cost: it can show that the model's period-by-period recommendation diverges from DCCC's actual behavior, but it cannot show that following the model's advice across many consecutive periods would have produced a better realized outcome, since the polling and fundraising path that would actually have resulted from different spending decisions is unobserved. Only the live 2026 application (Section 7) evaluates the architecture's multi-period recommendations against real, uncontaminated outcomes.

**The receding-horizon procedure is not shown to be dynamically consistent.** A sequence of myopic re-solves is not guaranteed to match the solution of a true multi-period dynamic program, even setting aside the option-value question in Section 5. We do not attempt that comparison here.

---

## 9. Conclusion

Paper I asks what a campaign dollar is worth. This paper asks a related but distinct question: given that a committee cannot spend all its dollars at once, cannot un-spend a dollar once committed, and cannot know today what it will learn tomorrow, how should it operate the valuation model from Paper I as a live decision system rather than a one-time calculation? The answer we propose is architectural rather than mathematical: separate committed from deployable capital; re-solve Paper I's existing optimizer over deployable capital at each reporting period as new information updates the campaign state; and — short of solving it — make explicit that capital retained rather than spent is itself a valuable, and currently unpriced, asset. Together, the two papers form a single research program in the pattern of institutional asset management: Paper I is the pricing model — how to value the next campaign dollar; this paper is the portfolio management system — how to deploy those dollars, and when not to, over the course of an election cycle.

**Update (2026-07-22): "currently unpriced" no longer describes the state of this research program.** A third paper (`docs/paper3_draft.md`) now prices that asset — specifying the state-transition process this paper leaves generic and solving the resulting optimal-stopping problem. The three-paper program now reads: Paper I prices the next dollar; this paper builds the system that deploys it repeatedly; Paper III prices the alternative of *not* deploying it, and reports that at the live 2026 decision, not deploying wins.

---

*Draft status: Sections 1–5 and 8–9 are conceptually complete pending final wording. Section 6 (historical simulation) describes methodology only; no one-step-ahead historical results are reported in this draft. **Update, 2026-07-23c:** `scripts/run_dynamic_backtest.py` has since been run for both cycles under the current (codebase-audit-fixed) pipeline — 2024: 38 one-step-ahead periods, `dynamic_timing_2024.csv`, timing-gap-vs-volatility correlation −0.665, total model-vs-actual deployment gap $13.39B (model front-loads relative to DCCC's actual pacing, consistent with this section's own Θ-absence prediction); 2022: 38 periods, `dynamic_timing_2022.csv`, correlation −0.594, gap $9.44B. These are real numbers, not yet written into Section 6's prose — flagged here as available raw material rather than interpreted, since turning them into a proper Section 6 results narrative is authorial work this pass intentionally left undone rather than drafted mechanically. Section 7.1 reports one real, live result (2026-07-08, re-run 2026-07-23c, then 2026-07-24 for the persuasion-ceiling fix), including the finding that 51.4% of recommended capital in that run went to non-competitive seats (was 76.8% under 2026-07-23c, 65.5% pre-fix) — see that section and Section 8 for the specific approximations and the Θ-absence mechanism this result depends on.*

*Update (2026-07-22): the "Θ-absence mechanism" referenced above is no longer an open gap in this research program — see the dated notes in Sections 5.3, 7.1, 7.2, 8, and 9 above, and `docs/paper3_draft.md`/`docs/full_derivation.md` §V for the full, corrected result. This draft's own text is left as the historical record of what this paper could say before that resolution existed, not rewritten to read as though Θ had always been priced.*
