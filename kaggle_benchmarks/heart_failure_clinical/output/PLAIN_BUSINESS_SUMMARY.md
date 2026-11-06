## 🇬🇧 Executive Business Summary (Plain English — Zero Jargon)

### 1. Business Health Snapshot
Across **299 physical records** audited in your dataset, our system identified **96 critical failure events (32.11%)**, generating **96 critical quality/failure events** (32.11% defect rate).

### 2. Where Is the Bottleneck?
- **Main Bottleneck Identified**: Group `ejection_fraction` = **'20'** has the highest failure rate at **88.89%** (compared to 28.47% across the rest of the business).
- **Strategic Priority**: Direct intervention on this specific group will yield the highest return on operational effort.

### 3. Danger Threshold (Red-Line)
- **Key Operational Red-Line**: In metric `time`, when values reach **(3.999, 73.0]**, failure risk surges abruptly to **82.89%** (compared to **5.33%** in range (203.0, 285.0]).
- **Preventive Guardrail**: Establish early-warning alerts before accounts cross this critical `time` threshold to prevent realized losses.

### 4. Your 3 Strategic Choices (You Decide — We Don't Force Dictates)
- **Pathway A (Low-Risk Pilot)**: **3 events prevented** (25% Excess-Risk Compression). Est. Cost: Internal Staff Hours (No CapEx), Timeline: 1 - 2 Weeks. *Advantage*: Zero disruption to daily operations; uses simple early-warning queue alerts on `ejection_fraction = 20` to stop the first 25% of avoidable excess failures. *Trade-Off*: Leaves 75% of excess losses in `ejection_fraction = 20` unaddressed.
- **Pathway B (Focused Operational Fix)**: **7 events prevented** (60% Excess-Risk Compression). Est. Cost: Dedicated Protocol Buffer & Daily Monitoring, Timeline: 30 - 45 Days. *Advantage*: Highest return on operational effort; directly fixes the `ejection_fraction = 20` bottleneck (88.89% failure rate vs 28.47% across the rest of the business). *Trade-Off*: Requires frontline team training on targeted outreach protocols.
- **Pathway C (Deep Structural Overhaul)**: **11 events prevented** (100% Baseline Parity). Est. Cost: Dedicated Telemetry / Automated Infrastructure Revamp, Timeline: 90 - 180 Days. *Advantage*: Brings `ejection_fraction = 20` down from 88.89% to normal rest-of-business parity (28.47%), eliminating all 11 avoidable excess failures. *Trade-Off*: Higher upfront investment and 90 to 180 days payback timeline.

### 5. Immediate Team Action Worklist (`actionable_priority_worklist.csv`)
- **Preventive Retention Watch (203 active accounts)**: High-risk active accounts that have NOT yet failed. Have your customer success or QA team contact these accounts immediately.
- **Realized Loss Recovery Audit (96 accounts)**: Already-breached records prioritized by financial impact for root-cause analysis and recovery.

---

## 🇮🇳 Business X-Ray Summary (Simple Hinglish — Seedhi Bhasha Mein)

### 1. Aaj Business Ki Asli Halat (Health Snapshot)
Aapke audit kiye gaye **299 records** mein se, system ne **96 failure / churn cases (32.11%)** pakde hain, jisse kul **96 critical failure/defect events** (32.11% defect rate) ho raha hai.

### 2. Sabse Bada Nuksan Kahan Ho Raha Hai?
- **Sabse Bada Bottleneck Kahan Hai?**: Group `ejection_fraction` = **'20'** mein sabse zyada failure/churn rate **88.89%** hai (jabki baaki business mein yeh sirf 28.47% hai).
- **Team Ka Focus**: Sabse pehle isi specific cohort par dhyan dein, yahin se sabse tez improvement milega.

### 3. Khatre Ki Laal Rekha (Danger Limit)
- **Khatre Ki Laal Rekha (Danger Limit)**: Metric `time` mein jab values **(3.999, 73.0]** ke daayre mein pahunchti hain, toh failure rate badhkar **82.89%** ho jata hai (jabki (203.0, 285.0] range mein yeh sirf **5.33%** rehta hai).
- **Bachav Ka Tarika**: Accounts ko is `time` limit tak pahunchne se pehle hi early-warning trigger karein taaki realized churn/default ko pehle hi roka ja sake.

### 4. Aapke Paas 3 Imandar Raste Hain (Faisla Aapka — Koi Jabardasti Nahi)
- **Pathway A (Chhota / Low-Risk Trial)**: **3 events prevented** (25% Excess-Risk Compression). Kharcha: Internal Staff Hours (No CapEx), Samay: 1 - 2 Weeks. *Fayda*: Daily kaam mein bina kisi rukawat ke `ejection_fraction = 20` par simple early-warning alerts lagakar shuruati 25% avoidable nuksan turant roka ja sakta hai. *Nuksan*: Is group ka baaki 75% extra risk abhi bhi bacha rahega.
- **Pathway B (Focused / Targeted Fix)**: **7 events prevented** (60% Excess-Risk Compression). Kharcha: Dedicated Protocol Buffer & Daily Monitoring, Samay: 30 - 45 Days. *Fayda*: Mehnat aur paise par sabse behtar return (Best ROI); seedha `ejection_fraction = 20` bottleneck (88.89% failure rate vs baaki business mein 28.47%) ko theek karke 60% extra nuksan kam karta hai. *Nuksan*: Frontline team ko naye targeted follow-up process ki training deni hogi.
- **Pathway C (Bada / Structural Badlav)**: **11 events prevented** (100% Baseline Parity). Kharcha: Dedicated Telemetry / Automated Infrastructure Revamp, Samay: 90 - 180 Days. *Fayda*: `ejection_fraction = 20` ke 88.89% failure rate ko ghata kar baaki business ke normal 28.47% level par le aata hai, jisse poore 11 avoidable excess failures khatam ho jate hain. *Nuksan*: Shuruati kharcha zyada hai aur poora asar aane mein 90 se 180 din lagenge.

### 5. Aaj Subah Team Ko Kya Kaam Dein? (`actionable_priority_worklist.csv`)
- **Bachav Soochi - Preventive Retention Watch (203 active accounts)**: Yeh wo active accounts hain jo abhi tak kharab nahi hue hain, par risk zone mein hain. Team se turant preventive contact karwayein.
- **Vasooli Aur Jaanch - Realized Loss Recovery Audit (96 accounts)**: Yeh wo accounts hain jinka nuksan pehle hi ho chuka hai. Inhein recovery aur root-cause audit ke liye use karein.
