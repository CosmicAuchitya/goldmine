# DataX-Ray: Autonomous Enterprise AI Data Automation & Forensic Engine

> **Certified Enterprise Benchmark Milestone: 61 of 100 Datasets Completed (11,587,913 Physical Fact Rows Audited with 0 Cartesian Drift, 0 Duplicate Keys, and 0 Hallucinations).**

Welcome to **DataX-Ray**, a production-grade, self-healing autonomous data engineering and forensic analytics system. The engine ingests arbitrary raw enterprise datasets (CSV, Excel, Parquet), dynamically profiles relational topology, writes vectorized ETL pipelines, heals runtime errors automatically, compiles Star-Schema dimensional models, and synthesizes executive decision matrices with micro-level statistical proof.

---

## ⚡ Quick Start for AI Agents & Developers

- **AI Agent Onboarding Guide**: Read [`AGENTS.md`](file:///c:/Users/91945/OneDrive/Desktop/XXX/Ai%20aotumation%20learning/AGENTS.md) for full context, system state, operational rules, and execution commands.
- **100-Dataset Master Campaign Artifact**: View [`ENTERPRISE_100_DATASET_CAMPAIGN_AND_ANTI_HALLUCINATION_REPORT.md`](file:///C:/Users/91945/.gemini/antigravity/brain/1d6bc462-5073-421e-8214-0b3b58a1f206/ENTERPRISE_100_DATASET_CAMPAIGN_AND_ANTI_HALLUCINATION_REPORT.md).

---

## 🏛️ Pipeline Architecture

The engine executes in 5 autonomous stages orchestrated by `autonomous_engine/master_orchestrator.py`:

```mermaid
flowchart TD
    A["Raw Data (CSV / Excel / Parquet)"] --> B["Stage 1: Topology Profiler & Cardinality Scanner"]
    B -->|Local PII Scrubbing + Hazard Scan| C["Stage 2: Gemini Relational Blueprint Architect"]
    C -->|Star-Schema Design (28 RPM Multi-Key Pool)| D["Stage 3: Vectorized Python ETL Code Synthesizer"]
    D -->|Assertion Gates Injected| E["Stage 4: Sandbox Executor & AST Self-Healing Compiler"]
    E -->|Error Detected| F["Self-Healing Patch Loop (AST Rewriter)"]
    F -->|Re-compile & Test| E
    E -->|Verified Fact Parquet| G["Stage 5: Enterprise BI & Micro-Forensic Synthesizer"]
    G --> H["Power BI / Tableau Measure Guide (DAX)"]
    G --> I["Strategic Decision Matrix (Unbiased 3 Pathways)"]
    G --> J["Micro-Level Forensic Inquiry Engine (8 Q&As)"]
    G --> K["DuckDB Anti-Hallucination Truth Audit"]
    K -->|100.0% Match| L["Certified Enterprise Catalog"]
```

---

## 🔬 Core Capabilities

### 1. Zero Cartesian Drift & Invariant Preservation
- Detects `1:1`, `1:N`, and `N:M` relationships before joining.
- Pre-aggregates dimensional lookups so fact row count remains identical:
  $$\text{Row Preservation} = 100.0\%, \quad \text{Multiplicity Drift} = 0 \text{ rows}$$

### 2. Autonomous Runtime Self-Healing (Compiler Guard)
- When runtime pandas/numpy type errors occur, Stage 4 catches the traceback, creates a non-destructive `.bak` file, invokes an AST-safe patch synthesizer, and re-executes in under 2 seconds without human intervention.

### 3. Micro-Level Forensic Inquiry Engine (`MicroForensicEngine`)
- **Non-Linear Threshold Cliffs**: Discretizes numeric features into quartiles to locate structural inflection points where failure flips from minority to majority.
- **2x2 Orthogonal Interaction Matrices**: Tests cross-variable synergy and antagonism (e.g., whether high alcohol can buffer high volatile acidity in wine).
- **Tail Anomaly Compounding**: Audits the worst 5% catastrophic records to prove whether failure is driven by single outliers or compound multi-system violations.
- **Operational Triage Scrap vs Yield Simulation**: Evaluates Conservative, Surgical, and Compound cutoff filters, measuring defect recall, false discard volume, and net product purity.
- **Simpson's Paradox & Confounder Defense**: Detects collinear feature pairs ($|r| > 0.40$) and conducts stratified subgroup correlations to debunk false causal illusions.
- **Autonomous Q&A Generation**: Formulates 8 deep executive questions and discovers empirical, data-grounded answers.

### 4. Unbiased Strategic Decision Matrix (Raste, Dictates Nahi)
- Evaluates 3 viable options:
  - **Pathway A**: Conservative (Hygiene & Queue Alerts - Low CapEx)
  - **Pathway B**: Surgical (Dedicated High-Risk Protocol - Moderate CapEx)
  - **Pathway C**: Structural (Full System Revamp & Telemetry - High CapEx)
- For every pathway, provides honest **Fayda (Pros)**, **Nuksan (Cons)**, and **Collateral Friction** with 95% confidence bounds.

---

## 📊 Certified Benchmarks (61 of 100 Completed)

Across 61 diverse enterprise datasets in Healthcare, FinTech, Logistics, SaaS, Retail, Manufacturing, and Agriculture:

| Metric | Measured Result | Audit Status |
| :--- | :--- | :--- |
| **Total Physical Fact Rows** | **11,587,913 rows** | 🟢 100% Preserved |
| **Cartesian Multiplicity Drift** | **0 rows (0.00%)** | 🟢 Zero Drift |
| **Primary Key Collisions** | **0 duplicate keys** | 🟢 100% Unique |
| **Hallucinated Metric Claims** | **0 columns / claims** | 🟢 100.0% Truth Grounded |
| **Autonomous Runtime** | **2,913.43 seconds** (~48.5 min) | 🟢 Certified Production Ready |

*See full benchmark breakdown in [`ENTERPRISE_100_DATASET_CAMPAIGN_AND_ANTI_HALLUCINATION_REPORT.md`](file:///C:/Users/91945/.gemini/antigravity/brain/1d6bc462-5073-421e-8214-0b3b58a1f206/ENTERPRISE_100_DATASET_CAMPAIGN_AND_ANTI_HALLUCINATION_REPORT.md).*

---

## 🚀 How to Execute a Benchmark

```powershell
# 1. Download Kaggle Dataset (e.g. Benchmark 62)
python autonomous_engine/kaggle_harvester.py --slug "<owner>/<dataset-name>" --dest "kaggle_benchmarks/<dataset_name>/raw_data"

# 2. Run Autonomous Pipeline
python autonomous_engine/master_orchestrator.py --data "kaggle_benchmarks/<dataset_name>/raw_data" --output "kaggle_benchmarks/<dataset_name>/output"

# 3. Verify Physical Parquet Facts with DuckDB
python -c "import duckdb; p = r'kaggle_benchmarks/<dataset_name>/output/bi_ready_fact.parquet'; print(duckdb.query(f'SELECT count(*) as total_rows, count(distinct Id) as unique_keys FROM read_parquet(\'{p}\')').df())"
```

---

## 🛠️ Repository Structure

```
├── AGENTS.md                                             <-- Comprehensive Agent Onboarding Briefing
├── README.md                                             <-- Master Project Documentation
├── autonomous_engine/                                    <-- Autonomous Engine Pipeline Modules
│   ├── master_orchestrator.py                            <-- Main Entry Point
│   ├── stage1_topology_profiler.py                       <-- Stage 1 Profiler & Key Detector
│   ├── stage2_ai_blueprint.py                            <-- Stage 2 Blueprint Architect
│   ├── stage3_ai_code_generator.py                       <-- Stage 3 Dynamic Python ETL Generator
│   ├── stage4_sandbox_executor.py                        <-- Stage 4 Sandbox Executor & Self-Healer
│   ├── stage5_bi_synthesizer.py                          <-- Stage 5 BI Deliverables & DAX Guides
│   ├── strategic_decision_matrix.py                      <-- Micro-Forensic & Decision Matrix V3.5
│   ├── anti_hallucination_guard.py                       <-- DuckDB Physical Truth Verifier
│   ├── loop_fix_engine.py                                <-- Continuous Invariant Regression Verifier
│   └── kaggle_harvester.py                               <-- Automated Dataset Harvester
├── 02_domain_intelligence/                               <-- Master Business Knowledge Base
│   └── business_ontology.py                              <-- Ontologies for 12 Global Business Models
└── kaggle_benchmarks/                                    <-- Benchmarks 1 through 61
```
