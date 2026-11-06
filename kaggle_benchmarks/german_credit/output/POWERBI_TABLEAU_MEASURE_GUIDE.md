# ENTERPRISE STAR SCHEMA & POWER BI / TABLEAU MEASURE GUIDE
## Data Model: `bi_ready_fact`

### 1. Data Model Architecture (Star Schema)
```
Fact Table: 'bi_ready_fact.parquet'
Total Verified Records: 1,000 (Zero Duplication Verified)
  ├── Linked Dimension: 'bi_dim_accounts.csv'
  ├── Linked Dimension: 'bi_dim_demographics.csv'
  ├── Linked Dimension: 'bi_dim_purpose.csv'
```

---

### 2. Copy-Paste Enterprise DAX Measures (Power BI)

```dax
// 1. Total Volume of Records
Total Records = 
COUNTROWS('bi_ready_fact')

// 2. Monitored Target Events (Risk)
Target Events = 
CALCULATE(
    COUNTROWS('bi_ready_fact'),
    'bi_ready_fact'[Risk] = "bad"
)

// 3. System Target Event Vulnerability Rate %
Event Vulnerability Rate % = 
DIVIDE([Target Events], [Total Records], 0) * 100

// 4. System Reliability / Performance Rate %
System Reliability Rate % = 
100 - [Event Vulnerability Rate %]

// 5. Total Adverse Capital Drag ($) (Direct Financial Drag on Adverse Cohort)
Total Adverse Capital Drag ($) = 
CALCULATE(
    SUM('bi_ready_fact'[Credit amount]),
    'bi_ready_fact'[Risk] = "bad"
)

// 5b. Total Baseline Portfolio Volume ($)
Total Portfolio Volume ($) = 
SUM('bi_ready_fact'[Credit amount])

// 6. Average Financial Impact Per Adverse Event
Avg Friction Impact ($) = 
DIVIDE([Total Adverse Capital Drag ($)], [Target Events], 0)
```

---

### 3. Tableau Calculated Fields Equivalent
- **[Total Records]**: `COUNT([Unnamed: 0])`
- **[Target Events]**: `SUM([Risk])`
- **[Event Rate %]**: `[Target Events] / [Total Records]`
- **[Total Financial Friction ($)]**: `SUM([Credit amount])`

---
*Generated autonomously by Enterprise DataX-Ray Core*
