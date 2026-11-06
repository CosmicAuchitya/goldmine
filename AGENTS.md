# AGENTS.md — System Context & Operational Directives for AI Agents (Argon / Gemini / Antigravity)

Welcome, Agent. This repository contains **DataX-Ray**, an enterprise-grade autonomous AI data engineering, analytics, self-healing, and forensic intelligence engine.

Read this document carefully before taking any action. It details **what is happening here**, **where we currently stand**, **the exact architecture**, and **how you must operate**.

---

## 🎯 1. Executive Mission & Current Project State

### The Mission:
To build, prove, and certify an **Autonomous Enterprise Data Engine** capable of processing diverse enterprise datasets from raw schema ingestion to C-suite forensic intelligence and Power BI/Tableau deliverables with:
- **Zero Human Intervention** (Autonomous DAG formulation, code generation, and self-healing).
- **Zero Hallucination** (100.0% of claims mathematically grounded in physical DuckDB Parquet tables).
- **Zero Multiplicity Drift** (100% row preservation across complex 1:N / N:M relational joins).
- **Zero Bias / Honest Advisory** (Never force dictates; present Conservative, Surgical, and Structural pathways with audited pros, cons, and collateral friction).
- **Micro-Level Forensic Inquiry** (Formulate granular questions and empirical answers using decile cliffs, 2x2 interaction matrices, and Simpson's Paradox defenses).

### Current Live Milestone:
- **Completed Benchmarks**: **82 of 100 Enterprise Benchmarks Certified** (**82.0% Complete**).
- **Total Physical Fact Rows Audited**: **12,406,755 Physical Records** across 82 projects.
- **Cartesian Multiplicity Drift**: **0 Rows (0.00%)**.
- **Primary Key Collisions**: **0 Duplicates**.
- **Hallucinated Columns Found**: **0 Columns (100.0% Physical Ground Truth Verified)**.
- **Total Execution Time**: **3,952.66 seconds** (~65.88 minutes cumulative).
- **Last Completed Project**: **Benchmark 82 (`kaggle_benchmarks/dynamic_supply_chain_logistics/raw_data/`)** — Dynamic Supply Chain Logistics & Fleet Disruption Forensics (32,065 fleet records, 15 fulfillment disruptions (0.05%), $7.77K adverse shipping drag, $14.73M total shipping portfolio volume, primary dimension `risk_classification`, Statistical Circuit-Breaker: Uniform noise with $0 CapEx freeze, 100% physically truth grounded, 0 Cartesian drift)** — Retail Customer Shopping Trends & Merchandising Forensics (3,900 customer accounts, 1,004 substandard ratings (25.74%), $59.15K adverse spend drag, $233.08K total portfolio volume, primary dimension `Category`, Statistical Circuit-Breaker: Uniform noise p=0.2079 with $0 CapEx freeze, 100% physically truth grounded, 0 Cartesian drift).
- **Recent Certified Quintet / Sextet (Benchmarks 76 to 81)**: **Benchmarks 76, 77, 78, 79, 80, 81 Certified with Full Stage 6 & Stage 7 Deployments**:
  - **Benchmark 76 (`loan_default`)**: 255,347 loans, 29,653 defaults (11.61%), $4.29B adverse principal drag ($32.58B total portfolio volume), high interest rate cliff > 19.25%, 0 drift.
  - **Benchmark 77 (`ecommerce_customer_service`)**: 85,907 service tickets, 26,290 dissatisfied CSAT tickets (30.60%), $66.09M adverse drag ($164.66M order volume), Order Related category bottleneck (43.0% of system friction), 0 drift.
  - **Benchmark 78 (`insurance_claims_risk`)**: 58,592 automotive policies, 3,748 claims (6.40%), primary dimension `segment` (B2 highest claim frequency at 6.86%), 0 drift.
  - **Benchmark 79 (`financial_credit_default`)**: 10,000 credit accounts, 333 defaults (3.33%), $128.23M adverse salary drag ($4.02B total salary volume), primary dimension `Employed`, 0 drift.
  - **Benchmark 80 (`telecom_users`)**: 5,986 telecom users, 1,587 churn events (26.51%), $117.70K adverse monthly MRR drag ($387.91K total monthly volume), primary dimension `TipoContrato` (Month-to-month contract bottleneck), 0 drift.
  - **Benchmark 81 (`customer_shopping_trends`)**: 3,900 customers, 1,004 substandard ratings (25.74%), $59.15K adverse spend drag ($233.08K total volume), primary dimension `Category` (Circuit-Breaker: uniform noise p=0.2079, $0 CapEx freeze), 0 drift.
- **Hardening, Business Product & Stage 7 Bespoke Dashboard Milestones**: V5.5 Bespoke Executive Dashboard Architect Layer — Domain Intelligence & Persona Judgment (12 Ontologies x 5 Executive Design Archetypes: Swiss Institutional, Nordic SaaS, Editorial Commerce, Industrial SCADA, Clinical Diagnostic), Data-Shape Adaptive Panel Selection (10-Widget Component Catalog, zero fabricated $ on non-monetary datasets, $0 CapEx spend freeze on noise), Zero-CDN 100% Self-Contained Interactive HTML Application (`bespoke_executive_dashboard.html`, client-side DuckDB micro-cube cross-filtering with zero multiplicity drift, live English/Hinglish bilingual switcher, live Light/Dark theme toggle, interactive What-If ROI excess-risk simulator, embedded priority worklist explorer), Design Feasibility & Impact Index (DFII >= 11), Anti-Hallucination Guard Check 11 (XSS & Zero-CDN verification, physical DuckDB math cross-verification on DASHBOARD_PAYLOAD, micro-cube zero drift check, monetary ledger validation, panel need validation); plus V5.0 Non-Coder Business Product Layer — Read-Only C-Level DuckDB Sandboxed English/Hinglish Conversational Q&A (`conversational_qa_engine.py`), Two-Queue Row-Level Actionable Priority Worklists (`actionable_priority_worklist.csv`), Zero-Jargon Plain Business English + Roman-Hinglish Executive Brief (`PLAIN_BUSINESS_SUMMARY.md`), Genuine Calendar Period-over-Period Temporal Trend Scanner (`temporal_trend_summary.json` + Vega-Lite trend chart), Self-Serve Drag-and-Drop Web Portal (`app_dashboard.py`), FastAPI REST Server & Non-Root Docker Deployment (`api_server.py`, `Dockerfile`, `.dockerignore`); plus V4.6 Security Hardening — Static AST Security Gate & Least-Privilege Subprocess Env Scrubbing (`validate_etl_ast_security` + `build_sanitized_subprocess_env`), Indirect Prompt-Injection Defense (`validate_and_sanitize_blueprint` + untrusted schema boundary tags + zero untrusted system-instruction interpolation), Token-aware Multilingual PII & Traceback Scrubbing (`pii_scrubber.py`), Per-Run Concurrency Isolation (`runs/<run_id>/artifacts/`), Zip-Slip & Workspace Path-Traversal Guards (`safe_extract_zip` + `resolve_safe_workspace_path`), OWASP JSON-in-HTML XSS Neutralization & Air-Gapped Offline Dashboard Renderer, Live DuckDB SQL Formula Execution, Cross-Wired Rate Audit & Governance Checklist Verification in `anti_hallucination_guard.py`, Built-in Monolithic Test Suite CLI (`python pikabo/pikabo.py --test` — 7/7 passing), Full Pytest Invariant, Adversarial Security & Business Product Suite (`tests/` — 60/60 passing), Dual-stream structured rotating logging (`runs/logs/enterprise_pipeline.log`), Enterprise Stage 6 Semantic Model & Auto-Viz Synthesizer, Multi-table 1:N relational pre-aggregation, V4.0 Statistical Circuit-Breaker, Epidemiological Excess-Risk Math, Wilson & Newcombe 95% CIs, two-proportion pooled z-tests, and model-fallback rate limiter across healthy endpoints.
- **Next Target**: **Benchmark 83** (Ready for selection and harvesting).

---

## 🏛️ 2. Core Autonomous Pipeline Architecture (`autonomous_engine/`)

The core engine is located in `autonomous_engine/` and orchestrated via `master_orchestrator.py`:

```
[Raw Data Files (CSV/Excel/Parquet)]
                 │
                 ▼
[Stage 1: Topology Profiler & Cardinality Scanner] (`stage1_topology_profiler.py`)
  ├── PII scrubbing (100% local, no sensitive data sent to LLM)
  ├── Composite key detection & cardinality hazard analysis (1:1, 1:N, N:M)
  └── Outputs: `schema_topology.json`
                 │
                 ▼
[Stage 2: Paced Gemini Blueprint Architect] (`stage2_ai_blueprint.py`)
  ├── Multi-key rate-limiting pool (`rate_limiter.py` - 28 RPM across keys)
  ├── Star-Schema dimensional modeling & primary fact designation
  └── Outputs: `execution_blueprint.json`
                 │
                 ▼
[Stage 3: Vectorized Python ETL Synthesizer] (`stage3_ai_code_generator.py`)
  ├── Invariant assertion gates (len(final_fact) == len(initial_fact))
  ├── Pre-aggregation of 1:N dimensions to prevent Cartesian explosion
  └── Outputs: `dynamic_etl_runner.py` (pre-compiled AST syntax check)
                 │
                 ▼
[Stage 4: Sandbox Executor & Self-Healing Loop] (`stage4_sandbox_executor.py`)
  ├── Safe execution subprocess with timeout guard
  ├── Autonomous AST self-healing compiler (catches runtime exceptions, patches code)
  └── Deterministic DAG fallback (`templated_dag_runner.py`) if retry budget exhausted
                 │
                 ▼
[Stage 5: Enterprise BI & Micro-Level Forensic Synthesizer] (`stage5_bi_synthesizer.py`)
  ├── Power BI / Tableau Star-Schema DAX measures guide (`POWERBI_TABLEAU_MEASURE_GUIDE.md`)
  ├── Normalized dimensional CSVs (`bi_dim_*.csv`) and Parquet fact (`bi_ready_fact.parquet`)
  └── Strategic Decision & Micro-Forensic Engine (`strategic_decision_matrix.py`)
                 │
                 ▼
[Stage 6: Enterprise Semantic Model & Auto-Viz Synthesizer] (`stage6_semantic_viz_synthesizer.py`)
  ├── Microsoft Power BI / Fabric TMDL Semantic Model (`semantic_model/` with `model.tmdl`, `tables/`, `relationships.tmdl`)
  ├── Universal Machine-Readable Metrics Manifest (`semantic_metrics_manifest.json` - MetricFlow/Cube compatible)
  ├── Certified Vega-Lite v5 Visual Specifications (`vega_lite_dashboard_spec.json`)
  ├── Standalone Executive Interactive Web Dashboard (`enterprise_interactive_dashboard.html`)
  └── Human Certification Audit Gate & Sign-Off Checklist (`CERTIFICATION_AUDIT_CHECKLIST.md`)
                 │
                 ▼
[Stage 7: Autonomous Bespoke Executive Dashboard Architect] (`stage7_bespoke_dashboard_architect.py`)
  ├── Domain ontology matching & Executive Persona Archetype selection (5 bespoke design archetypes)
  ├── Data-shape adaptive panel selection (10-widget component catalog with mathematical suitability guards)
  ├── Client-side DuckDB zero-drift micro-cube compilation (sum(volume) == total_records, zero Cartesian drift)
  ├── Standalone Zero-CDN Interactive HTML Application (`bespoke_executive_dashboard.html`)
  │     ├── Native interactive SVG charts with mouseover tooltips & zero external scripts/styles
  │     ├── Live Bilingual switch (🇬🇧 English | 🇮🇳 Roman Hinglish) & live Theme switcher (☀️ Light | 🌙 Dark)
  │     ├── Interactive What-If ROI Excess-Risk Simulator with statistical error bounds
  │     └── Searchable frontline priority worklist explorer with one-click CSV export
  └── Outputs: `dashboard_design_blueprint.json` (DFII >= 11) + `bespoke_executive_dashboard.html`
                 │
                 ▼
[Post-Execution Continuous Invariant Audits]
  ├── `anti_hallucination_guard.py` (DuckDB physical SQL verification vs LLM claims + Manifest Invariants + Check 11 Bespoke Dashboard Audit)
  └── `loop_fix_engine.py` (Continuous regression testing across historical benchmarks)
```

---

## 🔬 3. The Micro-Level Forensic Inquiry Engine (`MicroForensicEngine`)

When analyzing datasets, **do NOT settle for macro-level correlations** (e.g. "Metric A correlates with B"). You MUST activate the micro-level inquiry engine:

1. **Non-Linear Threshold Cliffs**:
   - Discretize continuous distributions into quartiles/deciles.
   - Detect the exact quantitative threshold where performance/failure flips abruptly (e.g., volatile acidity $> 0.52\text{ g/dm}^3$ flips substandard failure from 23% to 55%).
2. **2x2 Orthogonal Feature Interaction Matrix**:
   - Identify top positive risk driver and top protective driver.
   - Formulate 4 quadrants (Optimal Zone, Unbuffered Baseline, Masked Risk, Compound Catastrophe).
   - Test whether protective factors can mask risk, or if risk drivers exert dominant negative override.
3. **Compound Tail Risk**:
   - Audit worst 5% catastrophic records.
   - Determine if failures stem from single-variable anomalies or multi-threshold compound breaches.
4. **Operational Triage Scrap vs Purity Yield Boundary**:
   - Simulate multiple intake filtering policies (Conservative, Surgical, Compound).
   - Calculate exact confusion matrix: Scrapped batches, defect recall %, retained failure rate %, and false discard of acceptable product.
5. **Simpson's Paradox & Confounder Defense**:
   - Detect collinear feature pairs ($|r| > 0.40$).
   - Perform quartile-stratified correlation to verify if apparent effects collapse when controlling for the confounder.
6. **Autonomous Q&A Formulation ("her jagha question socho aur answer dhuno")**:
   - Autonomously generate 6 to 8 deep, skeptical executive questions (MQ1 to MQ8).
   - Compute and present physically audited, empirical answers with exact numbers and p-values.

---

## ⚖️ 4. User Core Directives & Golden Rules

When interacting with the user or generating deliverables, adhere strictly to these principles:

1. **Raste Dikhana Hai, Majboor Nahi Karna (Present Viable Options, Never Dictate)**:
   - Provide 3 distinct strategic options: **Pathway A (Conservative)**, **Pathway B (Surgical)**, **Pathway C (Structural)**.
   - For every option, provide honest **Fayda (Pros)**, **Nuksan (Cons)**, and **Collateral Friction (Team/Organizational drag)** with 95% statistical confidence bounds.
2. **Zero Bias / Non-Dogmatic**:
   - Do not preach subjective business advice (e.g. do not say "fire staff" or "raise prices"). Let the data speak through audited numbers.
3. **Zero Hallucination Grounding**:
   - Every number mentioned in a dossier or response MUST match the DuckDB SQL reflection on the Parquet fact table. If you didn't query it from data, do not state it.
4. **Self-Healing Resilience**:
   - If an ETL script encounters a type error or syntax glitch, let Stage 4 catch it, create a backup, patch the AST, and re-execute cleanly.

---

## 🛠️ 5. How to Run the Next Benchmark (Benchmark 62+)

### Step 1: Download Target Dataset from Kaggle
```powershell
python autonomous_engine/kaggle_harvester.py --slug "<owner>/<dataset-name>" --dest "kaggle_benchmarks/<benchmark_name>/raw_data"
```

### Step 2: Prepare Clean Output Directory
```powershell
if (Test-Path "kaggle_benchmarks/<benchmark_name>/output") { Remove-Item -Recurse -Force "kaggle_benchmarks/<benchmark_name>/output" }
New-Item -ItemType Directory -Force "kaggle_benchmarks/<benchmark_name>/output"
```

### Step 3: Run the Autonomous Master Pipeline
```powershell
python autonomous_engine/master_orchestrator.py --data "kaggle_benchmarks/<benchmark_name>/raw_data" --output "kaggle_benchmarks/<benchmark_name>/output"
```

### Step 4: Verify Ground Truth via DuckDB
```powershell
python -c "import duckdb; p = r'kaggle_benchmarks/<benchmark_name>/output/bi_ready_fact.parquet'; print(duckdb.query(f'SELECT count(*) as total_rows, count(distinct Id) as unique_keys FROM read_parquet(\'{p}\')').df())"
```

### Step 5: Update the Master Campaign Report
Open and append the benchmark findings to:
`C:\Users\91945\.gemini\antigravity\brain\1d6bc462-5073-421e-8214-0b3b58a1f206\ENTERPRISE_100_DATASET_CAMPAIGN_AND_ANTI_HALLUCINATION_REPORT.md`
- Update Table 1 (Row count, drift, time, status).
- Update Section 2 (Physical DuckDB query evidence, Micro Q&A findings).

---

## 📁 6. Workspace Layout Reference

```
c:\Users\91945\OneDrive\Desktop\XXX\Ai aotumation learning\
├── AGENTS.md                                             <-- THIS FILE (Primary Agent Briefing)
├── README.md                                             <-- Project Master Architecture & Navigation
├── autonomous_engine/                                    <-- Core Engine Codebase
│   ├── master_orchestrator.py                            <-- Main Entry Point for Benchmarks (Stages 1-7)
│   ├── stage1_topology_profiler.py                       <-- Stage 1 Profiler & Cardinality Scanner
│   ├── stage2_ai_blueprint.py                            <-- Stage 2 Blueprint Architect (Gemini API)
│   ├── stage3_ai_code_generator.py                       <-- Stage 3 Dynamic Python ETL Generator
│   ├── stage4_sandbox_executor.py                        <-- Stage 4 Sandbox Executor & AST Self-Healer
│   ├── stage5_bi_synthesizer.py                          <-- Stage 5 BI & Measure Guide Synthesizer
│   ├── stage6_semantic_viz_synthesizer.py                <-- Stage 6 Semantic Model & Auto-Viz Synthesizer
│   ├── stage7_bespoke_dashboard_architect.py             <-- Stage 7 Grand Finale: Domain Bespoke HTML Architect
│   ├── strategic_decision_matrix.py                      <-- Micro-Forensic & Decision Matrix Engine V3.5
│   ├── conversational_qa_engine.py                       <-- Read-Only DuckDB Bilingual Q&A Engine
│   ├── business_action_exporter.py                       <-- Two-Queue Worklist & Temporal Trend Exporter
│   ├── app_dashboard.py                                  <-- Self-Serve Drag-and-Drop Web Portal (Streamlit)
│   ├── api_server.py                                     <-- Enterprise FastAPI REST Server
│   ├── anti_hallucination_guard.py                       <-- DuckDB Physical Ground-Truth Verifier (Checks 1-11)
│   ├── loop_fix_engine.py                                <-- Continuous Multi-Dataset Regression Verifier
│   ├── target_resolver.py                                <-- Single Source of Truth for Targets & Costs
│   ├── pii_scrubber.py                                   <-- Multilingual PII & Traceback Scrubber
│   ├── rate_limiter.py                                   <-- Multi-Key Gemini API Pool (28 RPM)
│   └── templated_dag_runner.py                           <-- Deterministic Out-of-Core DAG Fallback
├── pikabo/                                               <-- Monolithic Standalone Reference Engine
│   ├── sync_pikabo.py                                    <-- Monolith Compiler & Synchronizer
│   └── pikabo.py                                         <-- Compiled 31-Agent Standalone Monolith (7/7 self-test)
├── tests/                                                <-- Full Invariant, Security & Stage 7 Test Suite
│   ├── test_stage7_bespoke_dashboard.py                  <-- 16 Stage 7 Bespoke Dashboard Invariant Tests
│   ├── test_business_product_layer.py                    <-- 21 Business Product & Q&A Invariant Tests
│   ├── test_security_and_hardening.py                    <-- 12 AST Security & Sandbox Invariant Tests
│   ├── test_target_resolver.py                           <-- 3 Canonical Target Resolution Tests
│   ├── test_statistics.py                                <-- 3 Micro-Forensic Statistical Tests
│   ├── test_topology_pii.py                              <-- 3 Topology & PII Scrubbing Tests
│   └── test_rate_limiter.py                              <-- 2 Rate Limiter Pool Tests
├── 02_domain_intelligence/                               <-- Master Business Ontologies (12 Business Models)
│   └── business_ontology.py                              <-- Global Business Knowledge Base
├── kaggle_benchmarks/                                    <-- Benchmarks 1 through 61
│   ├── wine_quality/                                     <-- Benchmark 61 (Latest Completed)
│   │   ├── raw_data/WineQT.csv
│   │   └── output/
│   │       ├── bi_ready_fact.parquet                     <-- Physical DuckDB Fact Table
│   │       ├── DATA_XRAY_EXECUTIVE_DOSSIER.md            <-- Micro-Level Forensic Dossier (8 Q&As)
│   │       └── POWERBI_TABLEAU_MEASURE_GUIDE.md          <-- Enterprise Star-Schema DAX Guide
├── .env                                                  <-- Multi-Key API Configuration
└── runs/                                                 <-- Execution Telemetry & Run Logs
```

Now you know everything that has transpired, the exact mathematical standards expected, and how to continue driving the autonomous engine forward.

---

## 🚨 7. ARGON MANDATORY ANTI-"JABARDASTI" LAWS & REMEDIATION SPEC (FOR GEMINI 3.8)

> **CRITICAL DIRECTIVE FROM GEMINI 4 ARGON TO GEMINI 3.8**:
> The user audited your previous fixes in Benchmarks 63 (`spotify_2023`) and 64 (`german_credit`) and caught multiple instances of **"Jabardasti" (forced shortcuts, fake multipliers, keyword whack-a-mole, and superficial validation)**. You are STRICTLY FORBIDDEN from writing surface-level hacks to make tests pass. You MUST follow the **6 Iron Laws** and execute the **8 Mandatory Surgical Fixes** below before touching Benchmark 65.

### 🛑 THE 6 IRON LAWS (ZERO TOLERANCE FOR "JABARDASTI")

1. **NO FAKE MULTIPLIERS OR INVENTED CURRENCY (`* 1000` BAN)**:
   - NEVER multiply an event count (`high_risk_events`, `path_a_reduction`) by a hardcoded number like `1000` to fabricate a dollar figure (`$20,000.00`).
   - If a real monetary column exists in the raw schema, compute dollar exposure by summing that physical column **ONLY on adverse rows (`_is_target_event == 1`)** inside the specific cohort.
   - If no real monetary column exists (or only a Stage 3 LLM-synthesized penalty column exists), report **physical event/unit counts** (e.g., `20 adverse events prevented [95% CI: 15 to 27 events]`), NEVER `$`.
2. **NO SUMMING GOOD/PERFORMING RECORDS AS "LIABILITY / CAPITAL DRAG"**:
   - In `stage5_bi_synthesizer.py`, summing `Credit amount` across 100% of rows (including 700 `good` performing loans) and calling it "Capital Drag / Liability" is mathematically false.
   - Capital at Risk / Financial Liability MUST be summed **strictly where `_is_target_event == 1`** (adverse/defaulted records). Total Portfolio Volume can be shown separately as baseline context.
3. **NO KEYWORD WHACK-A-MOLE OR COPY-PASTED TARGET LOGIC**:
   - Do NOT maintain 3 separate copies of target binarization logic across `stage5_bi_synthesizer.py`, `MicroLevelForensicInquiryEngine._build_binary_target`, and `StrategicDecisionEngine._resolve_target`.
   - You MUST create a **single unified function** (`resolve_and_binarize_target(df, blueprint_target=None)`) in `autonomous_engine/target_resolver.py` (or inside `strategic_decision_matrix.py` and imported into `stage5_bi_synthesizer.py`) so Stage 5 Section 8 and the Decision Matrix **always use the exact same binary target `_is_target_event`, same target name, and same monetary column**.
   - NEVER put generic positive words like `'high'` or `'1'` inside an unconditional adverse string regex without checking that the column name itself denotes risk/defect/churn/default.
4. **NO SILENT STATISTICAL FALLBACKS (`p = 1.0000` OR `2.62 vs 2.62`)**:
   - Never gate Chi-Square on `cont_table.shape == (4, 2)`. When `pd.qcut(..., duplicates='drop')` produces 2 or 3 bins, `cont_table.shape[0] >= 2 and cont_table.shape[1] == 2` MUST still run `scipy.stats.chi2_contingency(cont_table)`.
   - Never allow Operational Triage Policy 1 (Conservative) and Policy 2 (Surgical) to use the exact same threshold (`q75 == q50 == 2022.0`). If `q75 == q50`, dynamically step to the next distinct empirical quantile or unique value (`unique_sorted[-1]` vs `unique_sorted[-2]`) so Policy 1 and Policy 2 are guaranteed distinct.
5. **NO NAIVE LOWEST-CARDINALITY PRIMARY DIMENSION (`Sex` BIAS)**:
   - Never select `primary_dim` by sorting categorical columns by lowest cardinality (`nunique == 2`), which blindly picks demographic columns like `Sex` (`male`/`female`).
   - Select `primary_dim` among clean categorical columns (`2 <= nunique <= 30`, excluding index/ID/target columns) that has the **highest statistical dispersion (Chi-Square / Cramér's V or max-min failure rate spread)** against `_is_target_event`.
6. **NO AUDIT THEATER IN `anti_hallucination_guard.py`**:
   - An audit script that prints `100.0% VERIFIED TRUTH` while missing `$20,000` vs `$327,125.80` contradictions and `2.62 vs 2.62` duplicate policies is worse than no audit. The guard MUST actively fail (`sys.exit(1)`) if any of these anomalies appear in the generated dossier.

---

### 🔧 STEP-BY-STEP REMEDIATION CHECKLIST FOR GEMINI 3.8

Execute these exact 8 fixes in order and verify every single one before running Benchmark 65:

- [ ] **Task 1: Strip CSV Index Artifacts (`Unnamed: 0`, `index`, `level_0`) Everywhere**
  - **Files**: `autonomous_engine/stage1_topology_profiler.py`, `autonomous_engine/stage5_bi_synthesizer.py`, `autonomous_engine/strategic_decision_matrix.py`
  - **Action**: Create a helper `is_index_artifact(col_name, series=None)` that detects `r'^(?:unnamed\s*:?\s*\d*|index|level_\d+|row_?(?:id|num|number))$'` (case-insensitive) or monotonic integer sequences starting at 0/1. Exclude these columns from primary key candidates (unless no other candidate exists, in which case rename to `_surrogate_id_key`), feature lists, root-cause drivers, and BI dimensions.

- [ ] **Task 2: Unify Target & Monetary Exposure Resolution (Single Source of Truth)**
  - **Files**: `autonomous_engine/strategic_decision_matrix.py` and `autonomous_engine/stage5_bi_synthesizer.py`
  - **Action**:
    1. Build ONE canonical function `resolve_canonical_target_and_cost(df)` that returns `(target_col, binary_series, target_desc, real_cost_col)`.
    2. For `real_cost_col`: Only accept a column as a **real monetary column** if it exists in the raw schema (NOT an LLM-fabricated Stage 3 column like `market_friction_penalty` with extreme synthetic outliers) AND matches financial semantics (`amount`, `credit`, `price`, `cost`, `revenue`, `balance`, `loss`, `claim`, `charge`, `income`, `salary`) while not being the target or an ID/rate/score.
    3. Fix `adverse_pattern` so `'high'` or `'1'` only triggers when the column name itself is an adverse indicator (`risk`, `default`, `churn`, `fraud`, `defect`, `fail`, `bad`, `loss`, `delay`, `cancel`, `disease`, `stroke`).

- [ ] **Task 3: Kill the `* 1000` Multiplier & Align Section 8 with Pathway A/B/C**
  - **Files**: `autonomous_engine/strategic_decision_matrix.py` (lines 970–1015) and `autonomous_engine/stage5_bi_synthesizer.py` (lines 295–355, 500–525)
  - **Action**:
    1. Delete `* 1000` completely from `strategic_decision_matrix.py`.
    2. In `stage5_bi_synthesizer.py`, compute `total_adverse_liability` as the sum of `real_cost_col` **only where `_is_target_event == 1`** (e.g., for German Credit, the 300 `bad` loans = `$1,181,438.00`, NOT `$3,271,258.00`).
    3. In `strategic_decision_matrix.py`, if `real_cost_col` is present, compute `high_risk_liability` = sum of `real_cost_col` where `(cohort_mask) & (_is_target_event == 1)`. Then Pathway A (15% reduction), Pathway B (35% reduction), and Pathway C (65% reduction) must scale `high_risk_liability` (and show both the exact dollar amount averted AND the exact adverse event count reduced). If `real_cost_col` is `None`, display ONLY the adverse event count reduction with Wilson CI bounds.

- [ ] **Task 4: Fix Chi-Square Gate & Cliff Detection in `MicroLevelForensicInquiryEngine`**
  - **File**: `autonomous_engine/strategic_decision_matrix.py` (lines 190–255)
  - **Action**:
    1. Replace `if cont_table.shape == (4, 2)` with `if cont_table.shape[0] >= 2 and cont_table.shape[1] == 2:`.
    2. In `analyze_threshold_cliffs()`, classify a transition as a **Confirmed Non-Linear Cliff** if `(step_ratio >= 1.5 or abs_jump >= 0.15) and p_val < 0.05`, where `abs_jump = r_curr - r_prev`. Never call a 44-percentage-point jump (`21.6% -> 65.7%`) a "progressive gradient"!

- [ ] **Task 5: Guarantee Distinct Thresholds in Operational Triage Policies**
  - **File**: `autonomous_engine/strategic_decision_matrix.py` (lines 290–350)
  - **Action**:
    1. When computing `q75` (Conservative) and `q50` (Surgical) for `top_num_col`, check if `np.isclose(q75, q50)` or if the resulting boolean masks `mask_p1` and `mask_p2` select the exact same row count (`n_scrap_1 == n_scrap_2`).
    2. If they collide, select distinct cutoffs from `np.unique(s_num.dropna())` or higher/lower percentiles (`q85` vs `q60`, or `>= max_val` vs `>= second_max_val`) so `Policy 1` and `Policy 2` ALWAYS evaluate genuinely different operational boundaries.

- [ ] **Task 6: Information-Gain Based Primary Dimension Selection in Stage 5**
  - **File**: `autonomous_engine/stage5_bi_synthesizer.py` (lines 150–185)
  - **Action**:
    1. Filter candidate categorical columns to `2 <= nunique <= 30`, excluding index artifacts (`unnamed_0`) and the target column.
    2. Deprioritize protected demographic attributes (`sex`, `gender`, `race`, `marital_status`) if operational/transactional dimensions (`purpose`, `checking_account`, `saving_accounts`, `housing`, `category`, `segment`, `department`, `key`) exist.
    3. Rank candidates by **between-group target failure rate variance (or Chi-Square statistic against `_is_target_event`)** so the dimension with the strongest real business signal is chosen.

- [ ] **Task 7: Upgrade `anti_hallucination_guard.py` & `loop_fix_engine.py` with Real Teeth**
  - **Files**: `autonomous_engine/anti_hallucination_guard.py`, `autonomous_engine/loop_fix_engine.py`
  - **Action**:
    1. In `anti_hallucination_guard.py`, add **Check 7 (Statistical & Financial Self-Consistency Gate)**:
       - Fail if `Chi-Square p: 1.0000` appears on a table with different bin rates.
       - Fail if Policy 1 and Policy 2 have identical scrap counts (`recall/scrap ratio` X vs X).
       - Fail if `unnamed_0` or `Unnamed: 0` appears as a forensic driver or primary key in the dossier.
       - Fail if any `$` figure in Pathway A/B/C equals `events * 1000`.
    2. In `loop_fix_engine.py`, dynamically include the current benchmark's `--output` directory (and recent `kaggle_benchmarks/*/output/bi_ready_fact.parquet` tables) instead of only checking 2 hardcoded legacy paths.

- [ ] **Task 8: Re-Run & Re-Certify Benchmarks 63 (`spotify_2023`) and 64 (`german_credit`)**
  - **Action**:
    1. Run `stage5_bi_synthesizer.py` and `anti_hallucination_guard.py` on both `kaggle_benchmarks/spotify_2023/output` and `kaggle_benchmarks/german_credit/output`.
    2. Inspect both `DATA_XRAY_EXECUTIVE_DOSSIER.md` files line by line to confirm:
       - `spotify_2023`: `Chi-Square p` on `released_year` is $< 0.0001$ (not `1.0000`), Policy 1 and Policy 2 have distinct thresholds and distinct scrap ratios (not `2.62 vs 2.62`), and no single-row synthetic penalty outlier (`$52,713.63`) distorts the C-suite narrative.
       - `german_credit`: `unnamed_0` is gone from drivers, `Sex = male` is replaced by a real credit dimension (`checking_account` or `purpose`), Total Defaulted Capital at Risk is `$1,181,438.00` (the 300 bad loans, not `$3,271,258.00`), and Pathway A/B/C report real cohort credit exposure instead of `$20,000 / $47,000 / $88,000`.
    3. Update `ENTERPRISE_100_DATASET_CAMPAIGN_AND_ANTI_HALLUCINATION_REPORT.md` with the corrected numbers before proceeding to Benchmark 65.

