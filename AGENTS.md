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
- **Completed Benchmarks**: **62 of 100 Enterprise Benchmarks Certified** (**62.0% Complete**).
- **Total Physical Fact Rows Audited**: **11,588,913 Physical Records** across 62 projects.
- **Cartesian Multiplicity Drift**: **0 Rows (0.00%)**.
- **Primary Key Collisions**: **0 Duplicates**.
- **Hallucinated Columns Found**: **0 Columns (100.0% Physical Ground Truth Verified)**.
- **Total Execution Time**: **3,039.95 seconds** (~50.7 minutes cumulative).
- **Last Completed Project**: **Benchmark 62 (`kaggle_benchmarks/imdb_top_1000/raw_data/imdb_top_1000.csv`)** — IMDB Top 1000 Movies Forensics (**Argon 22-Gap Hardening Formally Cleared & Certified**).
- **Hardening Milestones**: Wilson 95% CIs, two-proportion pooled z-tests, immutable Stage 4 fact Parquet table, dynamic discrete cliff tests, non-circular root cause filtering, URL/free-text exclusion from keys and targets, adaptive rating scale quantiles, and anti-hallucination verification 100% hardened and verified.
- **Next Target**: **Benchmark 63** (Staged and ready for selection and harvesting).

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
[Post-Execution Continuous Invariant Audits]
  ├── `anti_hallucination_guard.py` (DuckDB physical SQL verification vs LLM claims)
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
│   ├── master_orchestrator.py                            <-- Main Entry Point for Benchmarks
│   ├── stage1_topology_profiler.py                       <-- Stage 1 Profiler & Cardinality Scanner
│   ├── stage2_ai_blueprint.py                            <-- Stage 2 Blueprint Architect (Gemini API)
│   ├── stage3_ai_code_generator.py                       <-- Stage 3 Dynamic Python ETL Generator
│   ├── stage4_sandbox_executor.py                        <-- Stage 4 Sandbox Executor & AST Self-Healer
│   ├── stage5_bi_synthesizer.py                          <-- Stage 5 BI & Measure Guide Synthesizer
│   ├── strategic_decision_matrix.py                      <-- Micro-Forensic & Decision Matrix Engine V3.5
│   ├── anti_hallucination_guard.py                       <-- DuckDB Physical Ground-Truth Verifier
│   ├── loop_fix_engine.py                                <-- Continuous Multi-Dataset Regression Verifier
│   ├── kaggle_harvester.py                               <-- Automated Dataset Ingestion Tool
│   ├── rate_limiter.py                                   <-- Multi-Key Gemini API Pool (28 RPM)
│   └── templated_dag_runner.py                           <-- Deterministic Out-of-Core DAG Fallback
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
