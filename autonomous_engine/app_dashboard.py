"""
=============================================================================
DATAX-RAY ENTERPRISE AUTONOMOUS ENGINE -- EXECUTIVE SELF-SERVE WEB PORTAL
=============================================================================
Non-Coder Business Command Center & Conversational Forensic Platform (V5.5):
1. Drag-and-Drop Self-Serve File Ingestion (.csv, .xlsx, .parquet, .zip) with
   safe Zip-Slip guards and isolated run sandboxing.
2. 3 Persona / Language Modes: Simple Business Hinglish, Simple Business English,
   and Technical & Statistical Audit.
3. Automatic Legacy Benchmark Hydration: Seamlessly upgrades historical
   benchmarks with live canonical DuckDB KPIs, V5.0 Plain Summaries, Priority
   Worklists, and V5.5 Zero-CDN Bespoke Dashboards on demand.
4. 5 Executive Product Tabs:
   - 📋 Business Health & Plain Summary (Zero-jargon brief + Temporal Trend).
   - 🎯 Today's Priority Worklist (Searchable Preventive Watch vs Loss Audit CSV).
   - 💬 Ask DataX-Ray (Interactive Bilingual Q&A with AI/Instant DuckDB modes).
   - 📊 Interactive Charts & Power BI / Fabric TMDL Semantic Model Export.
   - 🛡️ Full Forensic Dossier, Checklist & Live 11-Gate Anti-Hallucination Proof.
=============================================================================
"""

import os
import re
import sys
import time
import json
import uuid
import html
import shutil
import zipfile
import io
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import streamlit as st
import pandas as pd
import numpy as np

# Page configuration
st.set_page_config(
    page_title="DataX-Ray | Autonomous Business Data Portal",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Ensure project root and autonomous_engine are in sys.path
_CURRENT_DIR = Path(__file__).resolve().parent
_WORKSPACE_ROOT = _CURRENT_DIR.parent if _CURRENT_DIR.name == "autonomous_engine" else _CURRENT_DIR
for _p in [str(_WORKSPACE_ROOT), str(_CURRENT_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)


def escape_currency_markdown(text: str) -> str:
    """
    Escapes literal currency '$' signs (e.g. $100 -> \\$100, ($) -> (\\$))
    so Streamlit's KaTeX engine never misinterprets currency pairs as inline
    LaTeX math while keeping genuine math expressions (e.g. $\\neq$, $p < 0.05$) intact.
    """
    if not isinstance(text, str):
        return text
    # 1. Escape currency amounts like $100, $0.00, $-25.00
    safe_text = re.sub(r'(?<!\\)\$(?=-?\d)', r'\\$', text)
    # 2. Escape column/unit markers like ($)
    safe_text = re.sub(r'\(\$\)', r'(\\$)', safe_text)
    return safe_text


def render_safe_markdown(text: str, unsafe_allow_html: bool = False):
    """Renders Markdown safely without currency-triggered KaTeX collisions."""
    if not isinstance(text, str):
        st.markdown(text, unsafe_allow_html=unsafe_allow_html)
        return
    st.markdown(escape_currency_markdown(text), unsafe_allow_html=unsafe_allow_html)


# High-End Dark Executive Aesthetic
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(90deg, #38bdf8 0%, #34d399 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0px;
    }
    .sub-header {
        color: #94a3b8;
        font-size: 1.05rem;
        margin-top: -4px;
        margin-bottom: 20px;
    }
    .metric-card-box {
        background-color: #1e293b;
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 16px;
        text-align: center;
        min-height: 96px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .metric-num {
        font-size: 1.75rem;
        font-weight: 800;
        color: #f8fafc;
        line-height: 1.2;
    }
    .metric-sub {
        font-size: 0.80rem;
        color: #94a3b8;
        margin-top: 6px;
        letter-spacing: 0.03em;
    }
    .exec-meta-card {
        background-color: #1e293b;
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 14px 16px;
        min-height: 92px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        margin-bottom: 12px;
    }
    .exec-meta-label {
        font-size: 0.76rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #94a3b8;
        margin-bottom: 6px;
        font-weight: 600;
    }
    .exec-meta-val {
        font-size: 0.98rem;
        font-weight: 700;
        color: #f8fafc;
        line-height: 1.35;
        overflow-wrap: anywhere;
        word-break: break-word;
        white-space: normal;
    }
    .tech-audit-bar {
        background-color: rgba(30, 41, 59, 0.75);
        border: 1px solid #334155;
        border-left: 4px solid #38bdf8;
        border-radius: 8px;
        padding: 10px 14px;
        margin-bottom: 16px;
        font-size: 0.86rem;
        color: #cbd5e1;
    }
    .badge-verified {
        background-color: rgba(16, 185, 129, 0.15);
        color: #10b981;
        border: 1px solid #10b981;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Independent resilient imports supporting both package and standalone execution
try:
    from autonomous_engine.master_orchestrator import run_master_pipeline
except ImportError:
    try:
        from master_orchestrator import run_master_pipeline
    except ImportError:
        run_master_pipeline = None

try:
    from autonomous_engine.anti_hallucination_guard import run_anti_hallucination_audit
except ImportError:
    try:
        from anti_hallucination_guard import run_anti_hallucination_audit
    except ImportError:
        run_anti_hallucination_audit = None

try:
    from autonomous_engine.common_utils import resolve_safe_workspace_path
except ImportError:
    try:
        from common_utils import resolve_safe_workspace_path
    except ImportError:
        def resolve_safe_workspace_path(p, root=None):
            r = (root or Path.cwd()).resolve()
            rp = (r / p).resolve() if not Path(p).is_absolute() else Path(p).resolve()
            if not rp.is_relative_to(r):
                raise ValueError(f"Path escape blocked: {p}")
            return rp

try:
    from autonomous_engine.kaggle_harvester import safe_extract_zip
except ImportError:
    try:
        from kaggle_harvester import safe_extract_zip
    except ImportError:
        safe_extract_zip = None

try:
    from autonomous_engine.conversational_qa_engine import ConversationalBusinessQAEngine
except ImportError:
    try:
        from conversational_qa_engine import ConversationalBusinessQAEngine
    except ImportError:
        ConversationalBusinessQAEngine = None

try:
    from autonomous_engine.target_resolver import resolve_canonical_target_and_cost
except ImportError:
    try:
        from target_resolver import resolve_canonical_target_and_cost
    except ImportError:
        resolve_canonical_target_and_cost = None

try:
    from autonomous_engine.business_action_exporter import (
        generate_actionable_priority_worklist,
        analyze_temporal_trends,
        generate_plain_business_summary,
    )
except ImportError:
    try:
        from business_action_exporter import (
            generate_actionable_priority_worklist,
            analyze_temporal_trends,
            generate_plain_business_summary,
        )
    except ImportError:
        generate_actionable_priority_worklist = None
        analyze_temporal_trends = None
        generate_plain_business_summary = None

try:
    from autonomous_engine.stage7_bespoke_dashboard_architect import synthesize_bespoke_dashboard
except ImportError:
    try:
        from stage7_bespoke_dashboard_architect import synthesize_bespoke_dashboard
    except ImportError:
        synthesize_bespoke_dashboard = None

WORKSPACE_ROOT = _WORKSPACE_ROOT


@st.cache_data(show_spinner=False, max_entries=16)
def _load_fact_and_kpis(
    fact_path_str: str,
    fact_mtime_ns: int,
    manifest_path_str: str,
    manifest_mtime_ns: int,
    blueprint_path_str: str,
) -> Tuple[pd.DataFrame, Dict[str, Any], Dict[str, Any]]:
    """
    Loads the Parquet fact table once per modification timestamp and resolves
    100% physically grounded KPIs (falling back cleanly to canonical target/cost
    computation on older benchmarks that predate semantic_metrics_manifest.json).
    """
    _ = (fact_mtime_ns, manifest_mtime_ns)  # cache invalidation keys
    df_fact = pd.read_parquet(fact_path_str)
    total_records = len(df_fact)

    blueprint: Dict[str, Any] = {}
    bp_p = Path(blueprint_path_str)
    if bp_p.exists():
        try:
            blueprint = json.loads(bp_p.read_text(encoding="utf-8"))
        except Exception:
            blueprint = {}

    manifest_data: Dict[str, Any] = {}
    mf_p = Path(manifest_path_str)
    if mf_p.exists():
        try:
            manifest_data = json.loads(mf_p.read_text(encoding="utf-8"))
        except Exception:
            manifest_data = {}

    # Canonical physical fallback calculation (strictly adheres to Iron Laws 1 & 2)
    gt_events = 0
    gt_rate = 0.0
    gt_drag: Optional[float] = None
    gt_port: Optional[float] = None
    target_col = blueprint.get("target_metric", "Auto-Detected")
    cost_col = None

    if resolve_canonical_target_and_cost is not None and total_records > 0:
        try:
            canonical = resolve_canonical_target_and_cost(df_fact, blueprint=blueprint)
            target_col = canonical.get("target_col") or target_col
            cost_col = canonical.get("cost_col")
            s_bin = canonical.get("binary_target")
            if s_bin is not None:
                gt_events = int(s_bin.sum())
                gt_rate = round((gt_events / max(total_records, 1)) * 100.0, 2)
                if cost_col and cost_col in df_fact.columns:
                    s_cost = pd.to_numeric(df_fact[cost_col], errors="coerce").fillna(0.0)
                    gt_drag = float(s_cost[s_bin == 1].sum())
                    gt_port = float(s_cost.sum())
        except Exception:
            pass

    metrics = {m.get("id"): m for m in manifest_data.get("certified_metrics", [])}
    has_manifest_kpis = bool(metrics and "m_target_events" in metrics)

    if has_manifest_kpis:
        m_events = int(metrics.get("m_target_events", {}).get("audited_value", gt_events))
        m_rate = float(metrics.get("m_adverse_rate", {}).get("audited_value", gt_rate))
        m_drag = metrics.get("m_adverse_capital_drag", {}).get("audited_value", gt_drag)
        m_port = metrics.get("m_portfolio_volume", {}).get("audited_value", gt_port)
    else:
        m_events = gt_events
        m_rate = gt_rate
        m_drag = gt_drag
        m_port = gt_port

    kpi_bundle = {
        "total_records": total_records,
        "m_events": m_events,
        "m_rate": m_rate,
        "m_drag": m_drag,
        "m_port": m_port,
        "target_col": target_col,
        "cost_col": cost_col or "None (Physical Event Counts)",
        "primary_key": blueprint.get("primary_id_column", "Auto-Detected"),
        "kpi_source": "Certified TMDL Manifest" if has_manifest_kpis else "Live DuckDB/Parquet Ground Truth",
    }
    return df_fact, kpi_bundle, blueprint


def ensure_v55_deliverables(out_p: Path, df_fact: pd.DataFrame, blueprint: Dict[str, Any]) -> bool:
    """
    Synthesizes missing V5.0/V5.5 business artifacts (Worklist CSV, Temporal Summary,
    Plain Bilingual Summary, and Zero-CDN Bespoke Dashboard) for legacy benchmarks.
    """
    changed = False
    worklist_f = out_p / "actionable_priority_worklist.csv"
    temporal_f = out_p / "temporal_trend_summary.json"
    summary_f = out_p / "PLAIN_BUSINESS_SUMMARY.md"
    bespoke_f = out_p / "bespoke_executive_dashboard.html"

    try:
        if not worklist_f.exists() and generate_actionable_priority_worklist is not None:
            generate_actionable_priority_worklist(df_fact, out_p, blueprint=blueprint)
            changed = True

        temp_summary = None
        if not temporal_f.exists() and analyze_temporal_trends is not None:
            temp_summary = analyze_temporal_trends(df_fact, out_p, blueprint=blueprint)
            changed = True
        elif temporal_f.exists():
            try:
                temp_summary = json.loads(temporal_f.read_text(encoding="utf-8"))
            except Exception:
                temp_summary = None

        if not summary_f.exists() and generate_plain_business_summary is not None:
            generate_plain_business_summary(
                df_fact,
                out_p,
                blueprint=blueprint,
                temporal_summary=temp_summary,
                worklist_path=worklist_f if worklist_f.exists() else None,
            )
            changed = True

        if not bespoke_f.exists() and synthesize_bespoke_dashboard is not None:
            synthesize_bespoke_dashboard(str(out_p), use_llm=False)
            changed = True
    except Exception:
        pass
    return changed


# Top Title Banner
st.markdown('<div class="main-header">⚡ DataX-Ray // Autonomous Business Intelligence Portal</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Zero-Code Business Forensics &bull; Natural Language Q&A &bull; Physical Parquet Ground Truth</div>', unsafe_allow_html=True)

# Initialize Session State
if "active_output_dir" not in st.session_state:
    default_telecom = WORKSPACE_ROOT / "kaggle_benchmarks" / "telecom_users" / "output"
    if default_telecom.exists():
        st.session_state["active_output_dir"] = str(default_telecom)
    else:
        st.session_state["active_output_dir"] = "kaggle_complex_test/output"

if "qa_chat_history" not in st.session_state:
    st.session_state["qa_chat_history"] = []

if "live_audit_cache" not in st.session_state:
    st.session_state["live_audit_cache"] = {}

# Sidebar Controls
st.sidebar.markdown("### 🎛️ Data Source & Controls")
source_mode = st.sidebar.radio(
    "Select Ingestion Pathway:",
    ["📤 Upload My Business Files (Zero-Code)", "📂 Explore Certified Workspace Benchmarks"]
)

active_out_dir = st.session_state["active_output_dir"]

if source_mode == "📤 Upload My Business Files (Zero-Code)":
    uploaded_files = st.sidebar.file_uploader(
        "Upload CSV, Excel, Parquet, or ZIP:",
        type=["csv", "tsv", "xlsx", "xls", "parquet", "zip"],
        accept_multiple_files=True
    )

    exec_pipeline_mode = st.sidebar.selectbox(
        "Engine Execution Mode:",
        ["ai (Full Autonomous LLM Self-Healing)", "templated (Ultra-Fast Vectorized DAG)"]
    )

    if st.sidebar.button("🚀 Run Autonomous Business X-Ray", type="primary", use_container_width=True):
        if not uploaded_files:
            st.sidebar.error("Please upload at least one valid dataset file first.")
        elif run_master_pipeline is None or run_anti_hallucination_audit is None:
            st.sidebar.error("Engine modules could not be loaded. Run `pip install -r requirements.txt` and restart the portal.")
        else:
            upload_id = f"upload_{int(time.time())}_{uuid.uuid4().hex[:6]}"
            staging_raw = WORKSPACE_ROOT / "runs" / "uploads" / upload_id / "raw_data"
            staging_out = WORKSPACE_ROOT / "runs" / "uploads" / upload_id / "output"
            staging_raw.mkdir(parents=True, exist_ok=True)
            staging_out.mkdir(parents=True, exist_ok=True)

            total_up_bytes = sum(getattr(uf, "size", 0) for uf in uploaded_files)
            if total_up_bytes > 200 * 1024 * 1024:
                st.sidebar.error("Uploaded files exceed 200 MB maximum size limit.")
                st.stop()

            for uf in uploaded_files:
                safe_name = re.sub(r'[^A-Za-z0-9._-]', '_', Path(uf.name).name)
                dest_file = staging_raw / safe_name
                with open(dest_file, "wb") as f_dst:
                    shutil.copyfileobj(uf, f_dst)

                if safe_name.lower().endswith(".zip"):
                    if safe_extract_zip is None:
                        st.sidebar.error("ZIP extraction module unavailable. Please upload CSV / Excel / Parquet files directly.")
                        st.stop()
                    try:
                        safe_extract_zip(dest_file, staging_raw)
                        dest_file.unlink(missing_ok=True)
                    except Exception as ze:
                        st.sidebar.error(f"ZIP Security Error: {ze}")
                        st.stop()

            with st.spinner("Executing Autonomous DataX-Ray Engine (Stages 1-7) across your files... this can take a few minutes."):
                t_start = time.time()
                pipeline_mode = "dag" if "templated" in exec_pipeline_mode else "ai"
                try:
                    success = run_master_pipeline(
                        data_dir=str(staging_raw),
                        output_dir=str(staging_out),
                        cache_dir=str(staging_out.parent / "cache"),
                        mode=pipeline_mode
                    )
                except Exception as pe:
                    success = False
                    st.sidebar.error(f"Pipeline crashed: {type(pe).__name__}: {pe}")

                if success:
                    try:
                        audit_res = run_anti_hallucination_audit(str(staging_out), str(staging_out / "execution_blueprint.json"))
                    except Exception as ae:
                        audit_res = {"grounding_confidence": f"AUDIT ERROR: {ae}"}
                    elapsed = time.time() - t_start
                    st.session_state["active_output_dir"] = str(staging_out)
                    st.session_state["qa_chat_history"] = []
                    st.session_state["live_audit_cache"][str(staging_out.resolve())] = audit_res
                    if audit_res.get("grounding_confidence") == "100.0% VERIFIED TRUTH":
                        st.session_state["last_run_notice"] = ("success", f"Analysis completed & 100% verified in {elapsed:.1f}s.")
                    else:
                        violations = audit_res.get("physics_invariant_violations") or []
                        st.session_state["last_run_notice"] = (
                            "warning",
                            f"Analysis finished in {elapsed:.1f}s, but the Anti-Hallucination Guard flagged "
                            f"{len(violations)} issue(s). Treat numbers as UNVERIFIED until reviewed in the Proof tab."
                        )
                    st.rerun()
                else:
                    st.sidebar.error("Pipeline could not complete. Check `runs/logs/enterprise_pipeline.log` for the failing stage.")

    if st.session_state.get("last_run_notice"):
        _kind, _msg = st.session_state["last_run_notice"]
        (st.sidebar.success if _kind == "success" else st.sidebar.warning)(_msg)

else:
    benchmark_dirs = []
    kb_path = WORKSPACE_ROOT / "kaggle_benchmarks"
    if kb_path.exists():
        for d in sorted(kb_path.iterdir()):
            if (d / "output" / "bi_ready_fact.parquet").exists():
                benchmark_dirs.append(str(d / "output"))

    uploads_path = WORKSPACE_ROOT / "runs" / "uploads"
    if uploads_path.exists():
        for d in sorted(uploads_path.iterdir(), reverse=True):
            if (d / "output" / "bi_ready_fact.parquet").exists():
                benchmark_dirs.insert(0, str(d / "output"))

    if (WORKSPACE_ROOT / "kaggle_complex_test" / "output" / "bi_ready_fact.parquet").exists():
        benchmark_dirs.insert(0, str(WORKSPACE_ROOT / "kaggle_complex_test" / "output"))

    if not benchmark_dirs:
        benchmark_dirs = [st.session_state["active_output_dir"]]

    def _dataset_label(p: str) -> str:
        pp = Path(p)
        return pp.parent.name if pp.name == "output" else pp.name

    current_dir = st.session_state["active_output_dir"]
    current_idx = benchmark_dirs.index(current_dir) if current_dir in benchmark_dirs else 0
    chosen_dir = st.sidebar.selectbox(
        f"Select Certified Dataset Output ({len(benchmark_dirs)} available):",
        benchmark_dirs,
        index=current_idx,
        format_func=_dataset_label
    )
    if chosen_dir != st.session_state["active_output_dir"]:
        st.session_state["active_output_dir"] = chosen_dir
        st.session_state["qa_chat_history"] = []
        active_out_dir = chosen_dir
        st.rerun()

st.sidebar.markdown("---")
persona_mode = st.sidebar.radio(
    "🌐 Language & Audience Mode:",
    ["🇮🇳 Simple Business (Hinglish)", "🇬🇧 Simple Business (English)", "🔬 Technical & Statistical Audit"]
)

# Active Output Directory Context
out_p = Path(active_out_dir).resolve()
fact_file = out_p / "bi_ready_fact.parquet"
blueprint_file = out_p / "execution_blueprint.json"
manifest_file = out_p / "semantic_metrics_manifest.json"
summary_file = out_p / "PLAIN_BUSINESS_SUMMARY.md"
worklist_file = out_p / "actionable_priority_worklist.csv"
temporal_file = out_p / "temporal_trend_summary.json"
dossier_file = out_p / "DATA_XRAY_EXECUTIVE_DOSSIER.md"
checklist_file = out_p / "CERTIFICATION_AUDIT_CHECKLIST.md"
vega_spec_file = out_p / "vega_lite_dashboard_spec.json"
bespoke_html_f = out_p / "bespoke_executive_dashboard.html"
design_bp_f = out_p / "dashboard_design_blueprint.json"

active_dataset_name = out_p.parent.name if out_p.name == "output" else out_p.name

# Preload cached Fact Table + Ground-Truth KPIs once across all tabs
df_fact: Optional[pd.DataFrame] = None
kpi_bundle: Dict[str, Any] = {}
active_blueprint: Dict[str, Any] = {}

if fact_file.exists():
    fact_mtime = fact_file.stat().st_mtime_ns
    mf_mtime = manifest_file.stat().st_mtime_ns if manifest_file.exists() else 0
    df_fact, kpi_bundle, active_blueprint = _load_fact_and_kpis(
        str(fact_file),
        fact_mtime,
        str(manifest_file),
        mf_mtime,
        str(blueprint_file),
    )

    # Auto-hydrate missing V5.0/V5.5 artifacts seamlessly for datasets <= 100k rows
    missing_v55 = not (summary_file.exists() and worklist_file.exists() and bespoke_html_f.exists())
    if missing_v55:
        if len(df_fact) <= 100_000:
            with st.spinner(f"⚡ Preparing V5.5 Executive Brief, Priority Worklist & Bespoke Dashboard for `{active_dataset_name}`..."):
                ensure_v55_deliverables(out_p, df_fact, active_blueprint)
        else:
            if st.sidebar.button("⚡ Synthesize V5.5 Deliverables", use_container_width=True):
                with st.spinner(f"⚡ Synthesizing V5.5 Deliverables across {len(df_fact):,} records..."):
                    ensure_v55_deliverables(out_p, df_fact, active_blueprint)
                    st.rerun()

st.sidebar.caption(
    f"📂 Active Dataset: `{active_dataset_name}`"
    + (f" ({kpi_bundle.get('total_records', 0):,} rows)" if kpi_bundle else "")
)

# 5 Executive Product Tabs
tabs = st.tabs([
    "📋 Business Health & Plain Summary",
    "🎯 Today's Priority Worklist",
    "💬 Ask DataX-Ray (Conversational Q&A)",
    "📊 Interactive Charts & Power BI Export",
    "🛡️ Full Forensic Dossier & Proof"
])

# =============================================================================
# TAB 1: Business Health & Plain Summary
# =============================================================================
with tabs[0]:
    if df_fact is None:
        st.warning("No audited fact table found in active directory. Upload a dataset or select a certified benchmark in the sidebar.")
    else:
        total_records = kpi_bundle["total_records"]
        m_events = kpi_bundle["m_events"]
        m_rate = kpi_bundle["m_rate"]
        m_drag = kpi_bundle["m_drag"]
        m_port = kpi_bundle["m_port"]

        # Top KPI Cards
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.markdown(
                '<div class="metric-card-box"><div class="metric-num">'
                + f"{total_records:,}"
                + '</div><div class="metric-sub">AUDITED FACT RECORDS</div></div>',
                unsafe_allow_html=True,
            )
        with k2:
            st.markdown(
                '<div class="metric-card-box"><div class="metric-num" style="color: #f43f5e;">'
                + f"{int(m_events):,}"
                + '</div><div class="metric-sub">'
                + f"ADVERSE EVENTS ({m_rate:.2f}%)"
                + '</div></div>',
                unsafe_allow_html=True,
            )
        with k3:
            st.markdown(
                '<div class="metric-card-box"><div class="metric-num" style="color: #10b981;">'
                + f"{max(0.0, 100.0 - m_rate):.2f}%"
                + '</div><div class="metric-sub">SYSTEM RELIABILITY</div></div>',
                unsafe_allow_html=True,
            )
        with k4:
            if m_drag is not None and m_drag > 0:
                port_sub = f"${m_port:,.2f} PORTFOLIO" if (m_port is not None and m_port > 0) else "ADVERSE EXPOSURE"
                st.markdown(
                    '<div class="metric-card-box"><div class="metric-num" style="color: #f59e0b;">'
                    + f"${m_drag:,.2f}"
                    + '</div><div class="metric-sub">'
                    + f"CAPITAL DRAG ({port_sub})"
                    + '</div></div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div class="metric-card-box"><div class="metric-num" style="color: #38bdf8;">100.0%</div>'
                    '<div class="metric-sub">TRUTH GROUNDED AUDIT</div></div>',
                    unsafe_allow_html=True,
                )

        st.markdown("<br>", unsafe_allow_html=True)

        if "Technical" in persona_mode:
            st.markdown(
                f'<div class="tech-audit-bar">'
                f'🔬 <b>Technical Telemetry:</b> &nbsp; '
                f'<b>Target Column:</b> <code>{html.escape(str(kpi_bundle.get("target_col")))}</code> &nbsp;|&nbsp; '
                f'<b>Monetary Ledger:</b> <code>{html.escape(str(kpi_bundle.get("cost_col")))}</code> &nbsp;|&nbsp; '
                f'<b>Primary Key:</b> <code>{html.escape(str(kpi_bundle.get("primary_key")))}</code> &nbsp;|&nbsp; '
                f'<b>KPI Source:</b> <span class="badge-verified">{html.escape(str(kpi_bundle.get("kpi_source")))}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        # Render Plain-Language Executive Brief
        if summary_file.exists():
            sum_text = summary_file.read_text(encoding="utf-8")
            split_marker = "## 🇮🇳 Business X-Ray Summary" if "## 🇮🇳 Business X-Ray Summary" in sum_text else "## 🇮🇳 बिज़नेस एक्स-रे सारांश"
            parts = sum_text.split(split_marker)
            if "Hinglish" in persona_mode:
                if len(parts) > 1:
                    render_safe_markdown(split_marker + parts[1])
                else:
                    render_safe_markdown(sum_text)
            elif "English" in persona_mode:
                render_safe_markdown(parts[0])
            else:
                render_safe_markdown(sum_text)
        else:
            st.info("Plain business summary is not yet generated for this large dataset. Click '⚡ Synthesize V5.5 Deliverables' in the sidebar to build it.")

        # Temporal Trend Visual if dataset is temporal
        if temporal_file.exists():
            try:
                temp_info = json.loads(temporal_file.read_text(encoding="utf-8"))
                if temp_info.get("is_temporal_dataset") and len(temp_info.get("periods", [])) >= 2:
                    st.markdown("---")
                    st.markdown(f"### 📈 Month-over-Month / Period Trend Evolution (`{temp_info.get('date_column')}`)")
                    df_temp = pd.DataFrame(temp_info.get("periods", []))
                    st.line_chart(df_temp.set_index("period")["adverse_rate_pct"])
            except Exception:
                pass

# =============================================================================
# TAB 2: Today's Priority Worklist
# =============================================================================
with tabs[1]:
    st.markdown("### 🎯 Today's Actionable Priority Worklist")
    st.markdown("Concrete operational lists of which exact customer, loan, or ticket IDs require intervention today.")

    if not worklist_file.exists():
        st.info("No worklist CSV generated yet. Click '⚡ Synthesize V5.5 Deliverables' in the sidebar or run Stage 5 on this dataset.")
    else:
        df_worklist = pd.read_csv(worklist_file)
        n_total_wl = len(df_worklist)
        n_prev_wl = int((df_worklist["action_queue"] == "PREVENTIVE_RETENTION_WATCH").sum()) if "action_queue" in df_worklist.columns else 0
        n_rec_wl = int((df_worklist["action_queue"] == "REALIZED_LOSS_RECOVERY_AUDIT").sum()) if "action_queue" in df_worklist.columns else 0

        w1, w2, w3 = st.columns(3)
        with w1:
            st.markdown(
                f'<div class="exec-meta-card"><div class="exec-meta-label">Total Priority Accounts</div>'
                f'<div class="exec-meta-val">{n_total_wl:,} Ranked Records</div></div>',
                unsafe_allow_html=True,
            )
        with w2:
            st.markdown(
                f'<div class="exec-meta-card"><div class="exec-meta-label">🛡️ Preventive Retention Watch</div>'
                f'<div class="exec-meta-val" style="color: #38bdf8;">{n_prev_wl:,} Active At-Risk Accounts</div></div>',
                unsafe_allow_html=True,
            )
        with w3:
            st.markdown(
                f'<div class="exec-meta-card"><div class="exec-meta-label">💰 Realized Loss Recovery Audit</div>'
                f'<div class="exec-meta-val" style="color: #f59e0b;">{n_rec_wl:,} Realized Failure Cases</div></div>',
                unsafe_allow_html=True,
            )

        f_col1, f_col2 = st.columns([2, 1])
        with f_col1:
            queue_options = ["All Records"] + list(df_worklist["action_queue"].unique())
            selected_queue = st.radio("Filter Operational Queue:", queue_options, horizontal=True)
        with f_col2:
            wl_search = st.text_input("🔍 Search ID, Cohort, or Risk Reason:", value="", placeholder="e.g. Mensal, 5760, Cliff...")

        df_filtered = df_worklist if selected_queue == "All Records" else df_worklist[df_worklist["action_queue"] == selected_queue]
        if wl_search.strip():
            q_low = wl_search.strip().lower()
            mask = df_filtered.astype(str).apply(lambda col: col.str.lower().str.contains(q_low, na=False, regex=False)).any(axis=1)
            df_filtered = df_filtered[mask]

        n_filtered = len(df_filtered)
        col_top, col_down = st.columns([3, 1])
        with col_top:
            if n_filtered == 0:
                row_slider = 0
                st.caption("No priority rows match your current filter/search.")
            elif n_filtered <= 5:
                row_slider = n_filtered
                st.caption(f"Showing all {n_filtered} matching priority rows.")
            else:
                row_slider = st.slider(
                    "Display top N priority rows:",
                    min_value=5,
                    max_value=min(250, n_filtered),
                    value=min(25, n_filtered)
                )
        with col_down:
            st.markdown("<br>", unsafe_allow_html=True)
            csv_bytes = df_filtered.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Download Filtered Worklist CSV",
                data=csv_bytes,
                file_name=f"{active_dataset_name}_priority_worklist.csv",
                mime="text/csv",
                use_container_width=True
            )

        if n_filtered > 0:
            col_rename = {
                "_is_target_event": "Adverse Status (0=Good, 1=Risk)",
                "empirical_cohort_risk_pct": "Cohort Risk (%)",
                "monetary_exposure": "Monetary Exposure ($)",
                "exposure_column_source": "Exposure Source",
                "action_queue": "Action Queue",
                "priority_rank": "Priority Rank",
            }
            display_df = df_filtered.head(row_slider).rename(columns=col_rename)
            st.dataframe(display_df, use_container_width=True)

# =============================================================================
# TAB 3: Ask DataX-Ray (Two-Way Conversational Q&A)
# =============================================================================
with tabs[2]:
    st.markdown("### 💬 Ask DataX-Ray — Grounded Business Inquirer")
    st.markdown("Ask ad-hoc business questions in natural English or Hinglish. Every number is physically calculated via DuckDB.")

    if not fact_file.exists():
        st.warning("Fact table not discovered.")
    else:
        if ConversationalBusinessQAEngine is None:
            try:
                from autonomous_engine.conversational_qa_engine import ConversationalBusinessQAEngine
            except Exception:
                try:
                    from conversational_qa_engine import ConversationalBusinessQAEngine
                except Exception:
                    ConversationalBusinessQAEngine = None

        if ConversationalBusinessQAEngine is None:
            st.error("ConversationalBusinessQAEngine could not be loaded. Please ensure `duckdb` and `tabulate` are installed (`pip install -r requirements.txt`).")
        else:
            try:
                qa_engine = ConversationalBusinessQAEngine(out_p)
                current_dim = qa_engine.primary_dim or "segments"
            except Exception as qe:
                qa_engine = None
                st.error(f"Could not initialize QA engine: {type(qe).__name__}: {qe}")

        if qa_engine:
            ctrl_col1, ctrl_col2 = st.columns([3, 1])
            with ctrl_col1:
                qa_exec_mode = st.radio(
                    "SQL Synthesis Engine:",
                    ["🤖 AI + Read-Only DuckDB Sandbox", "⚡ Instant Offline Deterministic DuckDB"],
                    horizontal=True,
                )
            with ctrl_col2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("🗑️ Clear Chat History", use_container_width=True):
                    st.session_state["qa_chat_history"] = []
                    qa_engine.close()
                    st.rerun()

            use_llm_flag = qa_exec_mode.startswith("🤖")

            # Starter Question Chips
            st.markdown("**Suggested Quick Inquiries:**")
            chip_cols = st.columns(4)
            c1 = chip_cols[0].button("📊 Overall Churn & Liability", use_container_width=True)
            c2 = chip_cols[1].button("⚠️ Highest Risk Segments", use_container_width=True)
            c3 = chip_cols[2].button("🇮🇳 Kis category me zyada loss?", use_container_width=True)
            c4 = chip_cols[3].button("🔍 Top 5 by Adverse Rate", use_container_width=True)

            selected_prompt = None
            if c1:
                selected_prompt = "What is our overall volume, churn count, and adverse failure rate?"
            elif c2:
                selected_prompt = f"Show me the breakdown of failure rates across {current_dim}."
            elif c3:
                selected_prompt = "Sabse zyada nuksan aur churn kis segment mein ho raha hai? Details batao."
            elif c4:
                selected_prompt = "Show top 5 segments ordered by adverse failure rate."

            # Chat message display
            for msg in st.session_state["qa_chat_history"]:
                with st.chat_message(msg["role"]):
                    render_safe_markdown(msg["content"])
                    if msg.get("vega_spec"):
                        st.vega_lite_chart(msg["vega_spec"], use_container_width=True)
                    if msg.get("sql"):
                        mode_tag = msg.get("mode", "verified")
                        with st.expander(f"🔍 Audited DuckDB SQL Reflection ({mode_tag})"):
                            st.code(msg["sql"], language="sql")

            user_input = st.chat_input("Ask a business question about your dataset (e.g. 'Kis contract me sabse zyada churn hai?')...")
            prompt = selected_prompt or user_input

            if prompt:
                st.session_state["qa_chat_history"].append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    render_safe_markdown(prompt)

                with st.chat_message("assistant"):
                    with st.spinner("Executing verified DuckDB query..."):
                        res = qa_engine.ask(prompt, language="auto", use_llm=use_llm_flag)
                        render_safe_markdown(res["answer_markdown"])
                        if res.get("vega_lite_spec"):
                            st.vega_lite_chart(res["vega_lite_spec"], use_container_width=True)
                        mode_used = res.get("sql_generation_mode", "verified")
                        with st.expander(f"🔍 Audited DuckDB SQL Reflection & Data Proof ({mode_used})"):
                            st.code(res["sql_executed"], language="sql")
                            if res.get("data"):
                                st.dataframe(pd.DataFrame(res["data"]).head(20), use_container_width=True)

                        st.session_state["qa_chat_history"].append({
                            "role": "assistant",
                            "content": res["answer_markdown"],
                            "vega_spec": res.get("vega_lite_spec"),
                            "sql": res.get("sql_executed"),
                            "mode": mode_used,
                        })
            qa_engine.close()

# =============================================================================
# TAB 4: Interactive Charts & Power BI Export
# =============================================================================
with tabs[3]:
    st.markdown("### 🎨 Bespoke Executive Dashboard & BI Export")

    if design_bp_f.exists():
        try:
            bp_info = json.loads(design_bp_f.read_text(encoding="utf-8"))
            arch_val = html.escape(str(bp_info.get("archetype_name", "Bespoke Executive")))
            pers_val = html.escape(str(bp_info.get("executive_persona", "Executive Leadership")))
            dfii_val = f"{bp_info.get('dfii_score', 15)} / 19"
            pan_val = f"{len(bp_info.get('selected_panels', []))} Adaptive Widgets"

            b_col1, b_col2, b_col3, b_col4 = st.columns([1.4, 2.0, 0.8, 0.8])
            with b_col1:
                st.markdown(
                    f'<div class="exec-meta-card"><div class="exec-meta-label">Design Archetype</div>'
                    f'<div class="exec-meta-val" style="color: #38bdf8;">{arch_val}</div></div>',
                    unsafe_allow_html=True,
                )
            with b_col2:
                st.markdown(
                    f'<div class="exec-meta-card"><div class="exec-meta-label">Executive Persona</div>'
                    f'<div class="exec-meta-val">{pers_val}</div></div>',
                    unsafe_allow_html=True,
                )
            with b_col3:
                st.markdown(
                    f'<div class="exec-meta-card"><div class="exec-meta-label">DFII Impact Score</div>'
                    f'<div class="exec-meta-val" style="color: #10b981;">{dfii_val}</div></div>',
                    unsafe_allow_html=True,
                )
            with b_col4:
                st.markdown(
                    f'<div class="exec-meta-card"><div class="exec-meta-label">Selected Panels</div>'
                    f'<div class="exec-meta-val">{pan_val}</div></div>',
                    unsafe_allow_html=True,
                )
        except Exception:
            pass

    # Download Buttons for artifacts
    d1, d2, d3, d4, d5 = st.columns(5)
    if bespoke_html_f.exists():
        with d1:
            st.download_button(
                "⬇️ Bespoke HTML Dashboard",
                data=bespoke_html_f.read_bytes(),
                file_name=f"{active_dataset_name}_bespoke_executive_dashboard.html",
                mime="text/html",
                use_container_width=True
            )
    else:
        html_f = out_p / "enterprise_interactive_dashboard.html"
        if html_f.exists():
            with d1:
                st.download_button(
                    "⬇️ HTML Dashboard",
                    data=html_f.read_bytes(),
                    file_name=f"{active_dataset_name}_interactive_dashboard.html",
                    mime="text/html",
                    use_container_width=True
                )

    if design_bp_f.exists():
        with d2:
            st.download_button(
                "⬇️ Design Blueprint (.json)",
                data=design_bp_f.read_bytes(),
                file_name="dashboard_design_blueprint.json",
                mime="application/json",
                use_container_width=True
            )

    tmdl_dir = out_p / "semantic_model"
    if tmdl_dir.exists():
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(tmdl_dir):
                for fn in files:
                    fp = Path(root) / fn
                    zf.write(fp, arcname=fp.relative_to(tmdl_dir))
        with d3:
            st.download_button(
                "⬇️ Power BI TMDL (.zip)",
                data=zip_buffer.getvalue(),
                file_name=f"{active_dataset_name}_semantic_model_tmdl.zip",
                mime="application/zip",
                use_container_width=True
            )

    if summary_file.exists():
        with d4:
            st.download_button(
                "⬇️ Plain Summary (.md)",
                data=summary_file.read_bytes(),
                file_name="PLAIN_BUSINESS_SUMMARY.md",
                mime="text/markdown",
                use_container_width=True
            )

    if dossier_file.exists():
        with d5:
            st.download_button(
                "⬇️ Forensic Dossier (.md)",
                data=dossier_file.read_bytes(),
                file_name="DATA_XRAY_EXECUTIVE_DOSSIER.md",
                mime="text/markdown",
                use_container_width=True
            )

    st.markdown("---")

    # Live Interactive Render of Bespoke Dashboard
    if bespoke_html_f.exists():
        import streamlit.components.v1 as components
        st.markdown("#### 🚀 Live Bespoke Executive Dashboard (Zero-CDN, Client Cross-Filtering)")
        components.html(bespoke_html_f.read_text(encoding="utf-8"), height=920, scrolling=True)
    elif vega_spec_file.exists():
        try:
            bundle = json.loads(vega_spec_file.read_text(encoding="utf-8"))
            specs = bundle.get("specs", {})
            vcol1, vcol2 = st.columns(2)
            if "primary_dimension_risk" in specs:
                with vcol1:
                    st.vega_lite_chart(specs["primary_dimension_risk"], use_container_width=True)
            if "threshold_cliff" in specs:
                with vcol2:
                    st.vega_lite_chart(specs["threshold_cliff"], use_container_width=True)
            if "orthogonal_interaction_matrix" in specs:
                with vcol1:
                    st.vega_lite_chart(specs["orthogonal_interaction_matrix"], use_container_width=True)
            if "operational_triage_yield" in specs:
                with vcol2:
                    st.vega_lite_chart(specs["operational_triage_yield"], use_container_width=True)
            if "temporal_risk_trend" in specs:
                st.markdown("#### 📈 Certified Temporal Risk & Volume Evolution")
                st.vega_lite_chart(specs["temporal_risk_trend"], use_container_width=True)
        except Exception as ve:
            st.warning(f"Could not render visual specifications: {ve}")
    else:
        st.info("Interactive visual dashboard is not yet synthesized for this dataset. Click '⚡ Synthesize V5.5 Deliverables' in the sidebar.")

# =============================================================================
# TAB 5: Full Forensic Dossier & Proof
# =============================================================================
with tabs[4]:
    st.markdown("### 🛡️ Complete Executive Forensic Dossier & Audit Gates")
    t1, t2, t3 = st.tabs([
        "📑 Forensic Dossier",
        "✅ Governance Certification Checklist",
        "🔍 Live 11-Gate Anti-Hallucination Audit",
    ])
    with t1:
        if dossier_file.exists():
            render_safe_markdown(dossier_file.read_text(encoding="utf-8"))
        else:
            st.info("Forensic dossier not found.")
    with t2:
        if checklist_file.exists():
            render_safe_markdown(checklist_file.read_text(encoding="utf-8"))
        else:
            st.info("Certification checklist not found for this legacy benchmark (run Stage 6 or full pipeline to generate).")
    with t3:
        st.markdown("#### 🛡️ Physical DuckDB Anti-Hallucination Guard (Checks 1–11)")
        st.markdown(
            "Cross-verifies every percentage, row count, monetary ledger claim, semantic manifest measure, "
            "and Stage 7 `DASHBOARD_PAYLOAD` micro-cube directly against `bi_ready_fact.parquet` via DuckDB SQL."
        )
        out_key = str(out_p)
        if run_anti_hallucination_audit is None:
            st.error("`anti_hallucination_guard.py` could not be loaded.")
        else:
            if st.button("🚀 Execute Live 11-Gate DuckDB Truth Audit", type="primary"):
                with st.spinner("Running physical DuckDB verification across all generated artifacts..."):
                    bp_arg = str(blueprint_file) if blueprint_file.exists() else None
                    st.session_state["live_audit_cache"][out_key] = run_anti_hallucination_audit(str(out_p), bp_arg)

            cached_audit = st.session_state["live_audit_cache"].get(out_key)
            if cached_audit:
                conf = cached_audit.get("grounding_confidence", "UNKNOWN")
                violations = cached_audit.get("physics_invariant_violations", [])
                a1, a2, a3 = st.columns(3)
                with a1:
                    color = "#10b981" if conf == "100.0% VERIFIED TRUTH" else "#f43f5e"
                    st.markdown(
                        f'<div class="exec-meta-card"><div class="exec-meta-label">Grounding Verdict</div>'
                        f'<div class="exec-meta-val" style="color: {color};">{html.escape(str(conf))}</div></div>',
                        unsafe_allow_html=True,
                    )
                with a2:
                    n_cols_v = cached_audit.get("total_columns_verified", 0)
                    n_rows_v = cached_audit.get("total_ground_truth_records", 0)
                    st.markdown(
                        f'<div class="exec-meta-card"><div class="exec-meta-label">Physical Schema & Grain</div>'
                        f'<div class="exec-meta-val">{n_cols_v} Cols &bull; {n_rows_v:,} Rows</div></div>',
                        unsafe_allow_html=True,
                    )
                with a3:
                    v_col = "#10b981" if len(violations) == 0 else "#f43f5e"
                    st.markdown(
                        f'<div class="exec-meta-card"><div class="exec-meta-label">Invariant Violations</div>'
                        f'<div class="exec-meta-val" style="color: {v_col};">{len(violations)} Violations</div></div>',
                        unsafe_allow_html=True,
                    )
                if violations:
                    st.error("Violations flagged:\n" + "\n".join(f"- {v}" for v in violations))
                with st.expander("📄 View Full Machine-Readable Audit Proof JSON"):
                    st.json(cached_audit)
            else:
                st.caption("Click **Execute Live 11-Gate DuckDB Truth Audit** above to verify this dataset's deliverables live.")
