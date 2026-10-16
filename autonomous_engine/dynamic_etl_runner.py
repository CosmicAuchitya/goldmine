import pandas as pd
import numpy as np
import sys
import os
import json
from pathlib import Path

# Enforce UTF-8 on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def setup_directories(paths):
    for p in paths:
        p.mkdir(parents=True, exist_ok=True)

def run_etl():
    # 1. Configuration & Directories
    BASE_DIR = Path('C:/Users/91945/OneDrive/Desktop/XXX/Ai aotumation learning/kaggle_benchmarks/wine_quality')
    RAW_DIR = BASE_DIR / 'raw_data'
    CACHE_DIR = BASE_DIR / 'cache'
    OUTPUT_DIR = BASE_DIR / 'output'
    
    setup_directories([CACHE_DIR, OUTPUT_DIR])

    # 2. Ingestion
    file_path = RAW_DIR / "WineQT.csv"
    df = pd.read_csv(file_path, sep=',', encoding='utf-8', na_values=['?'], low_memory=False)
    
    # Standardize Column Names
    df.columns = [c.strip() for c in df.columns]
    
    initial_fact_count = len(df)
    
    # 3. Entity Resolution & Cardinality Defense
    # Generate unique surrogate ID
    df['fact_surrogate_id'] = (df.index + 1).astype(str)
    
    # Impute missing values strictly preserving row count
    for col in df.select_dtypes(include=[np.number]).columns:
        df[col] = df[col].fillna(df[col].median())
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].fillna('UNKNOWN')

    # 4. Forensic Enrichments
    # sulfur_ratio = total sulfur dioxide / free sulfur dioxide
    # Note: Handle division by zero
    df['sulfur_ratio'] = np.where(df['free sulfur dioxide'] != 0, 
                                  df['total sulfur dioxide'] / df['free sulfur dioxide'], 0)
    
    # acidity_velocity = (fixed acidity + volatile acidity) / pH
    df['acidity_velocity'] = (df['fixed acidity'] + df['volatile acidity']) / df['pH'].replace(0, 1)
    
    # chemical_impurity_index = (chlorides + sulphates) / alcohol
    df['chemical_impurity_index'] = (df['chlorides'] + df['sulphates']) / df['alcohol'].replace(0, 1)

    # 5. Final Preparation
    # Cast to string for parquet compatibility
    df['fact_surrogate_id'] = df['fact_surrogate_id'].astype(str)
    
    final_fact = df.loc[:, ~df.columns.duplicated()]

    # 6. Assertion Gates
    assert len(final_fact) == initial_fact_count, 'Row count mismatch: Cartesian duplicate explosion or row loss occurred!'
    assert final_fact['fact_surrogate_id'].duplicated().sum() == 0, 'Duplicate primary IDs detected!'
    assert 'quality' in final_fact.columns, 'Missing expected dimension features!'

    # 7. Exports
    # Export Fact Table
    final_fact.to_parquet(OUTPUT_DIR / 'bi_ready_fact.parquet', engine='pyarrow', index=False)
    
    # Export Dimension (subset of fact as per blueprint request)
    dim_df = final_fact[['fact_surrogate_id', 'quality']]
    dim_df.to_csv(OUTPUT_DIR / 'bi_dim_wine_profile.csv', index=False)
    
    # Export Diagnostic Dossier
    dossier = {
        "status": "SUCCESS",
        "processed_rows": len(final_fact),
        "columns_processed": list(final_fact.columns),
        "dax_spec_reference": "Embedded in blueprint logic"
    }
    with open(OUTPUT_DIR / 'forensic_dossier.json', 'w') as f:
        json.dump(dossier, f, indent=4)

    # 8. Execution Summary
    print("-" * 30)
    print("ETL JOB COMPLETED SUCCESSFULLY")
    print(f"Total Records Processed: {len(final_fact)}")
    print(f"Fact Table Artifact: {OUTPUT_DIR / 'bi_ready_fact.parquet'}")
    print("-" * 30)

if __name__ == "__main__":
    run_etl()