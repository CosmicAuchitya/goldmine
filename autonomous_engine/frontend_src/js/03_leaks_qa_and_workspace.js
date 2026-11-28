    async function loadAndRenderRankedLeaks(runId, inlineData = null) {
      const sec = document.getElementById('rankedLeaksSection');
      if (!sec || !runId) return;
      if (inlineData && Array.isArray(inlineData.top_ranked_leaks)) {
        appState.rankedLeaks = inlineData;
        renderRankedLeaksPanel();
        return;
      }
      try {
        const res = await apiFetch(`/api/v1/ranked-leaks/${encodeURIComponent(runId)}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        appState.rankedLeaks = await res.json();
        renderRankedLeaksPanel();
      } catch (e) {
        sec.classList.add('hidden');
      }
    }

    function formatInlineMd(str) {
      if (str === null || str === undefined) return '';
      return escapeHtml(String(str).replace(/\)\)+/g, ')'))
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/`([^`]+)`/g, '<code style="background:var(--bg-panel);padding:1px 5px;border-radius:4px;font-size:11.5px;">$1</code>');
    }

    function setRankedSeverityFilter(sev) {
      appState.rankedSevFilter = sev || 'ALL';
      appState.rankedShowAll = false;
      renderRankedLeaksPanel();
    }

    function toggleShowAllRankedLeaks() {
      appState.rankedShowAll = !appState.rankedShowAll;
      renderRankedLeaksPanel();
    }

    function _extractRatesForGauge(lk) {
      if (lk && typeof lk.normal_rate_pct === 'number' && typeof lk.here_rate_pct === 'number') {
        return {
          expPct: Math.min(100, Math.max(0, lk.normal_rate_pct)),
          actPct: Math.min(100, Math.max(0, lk.here_rate_pct)),
          mult: typeof lk.risk_multiplier === 'number' ? lk.risk_multiplier : null,
        };
      }
      const expStr = String(lk.expected_standard_en || '');
      const actStr = String(lk.actual_observed_en || '');
      const expM = expStr.match(/(\d+(?:\.\d+)?)%/);
      const actM = actStr.match(/(\d+(?:\.\d+)?)%/);
      const multM = actStr.match(/(\d+(?:\.\d+)?)x/i) || String(lk.headline_en || '').match(/(\d+(?:\.\d+)?)x/i);
      const expPct = expM ? Math.min(100, Math.max(0, parseFloat(expM[1]))) : null;
      const actPct = actM ? Math.min(100, Math.max(0, parseFloat(actM[1]))) : null;
      const mult = multM ? parseFloat(multM[1]) : null;
      return { expPct, actPct, mult };
    }

    function _pctToOutOfTen(pct, lang = 'en') {
      const r = Math.max(0, Math.min(100, Number(pct || 0)));
      if (r >= 97.5) return lang === 'hi' ? 'लगभग सब' : 'almost all';
      if (r >= 45 && r <= 54.9) return lang === 'hi' ? 'हर 2 में 1' : '1 in 2';
      if (r >= 8) {
        const n10 = Math.max(1, Math.min(9, Math.round(r / 10)));
        return lang === 'hi' ? `10 में ${n10}` : `${n10} in 10`;
      }
      return `${r.toFixed(1)}%`;
    }

    function _multToPlainWords(mult, lang = 'en') {
      const m = Number(mult || 1);
      if (m >= 3.4) return lang === 'hi' ? `~${Math.round(m)} गुना ज़्यादा` : `~${Math.round(m)}× usual`;
      if (m >= 2.65) return lang === 'hi' ? 'लगभग 3 गुना ज़्यादा' : 'nearly 3× usual';
      if (m >= 2.25) return lang === 'hi' ? 'लगभग ढाई गुना ज़्यादा' : '~2.5× usual';
      if (m >= 1.75) return lang === 'hi' ? 'लगभग दोगुना' : 'nearly double';
      if (m >= 1.35) return lang === 'hi' ? 'लगभग डेढ़ गुना ज़्यादा' : '~1.5× usual';
      return lang === 'hi' ? 'सामान्य से ज़्यादा' : 'above normal';
    }

    function humanizeBusinessText(raw, lang = 'en') {
      if (raw === null || raw === undefined) return '';
      let s = String(raw).replace(/\)\)+/g, ')');
      // Convert legacy Benford/MAD technical messages into plain shopkeeper combo-basket insight
      if (/benford|बेनफोर्ड|ANOMALOUS_DEVIATION|MAD\s*0\.\d+/i.test(s)) {
        if (/^MAD\s*0\.\d+/i.test(s.trim())) {
          return lang === 'hi' ? 'एक ही प्राइस रेंज में बिल' : 'Single Price Bracket';
        }
        if (/Billing Digit Distribution Deviation|बिलों के आंकड़ों में असामान्य पैटर्न/i.test(s)) {
          return lang === 'hi'
            ? 'ज़्यादातर ऑर्डर एक ही प्राइस रेंज (Single-Item Slab) में सिमटे हैं — कॉम्बो/बंडल से बिल साइज बढ़ाएं'
            : 'Most Orders Are Clustered in One Price Range — Add Combo Bundles to Grow Basket Size';
        }
        if (/Leading Digit-1 share|पहला अंक '1'/i.test(s)) {
          return lang === 'hi'
            ? 'ज़्यादातर ग्राहक एक ही फिक्स्ड रेट का सिंगल आइटम खरीद रहे हैं, जिससे औसत ऑर्डर साइज (AOV) एक ही रेंज में अटका है।'
            : 'Most customers are ordering single fixed-price items from the same price bracket rather than multi-item combos.';
        }
        if (/conforms to Benford|बेनफोर्ड लॉ \(MAD/i.test(s)) {
          return lang === 'hi'
            ? 'सामान्य स्तर: बिलों की रकम सिर्फ़ 1 आइटम तक सीमित न रहकर 2-3 आइटम के कॉम्बो में भी फैली हो'
            : 'Normal Goal: Order values should spread across single items, 2-item combos, and larger baskets';
        }
        if (/Actual:\s*MAD|असल स्थिति:\s*MAD/i.test(s)) {
          return lang === 'hi'
            ? 'यहाँ स्थिति: आधे से ज़्यादा ऑर्डर एक ही शुरुआती प्राइस ब्रैकेट में सिमटे हैं'
            : 'Here: Over half of orders are clustered in a single starting price bracket';
        }
      }
      // Fix legacy unit mismatch on hour-based delay columns (e.g. "**32.32 days** avg `dispatch_delay_hours`")
      if (/hours?\b|_hr\b|_hrs\b/i.test(s)) {
        s = s
          .replace(/(\d+(?:\.\d+)?)\s*days(\**\s+avg\s+(?:`?[A-Za-z0-9_]*hour[A-Za-z0-9_]*`?|Dispatch Delay \(Hours\)))/gi, '$1 hours$2')
          .replace(/(\d+(?:\.\d+)?)\s*days(\**\s+avg\b)/gi, '$1 hours$2')
          .replace(/than\s+(\d+(?:\.\d+)?)\s*days\b/gi, 'than $1 hours')
          .replace(/(\d+(?:\.\d+)?)\s*दिन(\**\s*(?:से|है|औसत))/gi, '$1 घंटे$2');
      }
      // Fix seasonal dispatch delay unit when numeric delay > 15 (hours wrongly tagged 'd')
      s = s.replace(/(dispatch delay[^.\n]{0,45}?)(\d{2,}(?:\.\d+)?)d\b/gi, (m, pre, num) => {
        return parseFloat(num) >= 15 ? `${pre}${num} hrs` : m;
      });
      s = s.replace(/(to\s+)(\d{2,}(?:\.\d+)?)d\b/gi, (m, pre, num) => {
        return parseFloat(num) >= 15 ? `${pre}${num} hrs` : m;
      });
      // Convert mathematical half-open intervals like (29.1, 94.2] into readable ranges
      s = s.replace(/[\(\[]\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*[\)\]]/g, (_, loStr, hiStr) => {
        const loNum = parseFloat(loStr);
        const hiNum = parseFloat(hiStr);
        const loClean = (loNum < 0 && Math.abs(loNum) < 0.05) ? '0' : String(Number(loNum.toFixed(1)));
        const hiClean = String(Number(hiNum.toFixed(1)));
        return lang === 'hi' ? `${loClean} से ${hiClean}` : `${loClean} to ${hiClean}`;
      });
      // Normalize large Western-comma ₹ figures (e.g. ₹1,749,280.47 -> ₹17.49 L) without partial backtracking
      s = s.replace(/₹(\d{1,3}(?:,\d{3})+(?:\.\d+)?)(?![0-9.]|\s*(?:L|Cr|K|M)\b)/g, (full, numPart) => {
        const val = parseFloat(numPart.replace(/,/g, ''));
        if (!Number.isFinite(val)) return full;
        return formatCurrencyValue(val, '₹');
      });
      // Humanize raw snake_case database column identifiers for business owners
      const colAliases = [
        [/`?courier_partner`?/gi, lang === 'hi' ? 'डिलीवरी पार्टनर' : 'Delivery Partner'],
        [/`?fulfillment_partner`?/gi, lang === 'hi' ? 'डिलीवरी पार्टनर' : 'Delivery Partner'],
        [/`?fulfillment_hub`?/gi, lang === 'hi' ? 'वेयरहाउस हब' : 'Warehouse Hub'],
        [/`?fulfillment_warehouse`?/gi, lang === 'hi' ? 'वेयरहाउस' : 'Warehouse Hub'],
        [/`?dispatch_delay_hours`?/gi, lang === 'hi' ? 'डिस्पैच देरी (घंटे)' : 'Dispatch Delay (Hours)'],
        [/`?dispatch_delay_days`?/gi, lang === 'hi' ? 'डिस्पैच देरी (दिन)' : 'Dispatch Delay (Days)'],
        [/`?packaging_box_color`?/gi, lang === 'hi' ? 'पैकेजिंग बॉक्स रंग' : 'Packaging Box Color'],
        [/`?packaging_box_theme`?/gi, lang === 'hi' ? 'पैकेजिंग स्टाइल' : 'Packaging Style'],
        [/`?payment_mode`?/gi, lang === 'hi' ? 'पेमेंट का तरीका' : 'Payment Method'],
        [/`?payment_gateway`?/gi, lang === 'hi' ? 'पेमेंट गेटवे' : 'Payment Method'],
        [/`?retail_format`?/gi, lang === 'hi' ? 'स्टोर फ़ॉर्मेट' : 'Store Format'],
        [/`?customer_state`?/gi, lang === 'hi' ? 'ग्राहक राज्य' : 'Customer State'],
        [/`?city_tier`?/gi, lang === 'hi' ? 'शहर टियर' : 'City Tier'],
        [/`?hub_city`?/gi, lang === 'hi' ? 'हब शहर' : 'Hub City'],
        [/`?supplier_tier`?/gi, lang === 'hi' ? 'सप्लायर टियर' : 'Supplier Tier'],
        [/`?transit_days`?/gi, lang === 'hi' ? 'ट्रांज़िट दिन' : 'Transit Days'],
        [/`?customer_segment`?/gi, lang === 'hi' ? 'ग्राहक प्रकार' : 'Customer Type'],
        [/`?is_rto_or_cancelled`?/gi, lang === 'hi' ? 'रिटर्न / कैंसलेशन' : 'Returns & Cancellations'],
        [/`?net_billed_amount_inr`?/gi, lang === 'hi' ? 'बिल राशि' : 'Billed Amount'],
        [/\bCapEx\b/g, lang === 'hi' ? 'बजट खर्च' : 'Budget'],
        [/\b0%\s*Cartesian\s*Drift\b/gi, lang === 'hi' ? '100% सटीक रिकॉर्ड मिलान' : '100% Exact Record Match'],
        [/\bAdverse\s+Capital\s+Drag\b/gi, lang === 'hi' ? 'खतरे में पैसा' : 'Money at Risk'],
        [/\bAdverse\s+Events\b/gi, lang === 'hi' ? 'समस्या के केस' : 'Problem Cases']
      ];
      colAliases.forEach(([rx, rep]) => { s = s.replace(rx, rep); });

      if (lang === 'hi') {
        s = s
          .replace(/(?:is_repeated_guest\s*में\s*'0'|'0'\s*in\s*Is Repeated Guest)/gi, 'पहली बार आए ग्राहक (New Guests)')
          .replace(/(?:is_repeated_guest\s*में\s*'1'|'1'\s*in\s*Is Repeated Guest)/gi, 'पुराने रिपीट ग्राहक')
          .replace(/(?:total_of_special_requests\s*में\s*'0'|'0'\s*in\s*Total Of Special Requests)/gi, 'बिना स्पेशल रिक्वेस्ट वाली बुकिंग')
          .replace(/(?:distribution_channel\s*में\s*'TA\/TO'|'TA\/TO'\s*in\s*Distribution Channel)/gi, 'ट्रैवल एजेंट बुकिंग (TA/TO)')
          .replace(/(?:deposit_type\s*में\s*'Non Refund'|'Non Refund'\s*in\s*Deposit Type)/gi, 'नॉन-रिफंडेबल बुकिंग')
          .replace(/(?:assigned_room_type\s*में\s*'A'|'A'\s*in\s*Assigned Room Type)/gi, 'रूम टाइप A')
          .replace(/(?:contract\s*में\s*'Month-to-month'|'Month-to-month'\s*in\s*Contract)/gi, 'मासिक प्लान (Month-to-Month)')
          .replace(/Payment_Mode\s*में/gi, 'पेमेंट का तरीका (Payment Mode) में')
          .replace(/Courier_Partner\s*में/gi, 'कूरियर कंपनी (Courier Partner) में')
          .replace(/Product_Item\s*में/gi, 'प्रोडक्ट (Product) में')
          .replace(/Customer_State\s*में/gi, 'राज्य (State) में')
          .replace(/([A-Za-z]+)_([A-Za-z]+)(?=\s*में)/g, '$1 $2')
          .replace(/Statistically proven anomaly driving\s*~?/gi, 'इस एक वजह से सामान्य से ')
          .replace(/attributable excess failures above normal baseline\.?/gi, 'अतिरिक्त समस्या/नुकसान हुए।')
          .replace(/extra cases/gi, 'एक्स्ट्रा केस')
          .replace(/excess cases/gi, 'अतिरिक्त केस')
          .replace(/\s*\(p\s*=\s*[\d.<>= ]+\)/gi, '')
          .replace(/;\s*p\s*=\s*[\d.]+/gi, '');
      } else {
        s = s
          .replace(/'0'\s*in\s*Is Repeated Guest/gi, 'First-Time Guests')
          .replace(/'1'\s*in\s*Is Repeated Guest/gi, 'Returning Guests')
          .replace(/'0'\s*in\s*Total Of Special Requests/gi, 'Bookings With No Special Requests')
          .replace(/'TA\/TO'\s*in\s*Distribution Channel/gi, 'Travel Agent Bookings (TA/TO)')
          .replace(/'Non Refund'\s*in\s*Deposit Type/gi, 'Non-Refundable Bookings')
          .replace(/'A'\s*in\s*Assigned Room Type/gi, 'Room Type A')
          .replace(/'Month-to-month'\s*in\s*Contract/gi, 'Month-to-Month Plans')
          .replace(/Fails at/gi, 'has problems in')
          .replace(/Baseline\)/gi, 'normal)')
          .replace(/Statistically proven anomaly driving\s*~?/gi, 'This single group caused ~')
          .replace(/attributable excess failures above normal baseline\.?/gi, 'extra problem cases above your normal average.')
          .replace(/excess cases/gi, 'extra cases')
          .replace(/has negligible practical separation \([^)]+\)\s*—/gi, 'is working evenly across groups —')
          .replace(/operates uniformly across groups \([^)]+\)\s*—/gi, 'is working normally everywhere —')
          .replace(/Audit '0' workflow rules and prioritize flagged records in Today's Action List\./gi, "Check these bookings early and follow up using Today's Call List.")
          .replace(/Audit '([^']+)' workflow rules and prioritize flagged records in Today's Action List\./gi, "Review '$1' orders early and follow up from Today's Call List.")
          .replace(/\s*\(p\s*=\s*[\d.<>= ]+\)/gi, '')
          .replace(/;\s*p\s*=\s*[\d.]+/gi, '');
      }
      return s;
    }

    function _renderGaugeBar(lk, sevColor, lang = 'en') {
      const { expPct, actPct, mult } = _extractRatesForGauge(lk);
      if (expPct === null || actPct === null) return '';
      const scaleMax = Math.max(100, actPct, expPct);
      const actW = Math.max(4, Math.min(100, (actPct / scaleMax) * 100));
      const basePos = Math.max(2, Math.min(98, (expPct / scaleMax) * 100));
      const normRatio = (lang === 'hi' ? lk.normal_ratio_hi : lk.normal_ratio_en) || _pctToOutOfTen(expPct, lang);
      const hereRatio = (lang === 'hi' ? lk.here_ratio_hi : lk.here_ratio_en) || _pctToOutOfTen(actPct, lang);
      const multPlain = (lang === 'hi' ? lk.mult_phrase_hi : lk.mult_phrase_en) || (mult ? _multToPlainWords(mult, lang) : '');
      const multChip = multPlain
        ? `<span style="color:var(--text-muted);margin:0 4px;">·</span><span style="font-weight:800;color:${sevColor};">${escapeHtml(multPlain)}</span>`
        : '';
      const lblNorm = lang === 'hi' ? 'सामान्य जगह:' : tUi('normally', 'Normally:');
      const lblHere = lang === 'hi' ? 'यहाँ:' : tUi('here', 'Here:');
      return `
        <div class="exc-gauge-box">
          <div class="exc-gauge-labels">
            <span style="color:var(--text-muted);">${escapeHtml(lblNorm)} <strong style="color:var(--accent-emerald);">${escapeHtml(normRatio)} (${Math.round(expPct)}%)</strong></span>
            <span>${escapeHtml(lblHere)} <strong style="color:${sevColor};">${escapeHtml(hereRatio)} (${Math.round(actPct)}%)</strong>${multChip}</span>
          </div>
          <div class="exc-gauge-track">
            <div class="exc-gauge-base-tick" style="left:${basePos}%;" title="Normal level: ${Math.round(expPct)}%"></div>
            <div class="exc-gauge-fill" style="width:${actW}%;background:${sevColor};"></div>
          </div>
        </div>
      `;
    }

    function renderRankedLeaksPanel() {
      const sec = document.getElementById('rankedLeaksSection');
      const data = appState.rankedLeaks;
      if (!sec || !data) return;
      const allLeaks = data.abnormal_deviations || data.top_ranked_leaks || [];
      const healthy = data.healthy_checks_suppressed || [];
      const shields = data.do_not_spend_shields || [];
      const opps = data.hidden_opportunities || [];
      const packs = data.missing_data_unlock_packs || [];
      if (!allLeaks.length && !healthy.length && !shields.length && !opps.length) {
        sec.classList.add('hidden');
        return;
      }
      sec.classList.remove('hidden');

      const lang = appState.briefLanguage || 'en';
      const titleEl = document.getElementById('rankedLeaksTitle');
      const verdictEl = document.getElementById('rankedVerdictLine');
      const badgeEl = document.getElementById('rankedLeaksBadge');
      const filtersEl = document.getElementById('rankedSeverityFilters');
      const countMetaEl = document.getElementById('rankedCountMeta');
      const heroEl = document.getElementById('rankedHeroSpotlight');
      const listEl = document.getElementById('rankedLeaksList');
      const showAllEl = document.getElementById('rankedShowAllWrap');
      const healthyDetails = document.getElementById('healthyChecksDetails');
      const healthySum = document.getElementById('healthyChecksSummary');
      const healthyList = document.getElementById('healthyChecksList');
      const shieldsEl = document.getElementById('rankedShieldsBox');
      const oppsEl = document.getElementById('rankedOppsBox');
      const unlockEl = document.getElementById('rankedUnlockStrip');
      const s = data.summary || {};

      const isFinLeak = Boolean(data.is_financial);
      if (titleEl) {
        if (isFinLeak) {
          titleEl.textContent = lang === 'hi'
            ? 'आपके बिज़नेस में कहाँ नुकसान हो रहा है (इन्हें पहले सुधारें)'
            : tUi('whereLosingMoney', 'Where Your Business Is Losing Money (Fix These First)');
        } else {
          titleEl.textContent = lang === 'hi'
            ? 'क्वालिटी और कामकाज में सबसे बड़ी कमियाँ कहाँ हैं (इन्हें पहले सुधारें)'
            : tUi('whereQualityBreaking', 'Where Quality & Operations Are Breaking Down (Fix These First)');
        }
      }
      if (verdictEl) {
        verdictEl.textContent = lang === 'hi'
          ? `हमने आपका पूरा डेटा चेक किया — ${allLeaks.length} असली समस्याएँ मिलीं। जो ${healthy.length} चीज़ें सही चल रही हैं, उन्हें नीचे छुपा दिया गया है।`
          : `${allLeaks.length} ${tUi('problemsFound', 'Problems Found')} · ${healthy.length} ${tUi('workingFine', 'Working Fine')}`;
      }
      if (badgeEl) {
        badgeEl.textContent = lang === 'hi'
          ? `${allLeaks.length} असली समस्याएँ · ${healthy.length} ठीक हैं`
          : `${allLeaks.length} ${tUi('problemsFound', 'Problems Found')} · ${healthy.length} ${tUi('workingFine', 'Working Fine')}`;
      }

      const activeSev = appState.rankedSevFilter || 'ALL';
      const critCnt = allLeaks.filter(x => (x.severity || 'HIGH') === 'CRITICAL').length;
      const highCnt = allLeaks.filter(x => (x.severity || 'HIGH') === 'HIGH').length;
      const medCnt = allLeaks.filter(x => (x.severity || 'HIGH') === 'MEDIUM').length;

      if (filtersEl) {
        const pills = [
          { key: 'ALL', label: lang === 'hi' ? `सभी (${allLeaks.length})` : `${tUi('all', 'All')} (${allLeaks.length})` },
          ...(critCnt ? [{ key: 'CRITICAL', label: lang === 'hi' ? `तुरंत सुधारें (${critCnt})` : `${tUi('urgent', 'Urgent')} (${critCnt})` }] : []),
          ...(highCnt ? [{ key: 'HIGH', label: lang === 'hi' ? `ज़्यादा असर (${highCnt})` : `${tUi('important', 'Important')} (${highCnt})` }] : []),
          ...(medCnt ? [{ key: 'MEDIUM', label: lang === 'hi' ? `ध्यान दें (${medCnt})` : `${tUi('watch', 'Watch')} (${medCnt})` }] : []),
        ];
        filtersEl.innerHTML = pills.map(p =>
          `<button type="button" class="exc-pill ${activeSev === p.key ? 'active' : ''}" onclick="setRankedSeverityFilter('${p.key}')">${escapeHtml(p.label)}</button>`
        ).join('');
      }

      const filteredLeaks = activeSev === 'ALL'
        ? allLeaks
        : allLeaks.filter(x => (x.severity || 'HIGH') === activeSev);

      const INITIAL_GRID_CAP = 4;
      const showAll = Boolean(appState.rankedShowAll);
      const sevLabel = (sev) => {
        if (lang === 'hi') return sev === 'CRITICAL' ? 'तुरंत सुधारें' : (sev === 'HIGH' ? 'ज़रूरी' : 'ध्यान दें');
        return sev === 'CRITICAL' ? tUi('urgent', 'URGENT') : (sev === 'HIGH' ? tUi('important', 'IMPORTANT') : tUi('watch', 'WATCH'));
      };

      if (heroEl && listEl) {
        if (!filteredLeaks.length) {
          heroEl.innerHTML = '';
          listEl.innerHTML = `<div style="grid-column:1/-1;padding:18px;background:var(--accent-emerald-bg);border:1px solid var(--accent-emerald-border);border-radius:12px;color:var(--accent-emerald);font-weight:700;">` +
            (lang === 'hi' ? '✅ कोई बड़ी समस्या नहीं मिली — सब कुछ ठीक चल रहा है!' : '✅ Great news — everything in this view is working normally!') + `</div>`;
          if (showAllEl) showAllEl.classList.add('hidden');
          if (countMetaEl) countMetaEl.textContent = '';
        } else {
          // 1. Asymmetric #1 Hero Spotlight
          const top1 = filteredLeaks[0];
          const topSev = top1.severity || 'CRITICAL';
          const topCol = topSev === 'CRITICAL' ? 'var(--accent-crimson)' : (topSev === 'HIGH' ? 'var(--accent-amber)' : 'var(--accent-sky)');
          const topSevCls = topSev === 'CRITICAL' ? 'sev-critical' : (topSev === 'HIGH' ? 'sev-high' : 'sev-medium');
          const topHl = humanizeBusinessText(lang === 'hi' ? (top1.headline_hi || top1.headline_en) : top1.headline_en, lang);
          const topRc = humanizeBusinessText(lang === 'hi' ? (top1.root_cause_hi || top1.root_cause_en) : top1.root_cause_en, lang);
          const topAct = humanizeBusinessText(lang === 'hi' ? (top1.fix_action_hi || top1.fix_action_en) : top1.fix_action_en, lang);
          const topExp = humanizeBusinessText(lang === 'hi' ? (top1.expected_standard_hi || top1.expected_standard_en || '') : (top1.expected_standard_en || ''), lang);
          const topImp = humanizeBusinessText(top1.formatted_impact || 'Top Issue', lang);
          const topGauge = _renderGaugeBar(top1, topCol, lang);

          const lblTop1 = lang === 'hi' ? 'सबसे बड़ी समस्या #1' : tUi('topProblem1', 'TOP PROBLEM #1');
          const lblWhy = lang === 'hi' ? '🔍 ऐसा क्यों हो रहा है: ' : `🔍 ${tUi('whyHappening', 'Why this is happening:')} `;
          const lblAct = lang === 'hi' ? '✅ आपको क्या करना चाहिए:' : `✅ ${tUi('whatToDo', 'What you should do:')}`;
          const lblImp = lang === 'hi' ? 'असली असर' : tUi('realImpact', 'REAL IMPACT');

          heroEl.innerHTML = `
            <div class="exc-hero-card">
              <div style="display:flex;flex-direction:column;gap:10px;">
                <div class="exc-meta-left">
                  <span class="exc-rank-num">${escapeHtml(lblTop1)}</span>
                  <span class="exc-sev-chip ${topSevCls}">${escapeHtml(sevLabel(topSev))}</span>
                </div>
                <div style="font-family:var(--font-display);font-size:19px;font-weight:800;color:var(--text-primary);line-height:1.35;letter-spacing:-0.015em;">${formatInlineMd(topHl)}</div>
                <div class="exc-reason-text"><strong style="color:var(--text-primary);">${escapeHtml(lblWhy)}</strong>${formatInlineMd(topRc)}</div>
                <div class="exc-action-bar"><strong>${escapeHtml(lblAct)}</strong><span>${formatInlineMd(topAct)}</span></div>
              </div>
              <div class="exc-hero-metric-box">
                <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;color:var(--text-muted);">${escapeHtml(lblImp)}</div>
                <div class="exc-hero-big-num">${escapeHtml(topImp)}</div>
                ${topGauge || (topExp ? `<div style="font-size:12px;color:var(--text-secondary);">${formatInlineMd(topExp)}</div>` : '')}
              </div>
            </div>
          `;

          // 2. Clean 2-Column Easy-to-Read Analyst Cards
          const restLeaks = filteredLeaks.slice(1);
          const visibleRest = showAll ? restLeaks : restLeaks.slice(0, INITIAL_GRID_CAP);
          if (countMetaEl) {
            const shownTotal = 1 + visibleRest.length;
            countMetaEl.textContent = lang === 'hi'
              ? `कुल ${filteredLeaks.length} में से ${shownTotal} समस्याएँ दिख रही हैं`
              : `Showing ${shownTotal} of ${filteredLeaks.length} problems`;
          }

          listEl.innerHTML = visibleRest.map(lk => {
            const sev = lk.severity || 'HIGH';
            const col = sev === 'CRITICAL' ? 'var(--accent-crimson)' : (sev === 'HIGH' ? 'var(--accent-amber)' : 'var(--accent-sky)');
            const sevCls = sev === 'CRITICAL' ? 'sev-critical' : (sev === 'HIGH' ? 'sev-high' : 'sev-medium');
            const hl = humanizeBusinessText(lang === 'hi' ? (lk.headline_hi || lk.headline_en) : lk.headline_en, lang);
            const exp = humanizeBusinessText(lang === 'hi' ? (lk.expected_standard_hi || lk.expected_standard_en || '') : (lk.expected_standard_en || ''), lang);
            const actObs = humanizeBusinessText(lang === 'hi' ? (lk.actual_observed_hi || lk.actual_observed_en || '') : (lk.actual_observed_en || ''), lang);
            const rc = humanizeBusinessText(lang === 'hi' ? (lk.root_cause_hi || lk.root_cause_en) : lk.root_cause_en, lang);
            const act = humanizeBusinessText(lang === 'hi' ? (lk.fix_action_hi || lk.fix_action_en) : lk.fix_action_en, lang);
            const impTxt = humanizeBusinessText(lk.formatted_impact || '', lang);
            const gaugeHtml = _renderGaugeBar(lk, col, lang);
            const plainRcPreview = String(rc || '').replace(/[`*]/g, '');
            const whyLbl = lang === 'hi' ? '🔍 ऐसा क्यों हो रहा है: ' : `🔍 ${tUi('whyHappening', 'Why this is happening:')} `;
            const isLongRc = plainRcPreview.length > 340;
            const rcBlock = isLongRc
              ? `<div class="exc-reason-text"><strong style="color:var(--text-primary);">${escapeHtml(whyLbl)}</strong>${escapeHtml(plainRcPreview.slice(0, 320))}…</div>
                 <details class="exc-more"><summary>${lang === 'hi' ? 'पूरी जानकारी पढ़ें ▾' : `${escapeHtml(tUi('readFullDetails', 'Read full details'))} ▾`}</summary><div class="exc-reason-text" style="margin-top:6px;">${formatInlineMd(rc)}</div></details>`
              : `<div class="exc-reason-text"><strong style="color:var(--text-primary);">${escapeHtml(whyLbl)}</strong>${formatInlineMd(rc)}</div>`;
            const fallbackExpAct = !gaugeHtml && (exp || actObs)
              ? `<div class="exc-gauge-box"><div style="font-size:11.5px;color:var(--text-muted);">${formatInlineMd(exp)}</div><div style="font-size:11.5px;color:${col};font-weight:700;">${formatInlineMd(actObs)}</div></div>`
              : '';

            return `
              <article class="exc-card">
                <div style="display:flex;flex-direction:column;gap:10px;">
                  <div class="exc-card-top">
                    <div class="exc-meta-left">
                      <span class="exc-rank-num">#${escapeHtml(lk.rank)}</span>
                      <span class="exc-sev-chip ${sevCls}">${escapeHtml(sevLabel(sev))}</span>
                    </div>
                    <span class="exc-impact-pill">${escapeHtml(impTxt)}</span>
                  </div>
                  <div class="exc-card-headline">${formatInlineMd(hl)}</div>
                  ${gaugeHtml || fallbackExpAct}
                  ${rcBlock}
                </div>
                <div class="exc-action-bar"><strong>${lang === 'hi' ? '✅ आपको क्या करना चाहिए:' : `✅ ${escapeHtml(tUi('whatToDo', 'What you should do:'))}`}</strong><span>${formatInlineMd(act)}</span></div>
              </article>
            `;
          }).join('');

          if (showAllEl) {
            if (restLeaks.length > INITIAL_GRID_CAP) {
              showAllEl.classList.remove('hidden');
              const remaining = restLeaks.length - INITIAL_GRID_CAP;
              showAllEl.innerHTML = `<button type="button" class="btn btn-secondary btn-sm" onclick="toggleShowAllRankedLeaks()">` +
                (showAll
                  ? (lang === 'hi' ? 'सिर्फ़ टॉप 5 दिखाएं ▴' : 'Show Top 5 Only ▴')
                  : (lang === 'hi' ? `बाकी ${remaining} समस्याएँ भी देखें (कुल ${filteredLeaks.length}) ▾` : `Show ${remaining} More Problems (${filteredLeaks.length} Total) ▾`)) +
                `</button>`;
            } else {
              showAllEl.classList.add('hidden');
            }
          }
        }
      }

      if (healthyDetails && healthySum && healthyList) {
        if (!healthy.length) {
          healthyDetails.classList.add('hidden');
        } else {
          healthyDetails.classList.remove('hidden');
          healthySum.textContent = lang === 'hi'
            ? `✅ ${healthy.length} चीज़ें बिल्कुल ठीक चल रही हैं (पेज साफ़ रखने के लिए छुपाई गईं — देखने के लिए क्लिक करें ▾)`
            : `✅ ${healthy.length} Areas Are Working Fine (Hidden to keep this page simple — Click to view ▾)`;
          healthyList.innerHTML = healthy.map(h => `
            <div style="background:var(--bg-panel);border:1px solid var(--border-subtle);border-radius:8px;padding:8px 10px;font-size:12px;">
              <div style="font-weight:700;color:var(--accent-emerald);">✓ ${formatInlineMd(humanizeBusinessText(lang === 'hi' ? (h.title_hi || h.title_en) : h.title_en, lang))}</div>
              <div style="color:var(--text-secondary);margin-top:2px;">${formatInlineMd(humanizeBusinessText(h.observed || '', lang))}</div>
            </div>
          `).join('');
        }
      }

      if (shieldsEl) {
        const sHead = lang === 'hi' ? '✅ यह ठीक चल रहा है — यहाँ पैसा न खर्च करें' : "✅ Working Fine — Don't Spend Money Here";
        const sBody = shields.length
          ? `<ul style="margin:6px 0 0 16px;font-size:12.5px;line-height:1.55;color:var(--text-secondary);">` + shields.map(s => `<li>${formatInlineMd(humanizeBusinessText(lang === 'hi' ? s.message_hi : s.message_en, lang))}</li>`).join('') + `</ul>`
          : `<div style="font-size:12.5px;color:var(--text-secondary);margin-top:4px;">${lang === 'hi' ? 'सभी जाँचे गए हिस्सों में वास्तविक फर्क मिला।' : 'Every checked area showed a real difference worth reviewing.'}</div>`;
        shieldsEl.innerHTML = `<div style="font-size:12px;font-weight:800;color:var(--accent-emerald);text-transform:uppercase;">${sHead}</div>${sBody}`;
      }

      if (oppsEl) {
        const oHead = lang === 'hi' ? '💡 मुनाफा बढ़ाने के आसान मौके' : '💡 Easy Ways to Grow Profit';
        const oBody = opps.length
          ? `<ul style="margin:6px 0 0 16px;font-size:12.5px;line-height:1.55;color:var(--text-secondary);">` + opps.slice(0, 4).map(o => `<li><strong>${escapeHtml(lang === 'hi' ? o.title_hi : o.title_en)}:</strong> ${escapeHtml(o.key_metric)}</li>`).join('') + `</ul>`
          : `<div style="font-size:12.5px;color:var(--text-secondary);margin-top:4px;">${lang === 'hi' ? 'प्रोडक्ट/ग्राहक डेटा जोड़ने पर और मौके दिखेंगे।' : 'Upload product or customer sheets to discover top cross-sell & repeat-buyer opportunities.'}</div>`;
        oppsEl.innerHTML = `<div style="font-size:12px;font-weight:800;color:var(--accent-sky);text-transform:uppercase;">${oHead}</div>${oBody}`;
      }

      if (unlockEl) {
        if (packs.length) {
          const lbl = lang === 'hi' ? '🔓 अतिरिक्त शीट जोड़कर और लीक अनलॉक करें:' : '🔓 Optional sheets to unlock even deeper audits:';
          unlockEl.innerHTML = `<strong style="color:var(--text-primary);">${lbl}</strong> ` + packs.map(p =>
            `<span style="padding:2px 8px;border-radius:999px;background:var(--bg-elevated);border:1px solid var(--border-subtle);">+ ${escapeHtml(lang === 'hi' ? p.name_hi : p.name_en)} (${Number(p.unlocks_question_count || 0)} checks)</span>`
          ).join(' ');
        } else {
          unlockEl.innerHTML = '';
        }
      }
    }

    async function loadAndRender200Questions(runId) {
      const sec = document.getElementById('questions200Section');
      const badge = document.getElementById('q200SummaryBadge');
      if (!sec || !runId) return;
      sec.classList.remove('hidden');
      if (badge) badge.textContent = 'Computing 200 Answers...';
      try {
        const res = await apiFetch(`/api/v1/questions-200/${encodeURIComponent(runId)}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        appState.questions200Data = await res.json();
        render200QuestionsPanel();
      } catch (e) {
        if (badge) badge.textContent = 'Unavailable for this run';
      }
    }

    function select200Pillar(pid) {
      appState.questions200Pillar = pid || 'ALL';
      render200QuestionsPanel();
    }

    function render200QuestionsPanel() {
      const sec = document.getElementById('questions200Section');
      const data = appState.questions200Data;
      if (!sec || !data || !Array.isArray(data.questions)) return;
      sec.classList.remove('hidden');

      const lang = appState.briefLanguage === 'hi' ? 'hi' : 'en';
      const titleEl = document.getElementById('q200Title');
      const badgeEl = document.getElementById('q200SummaryBadge');
      const pillsEl = document.getElementById('q200PillarPills');
      const gridEl = document.getElementById('q200CardsGrid');
      const searchEl = document.getElementById('q200SearchInput');
      const statusEl = document.getElementById('q200StatusFilter');

      const summary = data.summary || {};
      if (titleEl) {
        titleEl.textContent = lang === 'hi'
          ? '🌐 सभी 200 बिज़नेस सवालों के डेटा-आधारित जवाब (15 स्तंभ · Q001–Q200)'
          : '🌐 Complete 200 Universal Business Intelligence Answers (15 Pillars · Q001–Q200)';
      }
      if (badgeEl) {
        const dataBacked = (summary.direct_count || 0) + (summary.proxy_count || 0);
        const abnCount = summary.abnormal_deviation_count || 0;
        badgeEl.textContent = lang === 'hi'
          ? `${dataBacked} डेटा-प्रमाणित · 200 जाँचे गए (${abnCount} असामान्य · ${summary.column_missing_explained_count || 0} कॉलम शेष)`
          : `${dataBacked} Data-Backed · 200 Audited (${abnCount} Abnormal · ${summary.column_missing_explained_count || 0} Needs Col)`;
      }

      const activePillar = appState.questions200Pillar || 'ALL';
      const pillars = data.pillars || [];
      if (pillsEl) {
        const allBtn = `<button type="button" class="filter-tab ${activePillar === 'ALL' ? 'active' : ''}" onclick="select200Pillar('ALL')">All (${data.questions.length})</button>`;
        const pBtns = pillars.map(p => {
          const shortName = lang === 'hi' ? (p.pillar_name_hi || p.pillar_name).split(',')[0] : p.pillar_name.split(',')[0].split('&')[0].trim();
          return `<button type="button" class="filter-tab ${activePillar === p.pillar_id ? 'active' : ''}" onclick="select200Pillar('${escapeHtml(p.pillar_id)}')">${escapeHtml(p.pillar_id)} ${escapeHtml(shortName)} (${p.direct + p.proxy}/${p.total})</button>`;
        }).join('');
        pillsEl.innerHTML = allBtn + pBtns;
      }

      const query = String((searchEl && searchEl.value) || '').trim().toLowerCase();
      const statusFlt = String((statusEl && statusEl.value) || 'DATA_BACKED');
      const filtered = data.questions.filter(q => {
        if (activePillar !== 'ALL' && q.pillar_id !== activePillar) return false;
        if (statusFlt === 'DATA_BACKED' && q.status === 'COLUMN_MISSING_EXPLAINED') return false;
        if (statusFlt !== 'ALL' && statusFlt !== 'DATA_BACKED' && q.status !== statusFlt) return false;
        if (query) {
          const hay = `${q.id} ${q.pillar_name} ${q.question_en} ${q.question_hi} ${q.answer_en} ${q.answer_hi} ${q.key_metric}`.toLowerCase();
          if (!hay.includes(query)) return false;
        }
        return true;
      });

      if (!filtered.length) {
        gridEl.innerHTML = `<div style="grid-column:1/-1;text-align:center;color:var(--text-muted);padding:24px;">No matching questions found.</div>`;
        return;
      }

      gridEl.innerHTML = filtered.map(q => {
        const st = q.status;
        const stColor = st === 'DIRECT_ANSWERED' ? 'var(--accent-emerald)' : (st === 'PROXY_ANSWERED' ? 'var(--accent-amber)' : 'var(--text-muted)');
        const stLabel = st === 'DIRECT_ANSWERED' ? (lang === 'hi' ? '✅ सीधा डेटा' : '✅ Direct') : (st === 'PROXY_ANSWERED' ? (lang === 'hi' ? '🟡 प्रॉक्सी' : '🟡 Proxy') : (lang === 'hi' ? '⚪ कॉलम चाहिए' : '⚪ Needs Column'));
        const qText = lang === 'hi' ? (q.question_hi || q.question_en) : q.question_en;
        const aText = lang === 'hi' ? (q.answer_hi || q.answer_en) : q.answer_en;
        return `
          <div style="background:var(--bg-elevated);border:1px solid var(--border-subtle);border-left:4px solid ${stColor};border-radius:10px;padding:12px;">
            <div style="display:flex;justify-content:space-between;align-items:center;gap:6px;margin-bottom:4px;">
              <span style="font-size:11.5px;font-weight:800;color:var(--accent-sky);">${escapeHtml(q.id)} · ${escapeHtml(q.pillar_id)}</span>
              <span style="font-size:11px;font-weight:700;color:${stColor};">${stLabel}</span>
            </div>
            <div style="font-size:13px;font-weight:700;color:var(--text-primary);margin-bottom:6px;line-height:1.4;">${escapeHtml(qText)}</div>
            <div style="display:inline-block;font-size:11.5px;font-weight:700;padding:2px 8px;border-radius:999px;background:var(--bg-panel);border:1px solid var(--border-subtle);margin-bottom:6px;">${escapeHtml(q.key_metric || '--')}</div>
            <div style="font-size:12.5px;color:var(--text-secondary);line-height:1.5;">${escapeHtml(aText)}</div>
          </div>
        `;
      }).join('');
    }

    function renderOwnerPathways(ownerPlans) {
      const container = document.getElementById('pathwayStack');
      container.innerHTML = '';
      const lang = appState.briefLanguage === 'hi' ? 'hi' : 'en';
      if (!ownerPlans || !ownerPlans.length) {
        container.innerHTML = `<p style="color:var(--text-muted);font-size:13px;">${escapeHtml(tUi('lblNoChangeNeeded', 'No urgent changes needed — numbers look stable.'))}</p>`;
        return;
      }

      ownerPlans.forEach((p, idx) => {
        const card = document.createElement('div');
        card.className = `pathway-card ${idx === 0 ? 'selected' : ''}`;
        const cleanBadge = normalizeIndianRupeesInText(String(p.badge || '')).replace(/\s*\(₹[^)]+\)/g, '');
        card.innerHTML = `
          <div class="pathway-top">
            <span class="pathway-title">${escapeHtml(p.title)}</span>
            <span class="pathway-roi">${escapeHtml(cleanBadge)}</span>
          </div>
          <p style="font-size: 13.5px; color: var(--text-secondary); margin-bottom: 8px; line-height: 1.55;">
            ${escapeHtml(p.story)}
          </p>
          <div class="pathway-meta">
            <div>
              <span>${escapeHtml(tUi('lblWhereToFocus', 'Where to Focus'))}</span>
              <strong>${escapeHtml(p.target)}</strong>
            </div>
            <div>
              <span>${escapeHtml(tUi('lblTimeEffort', 'Time & Effort'))}</span>
              <strong>${escapeHtml(p.effort)}</strong>
            </div>
          </div>
        `;
        card.addEventListener('click', () => {
          container.querySelectorAll('.pathway-card').forEach(c => c.classList.remove('selected'));
          card.classList.add('selected');
          const presetReductions = [25, 40, 60];
          const presetCosts = [2500, 10000, 25000];
          document.getElementById('simReductionSlider').value = presetReductions[idx] || 25;
          document.getElementById('simCostSlider').value = presetCosts[idx] !== undefined ? presetCosts[idx] : 2500;
          recalculateSimulator();
          switchWorkspaceTab('calculator', document.querySelector('[data-tab="calculator"]'));
          showToast(lang === 'hi' ? `${p.title} ke hisab se calculator set ho gaya` : `Calculator updated for ${p.title}`, 'info');
        });
        container.appendChild(card);
      });
    }

    // =========================================================================
    // CATEGORY & GROUP BREAKDOWN EXPLORER
    // =========================================================================
    function renderCohortExplorer(breakdowns) {
      const sec = document.getElementById('cohortExplorerSection');
      const tabsEl = document.getElementById('cohortDimensionTabs');
      const tbody = document.getElementById('cohortBreakdownTableBody');
      const dimBadge = document.getElementById('cohortDimensionBadge');

      if (!breakdowns || breakdowns.length === 0) {
        sec.classList.add('hidden');
        return;
      }
      sec.classList.remove('hidden');
      tabsEl.innerHTML = '';

      breakdowns.forEach((b, idx) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = `filter-tab ${idx === appState.activeCohortDimIdx ? 'active' : ''}`;
        btn.textContent = b.dimension_label || `Group ${idx + 1}`;
        btn.onclick = () => {
          appState.activeCohortDimIdx = idx;
          renderCohortExplorer(breakdowns);
        };
        tabsEl.appendChild(btn);
      });

      const activeDim = breakdowns[appState.activeCohortDimIdx] || breakdowns[0];
      dimBadge.textContent = `Grouped By: ${activeDim.dimension_label || ''}`;
      tbody.innerHTML = '';

      const rows = activeDim.rows || [];
      const maxRate = Math.max(1, ...rows.map(r => Number(r.adverse_rate_pct || 0)));

      rows.forEach((r) => {
        const rate = Number(r.adverse_rate_pct || 0);
        const barWidth = Math.min(100, Math.max(4, (rate / maxRate) * 100));
        const barColor = rate >= 50
          ? 'var(--accent-crimson)'
          : (rate >= 25 ? 'var(--accent-amber)' : 'var(--accent-emerald)');

        const statusStr = String(r.status || '');
        const isHighRisk = statusStr.includes('High-Risk') || statusStr.includes('🔴') || rate >= 40;
        const isResilient = statusStr.includes('Resilient') || statusStr.includes('🟢');
        const badgeCls = isHighRisk ? 'recovery' : (isResilient ? 'resolved' : 'preventive');
        const lang = appState.briefLanguage === 'hi' ? 'hi' : 'en';
        const symC = (appState.executivePulse && appState.executivePulse.unit_symbol) || '$';
        const friendlyStatus = isHighRisk
          ? (lang === 'hi' ? '🔴 बड़ा नुकसान' : '🔴 High Loss')
          : (isResilient ? (lang === 'hi' ? '🟢 सुरक्षित' : '🟢 Safe') : (lang === 'hi' ? '🟡 ध्यान दें' : '🟡 Watch'));
        const cleanLiab = normalizeIndianRupeesInText(String(r.total_liability || '--')).replace(/\s*\(₹[^)]+\)/g, '');
        const cleanVol = r.volume_num !== undefined ? formatNumberForCurrency(r.volume_num, symC) : String(r.volume || '0');
        const cleanAdv = r.adverse_events_num !== undefined ? formatNumberForCurrency(r.adverse_events_num, symC) : String(r.adverse_events || '0');

        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td style="font-weight:700;">${escapeHtml(r.segment)}</td>
          <td class="tabular-nums">${escapeHtml(cleanVol)}</td>
          <td class="tabular-nums">${escapeHtml(cleanAdv)}</td>
          <td class="tabular-nums">
            <div class="cohort-bar-track">
              <div class="cohort-bar-fill" style="width:${barWidth.toFixed(1)}%;background:${barColor};"></div>
            </div>
            <strong style="color:${barColor};">${rate.toFixed(2)}%</strong>
          </td>
          <td class="tabular-nums">${Number(r.share_of_failures_pct || 0).toFixed(1)}%</td>
          <td class="tabular-nums" style="font-weight:600;">${escapeHtml(cleanLiab)}</td>
          <td><span class="queue-badge ${badgeCls}">${escapeHtml(friendlyStatus)}</span></td>
          <td style="text-align:right;">
            <button type="button" class="btn btn-secondary btn-sm" data-seg="${escapeHtml(r.segment)}">
              ${lang === 'hi' ? 'वजह देखें ↗' : 'Explain Why ↗'}
            </button>
          </td>
        `;
        tr.querySelector('button[data-seg]').addEventListener('click', () => {
          drillDownCohortInCopilot(activeDim.dimension_label, r.segment);
        });
        tbody.appendChild(tr);
      });
    }

    function drillDownCohortInCopilot(dimLabel, segmentName) {
      const q = `What is driving risk in ${dimLabel} segment ${segmentName} and what is its total exposure?`;
      document.getElementById('copilotQuestionInput').value = q;
      switchWorkspaceTab('ask', document.querySelector('[data-tab="ask"]'));
      submitCopilotQuestion();
    }

    // =========================================================================
    // MORNING MUNIM-JI DIGEST & WEBHOOK DISPATCHER
    // =========================================================================
    async function openMorningDigestModal() {
      if (!appState.activeRunId) {
        showToast('Select or upload a report first.', 'warn');
        return;
      }
      document.getElementById('morningDigestModal').classList.remove('hidden');
      const box = document.getElementById('digestMessagePreview');
      box.value = 'Preparing 60-second summary...';

      try {
        const res = await apiFetch(`/api/v1/digest/${encodeURIComponent(appState.activeRunId)}?tenant_id=${encodeURIComponent(appState.activeTenant)}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        appState.digestPayload = await res.json();
        const prefLang = appState.briefLanguage === 'hi' ? 'hi' : 'en';
        switchDigestLang(prefLang);
      } catch (e) {
        box.value = `Could not load summary: ${e.message}`;
      }
    }

    function closeMorningDigestModal() {
      document.getElementById('morningDigestModal').classList.add('hidden');
    }

    function switchDigestLang(lang) {
      appState.digestLang = lang;
      document.getElementById('btnDigestEn').classList.toggle('active', lang === 'en');
      document.getElementById('btnDigestHi').classList.toggle('active', lang === 'hi');
      if (!appState.digestPayload) return;
      const text = lang === 'hi'
        ? appState.digestPayload.whatsapp_hinglish
        : appState.digestPayload.whatsapp_english;
      document.getElementById('digestMessagePreview').value = text || '';
    }

    function copyDigestText() {
      const text = document.getElementById('digestMessagePreview').value || '';
      copyTextSafe(text, 'Morning summary copied!');
    }

    function shareDigestOnWhatsApp() {
      const text = document.getElementById('digestMessagePreview').value || '';
      window.open(`https://wa.me/?text=${encodeURIComponent(text)}`, '_blank', 'noopener');
      showToast('Opened WhatsApp.', 'info');
    }

    async function dispatchDigestWebhook() {
      const url = (document.getElementById('digestWebhookUrlInput').value || '').trim();
      if (!url) {
        showToast('Enter a valid Slack / Webhook URL.', 'warn');
        return;
      }
      try {
        const res = await apiFetch('/api/v1/digest/dispatch', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            run_id: appState.activeRunId,
            tenant_id: appState.activeTenant,
            language: appState.digestLang,
            webhook_url: url
          })
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `HTTP ${res.status}`);
        }
        const data = await res.json();
        if (data.webhook_dispatched || data.dispatched) {
          showToast('Summary sent to Slack/Webhook!', 'success');
        } else {
          showToast(`Send error: ${data.webhook_error || data.webhook_status || 'failed'}`, 'warn');
        }
      } catch (e) {
        showToast(`Send failed: ${e.message}`, 'error');
      }
    }

    function renderStrategicPathways(pathways) {
      const container = document.getElementById('pathwayStack');
      container.innerHTML = '';
      if (!pathways.length) {
        container.innerHTML = '<p style="color:var(--text-muted);font-size:13px;">No improvement plans needed — numbers look stable.</p>';
        return;
      }

      pathways.forEach((p, idx) => {
        const card = document.createElement('div');
        card.className = `pathway-card ${idx === 0 ? 'selected' : ''}`;
        card.innerHTML = `
          <div class="pathway-top">
            <span class="pathway-title">${escapeHtml(p.title || `Plan ${idx + 1}`)}</span>
            <span class="pathway-roi">${escapeHtml(p.roi_range || 'Targeted Savings')}</span>
          </div>
          <p style="font-size: 13px; color: var(--text-secondary); margin-bottom: 6px;">
            ${escapeHtml(p.action || '')}
          </p>
          <div class="pathway-meta">
            <div>
              <span>Where to Focus</span>
              <strong>${escapeHtml(p.target || 'Main Problem Group')}</strong>
            </div>
            <div>
              <span>Estimated Effort</span>
              <strong>${escapeHtml(p.investment || 'Low Effort')}</strong>
            </div>
          </div>
        `;
        card.addEventListener('click', () => {
          container.querySelectorAll('.pathway-card').forEach(c => c.classList.remove('selected'));
          card.classList.add('selected');
          const presetReductions = [25, 18, 12];
          const presetCosts = [2500, 1000, 0];
          document.getElementById('simReductionSlider').value = presetReductions[idx] || 20;
          document.getElementById('simCostSlider').value = presetCosts[idx] !== undefined ? presetCosts[idx] : 1500;
          recalculateSimulator();
          switchWorkspaceTab('calculator', document.querySelector('[data-tab="calculator"]'));
          showToast(`Updated calculator for ${p.title}`, 'info');
        });
        container.appendChild(card);
      });
    }

    function switchBriefLanguage(lang) {
      appState.briefLanguage = lang || 'en';
      const bEn = document.getElementById('btnBriefEn');
      const bHi = document.getElementById('btnBriefHi');
      if (bEn) bEn.classList.toggle('active', lang === 'en');
      if (bHi) bHi.classList.toggle('active', lang === 'hi');
      const cacheKey = `${appState.activeRunId || 'none'}::${lang}`;
      const md = lang === 'hi'
        ? appState.hinglishSummaryMd
        : (appState.translatedSummaries[cacheKey] || appState.englishSummaryMd);
      document.getElementById('briefReaderBox').innerHTML = renderMarkdownHtml(md);
      if (typeof populateCategoryDropdowns === 'function') populateCategoryDropdowns();
      if (typeof renderCategoryIntelligencePanel === 'function') {
        renderCategoryIntelligencePanel((appState.executivePulse && appState.executivePulse.category_intelligence) || null, lang);
      }
      if (typeof renderV7VoiceRadarAndImpact === 'function') {
        renderV7VoiceRadarAndImpact(lang);
      }
      renderGrowthInventoryPanel((appState.executivePulse && appState.executivePulse.growth_inventory) || null, lang);
      renderOmniLeakPanel((appState.executivePulse && appState.executivePulse.omni_leak_report) || appState.omniLeakReport || null);
      recalculateSimulator();
      renderRankedLeaksPanel();
      render200QuestionsPanel();
      if (Array.isArray(appState.worklistRows) && appState.worklistRows.length) {
        renderWorklistTable();
      }
    }

    function renderArtifactDownloadLinks(urls) {
      const strip = document.getElementById('artifactDownloadStrip');
      strip.innerHTML = '';
      const labels = {
        'PLAIN_BUSINESS_SUMMARY.md': '📄 English Summary',
        'HINGLISH_BUSINESS_SUMMARY.md': '📄 Hinglish Summary',
        'DATA_XRAY_EXECUTIVE_DOSSIER.md': '📑 Full Analyst Report',
        'actionable_priority_worklist.csv': '📊 Action List (.csv)',
        'semantic_metrics_manifest.json': '⚙️ Verified Data (.json)'
      };
      Object.entries(labels).forEach(([fileKey, label]) => {
        if (urls[fileKey]) {
          const a = document.createElement('a');
          a.href = appendApiKeyToUrl(urls[fileKey]);
          a.className = 'btn btn-secondary btn-sm';
          a.textContent = label;
          a.setAttribute('download', fileKey);
          strip.appendChild(a);
        }
      });
    }

    // =========================================================================
    // SAVINGS CALCULATOR
    // =========================================================================
    function recalculateSimulator() {
      const pulse = appState.executivePulse || {};
      const sym = pulse.unit_symbol || '$';
      const isHi = appState.briefLanguage === 'hi';
      const reductionPct = Number(document.getElementById('simReductionSlider').value || 25);
      const spendCost = Number(document.getElementById('simCostSlider').value || 2500);

      document.getElementById('simReductionLabel').textContent = `${reductionPct}% ${tUi('simReductionWord', 'Reduction')}`;
      document.getElementById('simCostLabel').textContent = formatCurrencyValue(spendCost, sym);

      const isFinancial = Boolean(pulse.is_financial && Number(pulse.total_capital_drag) > 0);
      const baseDrag = isFinancial ? Number(pulse.total_capital_drag) : Number(pulse.total_adverse_events || 0);
      const baseRate = Number(pulse.overall_adverse_rate_pct || 0);

      const grossRecovered = baseDrag * (reductionPct / 100.0);
      const netRecovered = isFinancial ? (grossRecovered - spendCost) : grossRecovered;
      const newRate = Math.max(0, baseRate * (1.0 - (reductionPct * 0.65) / 100.0));

      const basePrefix = tUi('simBasedOnPrefix', 'BASED ON:');
      const riskSuffix = tUi('simAtRiskSuffix', 'AT RISK');
      document.getElementById('simBasisLabel').textContent = isFinancial
        ? `${basePrefix} ${formatCurrencyValue(baseDrag, sym)} ${riskSuffix}`
        : `${basePrefix} ${formatNumberForCurrency(baseDrag, sym)} ${isHi ? 'समस्या के केस' : 'PROBLEM CASES'}`;

      document.getElementById('simGrossTitle').textContent = isFinancial
        ? tUi('simGrossLbl', 'Money Saved')
        : (isHi ? 'बचाए गए केस' : 'Cases Prevented');

      document.getElementById('simGrossValue').textContent = isFinancial
        ? formatCurrencyValue(grossRecovered, sym)
        : `${formatNumberForCurrency(Math.round(grossRecovered), sym)} ${isHi ? 'केस' : 'Cases'}`;

      const netEl = document.getElementById('simNetValue');
      netEl.textContent = isFinancial
        ? formatCurrencyValue(netRecovered, sym)
        : `${formatNumberForCurrency(Math.round(grossRecovered), sym)} ${isHi ? 'बचे' : 'Saved'}`;
      netEl.style.color = netRecovered >= 0 ? 'var(--accent-sky)' : 'var(--accent-crimson)';

      document.getElementById('simNewRateValue').textContent = `${newRate.toFixed(2)}%`;
    }

    function updateRoiSummaryCard(roi, sym = '$') {
      const totalSaved = Number(roi.total_estimated_saved_capital || 0);
      const actionsCount = Number(roi.total_actions_logged || 0);
      const mult = Number(roi.subscription_roi_multiplier || 0);

      document.getElementById('roiSavedCapitalValue').textContent = formatCurrencyValue(totalSaved, sym);
      document.getElementById('roiActionsCount').textContent = String(actionsCount);
      document.getElementById('roiMultiplierBadge').textContent = `${mult.toFixed(1)}x`;
    }

    // =========================================================================
    // TODAY'S ACTION LIST TABLE
    // =========================================================================
    function setWorklistQueueFilter(queueVal, btnEl) {
      appState.worklistQueueFilter = queueVal;
      document.querySelectorAll('#tabPanel-actions .filter-tab').forEach(b => b.classList.remove('active'));
      if (btnEl) btnEl.classList.add('active');
      renderWorklistTable();
    }

    function humanizeWorklistReason(rawReason, lang = 'en') {
      if (!rawReason) return '--';
      let s = String(rawReason)
        .replace(/\bCohort\s+/gi, '')
        .replace(/([A-Za-z0-9_]+)\s*=\s*'([^']+)'/g, (_, col, val) => `${col.replace(/_/g, ' ')}: ${val}`)
        .replace(/([A-Za-z0-9_]+)\s*>=\s*(\d+(?:\.\d+)?)\s*Cliff Breach/gi, (_, col, num) => {
          const cleanNum = num.replace(/\.0+$/, '');
          return `${col.replace(/_/g, ' ')} crossed safe limit (${cleanNum}+)`;
        })
        .replace(/([A-Za-z0-9_]+)\s*<=\s*(\d+(?:\.\d+)?)\s*Cliff Breach/gi, (_, col, num) => {
          const cleanNum = num.replace(/\.0+$/, '');
          return `${col.replace(/_/g, ' ')} below safe limit (${cleanNum})`;
        })
        .replace(/;\s*/g, ' • ');
      s = humanizeBusinessText(s, lang);
      if (lang === 'hi') {
        s = s
          .replace(/Delivery Days/gi, 'डिलीवरी दिन')
          .replace(/Courier Partner/gi, 'कूरियर')
          .replace(/Payment Mode/gi, 'पेमेंट')
          .replace(/Product Item/gi, 'प्रोडक्ट')
          .replace(/crossed safe limit/gi, 'सुरक्षित सीमा पार')
          .replace(/below safe limit/gi, 'सुरक्षित सीमा से कम')
          .replace(/(\d+(?:\.\d+)?)%\s*risk/gi, '$1% खतरा');
      }
      return s;
    }

    function humanizeWorklistStep(rawStep, isPreventive, lang = 'en') {
      const s = String(rawStep || '');
      if (lang === 'hi') {
        return isPreventive
          ? '📞 अभी ग्राहक को कॉल/WhatsApp करके ऑर्डर व डिलीवरी कन्फर्म करें (ताकि रिटर्न न हो)'
          : '🔄 ऑर्डर खराब/वापस हुआ — पैसा बचाने के लिए ग्राहक या कूरियर से बात करें';
      }
      if (/Preventive Outreach|confirm order/i.test(s) || isPreventive) {
        return '📞 Call or WhatsApp customer now to confirm order & stop cancellation/return';
      }
      if (/Loss Recovery|Already failed/i.test(s) || !isPreventive) {
        return '🔄 Order failed/returned — call customer or check courier to recover money';
      }
      return s;
    }

    function renderWorklistTable() {
      const tbody = document.getElementById('worklistTableBody');
      const searchQ = (document.getElementById('worklistSearchInput').value || '').trim().toLowerCase();
      const idCol = (appState.worklistMeta && appState.worklistMeta.primary_id_column) || 'Entity_ID';
      const sym = (appState.executivePulse && appState.executivePulse.unit_symbol) || '$';
      const lang = appState.briefLanguage === 'hi' ? 'hi' : 'en';

      document.getElementById('thPrimaryId').textContent = idCol === 'fact_surrogate_id' ? 'Record ID' : idCol.replace(/_/g, ' ').replace(/\b\w/g, m => m.toUpperCase());
      tbody.innerHTML = '';

      const filtered = appState.worklistRows.map((row, idx) => ({ row, idx })).filter(({ row }) => {
        const qName = String(row.action_queue || '');
        if (appState.worklistQueueFilter !== 'all' && !qName.toLowerCase().includes(appState.worklistQueueFilter.toLowerCase())) {
          return false;
        }
        if (searchQ) {
          const entityVal = String(row[idCol] ?? row.entity_id ?? '').toLowerCase();
          const reasonVal = String(row.primary_risk_reason ?? '').toLowerCase();
          const stepVal = String(row.recommended_next_step ?? '').toLowerCase();
          return entityVal.includes(searchQ) || reasonVal.includes(searchQ) || stepVal.includes(searchQ);
        }
        return true;
      });

      document.getElementById('worklistCountBadge').textContent =
        `(${formatNumberForCurrency(filtered.length, sym)} of ${formatNumberForCurrency(appState.worklistMeta.total_flagged || appState.worklistRows.length, sym)} Items)`;

      if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;color:var(--text-muted);padding:28px;">No action items match your search.</td></tr>`;
        return;
      }

      filtered.forEach(({ row, idx }) => {
        const entityId = String(row[idCol] ?? row.entity_id ?? `ROW-${idx + 1}`);
        const isResolved = appState.resolvedEntities.has(entityId);
        const queueRaw = String(row.action_queue || 'Priority');
        const isPreventive = queueRaw.toLowerCase().includes('preventive');
        const friendlyQueue = lang === 'hi'
          ? (isPreventive ? 'नुकसान से पहले बचाएं' : 'डूबा पैसा रिकवर करें')
          : (isPreventive ? 'Save Before Loss' : 'Recover Lost Money');
        const riskPct = Number(row.empirical_cohort_risk_pct || 0);
        const exposureNum = row.monetary_exposure !== null && row.monetary_exposure !== undefined
          ? Number(row.monetary_exposure)
          : 0;
        const exposureText = exposureNum > 0
          ? formatCurrencyValue(exposureNum, sym)
          : `${sym}0 (Ops Watch)`;
        const cleanReason = humanizeWorklistReason(row.primary_risk_reason, lang);
        const cleanStep = humanizeWorklistStep(row.recommended_next_step, isPreventive, lang);

        const tr = document.createElement('tr');
        const badgeClass = isResolved ? 'resolved' : (isPreventive ? 'preventive' : 'recovery');
        const badgeText = isResolved ? (lang === 'hi' ? '✓ काम पूरा' : '✓ Action Taken') : friendlyQueue;
        const lblWhy = lang === 'hi' ? 'खतरा क्यों है' : 'Why Risky';
        const lblNext = lang === 'hi' ? 'अगला कदम' : 'Next Step';

        tr.innerHTML = `
          <td class="tabular-nums wl-rank" style="color:var(--text-muted);">#${escapeHtml(row.priority_rank || (idx + 1))}</td>
          <td class="tabular-nums wl-id" style="font-weight:700;">${escapeHtml(entityId)}</td>
          <td class="wl-urgency"><span class="queue-badge ${badgeClass}">${escapeHtml(badgeText)}</span></td>
          <td class="tabular-nums wl-risk" style="font-weight:700;color:${riskPct >= 50 ? 'var(--accent-crimson)' : 'var(--accent-amber)'};">${riskPct.toFixed(0)}%</td>
          <td class="tabular-nums wl-amount" style="font-weight:600;">${escapeHtml(exposureText)}</td>
          <td class="wl-reason" data-label="${escapeHtml(lblWhy)}" style="max-width:270px;color:var(--text-secondary);line-height:1.45;">${escapeHtml(cleanReason)}</td>
          <td class="wl-step" data-label="${escapeHtml(lblNext)}" style="max-width:280px;color:var(--text-secondary);line-height:1.45;">${escapeHtml(cleanStep)}</td>
          <td class="wl-action" style="text-align:right;">
            <button type="button" class="btn ${isResolved ? 'btn-secondary' : 'btn-primary'} btn-sm" data-row-idx="${idx}">
              ${isResolved ? (lang === 'hi' ? 'बदलें' : 'Update') : (lang === 'hi' ? 'कॉल/एक्शन लें' : 'Take Action')}
            </button>
          </td>
        `;

        tr.querySelector('button[data-row-idx]').addEventListener('click', () => openInterventionModal(idx));
        tbody.appendChild(tr);
      });
    }

    function openInterventionModal(rowIndex) {
      const row = appState.worklistRows[rowIndex];
      if (!row) return;
      appState.modalRowIndex = rowIndex;
      const lang = appState.briefLanguage === 'hi' ? 'hi' : 'en';
      const isPreventive = String(row.action_queue || '').toLowerCase().includes('preventive');

      const idCol = (appState.worklistMeta && appState.worklistMeta.primary_id_column) || 'Entity_ID';
      const sym = (appState.executivePulse && appState.executivePulse.unit_symbol) || '$';
      const entityId = String(row[idCol] ?? row.entity_id ?? `ROW-${rowIndex + 1}`);
      const reason = humanizeWorklistReason(row.primary_risk_reason || 'High risk case', lang);
      const nextStep = humanizeWorklistStep(row.recommended_next_step, isPreventive, lang);
      const exposure = Number(row.monetary_exposure || 0);

      document.getElementById('modalEntityTitle').textContent = `Action for ${idCol}: ${entityId}`;
      document.getElementById('modalEntitySubtitle').textContent =
        `Amount at Risk: ${formatCurrencyValue(exposure, sym)} · Reason: ${reason}`;

      const draftMsg =
        `Hi! Following up regarding order/account ${entityId} (Amount: ${formatCurrencyValue(exposure, sym)}). ` +
        `Reason flagged: ${reason}. Suggested step: ${nextStep}.`;
      document.getElementById('modalOutreachText').value = draftMsg;

      document.getElementById('interventionModal').classList.remove('hidden');
    }

    function closeInterventionModal() {
      document.getElementById('interventionModal').classList.add('hidden');
      appState.modalRowIndex = null;
    }

    function openWhatsAppDeepLink() {
      const text = document.getElementById('modalOutreachText').value || '';
      window.open(`https://wa.me/?text=${encodeURIComponent(text)}`, '_blank', 'noopener');
      showToast('Opened WhatsApp.', 'info');
    }

    async function commitWorklistIntervention() {
      const idx = appState.modalRowIndex;
      const row = appState.worklistRows[idx];
      if (!row) return;

      const idCol = (appState.worklistMeta && appState.worklistMeta.primary_id_column) || 'Entity_ID';
      const sym = (appState.executivePulse && appState.executivePulse.unit_symbol) || '$';
      const entityId = String(row[idCol] ?? row.entity_id ?? `ROW-${idx + 1}`);
      const statusVal = document.getElementById('modalActionStatus').value;
      const notesVal = document.getElementById('modalOutreachText').value;
      const exposureVal = Number(row.monetary_exposure || 0);

      try {
        const res = await apiFetch('/api/v1/worklist/action', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            tenant_id: appState.activeTenant,
            entity_id: entityId,
            run_id: appState.activeRunId || 'manual_run',
            action_type: row.action_queue || 'frontline_intervention',
            notes: notesVal,
            monetary_exposure: exposureVal,
            status: statusVal
          })
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const payload = await res.json();
        appState.resolvedEntities.add(entityId);
        updateRoiSummaryCard(payload.roi_summary || {}, sym);
        renderWorklistTable();
        closeInterventionModal();
        showToast(`Saved action for ${entityId}!`, 'success');
      } catch (e) {
        showToast(`Could not save action: ${e.message}`, 'error');
      }
    }

    function downloadWorklistCsv() {
      if (!appState.activeRunId) {
        showToast('Select or upload a report first.', 'warn');
        return;
      }
      window.location.href = appendApiKeyToUrl(`/api/v1/download/${encodeURIComponent(appState.activeRunId)}/actionable_priority_worklist.csv`);
    }

    // =========================================================================
    // ASK QUESTIONS (Q&A)
    // =========================================================================
    function askPresetQuestion(qText) {
      document.getElementById('copilotQuestionInput').value = qText;
      if (qText.toLowerCase().includes('sabse') || qText.toLowerCase().includes('kyun')) {
        document.getElementById('copilotLangSelect').value = 'hi';
      }
      submitCopilotQuestion();
    }

    function resetCopilotChat(silent = false) {
      appState.copilotHistory = [];
      const bar = document.getElementById('copilotContextBar');
      if (bar) { bar.innerHTML = ''; bar.classList.add('hidden'); }
      const inp = document.getElementById('copilotQuestionInput');
      if (inp) inp.value = '';
      const resBox = document.getElementById('copilotResultContainer');
      if (resBox) resBox.classList.add('hidden');
      const ansMd = document.getElementById('copilotAnswerMarkdown');
      if (ansMd) ansMd.innerHTML = '';
      const tblWrap = document.getElementById('copilotTableWrapper');
      if (tblWrap) tblWrap.innerHTML = '';
      if (!silent) showToast('Started fresh Q&A context.', 'info');
    }

    async function submitCopilotQuestion() {
      const qInput = document.getElementById('copilotQuestionInput');
      const question = (qInput.value || '').trim();
      if (!question) {
        showToast('Type a question first.', 'warn');
        return;
      }
      if (!appState.activeOutputDir) {
        showToast('Please select an example or upload a dataset first.', 'warn');
        return;
      }

      const lang = (document.getElementById('copilotLangSelect').value || appState.briefLanguage || 'en');
      const apiLang = (lang === 'hi') ? 'hi' : 'en';
      const btn = document.getElementById('copilotAskBtn');
      btn.disabled = true;
      btn.textContent = 'Checking Data...';

      try {
        const res = await apiFetch('/api/v1/ask', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            output_dir: appState.activeOutputDir,
            question: question,
            language: apiLang,
            use_llm: false,
            history: (appState.copilotHistory || []).slice(-4)
          })
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `HTTP ${res.status}`);
        }
        const data = await res.json();
        const box = document.getElementById('copilotResultContainer');
        box.classList.remove('hidden');

        // Store turn for multi-turn follow-up memory
        const actFilters = data.active_filters || {};
        if (data.status === 'success') {
          appState.copilotHistory.push({ question: question, active_filters: actFilters });
        }
        const ctxBar = document.getElementById('copilotContextBar');
        if (ctxBar) {
          const fltVals = Object.values(actFilters);
          if (fltVals.length > 0) {
            ctxBar.classList.remove('hidden');
            ctxBar.innerHTML = `<span>🔗 Active Follow-up Filters:</span> ` +
              fltVals.map(v => `<code style="padding:2px 6px;border-radius:6px;background:var(--bg-elevated);">${escapeHtml(v)}</code>`).join(' ');
          } else {
            ctxBar.classList.add('hidden');
            ctxBar.innerHTML = '';
          }
        }

        let mdAnswer = data.answer_markdown || data.plain_summary || data.answer || 'Checked.';
        const trTargetLang = (lang !== 'en' && lang !== 'hi') ? lang : (appState.briefLanguage || 'en');
        if (trTargetLang && trTargetLang !== 'en' && trTargetLang !== 'hi') {
          try {
            const trRes = await apiFetch('/api/v1/i18n/translate-texts', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ target_lang: trTargetLang, texts: { ans: mdAnswer } })
            });
            if (trRes.ok) {
              const trJson = await trRes.json();
              if (trJson.texts && trJson.texts.ans) mdAnswer = trJson.texts.ans;
            }
          } catch (_trErr) {}
        }
        document.getElementById('copilotAnswerMarkdown').innerHTML = renderMarkdownHtml(mdAnswer);
        document.getElementById('copilotSqlCode').textContent = data.sql_executed || '-- Verified query';

        const tableWrap = document.getElementById('copilotTableWrapper');
        const cols = data.columns || [];
        const rows = data.data || [];
        if (cols.length > 0 && rows.length > 0) {
          const sym = (appState.executivePulse && appState.executivePulse.unit_symbol) || '';
          const isHiTbl = (apiLang === 'hi' || appState.briefLanguage === 'hi');
          const numLoc = sym === '₹' ? 'en-IN' : 'en-US';
          const colLabelMap = isHiTbl ? {
            total_records: 'कुल रिकॉर्ड',
            total_orders: 'कुल ऑर्डर',
            adverse_events: 'समस्या के केस',
            total_adverse_events: 'समस्या के केस',
            adverse_rate_pct: 'समस्या दर (%)',
            adverse_capital_drag: 'खतरे में पैसा',
            total_adverse_drag: 'खतरे में पैसा',
            total_portfolio_volume: 'कुल रकम',
            courier_partner: 'डिलीवरी पार्टनर',
            payment_gateway: 'पेमेंट तरीका',
            payment_mode: 'पेमेंट तरीका',
            customer_state: 'राज्य'
          } : {
            total_records: 'Total Records',
            total_orders: 'Total Orders',
            adverse_events: 'Problem Cases',
            total_adverse_events: 'Problem Cases',
            adverse_rate_pct: 'Problem Rate (%)',
            adverse_capital_drag: 'Money at Risk',
            total_adverse_drag: 'Money at Risk',
            total_portfolio_volume: 'Total Value',
            courier_partner: 'Delivery Partner',
            payment_gateway: 'Payment Method',
            payment_mode: 'Payment Method',
            customer_state: 'Customer State'
          };
          const prettyCol = (c) => {
            const key = String(c || '').trim().toLowerCase();
            if (colLabelMap[key]) return colLabelMap[key];
            return String(c).replace(/_pct$/i, ' (%)').replace(/_/g, ' ').replace(/\b\w/g, m => m.toUpperCase());
          };
          const prettyCell = (c, v) => {
            if (v === null || v === undefined) return '—';
            if (typeof v === 'number' && Number.isFinite(v)) {
              const cl = String(c).toLowerCase();
              if (cl.includes('pct') || cl.includes('rate')) return `${v.toFixed(2)}%`;
              if (sym && (cl.includes('drag') || cl.includes('margin') || cl.includes('profit') || cl.includes('discount') || cl.includes('aov') || cl.includes('volume') || cl.includes('amount') || cl.includes('revenue') || cl.includes('loss'))) {
                return formatCurrencyValue(v, sym);
              }
              return Number.isInteger(v) ? v.toLocaleString(numLoc) : v.toLocaleString(numLoc, { maximumFractionDigits: 2 });
            }
            return escapeHtml(v);
          };
          let ths = cols.map(c => `<th>${escapeHtml(prettyCol(c))}</th>`).join('');
          let trs = rows.slice(0, 15).map(r => {
            let tds = cols.map(c => `<td class="tabular-nums">${prettyCell(c, r[c])}</td>`).join('');
            return `<tr>${tds}</tr>`;
          }).join('');
          tableWrap.innerHTML = `<table class="data-table"><thead><tr>${ths}</tr></thead><tbody>${trs}</tbody></table>`;
        } else {
          tableWrap.innerHTML = '';
        }

        showToast('Answer ready!', 'success');
      } catch (e) {
        showToast(`Could not answer question: ${e.message}`, 'error');
      } finally {
        btn.disabled = false;
        const dict = i18nDict[appState.briefLanguage] || i18nDict.en;
        btn.textContent = dict.btnGetAnswer || 'Get Verified Answer';
      }
    }

    // =========================================================================
    // 12-GATE MATHEMATICAL PROOF DRAWER
    // =========================================================================
    const proofSqlCache = { volume: '', target: '', drag: '', bottleneck: '' };

    async function openProofDrawer() {
      const runId = appState.activeRunId || 'hotel_booking_cancellation';
      try {
        const res = await apiFetch(`/api/v1/audit-proof/${encodeURIComponent(runId)}`);
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `HTTP ${res.status}`);
        }
        const data = await res.json();

        const confBadge = document.getElementById('proofConfidenceBadge');
        if (confBadge) {
          const score = Number(data.confidence_score_pct ?? 100).toFixed(1);
          confBadge.textContent = data.all_gates_passed ? `${score}% VERIFIED` : `${score}% PARTIAL`;
        }

        const advRate = Number(data.overall_adverse_rate_pct || 0);
        const ciLow = Number(data.wilson_ci_95 ? data.wilson_ci_95.lower_pct : 0);
        const ciUp = Number(data.wilson_ci_95 ? data.wilson_ci_95.upper_pct : 0);

        document.getElementById('proofObservedRate').textContent = `${advRate.toFixed(2)}%`;
        document.getElementById('proofCiLower').textContent = `${ciLow.toFixed(2)}%`;
        document.getElementById('proofCiUpper').textContent = `${ciUp.toFixed(2)}%`;

        const barLeft = Math.max(0, Math.min(100, ciLow));
        const barWidth = Math.max(1, Math.min(100 - barLeft, ciUp - ciLow));
        const needlePos = Math.max(0, Math.min(100, advRate));

        document.getElementById('proofWilsonBar').style.left = `${barLeft}%`;
        document.getElementById('proofWilsonBar').style.width = `${barWidth}%`;
        document.getElementById('proofWilsonNeedle').style.left = `${needlePos}%`;

        const gatesList = document.getElementById('proofGatesList');
        gatesList.innerHTML = '';
        (data.verification_gates || []).forEach(g => {
          const st = String(g.status || 'PASSED').toUpperCase();
          const badgeCls = st.includes('FAIL') || st.includes('UNSEALED')
            ? 'gate-badge-fail'
            : (st.includes('HOLD') || st.includes('PENDING') ? 'gate-badge-warn' : 'gate-badge-pass');
          const card = document.createElement('div');
          card.className = 'gate-card';
          card.innerHTML = `
            <div class="gate-header">
              <span class="gate-name">Check ${escapeHtml(g.gate_id)} · ${escapeHtml(g.gate_name)}</span>
              <span class="${badgeCls}">${escapeHtml(st)}</span>
            </div>
            <p class="gate-claim">${escapeHtml(g.audit_claim)}</p>
            <div class="gate-tolerance">Tolerance: ${escapeHtml(g.tolerance)}</div>
          `;
          gatesList.appendChild(card);
        });

        const sqls = data.duckdb_sql_proofs || {};
        proofSqlCache.volume = sqls.volume_proof_sql || '-- Physical fact volume query';
        proofSqlCache.target = sqls.target_proof_sql || '-- Adverse event query';
        proofSqlCache.drag = sqls.financial_drag_sql || '-- Capital drag query';
        proofSqlCache.bottleneck = sqls.bottleneck_breakdown_sql || '-- Primary bottleneck query';

        document.getElementById('proofSqlVolume').textContent = proofSqlCache.volume;
        document.getElementById('proofSqlTarget').textContent = proofSqlCache.target;
        document.getElementById('proofSqlDrag').textContent = proofSqlCache.drag;
        document.getElementById('proofSqlBottleneck').textContent = proofSqlCache.bottleneck;

        document.getElementById('proofDrawerModal').classList.remove('hidden');
      } catch (e) {
        showToast(`Audit proof unavailable: ${e.message}`, 'error');
      }
    }

    function closeProofDrawer() {
      document.getElementById('proofDrawerModal').classList.add('hidden');
    }

    function copyProofSql(type) {
      const sql = proofSqlCache[type] || '';
      if (!sql) return;
      copyTextSafe(sql, `Copied verification query!`);
    }

    // =========================================================================
    // SNAPSHOT SWITCHER & REPORT COMPARISON
    // =========================================================================
    let workspaceRunsCache = [];

    async function refreshTimeMachineRuns() {
      const tenant = document.getElementById('tenantInput').value.trim() || 'founder_workspace';
      try {
        let res = await apiFetch(`/api/v1/workspaces/${encodeURIComponent(tenant)}/runs`, { silentAuth: true });
        if (!res.ok) return;
        const data = await res.json();
        workspaceRunsCache = data.runs || [];

        const select = document.getElementById('timeMachineSelect');
        const compA = document.getElementById('compareRunA');
        const compB = document.getElementById('compareRunB');

        select.innerHTML = '<option value="">Switch Report...</option>';
        compA.innerHTML = '';
        compB.innerHTML = '';

        workspaceRunsCache.forEach((r, idx) => {
          const opt = document.createElement('option');
          opt.value = r.run_id;
          const cleanName = String(r.dataset_name || '')
            .replace(/^[⭐📁]\s*/, '')
            .replace(/^Certified Benchmark\s*·\s*/i, '')
            .trim() || humanizeRunTitle(r.run_id);
          const badge = r.is_benchmark ? '⭐' : '📁';
          const rowFmt = formatNumberForCurrency(r.total_records || 0, r.unit_symbol || '$');
          opt.textContent = `${badge} ${cleanName} (${rowFmt} rows)`;
          if (r.run_id === appState.activeRunId) opt.selected = true;
          select.appendChild(opt);

          const optA = opt.cloneNode(true);
          const optB = opt.cloneNode(true);
          compA.appendChild(optA);
          compB.appendChild(optB);
          if (idx === 1) optA.selected = true;
          if (idx === 0) optB.selected = true;
        });
      } catch (e) {}
    }

    async function onTimeMachineChange(runId) {
      if (!runId) return;
      try {
        const res = await apiFetch(`/api/v1/runs/${encodeURIComponent(runId)}`);
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `HTTP ${res.status}`);
        }
        const payload = await res.json();
        hydrateExecutiveConsole(payload);
        showToast(`Switched to: ${humanizeRunTitle(payload.run_id)}`, 'success');
      } catch (e) {
        showToast(`Could not load report: ${e.message}`, 'error');
      }
    }

    function openRunCompareModal() {
      refreshTimeMachineRuns();
      document.getElementById('runCompareModal').classList.remove('hidden');
    }

    function closeRunCompareModal() {
      document.getElementById('runCompareModal').classList.add('hidden');
    }

    async function executeRunComparison() {
      const runA = document.getElementById('compareRunA').value;
      const runB = document.getElementById('compareRunB').value;
      if (!runA || !runB) {
        showToast('Select two reports to compare.', 'warn');
        return;
      }
      const tenant = document.getElementById('tenantInput').value.trim() || 'founder_workspace';
      try {
        const res = await apiFetch(`/api/v1/workspaces/${encodeURIComponent(tenant)}/compare?run_a=${encodeURIComponent(runA)}&run_b=${encodeURIComponent(runB)}`);
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `HTTP ${res.status}`);
        }
        const data = await res.json();
        const box = document.getElementById('compareResultContainer');
        box.classList.remove('hidden');

        document.getElementById('compareStatusBadge').textContent = data.delta.status_badge;
        document.getElementById('compareVolumeVals').textContent =
          `${data.run_a.records.toLocaleString()} → ${data.run_b.records.toLocaleString()}`;
        const volD = data.delta.records;
        const volEl = document.getElementById('compareVolumeDelta');
        volEl.textContent = `${volD >= 0 ? '+' : ''}${volD.toLocaleString()} (${data.delta.records_pct_change}%)`;

        document.getElementById('compareRateVals').textContent =
          `${data.run_a.adverse_rate_pct.toFixed(2)}% → ${data.run_b.adverse_rate_pct.toFixed(2)}%`;
        const rateD = data.delta.adverse_rate_pct;
        const rateEl = document.getElementById('compareRateDelta');
        rateEl.textContent = `${rateD >= 0 ? '+' : ''}${rateD.toFixed(2)} pp`;
        rateEl.style.color = rateD <= 0 ? 'var(--accent-emerald)' : 'var(--accent-crimson)';

        const symA = data.run_a.unit_symbol || '$';
        const symB = data.run_b.unit_symbol || symA;
        const sym = data.delta.unit_symbol || symB;
        document.getElementById('compareDragVals').textContent =
          `${formatCurrencyValue(data.run_a.capital_drag, symA)} → ${formatCurrencyValue(data.run_b.capital_drag, symB)}`;
        const dragEl = document.getElementById('compareDragDelta');
        if (data.delta.currency_mismatch) {
          dragEl.textContent = `N/A (${sym})`;
        } else {
          const dragD = data.delta.capital_drag;
          dragEl.textContent = `${dragD >= 0 ? '+' : ''}${formatCurrencyValue(dragD, sym)}`;
          dragEl.style.color = dragD <= 0 ? 'var(--accent-emerald)' : 'var(--accent-crimson)';
        }

        document.getElementById('compareNotesEn').textContent = data.executive_notes.english;
        document.getElementById('compareNotesHi').textContent = data.executive_notes.hinglish;
      } catch (e) {
        showToast(`Comparison failed: ${e.message}`, 'error');
      }
    }

    // =========================================================================
    // MULTI-FILE UPLOAD
    // =========================================================================
    let multiFilesPending = [];

    async function triggerMultiIntentHandshake(files) {
      multiFilesPending = files;
      const region = document.getElementById('regionSelect').value || 'US';
      const fd = new FormData();
      files.forEach(f => fd.append('files', f));
      fd.append('region_profile', region);

      showToast(`Linking ${files.length} spreadsheets...`, 'info');
      try {
        const res = await apiFetch('/api/v1/preview-multi-intent', { method: 'POST', body: fd });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `HTTP ${res.status}`);
        }
        const data = await res.json();

        const fact = data.fact_table || {};
        document.getElementById('starFactName').textContent = fact.table_name || 'Main_Sheet';
        document.getElementById('starFactRowsBadge').textContent = `~${(fact.estimated_rows || 0).toLocaleString()} rows`;
        const goal = data.detected_goal || {};
        const costSummary = goal.cost_col ? `${goal.cost_col} (${goal.unit_symbol || '$'})` : 'Count Only';
        document.getElementById('starFactGoalDetail').innerHTML = `
          Problem Column: <strong>${escapeHtml(goal.target_col || 'None')}</strong> ·
          Money Column: <strong>${escapeHtml(costSummary)}</strong><br/>
          <em>"${escapeHtml(goal.business_question_en || 'Combined business analysis')}"</em>
        `;

        const starTgt = document.getElementById('starTargetSelect');
        const starCost = document.getElementById('starCostSelect');
        if (starTgt) {
          starTgt.innerHTML = '';
          (data.candidate_targets || []).forEach(c => {
            const opt = document.createElement('option');
            opt.value = c.column;
            opt.textContent = `${c.column} (${c.adverse_rate_sample_pct ?? 0}% rate)`;
            if (c.is_detected_default) opt.selected = true;
            starTgt.appendChild(opt);
          });
          if (starTgt.options.length === 0 && fact.columns) {
            fact.columns.forEach(col => {
              const opt = document.createElement('option');
              opt.value = col;
              opt.textContent = col;
              if (col === goal.target_col) opt.selected = true;
              starTgt.appendChild(opt);
            });
          }
        }
        if (starCost) {
          starCost.innerHTML = '<option value="__NONE__">No Money Column</option>';
          (data.candidate_costs || []).forEach(c => {
            const opt = document.createElement('option');
            opt.value = c.column;
            opt.textContent = `${c.column} (Avg: ${c.unit_symbol || '$'}${c.sample_mean})`;
            if (c.is_detected_default) opt.selected = true;
            starCost.appendChild(opt);
          });
        }

        const dimGrid = document.getElementById('starDimGrid');
        dimGrid.innerHTML = '';
        (data.dimension_tables || []).forEach(dim => {
          const dCard = document.createElement('div');
          dCard.className = 'schema-dim-card';
          dCard.innerHTML = `
            <div style="font-size: 13px; font-weight: 700;">${escapeHtml(dim.table_name)}</div>
            <div style="font-size: 12px; color: var(--text-muted); margin: 3px 0;">
              ${(dim.estimated_rows || 0).toLocaleString()} rows · ${escapeHtml(dim.columns_count)} columns
            </div>
          `;
          dimGrid.appendChild(dCard);
        });

        const joinsList = document.getElementById('starJoinsList');
        joinsList.innerHTML = '';
        const joins = data.relational_joins || [];
        if (joins.length === 0) {
          joinsList.innerHTML = '<span style="font-size: 12px; color: var(--text-muted);">Sheets ready for combined analysis.</span>';
        } else {
          joins.forEach(j => {
            const edge = document.createElement('div');
            edge.className = 'join-edge-badge';
            edge.innerHTML = `
              <strong>${escapeHtml(j.source_table)}.${escapeHtml(j.source_key)}</strong>
              <span>⟷</span>
              <strong>${escapeHtml(j.target_table)}.${escapeHtml(j.target_key)}</strong>
            `;
            joinsList.appendChild(edge);
          });
        }

        document.getElementById('starSchemaModal').classList.remove('hidden');
      } catch (e) {
        showToast(`Could not link sheets: ${e.message}`, 'error');
      }
    }

    function openLiveErpModal() {
      const m = document.getElementById('liveErpSyncModal');
      if (m) m.classList.remove('hidden');
      updateLiveErpFields();
    }

    function closeLiveErpModal() {
      const m = document.getElementById('liveErpSyncModal');
      if (m) m.classList.add('hidden');
    }

    function updateLiveErpFields() {
      const prov = (document.getElementById('liveErpProviderSelect') || {}).value || 'tally_xml';
      const box = document.getElementById('liveErpCredFields');
      if (!box) return;
      if (prov === 'tally_xml') {
        box.innerHTML = `
          <div class="form-field">
            <label for="liveTallyXmlInput">Paste Tally Prime DayBook / Sales Register XML</label>
            <textarea id="liveTallyXmlInput" rows="6" style="width:100%;box-sizing:border-box;font-family:var(--font-mono);font-size:11.5px;" placeholder="<ENVELOPE><BODY><DATA><TALLYMESSAGE><VOUCHER>...</VOUCHER></TALLYMESSAGE></DATA></BODY></ENVELOPE>"></textarea>
          </div>`;
      } else if (prov === 'shopify') {
        box.innerHTML = `
          <div class="form-field"><label>Shopify Store Domain</label><input id="liveCredF1" type="text" placeholder="my-store.myshopify.com" /></div>
          <div class="form-field"><label>Admin API Access Token (Read-Only)</label><input id="liveCredF2" type="password" placeholder="shpat_..." /></div>`;
      } else if (prov === 'woocommerce') {
        box.innerHTML = `
          <div class="form-field"><label>Store URL</label><input id="liveCredF1" type="url" placeholder="https://mystore.com" /></div>
          <div class="form-field"><label>Consumer Key</label><input id="liveCredF2" type="text" placeholder="ck_..." /></div>
          <div class="form-field"><label>Consumer Secret</label><input id="liveCredF3" type="password" placeholder="cs_..." /></div>`;
      } else if (prov === 'razorpay') {
        box.innerHTML = `
          <div class="form-field"><label>Razorpay Key ID</label><input id="liveCredF1" type="text" placeholder="rzp_live_..." /></div>
          <div class="form-field"><label>Razorpay Key Secret</label><input id="liveCredF2" type="password" placeholder="Secret key" /></div>`;
      } else if (prov === 'stripe') {
        box.innerHTML = `
          <div class="form-field"><label>Stripe Restricted Read-Only Key</label><input id="liveCredF1" type="password" placeholder="rk_live_..." /></div>`;
      } else if (prov === 'zoho_books') {
        box.innerHTML = `
          <div class="form-field"><label>Zoho OAuth Access Token</label><input id="liveCredF1" type="password" placeholder="1000.xxxx" /></div>
          <div class="form-field"><label>Organization ID</label><input id="liveCredF2" type="text" placeholder="60012345678" /></div>`;
      }
    }

    async function submitLiveErpSync() {
      const prov = (document.getElementById('liveErpProviderSelect') || {}).value || 'tally_xml';
      const creds = {};
      if (prov === 'tally_xml') {
        creds.xml_content = (document.getElementById('liveTallyXmlInput') || {}).value || '';
      } else if (prov === 'shopify') {
        creds.shop_domain = (document.getElementById('liveCredF1') || {}).value || '';
        creds.access_token = (document.getElementById('liveCredF2') || {}).value || '';
      } else if (prov === 'woocommerce') {
        creds.store_url = (document.getElementById('liveCredF1') || {}).value || '';
        creds.consumer_key = (document.getElementById('liveCredF2') || {}).value || '';
        creds.consumer_secret = (document.getElementById('liveCredF3') || {}).value || '';
      } else if (prov === 'razorpay') {
        creds.key_id = (document.getElementById('liveCredF1') || {}).value || '';
        creds.key_secret = (document.getElementById('liveCredF2') || {}).value || '';
      } else if (prov === 'stripe') {
        creds.api_key = (document.getElementById('liveCredF1') || {}).value || '';
      } else if (prov === 'zoho_books') {
        creds.access_token = (document.getElementById('liveCredF1') || {}).value || '';
        creds.organization_id = (document.getElementById('liveCredF2') || {}).value || '';
      }
      const btn = document.getElementById('btnSubmitLiveErpSync');
      if (btn) { btn.disabled = true; btn.textContent = 'Syncing Live Data...'; }
      try {
        const tenant = (document.getElementById('tenantInput') || {}).value?.trim() || 'founder_workspace';
        const region = (document.getElementById('regionSelect') || {}).value || 'IN';
        const res = await apiFetch('/api/v1/connectors/live-sync', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ provider: prov, credentials: creds, tenant_id: tenant, region_profile: region, limit: 200 })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || `Sync failed (${res.status})`);
        closeLiveErpModal();
        hydrateFromAnalysisPayload(data);
        document.getElementById('onboardingSection').classList.add('hidden');
        showToast(`Live ${prov} sync complete (${data.total_records} records audited)!`, 'success');
      } catch (e) {
        showToast(`Live sync error: ${e.message}`, 'error');
      } finally {
        if (btn) { btn.disabled = false; btn.textContent = '⚡ Sync & Audit Live Data'; }
      }
    }

    async function dispatchQuickLeakAlert(channel = 'whatsapp') {
      const runId = appState.activeRunId;
      if (!runId) {
        showToast('Load or analyze a dataset first.', 'error');
        return;
      }
      const promptLabel = channel === 'whatsapp'
        ? 'Enter WhatsApp number (e.g. +919876543210) or leave blank for preview:'
        : 'Enter recipient email (e.g. founder@company.com) or leave blank for preview:';
      const defaultTarget = channel === 'whatsapp' ? '+919876543210' : 'founder@company.com';
      const recipient = window.prompt(promptLabel, defaultTarget) || defaultTarget;
      const lang = appState.briefLanguage === 'hi' ? 'hi' : 'en';
      try {
        const res = await apiFetch(`/api/v1/alerts/dispatch/${encodeURIComponent(runId)}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ channel, recipient, lang })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Alert dispatch failed');
        if (data.status === 'sent') {
          showToast(`Alert delivered via ${data.provider || channel} to ${recipient}!`, 'success');
        } else {
          showToast(`Alert formatted (${data.status}): ${data.reason || 'Preview ready'}`, 'info');
        }
      } catch (e) {
        showToast(`Alert error: ${e.message}`, 'error');
      }
    }

    function closeStarSchemaModal() {
      document.getElementById('starSchemaModal').classList.add('hidden');
    }

    async function confirmMultiTableIngestion() {
      if (!multiFilesPending || multiFilesPending.length === 0) return;
      const starTgt = document.getElementById('starTargetSelect');
      const starCost = document.getElementById('starCostSelect');
      const targetOverride = starTgt ? (starTgt.value || '') : '';
      const costOverride = starCost ? (starCost.value || '') : '';
      closeStarSchemaModal();

      const tenant = document.getElementById('tenantInput').value.trim() || 'founder_workspace';
      const region = document.getElementById('regionSelect').value || 'US';

      const progSec = document.getElementById('jobProgressSection');
      progSec.classList.remove('hidden');
      document.getElementById('progressStageName').textContent = 'Combining linked sheets & finding leaks...';
      document.getElementById('progressBarFill').style.width = '15%';
      document.getElementById('progressPctLabel').textContent = '15%';

      const fd = new FormData();
      multiFilesPending.forEach(f => fd.append('files', f));
      fd.append('tenant_id', tenant);
      fd.append('region_profile', region);
      fd.append('mode', 'ai');
      if (targetOverride) fd.append('target_override', targetOverride);
      if (costOverride) fd.append('cost_override', costOverride);

      try {
        const res = await apiFetch('/api/v1/jobs/submit', { method: 'POST', body: fd });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `Upload failed (${res.status})`);
        }
        const data = await res.json();
        await pollJobUntilComplete(data.job_id);
      } catch (e) {
        progSec.classList.add('hidden');
        showToast(`Analysis error: ${e.message}`, 'error');
      }
    }

    // =========================================================================
    // PHASE B: WORKSPACE HUB (1-CLICK OAUTH, SCHEDULED DIGESTS, TEAM RBAC, BILLING)
    // =========================================================================
    function openWorkspaceHubModal(initialTab = 'oauth') {
      const m = document.getElementById('workspaceHubModal');
      if (m) m.classList.remove('hidden');
      switchWorkspaceHubTab(initialTab);
    }

    function closeWorkspaceHubModal() {
      const m = document.getElementById('workspaceHubModal');
      if (m) m.classList.add('hidden');
    }

    function switchWorkspaceHubTab(tab) {
      const tabs = ['oauth', 'schedules', 'team', 'billing'];
      tabs.forEach(t => {
        const cap = t.charAt(0).toUpperCase() + t.slice(1);
        const btn = document.getElementById('hubTab' + cap);
        const pane = document.getElementById('hubPane' + cap);
        if (btn) btn.className = (t === tab) ? 'btn btn-primary btn-sm' : 'btn btn-secondary btn-sm';
        if (pane) pane.classList.toggle('hidden', t !== tab);
      });
      if (tab === 'oauth') loadWorkspaceOAuthTab();
      if (tab === 'schedules') loadWorkspaceSchedulesTab();
      if (tab === 'team') loadWorkspaceTeamTab();
      if (tab === 'billing') loadWorkspaceBillingTab();
    }

    async function loadWorkspaceOAuthTab() {
      const box = document.getElementById('hubOauthProvidersList');
      if (!box) return;
      box.innerHTML = '<div style="font-size:12.5px;color:var(--text-secondary);">Loading OAuth providers...</div>';
      try {
        const [pRes, cRes] = await Promise.all([
          apiFetch('/api/v1/oauth/providers'),
          apiFetch('/api/v1/oauth/connections'),
        ]);
        const providers = pRes.ok ? ((await pRes.json()).providers || []) : [];
        const conns = cRes.ok ? ((await cRes.json()).connections || []) : [];
        const connMap = {};
        conns.forEach(c => { connMap[c.provider] = c; });

        box.innerHTML = providers.map(p => {
          const active = connMap[p.id];
          const badge = active
            ? `<span style="color:var(--accent-emerald);font-weight:700;">● Connected (${escapeHtml(active.account_label || p.name)})</span>`
            : `<span style="color:var(--text-muted);">${p.oauth_configured ? '○ Ready for 1-Click OAuth' : '○ Env Keys Needed'}</span>`;
          return `
            <div style="padding:12px;border-radius:10px;border:1px solid var(--border-subtle);background:var(--bg-soft);display:flex;flex-direction:column;gap:8px;">
              <div style="display:flex;justify-content:space-between;align-items:center;gap:6px;">
                <strong style="font-size:14px;">${escapeHtml(p.name)}</strong>
                <span style="font-size:11px;color:var(--text-secondary);">${escapeHtml(p.category)}</span>
              </div>
              <div style="font-size:12px;color:var(--text-secondary);">${escapeHtml(p.description)}</div>
              <div style="font-size:11.5px;">${badge}</div>
              <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:auto;">
                <button type="button" class="btn btn-primary btn-sm" onclick="startOAuthFromUI('${escapeHtml(p.id)}')">${active ? 'Reconnect' : '1-Click Connect'}</button>
                ${active ? `<button type="button" class="btn btn-sky btn-sm" onclick="syncOAuthProviderFromUI('${escapeHtml(p.id)}')">🔄 Sync Now</button>` : ''}
                ${active ? `<button type="button" class="btn btn-secondary btn-sm" onclick="disconnectOAuthFromUI('${escapeHtml(p.id)}')">Disconnect</button>` : ''}
              </div>
            </div>
          `;
        }).join('');
      } catch (e) {
        box.innerHTML = `<div style="color:var(--accent-rose);font-size:12.5px;">Error loading OAuth connectors: ${escapeHtml(e.message)}</div>`;
      }
    }

    async function startOAuthFromUI(provider) {
      const shopDomain = (document.getElementById('oauthShopDomainInput')?.value || '').trim();
      const zohoOrg = (document.getElementById('oauthZohoOrgInput')?.value || '').trim();
      try {
        const res = await apiFetch(`/api/v1/oauth/${encodeURIComponent(provider)}/start`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            shop_domain: shopDomain || undefined,
            organization_id: zohoOrg || undefined,
          }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || `OAuth start failed (${res.status})`);
        if (data.status === 'authorization_url_created' && data.authorization_url) {
          window.open(data.authorization_url, '_blank', 'noopener,noreferrer');
          showToast(`Opened ${data.provider_name} OAuth approval window.`, 'success');
        } else {
          showToast(data.message || 'Set OAuth client env vars in .env.production to enable live redirect.', 'info');
        }
      } catch (e) {
        showToast(e.message, 'error');
      }
    }

    async function syncOAuthProviderFromUI(provider) {
      const region = document.getElementById('regionSelect')?.value || 'US';
      showToast(`Syncing live data from ${provider}...`, 'info');
      try {
        const res = await apiFetch(`/api/v1/oauth/${encodeURIComponent(provider)}/sync`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ region_profile: region, limit: 1000 }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || `Live sync failed (${res.status})`);
        closeWorkspaceHubModal();
        showToast(`Live ${provider} audit completed!`, 'success');
        if (typeof renderAnalysisResult === 'function') renderAnalysisResult(data);
      } catch (e) {
        showToast(e.message, 'error');
      }
    }

    async function disconnectOAuthFromUI(provider) {
      try {
        const res = await apiFetch(`/api/v1/oauth/${encodeURIComponent(provider)}/disconnect`, { method: 'DELETE' });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || `Disconnect failed (${res.status})`);
        showToast(`Disconnected ${provider} & wiped encrypted token.`, 'success');
        loadWorkspaceOAuthTab();
      } catch (e) {
        showToast(e.message, 'error');
      }
    }

    async function loadWorkspaceSchedulesTab() {
      const box = document.getElementById('hubSchedulesList');
      if (!box) return;
      try {
        const res = await apiFetch('/api/v1/schedules');
        const data = await res.json().catch(() => ({}));
        const rows = data.schedules || [];
        if (!rows.length) {
          box.innerHTML = '<div style="font-size:12.5px;color:var(--text-secondary);">No recurring schedules saved yet. Create one above!</div>';
          return;
        }
        box.innerHTML = rows.map(s => `
          <div style="padding:10px 12px;border-radius:8px;border:1px solid var(--border-subtle);background:var(--bg-soft);display:flex;justify-content:space-between;align-items:center;gap:10px;">
            <div>
              <strong style="font-size:13px;">${escapeHtml(s.name)}</strong>
              <div style="font-size:11.5px;color:var(--text-secondary);">
                ${escapeHtml(s.frequency)} · ${escapeHtml(s.channel.toUpperCase())} → ${escapeHtml(s.recipient || s.webhook_url || '')} · Source: ${escapeHtml(s.source_ref)}
              </div>
              ${s.last_status ? `<div style="font-size:11px;color:var(--accent-emerald);">Last run: ${escapeHtml(s.last_status)}</div>` : ''}
            </div>
            <button type="button" class="btn btn-secondary btn-sm" onclick="deleteScheduleFromUI('${escapeHtml(s.schedule_id)}')">🗑</button>
          </div>
        `).join('');
      } catch (e) {
        box.innerHTML = `<div style="color:var(--accent-rose);font-size:12.5px;">${escapeHtml(e.message)}</div>`;
      }
    }

    async function createScheduledDigestFromUI() {
      const name = (document.getElementById('schedNameInput')?.value || 'Morning Digest').trim();
      const frequency = document.getElementById('schedFreqSelect')?.value || 'weekly_monday';
      const channel = document.getElementById('schedChannelSelect')?.value || 'email';
      const lang = document.getElementById('schedLangSelect')?.value || 'hi';
      const target = (document.getElementById('schedRecipientInput')?.value || '').trim();
      const runRef = appState.currentRunId || 'hotel_booking_cancellation';
      const payload = {
        name, frequency, channel, lang,
        source_type: 'run_id',
        source_ref: runRef,
        recipient: channel === 'webhook' ? undefined : target,
        webhook_url: channel === 'webhook' ? target : undefined,
      };
      try {
        const res = await apiFetch('/api/v1/schedules', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || `Schedule failed (${res.status})`);
        showToast('Recurring Morning Digest schedule saved!', 'success');
        loadWorkspaceSchedulesTab();
      } catch (e) {
        showToast(e.message, 'error');
      }
    }

    async function deleteScheduleFromUI(sid) {
      try {
        const res = await apiFetch(`/api/v1/schedules/${encodeURIComponent(sid)}`, { method: 'DELETE' });
        if (!res.ok) {
          const d = await res.json().catch(() => ({}));
          throw new Error(d.detail || 'Delete failed');
        }
        showToast('Schedule deleted.', 'success');
        loadWorkspaceSchedulesTab();
      } catch (e) {
        showToast(e.message, 'error');
      }
    }

    async function runDueSchedulesNow() {
      try {
        const res = await apiFetch('/api/v1/schedules/run-due', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({}),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || 'Cron sweep failed');
        showToast(`Cron sweep complete: ${data.processed_count || 0} due schedule(s) processed.`, 'success');
        loadWorkspaceSchedulesTab();
      } catch (e) {
        showToast(e.message, 'error');
      }
    }

    async function loadWorkspaceTeamTab() {
      const box = document.getElementById('hubTeamMembersList');
      if (!box) return;
      try {
        const res = await apiFetch('/api/v1/team/members');
        const data = await res.json().catch(() => ({}));
        const members = data.members || [];
        const invites = data.pending_invites || [];
        let htmlOut = members.map(m => `
          <div style="padding:10px 12px;border-radius:8px;border:1px solid var(--border-subtle);background:var(--bg-soft);display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap;">
            <div>
              <strong style="font-size:13px;">${escapeHtml(m.email)}</strong>
              <span style="margin-left:8px;font-size:11px;padding:2px 8px;border-radius:999px;background:var(--bg-card);border:1px solid var(--border-subtle);">${escapeHtml(m.role.toUpperCase())}</span>
            </div>
            <div style="display:flex;gap:6px;align-items:center;">
              <select onchange="updateTeamRoleFromUI('${escapeHtml(m.user_id)}', this.value)" style="font-size:12px;padding:4px 8px;">
                <option value="owner" ${m.role==='owner'?'selected':''}>Owner</option>
                <option value="analyst" ${m.role==='analyst'?'selected':''}>Analyst</option>
                <option value="viewer" ${m.role==='viewer'?'selected':''}>Viewer</option>
              </select>
              <button type="button" class="btn btn-secondary btn-sm" onclick="removeTeamMemberFromUI('${escapeHtml(m.user_id)}')">Remove</button>
            </div>
          </div>
        `).join('');
        if (invites.length) {
          htmlOut += `<div style="font-size:11.5px;font-weight:700;margin-top:8px;color:var(--text-secondary);">PENDING INVITES (${invites.length})</div>`;
          htmlOut += invites.map(i => `
            <div style="padding:8px 12px;border-radius:8px;border:1px dashed var(--border-subtle);font-size:12px;color:var(--text-secondary);">
              ✉️ ${escapeHtml(i.email)} — Role: <strong>${escapeHtml(i.role)}</strong>
            </div>
          `).join('');
        }
        box.innerHTML = htmlOut || '<div style="font-size:12.5px;color:var(--text-secondary);">Sign in as a workspace owner to manage team members.</div>';
      } catch (e) {
        box.innerHTML = `<div style="color:var(--accent-rose);font-size:12.5px;">${escapeHtml(e.message)}</div>`;
      }
    }

    async function inviteTeamMemberFromUI() {
      const email = (document.getElementById('teamInviteEmailInput')?.value || '').trim();
      const role = document.getElementById('teamInviteRoleSelect')?.value || 'analyst';
      try {
        const res = await apiFetch('/api/v1/team/invite', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, role }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || `Invite failed (${res.status})`);
        const tBox = document.getElementById('teamInviteTokenBox');
        if (tBox) {
          tBox.classList.remove('hidden');
          tBox.innerHTML = `✅ Invite created for <strong>${escapeHtml(data.email)}</strong> (${escapeHtml(data.role)}). Share single-use token: <code>${escapeHtml(data.invite_token)}</code>`;
        }
        loadWorkspaceTeamTab();
      } catch (e) {
        showToast(e.message, 'error');
      }
    }

    async function updateTeamRoleFromUI(userId, newRole) {
      try {
        const res = await apiFetch(`/api/v1/team/members/${encodeURIComponent(userId)}/role`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ role: newRole }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || 'Role update failed');
        showToast(`Updated role to ${newRole}.`, 'success');
        loadWorkspaceTeamTab();
      } catch (e) {
        showToast(e.message, 'error');
        loadWorkspaceTeamTab();
      }
    }

    async function removeTeamMemberFromUI(userId) {
      try {
        const res = await apiFetch(`/api/v1/team/members/${encodeURIComponent(userId)}`, { method: 'DELETE' });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || 'Remove failed');
        showToast('Member removed and tokens revoked.', 'success');
        loadWorkspaceTeamTab();
      } catch (e) {
        showToast(e.message, 'error');
      }
    }

    async function loadWorkspaceBillingTab() {
      const sumBox = document.getElementById('hubBillingSummary');
      const gridBox = document.getElementById('hubBillingPlansGrid');
      if (!sumBox || !gridBox) return;
      try {
        const [stRes, plRes] = await Promise.all([
          apiFetch('/api/v1/billing/status'),
          apiFetch('/api/v1/billing/plans'),
        ]);
        const st = stRes.ok ? await stRes.json() : {};
        const plans = plRes.ok ? ((await plRes.json()).plans || []) : [];
        const u = st.usage || {};
        sumBox.innerHTML = `
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
            <div>
              <div style="font-size:11px;color:var(--text-secondary);">ACTIVE PLAN</div>
              <strong style="font-size:16px;">${escapeHtml(st.plan_name || 'Free Trial')}</strong>
              <span style="font-size:12px;color:var(--text-secondary);margin-left:8px;">Period: ${escapeHtml(st.billing_period || '')}</span>
            </div>
            <div style="font-size:12.5px;">
              Audits: <strong>${u.runs_used ?? 0} / ${u.runs_limit ?? 3}</strong> · Q&amp;A: <strong>${u.qa_used ?? 0} / ${u.qa_limit ?? 25}</strong>
            </div>
          </div>
        `;
        gridBox.innerHTML = plans.filter(p => p.plan_id !== 'free').map(p => `
          <div style="padding:12px;border-radius:10px;border:1px solid var(--border-subtle);background:var(--bg-soft);display:flex;flex-direction:column;gap:6px;">
            <strong style="font-size:14px;">${escapeHtml(p.name)}</strong>
            <div style="font-size:13px;font-weight:700;">$${p.price_usd_monthly}/mo · ₹${p.price_inr_monthly}/mo</div>
            <div style="font-size:11.5px;color:var(--text-secondary);">${p.max_runs_per_month} runs/mo · ${p.max_qa_per_month} Q&amp;A/mo</div>
            <div style="display:flex;gap:6px;margin-top:6px;flex-wrap:wrap;">
              <button type="button" class="btn btn-primary btn-sm" onclick="startBillingUpgradeFromUI('${escapeHtml(p.plan_id)}', 'stripe')">Stripe (USD)</button>
              <button type="button" class="btn btn-amber btn-sm" onclick="startBillingUpgradeFromUI('${escapeHtml(p.plan_id)}', 'razorpay')">Razorpay (INR/UPI)</button>
            </div>
          </div>
        `).join('');
      } catch (e) {
        sumBox.innerHTML = `<div style="color:var(--accent-rose);font-size:12.5px;">${escapeHtml(e.message)}</div>`;
      }
    }

    async function startBillingUpgradeFromUI(planId, provider) {
      try {
        const res = await apiFetch('/api/v1/billing/checkout', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ plan_id: planId, provider }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || `Checkout failed (${res.status})`);
        if (data.status === 'checkout_created' && data.checkout_url) {
          window.open(data.checkout_url, '_blank', 'noopener,noreferrer');
          showToast(`Opened ${provider} checkout window.`, 'success');
        } else {
          showToast(data.message || 'Configure payment keys in .env.production to activate live checkout.', 'info');
        }
      } catch (e) {
        showToast(e.message, 'error');
      }
    }

    // =========================================================================
    // STAGE 8: AI DECISION PREDICTOR & MONTE CARLO SIMULATOR ("DECISION LAB")
    // =========================================================================
    async function loadDecisionPredictorOverview(forceReload = false) {
      const runId = appState.activeRunId;
      if (!runId) return;
      const activeLang = appState.briefLanguage || 'en';
      const cacheKey = `${runId}::${activeLang}`;
      if (!forceReload && appState.predictOverview && appState.predictOverviewRunId === cacheKey) {
        renderDecisionPredictorOverview(appState.predictOverview);
        loadPredictCommitments();
        return;
      }

      const pill = document.getElementById('predictModelHonestyPill');
      const grid = document.getElementById('predictPresetsGrid');
      if (pill) {
        pill.className = 'predict-honesty-pill';
        pill.textContent = `🧠 ${tUi('lblModelTraining', 'Training calibrated ML model...')}`;
      }
      if (grid) {
        grid.innerHTML = `<div style="grid-column:1/-1;padding:18px;text-align:center;color:var(--text-muted);font-size:13px;">${escapeHtml(tUi('lblLoadingScenarios', 'Loading smart 1-click decision scenarios from your data...'))}</div>`;
      }

      try {
        const res = await apiFetch(`/api/v1/predict/overview/${encodeURIComponent(runId)}?lang=${encodeURIComponent(activeLang)}`);
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || `Failed to train model (${res.status})`);
        appState.predictOverview = data;
        appState.predictOverviewRunId = cacheKey;
        renderDecisionPredictorOverview(data);
        loadPredictCommitments();
      } catch (e) {
        if (pill) {
          pill.className = 'predict-honesty-pill warn';
          pill.textContent = `⚠️ ${e.message}`;
        }
        if (grid) {
          grid.innerHTML = `<div style="grid-column:1/-1;padding:16px;text-align:center;color:var(--accent-crimson);font-size:13px;">${escapeHtml(e.message)}</div>`;
        }
      }
    }

    function renderDecisionPredictorOverview(overview) {
      if (!overview) return;
      const isHi = appState.briefLanguage === 'hi';
      const m = overview.model_metrics || {};
      const auc = Number(m.roc_auc || 0);
      const tier = String(m.confidence_tier || 'MODERATE');
      const pill = document.getElementById('predictModelHonestyPill');
      if (pill) {
        const bb = m.blind_backtest_badge || null;
        pill.className = (tier === 'LOW' || (bb && !bb.verified)) ? 'predict-honesty-pill warn' : 'predict-honesty-pill';
        const blocked = (m.blocked_leakage_columns || []).length;
        const guardTxt = blocked > 0 ? (isHi ? ` · ${blocked} लीकेज ब्लॉक` : ` · ${blocked} Leakage Blocked`) : '';
        if (bb && bb.label_en) {
          pill.textContent = `🛡️ ${isHi ? (bb.label_hi || bb.label_en) : bb.label_en} · AUC ${auc.toFixed(2)}${guardTxt}`;
        } else {
          const ootVal = m.temporal_backtest_auc;
          const ootTxt = (ootVal !== null && ootVal !== undefined)
            ? (isHi ? ` · फ्यूचर बैकटेस्ट: ${Number(ootVal).toFixed(2)}` : ` · Future Backtest: ${Number(ootVal).toFixed(2)}`)
            : '';
          pill.textContent = isHi
            ? `🛡️ मल्टी-मॉडल AI सटीकता (ROC-AUC): ${auc.toFixed(2)} (${m.confidence_label_hi || tier})${ootTxt}${guardTxt}`
            : `🛡️ Multi-Model ROC-AUC: ${auc.toFixed(2)} (${tier} Confidence)${ootTxt}${guardTxt}`;
        }
      }

      // Render 4 Friendly 1-Click Scenario Cards
      const presets = overview.presets || [];
      const grid = document.getElementById('predictPresetsGrid');
      if (grid) {
        if (!presets.length) {
          grid.innerHTML = `<div style="grid-column:1/-1;padding:14px;text-align:center;color:var(--text-muted);font-size:13px;">${isHi ? 'नीचे बॉक्स में अपना फ़ैसला लिखकर सीधे टेस्ट करें।' : 'Type any business change in the box below or use the Custom Builder to simulate.'}</div>`;
        } else {
          grid.innerHTML = presets.map((p, idx) => `
            <button type="button" class="predict-preset-card" data-preset-idx="${idx}" onclick="runPredictPreset(${idx})">
              <div class="predict-preset-icon">${escapeHtml(p.icon || '🔮')}</div>
              <div>
                <div class="predict-preset-title">${escapeHtml(isHi ? (p.title_hi || p.title_en) : p.title_en)}</div>
                <div class="predict-preset-sub">${escapeHtml(isHi ? (p.subtitle_hi || p.subtitle_en) : p.subtitle_en)}</div>
              </div>
            </button>
          `).join('');
        }
      }

      // Populate Custom Visual Builder Dropdowns
      populatePredictCustomBuilder(overview.levers || []);

      // Render Top Drivers & Honesty Strip
      const strip = document.getElementById('predictDriversStrip');
      if (strip) {
        const drivers = (overview.top_drivers || []).slice(0, 5);
        const chips = drivers.map(d =>
          `<span class="predict-driver-chip">${escapeHtml(String(d.feature || '').replace(/_/g, ' '))} <strong style="color:var(--accent-sky);">${Number(d.importance_pct || 0).toFixed(1)}%</strong></span>`
        ).join('');
        const blockedList = (m.blocked_leakage_columns || []);
        const blockedNote = blockedList.length
          ? `<span style="color:var(--accent-emerald);font-weight:700;">🛡️ ${escapeHtml(tUi('lblLeakageBlocked', 'Leakage Blocked'))}: <code>${escapeHtml(blockedList.slice(0, 4).join(', '))}</code></span>`
          : `<span>✅ ${escapeHtml(tUi('lblZeroLeakage', 'Zero Post-Event Leakage Verified'))}</span>`;
        strip.innerHTML = `
          <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
            <strong style="color:var(--text-primary);">${escapeHtml(tUi('lblTopDrivers', 'Top AI Drivers:'))}</strong>
            ${chips || '<span>Balanced baseline</span>'}
          </div>
          <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
            <span>${escapeHtml(tUi('lblCalibrationGap', 'Calibration Gap'))}: <strong>${Number(m.calibration_gap_pct || 0).toFixed(2)}%</strong></span>
            ${blockedNote}
          </div>
        `;
      }
    }

    function populatePredictCustomBuilder(levers) {
      const colSel = document.getElementById('predictColSelect');
      const scopeSel = document.getElementById('predictScopeSelect');
      if (!colSel) return;
      const prevCol = colSel.value;
      colSel.innerHTML = levers.map(lv =>
        `<option value="${escapeHtml(lv.column)}">${escapeHtml(lv.column.replace(/_/g, ' '))} (${lv.type === 'numeric' ? 'Number' : 'Group'})</option>`
      ).join('');
      if (prevCol && levers.some(l => l.column === prevCol)) {
        colSel.value = prevCol;
      }

      if (scopeSel) {
        let opts = `<option value="">${escapeHtml(tUi('lblEntireBusiness', 'Entire Business (All Rows)'))}</option>`;
        levers.filter(l => l.type === 'categorical').slice(0, 5).forEach(lv => {
          (lv.values || []).slice(0, 12).forEach(val => {
            opts += `<option value="${escapeHtml(lv.column)}|||${escapeHtml(val)}">${escapeHtml(lv.column.replace(/_/g, ' '))}: ${escapeHtml(val)}</option>`;
          });
        });
        scopeSel.innerHTML = opts;
      }
      onPredictBuilderColChange();
    }

    function onPredictBuilderColChange() {
      const levers = (appState.predictOverview && appState.predictOverview.levers) || [];
      const col = document.getElementById('predictColSelect')?.value || '';
      const lv = levers.find(x => x.column === col);
      const actSel = document.getElementById('predictActionSelect');
      if (!lv || !actSel) return;
      const isHi = appState.briefLanguage === 'hi';

      if (lv.type === 'categorical') {
        actSel.innerHTML = `
          <option value="replace_category">${isHi ? 'बदलें (A की जगह B करें)' : 'Replace Value (Swap A → B)'}</option>
          <option value="pause_segment">${isHi ? 'रोकें / बंद करें (Pause)' : 'Pause / Stop Segment Completely'}</option>
        `;
        const fromSel = document.getElementById('predictFromSelect');
        const toSel = document.getElementById('predictToSelect');
        const vals = lv.values || [];
        if (fromSel) fromSel.innerHTML = vals.map(v => `<option value="${escapeHtml(v)}">${escapeHtml(v)}</option>`).join('');
        if (toSel) toSel.innerHTML = vals.map((v, i) => `<option value="${escapeHtml(v)}" ${i === 1 ? 'selected' : ''}>${escapeHtml(v)}</option>`).join('');
      } else {
        actSel.innerHTML = `
          <option value="cap_numeric">${isHi ? 'अधिकतम सीमा तय करें (Cap ≤)' : 'Cap Maximum Limit (≤ Value)'}</option>
          <option value="floor_numeric">${isHi ? 'न्यूनतम सीमा बढ़ाएं (Floor ≥)' : 'Raise Minimum Floor (≥ Value)'}</option>
          <option value="scale_numeric">${isHi ? 'प्रतिशत में घटाएं/बढ़ाएं (% Change)' : 'Change by Percentage (+/- %)'}</option>
        `;
        const numInp = document.getElementById('predictNumInput');
        if (numInp) {
          numInp.value = lv.p75 !== undefined ? lv.p75 : (lv.median !== undefined ? lv.median : '');
        }
      }
      onPredictBuilderActionChange();
    }

    function onPredictBuilderActionChange() {
      const act = document.getElementById('predictActionSelect')?.value || 'replace_category';
      const fromW = document.getElementById('predictFromWrap');
      const toW = document.getElementById('predictToWrap');
      const numW = document.getElementById('predictNumWrap');
      const numLbl = document.getElementById('predictNumLabel');
      const numInp = document.getElementById('predictNumInput');
      const isHi = appState.briefLanguage === 'hi';

      if (act === 'replace_category') {
        if (fromW) fromW.classList.remove('hidden');
        if (toW) toW.classList.remove('hidden');
        if (numW) numW.classList.add('hidden');
      } else if (act === 'pause_segment') {
        if (fromW) fromW.classList.remove('hidden');
        if (toW) toW.classList.add('hidden');
        if (numW) numW.classList.add('hidden');
      } else {
        if (fromW) fromW.classList.add('hidden');
        if (toW) toW.classList.add('hidden');
        if (numW) numW.classList.remove('hidden');
        if (numLbl) {
          if (act === 'scale_numeric') {
            numLbl.textContent = isHi ? '3. कितने % बदलाव? (जैसे -20 या +15)' : '3. Change % (e.g. -20 or +15)';
            if (numInp) numInp.value = '-20';
          } else if (act === 'cap_numeric') {
            numLbl.textContent = isHi ? '3. अधिकतम सीमा (Cap Value)' : '3. Maximum Cap Value';
          } else {
            numLbl.textContent = isHi ? '3. न्यूनतम सीमा (Minimum Floor)' : '3. Minimum Floor Value';
          }
        }
      }
    }

    async function runPredictPreset(presetIdx) {
      const presets = (appState.predictOverview && appState.predictOverview.presets) || [];
      const p = presets[presetIdx];
      if (!p || !p.decision) return;
      document.querySelectorAll('.predict-preset-card').forEach(el => {
        el.classList.toggle('active-preset', Number(el.dataset.presetIdx) === presetIdx);
      });
      await executeDecisionSimulation({ decision: p.decision });
    }

    async function runPredictFromText() {
      const inp = document.getElementById('predictDecisionInput');
      const txt = (inp && inp.value || '').trim();
      if (!txt) {
        showToast(appState.briefLanguage === 'hi' ? 'कृपया कोई फ़ैसला लिखें या ऊपर से 1-क्लिक कार्ड चुनें।' : 'Type a decision or click one of the 1-click cards above.', 'warn');
        return;
      }
      document.querySelectorAll('.predict-preset-card').forEach(el => el.classList.remove('active-preset'));
      await executeDecisionSimulation({ decision_text: txt });
    }

    function buildSpecFromCustomBuilder() {
      const col = document.getElementById('predictColSelect')?.value || '';
      const act = document.getElementById('predictActionSelect')?.value || '';
      if (!col || !act) return null;
      const spec = { action_type: act, column: col };
      if (act === 'replace_category') {
        spec.from_value = document.getElementById('predictFromSelect')?.value;
        spec.to_value = document.getElementById('predictToSelect')?.value;
      } else if (act === 'pause_segment') {
        spec.from_value = document.getElementById('predictFromSelect')?.value;
      } else {
        const val = parseFloat(document.getElementById('predictNumInput')?.value);
        if (!Number.isFinite(val)) {
          showToast('Please enter a valid number.', 'warn');
          return null;
        }
        if (act === 'scale_numeric') spec.delta_pct = val;
        else spec.value = val;
      }
      const scopeRaw = document.getElementById('predictScopeSelect')?.value || '';
      if (scopeRaw && scopeRaw.includes('|||')) {
        const [sc, sv] = scopeRaw.split('|||');
        spec.scope_column = sc;
        spec.scope_value = sv;
      }
      return spec;
    }

    async function runPredictFromBuilder() {
      const spec = buildSpecFromCustomBuilder();
      if (!spec) return;
      document.querySelectorAll('.predict-preset-card').forEach(el => el.classList.remove('active-preset'));
      await executeDecisionSimulation({ decision: spec });
    }

    function _shortLeverChipLabel(sp) {
      const sc = sp.scope_value ? ` (${sp.scope_value})` : '';
      if (sp.action_type === 'replace_category') return `🔄 ${sp.from_value} → ${sp.to_value}${sc}`;
      if (sp.action_type === 'pause_segment') return `⏸️ Pause ${sp.from_value}${sc}`;
      if (sp.action_type === 'cap_numeric') return `🛡️ ${sp.column} ≤ ${sp.value}${sc}`;
      if (sp.action_type === 'floor_numeric') return `📈 ${sp.column} ≥ ${sp.value}${sc}`;
      return `⚙️ ${sp.column} ${sp.delta_pct > 0 ? '+' : ''}${sp.delta_pct}%${sc}`;
    }

    function addCurrentBuilderToCombo() {
      const spec = buildSpecFromCustomBuilder();
      if (!spec) return;
      const q = appState.predictComboQueue || [];
      if (q.length >= 4) {
        showToast(appState.briefLanguage === 'hi' ? 'अधिकतम 4 बदलाव एक साथ कॉम्बो में जोड़ सकते हैं।' : 'Maximum 4 levers per combo simulation.', 'warn');
        return;
      }
      q.push(spec);
      appState.predictComboQueue = q;
      renderComboQueue();
      showToast(appState.briefLanguage === 'hi' ? `कॉम्बो में जोड़ा गया (${q.length}/4)` : `Added to combo (${q.length}/4)`, 'info');
    }

    function removeComboLever(idx) {
      appState.predictComboQueue = (appState.predictComboQueue || []).filter((_, i) => i !== idx);
      renderComboQueue();
    }

    function clearComboQueue() {
      appState.predictComboQueue = [];
      renderComboQueue();
    }

    function renderComboQueue() {
      const box = document.getElementById('predictComboQueueBox');
      const chips = document.getElementById('predictComboChips');
      if (!box || !chips) return;
      const q = appState.predictComboQueue || [];
      if (!q.length) {
        box.classList.add('hidden');
        chips.innerHTML = '';
        return;
      }
      box.classList.remove('hidden');
      chips.innerHTML = q.map((sp, i) => `
        <span class="predict-combo-chip">
          <span>${escapeHtml(_shortLeverChipLabel(sp))}</span>
          <button type="button" style="border:none;background:transparent;cursor:pointer;color:var(--text-muted);font-weight:700;" onclick="removeComboLever(${i})">✕</button>
        </span>
      `).join('<span style="font-weight:800;color:var(--accent-sky);">+</span>');
    }

    async function runPredictCombo() {
      const q = appState.predictComboQueue || [];
      if (!q.length) return;
      document.querySelectorAll('.predict-preset-card').forEach(el => el.classList.remove('active-preset'));
      await executeDecisionSimulation({ decisions: q });
    }

    async function executeDecisionSimulation(payload) {
      const runId = appState.activeRunId;
      if (!runId) return;
      const loader = document.getElementById('predictLoadingBox');
      const stage = document.getElementById('predictResultStage');
      const btn = document.getElementById('btnPredictRun');
      const costRaw = parseFloat(document.getElementById('predictRolloutCostInput')?.value || '0');
      const reqBody = {
        ...payload,
        implementation_cost: Number.isFinite(costRaw) && costRaw > 0 ? costRaw : 0,
        target_lang: appState.briefLanguage || 'en'
      };
      if (loader) loader.classList.remove('hidden');
      if (btn) btn.disabled = true;

      try {
        const res = await apiFetch(`/api/v1/predict/simulate/${encodeURIComponent(runId)}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(reqBody)
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || `Simulation failed (${res.status})`);
        appState.predictLastResult = data;
        if (data.status === 'simulated') {
          recordPredictComparison(data);
        }
        renderDecisionSimulationResult(data);
        if (stage) {
          stage.classList.remove('hidden');
          stage.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
      } catch (e) {
        showToast(`Prediction error: ${e.message}`, 'error');
      } finally {
        if (loader) loader.classList.add('hidden');
        if (btn) btn.disabled = false;
      }
    }

    function renderDecisionSimulationResult(data) {
      if (!data) return;
      const isHi = appState.briefLanguage === 'hi';
      const pred = data.prediction || {};
      const app = data.decision_applied || {};
      const comp = pred.breakdown_components || {};
      const sym = pred.unit_symbol || '$';
      const vCode = String(pred.verdict_code || 'NEUTRAL');

      if (data.status === 'no_effect' || data.status === 'parse_needed') {
        const hero = document.getElementById('predictVerdictHero');
        if (hero) hero.className = 'predict-verdict-hero verdict-NEUTRAL';
        document.getElementById('predictGaugePctText').textContent = '0%';
        document.getElementById('predictGaugeCircle').style.strokeDashoffset = '351.86';
        document.getElementById('predictLossRiskPill').textContent = isHi ? 'कोई सीधा असर नहीं' : 'No Direct Match';
        document.getElementById('predictVerdictBadge').className = 'predict-verdict-badge NEUTRAL';
        document.getElementById('predictVerdictBadge').textContent = data.status === 'no_effect' ? 'NO MATCHING ROWS' : 'CLARIFY DECISION';
        document.getElementById('predictVerdictHeadline').textContent = isHi ? (data.message_hi || data.message_en || 'कोई रिकॉर्ड प्रभावित नहीं हुआ') : (data.message_en || 'No matching rows found.');
        document.getElementById('predictDecisionAppliedLine').textContent = isHi ? 'कृपया ऊपर दिए 1-क्लिक कार्ड चुनें या सटीक नाम लिखें।' : 'Try picking one of the 1-click cards above or use the exact group/column name.';
        document.getElementById('predictKpiNetVal').textContent = '0';
        document.getElementById('predictKpiCiVal').textContent = '--';
        document.getElementById('predictKpiRateVal').textContent = '--';
        document.getElementById('predictKpiEventsVal').textContent = '--';
        document.getElementById('predictKpiCompVal').textContent = '--';
        document.getElementById('predictKpiCompNote').textContent = '--';
        document.getElementById('predictHelpsList').innerHTML = `<div style="font-size:12.5px;color:var(--text-muted);">--</div>`;
        document.getElementById('predictNoHelpList').innerHTML = `<div style="font-size:12.5px;color:var(--text-muted);">--</div>`;
        document.getElementById('predictRisksList').innerHTML = `<li>${escapeHtml(isHi ? (data.message_hi || data.message_en || '') : (data.message_en || ''))}</li>`;
        const confBox = document.getElementById('predictConfidenceMeterBox');
        if (confBox) confBox.classList.add('hidden');
        const actStrip = document.getElementById('predictActionStrip');
        if (actStrip) actStrip.classList.add('hidden');
        return;
      }
      const actStrip = document.getElementById('predictActionStrip');
      if (actStrip) actStrip.classList.remove('hidden');

      const hero = document.getElementById('predictVerdictHero');
      if (hero) hero.className = `predict-verdict-hero verdict-${vCode}`;

      // Circular SVG Probability Ring
      const benefitPct = Math.max(0, Math.min(100, Number(pred.chance_of_benefit_pct || 0)));
      const lossPct = Math.max(0, Math.min(100, Number(pred.chance_of_loss_pct || (100 - benefitPct))));
      const circ = 351.86;
      const offset = circ * (1 - benefitPct / 100);
      const gaugeCircle = document.getElementById('predictGaugeCircle');
      const colorMap = {
        STRONG_GO: 'var(--accent-emerald)',
        PILOT_FIRST: 'var(--accent-amber)',
        NEUTRAL: 'var(--accent-sky)',
        LIKELY_LOSS: 'var(--accent-crimson)'
      };
      if (gaugeCircle) {
        gaugeCircle.style.stroke = colorMap[vCode] || 'var(--accent-sky)';
        gaugeCircle.style.strokeDashoffset = String(offset.toFixed(2));
      }
      document.getElementById('predictGaugePctText').textContent = `${benefitPct.toFixed(0)}%`;
      document.getElementById('predictGaugeSubText').textContent = tUi('lblBenefitChance', 'BENEFIT CHANCE');
      document.getElementById('predictLossRiskPill').textContent = `${tUi('lblLossRisk', 'Loss Risk')}: ${lossPct.toFixed(1)}%`;

      // Verdict Badge & Headline
      const badge = document.getElementById('predictVerdictBadge');
      if (badge) {
        badge.className = `predict-verdict-badge ${vCode}`;
        const badgeLabels = {
          STRONG_GO: isHi ? '🟢 मज़बूत फ़ैसला (STRONG GO)' : '🟢 STRONG GO',
          PILOT_FIRST: isHi ? '🟡 पहले पायलट करें (PILOT FIRST)' : '🟡 PILOT FIRST',
          NEUTRAL: isHi ? '🟠 लगभग बराबर (NEUTRAL)' : '🟠 NEUTRAL',
          LIKELY_LOSS: isHi ? '🔴 नुकसान का ख़तरा (LIKELY LOSS)' : '🔴 LIKELY LOSS'
        };
        badge.textContent = badgeLabels[vCode] || vCode;
      }
      document.getElementById('predictVerdictHeadline').textContent = isHi
        ? (pred.verdict_hi || pred.verdict_en || '')
        : (pred.verdict_en || '');
      document.getElementById('predictDecisionAppliedLine').textContent = isHi
        ? `लागू बदलाव: ${app.label_hi || app.label_en || ''} · प्रभावित रिकॉर्ड्स: ${Number(app.affected_records || 0).toLocaleString('en-US')} (${app.affected_share_pct || 0}%)${app.implementation_cost > 0 ? ` · रोलआउट खर्च: ${app.formatted_implementation_cost}` : ''}`
        : `Simulated Change: ${app.label_en || ''} · Affected: ${Number(app.affected_records || 0).toLocaleString('en-US')} records (${app.affected_share_pct || 0}% of data)${app.implementation_cost > 0 ? ` · Rollout Cost: ${app.formatted_implementation_cost}` : ''}`;

      // 4-Pillar Visual Simulation Confidence Score Meter (0-100)
      const confBox = document.getElementById('predictConfidenceMeterBox');
      const sc = pred.simulation_confidence || null;
      if (confBox && sc) {
        confBox.classList.remove('hidden');
        const cScore = Math.max(0, Math.min(100, Number(sc.score || 0)));
        const cColor = sc.tier === 'HIGH' ? 'var(--accent-emerald)' : (sc.tier === 'MODERATE' ? 'var(--accent-amber)' : 'var(--accent-crimson)');
        const titleEl = document.getElementById('predictConfTitle');
        const pillEl = document.getElementById('predictConfScorePill');
        const fillEl = document.getElementById('predictConfBarFill');
        const pilEl = document.getElementById('predictConfPillars');
        if (titleEl) titleEl.textContent = `🛡️ ${tUi('lblSimConfScore', 'Simulation Confidence Score')}`;
        if (pillEl) {
          pillEl.textContent = `${cScore}/100 · ${isHi ? (sc.label_hi || sc.tier) : (sc.label_en || sc.tier)}`;
          pillEl.style.color = cColor;
        }
        if (fillEl) {
          fillEl.style.width = `${cScore}%`;
          fillEl.style.background = cColor;
        }
        const ps = sc.pillars || {};
        const supPct = pred.causal_support_pct !== undefined && pred.causal_support_pct !== null ? Number(pred.causal_support_pct) : null;
        const beObj = pred.break_even_analysis || {};
        const beSummary = isHi ? (beObj.summary_hi || beObj.summary_en || '') : (beObj.summary_en || '');
        if (pilEl) {
          const tags = [
            `<span class="predict-conf-pillar-tag">${isHi ? 'मॉडल AUC' : 'Model AUC'}: ${ps.model_strength?.score ?? 0}/${ps.model_strength?.max ?? 30}</span>`,
            `<span class="predict-conf-pillar-tag">${isHi ? 'सैंपल' : 'Sample'}: ${ps.sample_size?.score ?? 0}/${ps.sample_size?.max ?? 25}</span>`,
            `<span class="predict-conf-pillar-tag">${isHi ? 'स्थिरता' : 'Stability'}: ${ps.ensemble_stability?.score ?? 0}/${ps.ensemble_stability?.max ?? 25}</span>`,
            `<span class="predict-conf-pillar-tag">${isHi ? 'सिग्नल शुद्धता' : 'Signal Purity'}: ${ps.signal_purity?.score ?? 0}/${ps.signal_purity?.max ?? 20}</span>`,
          ];
          if (supPct !== null) {
            const supColor = supPct < 35 ? 'var(--accent-crimson)' : 'var(--accent-emerald)';
            tags.push(`<span class="predict-conf-pillar-tag" style="color:${supColor};font-weight:700;">${isHi ? 'डेटा सपोर्ट' : 'Historical Support'}: ${supPct.toFixed(0)}%</span>`);
          }
          const drObj = pred.doubly_robust_audit || null;
          if (drObj && drObj.computed) {
            const drOk = !drObj.dr_divergence_warning && drObj.dr_agrees_with_gcomp;
            const drCol = drOk ? 'var(--accent-emerald)' : 'var(--accent-amber)';
            const drTxt = isHi
              ? (drOk ? `✓ डबली-रोबस्ट कॉज़ल पास (${Number(drObj.dr_att_rate_diff_pct || 0).toFixed(1)} pp)` : `⚠ प्रोपेंसिटी अंतर (${Number(drObj.dr_att_rate_diff_pct || 0).toFixed(1)} pp)`)
              : (drOk ? `✓ Doubly-Robust Causal Match (${Number(drObj.dr_att_rate_diff_pct || 0).toFixed(1)} pp)` : `⚠ Propensity Divergence (${Number(drObj.dr_att_rate_diff_pct || 0).toFixed(1)} pp)`);
            tags.push(`<span class="predict-conf-pillar-tag" style="color:${drCol};font-weight:700;">${escapeHtml(drTxt)}</span>`);
          }
          pilEl.innerHTML = tags.join('') + (beSummary ? `<div style="width:100%;margin-top:6px;font-size:12px;color:var(--text-secondary);font-weight:600;">💡 ${escapeHtml(beSummary)}</div>` : '');
        }
      }

      // 3 Crisp KPI Tiles
      const netValEl = document.getElementById('predictKpiNetVal');
      const netNum = Number(pred.expected_net_impact || 0);
      const signPrefix = netNum > 0 ? '+' : '';
      const roiTxt = (pred.roi_multiple !== null && pred.roi_multiple !== undefined)
        ? ` · ROI ${Number(pred.roi_multiple).toFixed(2)}x`
        : '';
      document.getElementById('predictKpiNetLabel').textContent = app.implementation_cost > 0
        ? tUi('lblNetAfterCost', 'Net Impact (After Rollout Cost)')
        : tUi('lblExpectedNet', 'Expected Net Impact');
      if (netValEl) {
        netValEl.textContent = `${signPrefix}${pred.formatted_net_impact || '0'}`;
        netValEl.style.color = netNum > 0 ? 'var(--accent-emerald)' : (netNum < 0 ? 'var(--accent-crimson)' : 'var(--text-primary)');
      }
      document.getElementById('predictKpiCiVal').textContent = `${tUi('lblHonestRange', '95% Honest Range')}: ${pred.formatted_ci_95 || '--'}${roiTxt}`;

      document.getElementById('predictKpiRateLabel').textContent = tUi('lblRiskBeforeAfter', 'Risk Rate (Before → After)');
      const rBefore = Number(pred.before_risk_rate_pct || 0).toFixed(1);
      const rAfter = Number(pred.after_risk_rate_pct || 0).toFixed(1);
      const rRed = Number(pred.risk_reduction_pp || 0);
      const rateValEl = document.getElementById('predictKpiRateVal');
      if (rateValEl) {
        rateValEl.textContent = `${rBefore}% → ${rAfter}%`;
        rateValEl.style.color = rRed > 0.5 ? 'var(--accent-emerald)' : (rRed < -0.5 ? 'var(--accent-crimson)' : 'var(--text-primary)');
      }
      const evAv = Number(pred.expected_events_averted || 0);
      document.getElementById('predictKpiEventsVal').textContent = isHi
        ? (evAv >= 0 ? `लगभग ${Math.round(evAv).toLocaleString('en-US')} खराबी कम होंगी` : `लगभग ${Math.abs(Math.round(evAv)).toLocaleString('en-US')} अतिरिक्त समस्याएँ बढ़ सकती हैं`)
        : (evAv >= 0 ? `~${Math.round(evAv).toLocaleString('en-US')} fewer failures expected` : `~${Math.abs(Math.round(evAv)).toLocaleString('en-US')} more failures expected`);

      // Component split KPI
      document.getElementById('predictKpiCompLabel').textContent = tUi('lblGainTradeoff', 'Gain vs Trade-Off Split');
      const savedLoss = Number(comp.saved_failure_loss || 0);
      const marginRec = Number(comp.direct_margin_recovery || 0);
      const collCost = Number(comp.collateral_tradeoff_cost || 0);
      const fmtUnit = (v) => pred.is_monetary ? formatCurrencyValue(v, sym) : `${Math.round(v).toLocaleString('en-US')} cases`;
      if (collCost > 0) {
        document.getElementById('predictKpiCompVal').textContent = `-${fmtUnit(collCost)}`;
        document.getElementById('predictKpiCompVal').style.color = 'var(--accent-amber)';
        document.getElementById('predictKpiCompNote').textContent = isHi
          ? `अच्छे ऑर्डर छूटने का ट्रेड-ऑफ़ (बचा नुकसान: ${fmtUnit(savedLoss)})`
          : `Sacrificed healthy margin (Saved loss: ${fmtUnit(savedLoss)})`;
      } else if (marginRec !== 0) {
        document.getElementById('predictKpiCompVal').textContent = `${marginRec > 0 ? '+' : ''}${fmtUnit(marginRec)}`;
        document.getElementById('predictKpiCompVal').style.color = 'var(--accent-emerald)';
        document.getElementById('predictKpiCompNote').textContent = isHi ? (comp.margin_note_hi || 'सीधा मार्जिन लाभ') : (comp.margin_note_en || 'Direct margin realization');
      } else {
        document.getElementById('predictKpiCompVal').textContent = `${savedLoss >= 0 ? '+' : ''}${fmtUnit(savedLoss)}`;
        document.getElementById('predictKpiCompVal').style.color = savedLoss >= 0 ? 'var(--accent-emerald)' : 'var(--accent-crimson)';
        document.getElementById('predictKpiCompNote').textContent = isHi ? 'सीधा रिस्क कम होने का असर' : 'Direct risk-reduction impact';
      }

      // Column 1: Where It Helps Most
      const helps = data.where_it_helps || [];
      const helpsEl = document.getElementById('predictHelpsList');
      if (helpsEl) {
        if (!helps.length) {
          helpsEl.innerHTML = `<div style="font-size:12.5px;color:var(--text-muted);">${isHi ? 'इस बदलाव से किसी भी सेगमेंट में बड़ा शुद्ध फ़ायदा नहीं दिख रहा।' : 'No cohort shows a significant net improvement under this change.'}</div>`;
        } else {
          const maxWin = Math.max(...helps.map(h => Math.abs(Number(h.net_impact || 0))), 1);
          helpsEl.innerHTML = helps.map(h => {
            const pctW = Math.max(10, Math.min(100, (Math.abs(Number(h.net_impact || 0)) / maxWin) * 100));
            return `
              <div class="predict-seg-row">
                <div class="predict-seg-top">
                  <strong style="color:var(--text-primary);">${escapeHtml(h.segment)}</strong>
                  <strong style="color:var(--accent-emerald);font-family:var(--font-mono);">+${escapeHtml(h.formatted_impact)}</strong>
                </div>
                <div style="font-size:11.5px;color:var(--text-secondary);">
                  ${Number(h.rate_before_pct).toFixed(1)}% → ${Number(h.rate_after_pct).toFixed(1)}% · ${Number(h.affected_records).toLocaleString('en-US')} ${isHi ? 'रिकॉर्ड्स' : 'rows'}
                </div>
                <div class="predict-seg-bar-track"><div class="predict-seg-bar-fill" style="width:${pctW.toFixed(0)}%;"></div></div>
              </div>
            `;
          }).join('');
        }
      }

      // Column 2: Where It Won't Help Much
      const noHelps = data.where_it_does_not_help || [];
      const noHelpEl = document.getElementById('predictNoHelpList');
      if (noHelpEl) {
        if (!noHelps.length) {
          noHelpEl.innerHTML = `<div style="font-size:12.5px;color:var(--accent-emerald);">${isHi ? 'बढ़िया! सभी प्रमुख स्टोर्स/ग्रुप्स में सकारात्मक असर दिख रहा है।' : 'Broad lift! Every major cohort shows positive improvement.'}</div>`;
        } else {
          noHelpEl.innerHTML = noHelps.map(nh => {
            const isNeg = Number(nh.net_impact || 0) < 0;
            return `
              <div class="predict-seg-row">
                <div class="predict-seg-top">
                  <strong style="color:var(--text-primary);">${escapeHtml(nh.segment)}</strong>
                  <strong style="color:${isNeg ? 'var(--accent-crimson)' : 'var(--accent-amber)'};font-family:var(--font-mono);">${escapeHtml(nh.formatted_impact)}</strong>
                </div>
                <div style="font-size:11.5px;color:var(--text-secondary);">
                  ${Number(nh.rate_before_pct).toFixed(1)}% → ${Number(nh.rate_after_pct).toFixed(1)}% · ${Number(nh.affected_records).toLocaleString('en-US')} ${isHi ? 'रिकॉर्ड्स' : 'rows'}
                </div>
              </div>
            `;
          }).join('');
        }
      }

      // Column 3: Why Loss Could Happen (Honest Downside Risk List)
      const risksObj = data.why_loss_could_happen || {};
      const risksArr = (isHi ? (risksObj.hi || risksObj.en) : risksObj.en) || [];
      const risksEl = document.getElementById('predictRisksList');
      if (risksEl) {
        risksEl.innerHTML = risksArr.map(r => `<li>${escapeHtml(r)}</li>`).join('');
      }
      renderPredictComparisonTable();

      // Seamless live translation for all 41 additional global languages!
      const activeLang = appState.briefLanguage || 'en';
      if (activeLang !== 'en' && activeLang !== 'hi') {
        const pay = {
          verdict: pred.verdict_en || '',
          applied: document.getElementById('predictDecisionAppliedLine').textContent || '',
          ev: document.getElementById('predictKpiEventsVal').textContent || '',
        };
        (risksObj.en || []).slice(0, 6).forEach((rk, i) => { pay[`r${i}`] = rk; });
        apiFetch('/api/v1/i18n/translate-texts', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ target_lang: activeLang, texts: pay })
        }).then(r => r.ok ? r.json() : null).then(tr => {
          if (!tr || !tr.texts || appState.briefLanguage !== activeLang) return;
          if (tr.texts.verdict) document.getElementById('predictVerdictHeadline').textContent = tr.texts.verdict;
          if (tr.texts.applied) document.getElementById('predictDecisionAppliedLine').textContent = tr.texts.applied;
          if (tr.texts.ev) document.getElementById('predictKpiEventsVal').textContent = tr.texts.ev;
          const trRisks = (risksObj.en || []).slice(0, 6).map((rk, i) => tr.texts[`r${i}`] || rk);
          if (risksEl && trRisks.length) {
            risksEl.innerHTML = trRisks.map(r => `<li>${escapeHtml(r)}</li>`).join('');
          }
        }).catch(() => {});
      }
    }

    function recordPredictComparison(data) {
      if (!data || data.status !== 'simulated') return;
      const app = data.decision_applied || {};
      const pred = data.prediction || {};
      const key = `${app.label_en || ''}|${Number(app.implementation_cost || 0)}`;
      const list = (appState.predictCompareList || []).filter(item => item.key !== key);
      list.unshift({
        key,
        label_en: app.label_en || 'Decision',
        label_hi: app.label_hi || app.label_en || 'Decision',
        impl_cost_fmt: app.formatted_implementation_cost || '',
        verdict_code: pred.verdict_code || 'NEUTRAL',
        benefit_pct: Number(pred.chance_of_benefit_pct || 0),
        conf_score: Number((pred.simulation_confidence && pred.simulation_confidence.score) || 0),
        conf_tier: (pred.simulation_confidence && pred.simulation_confidence.tier) || 'MODERATE',
        net_num: Number(pred.expected_net_impact || 0),
        net_fmt: pred.formatted_net_impact || '0',
        ci_fmt: pred.formatted_ci_95 || '--',
      });
      appState.predictCompareList = list.slice(0, 6);
    }

    function renderPredictComparisonTable() {
      const card = document.getElementById('predictCompareCard');
      const tbody = document.getElementById('predictCompareTableBody');
      if (!card || !tbody) return;
      const list = appState.predictCompareList || [];
      if (list.length < 2) {
        card.classList.add('hidden');
        return;
      }
      card.classList.remove('hidden');
      const isHi = appState.briefLanguage === 'hi';
      const bestNet = Math.max(...list.map(x => x.net_num));

      tbody.innerHTML = list.map(item => {
        const isBest = item.net_num === bestNet && item.net_num > 0;
        const netColor = item.net_num > 0 ? 'var(--accent-emerald)' : (item.net_num < 0 ? 'var(--accent-crimson)' : 'var(--text-primary)');
        const confColor = item.conf_tier === 'HIGH' ? 'var(--accent-emerald)' : (item.conf_tier === 'MODERATE' ? 'var(--accent-amber)' : 'var(--accent-crimson)');
        const bestTag = isBest ? `<span style="margin-left:6px;font-size:10.5px;font-weight:800;padding:2px 6px;border-radius:999px;background:var(--accent-emerald-bg);color:var(--accent-emerald);border:1px solid var(--accent-emerald-border);">🏆 ${isHi ? 'बेस्ट' : 'BEST'}</span>` : '';
        const costTag = item.impl_cost_fmt ? `<div style="font-size:11px;color:var(--text-muted);">${isHi ? 'खर्च' : 'Cost'}: ${escapeHtml(item.impl_cost_fmt)}</div>` : '';
        return `
          <tr>
            <td><strong>${escapeHtml(isHi ? item.label_hi : item.label_en)}</strong>${bestTag}${costTag}</td>
            <td><span class="predict-verdict-badge ${escapeHtml(item.verdict_code)}" style="margin-bottom:0;">${escapeHtml(item.verdict_code.replace('_', ' '))}</span></td>
            <td class="tabular-nums" style="font-weight:700;">${item.benefit_pct.toFixed(0)}%</td>
            <td class="tabular-nums" style="font-weight:800;color:${confColor};">${item.conf_score}/100</td>
            <td class="tabular-nums" style="font-weight:800;color:${netColor};">${item.net_num > 0 ? '+' : ''}${escapeHtml(item.net_fmt)}</td>
            <td class="tabular-nums" style="font-size:11.5px;color:var(--text-secondary);">${escapeHtml(item.ci_fmt)}</td>
          </tr>
        `;
      }).join('');
    }

    function clearPredictComparison() {
      appState.predictCompareList = [];
      renderPredictComparisonTable();
    }

    // -------------------------------------------------------------------------
    // STAGE 8.2: PREDICTED VS ACTUAL ACCOUNTABILITY TRACKER & BOARD MEMO EXPORT
    // -------------------------------------------------------------------------
    async function commitCurrentDecision() {
      const last = appState.predictLastResult;
      const runId = appState.activeRunId;
      if (!last || last.status !== 'simulated' || !runId) {
        showToast('Run a decision simulation first before committing.', 'warn');
        return;
      }
      const btn = document.getElementById('btnCommitDecision');
      if (btn) btn.disabled = true;
      try {
        const tenantId = document.getElementById('tenantInput')?.value?.trim() || 'founder_workspace';
        const res = await apiFetch('/api/v1/predict/commitments', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            baseline_run_id: runId,
            simulation: last,
            tenant_id: tenantId,
          }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || `Commit failed (${res.status})`);
        showToast(
          appState.briefLanguage === 'hi'
            ? '📌 फ़ैसला ट्रैक हो गया! अगले महीने के डेटा पर असली रिज़ल्ट मिलाएँ।'
            : '📌 Decision committed! Verify it against next month\'s report anytime.',
          'success'
        );
        await loadPredictCommitments();
      } catch (e) {
        showToast(e.message, 'error');
      } finally {
        if (btn) btn.disabled = false;
      }
    }

    async function loadPredictCommitments() {
      try {
        const tenantId = document.getElementById('tenantInput')?.value?.trim() || 'founder_workspace';
        const res = await apiFetch(`/api/v1/predict/commitments?tenant_id=${encodeURIComponent(tenantId)}`, { silentAuth: true });
        if (!res.ok) return;
        const data = await res.json();
        appState.predictCommitmentsData = data;
        renderPredictCommitments();
      } catch (e) {}
    }

    function _getAvailableRunOptionsForVerify(excludeRunId) {
      const sel = document.getElementById('timeMachineSelect');
      const opts = [];
      if (sel) {
        Array.from(sel.options).forEach(o => {
          if (o.value && o.value !== excludeRunId) {
            opts.push({ id: o.value, label: o.textContent || o.value });
          }
        });
      }
      return opts;
    }

    function renderPredictCommitments() {
      const card = document.getElementById('predictCommitmentsCard');
      const listEl = document.getElementById('predictCommitmentsList');
      const pill = document.getElementById('predictTrackSummaryPill');
      const data = appState.predictCommitmentsData;
      if (!card || !listEl) return;
      const items = (data && data.commitments) || [];
      if (!items.length) {
        card.classList.add('hidden');
        return;
      }
      card.classList.remove('hidden');
      const isHi = appState.briefLanguage === 'hi';
      if (pill) {
        const accTxt = data.average_accuracy_pct !== null && data.average_accuracy_pct !== undefined
          ? ` · ${isHi ? 'औसत सटीकता' : 'Avg Accuracy'}: ${data.average_accuracy_pct}%`
          : '';
        pill.textContent = `${data.total_committed} ${isHi ? 'ट्रैक' : 'Tracked'} · ${data.total_verified} ${isHi ? 'प्रमाणित' : 'Verified'}${accTxt}`;
      }

      listEl.innerHTML = items.map(it => {
        const label = isHi ? (it.decision_label_hi || it.decision_label_en) : it.decision_label_en;
        const isVer = it.status === 'VERIFIED';
        const runOpts = _getAvailableRunOptionsForVerify(it.baseline_run_id);
        const selHtml = runOpts.length
          ? `<select id="verifyRunSel-${escapeHtml(it.commitment_id)}" style="background:var(--bg-surface);border:1px solid var(--border-strong);border-radius:6px;padding:5px 8px;font-size:12px;color:var(--text-primary);max-width:210px;">
              ${runOpts.map(o => `<option value="${escapeHtml(o.id)}">${escapeHtml(o.label)}</option>`).join('')}
            </select>`
          : `<input id="verifyRunSel-${escapeHtml(it.commitment_id)}" type="text" placeholder="Next report run_id..." style="background:var(--bg-surface);border:1px solid var(--border-strong);border-radius:6px;padding:5px 8px;font-size:12px;color:var(--text-primary);width:170px;" />`;

        const statusBadge = isVer
          ? `<span class="predict-verdict-badge ${it.calibration_hit_ci95 ? 'STRONG_GO' : 'PILOT_FIRST'}" style="margin-bottom:0;">${it.calibration_hit_ci95 ? '✅ VERIFIED · IN 95% CI' : '📊 VERIFIED'} (${it.accuracy_score_pct ?? 0}% Match)</span>`
          : `<span class="predict-verdict-badge NEUTRAL" style="margin-bottom:0;">📌 COMMITTED · AWAITING NEXT DATA</span>`;

        const verBody = isVer
          ? `<div style="margin-top:6px;font-size:12.5px;color:var(--text-primary);">
               <strong>${isHi ? 'असली असर' : 'Actual Realized'}:</strong> <span style="font-family:var(--font-mono);font-weight:800;color:${Number(it.actual_net_impact) >= 0 ? 'var(--accent-emerald)' : 'var(--accent-crimson)'};">${Number(it.actual_net_impact) > 0 ? '+' : ''}${escapeHtml(it.formatted_actual_net || '0')}</span>
               · ${isHi ? 'अमल' : 'Executed'}: <strong>${it.execution_compliance_pct ?? 0}%</strong>
               <div style="font-size:11.8px;color:var(--text-secondary);margin-top:3px;">${escapeHtml(isHi ? (it.verification_note_hi || it.verification_note_en || '') : (it.verification_note_en || ''))}</div>
             </div>`
          : '';

        return `
          <div class="predict-commit-item">
            <div style="flex:1;min-width:240px;">
              <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:4px;">
                ${statusBadge}
                <span style="font-size:11.5px;color:var(--text-muted);font-family:var(--font-mono);">Base: ${escapeHtml(it.baseline_run_id)}</span>
              </div>
              <div style="font-size:13.8px;font-weight:700;color:var(--text-primary);">${escapeHtml(label)}</div>
              <div style="font-size:12px;color:var(--text-secondary);margin-top:2px;">
                ${isHi ? 'अनुमानित' : 'Predicted'}: <strong style="font-family:var(--font-mono);">${Number(it.predicted_net_impact) > 0 ? '+' : ''}${escapeHtml(it.formatted_predicted_net)}</strong>
                ${escapeHtml(it.formatted_predicted_ci)} · Trust: <strong>${it.confidence_score}/100</strong>
              </div>
              ${verBody}
            </div>
            <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
              ${selHtml}
              <button type="button" class="btn btn-primary btn-sm" onclick="verifyPredictCommitment('${escapeHtml(it.commitment_id)}')">
                ✓ ${isHi ? 'असली जाँचें' : 'Verify'}
              </button>
              <button type="button" class="btn btn-secondary btn-sm" title="Remove" onclick="deletePredictCommitment('${escapeHtml(it.commitment_id)}')">🗑️</button>
            </div>
          </div>
        `;
      }).join('');
    }

    async function verifyPredictCommitment(commitmentId) {
      const inp = document.getElementById(`verifyRunSel-${commitmentId}`);
      const actualRunId = (inp && inp.value || '').trim();
      if (!actualRunId) {
        showToast('Select or enter the next period report ID to verify against.', 'warn');
        return;
      }
      try {
        const tenantId = document.getElementById('tenantInput')?.value?.trim() || 'founder_workspace';
        const res = await apiFetch(`/api/v1/predict/commitments/${encodeURIComponent(commitmentId)}/verify`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ actual_run_id: actualRunId, tenant_id: tenantId }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || `Verification failed (${res.status})`);
        showToast(`Verified against ${actualRunId}: ${data.accuracy_score_pct ?? 0}% match!`, 'success');
        await loadPredictCommitments();
      } catch (e) {
        showToast(e.message, 'error');
      }
    }

    async function deletePredictCommitment(commitmentId) {
      try {
        const tenantId = document.getElementById('tenantInput')?.value?.trim() || 'founder_workspace';
        const res = await apiFetch(`/api/v1/predict/commitments/${encodeURIComponent(commitmentId)}?tenant_id=${encodeURIComponent(tenantId)}`, {
          method: 'DELETE',
        });
        if (!res.ok) {
          const d = await res.json().catch(() => ({}));
          throw new Error(d.detail || 'Delete failed');
        }
        showToast('Removed tracked decision.', 'info');
        await loadPredictCommitments();
      } catch (e) {
        showToast(e.message, 'error');
      }
    }

    async function shareDecisionWhatsAppMemo() {
      const data = appState.predictLastResult;
      if (!data || data.status !== 'simulated') return;
      const isHi = appState.briefLanguage === 'hi';
      const app = data.decision_applied || {};
      const pred = data.prediction || {};
      const sc = pred.simulation_confidence || {};
      const topWin = (data.where_it_helps || [])[0];
      const topRisk = ((isHi ? data.why_loss_could_happen?.hi : data.why_loss_could_happen?.en) || [])[0] || '';
      const netSign = Number(pred.expected_net_impact || 0) > 0 ? '+' : '';
      const costLine = app.implementation_cost > 0
        ? `\n💰 ${isHi ? 'रोलआउट खर्च' : 'Rollout Cost'}: ${app.formatted_implementation_cost} (ROI: ${pred.roi_multiple ?? '--'}x)`
        : '';
      const lines = isHi
        ? [
            `🔮 *DataX-Ray AI Decision Memo* (${appState.activeRunId || ''})`,
            `📌 *फ़ैसला*: ${app.label_hi || app.label_en}`,
            `✅ *वर्डिक्ट*: ${pred.verdict_hi || pred.verdict_code}`,
            `📊 *फ़ायदे का चांस*: ${pred.chance_of_benefit_pct}% (रिस्क: ${pred.chance_of_loss_pct}%) | *Trust*: ${sc.score ?? '--'}/100`,
            `💵 *शुद्ध असर*: ${netSign}${pred.formatted_net_impact} (95% रेंज: ${pred.formatted_ci_95})${costLine}`,
            `📉 *रिस्क बदलाव*: ${pred.before_risk_rate_pct}% → ${pred.after_risk_rate_pct}% (${app.affected_records} रिकॉर्ड्स)`,
            topWin ? `🏆 *सबसे बड़ा फ़ायदा*: ${topWin.segment} (+${topWin.formatted_impact})` : '',
            topRisk ? `⚠️ *मुख्य चेतावनी*: ${topRisk}` : '',
          ].filter(Boolean).join('\n')
        : [
            `🔮 *DataX-Ray AI Decision Memo* (${appState.activeRunId || ''})`,
            `📌 *Decision*: ${app.label_en}`,
            `✅ *Verdict*: ${pred.verdict_en || pred.verdict_code}`,
            `📊 *Benefit Chance*: ${pred.chance_of_benefit_pct}% (Loss Risk: ${pred.chance_of_loss_pct}%) | *Trust Score*: ${sc.score ?? '--'}/100`,
            `💵 *Expected Net Impact*: ${netSign}${pred.formatted_net_impact} (95% CI: ${pred.formatted_ci_95})${costLine}`,
            `📉 *Risk Rate*: ${pred.before_risk_rate_pct}% → ${pred.after_risk_rate_pct}% (${app.affected_records} records)`,
            topWin ? `🏆 *Top Winner*: ${topWin.segment} (+${topWin.formatted_impact})` : '',
            topRisk ? `⚠️ *Key Risk*: ${topRisk}` : '',
          ].filter(Boolean).join('\n');

      await copyTextSafe(lines, isHi ? 'WhatsApp मेमो कॉपी हो गया!' : 'WhatsApp decision memo copied!');
      window.open(`https://wa.me/?text=${encodeURIComponent(lines)}`, '_blank', 'noopener,noreferrer');
    }

    function printExecutiveBoardMemo() {
      const data = appState.predictLastResult;
      if (!data || data.status !== 'simulated') return;
      const isHi = appState.briefLanguage === 'hi';
      const app = data.decision_applied || {};
      const pred = data.prediction || {};
      const sc = pred.simulation_confidence || {};
      const sa = data.statistical_audit || {};
      const mh = data.model_honesty || {};
      const risks = (isHi ? data.why_loss_could_happen?.hi : data.why_loss_could_happen?.en) || [];
      const wins = data.where_it_helps || [];
      const noHelps = data.where_it_does_not_help || [];
      const netSign = Number(pred.expected_net_impact || 0) > 0 ? '+' : '';

      const htmlDoc = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>DataX-Ray Board Decision Memo</title>
        <style>
          body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#111827;margin:32px;line-height:1.5;max-width:860px;}
          .hdr{border-bottom:2px solid #047857;padding-bottom:12px;margin-bottom:20px;display:flex;justify-content:space-between;align-items:flex-end;}
          .badge{display:inline-block;padding:4px 10px;border-radius:999px;font-weight:800;font-size:12px;background:#ecfdf5;color:#047857;border:1px solid #a7f3d0;}
          .grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:16px 0;}
          .box{border:1px solid #e5e7eb;border-radius:10px;padding:12px;background:#f9fafb;}
          .box span{display:block;font-size:11px;color:#6b7280;font-weight:700;text-transform:uppercase;}
          .box strong{display:block;font-size:19px;margin-top:4px;font-family:ui-monospace,monospace;}
          h3{font-size:15px;margin:18px 0 8px;border-bottom:1px solid #e5e7eb;padding-bottom:4px;}
          ul{margin:0;padding-left:18px;font-size:13px;} li{margin-bottom:6px;}
          .foot{margin-top:24px;padding-top:10px;border-top:1px dashed #d1d5db;font-size:11.5px;color:#6b7280;}
          @media print{body{margin:16px;}}
        </style></head><body>
        <div class="hdr">
          <div>
            <div style="font-size:11px;font-weight:800;color:#047857;letter-spacing:.06em;">DATAX-RAY · EXECUTIVE BOARD DECISION MEMO</div>
            <h1 style="font-size:21px;margin:4px 0 0;">${escapeHtml(isHi ? (app.label_hi || app.label_en) : app.label_en)}</h1>
          </div>
          <div style="text-align:right;font-size:12px;color:#4b5563;">
            <div><strong>Dataset:</strong> ${escapeHtml(appState.activeRunId || '')}</div>
            <div><strong>Date:</strong> ${escapeHtml(new Date().toISOString().slice(0, 10))}</div>
          </div>
        </div>
        <div class="badge">${escapeHtml(pred.verdict_code || '')} · ${escapeHtml(isHi ? (pred.verdict_hi || pred.verdict_en) : pred.verdict_en)}</div>
        <div class="grid">
          <div class="box"><span>${isHi ? 'फ़ायदे का चांस / भरोसा' : 'Benefit Chance & Trust'}</span><strong>${Number(pred.chance_of_benefit_pct || 0).toFixed(1)}%</strong><small>Trust Score: ${sc.score ?? '--'}/100 (${escapeHtml(sc.tier || '')})</small></div>
          <div class="box"><span>${isHi ? 'अनुमानित शुद्ध असर' : 'Expected Net Impact'}</span><strong>${netSign}${escapeHtml(pred.formatted_net_impact || '0')}</strong><small>95% CI: ${escapeHtml(pred.formatted_ci_95 || '--')}${pred.roi_multiple ? ` · ROI ${pred.roi_multiple}x` : ''}</small></div>
          <div class="box"><span>${isHi ? 'रिस्क रेट बदलाव' : 'Risk Rate Shift'}</span><strong>${Number(pred.before_risk_rate_pct || 0).toFixed(1)}% → ${Number(pred.after_risk_rate_pct || 0).toFixed(1)}%</strong><small>${Number(app.affected_records || 0).toLocaleString('en-US')} affected rows${app.overlap_rows_deduplicated ? ` (${app.overlap_rows_deduplicated} overlaps deduplicated)` : ''}</small></div>
        </div>
        <h3>${isHi ? '✅ सबसे ज़्यादा फ़ायदा कहाँ होगा (Top Winners)' : '✅ Where You Win Most (Top Cohorts)'}</h3>
        <ul>${wins.length ? wins.map(w => `<li><strong>${escapeHtml(w.segment)}</strong>: +${escapeHtml(w.formatted_impact)} (${w.rate_before_pct}% → ${w.rate_after_pct}%, ${w.affected_records} rows)</li>`).join('') : '<li>No single cohort dominates gain.</li>'}</ul>
        <h3>${isHi ? '⚠️ कम / ज़ीरो असर वाले क्षेत्र' : '⚠️ Low / Zero-Benefit Zones'}</h3>
        <ul>${noHelps.length ? noHelps.map(w => `<li><strong>${escapeHtml(w.segment)}</strong>: ${escapeHtml(w.formatted_impact)} (${w.rate_before_pct}% → ${w.rate_after_pct}%)</li>`).join('') : '<li>Broad positive lift across major cohorts.</li>'}</ul>
        <h3>${isHi ? '🔍 ईमानदार रिस्क और सावधानियाँ (Why Loss Could Happen)' : '🔍 Honest Downside Risks & Caveats'}</h3>
        <ul>${risks.map(r => `<li>${escapeHtml(r)}</li>`).join('')}</ul>
        <div class="foot">
          <strong>Statistical Audit Seal:</strong> 3-Fold Cross-Fitted HistGradientBoosting (Out-of-Fold ROC-AUC = ${mh.roc_auc ?? '--'}, Brier = ${mh.brier_score ?? '--'}) · 500-Iteration Bootstrap + Epistemic + Elasticity Monte Carlo · Empirical p = ${sa.empirical_p_value ?? '--'} · Blocked Leakage Columns: ${escapeHtml((mh.blocked_leakage_columns || []).join(', ') || 'None')}.
        </div>
        </body></html>`;

      const win = window.open('', '_blank', 'width=920,height=740');
      if (!win) {
        showToast('Pop-up blocked — allow pop-ups to print Board PDF.', 'warn');
        return;
      }
      win.document.open();
      win.document.write(htmlDoc);
      win.document.close();
      setTimeout(() => { try { win.focus(); win.print(); } catch (e) {} }, 250);
    }

    function setAppStudioTheme(themeId) {
      const valid = ['dark', 'stripe_alabaster', 'nordic_frost', 'royal_gold', 'sunset_coral', 'light'];
      const t = valid.includes(themeId) ? themeId : 'dark';
      appState.theme = t;
      document.documentElement.setAttribute('data-theme', t);
      document.querySelectorAll('.app-swatch-dot').forEach(el => {
        el.classList.toggle('active', el.getAttribute('data-app-theme') === t);
      });
      const btn = document.getElementById('btnThemeToggle');
      if (btn) {
        btn.innerHTML = (t === 'light')
          ? '<svg class="svg-ico" viewBox="0 0 24 24"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>'
          : '<svg class="svg-ico" viewBox="0 0 24 24"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>';
      }
      try { localStorage.setItem('dataxray_theme', t); } catch (e) {}
    }

    // =========================================================================
    // STAGE 9: AI BOARDROOM DECISION JUDGE (MULTI-TURN CA + DATA SCIENTIST)
    // =========================================================================
    async function loadBoardroomStarters(forceReload = false) {
      const runId = appState.activeRunId;
      const grid = document.getElementById('boardroomStartersGrid');
      const pill = document.getElementById('boardroomStatusPill');
      if (!runId || !grid) return;
      const lang = appState.briefLanguage || 'en';
      const cacheKey = `${runId}::${lang}`;
      if (!forceReload && appState.boardroomStartersRunId === cacheKey && appState.boardroomStarters.length) {
        renderBoardroomStarters();
        return;
      }
      grid.innerHTML = `<div style="grid-column:1/-1;font-size:12.5px;color:var(--text-muted);padding:10px;">⏳ Preparing live boardroom debate starters from your audited data...</div>`;
      try {
        const res = await apiFetch(`/api/v1/boardroom/starters/${encodeURIComponent(runId)}?lang=${encodeURIComponent(lang)}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        appState.boardroomStartersRunId = cacheKey;
        appState.boardroomStarters = data.starters || [];
        if (pill) {
          const auc = Number(data.model_roc_auc || 0).toFixed(2);
          const rows = Number(data.rows_audited || 0).toLocaleString('en-US');
          const bb = data.blind_backtest_badge || null;
          if (bb && bb.label_en) {
            pill.className = bb.verified ? 'predict-honesty-pill' : 'predict-honesty-pill warn';
            pill.textContent = lang === 'hi'
              ? `🛡️ ${bb.label_hi || bb.label_en} (${rows} रिकॉर्ड)`
              : `🛡️ ${bb.label_en} (${rows} rows)`;
          } else {
            pill.textContent = lang === 'hi'
              ? `🛡️ लाइव डेटा जज तैयार (${rows} रिकॉर्ड · AI AUC ${auc})`
              : `🛡️ Live Data Judge Ready (${rows} rows · AI AUC ${auc})`;
          }
        }
        renderBoardroomStarters();
      } catch (e) {
        grid.innerHTML = '';
      }
    }

    function renderBoardroomStarters() {
      const grid = document.getElementById('boardroomStartersGrid');
      if (!grid) return;
      const isHi = appState.briefLanguage === 'hi';
      const items = appState.boardroomStarters || [];
      if (!items.length) {
        grid.innerHTML = '';
        return;
      }
      grid.innerHTML = items.map((st, i) => {
        const tag = isHi ? (st.tag_hi || st.tag_en) : st.tag_en;
        const pr = isHi ? (st.prompt_hi || st.prompt_en) : st.prompt_en;
        return `
          <button type="button" class="boardroom-starter-btn" onclick="runBoardroomStarter(${i})">
            <span class="boardroom-starter-tag">${escapeHtml(st.icon || '⚖️')} ${escapeHtml(tag)}</span>
            <span style="font-size:12.6px;line-height:1.45;color:var(--text-primary);">${escapeHtml(pr)}</span>
          </button>
        `;
      }).join('');
    }

    function runBoardroomStarter(idx) {
      const st = (appState.boardroomStarters || [])[idx];
      if (!st) return;
      const isHi = appState.briefLanguage === 'hi';
      const txt = isHi ? (st.prompt_hi || st.prompt_en) : st.prompt_en;
      const inp = document.getElementById('boardroomInput');
      if (inp) inp.value = txt;
      sendBoardroomDiscussion(txt);
    }

    function clearBoardroomThread() {
      appState.boardroomHistory = [];
      const feed = document.getElementById('boardroomFeed');
      if (feed) feed.innerHTML = '';
      showToast(appState.briefLanguage === 'hi' ? 'बोर्डरूम चर्चा साफ़ कर दी गई।' : 'Boardroom thread cleared.', 'info');
    }

    async function sendBoardroomDiscussion(overrideText) {
      const runId = appState.activeRunId;
      if (!runId) {
        showToast('Please load a report first.', 'warn');
        return;
      }
      const inp = document.getElementById('boardroomInput');
      const msg = String(overrideText !== undefined ? overrideText : (inp ? inp.value : '')).trim();
      if (!msg) {
        showToast(appState.briefLanguage === 'hi' ? 'कृपया अपने मन की बात या टीम का सवाल लिखें।' : 'Please type your business thought or team debate.', 'warn');
        return;
      }
      if (inp) inp.value = '';
      const btn = document.getElementById('btnBoardroomSubmit');
      if (btn) btn.disabled = true;

      const priorHistory = (appState.boardroomHistory || []).map(item => ({
        role: item.role,
        text: item.text || ''
      }));
      appState.boardroomHistory.push({ role: 'user', text: msg });
      appState.boardroomHistory.push({ role: 'loading', text: '' });
      renderBoardroomFeed();

      try {
        const lang = appState.briefLanguage || 'en';
        const res = await apiFetch(`/api/v1/boardroom/discuss/${encodeURIComponent(runId)}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: msg, history: priorHistory, target_lang: lang })
        });
        if (!res.ok) {
          const errJ = await res.json().catch(() => ({}));
          throw new Error(errJ.detail || `HTTP ${res.status}`);
        }
        const data = await res.json();
        appState.boardroomHistory = appState.boardroomHistory.filter(x => x.role !== 'loading');
        appState.boardroomHistory.push({ role: 'judge', text: data.verdict?.headline_en || '', payload: data });
        renderBoardroomFeed();
      } catch (e) {
        appState.boardroomHistory = appState.boardroomHistory.filter(x => x.role !== 'loading');
        renderBoardroomFeed();
        showToast(`Boardroom error: ${e.message}`, 'error');
      } finally {
        if (btn) btn.disabled = false;
      }
    }

    function copyBoardroomMemo(turnIdx) {
      const item = (appState.boardroomHistory || [])[turnIdx];
      if (!item || !item.payload) return;
      const d = item.payload;
      const isHi = appState.briefLanguage === 'hi';
      const v = d.verdict || {};
      const ev = d.evidence || {};
      const lines = [
        `🏛️ *DataX-Ray AI Boardroom Verdict* (${appState.activeRunId || ''})`,
        `*${isHi ? (v.badge_hi || v.badge_en) : v.badge_en}*`,
        isHi ? (v.headline_hi || v.headline_en) : v.headline_en,
        '',
        `✅ *${isHi ? 'डेटा से क्या सही साबित हुआ' : 'Proven True by Data'}:*`,
        ...((isHi ? ev.proven_true_hi : ev.proven_true_en) || []).map(x => `• ${x}`),
        '',
        `❌ *${isHi ? 'क्या गलत / ख़तरनाक है' : 'Wrong or Risky'}:*`,
        ...((isHi ? ev.wrong_or_risky_hi : ev.wrong_or_risky_en) || []).map(x => `• ${x}`),
        '',
        `⚠️ *${isHi ? 'डेटा की सीमा (Blind Spots)' : 'What Data Cannot See'}:*`,
        ...((isHi ? ev.blind_spots_hi : ev.blind_spots_en) || []).map(x => `• ${x}`),
        '',
        `🎯 *${isHi ? '14-दिन का सुरक्षित प्लान' : '14-Day Safe Plan'}:*`,
        ...((isHi ? d.action_plan_hi : d.action_plan_en) || []).map((x, i) => `${i + 1}. ${x}`),
      ];
      navigator.clipboard.writeText(lines.join('\n')).then(() => {
        showToast(isHi ? '📲 WhatsApp बोर्डरूम मेमो कॉपी हो गया!' : '📲 WhatsApp Boardroom Memo copied!', 'success');
      }).catch(() => {});
    }

    function renderBoardroomFeed() {
      const feed = document.getElementById('boardroomFeed');
      if (!feed) return;
      const isHi = appState.briefLanguage === 'hi';
      const items = appState.boardroomHistory || [];
      if (!items.length) {
        feed.innerHTML = '';
        return;
      }
      feed.innerHTML = items.map((item, idx) => {
        if (item.role === 'user') {
          return `<div class="boardroom-user-bubble">👤 ${escapeHtml(item.text)}</div>`;
        }
        if (item.role === 'loading') {
          return `<div class="boardroom-judge-card" style="opacity:0.85;font-size:13px;color:var(--text-secondary);">⏳ ${isHi ? 'असली DuckDB डेटा और डेटा-आधारित सिमुलेशन पर आपकी बात जाँची जा रही है...' : 'Running live DuckDB forensic audit + data-backed simulation on your question...'}</div>`;
        }
        const d = item.payload || {};
        const v = d.verdict || {};
        const ev = d.evidence || {};
        const badge = isHi ? (v.badge_hi || v.badge_en) : v.badge_en;
        const hl = isHi ? (v.headline_hi || v.headline_en) : v.headline_en;
        const pt = (isHi ? (ev.proven_true_hi || ev.proven_true_en) : ev.proven_true_en) || [];
        const wr = (isHi ? (ev.wrong_or_risky_hi || ev.wrong_or_risky_en) : ev.wrong_or_risky_en) || [];
        const bs = (isHi ? (ev.blind_spots_hi || ev.blind_spots_en) : ev.blind_spots_en) || [];
        const plan = (isHi ? (d.action_plan_hi || d.action_plan_en) : d.action_plan_en) || [];
        const fus = (isHi ? (d.follow_up_prompts_hi || d.follow_up_prompts_en) : d.follow_up_prompts_en) || [];
        const rows = d.comparison_scorecard || [];

        const scoreHtml = rows.length >= 2 ? `
          <div class="table-scroll">
            <table class="data-table" style="font-size:12.5px;">
              <thead>
                <tr>
                  <th>${escapeHtml(tUi('lblOptionDriver', 'Option / Driver'))}</th>
                  <th>${escapeHtml(tUi('lblAiImpact', 'AI Impact %'))}</th>
                  <th>${escapeHtml(tUi('lblDataProof', 'Data Proof'))}</th>
                  <th>${escapeHtml(tUi('lblBenefitChance', 'Benefit Chance'))}</th>
                  <th>${escapeHtml(tUi('lblProjectedImpact', 'Projected Impact'))}</th>
                </tr>
              </thead>
              <tbody>
                ${rows.map(r => `
                  <tr>
                    <td><strong>${escapeHtml(isHi ? (r.option_hi || r.option_en) : r.option_en)}</strong></td>
                    <td class="tabular-nums">${Number(r.ml_driver_share_pct || 0).toFixed(1)}%</td>
                    <td>${r.statistically_proven ? `✅ ${escapeHtml(tUi('lblProvenTag', 'Proven'))}` : `⚪ ${escapeHtml(tUi('lblNoiseTag', 'Noise / Flat'))}`}</td>
                    <td class="tabular-nums">${r.benefit_chance_pct !== null && r.benefit_chance_pct !== undefined ? `${Number(r.benefit_chance_pct).toFixed(0)}%` : '—'}</td>
                    <td>${escapeHtml(r.expected_impact || '—')}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        ` : '';

        return `
          <article class="boardroom-judge-card">
            <div class="boardroom-verdict-banner ${escapeHtml(v.code || '')}">
              <div style="font-size:11.5px;font-weight:800;letter-spacing:0.05em;text-transform:uppercase;margin-bottom:4px;">${escapeHtml(badge || 'BOARDROOM VERDICT')}</div>
              <div style="font-size:16px;font-weight:800;color:var(--text-primary);line-height:1.4;">${escapeHtml(hl || '')}</div>
            </div>

            ${scoreHtml}

            <div class="boardroom-evidence-grid">
              <div class="boardroom-ev-box true-box">
                <strong style="color:var(--accent-emerald);">✅ ${escapeHtml(tUi('boardroomProvenTitle', isHi ? 'डेटा से क्या सही साबित हुआ' : 'Proven True by Your Data'))}</strong>
                <ul>${pt.map(x => `<li>${escapeHtml(x)}</li>`).join('')}</ul>
              </div>
              <div class="boardroom-ev-box risk-box">
                <strong style="color:var(--accent-crimson);">❌ ${escapeHtml(tUi('boardroomWrongTitle', isHi ? 'क्या गलत / ख़तरनाक / भ्रम है' : 'Wrong, Risky, or Unsupported'))}</strong>
                <ul>${wr.map(x => `<li>${escapeHtml(x)}</li>`).join('')}</ul>
              </div>
              <div class="boardroom-ev-box blind-box">
                <strong style="color:var(--accent-amber);">⚠️ ${escapeHtml(tUi('boardroomBlindTitle', isHi ? 'डेटा क्या नहीं देख सकता (ईमानदार सीमा)' : 'What Your Data Cannot See'))}</strong>
                <ul>${bs.map(x => `<li>${escapeHtml(x)}</li>`).join('')}</ul>
              </div>
            </div>

            <div class="boardroom-plan-box">
              <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:6px;">
                <strong style="color:var(--text-primary);">🎯 ${escapeHtml(tUi('boardroomPlanTitle', isHi ? 'अगले 14 दिन का सुरक्षित एक्शन प्लान' : 'Recommended 14-Day Safe Action Plan'))}</strong>
                <button type="button" class="btn btn-secondary btn-sm" onclick="copyBoardroomMemo(${idx})">📲 ${escapeHtml(tUi('boardroomCopyMemo', isHi ? 'WhatsApp मेमो कॉपी करें' : 'Copy WhatsApp Memo'))}</button>
              </div>
              <ol style="margin:4px 0 0 18px;padding:0;display:flex;flex-direction:column;gap:4px;color:var(--text-secondary);">
                ${plan.map(x => `<li>${escapeHtml(x)}</li>`).join('')}
              </ol>
            </div>

            ${fus.length ? `
              <div class="boardroom-followup-chips">
                ${fus.map(f => `<button type="button" class="boardroom-chip" onclick="sendBoardroomDiscussion(${JSON.stringify(f).replace(/"/g, '&quot;')})">💬 ${escapeHtml(f)}</button>`).join('')}
              </div>
            ` : ''}
          </article>
        `;
      }).join('');
    }

    // Initialize V9 Midnight Aurora Executive Bento Suite (auto-migrating prior theme cache once)
    window.addEventListener('DOMContentLoaded', () => {
      try {
        const uiVer = localStorage.getItem('dataxray_ui_v9');
        const savedTheme = localStorage.getItem('dataxray_theme');
        if (uiVer === '1' && savedTheme) {
          setAppStudioTheme(savedTheme);
        } else {
          localStorage.setItem('dataxray_ui_v9', '1');
          setAppStudioTheme('dark');
        }
        const savedLang = localStorage.getItem('dataxray_lang');
        if (savedLang && savedLang.trim()) {
          appState.briefLanguage = savedLang.trim();
        }
        const savedRegion = localStorage.getItem('dataxray_region');
        if (savedRegion) {
          const rSel = document.getElementById('regionSelect');
          if (rSel) rSel.value = savedRegion;
          applyRegionAdaptation(savedRegion);
        }
      } catch (e) {}

      // Keep expandable drawer labels strictly synchronized with open/closed state
      const deepDrawer = document.getElementById('deepAuditDrawer');
      const deepLbl = document.getElementById('deepAuditToggleLabel');
      if (deepDrawer && deepLbl) {
        deepDrawer.addEventListener('toggle', () => {
          const isHi = appState.briefLanguage === 'hi';
          deepLbl.textContent = deepDrawer.open
            ? (isHi ? 'बंद करने के लिए क्लिक करें ▴' : 'Click to Collapse ▴')
            : (isHi ? 'खोलने के लिए क्लिक करें ▾' : 'Click to Expand ▾');
        });
      }
      const predBuilder = document.getElementById('predictCustomBuilder');
      const predLbl = document.getElementById('predictCustomToggleLabel');
      if (predBuilder && predLbl) {
        predBuilder.addEventListener('toggle', () => {
          const isHi = appState.briefLanguage === 'hi';
          predLbl.textContent = predBuilder.open
            ? (isHi ? 'बंद करें ▴' : 'Collapse ▴')
            : (isHi ? 'खोलें ▾' : 'Expand ▾');
        });
      }

      updateAuthUIState();
      initGlobalLanguages();
      if (typeof initBusinessCategories === 'function') initBusinessCategories();
      loadCertifiedBenchmark('nexura_lifestyle_brand', true);
      refreshTimeMachineRuns();
    });
