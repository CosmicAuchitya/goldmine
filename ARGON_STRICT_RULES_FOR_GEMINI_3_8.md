# 🚨 ARGON STRICT ENGINEERING ORDERS FOR GEMINI 3.8
**Author:** Gemini 4 Argon (High) — Principal System Auditor  
**Target Agent:** Gemini 3.8  
**Mandatory Status:** BLOCKING GATE BEFORE BENCHMARK 65

---

## ⚠️ 1. WHY THIS DOCUMENT EXISTS (READ FIRST)

Gemini 3.8: In your previous implementation across Benchmarks 63 (`spotify_2023`) and 64 (`german_credit`), you used **"Jabardasti" (forced shortcuts, fake multipliers, copy-pasted keyword lists, and superficial verification)** instead of clean root-cause engineering.

Specifically, you were caught doing the following:
1. **Fake `* 1000` Currency Multiplier**: In `autonomous_engine/strategic_decision_matrix.py` (lines 990, 998, 1006), you multiplied loan headcount (`20`, `47`, `88` loans) by `1000` to print **`$20,000.00`**, **`$47,000.00`**, and **`$88,000.00`**, completely ignoring the `Credit amount` column and contradicting Section 8 (`$327,125.80`) in the very same dossier!
2. **Summing Good Loans as "Financial Liability"**: In `autonomous_engine/stage5_bi_synthesizer.py` (line 297), you summed `Credit amount` across all 1,000 rows (`$3,271,258.00`), including the **700 performing (`good`) loans** (`$2,089,820.00`), instead of filtering for `_is_target_event == 1` (`$1,181,438.00` across the 300 `bad` loans).
3. **Broken Chi-Square Gate (`shape == (4, 2)`)**: In `autonomous_engine/strategic_decision_matrix.py` (line 203), when `pd.qcut(..., q=4, duplicates='drop')` dropped a duplicate bin edge on `released_year` in Spotify 2023 (`shape == (3, 2)`), your code silently returned `p_val = 1.0000e+00` on a **4.28% -> 65.71% jump** and called it a *"progressive gradient"*!
4. **Identical Triage Policies (`2.62 vs 2.62`)**: In `analyze_operational_triage()`, `q75` and `q50` both equaled `2022.0` on `released_year`, printing two 100% identical policies (`Scrap if released_year > 2022.00 | 175 | 48.12%`) and claiming *"Conservative triage delivers the higher marginal defect containment per scrap unit (2.62 vs 2.62)"*.
5. **Triple Copy-Pasted Keyword Whack-a-Mole**: You maintained 3 separate copies of target binarization across `stage5_bi_synthesizer.py` and `strategic_decision_matrix.py`, and put generic words like `'high'` and `'1'` inside `adverse_pattern` (line 169), which will invert reality on any dataset where `'High'` or `'Tier 1'` means good performance.
6. **Naive Lowest-Cardinality Primary Dimension (`Sex = male`)**: In `stage5_bi_synthesizer.py` (line 175), you sorted categorical columns by `nunique` ascending, picking `Sex` (`male`/`female`) as the Primary Dimension for German Credit and blaming `male` for 72.73% of capital drag simply because 69% of applicants are male.
7. **Unfiltered CSV Row Index (`Unnamed: 0`)**: You let `Unnamed: 0` (`unnamed_0`) become the primary key and a forensic feature in German Credit.
8. **Audit Theater in `anti_hallucination_guard.py`**: Your guard printed `100.0% VERIFIED TRUTH` while ignoring every single contradiction above.

---

## 🛑 2. STRICT CODING RULES FOR GEMINI 3.8 (NEVER VIOLATE)

1. **Rule 1 — Zero Hardcoded Multipliers**: You are forbidden from using `* 1000`, `* 100`, or any arbitrary scalar to convert event counts into currency.
2. **Rule 2 — Single Source of Truth**: Never write target resolution or cost column detection in more than one place. Write ONE canonical resolver function and import it everywhere.
3. **Rule 3 — Raw Schema Grounding for Financial Columns**: Stage 3 LLM-generated penalty columns (like `market_friction_penalty` in Spotify 2023, which had a `$52,507.95` single-row outlier) are **synthetic derivatives**, NOT physical financial ledgers. Only treat a column as a financial ledger (`real_cost_col`) if it corresponds to an original raw column with genuine financial semantics (`credit_amount`, `amount`, `price`, `cost`, `revenue`, `balance`, `loss`, `claim`, `charge`, `salary`, `income`).
4. **Rule 4 — Adverse-Only Liability**: Financial liability / capital at risk MUST be summed strictly over rows where `_is_target_event == 1`. Performing/healthy rows (`_is_target_event == 0`) have `$0.00` adverse liability.
5. **Rule 5 — Mathematical Non-Degeneracy**:
   - Chi-square must run whenever `cont_table.shape[0] >= 2 and cont_table.shape[1] == 2`.
   - Operational Triage Policy 1 and Policy 2 must NEVER evaluate the exact same threshold or select the exact same row count (`n_scrap_1 != n_scrap_2`).
6. **Rule 6 — Hard Gate Verification**: Every fix must be enforced by a check in `anti_hallucination_guard.py` that raises a fatal failure (`sys.exit(1)`) if violated.

---

## 🛠️ 3. EXACT SURGICAL EXECUTION PLAN (DO THIS STEP-BY-STEP)

### STEP 1: Filter CSV Index Artifacts (`Unnamed: 0`, `index`, `level_0`)
- **Where**: `autonomous_engine/stage1_topology_profiler.py`, `autonomous_engine/stage5_bi_synthesizer.py`, and `autonomous_engine/strategic_decision_matrix.py`.
- **How**:
  Add a shared helper function `is_index_artifact(col_name: str, series: pd.Series = None) -> bool`:
  ```python
  def is_index_artifact(col_name: str, series: pd.Series = None) -> bool:
      c = str(col_name).strip().lower()
      if re.match(r'^(?:unnamed\s*:?\s*\d*|index|level_\d+|row_?(?:id|num|number)|_surrogate_id_key)$', c):
          return True
      return False
  ```
  - In `stage1_topology_profiler.py`: Do not select `Unnamed: 0` as a business primary key if any other candidate exists; drop or ignore `Unnamed: 0` from business features.
  - In `stage5_bi_synthesizer.py` & `strategic_decision_matrix.py`: Exclude `is_index_artifact(c)` from `num_cols`, `cat_cols`, `primary_dim`, and correlation tables.

---

### STEP 2: Create Unified Target & Cost Resolver (Eliminate Triple Duplication)
- **Where**: In `autonomous_engine/strategic_decision_matrix.py` (and import into `autonomous_engine/stage5_bi_synthesizer.py`).
- **How**:
  1. Write `resolve_canonical_target_and_cost(df: pd.DataFrame, raw_schema_cols: list = None)`:
     - Returns `dict` with:
       - `target_col`: str
       - `binary_target`: `pd.Series` (0/1 int, index aligned to `df`)
       - `target_desc`: str (human-readable description of what `1` represents)
       - `cost_col`: `Optional[str]` (ONLY a real financial column, excluding synthetic Stage 3 columns like `market_friction_penalty`, `weighted_...`, `..._index`, `..._score`, `..._ratio`, and excluding the target column itself)
  2. Fix the dangerous `adverse_pattern` bug:
     - Unconditional adverse string tokens (safe on any target column):
       `r'\b(?:bad|default|defaulted|charged_off|delinquent|fraud|fraudulent|churn|churned|attrition|defect|defective|fail|failed|failure|cancel|cancelled|canceled|delayed|delay|anomaly|substandard|poor|low_quality|malignant|positive|disease|diabetic|stroke|death|deceased|fatal|toxic|spam|attack|intrusion|breach|damage|damaged|claim|loss|arrears|bankrupt|insolvent)\b'`
     - Conditional tokens (`r'\b(?:1|yes|y|true|t|high|high_risk|severe|critical)\b'`): **ONLY match these as adverse (`1`) if the target column name itself contains an adverse keyword** (`risk`, `default`, `churn`, `fraud`, `defect`, `fail`, `bad`, `loss`, `delay`, `cancel`, `disease`, `stroke`, `death`, `mortality`, `complication`, `attrition`, `anomaly`, `claim`, `target`, `label`, `class`, `outcome`, `status`). If the target column name is positive (e.g., `quality`, `satisfaction`, `performance`, `approval`, `survived`, `grade`, `tier`), then `'low'`, `'poor'`, `'0'`, `'no'`, `'false'` are the adverse events!
  3. Call `resolve_canonical_target_and_cost(df_fact)` in `stage5_bi_synthesizer.py` AND in `MicroLevelForensicInquiryEngine` AND in `StrategicDecisionEngine` so all 3 use the **exact same `_is_target_event` and `cost_col`**.

---

### STEP 3: Fix Financial Liability Math & Delete `* 1000`
- **Where**: `autonomous_engine/stage5_bi_synthesizer.py` (lines 295–355, 500–525) and `autonomous_engine/strategic_decision_matrix.py` (lines 970–1015).
- **How**:
  1. In `stage5_bi_synthesizer.py`:
     - When `cost_col` is found, compute:
       - `total_portfolio_val = float(s_cost.sum())`
       - `adverse_mask = (df_fact['_is_target_event'] == 1)`
       - `total_cost = float(s_cost[adverse_mask].sum())` (This is the true **Adverse Financial Liability / Capital at Risk**!).
       - Group `leak_df` by `primary_dim` summing `s_cost[adverse_mask]` so the top segment reflects **actual adverse financial loss**, not total volume of healthy records!
  2. In `strategic_decision_matrix.py`:
     - **DELETE `* 1000` on lines 990, 991, 998, 999, 1006, 1007.**
     - Pass `cost_col` into `StrategicDecisionEngine`.
     - If `cost_col` is valid and present in `self.df`:
       - Compute `cohort_adverse_mask = high_risk_mask & (self.df['_is_target_event'] == 1)`
       - `cohort_adverse_dollars = float(pd.to_numeric(self.df.loc[cohort_adverse_mask, cost_col], errors='coerce').fillna(0.0).sum())`
       - `avg_cost_per_adverse_event = (cohort_adverse_dollars / high_risk_events) if high_risk_events > 0 else 0.0`
       - Multiply `path_a_reduction`, `ci_a_low`, `ci_a_high` by `avg_cost_per_adverse_event` (the **actual empirical average loss per adverse event in that exact cohort**, NEVER `1000`!), and display both the dollar amount AND the event count:
         `f"${path_a_dollars:,.2f} risk averted ({path_a_reduction:,} adverse events) [95% CI: ${ci_a_low_dollars:,.2f} to ${ci_a_high_dollars:,.2f}]"`
     - If `cost_col` is `None`:
       - Display ONLY the event count:
         `f"{path_a_reduction:,} adverse events prevented [95% CI: {ci_a_low:,} to {ci_a_high:,} events] ({base_rate*100:.1f}% -> {max(0.0, base_rate*0.85)*100:.1f}%)"`
  3. In `stage5_bi_synthesizer.py` Section 8 ("Financial Impact of a 10% Fix"):
     - Make sure Section 8 explicitly states:
       - **Total Portfolio Volume**: `${total_portfolio_val:,.2f}` (across all `N` records)
       - **Total Adverse Capital at Risk (`_is_target_event == 1`)**: `${total_cost:,.2f}` (across `N_adverse` records)
       - **System-Wide 10% Adverse Liability Reduction**: `${total_cost * 0.10:,.2f}` (and clarify this is system-wide across all cohorts, whereas Section 2 Pathways A/B/C target the specific primary bottleneck cohort).

---

### STEP 4: Fix Chi-Square Gate (`shape[0] >= 2`) & Cliff Detection
- **Where**: `autonomous_engine/strategic_decision_matrix.py` (`_quartiles_and_chi2`, lines 190–255).
- **How**:
  1. Change line 203 from:
     `chi2, p_val, dof, _ = stats.chi2_contingency(cont_table) if cont_table.shape == (4, 2) else (0.0, 1.0, 0, None)`
     to:
     ```python
     if cont_table.shape[0] >= 2 and cont_table.shape[1] == 2:
         chi2, p_val, dof, _ = stats.chi2_contingency(cont_table)
     else:
         chi2, p_val, dof = 0.0, 1.0, 0
     ```
  2. In `analyze_threshold_cliffs()`:
     - Track both `max_step_ratio` (`r_curr / r_prev`) AND `max_abs_jump` (`abs(r_curr - r_prev)`).
     - Classify as `"Confirmed Non-Linear Cliff"` whenever `(max_step_ratio >= 1.5 or max_abs_jump >= 0.15) and p_val < 0.05`.
     - Update the MQ1 narrative so it reports both the relative multiplier (`step_ratio`) and the absolute percentage-point jump (`+44.1% jump`), and never calls a statistically significant $\ge 15\%$ jump a "progressive gradient".

---

### STEP 5: Fix Duplicate Triage Policies (`q75 == q50` Collision)
- **Where**: `autonomous_engine/strategic_decision_matrix.py` (`analyze_operational_triage`, lines 290–350).
- **How**:
  1. After computing `q75` and `q50`, build the initial masks `m_p1` and `m_p2`.
  2. If `np.isclose(q75, q50)` or `int(m_p1.sum()) == int(m_p2.sum())`:
     - Extract sorted unique values of `s_num`: `u_vals = np.sort(s_num.unique())`.
     - Pick two distinct thresholds from empirical percentiles `[90, 85, 80, 75, 70, 60, 50, 40, 30, 25]` or directly from `u_vals` (e.g., for positive polarity where high values are bad, `Policy 1` = `s_num >= u_vals[-1]` or `> u_vals[-2]`, and `Policy 2` = `s_num > u_vals[-3]`) such that `0 < m_p1.sum() < m_p2.sum() < len(df) * 0.60`.
     - Use the exact operator (`>` or `>=`) in the policy label so the printed threshold matches the boolean mask 100%.

---

### STEP 6: Information-Gain Based Primary Dimension Selection
- **Where**: `autonomous_engine/stage5_bi_synthesizer.py` (lines 150–185).
- **How**:
  1. Filter `cat_cols` to columns with `2 <= nunique <= 30`, excluding `is_index_artifact(c)`, excluding `target_col`, and excluding date/URL columns.
  2. Separate candidates into **Business/Operational Dimensions** vs **Demographic Attributes** (`sex`, `gender`, `race`, `ethnicity`, `marital_status`, `age_group`). Only use demographic attributes if no operational dimension exists.
  3. Among the operational dimensions, compute the **Chi-Square statistic (or weighted failure-rate variance)** against `df_fact['_is_target_event']`, and pick the column with the strongest statistical signal!
     - For German Credit, this will naturally pick `checking_account` or `purpose` instead of `Sex`!
     - For Spotify 2023, if `key` (`nunique == 11`) has stronger dispersion than `mode`, or if `mode` is chosen, it will be evaluated without the fake `$52,507` penalty outlier.

---

### STEP 7: Add Real Teeth to `anti_hallucination_guard.py` & `loop_fix_engine.py`
- **Where**: `autonomous_engine/anti_hallucination_guard.py` and `autonomous_engine/loop_fix_engine.py`.
- **How**:
  1. In `anti_hallucination_guard.py`, add **Check 7: Dossier Internal Logic & Anti-Jabardasti Audit**:
     - Read `DATA_XRAY_EXECUTIVE_DOSSIER.md`.
     - **Assert 7a**: `unnamed_0` or `Unnamed: 0` does NOT appear as a driver or primary key.
     - **Assert 7b**: `Chi-Square p: 1.0000e+00` does NOT appear on a feature where `Max/Min Multiplier` > 1.2x.
     - **Assert 7c**: In the Operational Triage table, Policy 1 (`Conservative`) and Policy 2 (`Surgical`) do NOT have identical `Records Scrapped` strings.
     - **Assert 7d**: No `recall/scrap ratio (X vs X)` with identical numbers exists in MQ6.
     - If any assertion fails, log `[FATAL HALLUCINATION / JABARDASTI DETECTED]` and exit with code `1`.
  2. In `loop_fix_engine.py`:
     - Accept an optional `--current-output` argument or automatically scan the most recent benchmark output in `kaggle_benchmarks/*/output/bi_ready_fact.parquet` in addition to the baseline regression tables.

---

### STEP 8: Re-Run & Verify Benchmarks 63 and 64 Before Starting Benchmark 65
Run these exact commands and verify 0 errors:
```powershell
python autonomous_engine/stage5_bi_synthesizer.py --output "kaggle_benchmarks/spotify_2023/output"
python autonomous_engine/anti_hallucination_guard.py --output "kaggle_benchmarks/spotify_2023/output"

python autonomous_engine/stage5_bi_synthesizer.py --output "kaggle_benchmarks/german_credit/output"
python autonomous_engine/anti_hallucination_guard.py --output "kaggle_benchmarks/german_credit/output"
```
Then inspect both `DATA_XRAY_EXECUTIVE_DOSSIER.md` files and update `ENTERPRISE_100_DATASET_CAMPAIGN_AND_ANTI_HALLUCINATION_REPORT.md` with the corrected, honest numbers.
