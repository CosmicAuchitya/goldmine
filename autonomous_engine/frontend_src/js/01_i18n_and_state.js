    // =========================================================================
    // GLOBAL APPLICATION STATE & BILINGUAL UI DICTIONARY
    // =========================================================================
    const appState = {
      selectedFile: null,
      activeRunId: null,
      activeOutputDir: null,
      activeTenant: 'founder_workspace',
      briefLanguage: 'en',
      theme: 'light',
      activeTab: 'overview',
      englishSummaryMd: '',
      hinglishSummaryMd: '',
      executivePulse: null,
      worklistRows: [],
      worklistMeta: { primary_id_column: 'Entity_ID', total_flagged: 0 },
      worklistQueueFilter: 'all',
      resolvedEntities: new Set(),
      modalRowIndex: null,
      activeCohortDimIdx: 0,
      digestPayload: null,
      digestLang: 'hi',
      questions200Data: null,
      questions200Pillar: 'ALL',
      rankedLeaks: null,
      rankedLeaksRaw: null,
      worldLanguages: [],
      translatedSummaries: {},
      translatedRankedLeaks: {},
      langRequestSeq: 0,
      inFlightLangKey: null,
      copilotHistory: [],
      predictOverview: null,
      predictOverviewRunId: null,
      predictLastResult: null,
      predictCompareList: [],
      predictComboQueue: [],
      predictCommitmentsData: null,
      boardroomHistory: [],
      boardroomStartersRunId: null,
      boardroomStarters: [],
      businessCategories: [],
      detectedCategoryMeta: null
    };

    const i18nDict = {
      en: {
        brandSubtitle: 'AI Executive Suite',
        lblReport: 'SWITCH REPORT',
        btnNewUpload: 'Upload Data',
        btnSettings: 'Settings',
        sealVerified: '100% Verified',
        eyebrowUpload: 'STEP 1 · CONNECT YOUR BUSINESS FILE',
        heroHeading: 'Find where your business is leaking money — in 30 seconds.',
        heroLead: 'Upload your Sales, Orders, Invoices, or Customer Excel/CSV sheet. No coding or formulas needed — see your #1 problem area, today\'s customer call list, and exact money you can save.',
        dropTitle: 'Drop your Excel or CSV file here, or click to pick',
        dropSub: 'Supports single files or multiple linked sheets (Orders + Customers). 100% private.',
        btnPickFile: 'Choose File from Computer',
        ben1Title: '100% Real Numbers',
        ben1Sub: 'Every rupee/dollar is counted directly from your sheet. Zero guesswork.',
        ben2Title: 'Plain Language',
        ben2Sub: 'Understand everything clearly in simple English or Hinglish.',
        ben3Title: 'Daily Action List',
        ben3Sub: 'Get a ready-made list of customers & orders to fix today.',
        eyebrowConnect: 'OR CONNECT DIRECTLY WITH 1 CLICK',
        eyebrowDemoConnectors: 'LIVE SYNC OR INTERACTIVE SAMPLE DEMOS',
        btnLoadSheet: 'Load Sheet',
        eyebrowExamples: 'SEE HOW IT WORKS FIRST',
        examplesTitle: 'Try Real Business Examples (1-Click)',
        examplesLead: 'Want to explore before uploading your own data? Click any business example below to see the complete report immediately:',
        lblRows: 'Total Records:',
        lblIssues: 'Problem Cases:',
        lblRiskMoney: 'Money at Risk:',
        btnWhatsAppBrief: 'Brief',
        btnPrintPdf: 'PDF',
        btnFullVisual: 'Charts',
        btnProof: 'Proof',
        tabOverview: 'Business Health',
        tabActions: 'Call List',
        tabCalculator: 'Calculator',
        tabAsk: 'Ask AI',
        tabPredict: 'Decision Lab',
        tabBoardroom: 'Boardroom',
        boardroomEyebrow: 'AI BUSINESS ADVISOR · DEBATE & VERIFY DECISIONS',
        boardroomTitle: 'Discuss Your Team Debate or Business Idea Against Real Data',
        boardroomLead: 'Type or speak any real business dilemma, budget proposal, or team argument in plain language — get a brutally honest verdict showing what your data proves TRUE, what is WRONG/risky, and what the data cannot see.',
        boardroomHint: 'Supports multi-turn follow-ups, ₹/$ budgets, team Option A vs B debates & all 43 world languages.',
        btnBoardroomAsk: 'Ask the Boardroom Judge',
        boardroomProvenTitle: 'Proven True by Your Data',
        boardroomWrongTitle: 'Wrong, Risky, or Unsupported',
        boardroomBlindTitle: 'What Your Data Cannot See',
        boardroomPlanTitle: 'Recommended 14-Day Safe Action Plan',
        boardroomCopyMemo: 'Copy WhatsApp Memo',
        eyebrowCheck: 'QUICK CHECK BEFORE STARTING',
        eyebrowPredict: 'WHAT-IF DECISION SIMULATOR · TEST BEFORE SPENDING',
        predictTitle: 'Test Your Business Decision Before You Take Action',
        predictLead: 'Pick a 1-click idea below or type your own change in plain English/Hinglish — see the honest % chance of profit, where it wins, where it won\'t help, and why loss could happen.',
        btnPredictNow: 'Predict Outcome',
        predictCustomToggle: '🎛️ Or Build a Custom Decision (Choose Any Business Factor & Change)',
        lblPredictCol: '1. What do you want to change?',
        lblPredictAct: '2. Type of change',
        lblPredictFrom: '3. Current value',
        lblPredictTo: '4. Change to',
        lblPredictScope: 'Optional: Only in specific store/group',
        btnTestCustom: 'Test This Change',
        predHelpsEye: 'WHERE IT HELPS MOST',
        predHelpsTitle: '✅ Where You Win',
        predNoHelpEye: 'WHERE IT WON\'T HELP MUCH',
        predNoHelpTitle: '⚠️ Low / Zero-Benefit Zones',
        predRisksEye: 'HONEST DOWNSIDE CHECK',
        predRisksTitle: '🔍 Why Loss Could Happen',
        lblRolloutCost: '💰 Rollout Cost:',
        predCmpEye: 'SIDE-BY-SIDE DECISION SCORECARD',
        predCmpTitle: '⚖️ Compare Your Tested Decisions',
        cmpColDec: 'Decision Tested',
        cmpColVer: 'Verdict',
        cmpColProb: 'Benefit %',
        cmpColConf: 'Trust Score',
        cmpColNet: 'Net Impact',
        cmpColCi: '95% Honest Range',
        btnAddCombo: 'Combo',
        btnRunCombo: 'Simulate Combo',
        btnCommitTrack: 'Commit & Track Reality',
        btnWaMemo: 'WhatsApp Memo',
        btnPrintMemo: 'Print Board PDF',
        predTrackEye: 'PREDICTED VS ACTUAL ACCOUNTABILITY LOG',
        predTrackTitle: '🎯 Did Our Predictions Come True?',
        eyebrowTrend: 'TREND COMPARED TO PREVIOUS REPORT',
        lblRateChange: 'Problem Rate Change',
        lblMoneyChange: 'Avg Order Change',
        card1Title: '01 · Your Safe Strength',
        card1Foot: 'KEEP DOING THIS',
        card2Title: '02 · Biggest Money Leak',
        card2Foot: 'FIX THIS FIRST',
        card3Title: '03 · Danger Limit',
        card3Foot: 'AVOID CROSSING THIS',
        card4Title: '04 · Money You Can Save',
        card4Foot: '30-DAY OPPORTUNITY',
        eyebrowPlans: 'YOUR 3 OPTIONS TO FIX THIS',
        clickSimulate: 'CLICK ONE TO ESTIMATE',
        plansTitle: 'Choose Your Improvement Plan',
        plansLead: 'We never force one decision. Pick any plan below to test how much money it saves in the calculator:',
        eyebrowStory: 'FULL BUSINESS SUMMARY',
        storyTitle: 'Simple Story of Your Numbers',
        eyebrowRoi: 'YOUR SAVED MONEY TRACKER',
        lblActionsDone: 'Actions Taken:',
        lblRoiMult: 'Return on Plan:',
        roiHelpText: 'Click "Take Action" on any customer/order below when your team calls or fixes it — your savings automatically update here.',
        btnDownloadList: 'Download Excel/CSV List',
        eyebrowQueue: 'TEAM DAILY WORKLIST',
        worklistTitle: 'Priority Customers & Orders to Act On Today',
        fltAll: 'All Cases',
        fltPrev: '🟡 Save Before Loss',
        fltRec: '🔴 Recover Lost Money',
        colPriority: 'Urgency',
        colChance: 'Risk %',
        colMoney: 'Amount at Risk',
        colWhy: 'Why It Is Risky',
        colDo: 'What to Do Next',
        colBtn: 'Action',
        eyebrowSim: 'WHAT-IF SAVINGS CALCULATOR',
        simTitle: 'Calculate How Much Profit You Can Recover',
        simLead: 'Move the sliders below to test: "If we reduce our main problem by X% and spend Y budget, how much net profit stays in our pocket?"',
        simSlider1: 'How much of the problem can we reduce?',
        simSlider2: 'Monthly Team / Fix Cost',
        simNetLbl: 'Net Profit Kept',
        simNewRateLbl: 'New Problem Rate',
        eyebrowBreak: 'CATEGORY & GROUP BREAKDOWN',
        breakTitle: 'Where Are Losses Happening Most?',
        brkColGroup: 'Group / Segment',
        brkColVol: 'Total Orders',
        brkColFail: 'Failed Cases',
        brkColRate: 'Problem Rate %',
        brkColShare: 'Share of All Problems',
        brkColMoney: 'Money Lost / At Risk',
        brkColHealth: 'Health',
        brkColWhy: 'Check Why',
        eyebrowAsk: 'ASK IN PLAIN ENGLISH OR HINGLISH',
        askTitle: 'Ask Any Question About Your Business',
        askLead: 'Type your question below just like texting a business analyst — or click one of the ready-made questions:',
        btnGetAnswer: 'Get Verified Answer',
        navMenuLabel: 'WORKSPACE',
        navConnectLabel: 'CONNECT',
        btnLiveErp: 'Connect Tally / Live ERP',
        btnWorkspaceHub: 'OAuth, Digests & Team',
        btnSignIn: 'Sign In',
        btnThemeLabel: 'Theme',
        lblWhereToFocus: 'Where to Focus',
        lblTimeEffort: 'Time & Effort',
        lblNoChangeNeeded: 'No urgent changes needed — numbers look stable.',
        lblAskNewChat: 'New Chat',
        lblBaselineSaved: 'First report saved — upload next month\'s file later to compare progress',
        lblBaselineDesc: 'Next time you upload updated sales/orders, you will see automatically whether problem rates improved or worsened.',
        lblTopDrivers: 'Top AI Drivers:',
        lblCalibrationGap: 'Calibration Gap',
        lblZeroLeakage: 'Zero Post-Event Leakage Verified',
        lblLeakageBlocked: 'Leakage Blocked',
        lblBenefitChance: 'BENEFIT CHANCE',
        lblLossRisk: 'Loss Risk',
        lblSimConfScore: 'Simulation Confidence Score',
        lblExpectedNet: 'Expected Net Impact',
        lblNetAfterCost: 'Net Impact (After Rollout Cost)',
        lblRiskBeforeAfter: 'Risk Rate (Before → After)',
        lblGainTradeoff: 'Gain vs Trade-Off Split',
        lblHonestRange: '95% Honest Range',
        lblOptionDriver: 'Option / Driver',
        lblAiImpact: 'AI Impact %',
        lblDataProof: 'Data Proof',
        lblProjectedImpact: 'Projected Impact',
        lblProvenTag: 'Proven',
        lblNoiseTag: 'Noise / Flat',
        lblEntireBusiness: 'Entire Business (All Rows)',
        lblModelTraining: 'Analyzing business patterns...',
        lblLoadingScenarios: 'Loading smart 1-click decision scenarios from your data...',
        lblLiveJudgeReady: 'Live Data Judge Ready',
        lblWorldLangs: '43 World Languages',
        lblSwitchLang: 'Language',
        lblHealthScore: 'HEALTH / 100',
        ctaFixToday: 'Open Today\'s Action List',
        ctaTestIdea: 'Test a Business Idea',
        kpiHealthyRate: 'Running Smoothly',
        kpiProblemRate: 'Problem Rate',
        kpiQuickSavings: 'Quick Savings',
        kpiFixableCases: 'Fixable Cases',
        chartLeaksTitle: 'Where Problems Happen Most',
        chartLeaksSub: 'Comparing each group against your business average',
        chartRoadmapTitle: 'Fastest Ways to Improve',
        chartRoadmapSub: 'Click any option to see exact profit in the calculator',
        statusHealthy: 'Strong Health',
        statusAttention: 'Needs Attention',
        statusUrgent: 'Urgent Leaks',
        lblRecordsChecked: 'records checked',
        lblAtRiskAcross: 'at risk across',
        lblProblemCasesFound: 'problem cases found',
        lblCasesWord: 'cases',
        lblTopPriorityPrefix: 'Top priority:',
        lblAvgPrefix: 'Avg:',
        lblHealthyShort: 'Healthy:',
        lblAtRiskShort: 'At Risk:',
        lblSimulateShort: 'Simulate →',
        lblUploadCategory: 'Business Category (Optional — Auto-Detected):',
        lblConfirmCat: '1. Business Category',
        lblConfirmSubCat: '2. Sub-Category / Focus',
        lblConfirmTarget: '3. Problem / Return / Cancel Column',
        lblConfirmCost: '4. Bill / Amount / Money Column',
        lblConfirmLang: '5. Summary Language',
        simGrossLbl: 'Money Saved',
        simBasedOnPrefix: 'BASED ON:',
        simAtRiskSuffix: 'AT RISK',
        simReductionWord: 'Reduction'
      },
      hi: {
        brandSubtitle: 'आसान बिज़नेस डॉक्टर',
        lblReport: 'रिपोर्ट बदलें',
        btnNewUpload: 'डेटा अपलोड',
        btnSettings: 'सेटिंग्स',
        sealVerified: '100% असली डेटा वेरिफ़ाइड',
        eyebrowUpload: 'स्टेप 1 · अपनी बिज़नेस फ़ाइल जोड़ें',
        heroHeading: '30 सेकंड में पकड़ें आपका बिज़नेस पैसा कहाँ खो रहा है।',
        heroLead: 'अपनी Sales, Orders, Invoices या Customers की Excel/CSV फ़ाइल डालें। कोई कोडिंग या फ़ॉर्मूला नहीं चाहिए — सीधे देखें सबसे बड़ा नुकसान, आज की कॉल लिस्ट और कितनी बचत हो सकती है।',
        dropTitle: 'अपनी Excel या CSV फ़ाइल यहाँ छोड़ें, या क्लिक करके चुनें',
        dropSub: 'एक शीट या आपस में जुड़ी कई शीट्स (Orders + Customers) दोनों चलेंगी। 100% सुरक्षित और निजी।',
        btnPickFile: 'कंप्यूटर से फ़ाइल चुनें',
        ben1Title: '100% असली हिसाब',
        ben1Sub: 'हर रुपया सीधे आपकी शीट से गिना जाता है। कोई अंदाज़ा नहीं।',
        ben2Title: 'सीधी सरल भाषा',
        ben2Sub: 'पूरी रिपोर्ट आसान हिन्दी या अंग्रेज़ी में समझें।',
        ben3Title: 'आज का काम तैयार',
        ben3Sub: 'टीम को देने के लिए प्रायोरिटी ग्राहक लिस्ट तुरंत मिलती है।',
        eyebrowConnect: 'या 1 क्लिक में सीधे कनेक्ट करें',
        eyebrowDemoConnectors: 'लाइव सिंक या सैंपल डेमो आज़माएँ',
        btnLoadSheet: 'शीट लोड करें',
        eyebrowExamples: 'पहले डेमो देखना चाहते हैं?',
        examplesTitle: 'असली बिज़नेस उदाहरण आज़माएँ (1-क्लिक)',
        examplesLead: 'अपना डेटा डालने से पहले देखना है कि रिपोर्ट कैसी दिखती है? नीचे किसी भी उदाहरण पर क्लिक करें:',
        lblRows: 'कुल रिकॉर्ड:',
        lblIssues: 'समस्या के केस:',
        lblRiskMoney: 'खतरे में पैसा:',
        btnWhatsAppBrief: 'संक्षेप',
        btnPrintPdf: 'PDF',
        btnFullVisual: 'चार्ट',
        btnProof: 'सबूत',
        tabOverview: 'बिज़नेस हेल्थ',
        tabActions: 'कॉल लिस्ट',
        tabCalculator: 'बचत कैलकुलेटर',
        tabAsk: 'AI से पूछें',
        tabPredict: 'फ़ैसला जाँचें',
        tabBoardroom: 'बोर्डरूम जज',
        boardroomEyebrow: 'AI बिज़नेस सलाहकार · टीम की बहस और फ़ैसले की जाँच',
        boardroomTitle: 'अपनी मन की बात या टीम की बहस को असली डेटा से जज करवाएँ',
        boardroomLead: 'कोई भी बिज़नेस आइडिया, बजट प्रस्ताव या टीम की बहस सीधी भाषा में लिखें या बोलें — डेटा से साफ़ जानें क्या सच है, क्या गलत/ख़तरनाक है, और क्या डेटा में दर्ज नहीं है।',
        boardroomHint: 'लगातार सवाल-जवाब, ₹/$ बजट चेक, Option A बनाम B बहस और सभी 43 भाषाओं में काम करता है।',
        btnBoardroomAsk: 'बोर्डरूम जज से फ़ैसला लें',
        boardroomProvenTitle: 'डेटा से क्या सही साबित हुआ',
        boardroomWrongTitle: 'क्या गलत / ख़तरनाक / भ्रम है',
        boardroomBlindTitle: 'डेटा क्या नहीं देख सकता (ईमानदार सीमा)',
        boardroomPlanTitle: 'अगले 14 दिन का सुरक्षित एक्शन प्लान',
        boardroomCopyMemo: 'WhatsApp मेमो कॉपी करें',
        eyebrowCheck: 'शुरू करने से पहले एक नज़र',
        eyebrowPredict: 'फ़ैसला सिमुलेटर · खर्च करने से पहले असर जाँचें',
        predictTitle: 'कोई भी फ़ैसला लेने से पहले उसका असर जाँचें',
        predictLead: 'नीचे 1-क्लिक विकल्प चुनें या सीधी हिन्दी/अंग्रेज़ी में अपना बदलाव लिखें — जानें फ़ायदे की कितनी % संभावना है, कहाँ जीत होगी, कहाँ असर नहीं होगा और नुकसान क्यों हो सकता है।',
        btnPredictNow: 'असर जाँचें',
        predictCustomToggle: '🎛️ या खुद अपना बदलाव चुनें (कोई भी बिज़नेस फ़ैक्टर और असर टेस्ट करें)',
        lblPredictCol: '1. क्या बदलना चाहते हैं?',
        lblPredictAct: '2. बदलाव का तरीका',
        lblPredictFrom: '3. अभी का मान',
        lblPredictTo: '4. किसमें बदलना है',
        lblPredictScope: 'वैकल्पिक: सिर्फ़ किसी खास स्टोर/ग्रुप पर',
        btnTestCustom: 'इस बदलाव को टेस्ट करें',
        predHelpsEye: 'कहाँ सबसे ज़्यादा फ़ायदा होगा',
        predHelpsTitle: '✅ यहाँ जीत होगी',
        predNoHelpEye: 'कहाँ ज़्यादा असर नहीं होगा',
        predNoHelpTitle: '⚠️ कम / शून्य फ़ायदे वाले हिस्से',
        predRisksEye: 'ईमानदार रिस्क जाँच',
        predRisksTitle: '🔍 नुकसान हुआ तो क्यों होगा?',
        lblRolloutCost: '💰 खर्च (वैकल्पिक):',
        predCmpEye: 'टेस्ट किए गए फ़ैसलों की तुलना',
        predCmpTitle: '⚖️ सभी फ़ैसलों का तुलनात्मक स्कोरकार्ड',
        cmpColDec: 'टेस्ट किया फ़ैसला',
        cmpColVer: 'निष्कर्ष',
        cmpColProb: 'फ़ायदा %',
        cmpColConf: 'भरोसा स्कोर',
        cmpColNet: 'शुद्ध असर',
        cmpColCi: '95% ईमानदार रेंज',
        btnAddCombo: 'कॉम्बो जोड़ें',
        btnRunCombo: 'कॉम्बो टेस्ट करें',
        btnCommitTrack: 'कमिट व ट्रैक करें',
        btnWaMemo: 'WhatsApp मेमो',
        btnPrintMemo: 'बोर्ड PDF प्रिंट',
        predTrackEye: 'अनुमान बनाम असली परिणाम ट्रैकर',
        predTrackTitle: '🎯 क्या हमारा अनुमान असल में सच निकला?',
        eyebrowTrend: 'पिछली रिपोर्ट के मुकाबले बदलाव',
        lblRateChange: 'समस्या दर में बदलाव',
        lblMoneyChange: 'औसत ऑर्डर बदलाव',
        card1Title: '01 · आपका सबसे मज़बूत हिस्सा',
        card1Foot: 'इसे बिल्कुल न बदलें',
        card2Title: '02 · सबसे बड़ा आर्थिक नुकसान',
        card2Foot: 'सबसे पहले इसे ठीक करें',
        card3Title: '03 · खतरे की लाल सीमा',
        card3Foot: 'इस सीमा से बचें',
        card4Title: '04 · अगले 30 दिन की बचत',
        card4Foot: 'रिकवरी का मौका',
        eyebrowPlans: 'ठीक करने के 3 ईमानदार रास्ते',
        clickSimulate: 'क्लिक करके बचत देखें',
        plansTitle: 'अपनी पसंद का सुधार प्लान चुनें',
        plansLead: 'हम कोई एक फ़ैसला ज़बरदस्ती नहीं थोपते। किसी भी प्लान पर क्लिक करके कैलकुलेटर में सटीक बचत देखें:',
        eyebrowStory: 'पूरे बिज़नेस की कहानी',
        storyTitle: 'आसान भाषा में पूरी रिपोर्ट',
        eyebrowRoi: 'आपकी बचाई हुई रकम',
        lblActionsDone: 'किए गए एक्शन:',
        lblRoiMult: 'प्लान रिटर्न:',
        roiHelpText: 'जब आपकी टीम किसी ग्राहक से बात कर ले, तो नीचे "कॉल/एक्शन लें" दबाएँ — आपकी बचत यहाँ जुड़ती जाएगी।',
        btnDownloadList: 'Excel/CSV लिस्ट डाउनलोड करें',
        eyebrowQueue: 'टीम के लिए आज की सूची',
        worklistTitle: 'आज इन ग्राहकों / ऑर्डर्स पर तुरंत काम करें',
        fltAll: 'सभी केस',
        fltPrev: '🟡 नुकसान से पहले बचाएँ',
        fltRec: '🔴 डूबा पैसा वापस लाएँ',
        colPriority: 'ज़रूरत',
        colChance: 'खतरा %',
        colMoney: 'खतरे में रकम',
        colWhy: 'खतरा क्यों है',
        colDo: 'अगला कदम',
        colBtn: 'एक्शन',
        eyebrowSim: 'बचत कैलकुलेटर (WHAT-IF)',
        simTitle: 'अंदाज़ा लगाएँ कितना मुनाफ़ा वापस आएगा',
        simLead: 'स्लाइडर घुमाकर जाँचें: "अगर हम मुख्य समस्या X% कम करें और Y बजट खर्च करें, तो जेब में कितना शुद्ध मुनाफ़ा बचेगा?"',
        simSlider1: 'समस्या कितने % कम करनी है?',
        simSlider2: 'महीने का टीम / सुधार खर्च',
        simNetLbl: 'शुद्ध मुनाफ़ा (Net)',
        simNewRateLbl: 'नई समस्या दर',
        eyebrowBreak: 'ग्रुप और कैटेगरी हिसाब',
        breakTitle: 'किस कैटेगरी / शहर में सबसे ज़्यादा नुकसान है?',
        brkColGroup: 'ग्रुप / कैटेगरी',
        brkColVol: 'कुल ऑर्डर',
        brkColFail: 'खराब केस',
        brkColRate: 'समस्या दर %',
        brkColShare: 'कुल नुकसान में हिस्सा',
        brkColMoney: 'खतरे में पैसा',
        brkColHealth: 'हालत',
        brkColWhy: 'वजह देखें',
        eyebrowAsk: 'अपनी भाषा में सवाल पूछें',
        askTitle: 'बिज़नेस से जुड़ा कोई भी सवाल पूछें',
        askLead: 'नीचे अपना सवाल लिखें या तैयार बटन दबाएँ — जवाब आपके असली डेटा से तुरंत मिलेगा:',
        btnGetAnswer: 'सत्यापित जवाब देखें',
        navMenuLabel: 'वर्कस्पेस',
        navConnectLabel: 'कनेक्ट करें',
        btnLiveErp: 'Tally / Live ERP जोड़ें',
        btnWorkspaceHub: 'OAuth, Digests और टीम',
        btnSignIn: 'साइन इन करें',
        btnThemeLabel: 'थीम',
        lblWhereToFocus: 'कहाँ फोकस करें',
        lblTimeEffort: 'समय और मेहनत',
        lblNoChangeNeeded: 'बिज़नेस बिल्कुल स्थिर चल रहा है।',
        lblAskNewChat: 'नई चैट',
        lblBaselineSaved: 'पहली रिपोर्ट सेव हो गई है — अगली बार नया डेटा डालने पर तुलना दिखेगी',
        lblBaselineDesc: 'आगे जब आप अगले महीने की शीट डालेंगे, तो सिस्टम खुद बताएगा कि नुकसान बढ़ा या कम हुआ।',
        lblTopDrivers: 'मुख्य AI कारण:',
        lblCalibrationGap: 'कैलिब्रेशन अंतर',
        lblZeroLeakage: 'ज़ीरो डेटा लीकेज वेरिफ़ाइड',
        lblLeakageBlocked: 'पोस्ट-इवेंट लीकेज रोका गया',
        lblBenefitChance: 'फ़ायदे का चांस',
        lblLossRisk: 'नुकसान का ख़तरा',
        lblSimConfScore: 'सिमुलेशन भरोसा स्कोर',
        lblExpectedNet: 'अनुमानित शुद्ध असर',
        lblNetAfterCost: 'खर्च काटकर शुद्ध लाभ',
        lblRiskBeforeAfter: 'रिस्क रेट (पहले → बाद में)',
        lblGainTradeoff: 'बचत बनाम ट्रेड-ऑफ़',
        lblHonestRange: '95% ईमानदार रेंज',
        lblOptionDriver: 'विकल्प / कारण',
        lblAiImpact: 'AI असर %',
        lblDataProof: 'डेटा सबूत',
        lblProjectedImpact: 'अनुमानित असर',
        lblProvenTag: 'साबित',
        lblNoiseTag: 'असर नहीं',
        lblEntireBusiness: 'पूरा बिज़नेस (सभी रिकॉर्ड्स)',
        lblModelTraining: 'आपके डेटा पैटर्न का विश्लेषण हो रहा है...',
        lblLoadingScenarios: 'डेटा से स्मार्ट निर्णय विकल्प तैयार हो रहे हैं...',
        lblLiveJudgeReady: 'लाइव डेटा जज तैयार',
        lblWorldLangs: '43 वैश्विक भाषाएँ',
        lblSwitchLang: 'भाषा',
        lblHealthScore: 'हेल्थ / 100',
        ctaFixToday: 'आज की एक्शन लिस्ट खोलें',
        ctaTestIdea: 'नया आइडिया टेस्ट करें',
        kpiHealthyRate: 'बिल्कुल ठीक चल रहा है',
        kpiProblemRate: 'समस्या / नुकसान दर',
        kpiQuickSavings: 'तुरंत बचत का मौका',
        kpiFixableCases: 'सुधारे जा सकने वाले केस',
        chartLeaksTitle: 'सबसे ज़्यादा समस्या कहाँ हो रही है',
        chartLeaksSub: 'हर ग्रुप की तुलना आपके बिज़नेस औसत से',
        chartRoadmapTitle: 'सुधार के सबसे तेज़ 3 रास्ते',
        chartRoadmapSub: 'किसी भी प्लान पर क्लिक करके सटीक मुनाफा देखें',
        statusHealthy: 'बढ़िया स्थिति',
        statusAttention: 'ध्यान देने की ज़रूरत',
        statusUrgent: 'तुरंत सुधार ज़रूरी',
        lblRecordsChecked: 'रिकॉर्ड जाँचे गए',
        lblAtRiskAcross: 'खतरे में — कुल',
        lblProblemCasesFound: 'समस्या के केस मिले',
        lblCasesWord: 'केस',
        lblTopPriorityPrefix: 'सबसे पहले यह ठीक करें:',
        lblAvgPrefix: 'औसत:',
        lblHealthyShort: 'सुरक्षित:',
        lblAtRiskShort: 'खतरे में:',
        lblSimulateShort: 'बचत देखें →',
        lblUploadCategory: 'बिज़नेस कैटेगरी (वैकल्पिक — ऑटो-डिटेक्ट होगी):',
        lblConfirmCat: '1. बिज़नेस कैटेगरी',
        lblConfirmSubCat: '2. सब-कैटेगरी / प्रकार',
        lblConfirmTarget: '3. समस्या / रिटर्न / कैंसल कॉलम',
        lblConfirmCost: '4. बिल / राशि / पैसा कॉलम',
        lblConfirmLang: '5. रिपोर्ट की भाषा',
        simGrossLbl: 'अनुमानित बचत',
        simBasedOnPrefix: 'आधार:',
        simAtRiskSuffix: 'खतरे में',
        simReductionWord: 'कमी'
      }
    };

    function tUi(key, fallback = '') {
      const lang = appState.briefLanguage || 'en';
      const dict = i18nDict[lang] || i18nDict.en || {};
      if (dict[key]) return dict[key];
      if (lang === 'hi' && i18nDict.hi && i18nDict.hi[key]) return i18nDict.hi[key];
      if (i18nDict.en && i18nDict.en[key]) return i18nDict.en[key];
      return fallback || key;
    }

    const RTL_LANG_CODES = new Set(['ar', 'ur', 'he', 'fa']);

    function _syncLanguageSelectors(lang, statusMsg) {
      const btnEn = document.getElementById('btnGlobalEn');
      const btnHi = document.getElementById('btnGlobalHi');
      const bEn = document.getElementById('btnBriefEn');
      const bHi = document.getElementById('btnBriefHi');
      if (btnEn) btnEn.classList.toggle('active', lang === 'en');
      if (btnHi) btnHi.classList.toggle('active', lang === 'hi');
      if (bEn) bEn.classList.toggle('active', lang === 'en');
      if (bHi) bHi.classList.toggle('active', lang === 'hi');

      const gSel = document.getElementById('globalLanguageSelect');
      const bSel = document.getElementById('briefLanguageSelect');
      if (gSel && gSel.value !== lang) gSel.value = lang;
      if (bSel && bSel.value !== lang) bSel.value = lang;

      const meta = (appState.worldLanguages || []).find(l => l.code === lang);
      const isRtl = meta ? meta.dir === 'rtl' : RTL_LANG_CODES.has(lang);
      document.documentElement.setAttribute('dir', isRtl ? 'rtl' : 'ltr');
      document.documentElement.setAttribute('lang', lang);

      const badgeEl = document.getElementById('globalLangBadge');
      if (badgeEl) {
        badgeEl.textContent = statusMsg || `${lang.toUpperCase()}${isRtl ? ' · RTL' : ''}`;
      }
    }

    function _applyUiDictionary(lang) {
      const dict = i18nDict[lang] || i18nDict.en;
      document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (dict[key]) el.textContent = dict[key];
      });
    }

    async function initGlobalLanguages() {
      try {
        const res = await fetch('/api/v1/i18n/languages');
        if (!res.ok) return;
        const data = await res.json();
        const langs = data.languages || [];
        if (!langs.length) return;
        appState.worldLanguages = langs;

        const regions = [];
        const byRegion = {};
        langs.forEach(l => {
          const r = l.region || 'Global';
          if (!byRegion[r]) {
            byRegion[r] = [];
            regions.push(r);
          }
          byRegion[r].push(l);
        });

        const buildOptions = () => regions.map(r => {
          const opts = byRegion[r].map(l => {
            const rtlTag = l.dir === 'rtl' ? ' · RTL' : '';
            let label;
            if (l.code === 'en') {
              label = `${l.native} (Global)`;
            } else if (l.code === 'hi') {
              label = 'हिन्दी / Hinglish';
            } else if (String(l.native || '').toLowerCase() === String(l.name || '').toLowerCase()) {
              label = `${l.native}${rtlTag}`;
            } else {
              label = `${l.native} (${l.name}${rtlTag})`;
            }
            return `<option value="${escapeHtml(l.code)}">${escapeHtml(label)}</option>`;
          }).join('');
          return `<optgroup label="${escapeHtml(r)}">${opts}</optgroup>`;
        }).join('');

        const htmlOpts = buildOptions();
        const gSel = document.getElementById('globalLanguageSelect');
        const bSel = document.getElementById('briefLanguageSelect');
        const cSel = document.getElementById('copilotLangSelect');
        if (gSel) gSel.innerHTML = htmlOpts;
        if (bSel) bSel.innerHTML = htmlOpts;
        if (cSel) cSel.innerHTML = htmlOpts;

        const st = document.getElementById('globalLangStatus');
        if (st && st.firstElementChild) {
          st.firstElementChild.textContent = `🌐 ${langs.length} World Languages`;
        }

        const activeLang = appState.briefLanguage || 'en';
        _syncLanguageSelectors(activeLang);
        if (activeLang !== 'en' && activeLang !== 'hi' && !appState.activeRunId && !i18nDict[activeLang]) {
          setGlobalLanguage(activeLang);
        }
      } catch (e) {
        // Fallback options already embedded in HTML
      }
    }

    async function initBusinessCategories() {
      try {
        const res = await fetch('/api/v1/categories');
        if (!res.ok) return;
        const data = await res.json();
        const cats = data.categories || [];
        if (!cats.length) return;
        appState.businessCategories = cats;
        populateCategoryDropdowns();
      } catch (e) {}
    }

    function populateCategoryDropdowns(selectedCat = null, selectedSub = null) {
      const cats = appState.businessCategories || [];
      if (!cats.length) return;
      const isHi = appState.briefLanguage === 'hi';
      const buildCatOpts = (cur) => cats.map(c => {
        const lbl = `${c.icon || ''} ${isHi ? (c.name_hi || c.name_en) : c.name_en}`;
        return `<option value="${escapeHtml(c.id)}" ${c.id === cur ? 'selected' : ''}>${escapeHtml(lbl)}</option>`;
      }).join('');

      const upSel = document.getElementById('uploadCategorySelect');
      if (upSel) {
        const prev = upSel.value || 'auto';
        upSel.innerHTML = buildCatOpts(prev);
      }
      const cfSel = document.getElementById('confirmCategorySelect');
      if (cfSel) {
        const targetVal = selectedCat || cfSel.value || 'auto';
        cfSel.innerHTML = buildCatOpts(targetVal);
        populateSubCategoryDropdown(targetVal, selectedSub);
      }
    }

    function populateSubCategoryDropdown(catId, selectedSub = null) {
      const subSel = document.getElementById('confirmSubCategorySelect');
      if (!subSel) return;
      const isHi = appState.briefLanguage === 'hi';
      const found = (appState.businessCategories || []).find(c => c.id === catId) || (appState.businessCategories || [])[0];
      const subs = (found && found.sub_categories) || [{ id: 'general', name_en: 'General Operations', name_hi: 'सामान्य संचालन' }];
      subSel.innerHTML = subs.map(s => {
        const lbl = isHi ? (s.name_hi || s.name_en) : s.name_en;
        return `<option value="${escapeHtml(s.id)}" ${s.id === selectedSub ? 'selected' : ''}>${escapeHtml(lbl)}</option>`;
      }).join('');
    }

    async function setGlobalLanguage(lang) {
      const code = String(lang || 'en').trim() || 'en';
      const cacheKey = `${appState.activeRunId || 'none'}::${code}`;
      if (appState.inFlightLangKey === cacheKey) {
        return; // Deduplicate simultaneous duplicate request for the exact same run+language
      }
      const reqId = ++appState.langRequestSeq;
      appState.briefLanguage = code;
      try { localStorage.setItem('dataxray_lang', code); } catch (e) {}

      const copilotSel = document.getElementById('copilotLangSelect');
      if (copilotSel) {
        const hasOpt = Array.from(copilotSel.options || []).some(o => o.value === code);
        copilotSel.value = hasOpt ? code : (code === 'hi' ? 'hi' : 'en');
      }

      // Invalidate tab-level language caches so Decision Lab & Boardroom refresh in new language
      appState.boardroomStartersRunId = null;
      appState.predictOverviewRunId = null;

      // Fast instant path for built-in English & Hindi
      if (code === 'en' || code === 'hi') {
        appState.inFlightLangKey = null;
        _syncLanguageSelectors(code);
        _applyUiDictionary(code);
        if (appState.rankedLeaksRaw) {
          appState.rankedLeaks = appState.rankedLeaksRaw;
        }
        if (appState.executivePulse) {
          renderOwnerCardsAndPlans();
          switchBriefLanguage(code);
          renderCohortExplorer((appState.executivePulse || {}).cohort_breakdowns || []);
          renderWorklistTable();
        }
        if (appState.activeTab === 'predict') {
          loadDecisionPredictorOverview(true);
        } else if (appState.predictOverview) {
          renderDecisionPredictorOverview(appState.predictOverview);
        }
        if (appState.predictLastResult) renderDecisionSimulationResult(appState.predictLastResult);
        if (appState.predictCommitmentsData) renderPredictCommitments();
        if (appState.activeTab === 'boardroom') {
          loadBoardroomStarters(true);
          renderBoardroomFeed();
        }
        return;
      }

      // Worldwide 41 additional languages (with v2 GTX disk & memory cache + number-lock!)
      const meta = (appState.worldLanguages || []).find(l => l.code === code);
      const niceName = meta ? `${meta.flag} ${meta.native}` : code.toUpperCase();

      _syncLanguageSelectors(code, '⏳...');
      if (!appState.translatedSummaries[cacheKey]) {
        showToast(`🌐 Translating into ${niceName}...`, 'info', 'lang-status');
      }

      appState.inFlightLangKey = cacheKey;
      try {
        if (appState.activeRunId && !appState.translatedSummaries[cacheKey]) {
          const res = await apiFetch(`/api/v1/i18n/translate-run/${encodeURIComponent(appState.activeRunId)}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ target_lang: code, ui_dict: i18nDict.en })
          });
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          const data = await res.json();
          if (reqId !== appState.langRequestSeq) return; // Stale request ignored

          if (data.ui_dict) i18nDict[code] = { ...i18nDict.en, ...data.ui_dict };
          if (data.owner_friendly && appState.executivePulse) {
            appState.executivePulse.owner_friendly = appState.executivePulse.owner_friendly || {};
            appState.executivePulse.owner_friendly[code] = data.owner_friendly;
          }
          if (data.ranked_leaks) {
            appState.translatedRankedLeaks[cacheKey] = data.ranked_leaks;
          }
          if (data.summary_markdown) {
            appState.translatedSummaries[cacheKey] = data.summary_markdown;
          }
          if (data.engine === 'offline_fallback') {
            showToast(`Offline mode: showing English fallback for ${niceName}`, 'warn', 'lang-status');
          } else {
            showToast(`✅ Translated into ${niceName} (100% numbers verified)`, 'success', 'lang-status');
          }
        } else if (!appState.activeRunId && !i18nDict[code]) {
          const res = await apiFetch('/api/v1/i18n/translate-ui', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ target_lang: code, ui_dict: i18nDict.en })
          });
          if (res.ok) {
            const data = await res.json();
            if (reqId !== appState.langRequestSeq) return;
            if (data.ui_dict) i18nDict[code] = { ...i18nDict.en, ...data.ui_dict };
          }
        }
      } catch (err) {
        if (reqId !== appState.langRequestSeq) return;
        showToast(`Could not translate into ${niceName}: ${err.message}`, 'warn', 'lang-status');
      } finally {
        if (appState.inFlightLangKey === cacheKey) {
          appState.inFlightLangKey = null;
        }
      }

      if (reqId !== appState.langRequestSeq) return;
      _syncLanguageSelectors(code);
      _applyUiDictionary(code);

      if (appState.translatedRankedLeaks[cacheKey]) {
        appState.rankedLeaks = appState.translatedRankedLeaks[cacheKey];
      }
      if (appState.executivePulse) {
        renderOwnerCardsAndPlans();
        switchBriefLanguage(code);
        renderCohortExplorer((appState.executivePulse || {}).cohort_breakdowns || []);
        renderWorklistTable();
      }
      if (appState.activeTab === 'predict') {
        loadDecisionPredictorOverview(true);
      } else if (appState.predictOverview) {
        renderDecisionPredictorOverview(appState.predictOverview);
      }
      if (appState.predictLastResult) renderDecisionSimulationResult(appState.predictLastResult);
      if (appState.predictCommitmentsData) renderPredictCommitments();
      if (appState.activeTab === 'boardroom') {
        loadBoardroomStarters(true);
        renderBoardroomFeed();
      }
    }

    function toggleTheme() {
      const next = appState.theme === 'dark' ? 'light' : 'dark';
      setAppStudioTheme(next);
    }

    function switchWorkspaceTab(tabName, btnEl) {
      appState.activeTab = tabName;
      document.querySelectorAll('.main-tab-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.tab === tabName);
      });
      document.querySelectorAll('.tab-panel').forEach(p => {
        p.classList.toggle('hidden', p.id !== `tabPanel-${tabName}`);
      });
      if (tabName === 'predict') {
        loadDecisionPredictorOverview(false);
      } else if (tabName === 'boardroom') {
        loadBoardroomStarters(false);
      }
      const sb = document.getElementById('appSidebar');
      if (sb) sb.classList.remove('mobile-open');
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    function toggleMobileSidebar() {
      const sb = document.getElementById('appSidebar');
      if (sb) sb.classList.toggle('mobile-open');
    }

    function openSettingsModal() {
      document.getElementById('settingsModal').classList.remove('hidden');
    }

    function closeSettingsModal() {
      document.getElementById('settingsModal').classList.add('hidden');
    }

    // =========================================================================
    // MULTI-TENANT JWT AUTH, API KEY AUTH & GEO-ADAPTATION HELPERS
    // =========================================================================
    let authModalMode = 'login';

    function getSavedJwtToken() {
      try {
        return localStorage.getItem('dataxray_jwt_token') || '';
      } catch (e) {
        return '';
      }
    }

    function getSavedAuthUser() {
      try {
        const raw = localStorage.getItem('dataxray_auth_user');
        return raw ? JSON.parse(raw) : null;
      } catch (e) {
        return null;
      }
    }

    function updateAuthUIState() {
      const user = getSavedAuthUser();
      const token = getSavedJwtToken();
      const btnLabel = document.getElementById('authBtnLabel');
      const loggedBox = document.getElementById('authLoggedInBox');
      const formBox = document.getElementById('authFormContainer');
      const tenantInput = document.getElementById('tenantInput');

      if (token && user) {
        if (btnLabel) btnLabel.textContent = user.workspace_name || user.email || 'Workspace';
        if (loggedBox) loggedBox.classList.remove('hidden');
        if (formBox) formBox.classList.add('hidden');
        const emailEl = document.getElementById('authSignedInEmail');
        const tenEl = document.getElementById('authSignedInTenant');
        if (emailEl) emailEl.textContent = user.email || '';
        if (tenEl) tenEl.textContent = `Isolated Workspace ID: ${user.tenant_id || ''}`;
        if (tenantInput && user.tenant_id) {
          tenantInput.value = user.tenant_id;
          appState.activeTenant = user.tenant_id;
        }
      } else {
        if (btnLabel) btnLabel.textContent = 'Sign In';
        if (loggedBox) loggedBox.classList.add('hidden');
        if (formBox) formBox.classList.remove('hidden');
      }
    }

    function openAuthModal() {
      updateAuthUIState();
      document.getElementById('authModal').classList.remove('hidden');
    }

    function closeAuthModal() {
      document.getElementById('authModal').classList.add('hidden');
    }

    function switchAuthMode(mode) {
      authModalMode = mode === 'register' ? 'register' : 'login';
      document.getElementById('authTabLogin').classList.toggle('active', authModalMode === 'login');
      document.getElementById('authTabRegister').classList.toggle('active', authModalMode === 'register');
      document.getElementById('authWorkspaceField').classList.toggle('hidden', authModalMode !== 'register');
      document.getElementById('authSubmitBtn').textContent = authModalMode === 'register' ? 'Create Account' : 'Sign In';
      document.getElementById('authModalTitle').textContent = authModalMode === 'register'
        ? '🔐 Create Free Workspace Account'
        : '🔐 Sign In to Your Workspace';
    }

    async function submitAuthForm() {
      const email = (document.getElementById('authEmailInput').value || '').trim();
      const password = document.getElementById('authPasswordInput').value || '';
      const workspaceName = (document.getElementById('authWorkspaceInput').value || '').trim();
      if (!email || !password) {
        showToast('Enter email and password.', 'warn');
        return;
      }

      const btn = document.getElementById('authSubmitBtn');
      btn.disabled = true;
      const endpoint = authModalMode === 'register' ? '/api/v1/auth/register' : '/api/v1/auth/login';
      const bodyPayload = authModalMode === 'register'
        ? { email, password, workspace_name: workspaceName || undefined }
        : { email, password };

      try {
        const res = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(bodyPayload)
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(data.detail || `Auth failed (${res.status})`);
        }
        try {
          localStorage.setItem('dataxray_jwt_token', data.access_token || '');
          localStorage.setItem('dataxray_auth_user', JSON.stringify(data.user || {}));
        } catch (e) {}
        updateAuthUIState();
        closeAuthModal();
        showToast(`Signed in as ${(data.user && data.user.workspace_name) || email}`, 'success');
        refreshTimeMachineRuns();
      } catch (e) {
        showToast(`Sign in error: ${e.message}`, 'error');
      } finally {
        btn.disabled = false;
      }
    }

    function logoutAccount() {
      try {
        localStorage.removeItem('dataxray_jwt_token');
        localStorage.removeItem('dataxray_auth_user');
      } catch (e) {}
      updateAuthUIState();
      closeAuthModal();
      showToast('Signed out cleanly.', 'info');
      refreshTimeMachineRuns();
    }

    function applyRegionAdaptation(regionCode) {
      const r = String(regionCode || 'US').toUpperCase();
      try { localStorage.setItem('dataxray_region', r); } catch (e) {}
      const grid = document.getElementById('connectorGrid');
      if (grid) {
        if (r === 'IN') {
          grid.innerHTML = `
            <button type="button" class="connector-chip" onclick="ingestLiveConnector('shopify_orders_live', 'IN')">
              <span>🛒 Shopify India (COD &amp; RTO)</span>
              <small style="color: var(--accent-amber);">₹ INR · Demo</small>
            </button>
            <button type="button" class="connector-chip" onclick="ingestLiveConnector('tally_prime_ledger_in', 'IN')">
              <span>📒 Tally Prime Pending Invoices</span>
              <small style="color: var(--accent-amber);">₹ INR · Demo</small>
            </button>
            <button type="button" class="connector-chip" onclick="ingestLiveConnector('razorpay_settlements_in', 'IN')">
              <span>💳 Razorpay Payment Failures</span>
              <small style="color: var(--accent-amber);">₹ INR · Demo</small>
            </button>
            <button type="button" class="connector-chip" onclick="ingestLiveConnector('stripe_saas_churn', 'US')">
              <span>⚡ Stripe SaaS Renewals</span>
              <small style="color: var(--accent-amber);">$ USD · Demo</small>
            </button>
          `;
        } else {
          grid.innerHTML = `
            <button type="button" class="connector-chip" onclick="ingestLiveConnector('shopify_global_orders', 'US')">
              <span>🛒 Shopify Global Orders</span>
              <small style="color: var(--accent-amber);">$ USD · Demo</small>
            </button>
            <button type="button" class="connector-chip" onclick="ingestLiveConnector('quickbooks_ar_invoices', 'EU')">
              <span>📒 QuickBooks / Xero AR</span>
              <small style="color: var(--accent-amber);">€ EUR · Demo</small>
            </button>
            <button type="button" class="connector-chip" onclick="ingestLiveConnector('stripe_saas_churn', 'US')">
              <span>⚡ Stripe SaaS Renewals</span>
              <small style="color: var(--accent-amber);">$ USD · Demo</small>
            </button>
            <button type="button" class="connector-chip" onclick="ingestLiveConnector('shopify_orders_live', 'IN')">
              <span>📦 Shopify India (COD &amp; RTO)</span>
              <small style="color: var(--accent-amber);">₹ INR · Demo</small>
            </button>
          `;
        }
      }
      const digestTitle = document.querySelector('#morningDigestModal h3');
      if (digestTitle) {
        digestTitle.textContent = r === 'IN'
          ? '📲 "Morning Munim-Ji" Daily Summary'
          : '📲 60-Second Morning Executive Brief';
      }
    }

    function getSavedApiKey() {
      try {
        return localStorage.getItem('dataxray_api_key') || '';
      } catch (e) {
        return '';
      }
    }

    function appendApiKeyToUrl(url) {
      if (!url) return url;
      const jwt = getSavedJwtToken();
      if (jwt) {
        const sep = url.includes('?') ? '&' : '?';
        return `${url}${sep}token=${encodeURIComponent(jwt)}`;
      }
      const k = getSavedApiKey();
      if (!k) return url;
      const sep = url.includes('?') ? '&' : '?';
      return `${url}${sep}api_key=${encodeURIComponent(k)}`;
    }

    function openApiKeyModal() {
      const inp = document.getElementById('apiKeyTokenInput');
      if (inp) inp.value = getSavedApiKey();
      document.getElementById('apiKeyModal').classList.remove('hidden');
    }

    function closeApiKeyModal() {
      document.getElementById('apiKeyModal').classList.add('hidden');
    }

    function saveApiKeyToken() {
      const val = (document.getElementById('apiKeyTokenInput').value || '').trim();
      try {
        if (val) localStorage.setItem('dataxray_api_key', val);
        else localStorage.removeItem('dataxray_api_key');
      } catch (e) {}
      closeApiKeyModal();
      showToast(val ? 'Access key saved. Refreshing...' : 'Access key cleared.', 'success');
      if (val) {
        loadCertifiedBenchmark(appState.activeRunId || 'hotel_booking_cancellation');
        refreshTimeMachineRuns();
      }
    }

    function clearSavedApiKey() {
      try {
        localStorage.removeItem('dataxray_api_key');
      } catch (e) {}
      const inp = document.getElementById('apiKeyTokenInput');
      if (inp) inp.value = '';
      closeApiKeyModal();
      showToast('Access key removed.', 'info');
    }

    async function apiFetch(url, options = {}) {
      const opts = { ...options };
      const silentAuth = Boolean(opts.silentAuth);
      delete opts.silentAuth;
      const headers = new Headers(opts.headers || {});
      const jwt = getSavedJwtToken();
      const apiKey = getSavedApiKey();
      if (jwt && !headers.has('Authorization')) {
        headers.set('Authorization', `Bearer ${jwt}`);
      } else if (apiKey && !headers.has('X-API-Key')) {
        headers.set('X-API-Key', apiKey);
      }
      opts.headers = headers;
      const res = await fetch(url, opts);
      if (res.status === 401 && !silentAuth && !url.includes('/api/v1/auth/')) {
        openAuthModal();
        showToast('Sign in or enter Access Key to open private workspace data.', 'warn');
      }
      return res;
    }

    async function copyTextSafe(text, successMsg) {
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          await navigator.clipboard.writeText(text);
          showToast(successMsg, 'success');
          return true;
        }
      } catch (e) {}
      try {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.left = '-9999px';
        document.body.appendChild(ta);
        ta.select();
        const ok = document.execCommand('copy');
        document.body.removeChild(ta);
        if (ok) {
          showToast(successMsg, 'success');
          return true;
        }
      } catch (e) {}
      showToast('Copy blocked by browser.', 'warn');
      return false;
    }

    // =========================================================================
    // TOAST NOTIFICATION SYSTEM
    // =========================================================================
    function showToast(message, level = 'success', replaceTag = null) {
      const container = document.getElementById('toastContainer');
      if (!container) return;
      if (replaceTag) {
        container.querySelectorAll(`[data-toast-tag="${replaceTag}"]`).forEach(oldEl => oldEl.remove());
      }
      // Keep at most 2 visible toasts so screen never clutters
      while (container.children.length >= 2) {
        container.firstElementChild.remove();
      }
      const el = document.createElement('div');
      el.className = `toast-item ${level}`;
      if (replaceTag) el.setAttribute('data-toast-tag', replaceTag);
      el.innerHTML = `
        <span>${escapeHtml(message)}</span>
        <button type="button" style="background:transparent;border:none;color:var(--text-muted);cursor:pointer;font-size:14px;" onclick="this.parentElement.remove()">✕</button>
      `;
      container.appendChild(el);
      setTimeout(() => {
        if (el.parentElement) el.remove();
      }, 4200);
    }

    function escapeHtml(str) {
      if (str === null || str === undefined) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }

    function formatNumberForCurrency(val, sym = '$') {
      const num = Number(val);
      if (!Number.isFinite(num)) return '0';
      return num.toLocaleString(sym === '₹' ? 'en-IN' : 'en-US');
    }

    function formatCurrencyValue(val, sym = '$') {
      const num = Number(val);
      if (!Number.isFinite(num)) return `${sym}0`;
      if (sym === '₹') {
        if (Math.abs(num) >= 10_000_000) return `${sym}${(num / 10_000_000).toFixed(2)} Cr`;
        if (Math.abs(num) >= 100_000) return `${sym}${(num / 100_000).toFixed(2)} L`;
        if (Math.abs(num) >= 1_000) return `${sym}${Math.round(num).toLocaleString('en-IN')}`;
        return `${sym}${num.toFixed(num % 1 === 0 ? 0 : 2)}`;
      }
      if (Math.abs(num) >= 1_000_000) {
        return `${sym}${(num / 1_000_000).toFixed(2)}M`;
      }
      if (Math.abs(num) >= 1_000) {
        return `${sym}${Math.round(num).toLocaleString('en-US')}`;
      }
      return `${sym}${num.toFixed(num % 1 === 0 ? 0 : 2)}`;
    }

    function normalizeIndianRupeesInText(str) {
      if (!str || typeof str !== 'string') return str;
      return str.replace(/₹(\d{1,3}(?:,\d{3})+(?:\.\d+)?)(?![0-9.]|\s*(?:L|Cr|K|M)\b)/g, (full, numPart) => {
        const val = parseFloat(numPart.replace(/,/g, ''));
        if (!Number.isFinite(val)) return full;
        if (Math.abs(val) >= 100_000) {
          return `${formatCurrencyValue(val, '₹')} (₹${Math.round(val).toLocaleString('en-IN')})`;
        }
        return `₹${Math.round(val).toLocaleString('en-IN')}`;
      });
    }

    function renderMarkdownHtml(mdText) {
      if (!mdText) return '<p>No summary available.</p>';
      let normalizedMd = normalizeIndianRupeesInText(String(mdText));
      if (typeof humanizeBusinessText === 'function') {
        normalizedMd = humanizeBusinessText(normalizedMd, appState.briefLanguage === 'hi' ? 'hi' : 'en');
      }
      const lines = normalizedMd.split('\n');
      let html = '';
      let inList = false;

      for (let rawLine of lines) {
        const line = rawLine.trim();
        if (!line) {
          if (inList) { html += '</ul>'; inList = false; }
          continue;
        }
        if (line.startsWith('---')) continue;

        let safe = escapeHtml(line)
          .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
          .replace(/(?<!\*)\*([^*]+?)\*(?!\*)/g, '<em>$1</em>')
          .replace(/`([^`]+)`/g, '<code class="tabular-nums" style="background:var(--bg-elevated);padding:2px 6px;border-radius:4px;color:var(--accent-sky);">$1</code>');

        if (safe.startsWith('### ')) {
          if (inList) { html += '</ul>'; inList = false; }
          html += `<h3>${safe.slice(4)}</h3>`;
        } else if (safe.startsWith('## ')) {
          if (inList) { html += '</ul>'; inList = false; }
          html += `<h2>${safe.slice(3)}</h2>`;
        } else if (safe.startsWith('# ')) {
          if (inList) { html += '</ul>'; inList = false; }
          html += `<h1>${safe.slice(2)}</h1>`;
        } else if (safe.startsWith('&gt; ')) {
          if (inList) { html += '</ul>'; inList = false; }
          html += `<blockquote>${safe.slice(5)}</blockquote>`;
        } else if (safe.startsWith('* ') || safe.startsWith('- ')) {
          if (!inList) { html += '<ul>'; inList = true; }
          html += `<li>${safe.slice(2)}</li>`;
        } else {
          if (inList) { html += '</ul>'; inList = false; }
          html += `<p>${safe}</p>`;
        }
      }
      if (inList) html += '</ul>';
      return html;
    }

    // =========================================================================
    // 1-CLICK CERTIFIED BENCHMARK LOADER
    // =========================================================================
    async function loadCertifiedBenchmark(benchmarkId, autoCollapseUpload = false) {
      try {
        document.querySelectorAll('.benchmark-item').forEach(btn => {
          btn.classList.toggle('active-bench', btn.dataset.bench === benchmarkId);
        });
        const res = await apiFetch(`/api/v1/benchmarks/${encodeURIComponent(benchmarkId)}`);
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `HTTP ${res.status}`);
        }
        const payload = await res.json();
        hydrateExecutiveConsole(payload);
        if (autoCollapseUpload) {
          document.getElementById('onboardingSection').classList.add('hidden');
        }
        showToast(`Loaded: ${payload.benchmark_meta ? payload.benchmark_meta.title : benchmarkId}`, 'success');
      } catch (e) {
        showToast(`Failed to load example: ${e.message}`, 'error');
      }
    }

    function toggleOnboardingPanel() {
      const sec = document.getElementById('onboardingSection');
      const sb = document.getElementById('appSidebar');
      if (sb) sb.classList.remove('mobile-open');
      if (sec) sec.classList.toggle('hidden');
    }

    function closeOnboardingPanel() {
      const sec = document.getElementById('onboardingSection');
      if (sec) sec.classList.add('hidden');
    }

    // =========================================================================
    // ZERO-UPLOAD LIVE ERP CONNECTORS & GOOGLE SHEETS URL INGESTION
    // =========================================================================
    async function ingestLiveConnector(connectorId, defaultRegion = 'IN') {
      const tenant = document.getElementById('tenantInput').value.trim() || 'founder_workspace';
      document.getElementById('regionSelect').value = defaultRegion;
      const progSec = document.getElementById('jobProgressSection');
      progSec.classList.remove('hidden');
      document.getElementById('progressStageName').textContent = `Connecting to ${connectorId}...`;
      document.getElementById('progressBarFill').style.width = '40%';
      document.getElementById('progressPctLabel').textContent = '40%';

      try {
        const res = await apiFetch('/api/v1/connectors/ingest', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            connector_id: connectorId,
            tenant_id: tenant,
            region_profile: defaultRegion
          })
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `Sync failed (${res.status})`);
        }
        const payload = await res.json();
        progSec.classList.add('hidden');
        document.getElementById('onboardingSection').classList.add('hidden');
        hydrateExecutiveConsole(payload);
        document.getElementById('executiveConsole').scrollIntoView({ behavior: 'smooth', block: 'start' });
        showToast(`Connected & analyzed: ${payload.connector_meta ? payload.connector_meta.connector_title : connectorId}`, 'success');
      } catch (e) {
        progSec.classList.add('hidden');
        showToast(`Connection error: ${e.message}`, 'error');
      }
    }

    async function ingestRemoteUrl() {
      const urlInput = document.getElementById('remoteSheetUrlInput');
      const rawUrl = (urlInput.value || '').trim();
      if (!rawUrl) {
        showToast('Paste a Google Sheets link or CSV link first.', 'warn');
        return;
      }
      const tenant = document.getElementById('tenantInput').value.trim() || 'founder_workspace';
      const region = document.getElementById('regionSelect').value || 'US';
      const btn = document.getElementById('btnSyncUrl');
      btn.disabled = true;

      const progSec = document.getElementById('jobProgressSection');
      progSec.classList.remove('hidden');
      document.getElementById('progressStageName').textContent = 'Reading Google Sheet & calculating leaks...';

      try {
        const res = await apiFetch('/api/v1/connectors/ingest', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            data_url: rawUrl,
            tenant_id: tenant,
            region_profile: region
          })
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `Sync failed (${res.status})`);
        }
        const payload = await res.json();
        progSec.classList.add('hidden');
        document.getElementById('onboardingSection').classList.add('hidden');
        hydrateExecutiveConsole(payload);
        showToast('Google Sheet synced and analyzed!', 'success');
      } catch (e) {
        progSec.classList.add('hidden');
        showToast(`Could not load sheet: ${e.message}`, 'error');
      } finally {
        btn.disabled = false;
      }
    }

    // =========================================================================
    // FILE UPLOAD & SIMPLE CONFIRMATION
    // =========================================================================
    const dropzoneEl = document.getElementById('dropzone');
    if (dropzoneEl) {
      dropzoneEl.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzoneEl.classList.add('drag-over');
      });
      dropzoneEl.addEventListener('dragleave', () => {
        dropzoneEl.classList.remove('drag-over');
      });
      dropzoneEl.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzoneEl.classList.remove('drag-over');
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
          if (e.dataTransfer.files.length > 1) {
            triggerMultiIntentHandshake(Array.from(e.dataTransfer.files));
          } else {
            triggerIntentHandshake(e.dataTransfer.files[0]);
          }
        }
      });
    }

