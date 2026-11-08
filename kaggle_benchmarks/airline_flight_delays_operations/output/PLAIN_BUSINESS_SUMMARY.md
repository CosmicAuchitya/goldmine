## 🇬🇧 Executive Business Summary (Plain English — Zero Jargon)

### 1. Business Health Snapshot
Across **123,984 physical records** audited in your dataset, our system identified **23,326 critical failure events (18.81%)**, generating **23,326 critical quality/failure events** (18.81% defect rate).

### 2. Where Is the Bottleneck?
- **Main Bottleneck Identified**: Group `carrier` = **'EV'** has the highest failure rate at **29.98%** (compared to 18.40% across the rest of the business).
- **Strategic Priority**: Direct intervention on this specific group will yield the highest return on operational effort.

### 3. Danger Threshold (Red-Line)
- **Key Operational Red-Line**: In metric `hour`, when values reach **(17.0, 23.0]**, failure risk surges abruptly to **31.59%** (compared to **8.19%** in range (4.999, 9.0]).
- **Preventive Guardrail**: Establish early-warning alerts before accounts cross this critical `hour` threshold to prevent realized losses.

### 4. Your 3 Strategic Choices (You Decide — We Don't Force Dictates)
- **Pathway A (Low-Risk Pilot)**: **174 events prevented** (25% Excess-Risk Compression). Est. Cost: Internal Staff Hours (No CapEx), Timeline: 1 - 2 Weeks. *Advantage*: Zero disruption to daily operations; uses simple early-warning queue alerts on `hour = 21` to stop the first 25% of avoidable excess failures. *Trade-Off*: Leaves 75% of excess losses in `hour = 21` unaddressed.
- **Pathway B (Focused Operational Fix)**: **417 events prevented** (60% Excess-Risk Compression). Est. Cost: Dedicated Protocol Buffer & Daily Monitoring, Timeline: 30 - 45 Days. *Advantage*: Highest return on operational effort; directly fixes the `hour = 21` bottleneck (33.96% failure rate vs 18.25% across the rest of the business). *Trade-Off*: Requires frontline team training on targeted outreach protocols.
- **Pathway C (Deep Structural Overhaul)**: **696 events prevented** (100% Baseline Parity). Est. Cost: Dedicated Telemetry / Automated Infrastructure Revamp, Timeline: 90 - 180 Days. *Advantage*: Brings `hour = 21` down from 33.96% to normal rest-of-business parity (18.25%), eliminating all 696 avoidable excess failures. *Trade-Off*: Higher upfront investment and 90 to 180 days payback timeline.

### 5. Immediate Team Action Worklist (`actionable_priority_worklist.csv`)
- **Preventive Retention Watch (250 active accounts)**: High-risk active accounts that have NOT yet failed. Have your customer success or QA team contact these accounts immediately.
- **Realized Loss Recovery Audit (250 accounts)**: Already-breached records prioritized by financial impact for root-cause analysis and recovery.

---

## 🇮🇳 Business X-Ray Summary (Simple Hinglish — Seedhi Bhasha Mein)

### 1. Aaj Business Ki Asli Halat (Health Snapshot)
Aapke audit kiye gaye **123,984 records** mein se, system ne **23,326 failure / churn cases (18.81%)** pakde hain, jisse kul **23,326 critical failure/defect events** (18.81% defect rate) ho raha hai.

### 2. Sabse Bada Nuksan Kahan Ho Raha Hai?
- **Sabse Bada Bottleneck Kahan Hai?**: Group `carrier` = **'EV'** mein sabse zyada failure/churn rate **29.98%** hai (jabki baaki business mein yeh sirf 18.40% hai).
- **Team Ka Focus**: Sabse pehle isi specific cohort par dhyan dein, yahin se sabse tez improvement milega.

### 3. Khatre Ki Laal Rekha (Danger Limit)
- **Khatre Ki Laal Rekha (Danger Limit)**: Metric `hour` mein jab values **(17.0, 23.0]** ke daayre mein pahunchti hain, toh failure rate badhkar **31.59%** ho jata hai (jabki (4.999, 9.0] range mein yeh sirf **8.19%** rehta hai).
- **Bachav Ka Tarika**: Accounts ko is `hour` limit tak pahunchne se pehle hi early-warning trigger karein taaki realized churn/default ko pehle hi roka ja sake.

### 4. Aapke Paas 3 Imandar Raste Hain (Faisla Aapka — Koi Jabardasti Nahi)
- **Pathway A (Chhota / Low-Risk Trial)**: **174 events prevented** (25% Excess-Risk Compression). Kharcha: Internal Staff Hours (No CapEx), Samay: 1 - 2 Weeks. *Fayda*: Daily kaam mein bina kisi rukawat ke `hour = 21` par simple early-warning alerts lagakar shuruati 25% avoidable nuksan turant roka ja sakta hai. *Nuksan*: Is group ka baaki 75% extra risk abhi bhi bacha rahega.
- **Pathway B (Focused / Targeted Fix)**: **417 events prevented** (60% Excess-Risk Compression). Kharcha: Dedicated Protocol Buffer & Daily Monitoring, Samay: 30 - 45 Days. *Fayda*: Mehnat aur paise par sabse behtar return (Best ROI); seedha `hour = 21` bottleneck (33.96% failure rate vs baaki business mein 18.25%) ko theek karke 60% extra nuksan kam karta hai. *Nuksan*: Frontline team ko naye targeted follow-up process ki training deni hogi.
- **Pathway C (Bada / Structural Badlav)**: **696 events prevented** (100% Baseline Parity). Kharcha: Dedicated Telemetry / Automated Infrastructure Revamp, Samay: 90 - 180 Days. *Fayda*: `hour = 21` ke 33.96% failure rate ko ghata kar baaki business ke normal 18.25% level par le aata hai, jisse poore 696 avoidable excess failures khatam ho jate hain. *Nuksan*: Shuruati kharcha zyada hai aur poora asar aane mein 90 se 180 din lagenge.

### 5. Aaj Subah Team Ko Kya Kaam Dein? (`actionable_priority_worklist.csv`)
- **Bachav Soochi - Preventive Retention Watch (250 active accounts)**: Yeh wo active accounts hain jo abhi tak kharab nahi hue hain, par risk zone mein hain. Team se turant preventive contact karwayein.
- **Vasooli Aur Jaanch - Realized Loss Recovery Audit (250 accounts)**: Yeh wo accounts hain jinka nuksan pehle hi ho chuka hai. Inhein recovery aur root-cause audit ke liye use karein.
