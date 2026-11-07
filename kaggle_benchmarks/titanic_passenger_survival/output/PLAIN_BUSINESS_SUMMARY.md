## 🇬🇧 Executive Business Summary (Plain English — Zero Jargon)

### 1. Business Health Snapshot
Across **891 physical records** audited in your dataset, our system identified **549 critical failure events (61.62%)**, generating **$12,142.72** in direct financial liability / capital at risk (out of $28,693.95 total monitored portfolio volume).

### 2. Where Is the Bottleneck?
- **Main Bottleneck Identified**: Group `Embarked` = **'S'** has the highest failure rate at **66.30%** (compared to 49.39% across the rest of the business).
- **Strategic Priority**: Direct intervention on this specific group will yield the highest return on operational effort.

### 3. Danger Threshold (Red-Line)
- **Key Operational Red-Line**: In metric `Fare`, when values reach **(-0.001, 7.91]**, failure risk surges abruptly to **80.27%** (compared to **41.89%** in range (31.0, 512.329]).
- **Preventive Guardrail**: Establish early-warning alerts before accounts cross this critical `Fare` threshold to prevent realized losses.

### 4. Your 3 Strategic Choices (You Decide — We Don't Force Dictates)
- **Pathway A (Low-Risk Pilot)**: **$97.00 risk averted** (14 excess adverse events — 25% Excess-Risk Compression). Est. Cost: $5,000 - $15,000, Timeline: 1 - 2 Weeks. *Advantage*: Zero disruption to daily operations; uses simple early-warning queue alerts on `Fare in (-0.001, 7.91]` to stop the first 25% of avoidable excess failures. *Trade-Off*: Leaves 75% of excess losses in `Fare in (-0.001, 7.91]` unaddressed.
- **Pathway B (Focused Operational Fix)**: **$228.65 risk averted** (33 excess adverse events — 60% Excess-Risk Compression). Est. Cost: $25,000 - $50,000, Timeline: 30 - 45 Days. *Advantage*: Highest return on operational effort; directly fixes the `Fare in (-0.001, 7.91]` bottleneck (80.27% failure rate vs 55.39% across the rest of the business). *Trade-Off*: Requires frontline team training on targeted outreach protocols.
- **Pathway C (Deep Structural Overhaul)**: **$381.08 risk averted** (55 excess adverse events — 100% Baseline Parity). Est. Cost: $100,000 - $250,000, Timeline: 90 - 180 Days. *Advantage*: Brings `Fare in (-0.001, 7.91]` down from 80.27% to normal rest-of-business parity (55.39%), eliminating all 56 avoidable excess failures. *Trade-Off*: Higher upfront investment and 90 to 180 days payback timeline.

### 5. Immediate Team Action Worklist (`actionable_priority_worklist.csv`)
- **Preventive Retention Watch (250 active accounts)**: High-risk active accounts that have NOT yet failed. Have your customer success or QA team contact these accounts immediately.
- **Realized Loss Recovery Audit (250 accounts)**: Already-breached records prioritized by financial impact for root-cause analysis and recovery.

---

## 🇮🇳 Business X-Ray Summary (Simple Hinglish — Seedhi Bhasha Mein)

### 1. Aaj Business Ki Asli Halat (Health Snapshot)
Aapke audit kiye gaye **891 records** mein se, system ne **549 failure / churn cases (61.62%)** pakde hain, jisse kul **$12,142.72** ka seedha financial nuksan / risk ($28,693.95 ke kul portfolio volume mein se) ho raha hai.

### 2. Sabse Bada Nuksan Kahan Ho Raha Hai?
- **Sabse Bada Bottleneck Kahan Hai?**: Group `Embarked` = **'S'** mein sabse zyada failure/churn rate **66.30%** hai (jabki baaki business mein yeh sirf 49.39% hai).
- **Team Ka Focus**: Sabse pehle isi specific cohort par dhyan dein, yahin se sabse tez improvement milega.

### 3. Khatre Ki Laal Rekha (Danger Limit)
- **Khatre Ki Laal Rekha (Danger Limit)**: Metric `Fare` mein jab values **(-0.001, 7.91]** ke daayre mein pahunchti hain, toh failure rate badhkar **80.27%** ho jata hai (jabki (31.0, 512.329] range mein yeh sirf **41.89%** rehta hai).
- **Bachav Ka Tarika**: Accounts ko is `Fare` limit tak pahunchne se pehle hi early-warning trigger karein taaki realized churn/default ko pehle hi roka ja sake.

### 4. Aapke Paas 3 Imandar Raste Hain (Faisla Aapka — Koi Jabardasti Nahi)
- **Pathway A (Chhota / Low-Risk Trial)**: **$97.00 risk averted** (14 excess adverse events — 25% Excess-Risk Compression). Kharcha: $5,000 - $15,000, Samay: 1 - 2 Weeks. *Fayda*: Daily kaam mein bina kisi rukawat ke `Fare in (-0.001, 7.91]` par simple early-warning alerts lagakar shuruati 25% avoidable nuksan turant roka ja sakta hai. *Nuksan*: Is group ka baaki 75% extra risk abhi bhi bacha rahega.
- **Pathway B (Focused / Targeted Fix)**: **$228.65 risk averted** (33 excess adverse events — 60% Excess-Risk Compression). Kharcha: $25,000 - $50,000, Samay: 30 - 45 Days. *Fayda*: Mehnat aur paise par sabse behtar return (Best ROI); seedha `Fare in (-0.001, 7.91]` bottleneck (80.27% failure rate vs baaki business mein 55.39%) ko theek karke 60% extra nuksan kam karta hai. *Nuksan*: Frontline team ko naye targeted follow-up process ki training deni hogi.
- **Pathway C (Bada / Structural Badlav)**: **$381.08 risk averted** (55 excess adverse events — 100% Baseline Parity). Kharcha: $100,000 - $250,000, Samay: 90 - 180 Days. *Fayda*: `Fare in (-0.001, 7.91]` ke 80.27% failure rate ko ghata kar baaki business ke normal 55.39% level par le aata hai, jisse poore 56 avoidable excess failures khatam ho jate hain. *Nuksan*: Shuruati kharcha zyada hai aur poora asar aane mein 90 se 180 din lagenge.

### 5. Aaj Subah Team Ko Kya Kaam Dein? (`actionable_priority_worklist.csv`)
- **Bachav Soochi - Preventive Retention Watch (250 active accounts)**: Yeh wo active accounts hain jo abhi tak kharab nahi hue hain, par risk zone mein hain. Team se turant preventive contact karwayein.
- **Vasooli Aur Jaanch - Realized Loss Recovery Audit (250 accounts)**: Yeh wo accounts hain jinka nuksan pehle hi ho chuka hai. Inhein recovery aur root-cause audit ke liye use karein.
