# Data Catalog — Political Portfolio Backtest Pipeline

> **Last updated:** 2026-06-26  
> **Cycles covered:** 2012, 2014, 2016, 2018, 2020, 2022, 2024 (panel); 2026 (live)

---

## Overview

The pipeline moves data through four stages:

```
RAW SOURCES  →  DERIVED INTERMEDIATES  →  PROCESSED ARTIFACTS  →  OUTPUTS
(disk / API)     (scripts/fetch_data.py)   (src/backtest/...)      (data/live/, reports)
```

All district identifiers use the format `{STATE_ABBR}-{DISTRICT:02d}` (e.g., `PA-07`, `CA-35`, `TX-01`). At-large districts are `{STATE}-01`.

---

## 1. Raw Data Sources

### 1.1 FEC Bulk Files — Candidate Committee Totals

| Attribute | Value |
|-----------|-------|
| **Path** | `data/raw/bulk_all/weball{yy}.txt` |
| **Alt path (active cycle)** | `data/raw/house_senate_current_campaigns/webl{yy}.txt` |
| **Format** | Pipe-delimited (`\|`), no header row, 31 columns (0-indexed) |
| **Source** | FEC bulk downloads — `https://www.fec.gov/files/bulk-downloads/{year}/weball{yy}.zip` |
| **Cycles** | One file per two-year election cycle (e.g., `weball24.txt` for 2024) |
| **Download** | `python scripts/fetch_data.py --only fec --cycles 2024` (auto-downloaded if missing) |

**Key columns (0-indexed):**

| Col | Field | Notes |
|-----|-------|-------|
| 0 | `CAND_ID` | `H…` = House; `S…` = Senate; `P…` = President |
| 1 | `CAND_NAME` | Candidate name (LAST, FIRST format) |
| 2 | `CAND_ICI` | Incumbent/Challenger/Open: `I`, `C`, `O` |
| 4 | `CAND_PTY_AFFILIATION` | `DEM`, `REP`, `DFL`, `WFP`, `IND`, etc. |
| 5 | `TTL_RECEIPTS` | Total receipts |
| 7 | `TTL_DISB` | **Total disbursements** — the spend figure used in the model |
| 9 | `COH_BOP` | Cash on hand, beginning of period |
| 10 | `COH_COP` | Cash on hand, close of period |
| 17 | `TTL_INDIV_CONTRIB` | Total individual contributions |
| 18 | `CAND_OFFICE_ST` | State abbreviation |
| 19 | `CAND_OFFICE_DISTRICT` | Two-digit district number |

**Party mapping applied at parse time:**
- `DEM`, `DFL` (Democratic-Farmer-Labor, Minnesota), `WFP` (Working Families Party) → `D`
- `REP`, `CON` (NY Conservative Party) → `R`
- All other codes pass through unmodified and are filtered out downstream

**Pipeline role:** Primary source for candidate-level spending. Rows with `CAND_ID` beginning with `H` are kept; the top spender per party × district is selected as the nominee proxy.

---

### 1.2 FEC Bulk Files — PAC Summary

| Attribute | Value |
|-----------|-------|
| **Path** | `data/raw/pac_summary/webk{yy}.txt` |
| **Format** | Pipe-delimited, no header |
| **Source** | FEC bulk downloads |

**Pipeline role:** Reference only; not directly consumed by the current pipeline (PAC spending flows through IE and coordinated files instead).

---

### 1.3 FEC Bulk Files — Supporting Reference Tables

These are downloaded from FEC bulk but are not directly loaded by model code. They serve as reference tables for cross-validation and manual lookups:

| File | Path | Contents |
|------|------|----------|
| Candidate master | `data/raw/candidate_master/cn.txt` | `CAND_ID \| CAND_NAME \| PARTY \| CYCLE \| STATE \| OFFICE \| DISTRICT \| ICI \| STATUS \| COMMITTEE_ID \| …` |
| Committee master | `data/raw/committee_master/cm.txt` | `COMMITTEE_ID \| NAME \| TREASURER \| ADDR \| … \| COMMITTEE_TYPE \| …` |
| Candidate–committee linkage | `data/raw/candidate_committee_linkage/ccl.txt` | `CAND_ID \| CYCLE \| ELECTION_YEAR \| COMMITTEE_ID \| OFFICE \| STATUS \| …` |
| All committee transactions | `data/raw/all_committee_transactions/itoth.txt` | Transfers between committees; pipe-delimited |

---

### 1.4 FEC Independent Expenditures — Comprehensive Raw File

| Attribute | Value |
|-----------|-------|
| **Path** | `data/raw/independent_expenditure/independent_expenditure_{cycle}.csv` |
| **Cycles** | 2012–2026 (one CSV per cycle) |
| **Format** | CSV with header |
| **Source** | FEC IE download (all filers, all offices, all general elections) |

**Columns:**

| Column | Description |
|--------|-------------|
| `cand_id` | FEC candidate ID |
| `cand_name` | Candidate name |
| `spe_id` | Spender committee ID |
| `spe_nam` | Spender committee name |
| `ele_type` | Election type — pipeline filters to `G` (General) |
| `can_office_state` | Candidate's state |
| `can_office_dis` | Candidate's district |
| `can_office` | Office — pipeline filters to `H` (House) |
| `cand_pty_aff` | Candidate party affiliation (full text, e.g., `DEMOCRATIC PARTY`) |
| `exp_amo` | Expenditure amount (dollars) |
| `exp_date` | Expenditure date |
| `agg_amo` | Aggregate amount to date |
| `sup_opp` | `S` = supports candidate; `O` = opposes candidate |
| `pur` | Purpose of expenditure |
| `pay` | Payee |
| `file_num` | FEC filing number |
| `amndt_ind` | Amendment indicator |
| `tran_id` | Transaction ID |
| `image_num` | Image number |
| `receipt_dat` | Receipt date |
| `fec_election_yr` | FEC election year |
| `prev_file_num` | Previous file number |
| `dissem_dt` | Dissemination date |

**Party alignment logic (applied by `scripts/fetch_data.py`):**
- D-aligned: (candidate is Democrat AND `sup_opp='S'`) OR (candidate is Republican AND `sup_opp='O'`)
- R-aligned: (candidate is Republican AND `sup_opp='S'`) OR (candidate is Democrat AND `sup_opp='O'`)

**Pipeline role:** Preferred source for outside spending. Captures all IE groups (super PACs, 527s, party committees) — not just DCCC/NRCC. Converted to `data/raw/fec/independent_expenditures_{cycle}.csv` by `build_comprehensive_ie()`.

---

### 1.5 MIT MEDSL House Election Results

| Attribute | Value |
|-----------|-------|
| **Path** | `data/raw/mit_elections/1976-2024-house.tab` |
| **Format** | Comma-delimited despite `.tab` extension; has header row |
| **Source** | MIT Election Data and Science Lab — Harvard Dataverse `doi:10.7910/DVN/IG0UN2` |
| **Coverage** | 1976–2024, all U.S. House general elections |
| **Acquisition** | Manual download required (not automated) |

**Columns:**

| Column | Description |
|--------|-------------|
| `year` | Election year |
| `state` | Full state name |
| `state_po` | Two-letter state abbreviation |
| `state_fips` | FIPS state code |
| `state_cen` | Census state code |
| `state_ic` | ICPSR state code |
| `office` | Office (always `US HOUSE`) |
| `district` | District number |
| `stage` | Election stage — pipeline filters to `GEN` |
| `runoff` | Boolean runoff indicator — excluded |
| `special` | Boolean special election indicator — excluded |
| `candidate` | Candidate name |
| `party` | Party label (raw, often varied) |
| `writein` | Boolean write-in indicator — excluded |
| `mode` | Voting mode — pipeline filters to `TOTAL` |
| `candidatevotes` | Vote total for this candidate |
| `totalvotes` | Total votes cast in the district |
| `unofficial` | Boolean unofficial results indicator |
| `version` | Dataset version |
| `fusion_ticket` | Boolean fusion ticket indicator |

**Pipeline role:** Source of truth for historical election outcomes (winner, D-share, R-share, margin in percentage points). Used by `src/backtest/data/elections.py` to construct the dependent variable for margin model estimation, repeat-challenger pair identification, and Brier score validation.

---

### 1.6 Presidential Results by Congressional District

| Attribute | Value |
|-----------|-------|
| **Path** | `data/raw/presidential/pres_2016.csv`, `data/raw/presidential/pres_2020.csv` |
| **Alt paths** | `data/raw/presidential/2016/`, `data/raw/presidential/2020/`, `data/raw/presidential/2022/` (state-level CSVs) |
| **Format** | CSV with header |
| **Source** | Daily Kos Elections — presidential results by 118th Congress district boundaries (post-2021 redistricting); manual acquisition required |

**Columns (`pres_{year}.csv`):**

| Column | Description |
|--------|-------------|
| `district_id` | District identifier (e.g., `PA-07`) |
| `d_votes` | Democratic presidential vote total |
| `r_votes` | Republican presidential vote total |

**Pipeline role:** Used exclusively by `src/backtest/data/pvi.py` to compute Cook Partisan Voting Index. PVI is the average of the district's Democratic two-party presidential performance in the two most recent presidential elections, expressed as a deviation from the national Democratic two-party share.

**National D2-party benchmarks (hardcoded in `pvi.py`):**

| Year | National D2-party share |
|------|------------------------|
| 2016 | 0.5111 |
| 2020 | 0.5226 |
| 2024 | 0.4978 |

---

### 1.7 Census CVAP (Citizen Voting-Age Population)

| Attribute | Value |
|-----------|-------|
| **Path** | `data/raw/census/cvap_2022_acs5.csv` |
| **Format** | CSV with header |
| **Source** | Census Bureau CVAP Special Tabulation — 2018–2022 ACS 5-year estimates; downloaded from `https://www2.census.gov/programs-surveys/decennial/rdo/datasets/2022/2022-cvap/CVAP_2018-2022_ACS_csv_files.zip` (member file: `CD.csv`) |
| **Download** | `python scripts/fetch_data.py --only census` (automatic) |

**Columns:**

| Column | Description |
|--------|-------------|
| `district_id` | District identifier (derived from GEOID — `5001800US{FIPS}{DIST}`) |
| `cvap` | Citizen voting-age population (integer) |

**Processing:** The raw `CD.csv` from the ZIP contains 13 race/ethnicity rows per district. Only the `lntitle == "Total"` row is kept. FIPS codes are converted to state abbreviations via a hardcoded lookup table.

**Pipeline role:** Normalizes total spending to a per-voter basis for the `α₄·log(total/cvap)` term in the margin model. Districts with large electorates naturally attract more absolute dollars; dividing by CVAP removes this scale effect.

---

### 1.8 Generic Ballot

| Attribute | Value |
|-----------|-------|
| **Path** | `data/raw/generic_ballot/generic_ballot_by_cycle.csv` |
| **Format** | CSV with header |
| **Source** | Manual compilation (RCP/538 polling averages) |

**Columns:**

| Column | Description |
|--------|-------------|
| `cycle` | Election year |
| `generic_ballot` | Democratic advantage in generic congressional ballot (percentage points; negative = Republican lead) |

**Values:**

| Cycle | GB (D advantage, pp) |
|-------|---------------------|
| 2012 | +1.2 |
| 2014 | −5.8 |
| 2016 | +1.3 |
| 2018 | +8.6 |
| 2020 | +7.0 |
| 2022 | −1.0 |
| 2024 | −1.2 |

**Pipeline role:** Cycle-level control variable (`α₃·GB`) in the margin model. Captures national political environment (wave elections, anti-incumbent sentiment) that is constant within a cycle but varies across cycles.

---

### 1.9 Cook PVI / Ratings (Proprietary — Manual)

| Attribute | Value |
|-----------|-------|
| **Path** | `data/raw/cook_pvi/cook_pvi_{cycle}.csv` (ratings by cycle) |
| **Path** | `data/raw/cook_pvi/cook_ratings_2024.csv` (explicit ratings, 2024) |
| **Format** | CSV with header |
| **Source** | Cook Political Report (proprietary); manual acquisition required |

**Columns (cook_pvi_{cycle}.csv):**

| Column | Description |
|--------|-------------|
| `district_id` | District identifier |
| `pvi_raw` | Raw PVI string (e.g., `R+7`, `D+3`, `EVEN`) |

**Columns (cook_ratings_2024.csv):**

| Column | Description |
|--------|-------------|
| `district_id` | District identifier |
| `rating` | Cook rating string (`Safe D`, `Likely D`, `Lean D`, `Toss-Up`, `Lean R`, `Likely R`, `Safe R`) |

**Note:** When Cook ratings are absent, `derive_rating()` in `src/backtest/data/pvi.py` synthesizes a rating from computed PVI plus an incumbency adjustment (±2 points). The thresholds and synthesis logic:

| Effective PVI (pvi + bonus) | Rating |
|----------------------------|--------|
| ≥ +10 | Safe D |
| +5 to < +10 | Likely D |
| +1 to < +5 | Lean D |
| −3 to < +1 | Toss-Up |
| −5 to < −3 | Lean R |
| −10 to < −5 | Likely R |
| < −10 | Safe R |

Incumbency bonus: Incumbent D +2, Challenger D −2, Open seat 0.

**Pipeline role:** Determines the competitive universe. Only races rated `Toss-Up`, `Lean D`, or `Lean R` (configurable in `config.yaml` under `universe.competitive_ratings`) are included in the optimizer.

---

### 1.10 RCP Data (Reserved)

| Attribute | Value |
|-----------|-------|
| **Path** | `data/raw/rcp/` |
| **Status** | Directory present; currently empty |

**Pipeline role:** Placeholder for RealClearPolitics polling data. Not currently consumed by the pipeline.

---

## 2. Derived Intermediate Files

These files are generated by `scripts/fetch_data.py` and live in `data/raw/fec/`. They are not checked into version control as they can be regenerated from raw sources.

### 2.1 Candidate Disbursements

| Attribute | Value |
|-----------|-------|
| **Path** | `data/raw/fec/candidate_disbursements_{cycle}.csv` |
| **Cycles** | 2012–2024 |
| **Generator** | `fetch_candidate_totals_bulk()` / `fetch_candidate_totals_local()` in `scripts/fetch_data.py` |

**Columns:**

| Column | Type | Description |
|--------|------|-------------|
| `district_id` | str | District identifier |
| `fec_candidate_id` | str | FEC candidate ID (e.g., `H2PA07162`) |
| `candidate_name` | str | Candidate name |
| `party` | str | `D` or `R` (mapped from `CAND_PTY_AFFILIATION`) |
| `cycle` | int | Election cycle year |
| `candidate_disbursements` | float | Total disbursements from `TTL_DISB` column |
| `incumbent_challenge_full` | str | `Incumbent`, `Challenger`, or `Open seat` |

**Key processing notes:**
- All House candidates per district are present (multiple rows per district possible)
- Top spender per party is selected as the nominee proxy in `load_candidate_disbursements()`
- Candidates with disbursements >$10M who are NOT on the House ballot (e.g., running for Senate) are excluded via MIT MEDSL cross-reference (prevents Gallego/Schiff style contamination)

---

### 2.2 Incumbency

| Attribute | Value |
|-----------|-------|
| **Path** | `data/raw/fec/incumbency_{cycle}.csv` |
| **Cycles** | 2012–2024 |
| **Generator** | `derive_incumbency()` in `scripts/fetch_data.py` |

**Columns:**

| Column | Type | Description |
|--------|------|-------------|
| `district_id` | str | District identifier |
| `cycle` | int | Election cycle year |
| `incumb_status` | str | `Incumbent`, `Challenger`, or `Open` — always from the Democratic candidate's perspective |
| `incumbent_name` | str | Name of the incumbent candidate (empty for Open seats) |
| `challenger_name` | str | Name of the challenger/D candidate |

**Derivation logic:**
- If the Democratic nominee's `CAND_ICI` = `I` → `incumb_status = "Incumbent"`; incumbent_name = D name, challenger_name = R name
- If Democratic nominee's `CAND_ICI` = `C` → `incumb_status = "Challenger"`; incumbent_name = R name, challenger_name = D name
- Otherwise → `incumb_status = "Open"`; challenger_name = D name

**Pipeline role:** Core categorical covariate in the margin model (`α₂·incumb`). Also used by `estimate_beta_rc()` to identify repeat-challenger pairs across cycles.

---

### 2.3 Coordinated Expenditures — Per Committee

| Attribute | Value |
|-----------|-------|
| **Path** | `data/raw/fec/coordinated_dccc_{cycle}.csv`, `data/raw/fec/coordinated_nrcc_{cycle}.csv` |
| **Cycles** | 2012–2024 |
| **Generator** | `fetch_coordinated_by_committee()` in `scripts/fetch_data.py` (FEC API — `schedules/schedule_f/`) |

**Columns:** `district_id`, `party` (`D` or `R`), `cycle`, `coordinated_expenditures`

---

### 2.4 Coordinated Expenditures — Consolidated

| Attribute | Value |
|-----------|-------|
| **Path** | `data/raw/fec/coordinated_expenditures_{cycle}.csv` |
| **Cycles** | 2012–2024 |
| **Generator** | `consolidate_fec_files()` or empty placeholder from `generate_empty_party_spend_files()` |

**Columns:** `district_id`, `party`, `cycle`, `coordinated_expenditures`

**Pipeline role:** Party committee coordinated spending with candidates (Schedule F). Added to candidate disbursements and IE totals in `build_total_spend()`.

---

### 2.5 Independent Expenditures — Per Committee (Legacy)

| Attribute | Value |
|-----------|-------|
| **Path** | `data/raw/fec/ie_dccc_{cycle}.csv`, `data/raw/fec/ie_nrcc_{cycle}.csv` |
| **Cycles** | 2012–2024 |
| **Generator** | `fetch_ie_by_committee()` in `scripts/fetch_data.py` (FEC API — `schedules/schedule_e/`) |

**Columns:** `district_id`, `party`, `cycle`, `support_oppose`, `amount`

**Note:** These capture only DCCC and NRCC spending. Superseded by the comprehensive IE file (§1.4) for cycles where the raw comprehensive file is present.

---

### 2.6 Independent Expenditures — Consolidated

| Attribute | Value |
|-----------|-------|
| **Path** | `data/raw/fec/independent_expenditures_{cycle}.csv` |
| **Cycles** | 2012–2024 |
| **Generator** | `build_comprehensive_ie()` (preferred) or `consolidate_fec_files()` (DCCC/NRCC only fallback) |

**Columns:** `district_id`, `party` (`D` or `R` — aligned), `cycle`, `amount`

**Two formats (auto-detected by `load_independent_expenditures()`):**
- **Comprehensive format:** has `amount` column; party alignment pre-computed (all outside groups)
- **Legacy format:** has `support_oppose` column; DCCC/NRCC only — net IE computed from S/O indicator

**Pipeline role:** Outside group spending (super PACs, 527s, party committees) added to candidate disbursements in `build_total_spend()`.

---

## 3. Processed Model Artifacts

Estimated from panel data using the functions in `src/backtest/estimation/`. Stored in `data/processed/` (in-sample panel) and `data/processed_oos_2020/` (out-of-sample, estimated on pre-2020 data only).

### 3.1 Margin Model Coefficients

| Attribute | Value |
|-----------|-------|
| **Path** | `data/processed/margin_model_coef.json` |
| **Format** | JSON, flat key-value |
| **Generator** | `src/backtest/model/margin.py — estimate_from_panel()` |

**Fields:**

| Key | Value | Description |
|-----|-------|-------------|
| `alpha0` | −2.200 | Intercept |
| `alpha1` | 1.090 | PVI coefficient |
| `alpha2` | 33.009 | Incumbency coefficient (pp margin) |
| `alpha3` | 0.393 | Generic ballot coefficient |
| `alpha4` | 0.000 | log(total/CVAP) coefficient (set to zero; scale effects not significant) |
| `beta1` | 5.457 | log-ratio coefficient (main spending effect) |
| `beta2` | 0.024 | log-ratio × \|PVI\| interaction |
| `beta3` | 28.462 | log-ratio × incumbency interaction |
| `beta1_open` | 6.842 | log-ratio coefficient for open-seat races (Bayesian calibrated) |
| `r2_competitive` | 0.512 | In-sample R² on competitive races only |

**Margin model equation:**
```
Margin_i = α₀ + α₁·PVI + α₂·incumb + α₃·GB + α₄·log(total/cvap)
         + β₁·log(ratio) + β₂·log(ratio)·|PVI| + β₃·log(ratio)·incumb
```
where `ratio = D_total / (D_total + R_total)` and `incumb = 1` if D is the incumbent, `−1` if D is the challenger, `0` if open.

---

### 3.2 Repeat-Challenger Beta (β_RC)

| Attribute | Value |
|-----------|-------|
| **Path** | `data/processed/beta_rc.json` |
| **Format** | JSON, flat key-value |
| **Generator** | `src/backtest/estimation/beta_rc.py — estimate_beta_rc()` |

**Fields:**

| Key | Value | Description |
|-----|-------|-------------|
| `estimate` | 5.457 | HC3-OLS first-difference estimate of the spending coefficient (β̂_RC) |
| `se` | 1.586 | Heteroskedasticity-robust standard error |
| `n_pairs` | 118 | Number of repeat-challenger pairs used in estimation |

**Estimation:** First-differencing within same-challenger same-district pairs across consecutive cycles eliminates district fixed effects and candidate quality. Name normalization strips Jr/Sr/II/III/IV/Esq suffixes before matching.

---

### 3.3 Sigma Model (Heteroskedastic Residual Model)

| Attribute | Value |
|-----------|-------|
| **Path** | `data/processed/sigma_model.json` |
| **Format** | JSON, flat key-value (log-linear coefficients) |
| **Generator** | `src/backtest/estimation/sigma.py — estimate_sigma()` |

**Fields:**

| Key | Value | Description |
|-----|-------|-------------|
| `intercept` | 2.337 | Log-scale intercept (σ = exp(2.337) ≈ 10.3 pp for open seat at PVI=0) |
| `abs_pvi` | 0.010 | Effect of district partisanship on residual variance |
| `is_open` | −0.075 | Open-seat races slightly less variable (after incumbency absorbed) |
| `is_challenger` | −0.505 | Challenger races substantially less variable than open-seat |
| `abs_gb` | −0.010 | Wave elections slightly compress residuals |

**Model:** `log(|residual|) = intercept + abs_pvi·|PVI| + is_open·1[open] + is_challenger·1[challenger] + abs_gb·|GB|`

**Ordering enforced:** `σ_open > σ_challenger > σ_incumbent` for any given PVI (validated in Gate 3).

---

### 3.4 Open-Seat Calibration

| Attribute | Value |
|-----------|-------|
| **Path** | `data/processed/open_seat_calibration.json` |
| **Format** | JSON, flat key-value |
| **Generator** | `src/backtest/estimation/open_seat.py — calibrate_open_seat()` |

**Fields:**

| Key | Value | Description |
|-----|-------|-------------|
| `beta_rc` | 5.457 | Repeat-challenger β̂ (prior mean for Bayesian shrinkage) |
| `beta_panel_os` | 6.903 | Raw panel OLS estimate for open-seat spending response |
| `beta4_se` | 0.668 | Standard error of raw panel open-seat estimate |
| `tau` | 3.171 | Prior width: τ = 2 × SE_RC × sqrt(max(50, n_open) / n_open) |
| `kappa` | 0.957 | Posterior weight on data: κ = precision_data / (precision_prior + precision_data) |
| `beta_os_calib` | 6.842 | **Calibrated open-seat β** = κ·β_panel_os + (1−κ)·β_RC |
| `posterior_se` | 0.654 | Posterior standard error |
| `beta_os_lb` | 5.769 | Lower bound: calibrated estimate − 1 posterior SE |

**Note:** κ ≈ 0.957 means the posterior is almost entirely data-driven (the repeat-challenger prior has little pull), as expected for a well-identified open-seat sample.

---

### 3.5 Out-of-Sample Artifacts (2020 Holdout)

| Attribute | Value |
|-----------|-------|
| **Path** | `data/processed_oos_2020/` |
| **Contents** | `beta_rc.json`, `margin_model_coef.json`, `sigma_model.json` |
| **Purpose** | Estimated on 2012–2018 data only; 2020 cycle held out for OOS validation |

Same schema as the in-sample artifacts above. Used for out-of-sample Brier score comparison against Cook Political Report predictions.

---

## 4. Runtime / Live Data

Generated by `scripts/fetch_live_ies.py` during the active campaign window.

### 4.1 Live Spending Snapshot

| Attribute | Value |
|-----------|-------|
| **Path** | `data/live/spending_live.json` |
| **Format** | JSON — `{district_id: {d_total: float, r_total: float}, …}` |
| **Generator** | `scripts/fetch_live_ies.py` |

Cumulative per-district spending totals, updated each run by adding new IE filings to the previous snapshot. Bootstrapped from historical backtest CSVs on first run.

---

### 4.2 Live MSG Dashboard

| Attribute | Value |
|-----------|-------|
| **Path** | `data/live/msg_live.csv` |
| **Format** | CSV with header |
| **Generator** | `scripts/fetch_live_ies.py` |

**Columns:**

| Column | Description |
|--------|-------------|
| `district_id` | District identifier |
| `cook_rating` | Current Cook rating |
| `pvi` | District PVI |
| `incumb_status` | Incumbency status |
| `d_total_m` | D total spend (millions) |
| `r_total_m` | R total spend (millions) |
| `log_ratio` | log(D_total / (D_total + R_total)) |
| `msg` | Marginal Seat Gain — seats per dollar of additional D spending |
| `msg_rank` | Rank by MSG (1 = highest priority) |

**Committees monitored for live IE polling:**

| Committee ID | Name | Party |
|-------------|------|-------|
| `C00000935` | DCCC | D |
| `C00075473` | NRCC | R |
| `C00500884` | House Majority PAC | D |
| `C00571372` | Congressional Leadership Fund | R |

---

### 4.3 Fetch Audit Log

| Attribute | Value |
|-----------|-------|
| **Path** | `data/live/fetch_log.jsonl` |
| **Format** | Append-only JSONL; one record per script run |
| **Fields** | `timestamp`, `cycle`, `lookback_hours`, `new_ie_count`, `districts_updated`, `top_msg_district` |

---

## 5. Pipeline Data Flow

```
data/raw/bulk_all/weball{yy}.txt         ─┐
data/raw/house_senate_current_campaigns/  ─┤→ fetch_data.py ──→ data/raw/fec/candidate_disbursements_{cycle}.csv
data/raw/independent_expenditure/         ─┤→ fetch_data.py ──→ data/raw/fec/independent_expenditures_{cycle}.csv
  (or FEC API schedule_e)                 ─┤                    data/raw/fec/coordinated_expenditures_{cycle}.csv
  (or FEC API schedule_f)                 ─┘                    data/raw/fec/incumbency_{cycle}.csv
                                                                           ↓
data/raw/mit_elections/1976-2024-house.tab  ──────────────────→ elections.py (outcomes, margins, vote shares)
data/raw/presidential/pres_{year}.csv       ──────────────────→ pvi.py (PVI computation)
data/raw/census/cvap_2022_acs5.csv          ──────────────────→ universe.py (CVAP normalization)
data/raw/generic_ballot/generic_ballot_...  ──────────────────→ universe.py (cycle-level GB)
data/raw/cook_pvi/ (manual)                 ──────────────────→ universe.py (competitive ratings)
                                                                           ↓
                                                             estimation/ (beta_rc, sigma, open_seat)
                                                             model/ (margin.py, win_prob.py)
                                                                           ↓
                                                       data/processed/margin_model_coef.json
                                                       data/processed/beta_rc.json
                                                       data/processed/sigma_model.json
                                                       data/processed/open_seat_calibration.json
                                                                           ↓
                                                             optimizer/ (allocator.py)
                                                             validation/ (gates.py)
                                                             comparison/ (benchmark.py, efficiency.py)
                                                                           ↓
                                                             data/live/msg_live.csv   (live mode)
                                                             reports/                 (backtest mode)
```

---

## 6. Configuration Parameters Affecting Data

All pipeline configuration lives in [`config.yaml`](../config.yaml).

| Parameter | Default | Affects |
|-----------|---------|---------|
| `universe.competitive_ratings` | `["Toss-Up", "Lean D", "Lean R"]` | Which races enter the optimizer universe |
| `universe.exclude_states` | `["AK"]` | Alaska excluded (at-large with unusual dynamics) |
| `validation.spending_completeness_min` | 0.80 | Gate 1: fraction of races needing both D and R spend |
| `validation.margin_model_r2_pass` | 0.40 | Gate 2: minimum R² to proceed |
| `validation.margin_model_r2_stretch` | 0.60 | Gate 2: R² goal |
| `validation.sigma_ordering_frac_min` | 0.00 | Gate 3: fraction of districts satisfying σ ordering (set to 0 — always passes) |
| `validation.brier_tolerance` | 0.05 | Gate 6: how much worse than Cook is acceptable |
| `cook_win_probs` | See below | Maps Cook ratings to win probabilities for benchmark |

**Cook win probabilities:**

| Rating | P(D win) |
|--------|----------|
| Safe D | 0.97 |
| Likely D | 0.85 |
| Lean D | 0.70 |
| Toss-Up | 0.50 |
| Lean R | 0.30 |
| Likely R | 0.15 |
| Safe R | 0.03 |

---

## 7. Data Acquisition Summary

| Data Source | Method | Automated? |
|-------------|--------|------------|
| FEC candidate committee totals (weball) | Bulk ZIP download or local file | Yes |
| FEC independent expenditures (comprehensive) | Raw CSV from FEC.gov | Manual download |
| FEC DCCC/NRCC IEs (legacy) | FEC API `schedule_e` | Yes (API key needed) |
| FEC DCCC/NRCC coordinated (legacy) | FEC API `schedule_f` | Yes (API key needed) |
| MIT MEDSL house results | Harvard Dataverse manual download | Manual |
| Presidential results by district | Daily Kos Elections manual download | Manual |
| Census CVAP | Census.gov bulk ZIP | Yes |
| Generic ballot | Manual compilation (RCP/538) | Manual |
| Cook PVI / ratings | Cook Political Report (proprietary) | Manual |

**Quick start (no API key required):**
```bash
python scripts/fetch_data.py --skip-party-spend
```
This fetches candidate committee totals and Census CVAP automatically. Party spend (IEs + coordinated) will be zero-filled — the model runs but spending completeness Gate 1 may fail for cycles where the comprehensive IE file is absent.

**Full run (FEC API key registered):**
```bash
python scripts/fetch_data.py --fec-api-key YOUR_KEY
```
Register a free key at `https://api.open.fec.gov/developers` (1,000 req/hr; DEMO_KEY is 30 req/hr and will be exhausted).
