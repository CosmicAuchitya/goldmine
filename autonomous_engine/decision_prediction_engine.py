"""
=============================================================================
STAGE 8: AUTONOMOUS PREDICTIVE DECISION INTELLIGENCE & ML SIMULATOR ENGINE
=============================================================================
Trains a real, leak-proof, 3-fold out-of-fold calibrated ML ensemble
(HistGradientBoosting) directly on any workspace's physical DuckDB Parquet
(`bi_ready_fact.parquet`), then simulates client business decisions using
500-iteration Bootstrap + Epistemic + Elasticity Monte Carlo counterfactual
inference to answer 4 exact founder questions with zero forced outcomes:
1. "Mere is faisle se kitne % chance hain ki fayda hoga?" (Calibrated Benefit %)
2. "Kis cheez / store / segment me sabse zyada fayda hoga?" (Top Winners Breakdown)
3. "Kis cheez me fayda nahi hoga ya kam hoga?" (No-Gain / Trade-Off Zones)
4. "Agar loss hoga toh kyun hoga?" (Explicit Downside Risks, Elasticity, Confounders & AUC)

Strict Scientific & Anti-Forcing Guardrails (Audited V8.1):
- Automatic Post-Event Target Purity Leakage Blocker (>96.5% purity columns like
  `return_reason` or `reservation_status` are automatically excluded).
- 3-Fold Stratified Cross-Fitted Ensemble: true out-of-fold ROC-AUC & Brier Score
  across 100% of working rows, plus real fold-to-fold epistemic disagreement in Monte Carlo.
- Per-Lever Statistical Noise Circuit-Breaker: even inside a high-AUC dataset, a noisy
  column (empirical p >= 0.05 AND out-of-sample permutation AUC drop < 0.003) is NEVER
  forced into STRONG_GO — it is honestly gated to NEUTRAL (~50% coin-flip).
- Simpson's Paradox / Confounder Detector: compares raw marginal gap vs ML controlled
  ceteris-paribus gap and explicitly alerts when a hidden confounder distorts raw numbers.
- CFO-Grade Empirical Accounting for `pause_segment` & Stochastic Elasticity for discounts.
- Exact 95% Confidence Intervals (2.5th to 97.5th percentile).
- Zero silent fallback: unrecognized prompts return honest `parse_needed` (never hijack
  the user's text to run an unrelated preset!).
=============================================================================
"""

from __future__ import annotations

import json
import math
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder, StandardScaler, TargetEncoder

try:
    from .pii_scrubber import is_sensitive_column_name
    from .target_resolver import (
        is_demographic_attribute,
        is_deterministic_target_leakage,
        is_index_artifact,
        is_pseudo_numeric_identifier,
        is_synthetic_column,
        resolve_canonical_target_and_cost,
    )
except ImportError:
    from pii_scrubber import is_sensitive_column_name
    from target_resolver import (
        is_demographic_attribute,
        is_deterministic_target_leakage,
        is_index_artifact,
        is_pseudo_numeric_identifier,
        is_synthetic_column,
        resolve_canonical_target_and_cost,
    )


MAX_TRAIN_ROWS = 36_000
MAX_SIM_ROWS = 25_000
BOOTSTRAP_ITERS = 500
N_ENSEMBLE_FOLDS = 3


def _fmt_money(val: float, unit_sym: str, is_monetary: bool) -> str:
    if not is_monetary or unit_sym in ("", "events", "Events"):
        return f"{val:,.1f} events"
    sign = "-" if val < 0 else ""
    av = abs(float(val))
    if unit_sym == "₹" and av >= 100_000:
        if av >= 10_000_000:
            return f"{sign}₹{av / 10_000_000:.2f} Cr (₹{av:,.0f})"
        return f"{sign}₹{av / 100_000:.2f} L (₹{av:,.0f})"
    if unit_sym in ("¥", "₩"):
        return f"{sign}{unit_sym}{av:,.0f}"
    return f"{sign}{unit_sym}{av:,.2f}"


def _compute_ece_pct(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    """Computes Expected Calibration Error (%) across 10 probability bins."""
    if len(y_true) < 20:
        return 0.0
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = float(len(y_true))
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        mask = (y_prob >= lo) & (y_prob <= hi if i == n_bins - 1 else y_prob < hi)
        cnt = int(mask.sum())
        if cnt > 0:
            ece += (cnt / n) * abs(float(y_prob[mask].mean()) - float(y_true[mask].mean()))
    return round(ece * 100.0, 2)


def _find_brier_optimal_weights(y: np.ndarray, probs_list: List[np.ndarray]) -> Tuple[float, ...]:
    """Finds Brier-score-optimal convex blend weights across 1-3 model families on OOF predictions."""
    k = len(probs_list)
    if k == 1:
        return (1.0,)
    best_w: Tuple[float, ...] = tuple([1.0] + [0.0] * (k - 1))
    best_brier = float(brier_score_loss(y, probs_list[0]))
    if k == 2:
        p0, p1 = probs_list
        for i in range(21):
            w0 = i / 20.0
            w1 = 1.0 - w0
            b = float(brier_score_loss(y, np.clip(w0 * p0 + w1 * p1, 0.001, 0.999)))
            if b < best_brier - 1e-6:
                best_brier = b
                best_w = (round(w0, 2), round(w1, 2))
        return best_w
    p0, p1, p2 = probs_list[0], probs_list[1], probs_list[2]
    for i in range(21):
        w0 = i / 20.0
        for j in range(21 - i):
            w1 = j / 20.0
            w2 = max(0.0, 1.0 - w0 - w1)
            b = float(brier_score_loss(y, np.clip(w0 * p0 + w1 * p1 + w2 * p2, 0.001, 0.999)))
            if b < best_brier - 1e-6:
                best_brier = b
                best_w = (round(w0, 2), round(w1, 2), round(w2, 2))
    return best_w


class _BlendedFoldModel:
    """
    Combines diverse model families (HistGradientBoosting + ExtraTrees + Regularized Logistic)
    using Brier-optimal out-of-fold convex weights and optional Platt probability calibration.
    """

    def __init__(
        self,
        models: List[Pipeline],
        weights: Tuple[float, ...],
        platt_coef: Optional[Tuple[float, float]] = None,
    ):
        self.models = models
        self.weights = weights
        self.platt_coef = platt_coef

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        p_blend = np.zeros(len(X), dtype=float)
        for m, w in zip(self.models, self.weights):
            if w > 0.0:
                p_blend += w * np.clip(m.predict_proba(X)[:, 1], 0.001, 0.999)
        p_blend = np.clip(p_blend, 0.001, 0.999)
        if self.platt_coef is not None:
            a, b = self.platt_coef
            logits = np.log(p_blend / (1.0 - p_blend))
            z = np.clip(a * logits + b, -12.0, 12.0)
            p_blend = np.clip(1.0 / (1.0 + np.exp(-z)), 0.001, 0.999)
        return np.column_stack([1.0 - p_blend, p_blend])


def _two_prop_p_value(k1: int, n1: int, k2: int, n2: int) -> float:
    """Two-sided pooled two-proportion z-test p-value (returns 1.0 on degenerate inputs)."""
    if n1 < 5 or n2 < 5:
        return 1.0
    p1 = k1 / n1
    p2 = k2 / n2
    p_pool = (k1 + k2) / (n1 + n2)
    se = math.sqrt(max(1e-12, p_pool * (1.0 - p_pool) * (1.0 / n1 + 1.0 / n2)))
    if se <= 1e-10:
        return 1.0
    z = abs(p1 - p2) / se
    return float(2.0 * (1.0 - scipy_stats.norm.cdf(z)))


def _is_post_event_purity_leakage(df: pd.DataFrame, col: str, y_bin: np.ndarray) -> bool:
    """
    Detects post-event explanation columns (e.g. `return_reason`, `cancel_reason`,
    `failure_code`, `refund_status`, `writeoff_note`) whose values almost perfectly
    separate adverse vs healthy rows (>96.5% purity or explicit post-event name).
    """
    c_low = str(col).lower()
    explicit_leak_tokens = (
        "return_reason", "cancel_reason", "cancellation_reason", "failure_reason",
        "churn_reason", "exit_reason", "refund_reason", "rejection_reason",
        "reservation_status", "refund_amount", "writeoff", "loss_reason",
        "defect_reason", "complaint_resolution", "outcome", "rto_reason",
        "claim_status", "settlement_status", "penalty_charged",
    )
    if any(tok in c_low for tok in explicit_leak_tokens):
        return True

    s = df[col]
    if not pd.api.types.is_numeric_dtype(s):
        nunq = int(s.nunique(dropna=False))
        if 2 <= nunq <= 40:
            tmp = pd.DataFrame({"v": s.fillna("__NA__").astype(str), "y": y_bin})
            grp = tmp.groupby("v")["y"].agg(["count", "mean"])
            weighted_purity = float((np.maximum(grp["mean"], 1.0 - grp["mean"]) * grp["count"]).sum() / max(len(tmp), 1))
            base_purity = max(float(y_bin.mean()), 1.0 - float(y_bin.mean()))
            if weighted_purity >= 0.965 and (weighted_purity - base_purity) >= 0.08:
                return True
    return False


def _is_date_like_column(series: pd.Series, col_name: str) -> bool:
    c_low = str(col_name).lower()
    if any(k in c_low for k in ("date", "timestamp", "created_at", "updated_at", "dob", "month_year")):
        return True
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
        sample = series.dropna().astype(str).head(25)
        if len(sample) >= 5:
            iso_hits = sample.str.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}").mean()
            if iso_hits >= 0.8:
                return True
    return False


class PredictiveDecisionEngine:
    """
    Self-contained, leak-proof, 3-fold cross-fitted ML Decision Predictor &
    Counterfactual Simulator for any audited DataX-Ray workspace (`bi_ready_fact.parquet`).
    """

    def __init__(self, output_dir: str, region_profile: Optional[str] = None):
        self.output_dir = Path(output_dir).resolve()
        self.region_profile = region_profile

        fact_path = self.output_dir / "bi_ready_fact.parquet"
        if not fact_path.exists():
            pqs = list(self.output_dir.glob("*.parquet"))
            if not pqs:
                raise FileNotFoundError(f"No Parquet fact table found in {self.output_dir}")
            fact_path = pqs[0]

        self.fact_path = fact_path
        self.df_full = pd.read_parquet(fact_path)

        blueprint: Dict[str, Any] = {}
        for cand in (self.output_dir / "execution_blueprint.json", self.output_dir.parent / "execution_blueprint.json"):
            if cand.exists():
                try:
                    blueprint = json.loads(cand.read_text(encoding="utf-8"))
                    break
                except Exception:
                    pass

        self.canonical = resolve_canonical_target_and_cost(
            self.df_full, blueprint=blueprint, region_profile=region_profile
        )
        self.target_col: Optional[str] = self.canonical.get("target_col")
        self.cost_col: Optional[str] = self.canonical.get("cost_col")
        self.is_monetary: bool = bool(self.cost_col and self.cost_col in self.df_full.columns)
        self.unit_sym: str = str(self.canonical.get("unit_symbol") or "$") if self.is_monetary else "events"

        y_raw = self.canonical["binary_target"].astype(int).to_numpy()
        self.df_full = self.df_full.copy()
        self.df_full["_dx_y_bin"] = y_raw

        # Detect optional pricing/margin/discount columns for algebraically consistent economics
        self.discount_col = self._find_semantic_numeric(("discount_pct", "discount_percent", "disc_pct", "discount_rate"))
        self.mrp_col = self._find_semantic_numeric(("mrp_inr", "mrp", "list_price", "base_price", "unit_price"))
        self.margin_col = self._find_semantic_numeric(("net_margin_inr", "gross_margin_inr", "profit_inr", "net_margin", "gross_margin", "profit"))
        self.cogs_col = self._find_semantic_numeric(("cost_price_inr", "cogs_inr", "cost_price", "unit_cost", "cogs"))

        # Check whether margin_col is a TRUE post-return ledger (negative mean on adverse rows) vs pre-return gross margin
        self._margin_is_post_event_ledger = False
        if self.margin_col and self.margin_col in self.df_full.columns:
            m_ser = pd.to_numeric(self.df_full[self.margin_col], errors="coerce")
            adv_m = m_ser[self.df_full["_dx_y_bin"] == 1].dropna()
            if len(adv_m) >= 10 and float(adv_m.mean()) < 0.0:
                self._margin_is_post_event_ledger = True

        # Feature discovery with strict anti-leakage filters
        self.numeric_features: List[str] = []
        self.categorical_features: List[str] = []
        self.blocked_leakage_cols: List[str] = []
        self._top_cat_maps: Dict[str, List[str]] = {}

        self._select_clean_features(blueprint)

        # Train 3-fold cross-fitted calibrated ML ensemble on clean features
        self.fold_models: List[Pipeline] = []
        self.model: Optional[Pipeline] = None
        self.model_metrics: Dict[str, Any] = {}
        self.feature_importances: List[Dict[str, Any]] = []
        self.feature_auc_drop_map: Dict[str, float] = {}
        self._train_cross_fitted_ensemble()

    def _find_semantic_numeric(self, candidates: Tuple[str, ...]) -> Optional[str]:
        cols_low = {c.lower(): c for c in self.df_full.columns}
        for tok in candidates:
            if tok in cols_low and pd.api.types.is_numeric_dtype(self.df_full[cols_low[tok]]):
                return cols_low[tok]
        for tok in candidates:
            for cl, orig in cols_low.items():
                if tok in cl and pd.api.types.is_numeric_dtype(self.df_full[orig]):
                    return orig
        return None

    def _select_clean_features(self, blueprint: Dict[str, Any]) -> None:
        y_bin = self.df_full["_dx_y_bin"].to_numpy()
        n_rows = len(self.df_full)
        skip_exact = {self.target_col, "_dx_y_bin", "_is_target_event"}

        for col in self.df_full.columns:
            if col in skip_exact:
                continue
            c_low = str(col).lower()
            if is_index_artifact(col):
                continue
            is_redundant_tier = c_low.endswith("_tier") and (col[:-5] in self.df_full.columns)
            is_raw_biz_pct = any(
                k in c_low for k in ("discount", "gst", "tax", "margin", "interest", "commission", "rebate", "city_tier", "sla_pct")
            )
            if is_redundant_tier or (is_synthetic_column(col, blueprint) and not is_raw_biz_pct):
                continue
            if is_sensitive_column_name(col) or is_demographic_attribute(col):
                continue
            if is_pseudo_numeric_identifier(col, self.df_full[col]):
                continue
            if c_low in ("latitude", "longitude", "lat", "lon", "lng", "geo_lat", "geo_lng"):
                continue
            if is_deterministic_target_leakage(col, self.df_full[col], self.canonical["binary_target"], target_col=self.target_col):
                self.blocked_leakage_cols.append(col)
                continue
            if _is_date_like_column(self.df_full[col], col):
                continue
            if _is_post_event_purity_leakage(self.df_full, col, y_bin):
                self.blocked_leakage_cols.append(col)
                continue
            # Also block post-event net margin ledger column from acting as an input predictor (target leakage!)
            if self._margin_is_post_event_ledger and col == self.margin_col:
                self.blocked_leakage_cols.append(col)
                continue

            ser = self.df_full[col]
            if ser.dropna().nunique() <= 1:
                continue

            if pd.api.types.is_numeric_dtype(ser):
                self.numeric_features.append(col)
            else:
                nunq = int(ser.nunique(dropna=True))
                if nunq > max(80, int(n_rows * 0.25)):
                    continue
                if nunq >= 2:
                    self.categorical_features.append(col)
                    top_vals = ser.fillna("Missing").astype(str).value_counts().head(65).index.tolist()
                    self._top_cat_maps[col] = top_vals

        self.all_features = self.numeric_features + self.categorical_features

    def _prepare_feature_matrix(self, df_in: pd.DataFrame) -> pd.DataFrame:
        X = pd.DataFrame(index=df_in.index)
        for c in self.numeric_features:
            X[c] = pd.to_numeric(df_in[c], errors="coerce").astype(float)
        for c in self.categorical_features:
            allowed = set(self._top_cat_maps.get(c, []))
            s = df_in[c].fillna("Missing").astype(str)
            X[c] = s.where(s.isin(allowed), "Other")
        return X

    def _build_hgb_pipeline(self, n_train: int, seed: int) -> Pipeline:
        transformers = []
        cat_indices: List[int] = []
        idx_cursor = 0
        if self.numeric_features:
            transformers.append(("num", SimpleImputer(strategy="median"), self.numeric_features))
            idx_cursor += len(self.numeric_features)
        if self.categorical_features:
            transformers.append((
                "cat",
                OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1),
                self.categorical_features,
            ))
            cat_indices = list(range(idx_cursor, idx_cursor + len(self.categorical_features)))

        pre = ColumnTransformer(transformers=transformers, remainder="drop")
        max_d = 6 if n_train >= 12000 else (5 if n_train >= 2500 else 4)
        min_leaf = max(12, min(32, n_train // 55))
        clf = HistGradientBoostingClassifier(
            max_iter=150 if n_train >= 12000 else 120,
            max_depth=max_d,
            learning_rate=0.055,
            min_samples_leaf=min_leaf,
            l2_regularization=1.5,
            early_stopping=(n_train >= 12000),
            validation_fraction=0.12 if n_train >= 12000 else None,
            n_iter_no_change=15,
            categorical_features=cat_indices if cat_indices else None,
            random_state=seed,
        )
        return Pipeline([("pre", pre), ("clf", clf)])

    def _build_et_pipeline(self, n_train: int, seed: int) -> Pipeline:
        transformers = []
        if self.numeric_features:
            transformers.append(("num", SimpleImputer(strategy="median"), self.numeric_features))
        if self.categorical_features:
            transformers.append((
                "cat",
                TargetEncoder(smooth="auto", cv=3, random_state=seed),
                self.categorical_features,
            ))
        pre = ColumnTransformer(transformers=transformers, remainder="drop")
        clf = ExtraTreesClassifier(
            n_estimators=85 if n_train <= 15000 else 55,
            max_depth=14 if n_train >= 1000 else 10,
            min_samples_leaf=max(4, min(20, n_train // 250)),
            max_features="sqrt",
            n_jobs=-1,
            random_state=seed,
        )
        return Pipeline([("pre", pre), ("clf", clf)])

    def _build_lr_pipeline(self, seed: int) -> Pipeline:
        transformers = []
        if self.numeric_features:
            transformers.append((
                "num",
                Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler())]),
                self.numeric_features,
            ))
        if self.categorical_features:
            transformers.append((
                "cat",
                Pipeline([("te", TargetEncoder(smooth="auto", cv=3, random_state=seed)), ("sc", StandardScaler())]),
                self.categorical_features,
            ))
        pre = ColumnTransformer(transformers=transformers, remainder="drop")
        clf = LogisticRegression(C=0.6, max_iter=300, random_state=seed)
        return Pipeline([("pre", pre), ("clf", clf)])

    def _find_temporal_order_series(self, df_in: pd.DataFrame) -> Tuple[Optional[str], Optional[pd.Series]]:
        """Detects a genuine chronological date column for honest Out-of-Time future backtesting."""
        best_col = None
        best_dt = None
        for col in df_in.columns:
            c_low = str(col).lower()
            if c_low in (str(self.target_col or "").lower(), "_dx_y_bin", "_is_target_event"):
                continue
            if any(k in c_low for k in ("dob", "birth", "expir", "cancellation_date", "reservation_status_date", "exit_date")):
                continue
            ser = df_in[col]
            if pd.api.types.is_datetime64_any_dtype(ser):
                if ser.notna().mean() >= 0.85 and ser.nunique() >= 4:
                    return col, ser
            elif any(k in c_low for k in ("date", "timestamp", "created_at", "order_date", "invoice_date", "month_year")):
                try:
                    parsed = pd.to_datetime(ser, errors="coerce", format="mixed")
                    if parsed.notna().mean() >= 0.85 and parsed.nunique() >= 4:
                        best_col, best_dt = col, parsed
                        break
                except Exception:
                    continue
        if best_col is None and "arrival_date_year" in df_in.columns and "arrival_date_month" in df_in.columns:
            try:
                combo = df_in["arrival_date_year"].astype(str) + "-" + df_in["arrival_date_month"].astype(str) + "-01"
                parsed = pd.to_datetime(combo, errors="coerce", format="mixed")
                if parsed.notna().mean() >= 0.90 and parsed.nunique() >= 4:
                    return "arrival_date_year/month", parsed
            except Exception:
                pass
        return best_col, best_dt

    def _run_temporal_backtest(self, df_work: pd.DataFrame, X_all: pd.DataFrame, y_work: np.ndarray) -> Dict[str, Any]:
        """Chronological walk-forward backtest: trains strictly on oldest 75%, evaluates on newest 25%."""
        if len(df_work) < 160:
            return {}
        d_col, d_ser = self._find_temporal_order_series(df_work)
        if d_col is None or d_ser is None:
            return {}
        try:
            valid_m = d_ser.notna().to_numpy()
            if valid_m.sum() < 160:
                return {}
            order = np.argsort(d_ser.loc[valid_m].to_numpy())
            valid_idx = np.where(valid_m)[0][order]
            split_pt = int(len(valid_idx) * 0.75)
            tr_i, te_i = valid_idx[:split_pt], valid_idx[split_pt:]
            if len(np.unique(y_work[tr_i])) < 2 or len(np.unique(y_work[te_i])) < 2:
                return {}
            pipe_t = self._build_hgb_pipeline(len(tr_i), seed=777)
            pipe_t.fit(X_all.iloc[tr_i], y_work[tr_i])
            p_oot = np.clip(pipe_t.predict_proba(X_all.iloc[te_i])[:, 1], 0.001, 0.999)
            return {
                "temporal_date_col": d_col,
                "temporal_backtest_auc": round(float(roc_auc_score(y_work[te_i], p_oot)), 4),
                "temporal_backtest_brier": round(float(brier_score_loss(y_work[te_i], p_oot)), 4),
                "temporal_test_rows": int(len(te_i)),
            }
        except Exception:
            return {}

    def _train_cross_fitted_ensemble(self) -> None:
        t0 = time.perf_counter()
        n_total = len(self.df_full)
        y_all = self.df_full["_dx_y_bin"].to_numpy()
        pos_cnt = int(y_all.sum())
        neg_cnt = int(n_total - pos_cnt)

        if not self.all_features or pos_cnt < 6 or neg_cnt < 6 or n_total < 30:
            self.fold_models = []
            self.model = None
            self.model_metrics = {
                "trained": False,
                "reason": "Insufficient class variance or sample size for reliable ML training.",
                "roc_auc": 0.50,
                "brier_score": 0.25,
                "calibration_gap_pct": 0.0,
                "ece_pct": 0.0,
                "confidence_tier": "LOW",
                "confidence_label_hi": "कम डेटा सैंपल (Training Skipped)",
                "train_rows": n_total,
                "test_rows": 0,
                "features_used": self.all_features,
                "blocked_leakage_columns": self.blocked_leakage_cols,
            }
            return

        if n_total > MAX_TRAIN_ROWS:
            df_work = self.df_full.sample(n=MAX_TRAIN_ROWS, random_state=42)
        else:
            df_work = self.df_full

        X_all = self._prepare_feature_matrix(df_work).reset_index(drop=True)
        y_work = df_work["_dx_y_bin"].to_numpy()

        n_splits = N_ENSEMBLE_FOLDS if min(int(y_work.sum()), int((1 - y_work).sum())) >= N_ENSEMBLE_FOLDS * 2 else 2
        skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)

        oof_hgb = np.zeros(len(y_work), dtype=float)
        oof_et = np.zeros(len(y_work), dtype=float)
        oof_lr = np.zeros(len(y_work), dtype=float)
        raw_fold_triples: List[List[Pipeline]] = []
        fold_splits: List[Tuple[np.ndarray, np.ndarray]] = []
        use_et = (len(y_work) >= 80)
        use_lr = (len(y_work) >= 60)

        for fold_idx, (tr_idx, va_idx) in enumerate(skf.split(X_all, y_work)):
            seed = 42 + fold_idx * 17
            X_tr, y_tr = X_all.iloc[tr_idx], y_work[tr_idx]
            X_va = X_all.iloc[va_idx]

            m_hgb = self._build_hgb_pipeline(len(tr_idx), seed=seed)
            m_hgb.fit(X_tr, y_tr)
            oof_hgb[va_idx] = np.clip(m_hgb.predict_proba(X_va)[:, 1], 0.001, 0.999)
            f_list: List[Pipeline] = [m_hgb]

            if use_et:
                try:
                    m_et = self._build_et_pipeline(len(tr_idx), seed=seed + 3)
                    m_et.fit(X_tr, y_tr)
                    oof_et[va_idx] = np.clip(m_et.predict_proba(X_va)[:, 1], 0.001, 0.999)
                    f_list.append(m_et)
                except Exception:
                    use_et = False
            if use_lr:
                try:
                    m_lr = self._build_lr_pipeline(seed=seed + 7)
                    m_lr.fit(X_tr, y_tr)
                    oof_lr[va_idx] = np.clip(m_lr.predict_proba(X_va)[:, 1], 0.001, 0.999)
                    f_list.append(m_lr)
                except Exception:
                    use_lr = False

            raw_fold_triples.append(f_list)
            fold_splits.append((tr_idx, va_idx))

        # Keep consistent family count across all folds
        min_fams = min(len(fl) for fl in raw_fold_triples)
        oof_list = [oof_hgb]
        fam_names = ["HGB"]
        if min_fams >= 2 and use_et:
            oof_list.append(oof_et)
            fam_names.append("ExtraTrees")
        if min_fams >= 3 and use_lr:
            oof_list.append(oof_lr)
            fam_names.append("Logistic")
        elif min_fams == 2 and not use_et and use_lr:
            oof_list.append(oof_lr)
            fam_names.append("Logistic")

        weights = _find_brier_optimal_weights(y_work, oof_list)
        oof_probs = np.zeros(len(y_work), dtype=float)
        for w, arr in zip(weights, oof_list):
            oof_probs += w * arr
        oof_probs = np.clip(oof_probs, 0.001, 0.999)

        # Optional Platt Recalibration ONLY if it strictly lowers OOF Brier Score & ECE!
        platt_coef: Optional[Tuple[float, float]] = None
        raw_brier = float(brier_score_loss(y_work, oof_probs))
        raw_ece = _compute_ece_pct(y_work, oof_probs)
        if len(y_work) >= 200 and raw_ece >= 1.2:
            try:
                logits_oof = np.log(oof_probs / (1.0 - oof_probs)).reshape(-1, 1)
                cal_oof = np.zeros_like(oof_probs)
                for tr_i, va_i in fold_splits:
                    lr_c = LogisticRegression(C=10.0, max_iter=200)
                    lr_c.fit(logits_oof[tr_i], y_work[tr_i])
                    cal_oof[va_i] = np.clip(lr_c.predict_proba(logits_oof[va_i])[:, 1], 0.001, 0.999)
                cal_brier = float(brier_score_loss(y_work, cal_oof))
                cal_ece = _compute_ece_pct(y_work, cal_oof)
                if cal_brier < raw_brier - 0.0004 and cal_ece <= raw_ece:
                    lr_full = LogisticRegression(C=10.0, max_iter=200)
                    lr_full.fit(logits_oof, y_work)
                    platt_coef = (float(lr_full.coef_[0][0]), float(lr_full.intercept_[0]))
                    oof_probs = cal_oof
            except Exception:
                platt_coef = None

        fold_models: List[Any] = [
            _BlendedFoldModel(fl[:len(weights)], weights, platt_coef=platt_coef)
            for fl in raw_fold_triples
        ]

        auc_val = float(roc_auc_score(y_work, oof_probs))
        brier_val = float(brier_score_loss(y_work, oof_probs))
        ece_val = _compute_ece_pct(y_work, oof_probs)
        base_rate = float(y_work.mean())
        pred_mean = float(oof_probs.mean())

        # Out-of-Time Chronological Backtest (when dataset has a real date column!)
        temporal_info = self._run_temporal_backtest(df_work, X_all, y_work)
        oot_auc = temporal_info.get("temporal_backtest_auc")
        temporal_drift_gap = round(auc_val - float(oot_auc), 4) if oot_auc is not None else None
        temporal_drift_detected = bool(
            temporal_drift_gap is not None and temporal_drift_gap >= 0.08 and float(oot_auc) < 0.72
        )

        if auc_val >= 0.72 and len(y_work) >= 120:
            tier = "HIGH"
            tier_hi = "उच्च विश्वसनीयता (Strong Pattern)"
        elif auc_val >= 0.60 and len(y_work) >= 60:
            tier = "MODERATE"
            tier_hi = "मध्यम विश्वसनीयता (Usable Signal)"
        else:
            tier = "LOW"
            tier_hi = "कम पैटर्न / ज़्यादा शोर (Caution Advised)"

        # True Out-of-Sample Permutation Feature Importance on Fold 0 validation set
        rng = np.random.default_rng(42)
        va0_idx = fold_splits[0][1]
        if len(va0_idx) > 2500:
            va0_idx = rng.choice(va0_idx, size=2500, replace=False)
        X_ev = X_all.iloc[va0_idx].copy()
        y_ev = y_work[va0_idx]
        m0 = fold_models[0]
        base_ev_auc = float(roc_auc_score(y_ev, np.clip(m0.predict_proba(X_ev)[:, 1], 0.001, 0.999)))

        imp_rows = []
        for col in self.all_features:
            X_perm = X_ev.copy()
            X_perm[col] = rng.permutation(X_perm[col].to_numpy())
            p_perm = np.clip(m0.predict_proba(X_perm)[:, 1], 0.001, 0.999)
            try:
                drop = max(0.0, base_ev_auc - float(roc_auc_score(y_ev, p_perm)))
            except Exception:
                drop = 0.0
            self.feature_auc_drop_map[col] = drop
            imp_rows.append({
                "feature": col,
                "type": "numeric" if col in self.numeric_features else "categorical",
                "auc_drop": round(drop, 4),
            })

        imp_rows.sort(key=lambda r: r["auc_drop"], reverse=True)
        tot_imp = sum(r["auc_drop"] for r in imp_rows) or 1.0
        for r in imp_rows:
            r["importance_pct"] = round((r["auc_drop"] / tot_imp) * 100.0, 1)

        active_fams = [f"{nm}({int(round(w*100))}%)" for nm, w in zip(fam_names, weights) if w >= 0.05]
        cal_tag = " + Platt Calibrated" if platt_coef is not None else ""
        algo_desc = f"{n_splits}-Fold Multi-Model Ensemble [{' + '.join(active_fams)}]{cal_tag}"

        self.fold_models = fold_models
        self.model = fold_models[0]
        self.feature_importances = imp_rows[:12]
        self.model_metrics = {
            "trained": True,
            "algorithm": algo_desc,
            "ensemble_weights": {nm: w for nm, w in zip(fam_names, weights)},
            "platt_calibrated": platt_coef is not None,
            "roc_auc": round(auc_val, 4),
            "brier_score": round(brier_val, 4),
            "ece_pct": ece_val,
            "calibration_gap_pct": round(abs(pred_mean - base_rate) * 100.0, 2),
            "baseline_adverse_rate_pct": round(base_rate * 100.0, 2),
            "temporal_backtest_auc": oot_auc,
            "temporal_backtest_brier": temporal_info.get("temporal_backtest_brier"),
            "temporal_date_col": temporal_info.get("temporal_date_col"),
            "temporal_drift_gap": temporal_drift_gap,
            "temporal_drift_detected": temporal_drift_detected,
            "confidence_tier": tier,
            "confidence_label_hi": tier_hi,
            "train_rows": int(len(y_work)),
            "test_rows": int(len(y_work)),
            "total_rows": int(n_total),
            "ensemble_folds": n_splits,
            "train_time_sec": round(time.perf_counter() - t0, 2),
            "features_used": list(self.all_features),
            "numeric_features": list(self.numeric_features),
            "categorical_features": list(self.categorical_features),
            "blocked_leakage_columns": list(self.blocked_leakage_cols),
            "is_monetary": self.is_monetary,
            "unit_symbol": self.unit_sym,
            "target_col": self.target_col,
            "cost_col": self.cost_col,
        }

    # -------------------------------------------------------------------------
    # SMART 1-CLICK DECISION SCENARIO GENERATOR (ONLY STATISTICALLY VALID PRESETS)
    # -------------------------------------------------------------------------
    def get_model_overview_and_presets(self) -> Dict[str, Any]:
        presets: List[Dict[str, Any]] = []
        df = self.df_full
        y = df["_dx_y_bin"].to_numpy()
        base_rate = float(y.mean()) if len(y) else 0.0

        non_replaceable_tokens = (
            "store", "branch", "city", "region", "state", "country", "zone",
            "geography", "location", "manager", "cashier", "circle", "hub",
        )
        top_cat_feats = [f["feature"] for f in self.feature_importances if f["type"] == "categorical"] or self.categorical_features[:3]

        # 1. Best Statistically Significant Categorical Replacement Preset
        for c_col in top_cat_feats:
            if any(tok in c_col.lower() for tok in non_replaceable_tokens):
                continue
            grp = df.groupby(c_col, dropna=False)["_dx_y_bin"].agg(["count", "sum", "mean"])
            valid = grp[grp["count"] >= max(15, int(len(df) * 0.02))].sort_values("mean", ascending=False)
            if len(valid) >= 2:
                worst_val = str(valid.index[0])
                best_val = str(valid.index[-1])
                worst_r = float(valid.iloc[0]["mean"])
                best_r = float(valid.iloc[-1]["mean"])
                pval = _two_prop_p_value(
                    int(valid.iloc[0]["sum"]), int(valid.iloc[0]["count"]),
                    int(valid.iloc[-1]["sum"]), int(valid.iloc[-1]["count"]),
                )
                if worst_r > best_r + 0.03 and pval < 0.05:
                    presets.append({
                        "preset_id": f"replace_{c_col}",
                        "icon": "🔄",
                        "title_en": f"Replace '{worst_val}' with '{best_val}' ({c_col.replace('_', ' ').title()})",
                        "title_hi": f"'{worst_val}' को हटाकर '{best_val}' से बदल दें ({c_col.replace('_', ' ')})",
                        "subtitle_en": f"Shifts {int(valid.iloc[0]['count']):,} records from {worst_r*100:.1f}% risk cohort to {best_r*100:.1f}% best performer.",
                        "subtitle_hi": f"{int(valid.iloc[0]['count']):,} रिकॉर्ड्स को {worst_r*100:.1f}% रिस्क से {best_r*100:.1f}% सुरक्षित स्तर पर शिफ्ट करें।",
                        "decision": {
                            "action_type": "replace_category",
                            "column": c_col,
                            "from_value": worst_val,
                            "to_value": best_val,
                            "description": f"Switch {c_col} from {worst_val} to {best_val}",
                        },
                    })
                    if len(presets) >= 1:
                        break

        # 2. Best Statistically Significant Numeric Cap / Floor Preset
        top_num_feats = [f["feature"] for f in self.feature_importances if f["type"] == "numeric"] or self.numeric_features[:3]
        for n_col in top_num_feats:
            if n_col in (self.cost_col, self.margin_col, self.cogs_col, self.mrp_col):
                continue
            s_num = pd.to_numeric(df[n_col], errors="coerce")
            valid_mask = s_num.notna()
            if valid_mask.sum() < 30:
                continue
            q70 = float(s_num[valid_mask].quantile(0.70))
            q30 = float(s_num[valid_mask].quantile(0.30))
            hi_m = valid_mask & (s_num > q70)
            lo_m = valid_mask & (s_num <= q30)
            if hi_m.sum() < 10 or lo_m.sum() < 10:
                continue
            hi_rate = float(y[hi_m].mean())
            lo_rate = float(y[lo_m].mean())
            pval = _two_prop_p_value(int(y[hi_m].sum()), int(hi_m.sum()), int(y[lo_m].sum()), int(lo_m.sum()))
            if hi_rate > lo_rate + 0.04 and pval < 0.05:
                cap_v = round(q70, 1)
                presets.append({
                    "preset_id": f"cap_{n_col}",
                    "icon": "🛡️",
                    "title_en": f"Cap '{n_col.replace('_', ' ').title()}' at ≤ {cap_v:g}",
                    "title_hi": f"'{n_col.replace('_', ' ')}' की अधिकतम सीमा {cap_v:g} तय करें",
                    "subtitle_en": f"High values (> {cap_v:g}) fail at {hi_rate*100:.1f}% vs {lo_rate*100:.1f}% in lower band.",
                    "subtitle_hi": f"{cap_v:g} से ऊपर खराबी {hi_rate*100:.1f}% है, जबकि नीचे सिर्फ़ {lo_rate*100:.1f}%।",
                    "decision": {
                        "action_type": "cap_numeric",
                        "column": n_col,
                        "value": cap_v,
                        "description": f"Cap {n_col} at maximum {cap_v:g}",
                    },
                })
                if len(presets) >= 3:
                    break
            elif lo_rate > hi_rate + 0.04 and pval < 0.05:
                fl_v = round(q30, 1)
                presets.append({
                    "preset_id": f"floor_{n_col}",
                    "icon": "📈",
                    "title_en": f"Raise Minimum '{n_col.replace('_', ' ').title()}' to ≥ {fl_v:g}",
                    "title_hi": f"'{n_col.replace('_', ' ')}' का न्यूनतम स्तर {fl_v:g} बढ़ाएं",
                    "subtitle_en": f"Low values (≤ {fl_v:g}) fail at {lo_rate*100:.1f}% vs {hi_rate*100:.1f}% above.",
                    "subtitle_hi": f"{fl_v:g} से नीचे खराबी {lo_rate*100:.1f}% है, ऊपर सिर्फ़ {hi_rate*100:.1f}%।",
                    "decision": {
                        "action_type": "floor_numeric",
                        "column": n_col,
                        "value": fl_v,
                        "description": f"Raise floor of {n_col} to {fl_v:g}",
                    },
                })
                if len(presets) >= 3:
                    break

        # 3. Discount Cap Preset if discount_col exists and wasn't added yet
        if self.discount_col and not any(p["decision"].get("column") == self.discount_col for p in presets):
            s_d = pd.to_numeric(df[self.discount_col], errors="coerce").dropna()
            if len(s_d) >= 30 and float(s_d.max()) > 15.0:
                cap_disc = round(min(20.0, float(s_d.quantile(0.75))), 1)
                if (s_d > cap_disc).sum() >= 10:
                    presets.append({
                        "preset_id": f"cap_{self.discount_col}",
                        "icon": "💰",
                        "title_en": f"Limit Discounts ({self.discount_col.replace('_', ' ')}) to Max {cap_disc:g}%",
                        "title_hi": f"डिस्काउंट ({self.discount_col.replace('_', ' ')}) को अधिकतम {cap_disc:g}% पर रोकें",
                        "subtitle_en": "Tests margin recovery vs customer walk-away elasticity honestly.",
                        "subtitle_hi": "ज़्यादा डिस्काउंट रोकने से बचने वाला मार्जिन बनाम ग्राहक छूटने के रिस्क की जाँच करें।",
                        "decision": {
                            "action_type": "cap_numeric",
                            "column": self.discount_col,
                            "value": cap_disc,
                            "description": f"Cap {self.discount_col} at {cap_disc:g}%",
                        },
                    })

        # 4. Pause / Exclude Worst Cohort Preset (Honest Trade-Off Test!)
        if top_cat_feats:
            c0 = top_cat_feats[0]
            grp = df.groupby(c0, dropna=False)["_dx_y_bin"].agg(["count", "mean"])
            valid = grp[grp["count"] >= max(15, int(len(df) * 0.02))].sort_values("mean", ascending=False)
            if len(valid) >= 2:
                w_val = str(valid.index[0])
                presets.append({
                    "preset_id": f"pause_{c0}",
                    "icon": "⏸️",
                    "title_en": f"Pause / Stop '{w_val}' Completely (Trade-Off Test)",
                    "title_hi": f"'{w_val}' को पूरी तरह बंद करें (नफ़ा बनाम नुकसान टेस्ट)",
                    "subtitle_en": "Honest CFO test: does shutting it down save more than the healthy profit you give up?",
                    "subtitle_hi": "ईमानदार जाँच: क्या इसे बंद करने से नुकसान बचेगा या अच्छे ऑर्डर छूटने का घाटा ज़्यादा होगा?",
                    "decision": {
                        "action_type": "pause_segment",
                        "column": c0,
                        "from_value": w_val,
                        "description": f"Pause/exclude {c0} = {w_val}",
                    },
                })

        levers = []
        for c in self.categorical_features[:12]:
            vals = df[c].fillna("Missing").astype(str).value_counts().head(25).index.tolist()
            levers.append({"column": c, "type": "categorical", "values": vals})
        for c in self.numeric_features[:12]:
            s = pd.to_numeric(df[c], errors="coerce").dropna()
            if len(s):
                levers.append({
                    "column": c,
                    "type": "numeric",
                    "min": round(float(s.min()), 2),
                    "median": round(float(s.median()), 2),
                    "p75": round(float(s.quantile(0.75)), 2),
                    "max": round(float(s.max()), 2),
                })

        return {
            "status": "ready" if self.fold_models else "limited",
            "model_metrics": self.model_metrics,
            "top_drivers": self.feature_importances[:8],
            "presets": presets[:4],
            "levers": levers,
        }

    # -------------------------------------------------------------------------
    # NATURAL LANGUAGE DECISION PARSER (WORD-BOUNDARY SAFE, ZERO FORCED FALLBACK)
    # -------------------------------------------------------------------------
    def parse_decision_text(self, decision_text: str) -> Optional[Dict[str, Any]]:
        """
        Parses a plain English or Hinglish founder decision into a structured action spec.
        Returns None (never silently forces an unrelated preset!) if no recognized lever
        or entity matches the dataset.
        """
        txt = str(decision_text or "").strip()
        low = txt.lower()
        df = self.df_full

        scope_col: Optional[str] = None
        scope_val: Optional[str] = None
        matched_cat_values: List[Tuple[str, str, int, int]] = []  # (col, val, start, end)

        for c in self.categorical_features:
            for v in self._top_cat_maps.get(c, []):
                vl = v.lower().strip()
                if len(vl) < 2:
                    continue
                # Strict word-boundary regex so "Goa" never falsely matches "goal"
                pat = r"(?<!\w)" + re.escape(vl) + r"(?!\w)"
                m = re.search(pat, low)
                if m:
                    matched_cat_values.append((c, v, m.start(), m.end()))

        # Prefer earlier start, then longer match
        matched_cat_values.sort(key=lambda x: (x[2], -(x[3] - x[2])))

        # Deduplicate overlapping spans
        clean_matches: List[Tuple[str, str, int, int]] = []
        for c, v, st, en in matched_cat_values:
            if not any(not (en <= st2 or st >= en2) for _, _, st2, en2 in clean_matches):
                clean_matches.append((c, v, st, en))

        # Detect explicit numeric column mention
        matched_num_col: Optional[str] = None
        for c in self.numeric_features:
            cn_space = c.lower().replace("_", " ")
            if re.search(r"(?<!\w)" + re.escape(c.lower()) + r"(?!\w)", low) or re.search(r"(?<!\w)" + re.escape(cn_space) + r"(?!\w)", low):
                matched_num_col = c
                break
        if not matched_num_col:
            if any(w in low for w in ("discount", "chhoot", "choot", "डिस्काउंट", "छूट")) and self.discount_col:
                matched_num_col = self.discount_col
            elif any(w in low for w in ("age", "old stock", "purana stock", "stock_age", "दिन", "पुराना")):
                matched_num_col = next((c for c in self.numeric_features if "age" in c.lower() or "day" in c.lower()), None)
            elif any(w in low for w in ("delivery", "sla", "dispatch", "delay", "देरी", "डिलीवरी")):
                matched_num_col = next((c for c in self.numeric_features if any(k in c.lower() for k in ("delay", "sla", "hour", "minute", "day", "lead"))), None)
            elif any(w in low for w in ("price", "mrp", "rate", "कीमत", "दाम")):
                matched_num_col = self.mrp_col or self.cost_col

        # Mask matched categorical value spans BEFORE extracting standalone numbers
        # so "In V2 Kanpur Kakadeo cap discount at 15" extracts 15, NOT 2 from "V2"!
        low_chars = list(low)
        for _, _, st, en in clean_matches:
            for i in range(st, en):
                low_chars[i] = " "
        low_no_cats = "".join(low_chars)

        nums = re.findall(r"(?<!\w)(-?\d+(?:\.\d+)?)\s*(%|percent|प्रतिशत)?(?!\w)", low_no_cats)
        first_num = float(nums[0][0]) if nums else None
        has_pct = bool(nums and nums[0][1])

        # Case A: Two values from the SAME categorical column -> replace_category!
        by_col: Dict[str, List[str]] = {}
        for c, v, _, _ in clean_matches:
            by_col.setdefault(c, []).append(v)

        for c, vals in by_col.items():
            if len(vals) >= 2:
                for c2, v2, _, _ in clean_matches:
                    if c2 != c:
                        scope_col, scope_val = c2, v2
                        break
                return {
                    "action_type": "replace_category",
                    "column": c,
                    "from_value": vals[0],
                    "to_value": vals[1],
                    "scope_column": scope_col,
                    "scope_value": scope_val,
                    "description": txt,
                }

        # Case B: Numeric cap / floor / scale
        if matched_num_col and first_num is not None:
            if clean_matches:
                scope_col, scope_val = clean_matches[0][0], clean_matches[0][1]
            is_raise = any(w in low for w in ("increase", "raise", "badha", "min", "minimum", "at least", "बढ़ा", "ज्यादा"))
            is_scale = has_pct and any(
                w in low for w in ("reduce by", "cut by", "kam kare", "ghata", "increase by", "badha de", "कम कर", "घटा", "बढ़ा")
            ) and ("pct" not in matched_num_col.lower())
            if is_scale:
                delta = abs(first_num) if is_raise else -abs(first_num)
                mult = max(0.05, 1.0 + delta / 100.0)
                return {
                    "action_type": "scale_numeric",
                    "column": matched_num_col,
                    "delta_pct": round(delta, 2),
                    "multiplier": round(mult, 4),
                    "scope_column": scope_col,
                    "scope_value": scope_val,
                    "description": txt,
                }
            return {
                "action_type": "floor_numeric" if is_raise else "cap_numeric",
                "column": matched_num_col,
                "value": first_num,
                "scope_column": scope_col,
                "scope_value": scope_val,
                "description": txt,
            }

        # Case C: Pause / Stop / Replace single categorical value
        if clean_matches:
            c0, v0, _, _ = clean_matches[0]
            if len(clean_matches) >= 2 and clean_matches[1][0] != c0:
                scope_col, scope_val = clean_matches[1][0], clean_matches[1][1]
            is_pause = any(w in low for w in ("stop", "pause", "band", "drop", "remove", "hata", "बंद", "रोक"))
            is_replace = any(w in low for w in ("replace", "switch", "badal", "change", "बदल"))
            if is_replace and not is_pause:
                grp = df.groupby(c0, dropna=False)["_dx_y_bin"].agg(["count", "mean"])
                peers = grp[(grp.index.astype(str) != v0) & (grp["count"] >= 10)].sort_values("mean")
                if len(peers):
                    return {
                        "action_type": "replace_category",
                        "column": c0,
                        "from_value": v0,
                        "to_value": str(peers.index[0]),
                        "scope_column": scope_col,
                        "scope_value": scope_val,
                        "description": txt,
                    }
            return {
                "action_type": "pause_segment",
                "column": c0,
                "from_value": v0,
                "scope_column": scope_col,
                "scope_value": scope_val,
                "description": txt,
            }

        # Only run top preset if user EXPLICITLY asked for the best/recommended decision!
        explicit_auto_tokens = ("best decision", "top recommendation", "best idea", "sabse achha", "sabse best", "auto suggest", "सबसे अच्छा")
        if any(tok in low for tok in explicit_auto_tokens):
            overview = self.get_model_overview_and_presets()
            if overview["presets"]:
                d = dict(overview["presets"][0]["decision"])
                d["description"] = txt
                return d

        # Honest refusal — NEVER hijack unrecognized text with an unrelated preset!
        return None

    def parse_combo_decision_text(self, decision_text: str) -> List[Dict[str, Any]]:
        """
        Parses either a single decision OR a multi-lever combo joined by explicit
        conjunctions ('AND', 'aur', 'और', '+', ';') up to 4 simultaneous levers.
        Only activates combo mode when >= 2 clauses independently parse to valid specs.
        """
        txt = str(decision_text or "").strip()
        if not txt:
            return []
        parts = re.split(r"\s+(?:AND|and|aur|और|saath\s+mein|साथ\s+में)\s+|\s*\+\s*|\s*;\s*", txt)
        if len(parts) >= 2:
            parsed_specs: List[Dict[str, Any]] = []
            for p in parts[:4]:
                p_clean = p.strip()
                if not p_clean:
                    continue
                sp = self.parse_decision_text(p_clean)
                if sp is not None:
                    parsed_specs.append(sp)
            if len(parsed_specs) >= 2:
                return parsed_specs
        single = self.parse_decision_text(txt)
        return [single] if single is not None else []

    def _apply_lever_spec(
        self,
        df_base: pd.DataFrame,
        df_after: pd.DataFrame,
        spec: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Applies one lever mutation in-place onto `df_after` and returns masks, labels & empirical gate."""
        action_type = str(spec.get("action_type") or "").strip().lower()
        col = str(spec.get("column") or "").strip()
        if col not in df_base.columns:
            return {
                "error_response": {
                    "status": "parse_needed",
                    "message_en": f"Column '{col}' does not exist in your audited dataset.",
                    "message_hi": f"कॉलम '{col}' आपके डेटा में मौजूद नहीं है।",
                    "available_columns": list(self.all_features[:12]),
                }
            }

        scope_col = spec.get("scope_column")
        scope_val = spec.get("scope_value")
        scope_mask = pd.Series(True, index=df_base.index)
        if scope_col and scope_col in df_base.columns and scope_val not in (None, "", "All"):
            scope_mask = df_base[scope_col].fillna("Missing").astype(str) == str(scope_val)

        affected_mask = pd.Series(False, index=df_base.index)
        action_label_en = spec.get("description") or f"{action_type} on {col}"
        action_label_hi = action_label_en
        is_pause_action = False

        if action_type == "replace_category":
            from_v = str(spec.get("from_value") or "")
            to_v = str(spec.get("to_value") or "")
            if not from_v or not to_v:
                raise ValueError("replace_category requires both 'from_value' and 'to_value'.")
            if from_v == to_v:
                return {
                    "error_response": {
                        "status": "no_effect",
                        "message_en": f"Source and target values are identical ('{from_v}'). Zero net change.",
                        "message_hi": f"दोनों नाम एक ही हैं ('{from_v}') — कोई बदलाव लागू नहीं हुआ।",
                    }
                }
            affected_mask = scope_mask & (df_base[col].fillna("Missing").astype(str) == from_v)
            df_after.loc[affected_mask, col] = to_v
            action_label_en = f"Switch {col} from '{from_v}' → '{to_v}'" + (f" (in {scope_val})" if scope_val else "")
            action_label_hi = f"{col} में '{from_v}' की जगह '{to_v}' का उपयोग करें" + (f" ({scope_val} में)" if scope_val else "")

        elif action_type == "cap_numeric":
            cap_v = float(spec["value"])
            s_num = pd.to_numeric(df_base[col], errors="coerce")
            affected_mask = scope_mask & s_num.notna() & (s_num > cap_v)
            df_after.loc[affected_mask, col] = cap_v
            action_label_en = f"Cap {col} at ≤ {cap_v:g}" + (f" (in {scope_val})" if scope_val else "")
            action_label_hi = f"{col} की ऊपरी सीमा {cap_v:g} तय करें" + (f" ({scope_val} में)" if scope_val else "")

        elif action_type == "floor_numeric":
            fl_v = float(spec["value"])
            s_num = pd.to_numeric(df_base[col], errors="coerce")
            affected_mask = scope_mask & s_num.notna() & (s_num < fl_v)
            df_after.loc[affected_mask, col] = fl_v
            action_label_en = f"Raise minimum {col} to ≥ {fl_v:g}" + (f" (in {scope_val})" if scope_val else "")
            action_label_hi = f"{col} का न्यूनतम स्तर {fl_v:g} करें" + (f" ({scope_val} में)" if scope_val else "")

        elif action_type == "scale_numeric":
            if "delta_pct" in spec and spec["delta_pct"] is not None:
                delta_pct_val = float(spec["delta_pct"])
                mult = max(0.05, 1.0 + delta_pct_val / 100.0)
            else:
                mult = max(0.05, float(spec.get("multiplier", 1.0)))
                delta_pct_val = (mult - 1.0) * 100.0
            if abs(mult - 1.0) < 1e-6:
                return {
                    "error_response": {
                        "status": "no_effect",
                        "message_en": "0% change selected — zero net impact.",
                        "message_hi": "0% बदलाव चुना गया है — कोई असर नहीं होगा।",
                    }
                }
            s_num = pd.to_numeric(df_after[col], errors="coerce")
            affected_mask = scope_mask & s_num.notna()
            df_after.loc[affected_mask, col] = np.round(s_num.loc[affected_mask] * mult, 4)
            action_label_en = f"Adjust {col} by {delta_pct_val:+.1f}%" + (f" (in {scope_val})" if scope_val else "")
            action_label_hi = f"{col} में {delta_pct_val:+.1f}% बदलाव करें" + (f" ({scope_val} में)" if scope_val else "")

        elif action_type == "pause_segment":
            from_v = str(spec.get("from_value") or "")
            if not from_v:
                raise ValueError("pause_segment requires 'from_value'.")
            affected_mask = scope_mask & (df_base[col].fillna("Missing").astype(str) == from_v)
            is_pause_action = True
            action_label_en = f"Pause / Stop '{from_v}' in {col}" + (f" (in {scope_val})" if scope_val else "")
            action_label_hi = f"{col} में '{from_v}' को बंद/पॉज़ करें" + (f" ({scope_val} में)" if scope_val else "")
        else:
            raise ValueError(f"Unsupported action_type '{action_type}'.")

        is_disc = bool(
            self.is_monetary and self.discount_col and col == self.discount_col and self.mrp_col and not is_pause_action
        )
        if is_disc and affected_mask.any():
            mrp_s = pd.to_numeric(df_after.loc[affected_mask, self.mrp_col], errors="coerce").fillna(0.0)
            d_after_s = pd.to_numeric(df_after.loc[affected_mask, self.discount_col], errors="coerce").fillna(0.0).clip(0.0, 95.0)
            df_after.loc[affected_mask, self.discount_col] = d_after_s
            new_sale = mrp_s * (1.0 - d_after_s / 100.0)
            if self.cost_col and self.cost_col in df_after.columns and self.cost_col != self.mrp_col:
                df_after.loc[affected_mask, self.cost_col] = np.round(new_sale, 2)
            if self.margin_col and self.margin_col in df_after.columns and self.cogs_col and self.cogs_col in df_after.columns and not self._margin_is_post_event_ledger:
                cogs_s = pd.to_numeric(df_after.loc[affected_mask, self.cogs_col], errors="coerce").fillna(0.0)
                df_after.loc[affected_mask, self.margin_col] = np.round(new_sale - cogs_s, 2)

        emp_gate = self._compute_empirical_lever_gate(df_base, scope_mask, action_type, col, spec)
        return {
            "error_response": None,
            "action_type": action_type,
            "column": col,
            "spec": spec,
            "affected_mask": affected_mask,
            "label_en": action_label_en,
            "label_hi": action_label_hi,
            "is_pause": is_pause_action,
            "is_disc": is_disc,
            "emp_gate": emp_gate,
        }

    # -------------------------------------------------------------------------
    # PER-LEVER EMPIRICAL STATISTICAL GATE & CONFOUNDER CHECK
    # -------------------------------------------------------------------------
    def _compute_empirical_lever_gate(
        self,
        df_base: pd.DataFrame,
        scope_mask: pd.Series,
        action_type: str,
        col: str,
        spec: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Computes raw empirical p-value and raw marginal risk gap directly from physical data."""
        y_all = df_base["_dx_y_bin"].to_numpy()
        df_sc = df_base.loc[scope_mask] if scope_mask.sum() >= 30 else df_base
        y_sc = df_sc["_dx_y_bin"].to_numpy()

        p_val = 1.0
        raw_rate_diff_pct = 0.0
        note = ""

        if action_type == "replace_category":
            from_v = str(spec.get("from_value") or "")
            to_v = str(spec.get("to_value") or "")
            s_sc = df_sc[col].fillna("Missing").astype(str)
            m1 = s_sc == from_v
            m2 = s_sc == to_v
            if m2.sum() < 5:
                # Fall back to full dataset for peer baseline if scoped peer count is tiny
                s_full = df_base[col].fillna("Missing").astype(str)
                m1 = s_full == from_v
                m2 = s_full == to_v
                y_use = y_all
            else:
                y_use = y_sc
            if m1.sum() >= 5 and m2.sum() >= 5:
                r1 = float(y_use[m1].mean())
                r2 = float(y_use[m2].mean())
                p_val = _two_prop_p_value(int(y_use[m1].sum()), int(m1.sum()), int(y_use[m2].sum()), int(m2.sum()))
                raw_rate_diff_pct = (r1 - r2) * 100.0
                note = f"raw {r1*100:.1f}% vs {r2*100:.1f}%"

        elif action_type in ("cap_numeric", "floor_numeric"):
            thresh = float(spec["value"])
            s_num = pd.to_numeric(df_sc[col], errors="coerce")
            m_aff = (s_num > thresh) if action_type == "cap_numeric" else (s_num < thresh)
            m_ref = (s_num <= thresh) if action_type == "cap_numeric" else (s_num >= thresh)
            if m_aff.sum() >= 5 and m_ref.sum() >= 5:
                r1 = float(y_sc[m_aff].mean())
                r2 = float(y_sc[m_ref].mean())
                p_val = _two_prop_p_value(int(y_sc[m_aff].sum()), int(m_aff.sum()), int(y_sc[m_ref].sum()), int(m_ref.sum()))
                raw_rate_diff_pct = (r1 - r2) * 100.0
                note = f"raw affected {r1*100:.1f}% vs target band {r2*100:.1f}%"

        elif action_type == "scale_numeric":
            s_num = pd.to_numeric(df_sc[col], errors="coerce")
            valid = s_num.notna()
            if valid.sum() >= 20 and s_num[valid].nunique() >= 2:
                rho, sp_p = scipy_stats.spearmanr(s_num[valid], y_sc[valid])
                if np.isfinite(sp_p):
                    p_val = float(sp_p)
                raw_rate_diff_pct = float(rho * 20.0) if np.isfinite(rho) else 0.0

        elif action_type == "pause_segment":
            from_v = str(spec.get("from_value") or "")
            s_sc = df_sc[col].fillna("Missing").astype(str)
            m1 = s_sc == from_v
            m2 = ~m1
            if m1.sum() >= 5 and m2.sum() >= 5:
                r1 = float(y_sc[m1].mean())
                r2 = float(y_sc[m2].mean())
                p_val = _two_prop_p_value(int(y_sc[m1].sum()), int(m1.sum()), int(y_sc[m2].sum()), int(m2.sum()))
                raw_rate_diff_pct = (r1 - r2) * 100.0

        return {
            "empirical_p_value": round(p_val, 5),
            "raw_rate_diff_pct": round(raw_rate_diff_pct, 2),
            "col_auc_drop": round(float(self.feature_auc_drop_map.get(col, 0.0)), 4),
            "note": note,
        }

    def _compute_causal_support(
        self,
        df_base: pd.DataFrame,
        df_after: pd.DataFrame,
        applied_levers: List[Dict[str, Any]],
        affected_mask: pd.Series,
    ) -> Dict[str, Any]:
        """
        Causal Positivity / Common-Support Overlap Guard:
        Checks whether the simulated counterfactual actually has historical precedent
        in the same confounder strata (defeating blind ML extrapolation!).
        """
        n_aff = int(affected_mask.sum())
        if n_aff <= 0 or not applied_levers:
            return {"causal_support_pct": 100.0, "extrapolation_warning": False, "note_en": "", "note_hi": ""}

        # Identify strongest external confounder column for stratified overlap verification
        lev_cols = {lv["column"] for lv in applied_levers}
        conf_col = None
        for f in self.feature_importances:
            fc = f["feature"]
            if fc not in lev_cols and fc in df_base.columns:
                conf_col = fc
                break

        support_scores: List[float] = []
        for lv in applied_levers:
            act = lv["action_type"]
            col = lv["column"]
            sp = lv["spec"]
            if act == "pause_segment":
                support_scores.append(100.0)
                continue
            if act == "replace_category":
                to_v = str(sp.get("to_value") or "")
                s_col = df_base[col].fillna("Missing").astype(str)
                peer_mask = s_col == to_v
                if int(peer_mask.sum()) < 5:
                    support_scores.append(5.0)
                    continue
                if conf_col and conf_col in df_base.columns:
                    if pd.api.types.is_numeric_dtype(df_base[conf_col]):
                        try:
                            strata = pd.qcut(pd.to_numeric(df_base[conf_col], errors="coerce"), q=4, duplicates="drop").astype(str)
                        except Exception:
                            strata = pd.Series("ALL", index=df_base.index)
                    else:
                        strata = df_base[conf_col].fillna("Missing").astype(str)
                    peer_counts = strata.loc[peer_mask].value_counts()
                    supported_strata = set(peer_counts[peer_counts >= 5].index)
                    aff_strata = strata.loc[lv["affected_mask"]]
                    sup_pct = float(aff_strata.isin(supported_strata).mean() * 100.0) if len(aff_strata) else 100.0
                    support_scores.append(sup_pct)
                else:
                    support_scores.append(100.0)
            elif act in ("cap_numeric", "floor_numeric", "scale_numeric"):
                s_orig = pd.to_numeric(df_base[col], errors="coerce").dropna()
                s_new = pd.to_numeric(df_after.loc[lv["affected_mask"], col], errors="coerce").dropna()
                if len(s_orig) >= 20 and len(s_new) > 0:
                    p01 = float(s_orig.quantile(0.01))
                    p99 = float(s_orig.quantile(0.99))
                    in_range = float(((s_new >= p01) & (s_new <= p99)).mean() * 100.0)
                    support_scores.append(in_range)
                else:
                    support_scores.append(100.0)

        min_sup = round(min(support_scores), 1) if support_scores else 100.0
        extrap = bool(min_sup < 35.0)
        note_en = (
            f"Thin Historical Match / Extrapolation Risk (Only {min_sup:.0f}% common support): "
            f"Very few similar records in your history ever operated at this target setting — widen your safety margin and run a small 10–20% pilot first."
            if extrap else ""
        )
        note_hi = (
            f"कम ऐतिहासिक मिलान (सिर्फ़ {min_sup:.0f}% Common Support): आपके पुराने डेटा में इस तरह के बहुत कम रिकॉर्ड इस नई सेटिंग पर चले हैं — इसलिए पहले 10–20% छोटे पायलट से शुरुआत करें।"
            if extrap else ""
        )
        return {
            "causal_support_pct": min_sup,
            "extrapolation_warning": extrap,
            "note_en": note_en,
            "note_hi": note_hi,
        }

    # -------------------------------------------------------------------------
    # COUNTERFACTUAL ML + EPISTEMIC + ELASTICITY MONTE CARLO SIMULATOR
    # -------------------------------------------------------------------------
    def simulate_decision(
        self,
        decision: Optional[Dict[str, Any]] = None,
        decision_text: Optional[str] = None,
        decisions: Optional[List[Dict[str, Any]]] = None,
        implementation_cost: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Simulates a single client decision OR a multi-lever combo (`decisions=[...]`, up to 4
        simultaneous levers) with ZERO double-counting on overlapping rows, using 3-fold
        cross-fitted ensemble predictions + 500-iteration Bootstrap/Epistemic/Elasticity Monte Carlo.
        """
        if not self.fold_models:
            raise ValueError("Predictive model could not be trained on this dataset (insufficient target variance).")

        specs: List[Dict[str, Any]] = []
        if decisions and len(decisions) > 0:
            specs = [dict(d) for d in decisions[:4]]
        elif decision:
            specs = [dict(decision)]
        else:
            specs = self.parse_combo_decision_text(str(decision_text or ""))
            if not specs:
                sample_cols = ", ".join((self.categorical_features[:4] + self.numeric_features[:3]))
                return {
                    "status": "parse_needed",
                    "message_en": (
                        f"Could not find a matching column or business segment in your data for '{str(decision_text or '').strip()}'. "
                        f"We never guess or force unrelated predictions. Available columns include: {sample_cols}."
                    ),
                    "message_hi": (
                        f"'{str(decision_text or '').strip()}' आपके अपलोड डेटा के किसी कॉलम या ग्रुप से मेल नहीं खाया। "
                        f"हम ज़बरदस्ती का अनुमान नहीं बनाते — कृपया ऊपर 1-क्लिक कार्ड चुनें या इन कॉलम का नाम लिखें: {sample_cols}।"
                    ),
                    "available_columns": list(self.all_features[:12]),
                }

        df_base = self.df_full if len(self.df_full) <= MAX_SIM_ROWS else self.df_full.sample(n=MAX_SIM_ROWS, random_state=42)
        df_base = df_base.copy()
        scale_factor = float(len(self.df_full)) / float(max(len(df_base), 1))

        # Apply all levers sequentially onto ONE unified counterfactual `df_after` (ZERO double-counting!)
        df_after = df_base.copy()
        applied_levers: List[Dict[str, Any]] = []
        union_affected_mask = pd.Series(False, index=df_base.index)
        union_pause_mask = pd.Series(False, index=df_base.index)
        union_disc_mask = pd.Series(False, index=df_base.index)
        sum_individual_aff = 0

        for sp in specs:
            ap = self._apply_lever_spec(df_base, df_after, sp)
            if ap.get("error_response") is not None:
                return ap["error_response"]
            applied_levers.append(ap)
            m_aff = ap["affected_mask"]
            sum_individual_aff += int(m_aff.sum())
            union_affected_mask = union_affected_mask | m_aff
            if ap["is_pause"]:
                union_pause_mask = union_pause_mask | m_aff
            if ap["is_disc"]:
                union_disc_mask = union_disc_mask | m_aff

        is_combo = len(applied_levers) > 1
        primary_lever = applied_levers[0]
        spec = primary_lever["spec"]
        action_type = primary_lever["action_type"]
        col = primary_lever["column"]
        affected_cols_set = {lv["column"] for lv in applied_levers}

        if is_combo:
            action_label_en = " + ".join(lv["label_en"] for lv in applied_levers)
            action_label_hi = " + ".join(lv["label_hi"] for lv in applied_levers)
        else:
            action_label_en = primary_lever["label_en"]
            action_label_hi = primary_lever["label_hi"]

        affected_mask = union_affected_mask
        n_aff = int(affected_mask.sum())
        overlap_raw = max(0, sum_individual_aff - n_aff)
        overlap_deduped = int(round(overlap_raw * scale_factor))

        if n_aff == 0:
            return {
                "status": "no_effect",
                "message_en": f"0 records match this condition ({action_label_en}). Adjust your limit or pick an existing group.",
                "message_hi": f"इस शर्त ({action_label_hi}) से 0 रिकॉर्ड प्रभावित हुए — कृपया सीमा या ग्रुप बदलें।",
            }

        is_pause_action = bool(union_pause_mask.any())
        is_all_pause = bool(is_pause_action and (union_pause_mask.loc[affected_mask].all()))
        is_discount_pricing_change = bool(union_disc_mask.any())

        # Aggregate empirical gates across all levers in the simulation
        emp_gate = primary_lever["emp_gate"]
        if is_combo:
            best_p = min(lv["emp_gate"]["empirical_p_value"] for lv in applied_levers)
            best_auc_drop = max(lv["emp_gate"]["col_auc_drop"] for lv in applied_levers)
            max_abs_raw = max((lv["emp_gate"]["raw_rate_diff_pct"] for lv in applied_levers), key=lambda x: abs(x))
            emp_gate = {
                "empirical_p_value": best_p,
                "raw_rate_diff_pct": max_abs_raw,
                "col_auc_drop": best_auc_drop,
                "note": f"combo of {len(applied_levers)} levers",
            }

        # Predict probabilities across ALL 3 cross-fitted fold models (gives real epistemic uncertainty!)
        df_aff_before = df_base.loc[affected_mask]
        df_aff_after = df_after.loc[affected_mask]
        pause_mask_aff = union_pause_mask.loc[affected_mask].to_numpy(dtype=bool)
        disc_mask_aff = union_disc_mask.loc[affected_mask].to_numpy(dtype=bool) & (~pause_mask_aff)

        X_before = self._prepare_feature_matrix(df_aff_before)
        p_before_folds = np.vstack([
            np.clip(m.predict_proba(X_before)[:, 1], 0.001, 0.999) for m in self.fold_models
        ])
        if is_all_pause:
            p_after_folds = np.zeros_like(p_before_folds)
        else:
            X_after = self._prepare_feature_matrix(df_aff_after)
            p_after_folds = np.vstack([
                np.clip(m.predict_proba(X_after)[:, 1], 0.001, 0.999) for m in self.fold_models
            ])
            if is_pause_action:
                p_after_folds[:, pause_mask_aff] = 0.0

        p_before = p_before_folds.mean(axis=0)
        p_after = p_after_folds.mean(axis=0)

        # Real fold-to-fold epistemic disagreement on the average risk delta!
        fold_mean_deltas = (p_before_folds - p_after_folds).mean(axis=1)
        epistemic_rate_sd = float(np.std(fold_mean_deltas, ddof=1)) if len(fold_mean_deltas) >= 2 else 0.01

        # Financial exposure & empirical unit economics per affected record
        if self.is_monetary and self.cost_col:
            exposure_arr = np.maximum(0.0, pd.to_numeric(df_aff_before[self.cost_col], errors="coerce").fillna(0.0).to_numpy())
        else:
            exposure_arr = np.ones(n_aff, dtype=float)

        margin_arr: Optional[np.ndarray] = None
        if self.is_monetary and self.margin_col and self.margin_col in df_aff_before.columns:
            margin_arr = pd.to_numeric(df_aff_before[self.margin_col], errors="coerce").fillna(0.0).to_numpy()

        cogs_arr: Optional[np.ndarray] = None
        if self.is_monetary and self.cogs_col and self.cogs_col in df_aff_before.columns:
            cogs_arr = np.maximum(0.0, pd.to_numeric(df_aff_before[self.cogs_col], errors="coerce").fillna(0.0).to_numpy())

        # Per-row CFO-grade accounting (supports pure single, pure pause, OR mixed combo cleanly!)
        averted_prob_delta = p_before - p_after
        saved_loss_arr = averted_prob_delta * exposure_arr
        collateral_cost_arr = np.zeros(n_aff, dtype=float)
        healthy_records_sacrificed = 0
        pause_damage_mid = 0.55

        if is_pause_action:
            pm = pause_mask_aff
            healthy_records_sacrificed = int(round((1.0 - p_before[pm]).sum() * scale_factor))
            if self.is_monetary:
                if self._margin_is_post_event_ledger and margin_arr is not None:
                    m_full = pd.to_numeric(self.df_full[self.margin_col], errors="coerce").fillna(0.0)
                    y_full = self.df_full["_dx_y_bin"].to_numpy()
                    pos_unit = max(1.0, float(m_full[y_full == 0].mean())) if (y_full == 0).any() else float(exposure_arr.mean() * 0.25)
                    neg_unit = max(1.0, abs(float(m_full[y_full == 1].mean()))) if (y_full == 1).any() else float(exposure_arr.mean() * 0.50)
                    saved_loss_arr[pm] = p_before[pm] * neg_unit
                    collateral_cost_arr[pm] = (1.0 - p_before[pm]) * pos_unit
                elif margin_arr is not None and cogs_arr is not None:
                    saved_loss_arr[pm] = p_before[pm] * (cogs_arr[pm] * pause_damage_mid)
                    collateral_cost_arr[pm] = (1.0 - p_before[pm]) * np.maximum(0.0, margin_arr[pm])
                elif margin_arr is not None:
                    saved_loss_arr[pm] = p_before[pm] * (exposure_arr[pm] * 0.50)
                    collateral_cost_arr[pm] = (1.0 - p_before[pm]) * np.maximum(0.0, margin_arr[pm])
                else:
                    saved_loss_arr[pm] = p_before[pm] * exposure_arr[pm]
                    collateral_cost_arr[pm] = (1.0 - p_before[pm]) * exposure_arr[pm]
            else:
                saved_loss_arr[pm] = p_before[pm]
                collateral_cost_arr[pm] = 1.0 - p_before[pm]

        # Direct discount pricing economics ONLY on `disc_mask_aff` rows!
        direct_margin_delta = np.zeros(n_aff, dtype=float)
        margin_note_en = ""
        margin_note_hi = ""
        mrp_arr = np.zeros(n_aff, dtype=float)
        d_before_arr = np.zeros(n_aff, dtype=float)
        d_after_arr = np.zeros(n_aff, dtype=float)
        unit_margin_est = np.zeros(n_aff, dtype=float)

        if is_discount_pricing_change and disc_mask_aff.any():
            mrp_arr = np.maximum(0.0, pd.to_numeric(df_aff_before[self.mrp_col], errors="coerce").fillna(0.0).to_numpy())
            d_before_arr = pd.to_numeric(df_aff_before[self.discount_col], errors="coerce").fillna(0.0).to_numpy()
            d_after_arr = pd.to_numeric(df_aff_after[self.discount_col], errors="coerce").fillna(0.0).to_numpy()
            if margin_arr is not None and not self._margin_is_post_event_ledger:
                unit_margin_est = np.maximum(0.0, margin_arr)
            else:
                unit_margin_est = exposure_arr * 0.25

            dm = disc_mask_aff
            price_rel_chg = (d_before_arr[dm] - d_after_arr[dm]) / np.maximum(15.0, 100.0 - d_before_arr[dm])
            walkaway_mid = np.where(price_rel_chg > 0, np.clip(1.15 * price_rel_chg, 0.0, 0.60), 0.0)
            healthy_p = 1.0 - p_after[dm]
            gain_surviving = mrp_arr[dm] * ((d_before_arr[dm] - d_after_arr[dm]) / 100.0) * healthy_p * (1.0 - walkaway_mid)
            lost_walkaway_margin = unit_margin_est[dm] * healthy_p * walkaway_mid
            direct_margin_delta[dm] = gain_surviving - lost_walkaway_margin
            margin_note_en = "Net of stochastic customer walk-away elasticity (0.6x–2.0x price sensitivity tested in Monte Carlo)."
            margin_note_hi = "इसमें ग्राहक छूटने के रिस्क (0.6x–2.0x प्राइस इलास्टिसिटी) को काटकर ईमानदार शुद्ध मार्जिन गिना गया है।"

        net_delta_arr = saved_loss_arr + direct_margin_delta - collateral_cost_arr

        # Causal Positivity / Historical Overlap Support Check (defeats blind ML extrapolation!)
        causal_sup = self._compute_causal_support(df_base, df_after, applied_levers, affected_mask)
        causal_support_pct = float(causal_sup["causal_support_pct"])
        extrapolation_warning = bool(causal_sup["extrapolation_warning"])

        # 500-Iteration Bootstrap + Fold-Epistemic + Elasticity + Extrapolation Monte Carlo Simulation!
        rng = np.random.default_rng(2026)
        brier_v = float(self.model_metrics.get("brier_score", 0.15))
        epistemic_sd_eff = max(epistemic_rate_sd, 0.005 * math.sqrt(max(0.05, brier_v) / 0.15))
        if extrapolation_warning:
            # Honestly widen epistemic spread when historical support is thin
            epistemic_sd_eff *= (1.0 + (35.0 - causal_support_pct) / 40.0)
        boot_totals = np.empty(BOOTSTRAP_ITERS, dtype=float)
        n_folds = len(self.fold_models)
        has_retail_pause_cogs = bool(
            is_pause_action and self.is_monetary and margin_arr is not None and cogs_arr is not None and not self._margin_is_post_event_ledger
        )

        for b in range(BOOTSTRAP_ITERS):
            idx = rng.integers(0, n_aff, size=n_aff)
            fk = b % n_folds
            pb_f = p_before_folds[fk][idx]
            pa_f = p_after_folds[fk][idx]
            ep_shift = rng.normal(0.0, epistemic_sd_eff)
            delta_p_b = (pb_f - pa_f) + ep_shift

            row_net_b = delta_p_b * exposure_arr[idx]

            if is_pause_action:
                pm_b = pause_mask_aff[idx]
                if pm_b.any():
                    if has_retail_pause_cogs:
                        dmg_b = rng.uniform(0.35, 0.75)
                        p_p = np.clip(pb_f[pm_b] + ep_shift, 0.0, 1.0)
                        row_net_b[pm_b] = p_p * (cogs_arr[idx[pm_b]] * dmg_b) - (1.0 - p_p) * np.maximum(0.0, margin_arr[idx[pm_b]])
                    else:
                        row_net_b[pm_b] = net_delta_arr[idx[pm_b]] + ep_shift * exposure_arr[idx[pm_b]]

            if is_discount_pricing_change:
                dm_b = disc_mask_aff[idx]
                if dm_b.any():
                    e_b = rng.uniform(0.6, 2.0)
                    di = idx[dm_b]
                    pr_chg = (d_before_arr[di] - d_after_arr[di]) / np.maximum(15.0, 100.0 - d_before_arr[di])
                    wa_b = np.where(pr_chg > 0, np.clip(e_b * pr_chg, 0.0, 0.65), 0.0)
                    hp_b = 1.0 - pa_f[dm_b]
                    dm_gain = (
                        mrp_arr[di] * ((d_before_arr[di] - d_after_arr[di]) / 100.0) * hp_b * (1.0 - wa_b)
                        - unit_margin_est[di] * hp_b * wa_b
                    )
                    row_net_b[dm_b] = row_net_b[dm_b] + dm_gain

            boot_totals[b] = float(row_net_b.sum()) * scale_factor

        # Optional one-time / rollout implementation cost subtracted across EVERY Monte Carlo draw!
        impl_cost = 0.0
        if self.is_monetary and implementation_cost is not None:
            try:
                impl_cost = max(0.0, float(implementation_cost))
            except (TypeError, ValueError):
                impl_cost = 0.0
        if impl_cost > 0.0:
            boot_totals = boot_totals - impl_cost

        expected_gross_net = float(net_delta_arr.sum() * scale_factor)
        expected_net = expected_gross_net - impl_cost
        expected_saved_loss = float(saved_loss_arr.sum() * scale_factor)
        expected_margin_delta = float(direct_margin_delta.sum() * scale_factor)
        expected_collateral_loss = float(collateral_cost_arr.sum() * scale_factor)
        expected_ev_averted = float(averted_prob_delta.sum() * scale_factor)
        roi_multiple = round(expected_gross_net / impl_cost, 2) if impl_cost > 0.0 else None

        # Exact 95% Confidence Interval (2.5th to 97.5th percentiles!)
        ci_low = float(np.percentile(boot_totals, 2.5))
        ci_high = float(np.percentile(boot_totals, 97.5))

        before_rate_pct = round(float(p_before.mean() * 100.0), 2)
        after_rate_pct = round(float(p_after.mean() * 100.0), 2)
        ml_rate_diff_pct = round(before_rate_pct - after_rate_pct, 2)

        # ---------------------------------------------------------------------
        # STAGE 8 PER-LEVER STATISTICAL NOISE CIRCUIT-BREAKER (ANTI-FORCING!)
        # ---------------------------------------------------------------------
        noise_circuit_breaker = False
        if (
            not is_pause_action
            and not is_discount_pricing_change
            and emp_gate["empirical_p_value"] >= 0.05
            and emp_gate["col_auc_drop"] < 0.003
            and abs(ml_rate_diff_pct) < 2.0
        ):
            noise_circuit_breaker = True

        # Simpson's Paradox / Confounder Divergence Check
        raw_diff = float(emp_gate["raw_rate_diff_pct"])
        confounder_alert = False
        if not is_pause_action and abs(raw_diff) >= 8.0:
            if is_combo:
                # In multi-lever combos, union averaging naturally blends slice deltas; only flag true confounder collapse
                if abs(ml_rate_diff_pct) < 3.0 and not is_discount_pricing_change:
                    confounder_alert = True
            elif (
                abs(ml_rate_diff_pct) <= abs(raw_diff) * 0.45
                or (raw_diff * ml_rate_diff_pct < 0 and abs(ml_rate_diff_pct) >= 1.5)
            ):
                confounder_alert = True

        raw_benefit_prob = float((boot_totals > 0.0).mean() * 100.0)
        auc_v = float(self.model_metrics.get("roc_auc", 0.65))
        max_honest_conf = min(95.0, max(60.0, 55.0 + (auc_v - 0.50) * 165.0))

        if noise_circuit_breaker:
            # Never force certainty on statistically indistinguishable noise!
            benefit_prob_pct = round(50.0 + float(np.clip((raw_benefit_prob - 50.0) * 0.14, -7.0, 7.0)), 1)
            loss_risk_pct = round(100.0 - benefit_prob_pct, 1)
            verdict_code = "NEUTRAL"
            verdict_en = "NO PROVEN SIGNAL (NOISE GUARD) — Do Not Spend Budget Here"
            verdict_hi = "🟠 कोई पक्का सबूत नहीं (Noise Guard) — इस बदलाव पर पैसा या मेहनत खर्च न करें"
        else:
            if raw_benefit_prob >= 50.0:
                benefit_prob_pct = round(min(max_honest_conf, raw_benefit_prob), 1)
            else:
                benefit_prob_pct = round(max(100.0 - max_honest_conf, raw_benefit_prob), 1)
            loss_risk_pct = round(100.0 - benefit_prob_pct, 1)

            if expected_net > 0 and benefit_prob_pct >= 80.0 and ci_low > 0:
                verdict_code = "STRONG_GO"
                verdict_en = "STRONG GO — High Probability of Profit / Risk Reduction"
                verdict_hi = "🟢 मज़बूत फ़ैसला (Strong Go) — फ़ायदा होने की बहुत ऊँची संभावना"
            elif expected_net > 0 and benefit_prob_pct >= 58.0:
                verdict_code = "PILOT_FIRST"
                verdict_en = "PILOT FIRST — Promising Gain, Test on 1–2 Stores / 20% Traffic First"
                verdict_hi = "🟡 पहले छोटा पायलट करें — फ़ायदा संभव है, पर रिस्क जाँचने को 1–2 स्टोर में टेस्ट करें"
            elif expected_net < 0 and (benefit_prob_pct <= 30.0 or ci_high < 0):
                verdict_code = "LIKELY_LOSS"
                verdict_en = "DO NOT EXECUTE AS-IS — High Risk of Net Loss / Backfire"
                verdict_hi = "🔴 सावधान (Likely Loss) — इस फ़ैसले से फ़ायदे से ज़्यादा नुकसान का ख़तरा है"
            else:
                verdict_code = "NEUTRAL"
                verdict_en = "NEUTRAL / UNCERTAIN — 95% Range Straddles Zero (No Clear Net Gain)"
                verdict_hi = "🟠 लगभग बराबर / अनिश्चित (Neutral) — 95% रेंज ज़ीरो के आर-पार है, पक्का फ़ायदा साबित नहीं"

        # ---------------------------------------------------------------------
        # PER-COHORT WINNERS & NON-BENEFICIARIES (FIXED FOR MARGIN-DRIVEN GAINS)
        # ---------------------------------------------------------------------
        breakdown_col = None
        for cand in [f["feature"] for f in self.feature_importances if f["type"] == "categorical"] + self.categorical_features:
            if cand not in affected_cols_set and cand in df_aff_before.columns and df_aff_before[cand].nunique() >= 2:
                breakdown_col = cand
                break

        winners: List[Dict[str, Any]] = []
        no_benefit_zones: List[Dict[str, Any]] = []
        if breakdown_col and not noise_circuit_breaker:
            tmp_b = pd.DataFrame({
                "seg": df_aff_before[breakdown_col].fillna("Missing").astype(str).to_numpy(),
                "p_before": p_before,
                "p_after": p_after,
                "net_delta": net_delta_arr,
                "margin_delta": direct_margin_delta,
                "exposure": exposure_arr,
            })
            for seg_name, grp in tmp_b.groupby("seg"):
                if len(grp) < 3:
                    continue
                seg_net = float(grp["net_delta"].sum() * scale_factor)
                seg_margin = float(grp["margin_delta"].sum() * scale_factor)
                seg_rec = int(round(len(grp) * scale_factor))
                r_b = float(grp["p_before"].mean() * 100.0)
                r_a = float(grp["p_after"].mean() * 100.0)
                entry = {
                    "dimension": breakdown_col,
                    "segment": str(seg_name),
                    "affected_records": seg_rec,
                    "rate_before_pct": round(r_b, 2),
                    "rate_after_pct": round(r_a, 2),
                    "net_impact": round(seg_net, 2),
                    "formatted_impact": _fmt_money(seg_net, self.unit_sym, self.is_monetary),
                }
                # Fix #8: Count profitable discount-margin cohorts as winners too!
                if seg_net > 0 and ((r_b - r_a) > 0.5 or seg_margin > 0):
                    winners.append(entry)
                else:
                    no_benefit_zones.append(entry)
            winners.sort(key=lambda x: x["net_impact"], reverse=True)
            no_benefit_zones.sort(key=lambda x: x["net_impact"])

        # ---------------------------------------------------------------------
        # EXPLICIT "WHY LOSS COULD HAPPEN" (HONEST DOWNSIDE RISK ENGINE)
        # ---------------------------------------------------------------------
        downside_reasons_en: List[str] = []
        downside_reasons_hi: List[str] = []

        if noise_circuit_breaker:
            downside_reasons_en.append(
                f"No Proven Statistical Signal (p = {emp_gate['empirical_p_value']:.3f}, Out-of-Sample Lift = {emp_gate['col_auc_drop']:.4f}): "
                f"Historical data shows no reliable impact from changing '{col}'. Any tiny ML movement is random noise — do NOT waste budget here."
            )
            downside_reasons_hi.append(
                f"डेटा में कोई पक्का सबूत नहीं (p = {emp_gate['empirical_p_value']:.3f}): पुराने रिकॉर्ड्स में '{col}' बदलने से कोई पक्का फ़र्क़ साबित नहीं होता। छोटा बदलाव सिर्फ़ रैंडम शोर है — इस पर बजट खर्च न करें।"
            )

        if expected_net <= 0 and not noise_circuit_breaker and verdict_code == "LIKELY_LOSS":
            downside_reasons_en.append(
                f"Negative Empirical Signal: Historical data shows this change harms net performance ({before_rate_pct:.1f}% → {after_rate_pct:.1f}% risk / collateral cost), "
                f"resulting in an estimated net loss of {_fmt_money(expected_net, self.unit_sym, self.is_monetary)}."
            )
            downside_reasons_hi.append(
                f"डेटा के हिसाब से सीधा घाटा: पुराने रिकॉर्ड्स दिखाते हैं कि इस बदलाव से कुल असर नकारात्मक है "
                f"(अनुमानित शुद्ध घाटा: {_fmt_money(expected_net, self.unit_sym, self.is_monetary)})।"
            )

        if confounder_alert:
            downside_reasons_en.append(
                f"Confounder / Simpson's Paradox Warning: Raw averages suggest a {raw_diff:+.1f} pp gap, "
                f"but once other business drivers are controlled by ML, the isolated effect of changing '{col}' alone is only {ml_rate_diff_pct:+.1f} pp. "
                "Fix the true root-cause driver instead of chasing surface correlation."
            )
            downside_reasons_hi.append(
                f"छुपे हुए कारण (Confounder) की चेतावनी: सीधे औसत में {raw_diff:+.1f}% फ़र्क़ दिखता है, "
                f"लेकिन बाकी कारणों को अलग करने पर '{col}' का असली असर सिर्फ़ {ml_rate_diff_pct:+.1f}% है — असली जड़ (root cause) पर काम करें।"
            )

        if expected_net <= 0 and not noise_circuit_breaker and verdict_code != "LIKELY_LOSS":
            downside_reasons_en.append(
                f"Marginal / Uncertain Net Effect: Estimated net impact ({_fmt_money(expected_net, self.unit_sym, self.is_monetary)}) is statistically indistinguishable from zero (95% CI straddles 0)."
            )
            downside_reasons_hi.append(
                f"अनिश्चित असर: अनुमानित असर ({_fmt_money(expected_net, self.unit_sym, self.is_monetary)}) ज़ीरो के बहुत करीब है — बड़ा फ़ायदा साबित नहीं होता।"
            )

        if is_pause_action and healthy_records_sacrificed > 0:
            downside_reasons_en.append(
                f"Collateral Volume Loss: Stopping '{spec.get('from_value')}' also cuts ~{healthy_records_sacrificed:,} healthy/profitable transactions "
                f"(estimated sacrificed profit/volume: {_fmt_money(expected_collateral_loss, self.unit_sym, self.is_monetary)})."
            )
            downside_reasons_hi.append(
                f"अच्छे ऑर्डर छूटने का नुकसान: '{spec.get('from_value')}' बंद करने से लगभग {healthy_records_sacrificed:,} सही/मुनाफ़े वाले ऑर्डर भी चले जाएंगे "
                f"(छूटा हुआ मार्जिन/वॉल्यूम: {_fmt_money(expected_collateral_loss, self.unit_sym, self.is_monetary)})।"
            )

        if is_discount_pricing_change and action_type == "cap_numeric":
            downside_reasons_en.append(
                "Price-Sensitive Walk-Away Risk: Cutting steep discounts can cause bargain-hunting shoppers to abandon checkout (tested across 0.6x–2.0x elasticity in Monte Carlo) — pilot on 1–2 stores first."
            )
            downside_reasons_hi.append(
                "ग्राहक छूटने का ख़तरा: ज़्यादा डिस्काउंट घटाने पर प्राइस-सेंसिटिव ग्राहक बिना खरीदे जा सकते हैं (0.6x–2.0x इलास्टिसिटी पर टेस्ट किया गया) — पहले 1–2 स्टोर में पायलट करें।"
            )

        if action_type == "replace_category" and expected_net > 0 and not noise_circuit_breaker:
            downside_reasons_en.append(
                f"Capacity & Transition Risk: Shifting {int(round(n_aff * scale_factor)):,} records onto '{spec.get('to_value')}' could strain supply capacity or unit cost if done overnight instead of phased 25% → 60% → 100%."
            )
            downside_reasons_hi.append(
                f"सप्लाई व कैपेसिटी का ख़तरा: अचानक {int(round(n_aff * scale_factor)):,} ऑर्डर '{spec.get('to_value')}' पर शिफ्ट करने से स्टॉक की कमी या लागत बढ़ सकती है — पहले 25% पायलट से शुरू करें।"
            )

        if extrapolation_warning and causal_sup.get("note_en"):
            downside_reasons_en.append(causal_sup["note_en"])
            downside_reasons_hi.append(causal_sup["note_hi"])

        if self.model_metrics.get("temporal_drift_detected"):
            oot_a = self.model_metrics.get("temporal_backtest_auc")
            downside_reasons_en.append(
                f"Time-Shift Concept Drift Warning: Recent-period walk-forward accuracy dropped to ROC-AUC {oot_a:.2f} (vs {auc_v:.2f} overall) — business behavior is evolving over time, so re-verify after 2–4 weeks."
            )
            downside_reasons_hi.append(
                f"समय के साथ पैटर्न बदलने की चेतावनी: हाल के महीनों का बैकटेस्ट AUC {oot_a:.2f} रहा (कुल {auc_v:.2f} की तुलना में) — मार्केट ट्रेंड बदल रहा है, इसलिए 2–4 हफ़्ते बाद दोबारा जाँचें।"
            )

        if auc_v < 0.65:
            downside_reasons_en.append(
                f"Moderate/Low Historical Predictability (ROC-AUC = {auc_v:.2f}): Unmeasured external factors (seasonality, competitor pricing, local events) drive much of the outcome."
            )
            downside_reasons_hi.append(
                f"बाहरी कारणों का असर (Model AUC = {auc_v:.2f}): सीज़न, कॉम्पिटिटर के दाम या लोकल कारण इस डेटा में दर्ज नहीं हैं — इसलिए छोटा ट्रायल ज़रूरी है।"
            )

        if int(round(n_aff * scale_factor)) < 40:
            downside_reasons_en.append(
                f"Small Sample Size ({int(round(n_aff * scale_factor))} affected rows): Wide statistical uncertainty bounds — verify on fresh records."
            )
            downside_reasons_hi.append(
                f"कम डेटा सैंपल (सिर्फ़ {int(round(n_aff * scale_factor))} रिकॉर्ड): कम सैंपल होने से रिज़ल्ट में उतार-चढ़ाव संभव है।"
            )

        if impl_cost > 0.0 and expected_net <= 0.0 and expected_gross_net > 0.0 and not noise_circuit_breaker:
            downside_reasons_en.insert(
                0,
                f"Rollout Cost Exceeds Expected Gain: Projected operational benefit ({_fmt_money(expected_gross_net, self.unit_sym, self.is_monetary)}) "
                f"does not recover your {_fmt_money(impl_cost, self.unit_sym, self.is_monetary)} rollout budget (Net: {_fmt_money(expected_net, self.unit_sym, self.is_monetary)})."
            )
            downside_reasons_hi.insert(
                0,
                f"लागू करने का खर्च फ़ायदे से ज़्यादा है: संभावित बचत ({_fmt_money(expected_gross_net, self.unit_sym, self.is_monetary)}) "
                f"आपके {_fmt_money(impl_cost, self.unit_sym, self.is_monetary)} रोलआउट बजट को कवर नहीं करती (शुद्ध असर: {_fmt_money(expected_net, self.unit_sym, self.is_monetary)})।"
            )

        # ---------------------------------------------------------------------
        # 4-PILLAR SIMULATION CONFIDENCE SCORE (0-100, TRANSPARENT & UNFORCED)
        # ---------------------------------------------------------------------
        aff_scaled = int(round(n_aff * scale_factor))
        pillar_model = round(min(30.0, max(0.0, ((auc_v - 0.50) / 0.35) * 30.0)), 1)
        pillar_sample = round(min(25.0, max(0.0, (math.log10(max(1, aff_scaled)) / math.log10(500.0)) * 25.0)), 1)
        ci_straddles_zero = (ci_low <= 0.0 <= ci_high)
        stab_raw = 25.0 - min(15.0, epistemic_rate_sd * 200.0) - (8.0 if ci_straddles_zero else 0.0)
        pillar_stability = round(max(2.0, stab_raw), 1)

        emp_p = float(emp_gate["empirical_p_value"])
        if noise_circuit_breaker:
            pillar_signal = 2.0
        else:
            sig_base = 20.0 if emp_p < 0.001 else (17.0 if emp_p < 0.01 else (13.0 if emp_p < 0.05 else 5.0))
            if confounder_alert:
                sig_base = max(3.0, sig_base - 9.0)
            if extrapolation_warning:
                sig_base = max(3.0, sig_base - 6.0)
            if self.model_metrics.get("temporal_drift_detected"):
                sig_base = max(3.0, sig_base - 3.0)
            pillar_signal = round(sig_base, 1)

        # CFO Margin-of-Safety / Break-Even Realization Analysis
        break_even_analysis: Dict[str, Any] = {
            "break_even_realization_pct": None,
            "margin_of_safety_x": None,
            "summary_en": "",
            "summary_hi": "",
        }
        if expected_net > 0 and not noise_circuit_breaker:
            hurdle = impl_cost + max(0.0, expected_collateral_loss)
            upside = max(0.0, expected_saved_loss) + max(0.0, expected_margin_delta)
            if hurdle > 0 and upside > 0:
                be_pct = round(min(100.0, (hurdle / upside) * 100.0), 1)
                mos_x = round(upside / hurdle, 2)
                break_even_analysis = {
                    "break_even_realization_pct": be_pct,
                    "margin_of_safety_x": mos_x,
                    "summary_en": f"Stays profitable as long as real-world results reach at least {be_pct:.0f}% of historical effect ({mos_x:.1f}× margin of safety).",
                    "summary_hi": f"अगर असल नतीजे अनुमान का सिर्फ़ {be_pct:.0f}% भी मिलें, तब भी आप मुनाफ़े में रहेंगे ({mos_x:.1f}× सेफ़्टी मार्जिन)।",
                }
            elif ci_low > 0:
                break_even_analysis = {
                    "break_even_realization_pct": 0.0,
                    "margin_of_safety_x": None,
                    "summary_en": f"Zero upfront rollout hurdle — even in the conservative 95% worst case, expected gain stays positive ({_fmt_money(ci_low, self.unit_sym, self.is_monetary)}).",
                    "summary_hi": f"कोई शुरुआती बजट बाधा नहीं — 95% सबसे कमज़ोर स्थिति में भी शुद्ध फ़ायदा पॉज़िटिव ({_fmt_money(ci_low, self.unit_sym, self.is_monetary)}) रहता है।",
                }

        raw_conf_score = pillar_model + pillar_sample + pillar_stability + pillar_signal
        if noise_circuit_breaker:
            raw_conf_score = min(raw_conf_score, 32.0)
        elif confounder_alert and verdict_code == "NEUTRAL":
            raw_conf_score = min(raw_conf_score, 52.0)
        sim_conf_score = int(round(min(96.0, max(5.0, raw_conf_score))))

        if sim_conf_score >= 75:
            sim_conf_tier = "HIGH"
            sim_conf_label_en = "High Trust — Decision-Grade Signal"
            sim_conf_label_hi = "उच्च भरोसा (Decision-Grade)"
        elif sim_conf_score >= 50:
            sim_conf_tier = "MODERATE"
            sim_conf_label_en = "Moderate Trust — Run Small Pilot First"
            sim_conf_label_hi = "मध्यम भरोसा (पहले छोटा पायलट करें)"
        else:
            sim_conf_tier = "LOW"
            sim_conf_label_en = "Low Trust — Noisy, Confounded, or Small Sample"
            sim_conf_label_hi = "कम भरोसा (शोर / कन्फ़ाउंडर / कम सैंपल)"

        if is_combo and overlap_deduped > 0:
            downside_reasons_en.append(
                f"Zero Double-Counting Applied: {overlap_deduped:,} overlapping records affected by multiple levers were evaluated jointly in one unified counterfactual (true net impact is lower than naively adding each lever separately)."
            )
            downside_reasons_hi.append(
                f"डबल-काउंटिंग रोकी गई: {overlap_deduped:,} ओवरलैपिंग ऑर्डर्स पर सभी बदलाव एक साथ गिने गए हैं — इसलिए कुल असर हर बदलाव को अलग जोड़ने से ज़्यादा सटीक और ईमानदार है।"
            )

        if is_combo and not noise_circuit_breaker:
            noisy_sub = [
                lv["column"] for lv in applied_levers
                if not lv["is_pause"] and not lv["is_disc"]
                and lv["emp_gate"]["empirical_p_value"] >= 0.05
                and lv["emp_gate"]["col_auc_drop"] < 0.003
            ]
            if noisy_sub:
                downside_reasons_en.append(
                    f"Weak / Noisy Lever in Combo: '{', '.join(noisy_sub)}' has no statistically proven lift (p >= 0.05) — you can drop it and still keep nearly 100% of the gain."
                )
                downside_reasons_hi.append(
                    f"कॉम्बो में कमज़ोर लीवर: '{', '.join(noisy_sub)}' का डेटा में कोई पक्का असर नहीं (p >= 0.05) — इसे हटाकर भी लगभग पूरा फ़ायदा मिल जाएगा।"
                )

        if not downside_reasons_en:
            downside_reasons_en.append(
                "Observational Data Caveat: Historical ML correlation cannot guarantee 100% causal response if market behavior shifts; monitor weekly after rollout."
            )
            downside_reasons_hi.append(
                "मार्केट बदलाव का ध्यान रखें: ऐतिहासिक डेटा पर आधारित प्रेडिक्शन मज़बूत है, फिर भी लागू करने के बाद हर हफ़्ते असल रिज़ल्ट ट्रैक करें।"
            )

        return {
            "status": "simulated",
            "decision_applied": {
                "spec": spec,
                "specs": specs,
                "is_combo": is_combo,
                "combo_count": len(applied_levers),
                "overlap_rows_deduplicated": overlap_deduped,
                "label_en": action_label_en,
                "label_hi": action_label_hi,
                "affected_records": aff_scaled,
                "affected_share_pct": round((n_aff * scale_factor) / max(len(self.df_full), 1) * 100.0, 2),
                "implementation_cost": round(impl_cost, 2),
                "formatted_implementation_cost": _fmt_money(impl_cost, self.unit_sym, self.is_monetary) if impl_cost > 0 else None,
            },
            "prediction": {
                "verdict_code": verdict_code,
                "verdict_en": verdict_en,
                "verdict_hi": verdict_hi,
                "chance_of_benefit_pct": benefit_prob_pct,
                "chance_of_loss_pct": loss_risk_pct,
                "before_risk_rate_pct": before_rate_pct,
                "after_risk_rate_pct": after_rate_pct,
                "risk_reduction_pp": ml_rate_diff_pct,
                "expected_events_averted": round(expected_ev_averted, 1),
                "expected_gross_impact": round(expected_gross_net, 2),
                "expected_net_impact": round(expected_net, 2),
                "formatted_net_impact": _fmt_money(expected_net, self.unit_sym, self.is_monetary),
                "implementation_cost": round(impl_cost, 2),
                "roi_multiple": roi_multiple,
                "ci_95_low": round(ci_low, 2),
                "ci_95_high": round(ci_high, 2),
                "formatted_ci_95": f"[{_fmt_money(ci_low, self.unit_sym, self.is_monetary)} to {_fmt_money(ci_high, self.unit_sym, self.is_monetary)}]",
                "noise_circuit_breaker_active": noise_circuit_breaker,
                "confounder_alert_active": confounder_alert,
                "causal_support_pct": causal_support_pct,
                "extrapolation_warning": extrapolation_warning,
                "break_even_analysis": break_even_analysis,
                "simulation_confidence": {
                    "score": sim_conf_score,
                    "tier": sim_conf_tier,
                    "label_en": sim_conf_label_en,
                    "label_hi": sim_conf_label_hi,
                    "pillars": {
                        "model_strength": {"score": pillar_model, "max": 30},
                        "sample_size": {"score": pillar_sample, "max": 25},
                        "ensemble_stability": {"score": pillar_stability, "max": 25},
                        "signal_purity": {"score": pillar_signal, "max": 20},
                    },
                },
                "breakdown_components": {
                    "saved_failure_loss": round(expected_saved_loss, 2),
                    "direct_margin_recovery": round(expected_margin_delta, 2),
                    "collateral_tradeoff_cost": round(expected_collateral_loss, 2),
                    "implementation_cost": round(impl_cost, 2),
                    "margin_note_en": margin_note_en,
                    "margin_note_hi": margin_note_hi,
                },
                "is_monetary": self.is_monetary,
                "unit_symbol": self.unit_sym,
            },
            "where_it_helps": winners[:6],
            "where_it_does_not_help": no_benefit_zones[:5],
            "why_loss_could_happen": {
                "en": downside_reasons_en,
                "hi": downside_reasons_hi,
            },
            "statistical_audit": {
                "empirical_p_value": emp_gate["empirical_p_value"],
                "raw_rate_diff_pct": emp_gate["raw_rate_diff_pct"],
                "ml_controlled_diff_pct": ml_rate_diff_pct,
                "feature_oos_auc_drop": emp_gate["col_auc_drop"],
                "fold_epistemic_sd_pct": round(epistemic_rate_sd * 100.0, 3),
                "causal_support_pct": causal_support_pct,
                "extrapolation_warning": extrapolation_warning,
                "temporal_backtest_auc": self.model_metrics.get("temporal_backtest_auc"),
                "ece_pct": self.model_metrics.get("ece_pct"),
                "noise_circuit_breaker_active": noise_circuit_breaker,
                "confounder_alert_active": confounder_alert,
            },
            "model_honesty": {
                "algorithm": self.model_metrics.get("algorithm"),
                "roc_auc": self.model_metrics.get("roc_auc"),
                "brier_score": self.model_metrics.get("brier_score"),
                "ece_pct": self.model_metrics.get("ece_pct"),
                "temporal_backtest_auc": self.model_metrics.get("temporal_backtest_auc"),
                "confidence_tier": self.model_metrics.get("confidence_tier"),
                "confidence_label_hi": self.model_metrics.get("confidence_label_hi"),
                "blocked_leakage_columns": self.model_metrics.get("blocked_leakage_columns", []),
            },
        }
