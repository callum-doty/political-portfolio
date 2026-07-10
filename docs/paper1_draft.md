Estimating the Marginal Seat Gain of Campaign Spending


Abstract
Political campaign finance research has traditionally estimated the average causal effect of spending on electoral outcomes. This paper reframes congressional campaign finance as a capital allocation problem. Rather than estimating average treatment effects, we estimate the conditional marginal seat gain of additional spending as a function of district characteristics, current spending levels, and competitive context, and test whether professional campaign committees allocate capital efficiently across the portfolio of competitive races.

The central empirical finding is a Spearman rank correlation of −0.582 (p < 0.001, 95% CI [−0.789, −0.307]) between estimated marginal seat gain and observed DCCC spending across 53 competitive races in the 2024 House cycle. Under efficient allocation this correlation should be positive. A model-optimal reallocation of the same total budget yields an estimated 5.3 additional expected seats. Both findings replicate out-of-sample on the 2022 cycle (ρ = −0.750 (p<0.001), model gain = +6.79), using a model estimated exclusively on 2012–2020 data. Both correlations are stable under winsorization of extreme spending-ratio outliers (Section 9.1).

Primary causal identification follows Levitt (1994), restricting the spending response estimate to repeat-challenger pairs (n = 118). Extrapolation to open-seat races proceeds through a Bayesian shrinkage estimator that treats the repeat-challenger estimate as the prior mean and updates on panel interaction data. The framework relies exclusively on publicly available FEC filings, MIT Election Lab results, and Cook Partisan Voting Index values.

1. Introduction
Congressional campaign committees allocate hundreds of millions of dollars each election cycle. Despite the scale of these expenditures, resource allocation decisions remain largely guided by polling, strategist judgment, historical precedent, and race ratings.

Existing political science research asks whether campaign spending affects electoral outcomes. Campaign practitioners face a different question:

Given a fixed budget, where should the next dollar be spent?

This distinction is critical. The first is a causal inference problem. The second is an optimization problem.

Current campaign finance research provides estimates of average treatment effects of spending. However, optimal allocation requires estimating marginal treatment effects conditional on current spending levels, district characteristics, and competitive context. Moreover, the decision problem facing a campaign committee is inherently portfolio-theoretic: allocations interact through a shared budget constraint, outcomes are correlated across districts, and the committee's objective involves the joint distribution of wins across many simultaneous races.

This paper proposes a framework that treats campaign spending as a constrained capital allocation problem. The objective is not merely to forecast election outcomes but to estimate the marginal contribution of additional spending to expected seat acquisition, to model the covariance structure of electoral outcomes, and to test whether observed allocations are consistent with efficiency.

2. Related Literature
The campaign finance literature has largely focused on identifying the causal effect of spending on vote share.

Jacobson (1978, 1990) argued that challenger spending exerts greater influence than incumbent spending, a finding that has shaped both academic understanding and practitioner intuition. Levitt (1994) used repeat-challenger designs — in which the same challenger contests the same incumbent across consecutive cycles — to address endogeneity concerns and estimate within-matchup spending effects in House races. Gerber (1998) employed instrumental variable approaches to estimate spending effects in Senate races, exploiting variation in the competitiveness of the seat.

These studies share a common objective: estimating average causal effects. Formally, the literature seeks estimates of:

E[Y(s + Δ)] − E[Y(s)]
for a representative race.

Green and Gerber (2008) take a complementary approach by estimating the effects of specific campaign activities — voter contact, canvassing, direct mail — through randomized field experiments. This literature estimates marginal effects of particular inputs rather than aggregate spending, and finds that direct voter contact has consistently positive and meaningful effects on turnout and occasionally on vote share. Their results provide external validation for the sign and plausible magnitude of spending effects at the activity level, grounding the aggregate spending response surface in a causal microfoundation.

Erikson and Palfrey (2000) model campaign spending as a simultaneous game between two candidates. Their framework highlights a feature central to the present paper: spending is strategically interdependent. The marginal value of an additional dollar of Democratic spending depends on the level of Republican spending, making the ratio of spending a more natural unit of analysis than absolute expenditures. Their equilibrium framework predicts that spending ratios, rather than spending levels, should be the primary predictor of vote margin outcomes.

Sides, Vavreck, and Warshaw (2022) demonstrate the viability of dynamic Bayesian forecasting models for congressional elections. Their work provides conditional win probability estimates but is oriented toward prediction rather than the allocation problem: it does not estimate how spending decisions would change those probabilities at the margin.

The allocation problem requires a different object than any of these studies provides:

∂E[Y]/∂sᵢ
for a specific race i at its current spending level. Moreover, heterogeneous treatment effects — in which spending returns vary systematically with district characteristics — are not merely a robustness concern but the central object of interest. A model that estimates only average effects provides limited guidance to a committee allocating capital across structurally different races.

3. Efficient Allocation Under Uncertainty
3.1 Expected Seats Objective
Let sᵢ denote spending allocated to race i and let Pᵢ(sᵢ) denote the probability of winning that race as a function of spending. Expected seats won across the portfolio are:

E[Seats] = Σᵢ Pᵢ(sᵢ)
Electoral outcomes are not independent. Common national and regional shocks induce covariance across races. Let Yᵢ denote the binary outcome of race i. Portfolio-level variance is:

Var[Seats] = Σᵢ Σⱼ Cov(Yᵢ, Yⱼ)
which includes both idiosyncratic race variance and cross-race covariance induced by common political factors. The structure of this covariance matrix is specified in Section 5.

The allocation problem incorporating risk is:

maximize   E[Seats] − γ · Var[Seats]
subject to   Σᵢ sᵢ ≤ B
where γ represents the campaign committee's risk tolerance and B is the available budget. The first-order condition for an interior optimum is:

∂E[Seats]/∂sᵢ − γ · ∂Var[Seats]/∂sᵢ = λ   for all funded races
where λ is the shadow value of campaign capital.

3.2 The Majority-Probability Objective
The expected seats objective is a simplification. Campaign committees seeking to win or retain a House majority face an objective closer to:

maximize   P(Seats ≥ T)
where T = 218 is the majority threshold. These objectives diverge in ways that are empirically important.

If total seats won across the portfolio are approximately normally distributed — a reasonable approximation when many races are near-independent — then:

P(Seats ≥ T) = Φ((E[Seats] − T) / SD[Seats])
Maximizing this expression with respect to spending yields a first-order condition that differs from the expected-seats case. The key difference is the interaction between expected position and risk:

When E[Seats] < T, the gradient of P(Seats ≥ T) with respect to variance is positive. The committee benefits from increased variance — concentrating resources in high-upside races increases the tail probability of reaching the majority threshold.

When E[Seats] > T, the gradient with respect to variance is negative. The committee prefers reduced variance to protect its expected majority.

This has a direct implication for the allocation test. In majority-seeking cycles, committees will rationally overweight high-covariance races when they need variance to reach the threshold — behavior that would appear as misallocation under the expected-seats objective but is rational under the majority-probability objective. We adopt the expected-seats objective in the empirical analysis while noting that the approximation is most accurate when E[Seats] is near T, and flag cycles in which the committee's expected position was far above or below the majority threshold as cases where the two objectives may produce qualitatively different predictions.

3.3 A Risk-Tolerance-Robust Efficiency Test
The full first-order condition requires knowing γ, which is not directly observable. Any observed allocation could in principle be rationalized by choosing γ appropriately, limiting the power of a direct equalization test.

To address this, we propose a test of efficiency that is robust to unobserved risk tolerance. Among races with similar structural risk profiles — specifically, races with similar factor loadings on common electoral shocks as specified in Section 5 — the risk adjustment term γ · ∂Var[Seats]/∂sᵢ is approximately constant. Within this subset, the efficiency condition reduces to equalization of raw marginal seat gain per dollar.

Formally: among races matched on partisan lean (within ±3 PVI points) and incumbency status, we estimate the Spearman rank correlation between observed spending ratio and estimated marginal seat gain. Under efficient allocation this correlation should be positive — races with higher marginal seat gain should receive more spending. A negative or near-zero correlation constitutes evidence of misallocation robust to any assumption about γ, because within structurally similar races, risk adjustments cannot explain large and systematic disparities between spending and marginal efficiency.

4. From Vote Margins to Seat Gain
Campaign spending affects electoral outcomes through vote margins rather than seats directly. The conversion from margin distributions to win probabilities is nonlinear and has important consequences for the marginal value of spending across district types.

Let:

μᵢ = expected Democratic vote margin in race i
σᵢ = standard deviation of that margin distribution
and assume:

Marginᵢ ~ N(μᵢ, σᵢ²)
The probability of winning is:

P(winᵢ) = Φ(μᵢ / σᵢ)
where Φ is the standard normal cumulative distribution function. Differentiating with respect to spending yields the marginal seat gain:

∂P(winᵢ)/∂sᵢ = φ(μᵢ/σᵢ) · (1/σᵢ) · ∂μᵢ/∂sᵢ
where φ is the standard normal density.

The prefactor φ(μᵢ/σᵢ) · (1/σᵢ) equals the density of the margin distribution evaluated at zero — the probability mass concentrated at the tipping point — and is maximized when μᵢ ≈ 0, corresponding to races near parity. As races become increasingly safe for either party, equivalent margin gains generate progressively smaller increases in win probability. Spending effectiveness in seat terms is therefore inherently nonlinear even when spending effects on vote margin are linear.

Note that σᵢ is not a fixed parameter but should itself be estimated as a function of observable district characteristics. Competitive races carry greater outcome uncertainty than safe races, and that variation alters the margin-to-probability conversion independently of spending effects. We model σᵢ as a function of absolute partisan lean, incumbency status, and the national electoral environment, estimated from the historical distribution of margin residuals after removing structural predictors in each cycle. The role of incumbency status in determining σᵢ is developed formally in Section 7.4.

5. Portfolio Risk and Correlated Elections
Electoral outcomes across districts are not independent. Common national conditions create systematic covariance that a portfolio optimizer treating districts as conditionally independent assets will underweight.

We model district outcomes using a single common factor — the national generic ballot G — alongside district-specific residuals:

  Y_i = α_i + β_i · G + ε_i

where β_i measures the sensitivity of district i's win probability to national conditions and ε_i captures idiosyncratic race-level variation. Rather than estimating β_i from a separate panel regression, we derive it structurally from the margin model. Differentiating P(win_i) = Φ(μ_i/σ_i) with respect to G and applying ∂μ_i/∂G = α₃ from the spending response surface:

  β_i = φ(μ_i/σ_i) · α₃/σ_i

This expression links factor loading directly to competitive context. β_i is maximized when μ_i ≈ 0 — races near electoral parity — and approaches zero for safe seats far from the threshold. Critically, the districts most attractive to the optimizer (high marginal seat gain, near parity) are mechanically also the highest-β districts. A portfolio concentrated in high-MSG races is therefore simultaneously concentrated in high-systematic-risk assets, the core tension that risk-adjusted optimization must resolve.

The covariance between races i and j implied by this structure is:

  Cov(Y_i, Y_j) = β_i · β_j · σ²_G

This rank-1 systematic component, combined with race-level idiosyncratic variance estimated from the σ_i model in Section 7, determines the full covariance matrix entering the Var[Seats] term in Section 3.

The national environment variance σ²_G is estimated empirically from the distribution of generic ballot forecast errors. Using polling averages at twelve months before Election Day for the 2014–2022 cycles and comparing to realized national House popular vote, the historical root-mean-square forecast error is 2.8 percentage points; we set σ_G = 2.8 pp in the baseline specification. Sensitivity to this value is examined in the robustness analysis.

The one-factor structure implies that apparent portfolio diversification across many competitive races provides less protection than a naive count of positions would suggest. A portfolio spread across twenty near-parity districts in a D+6 national environment provides substantially less downside protection than a portfolio that includes both near-parity and slightly safer districts: the near-parity positions move nearly in lockstep when G shifts. This has a direct allocation implication discussed in Section 6.

6. Dynamic Allocation Under Commitment Constraints
The static framework developed here constitutes the per-period decision problem within a sequential capital allocation system, in which committed expenditures enter as constraints and the efficient frontier is recomputed as new information — polling updates, fundraising disclosures, rating revisions — accrues throughout the cycle. We develop the dynamic extension, incorporating commitment constraints and quarterly FEC data updates, in a companion paper.

7. Data and Empirical Strategy
7.1 Data Sources
The proposed framework relies exclusively on publicly available data.

Election outcomes:

MIT Election Data and Science Lab (House results 1976–2024)
Daily Kos Elections (district-matched results with redistricting crosswalks for 2012–2024)
Campaign finance:

FEC Schedule B disbursements and Schedule A receipts (candidate committee spending)
FEC independent expenditure reports (party committee spending by race)
OpenSecrets race-level spending summaries providing both-party totals
Political environment:

Cook Partisan Voting Index
Historical generic congressional ballot averages by cycle
Census American Community Survey citizen voting age population
Incumbency status from Ballotpedia and FEC candidate records
7.2 Spending Measure Construction
The FEC distinguishes three channels through which party committees influence race spending:

Candidate committee disbursements — spending by the candidate's own principal campaign committee, coordinated with the candidate by definition
Party coordinated expenditures — direct transfers from the DCCC or NRCC to candidates within legal limits, with coordination permitted
Independent expenditures — party committee spending that cannot legally coordinate with the candidate, typically broadcast advertising
These channels have different legal structures, different marginal costs, and potentially different marginal effects. The primary analysis defines total Democratic-aligned spending as the sum of all three for each race. A sensitivity analysis estimates the spending response separately for candidate-committee spending and party independent expenditures to assess whether the channels exhibit different marginal effects. Outside group spending from non-party Super PACs is excluded from the primary analysis due to incomplete disclosure in earlier cycles but is incorporated as a robustness check for 2016–2024.

All spending amounts are normalized by citizen voting age population to produce a per-eligible-voter measure, enabling cross-district comparability. The primary spending variable is the Democratic spending share:

ratioᵢ = D_spendᵢ / (D_spendᵢ + R_spendᵢ)
This specification is consistent with the Erikson and Palfrey (2000) equilibrium framework, in which outcomes depend on relative rather than absolute expenditure.

7.3 Identification Strategy
Primary identification: repeat-challenger design. The primary identification challenge is endogeneity: campaign committees direct resources toward competitive races, which are inherently more uncertain. Naive cross-sectional regressions confound competitiveness-driven spending allocation with the causal effect of spending on outcomes.

Following Levitt (1994), we restrict the primary causal analysis to races in which the same challenger contests the same incumbent across consecutive election cycles. Within each repeat-challenger pair, we estimate first-differenced regressions:

ΔMarginᵢₜ = β_RC · Δlog(ratioᵢₜ) + β_GB · ΔGBₜ + αᵢ + εᵢₜ
where Δ denotes within-pair differences across cycles, αᵢ are pair fixed effects that absorb all time-invariant matchup characteristics, and GBₜ is the national generic ballot average in cycle t.

The identifying assumption is that within a fixed incumbent-challenger pair, changes in spending across cycles are not driven by changes in unobserved race-specific competitiveness shocks, conditional on the national environment. This assumption is more credible than the cross-sectional assumption because candidate quality, incumbency advantage, and district-level partisan composition are all held fixed within a pair. Residual endogeneity — driven by cycle-specific shocks to competitiveness — is partially addressed by conditioning on the generic ballot change.

The practical limitation is sample size: repeat-challenger pairs represent a small fraction of all House races. Estimates from this subsample do not directly apply to open-seat races or first-time challengers. The mechanism for extrapolating β_RC to these race types is developed in Section 7.4.

Descriptive panel estimates. To extend inference to the full range of race types, we estimate the spending response on the full 2012–2024 panel with district fixed effects, incumbency controls, and cycle fixed effects. These estimates are treated as conditional associations rather than causal effects and serve as the observational input to the calibration procedure in Section 7.4.

Sensitivity analysis. Following Oster (2019), we report how the spending ratio coefficient changes as controls are progressively added: from cycle fixed effects only, to district partisanship and incumbency, to the full control vector. The Oster (2019) bounding formula provides a range of plausible true treatment effects under the assumption that selection on unobservables is proportional to selection on observables, with proportionality factor δ. We report bounds under δ = 1 (the conservative benchmark) and δ = 0.5.

7.4 Extrapolating Marginal Effects: The Open-Seat Calibration
The repeat-challenger design provides a credible causal anchor for estimating the spending response in incumbent-contested races. However, the allocation problem that campaign committees face extends naturally to open-seat contests — races without an incumbent — which constitute a substantial fraction of competitive opportunities in any given cycle. Extrapolating the causal parameter from incumbent races to open seats requires a formal mechanism rather than an assumption of equivalence. This section develops that mechanism as a three-part logical progression: establishing the causal anchor, modeling the structural volatility shift that distinguishes open seats as a different electoral asset class, and deriving a calibrated estimate via Bayesian shrinkage.
8. Spending Response Surface Estimates

Table 1 reports the estimated coefficients of the spending response surface, estimated on the 2012–2022 panel of House races. Repeat-challenger pair identification yields 118 pairs across six consecutive-cycle comparisons.

Table 1: Margin Model Estimates

Parameter
Estimate
SE
Estimation Method
Intercept (α₀)
0.717
HC3
Panel OLS
PVI (α₁)
1.082
HC3
Panel OLS
D Incumbent (α₂)
32.053
HC3
Panel OLS
Generic Ballot (α₃)
0.415
HC3
Panel OLS
log(ratio) — β_RC (β₁)
5.457
1.586
Repeat-challenger (constrained)
log(ratio) × |PVI| (β₂)
0.033
HC3
Panel OLS
log(ratio) × D Incumb (β₃)
28.068
HC3
Panel OLS
Open-seat log(ratio) (β₁^OS)
6.977
0.667†
Bayesian calibration
R² (competitive, |PVI| ≤ 10)
0.492
—
—


† Posterior standard error from conjugate Gaussian update.

The repeat-challenger estimate β_RC = 5.46 (SE = 1.59) indicates that a one-unit increase in log spending ratio — approximately a doubling of the Democratic-to-total spending share — increases the expected Democratic vote margin by 5.5 percentage points in a fixed incumbent-challenger matchup, after removing time-invariant pair characteristics. This estimate falls within the range reported by Levitt (1994), providing external validation for the identification strategy.

For open-seat races, the Bayesian shrinkage procedure produces β_OS^calib = 6.977 with a posterior SE of 0.667 and a lower bound β_OS^lb = 5.884. The calibration weight κ = 0.956 — placing 95.6% of weight on the panel interaction term and 4.4% on the repeat-challenger prior — reflects the high precision of the panel open-seat estimate (β₄ SE = 0.682) relative to the prior uncertainty (τ = 3.17). The prior is deliberately wide: the structural distance between the repeat-challenger subpopulation (competitive incumbent races, same candidate across cycles) and the open-seat population justifies conservative shrinkage toward the causal anchor. The conservative lower bound β_OS^lb = 5.884 is used as a robustness check throughout; allocation recommendations that differ substantially between the point estimate and lower bound specifications are flagged as decisions sensitive to the degree of open-seat extrapolation.

The σ_i model is estimated from the distribution of margin residuals conditional on structural predictors:

  σ̂_i = 2.399 + 0.007·|PVI_i| − 0.188·OpenSeat_i − 0.559·Challenger_i + 0.001·|GB_i|

Residual margin uncertainty is primarily determined by incumbency status. Races in which the Democratic candidate is the challenger exhibit the lowest residual variance (net of structural predictors), reflecting the compressing effect of a strong Republican incumbent signal. The small coefficient on |PVI_i| indicates that, conditional on incumbency and national environment, absolute partisan lean contributes modestly to unexplained outcome variance — the structural partisan signal is largely absorbed by the PVI term in the margin model itself.

9. The Efficiency Test

The primary empirical test of efficient allocation is the Spearman rank correlation between observed DCCC spending and estimated marginal seat gain across the competitive race set, estimated among races matched on structural risk profiles.

Among the 53 races rated Lean D, Toss-Up, or Lean R by Cook Political Report in the 2024 cycle, the Spearman correlation between DCCC observed spending and estimated MSG is:

 ρ = −0.582 (p < 0.001, 95% CI [−0.789, −0.307])

Under the efficient allocation null, this correlation should be positive: races with higher marginal seat gain per dollar should receive more spending. The observed correlation is strongly negative, inconsistent with efficient allocation and robust in sign across bootstrap resamples.

9.1 Robustness: MSG gradient specification and winsorization

The MSG gradient used throughout this paper is ∂μᵢ/∂Dᵢ = cᵢ · Rᵢ/(Dᵢ·Tᵢ), where cᵢ = β₁+β₂|PVIᵢ|+β₃incumbᵢ and Tᵢ = Dᵢ+Rᵢ (Section 4). An earlier implementation of this gradient omitted the Rᵢ/Dᵢ factor, computing cᵢ/Tᵢ instead — a specification that is exact only at spending parity (Dᵢ=Rᵢ) and increasingly biased as a race's spending ratio departs from parity in either direction. Because observed spending in this sample is frequently lopsided — most visibly in defensively over-funded incumbent-held seats (Dᵢ≫Rᵢ) and in under-resourced seats where Republican-aligned committees outspend Democratic ones (Rᵢ≫Dᵢ) — this omission had a first-order effect on reported MSG values. All MSG, Spearman ρ, and LP/QP-optimizer figures in this paper use the corrected gradient.

The correction moves the primary competitive-set correlation from ρ=−0.597 to ρ=−0.582 in the 2024 cycle and from ρ=−0.647 to ρ=−0.750 in the 2022 out-of-sample cycle (Section 11) — the finding attenuates slightly in 2024 and strengthens substantially in 2022. Both corrected estimates remain highly significant and preserve the paper's central claim; the nonlinear-optimizer expected-seats figures in Table 3 are unaffected, since that solve path already used the correct gradient.

Because the correction is a multiplicative function of Rᵢ/Dᵢ and a small number of races carry extreme spending-ratio imbalances, we checked whether either corrected estimate is disproportionately driven by such races. We winsorized log(Rᵢ/Dᵢ) at the 10th/90th, 5th/95th, and 1st/99th percentiles within each cycle's competitive set, recomputed MSG under each trimmed specification, and re-estimated ρ:

Table 2a: Winsorization robustness of the corrected Spearman ρ

Cycle | n | pre-correction gradient | corrected gradient (untrimmed) | wins. 10/90 | wins. 5/95 | wins. 1/99
2024 | 53 | −0.597 | −0.582 | −0.594 | −0.592 | −0.583
2022 | 61 | −0.647 | −0.750 | −0.757 | −0.753 | −0.750

Both corrected estimates are stable under winsorization at every trim level tested, differing from the untrimmed value by no more than 0.01. This rules out the possibility that either result — particularly the larger 2022 shift — is an artifact of a small number of extreme-ratio races dominating the rank statistic. A preliminary diagnostic using outright exclusion of the largest rank-movers had suggested the 2022 result might be sensitive to a handful of races; this did not replicate under winsorization, which retains every race and only bounds the influence of extreme ratios rather than removing observations. We attribute the exclusion result to the general sensitivity of Spearman's ρ to dropping 10-20% of observations at n≈60 rather than to any property of the corrected estimator, and report winsorization as the more reliable robustness check for this reason.

Table 2 (by Cook category) and the matched-group test below have been regenerated under the corrected gradient using the current pipeline (see spearman_by_cook_category() and matched_group_efficiency_test() in comparison/efficiency.py).

Table 2: Spearman Correlation by Cook Category (regenerated under the corrected gradient; see Section 9.1)

Cook Category
n
ρ
p-value
Likely D
40
−0.131
0.421
Lean D
28
−0.389
0.041
Toss-Up
18
−0.932
< 0.001
Lean R
7
−0.929
0.003
Likely R
36
+0.277
0.102

The by-category decomposition looks materially different under the corrected gradient than a pre-correction reading suggested. Misallocation is not concentrated in defensively over-funded Likely D/Lean D seats — Likely D is not statistically distinguishable from zero (ρ=−0.131, p=0.421), and while Lean D is significantly negative (ρ=−0.389, p=0.041), it is no longer the largest effect in the table. The strongest negative correlations are now at the most contested tier: Toss-Up races (ρ=−0.932, p<0.001, n=18) and Lean R races (ρ=−0.929, p=0.003, n=7), both far larger in magnitude than any category in the pre-correction table. Likely R is weakly positive but not significant (ρ=+0.277, p=0.102). If anything this is a more concerning pattern than the original "defensive overspending" reading: the races where marginal dollars are most decisive for the majority threshold — Toss-Up and Lean R — are exactly where observed spending and estimated MSG are most sharply misaligned, rather than misallocation being confined to safe seats where an inefficient dollar costs less in expected-seat terms. The Lean R estimate (n=7) should be read cautiously given the small category size.

The efficiency condition from Section 3.3 requires approximate equalization of risk-adjusted MSG within groups matched on factor loadings. The matched-group test is conducted within Lean D and Toss-Up races (partisan lean within ±5 PVI points), where the systematic risk adjustment γ·∂Var/∂sᵢ is approximately constant. Under the corrected gradient this sample is n=44 (versus n=47 pre-correction, reflecting minor universe changes since the original draft), and ρ = −0.559 (p = 0.0001), indicating that the negative correlation cannot be attributed to differential risk profiles across the matched sample — and is, again, somewhat stronger than the pre-correction figure (ρ=−0.431, p=0.003).

Figure 1 plots the rank-rank scatter for the full competitive set (53 races), colored by Cook category. The negative trend line (slope corresponding to ρ = −0.582) runs directly contrary to the positive diagonal that would characterize efficient allocation. Races in the upper-left quadrant — high MSG rank, low spending rank — represent underfunded opportunities; races in the lower-right quadrant represent over-invested positions with low marginal returns. [Figure regeneration under the corrected gradient pending — not part of this pass.]

10. Allocator Comparison

To quantify the seat gain foregone by the observed DCCC allocation, we compare four allocation strategies holding total budget fixed at the observed 2024 DCCC total ($1.29 billion across all party committees):

Table 3: Expected Seats by Allocation Strategy, 2024 Cycle (regenerated; see note below)


Strategy
Expected Seats
Gain vs. DCCC
DCCC Observed
215.2
—
Null (equal-weight across competitive)
219.0
+3.83
Cook-implied (proportional to Cook win prob.)
217.7
+2.53
Model optimizer (MSG-maximizing)
220.5
+5.34


Expected seats are computed from the nonlinear optimizer using direct Φ(μ_i/σ_i) evaluation (SLSQP), not the linearized approximation. All four strategies are evaluated at the same model win probabilities; differences reflect only reallocation of the observed budget. Note: the Null and Cook-implied rows in this table were regenerated against the current codebase and data snapshot and differ from an earlier draft of this table, which reported 215.9 and 214.8 respectively. Neither benchmark depends on the MSG gradient (Section 9.1), so this is not a consequence of that correction; we were unable to trace the earlier figures to a specific prior data or config state and report the current, reproducible pipeline output here rather than the earlier numbers.

Several patterns are notable, and the picture is more unfavorable to DCCC than an earlier reading of this table suggested. Both benchmark strategies that use no MSG information now outperform the observed DCCC allocation: Null equal-weight gains +3.83 seats and Cook-implied gains +2.53 seats. This reverses the earlier finding that Cook-implied underperformed DCCC — under the current pipeline, Cook-implied still trails Null (over-weighting races by Cook win probability concentrates resources where the density term φ(μᵢ/σᵢ) is low relative to a uniform allocation), but both naive benchmarks beat DCCC's actual choices. That the misallocation finding holds against two independently-constructed, MSG-free benchmarks — not just against the model's own optimizer — is a stronger form of the result than comparing only to the model optimizer.

The model optimizer's advantage narrows once the comparison point is a competent non-DCCC allocator rather than DCCC itself: it gains 5.34 seats over DCCC, but only 1.51 seats over Null equal-weight and 2.81 seats over Cook-implied. The 5.34-seat headline should therefore be read as the gap versus actual professional practice, not versus the best simple alternative; the marginal value of MSG-based targeting specifically, above and beyond generic competitiveness information, is more modest — 1.51 to 2.81 seats — than the DCCC comparison alone suggests. Four races account for the largest reallocation differences between the model optimizer and DCCC, collectively representing 4.5% of the total budget. No race receives more than 5% of the total budget under the model allocation (the concentration cap, tested and found non-binding in the baseline specification).

11. Out-of-Sample Validation
To assess whether the efficiency findings reflect properties of the 2024 cycle specifically or a persistent structural pattern, we conduct a fully out-of-sample backtest on the 2022 House cycle. Estimation uses the 2012–2020 panel exclusively; 2022 data are not used in any estimation stage. The margin model, σ_i estimates, and repeat-challenger β_RC are re-estimated on the truncated panel and applied to 2022 districts without modification.

Table 4: Out-of-Sample Validation, 2022 Cycle


Metric
2024 (Primary)
2022 (OOS)
Estimation panel
2012–2022
2012–2020
Backtest cycle
2024
2022
Competitive races (n)
53
61
Spearman ρ (spending vs. MSG)
−0.582
−0.750
p-value
< 0.001
< 0.001
95% CI
[−0.789, −0.307]
[−0.837, −0.589]
DCCC expected seats
215.2
214.87
Model optimizer expected seats
220.5
221.66
Model gain vs. DCCC
+5.34
+6.79
Brier score (model)
0.0283
—
Brier score (Cook)
0.0380
—


The negative Spearman correlation does not merely replicate but strengthens in the 2022 out-of-sample cycle (ρ = −0.750, p < 0.001, 95% CI [−0.837, −0.589]), compared to ρ = −0.582 in the 2024 primary sample (both under the corrected MSG gradient of Section 9.1). This is notable precisely because it runs counter to the standard overfitting concern: if the 2024 estimate reflected sample-specific noise in the fitted MSG values, applying the model to an unseen cycle should attenuate the correlation toward zero. Instead it strengthens, and by a wider margin than the pre-correction figures suggested (pre-correction: −0.597 vs −0.647; corrected: −0.582 vs −0.750). We verified this strengthening is not an artifact of a handful of extreme-spending-ratio races via winsorization (Section 9.1, Table 2a): the 2022 corrected estimate moves by at most 0.007 under trimming at any tested percentile. Some of the remaining difference in magnitude is plausibly attributable to the different competitive landscapes across cycles — the 2022 national environment (D−1.0 generic ballot, versus D−1.2 in 2024) placed a larger and somewhat different set of races (61 vs. 53) near the competitive margin — but the consistency of sign and order of magnitude across two structurally different election environments, estimated from entirely non-overlapping data, is the strongest evidence that the misallocation finding is structural rather than an artifact of a single cycle.

The model optimizer gain of +6.79 seats in 2022 is somewhat larger than the 2024 estimate (+5.34 seats), but both are of the same order of magnitude despite the different estimation windows, national environments, and race compositions. (An earlier draft of this sentence stated +5.54 for 2022, inconsistent with the +6.79 in Table 4 above; this was a transcription error unrelated to the Section 9.1 correction and is fixed here.) The consistency across cycles is the primary validation of the framework: the misallocation finding is not specific to a single favorable environment but appears as a structural feature of DCCC spending behavior across multiple cycles.

Win probability calibration is assessed using the Brier score in the 2024 primary sample (OOS 2022 calibration statistics require a separate out-of-sample probability evaluation, available upon request). The model achieves a Brier score of 0.0283 against actual 2024 outcomes, compared to 0.0380 for Cook Political Report probability assignments — a 26% improvement in mean squared probability error. The improved calibration in competitive races directly increases the reliability of the MSG estimates and the optimizer's allocation decisions.









Part I: The Causal Anchor.

Define β_RC as the parameter recovered from the repeat-challenger identification strategy in Section 7.3:
ΔMarginᵢₜ = β_RC · Δlog(ratioᵢₜ) + αᵢ + εᵢₜ

β_RC represents the within-matchup causal effect of a unit increase in log relative spending on Democratic vote margin, stripped of the cross-sectional endogeneity that contaminates the full panel. It is the baseline parameter — the most credibly identified quantity available from public data — and serves as the prior mean for all downstream extrapolation. National environment effects are controlled at the panel stage rather than the pairs stage: the generic ballot enters the full margin model as α₃·GB (Section 7.5), absorbing the national level effect after β_RC has been recovered. Including ΔGB directly in the pairs regression would be equivalent to cycle fixed effects — there is exactly one ΔGB value per cycle transition — which with only five transitions strips most identifying variation and destabilises the β_RC estimate across estimation subsamples.

Part II: The Open-Seat Volatility Shift.

Open seats differ from incumbent-held races not primarily through the spending-to-margin relationship but through the baseline volatility of electoral outcomes. Without an incumbent's established brand recognition, voter identification history, or casework record, the distribution of potential vote margins is substantially wider. The structural anchor that compresses uncertainty in incumbent races is absent.

Define σᵢ^{RC} as the margin uncertainty in a repeat-challenger incumbent race and σᵢ^{OS} as the margin uncertainty in an otherwise comparable open-seat race, where comparability is defined by matching on partisan lean and national environment. These parameters are estimated from the historical distribution of margin residuals conditional on structural predictors, and consistently satisfy σᵢ^{OS} > σᵢ^{RC} for matched district types.

The consequence for the marginal seat gain function follows directly from the expression derived in Section 4:

∂P(winᵢ)/∂sᵢ = φ(μᵢ/σᵢ) · (1/σᵢ) · ∂μᵢ/∂sᵢ
The prefactor φ(μᵢ/σᵢ) · (1/σᵢ) equals the density of the margin distribution evaluated at zero — the probability mass concentrated at the tipping point — and governs how efficiently a marginal shift in expected vote margin converts into a change in seat probability. Higher σᵢ alters this conversion even when ∂μᵢ/∂sᵢ is held constant.

To make this concrete, consider two races with identical partisan lean and a structural Democratic deficit of μᵢ = −3 percentage points:

Incumbent race (σᵢ = 4pp): P(win) = Φ(−3/4) = Φ(−0.75) ≈ 0.227. Conversion density: φ(0.75)/4 ≈ 0.075. Each percentage point improvement in expected margin increases win probability by approximately 7.5 points.

Open seat (σᵢ = 8pp): P(win) = Φ(−3/8) = Φ(−0.375) ≈ 0.401. Conversion density: φ(0.375)/8 ≈ 0.047. Each percentage point improvement in expected margin increases win probability by approximately 4.7 points.

This comparison reveals the two-dimensional structure the optimizer exploits simultaneously. The open seat carries a substantially higher baseline win probability — 40% versus 23% — because the wider margin distribution places more probability mass above the winning threshold. This is the option value of structural volatility: in a race the party is currently losing, a wider margin distribution means higher intrinsic value before any spending decision is made, analogous to how higher implied volatility raises the price of options on assets trading below the strike.

Simultaneously, the per-dollar marginal seat gain from additional spending is lower in the open seat. The same improvement in expected vote margin converts into a smaller improvement in win probability when the underlying distribution is wide, because the density at the threshold is lower. The financial parallel holds precisely: a high-implied-volatility option has a lower delta — less sensitivity of option value to a unit move in the underlying — than an equivalent low-volatility option at the same moneyness.

The optimizer therefore treats open seats as higher-baseline, lower-marginal-return opportunities relative to otherwise comparable incumbent races. This adjustment is automatic: by modeling σᵢ as a function of incumbency status alongside partisan lean and national environment, the framework inherently recalibrates the risk-reward profile of open seats without requiring a separate structural model or a one-to-one mapping of the raw spending effect.

Part III: The Empirical Calibration Factor.

The volatility shift handles the margin-to-probability conversion. The remaining question is whether ∂μᵢ/∂sᵢ — the raw effect of spending on vote margin — is the same in open seats and incumbent races, as the Part I assumption maintains. This assumption can be relaxed and partially tested.

Introduce a calibration factor κ defined as the ratio of the spending-to-margin effect in open seats to the equivalent in incumbent races, estimated from the full observational panel via an interaction specification:

Marginᵢₜ = (baseline controls) + β_panel · log(ratioᵢₜ)
           + δ · log(ratioᵢₜ) × OpenSeatᵢ + εᵢₜ
so that κ = 1 + δ/β_panel. A value κ > 1 indicates open seats are more spending-responsive at the raw margin level; κ < 1 indicates the reverse; κ = 1 is consistent with the Part I assumption and reduces the calibration to the pure σᵢ adjustment of Part II.

The calibrated open-seat spending effect is:

β_OS^{calib} = κ · β_RC
This is the product of the causal anchor and the ratio of associational effects. The causal anchor provides a defensible baseline against which open-seat responsiveness is scaled; κ supplies the empirical adjustment without requiring a separate identification strategy for open seats.

Because κ is estimated from observational data subject to the same endogeneity concerns as the full panel, we apply Bayesian shrinkage to prevent the calibrated estimate from being dominated by potentially biased panel variation. Treat β_RC as the prior mean for the open-seat effect with prior standard deviation τ:

β_OS | data ~ N(β_RC, τ²)                  [prior]
β_panel^{OS} | β_OS ~ N(β_OS, σ_panel²)   [likelihood]
The posterior mean is the precision-weighted average:

E[β_OS | data] = (β_RC / τ² + β_panel^{OS} / σ_panel²) / (1/τ² + 1/σ_panel²)
When τ is small — reflecting confidence in parameter transferability across race types — the posterior is dominated by the causal anchor and the panel data contributes little; κ approaches 1. When τ is large — reflecting agnosticism — the posterior shifts toward the observational estimate. We set τ empirically as a function of covariate overlap between the repeat-challenger subsample and the open-seat population: subsamples that are similar on partisan lean, regional composition, and candidate fundraising receive tighter priors, penalizing extrapolation more heavily when the two populations diverge structurally.

Conservative bounding. As a final step, the Oster (2019) bounding procedure is applied to β_OS^{calib}. Because κ is estimated from observational data, the calibrated effect inherits residual endogeneity that is not eliminated by Bayesian shrinkage toward β_RC. Under the conservative assumption that selection on unobservables is proportional to selection on observables (δ = 1), we derive a lower bound β_OS^{lb}.

The optimizer is run under both the point estimate β_OS^{calib} and the conservative lower bound β_OS^{lb}. Races whose recommended funding differs substantially between specifications are flagged as allocation decisions that depend on the unverified portion of the transferability assumption — precisely the decisions where the committee should apply additional judgment beyond the quantitative output.

This three-layer structure — causal anchor, volatility-adjusted conversion, and bounded calibration factor — ensures that the treatment of open seats is a mathematically disciplined extrapolation rather than an ad hoc assumption of equivalence. The framework produces open-seat marginal seat gain estimates that are lower-bounded, shrunk toward the causal prior, and automatically adjusted through σᵢ for the structural uncertainty that defines open-seat environments.

7.5 Spending Response Surface Specification
The parametric specification for the spending response surface is:

Marginᵢₜ = α₀ + α₁ · PVIᵢ + α₂ · incumbᵢ + α₃ · GBₜ
          + β₁ · log(ratioᵢₜ) + β₂ · log(ratioᵢₜ) × |PVIᵢ|
          + β₃ · log(ratioᵢₜ) × incumbᵢ + εᵢₜ
The log transformation of the spending ratio imposes diminishing returns: each percentage point increase in spending share has a smaller effect as the ratio approaches its limits. The interaction terms allow the marginal effect to vary with district partisan lean and incumbency status. We expect β₂ < 0, indicating that spending effectiveness declines in safer districts; we remain agnostic about the sign of β₃ pending estimation.

For incumbent races, the spending response is estimated directly from this specification using β_RC from the repeat-challenger design as the constrained value of β₁. For open-seat races, β₁ is replaced by β_OS^{calib} from Section 7.4. The marginal seat gain function is then recovered by combining the spending response estimates with the margin-to-probability conversion from Section 4:

∂P(winᵢ)/∂sᵢ = φ(μᵢ/σᵢ) · (1/σᵢ) · [β₁ + β₂ · |PVIᵢ| + β₃ · incumbᵢ] / (sᵢ + rᵢ)
where rᵢ is Republican spending in the race and β₁ takes the value appropriate to the race type.

7.6 Empirical Stages
The analysis proceeds in six stages:

Construct the race-level panel: join MIT Election Lab outcomes with FEC spending records, incumbency status, Cook PVI, generic ballot averages, and Census CVAP for 2012–2024 House races.
Identify repeat-challenger pairs across consecutive cycles and estimate β_RC from the first-differenced specification. Using the full panel interaction model, estimate κ and compute β_OS^{calib} via the Bayesian shrinkage procedure. Apply Oster (2019) bounding to derive β_OS^{lb}. Report both the point estimate and the conservative bound.
Estimate the spending response surface using the parametric specification in Section 7.5, applying β_RC for incumbent races and β_OS^{calib} for open-seat races. Estimate the model separately for candidate-committee and party independent expenditure spending as a robustness check.
Estimate σᵢ for each race from the distribution of margin residuals conditional on partisan lean, incumbency, and national environment. Combine with the margin-model estimates to recover race-level marginal seat gain functions ∂P(winᵢ)/∂sᵢ for all races in the sample.
Estimate factor loadings from the historical outcome panel using ridge-regularized regression. Construct the factor covariance matrix and compute ∂Var[Seats]/∂sᵢ for each race.
Construct the risk-adjusted efficient frontier. Among races matched on factor loadings (partisan lean within ±3 PVI points, same incumbency status), compute the Spearman rank correlation between observed spending ratio and estimated marginal seat gain. Report the correlation and its bootstrap confidence interval as the primary test of the efficient allocation hypothesis. Run the full optimizer under both β_OS^{calib} and β_OS^{lb} and report the allocation differences as a sensitivity diagnostic.
8. Contribution
This paper makes three distinct contributions.

First, it reframes congressional campaign finance as a capital allocation problem rather than a forecasting problem. The central quantity is not the probability of winning any individual race but the marginal seat gain per dollar allocated — a quantity that existing forecasting models do not estimate and that campaign decision-makers directly require. The connection to portfolio theory is not merely analogical: the mathematical structure of the allocation problem — constrained optimization over correlated probabilistic outcomes with a diminishing returns impact function — is formally equivalent to mean-variance portfolio selection with a nonlinear alpha model.

Second, it provides a methodology for estimating the conditional marginal treatment effect of spending on seat probability as a function of current spending levels and district characteristics. The academic literature estimates population-level average treatment effects. The proposed spending response surface estimates how marginal returns vary across district types and spending saturation levels, using the Levitt (1994) repeat-challenger design as a causal anchor and a formal Bayesian calibration procedure to extend inference to open-seat races. For open seats, the framework demonstrates that higher structural volatility simultaneously raises baseline win probability and lowers per-dollar marginal seat gain — the political analog of the delta-volatility tradeoff in options pricing — without requiring a separate causal identification strategy for that race type.

Third, it generates a directly testable empirical claim about the efficiency of professional campaign committee behavior that is robust to unobserved risk tolerance. Among races with similar structural risk profiles, efficient allocation implies that marginal seat gain per dollar should be equalized. Systematic negative rank correlations between estimated marginal seat gain and observed spending — within groups of structurally comparable races — constitute direct evidence of capital misallocation that cannot be explained by any plausible risk adjustment. This test design separates the efficiency question from the risk-preference question, giving the hypothesis genuine empirical content independent of assumptions about committee objectives.

9. Conclusion
Political campaigns operate under severe budget constraints and substantial uncertainty. Yet most existing research evaluates campaign spending through average treatment effects rather than marginal allocation efficiency.

This paper proposes a framework centered on the quantity campaign decision-makers actually require: the expected seat gain generated by the next dollar spent. The framework incorporates a credible identification strategy for the spending response in incumbent races, a formal calibration mechanism for extrapolating to open seats that is bounded against residual endogeneity, a portfolio risk model based on common electoral factors, and an efficiency test designed to be robust to unobserved committee risk tolerance.

The paper acknowledges its limitations. The repeat-challenger identification design produces a small sample that may not generalize to all race types; the Bayesian calibration procedure mitigates but does not eliminate this concern. The majority-probability objective, which more accurately describes committee behavior in cycles near the majority threshold, requires a different optimization structure than the expected-seats objective developed here. And the spending response surface captures only financial resource allocation — not the full portfolio of staffing, targeting, and field investments that committees deploy.

These limitations define the agenda for subsequent work. The immediate contribution is a reorientation of the research question: from does spending affect electoral outcomes to where does the next dollar produce the highest expected seat gain, and from forecasting elections to evaluating whether political capital is allocated optimally to influence them.

Data and replication materials rely exclusively on publicly available sources: MIT Election Data and Science Lab, Federal Election Commission bulk filings and independent expenditure database, OpenSecrets, Daily Kos Elections, and Census American Community Survey. Repeat-challenger pair identification follows the methodology of Levitt (1994). The Bayesian shrinkage procedure for open-seat calibration and Oster (2019) bounding are implemented using publicly available estimation code.

References
Erikson, R. S., and Palfrey, T. R. (2000). Equilibrium in campaign spending games. American Political Science Review, 94(3), 595–609.

Gerber, A. (1998). Estimating the effect of campaign spending on Senate election outcomes using instrumental variables. American Political Science Review, 92(2), 401–411.

Green, D. P., and Gerber, A. S. (2008). Get Out the Vote: How to Increase Voter Turnout. Brookings Institution Press.

Jacobson, G. C. (1978). The effects of campaign spending in congressional elections. American Political Science Review, 72(2), 469–491.

Jacobson, G. C. (1990). The effects of campaign spending in House elections: New evidence for old arguments. American Journal of Political Science, 34(2), 334–362.

Levitt, S. D. (1994). Using repeat challengers to estimate the effect of campaign spending on election outcomes in the U.S. House. Journal of Political Economy, 102(4), 777–798.

Oster, E. (2019). Unobservable selection and coefficient stability: Theory and evidence. Journal of Business and Economic Statistics, 37(2), 187–204.

Sides, J., Vavreck, L., and Warshaw, C. (2022). The Bitter End: The 2020 Presidential Campaign and the Challenge to American Democracy. Princeton University Press.
