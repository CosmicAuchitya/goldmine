# ENTERPRISE STAR SCHEMA & POWER BI / TABLEAU MEASURE GUIDE
## Data Model: `bi_ready_fact`

### 1. Data Model Architecture (Star Schema)
```
Fact Table: 'bi_ready_fact.parquet'
Total Verified Records: 119,390 (Zero Duplication Verified)
```

---

### 2. Copy-Paste Enterprise DAX Measures (Power BI)

```dax
// 1. Total Volume of Records
Total Records = 
COUNTROWS('bi_ready_fact')

// 2. Monitored Target Events (is_canceled)
Target Events = 
CALCULATE(
    COUNTROWS('bi_ready_fact'),
    'bi_ready_fact'[is_canceled] = 1
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
    SUM('bi_ready_fact'[adr]),
    'bi_ready_fact'[is_canceled] = 1
)

// 5b. Total Baseline Portfolio Volume ($)
Total Portfolio Volume ($) = 
SUM('bi_ready_fact'[adr])

// 6. Average Financial Impact Per Adverse Event
Avg Friction Impact ($) = 
DIVIDE([Total Adverse Capital Drag ($)], [Target Events], 0)
```

---

### 3. Tableau Calculated Fields Equivalent
- **[Total Records]**: `COUNT([hotel])`
- **[Target Events]**: `SUM([is_canceled])`
- **[Event Rate %]**: `[Target Events] / [Total Records]`
- **[Total Financial Friction ($)]**: `SUM([adr])`

---
*Generated autonomously by Enterprise DataX-Ray Core*
