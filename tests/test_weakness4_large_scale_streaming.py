import json
import time
from pathlib import Path
import numpy as np
import pandas as pd

from autonomous_engine.duckdb_streaming_engine import (
    duckdb_exact_segment_aggregation,
    optimize_dataframe_memory,
    stream_csv_to_parquet_duckdb,
)
from autonomous_engine.templated_dag_runner import execute_templated_pipeline


def test_w4_500k_row_duckdb_streaming_and_zero_drift_dag(tmp_path):
    """
    Benchmarks 500,000 physical rows (~30 MB CSV) through DuckDB out-of-core streaming,
    vectorized DAG execution, lossless memory compaction, and out-of-core DuckDB SQL aggregation.
    """
    n_rows = 500_000
    rng = np.random.default_rng(123)
    raw_dir = tmp_path / "raw_data"
    out_dir = tmp_path / "out"
    cache_dir = tmp_path / "cache"
    raw_dir.mkdir()
    out_dir.mkdir()
    cache_dir.mkdir()

    csv_path = raw_dir / "enterprise_500k_orders.csv"
    df_gen = pd.DataFrame({
        "order_id": np.arange(1, n_rows + 1, dtype=np.int64),
        "region": rng.choice(["North", "South", "East", "West"], size=n_rows, p=[0.25, 0.25, 0.30, 0.20]),
        "payment_mode": rng.choice(["UPI", "COD", "Card"], size=n_rows, p=[0.50, 0.30, 0.20]),
        "product_category": rng.choice(["Electronics", "Apparel", "Groceries", "Home_Decor"], size=n_rows),
        "order_amount": np.round(rng.uniform(200.0, 5000.0, size=n_rows), 2),
        "is_returned": rng.choice([0, 1], size=n_rows, p=[0.85, 0.15]),
    })
    df_gen.to_csv(csv_path, index=False)
    assert csv_path.stat().st_size > 15 * 1024 * 1024, "Expected >15 MB CSV to exercise DuckDB streaming path"

    # 1. Direct DuckDB Out-of-Core Streaming CSV -> ZSTD Parquet
    t0 = time.time()
    pq_stream = tmp_path / "streamed.parquet"
    st_meta = stream_csv_to_parquet_duckdb(csv_path, pq_stream)
    stream_sec = time.time() - t0
    assert st_meta["rows"] == n_rows
    assert st_meta["compression_ratio"] >= 1.5
    assert stream_sec < 20.0, f"DuckDB 500k streaming too slow: {stream_sec:.2f}s"

    # 2. Lossless Memory Compaction keeps monetary column exact float64
    comp_df, mem_stats = optimize_dataframe_memory(df_gen.copy())
    assert comp_df["order_amount"].dtype == np.float64
    assert comp_df["order_id"].dtype == np.int32
    assert mem_stats["after_mb"] < mem_stats["before_mb"]

    # 3. Full Deterministic DAG Execution on 500,000 rows -> 0 Cartesian drift, fast vectorized execution
    bp_path = tmp_path / "execution_blueprint.json"
    bp_path.write_text(
        json.dumps({
            "project_title": "500k Scale Stress Test",
            "fact_table": "enterprise_500k_orders",
            "primary_id_column": "order_id",
            "target_metric": "is_returned",
            "join_plan": [],
        }),
        encoding="utf-8",
    )
    t1 = time.time()
    summary = execute_templated_pipeline(str(bp_path), str(raw_dir), str(out_dir), cache_dir=str(cache_dir))
    dag_sec = time.time() - t1
    assert summary["status"] == "PASSED"
    assert summary["initial_rows"] == n_rows
    assert summary["final_fact_rows"] == n_rows
    assert summary["cartesian_drift"] == 0
    assert dag_sec < 45.0, f"500k DAG execution exceeded 45s budget: {dag_sec:.2f}s"

    # 4. Out-of-core DuckDB SQL exact segment aggregation on bi_ready_fact.parquet
    agg_df = duckdb_exact_segment_aggregation(
        out_dir / "bi_ready_fact.parquet",
        dim_col="region",
        target_event_col="is_returned",
        cost_col="order_amount",
    )
    assert int(agg_df["volume"].sum()) == n_rows
    assert len(agg_df) == 4
