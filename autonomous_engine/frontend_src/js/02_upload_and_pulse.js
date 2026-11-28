    function handleFileSelection(event) {
      const files = event.target.files;
      if (!files || files.length === 0) return;
      if (files.length > 1) {
        triggerMultiIntentHandshake(Array.from(files));
      } else {
        triggerIntentHandshake(files[0]);
      }
    }

    async function triggerIntentHandshake(file) {
      appState.selectedFile = file;
      const region = document.getElementById('regionSelect').value || 'US';
      const preCat = (document.getElementById('uploadCategorySelect') && document.getElementById('uploadCategorySelect').value) || 'auto';
      const fd = new FormData();
      fd.append('file', file);
      fd.append('region_profile', region);
      if (preCat && preCat !== 'auto') fd.append('business_category', preCat);

      showToast(`Scanning ${file.name}...`, 'info');
      try {
        const res = await apiFetch('/api/v1/preview-intent', { method: 'POST', body: fd });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `Scan failed (${res.status})`);
        }
        const data = await res.json();
        const card = document.getElementById('intentHandshakeCard');
        card.classList.remove('hidden');

        // Hydrate V6.0 Auto-Detected Business Category + Sub-Category + Soft Mismatch Warning
        appState.detectedCategoryMeta = data.detected_category || null;
        const detCat = (data.detected_category && data.detected_category.detected_category) || 'auto';
        const detSub = (data.detected_category && data.detected_category.detected_sub_category) || null;
        const chosenInitCat = (preCat && preCat !== 'auto') ? preCat : detCat;
        if (typeof populateCategoryDropdowns === 'function') {
          populateCategoryDropdowns(chosenInitCat, detSub);
        }
        const catBadge = document.getElementById('intentCategoryBadge');
        if (catBadge && data.detected_category) {
          const cPct = Number(data.detected_category.confidence_pct || 0);
          catBadge.textContent = data.detected_category.is_confident
            ? (appState.briefLanguage === 'hi' ? `ऑटो ${cPct}% मिलान` : `Auto ${cPct}% Match`)
            : (appState.briefLanguage === 'hi' ? 'सामान्य (बदलें)' : 'General (Optional)');
        }
        const catWarn = document.getElementById('intentCategoryWarningBanner');
        if (catWarn) {
          const mw = appState.briefLanguage === 'hi'
            ? (data.detected_category && data.detected_category.mismatch_warning_hi)
            : (data.detected_category && data.detected_category.mismatch_warning_en);
          if (mw) {
            catWarn.textContent = `⚠️ ${mw}`;
            catWarn.classList.remove('hidden');
          } else {
            catWarn.classList.add('hidden');
            catWarn.textContent = '';
          }
        }

        document.getElementById('intentFileTitle').textContent =
          `${data.filename} — ${data.columns_count} Columns Ready`;
        document.getElementById('intentQuestionSubtitle').textContent =
          data.detected_goal.business_question_en;

        const sanityBanner = document.getElementById('intentSanityBanner');
        if (sanityBanner && data.detected_goal) {
          const advPct = data.detected_goal.detected_adverse_rate_pct;
          const warnMsg = (appState.briefLanguage === 'hi' && data.detected_goal.target_sanity_warning_hi)
            ? data.detected_goal.target_sanity_warning_hi
            : data.detected_goal.target_sanity_warning_en;
          sanityBanner.classList.remove('hidden');
          if (warnMsg) {
            sanityBanner.style.background = 'rgba(245, 158, 11, 0.14)';
            sanityBanner.style.border = '1px solid rgba(245, 158, 11, 0.45)';
            sanityBanner.style.color = 'var(--accent-amber, #b45309)';
            sanityBanner.textContent = `⚠️ ${warnMsg}`;
          } else {
            sanityBanner.style.background = 'rgba(16, 185, 129, 0.10)';
            sanityBanner.style.border = '1px solid rgba(16, 185, 129, 0.35)';
            sanityBanner.style.color = 'var(--accent-emerald, #047857)';
            const costLabel = data.detected_goal.cost_col ? ` | Money: ${data.detected_goal.cost_col} (${data.detected_goal.unit_symbol})` : ' | Non-monetary counts';
            sanityBanner.textContent = `✅ Auto-Check Passed: ${advPct ?? '?'}% flagged as problem (${data.detected_goal.target_desc})${costLabel} — confirm below to start.`;
          }
        }

        const tgtSelect = document.getElementById('confirmTargetSelect');
        tgtSelect.innerHTML = '';
        const candidates = data.candidate_targets || [];
        candidates.forEach(c => {
          const opt = document.createElement('option');
          opt.value = c.column;
          const cntText = c.unique_values_count !== undefined
            ? `${c.unique_values_count} values`
            : `${c.adverse_rate_sample_pct ?? ''}% problem rate`;
          opt.textContent = `${c.column} (${cntText})`;
          if (c.is_detected_default) opt.selected = true;
          tgtSelect.appendChild(opt);
        });
        if (tgtSelect.options.length === 0 && data.columns) {
          data.columns.forEach(col => {
            const opt = document.createElement('option');
            opt.value = col;
            opt.textContent = col;
            tgtSelect.appendChild(opt);
          });
        }

        const costSelect = document.getElementById('confirmCostSelect');
        costSelect.innerHTML = '<option value="__NONE__">No Money Column (Count Problems Only)</option>';
        (data.candidate_costs || []).forEach(c => {
          const opt = document.createElement('option');
          opt.value = c.column;
          opt.textContent = `${c.column} (Avg: ${c.unit_symbol}${c.sample_mean})`;
          if (c.is_detected_default) opt.selected = true;
          costSelect.appendChild(opt);
        });

        // Auto-close upload onboarding modal so the 1-Second Intent Handshake card is immediately visible
        if (typeof closeOnboardingPanel === 'function') {
          closeOnboardingPanel();
        }
        card.scrollIntoView({ behavior: 'smooth', block: 'center' });
        showToast('File ready! Click "Start Analysis Now".', 'success');
      } catch (e) {
        showToast(`Could not read file: ${e.message}`, 'error');
      }
    }

    function onConfirmCategoryChange() {
      const cfSel = document.getElementById('confirmCategorySelect');
      const chosen = cfSel ? cfSel.value : 'auto';
      if (typeof populateSubCategoryDropdown === 'function') {
        populateSubCategoryDropdown(chosen, null);
      }
      const catWarn = document.getElementById('intentCategoryWarningBanner');
      const det = appState.detectedCategoryMeta;
      if (catWarn && det && det.is_confident && det.detected_category && det.detected_category !== 'auto' && chosen !== 'auto' && chosen !== det.detected_category) {
        const isHi = appState.briefLanguage === 'hi';
        catWarn.textContent = isHi
          ? `⚠️ आपकी फ़ाइल के कॉलम '${det.category_name_hi}' (${det.confidence_pct}% मिलान) से ज़्यादा मेल खाते हैं — सेफ़्टी गेट सक्रिय है, कोई नकली KPI नहीं बनेगा।`
          : `⚠️ Your file columns strongly resemble '${det.category_name_en}' (${det.confidence_pct}% match) — Safety Gate active: missing category KPIs will never be fabricated.`;
        catWarn.classList.remove('hidden');
      } else if (catWarn) {
        catWarn.classList.add('hidden');
        catWarn.textContent = '';
      }
    }

    function cancelIntentHandshake() {
      document.getElementById('intentHandshakeCard').classList.add('hidden');
      appState.selectedFile = null;
    }

    async function executeConfirmedPipeline() {
      if (!appState.selectedFile) {
        showToast('Pick a file first.', 'warn');
        return;
      }
      const tenant = document.getElementById('tenantInput').value.trim() || 'founder_workspace';
      const region = document.getElementById('regionSelect').value || 'US';
      const targetOverride = document.getElementById('confirmTargetSelect').value || '';
      const costOverride = document.getElementById('confirmCostSelect').value || '__NONE__';
      const bizCat = (document.getElementById('confirmCategorySelect') && document.getElementById('confirmCategorySelect').value) || 'auto';
      const bizSub = (document.getElementById('confirmSubCategorySelect') && document.getElementById('confirmSubCategorySelect').value) || '';
      const chosenLang = document.getElementById('confirmLangSelect').value || 'bilingual';
      if (chosenLang === 'hi') setGlobalLanguage('hi');
      else if (chosenLang === 'en') setGlobalLanguage('en');

      document.getElementById('intentHandshakeCard').classList.add('hidden');
      const progSec = document.getElementById('jobProgressSection');
      progSec.classList.remove('hidden');

      const fd = new FormData();
      fd.append('file', appState.selectedFile);
      fd.append('tenant_id', tenant);
      fd.append('region_profile', region);
      if (targetOverride) fd.append('target_override', targetOverride);
      if (costOverride) fd.append('cost_override', costOverride);
      if (bizCat) fd.append('business_category', bizCat);
      if (bizSub) fd.append('business_sub_category', bizSub);

      try {
        const submitRes = await apiFetch('/api/v1/jobs/submit', { method: 'POST', body: fd });
        if (!submitRes.ok) {
          throw new Error(`Submission error (${submitRes.status})`);
        }
        const jobMeta = await submitRes.json();
        await pollJobUntilComplete(jobMeta.job_id);
      } catch (e) {
        progSec.classList.add('hidden');
        showToast(`Analysis error: ${e.message}`, 'error');
      }
    }

    async function pollJobUntilComplete(jobId) {
      const progSec = document.getElementById('jobProgressSection');
      const fill = document.getElementById('progressBarFill');
      const pctLabel = document.getElementById('progressPctLabel');
      const stageName = document.getElementById('progressStageName');

      while (true) {
        const res = await apiFetch(`/api/v1/jobs/${encodeURIComponent(jobId)}/status`);
        if (!res.ok) throw new Error(`Status check failed (${res.status})`);
        const statusData = await res.json();

        const pct = statusData.progress_pct || 20;
        fill.style.width = `${pct}%`;
        pctLabel.textContent = `${pct}%`;
        stageName.textContent = statusData.current_stage || 'Processing...';

        const st = String(statusData.status || '').toUpperCase();
        if (st === 'COMPLETED' && statusData.result) {
          progSec.classList.add('hidden');
          document.getElementById('onboardingSection').classList.add('hidden');
          hydrateExecutiveConsole(statusData.result);
          showToast('Your Business Report is Ready!', 'success');
          return;
        }
        if (st === 'FAILED') {
          throw new Error(statusData.error || 'Analysis failed.');
        }
        await new Promise(r => setTimeout(r, 900));
      }
    }

    // =========================================================================
    // HYDRATE BUSINESS WORKSPACE
    // =========================================================================
    function hydrateExecutiveConsole(result) {
      appState.activeRunId = result.run_id;
      appState.activeOutputDir = result.output_dir;
      appState.activeTenant = result.tenant_id || document.getElementById('tenantInput').value || 'founder_workspace';
      appState.englishSummaryMd = result.english_summary_markdown || result.plain_summary_markdown || '';
      appState.hinglishSummaryMd = result.hinglish_summary_markdown || result.plain_summary_markdown || '';
      appState.executivePulse = result.executive_pulse || {};
      appState.proactiveAnomaly = result.proactive_anomaly || (appState.executivePulse && appState.executivePulse.proactive_anomaly) || null;
      appState.voiceBrief = result.voice_brief || (appState.executivePulse && appState.executivePulse.voice_brief) || null;
      appState.impactVerifier = result.impact_verifier || null;
      appState.omniLeakReport = result.omni_leak_report || (appState.executivePulse && appState.executivePulse.omni_leak_report) || null;
      appState.historicalDrift = result.historical_drift || {};
      appState.worklistRows = result.worklist_preview || [];
      appState.worklistMeta = result.worklist_meta || { primary_id_column: 'Entity_ID', total_flagged: appState.worklistRows.length };
      appState.resolvedEntities.clear();
      appState.digestPayload = null;
      appState.questions200Data = null;
      appState.questions200Pillar = 'ALL';
      appState.rankedLeaks = result.ranked_leaks || null;
      appState.rankedLeaksRaw = result.ranked_leaks || null;
      if (typeof resetCopilotChat === 'function') {
        resetCopilotChat(true);
      } else {
        appState.copilotHistory = [];
      }

      document.getElementById('executiveConsole').classList.remove('hidden');

      const pulse = appState.executivePulse;
      const sym = pulse.unit_symbol || '$';

      // Top Summary Ribbon (Humanized business name instead of ugly raw snake_case ID)
      const prettyBizName = humanizeRunTitle(result.run_id);
      document.getElementById('activeRunBadge').textContent = prettyBizName;
      document.getElementById('metaTotalRecords').textContent = formatNumberForCurrency(pulse.total_records || 0, sym);
      document.getElementById('metaAdverseCount').textContent = formatNumberForCurrency(pulse.total_adverse_events || 0, sym);
      document.getElementById('metaAdverseRate').textContent = `${Number(pulse.overall_adverse_rate_pct || 0).toFixed(2)}%`;
      document.getElementById('metaCapitalDrag').textContent =
        pulse.is_financial && pulse.total_capital_drag > 0
          ? pulse.formatted_capital_drag
          : `${formatNumberForCurrency(pulse.total_adverse_events || 0, sym)} Cases`;

      const dashLink = document.getElementById('openFullDashboardLink');
      dashLink.href = appendApiKeyToUrl(
        result.dashboard_url || `/api/v1/dashboard/${encodeURIComponent(result.run_id)}`
      );

      const certLink = document.getElementById('openPrintableCertLink');
      if (certLink) {
        certLink.href = appendApiKeyToUrl(
          `/api/v1/report/${encodeURIComponent(result.run_id)}/printable`
        );
      }

      renderOwnerCardsAndPlans();
      switchBriefLanguage(appState.briefLanguage);
      if (appState.briefLanguage && appState.briefLanguage !== 'en' && appState.briefLanguage !== 'hi') {
        setGlobalLanguage(appState.briefLanguage);
      }
      renderArtifactDownloadLinks(result.artifact_download_urls || {});
      recalculateSimulator();
      updateRoiSummaryCard(result.roi_summary || {}, sym);

      appState.activeCohortDimIdx = 0;
      renderCohortExplorer(pulse.cohort_breakdowns || []);
      renderWorklistTable();

      document.getElementById('copilotResultContainer').classList.add('hidden');
      appState.predictOverview = null;
      appState.predictOverviewRunId = null;
      appState.predictLastResult = null;
      appState.predictCompareList = [];
      appState.predictComboQueue = [];
      const predStage = document.getElementById('predictResultStage');
      if (predStage) predStage.classList.add('hidden');
      const predCmp = document.getElementById('predictCompareCard');
      if (predCmp) predCmp.classList.add('hidden');
      const predCombo = document.getElementById('predictComboQueueBox');
      if (predCombo) predCombo.classList.add('hidden');
      if (appState.activeTab === 'predict') {
        loadDecisionPredictorOverview(true);
      }
      appState.boardroomHistory = [];
      appState.boardroomStartersRunId = null;
      appState.boardroomStarters = [];
      const bFeed = document.getElementById('boardroomFeed');
      if (bFeed) bFeed.innerHTML = '';
      if (appState.activeTab === 'boardroom') {
        loadBoardroomStarters(true);
      }
      refreshTimeMachineRuns();
    }

    function renderOwnerCardsAndPlans() {
      const pulse = appState.executivePulse || {};
      const drift = appState.historicalDrift || {};
      const sym = pulse.unit_symbol || '$';
      const lang = appState.briefLanguage || 'en';
      const friendly = (pulse.owner_friendly && (pulse.owner_friendly[lang] || pulse.owner_friendly.en)) || null;

      // Period-over-Period Trend Banner in plain language
      const rateDelta = Number((drift.deltas && drift.deltas.event_rate_delta_pct) || 0);
      const expDelta = Number((drift.deltas && drift.deltas.mean_exposure_delta) || 0);
      const isBaseline = !drift.deltas || (rateDelta === 0 && expDelta === 0);
      if (isBaseline) {
        document.getElementById('driftHeadline').textContent = tUi(
          'lblBaselineSaved',
          'First report saved — upload next month\'s file later to compare progress'
        );
        document.getElementById('driftNarrative').textContent = tUi(
          'lblBaselineDesc',
          'Next time you upload updated sales/orders, you will see automatically whether problem rates improved or worsened.'
        );
      } else {
        document.getElementById('driftHeadline').textContent = drift.headline || 'Comparison Ready';
        document.getElementById('driftNarrative').textContent = drift.narrative_en || '';
      }
      const rateEl = document.getElementById('driftRateDelta');
      rateEl.textContent = `${rateDelta > 0 ? '+' : ''}${rateDelta.toFixed(2)} pp`;
      rateEl.style.color = rateDelta > 0.5 ? 'var(--accent-crimson)' : (rateDelta < -0.5 ? 'var(--accent-emerald)' : 'var(--text-primary)');
      document.getElementById('driftExposureDelta').textContent = `${expDelta >= 0 ? '+' : ''}${formatCurrencyValue(expDelta, sym)}`;

      // 4 Owner-Friendly Business Analyst Health Cards (adapt Money vs Quality labels automatically)
      const isFinPulse = Boolean(pulse.is_financial && Number(pulse.total_capital_drag || 0) > 0);
      const card2Lbl = document.querySelector('[data-i18n="card2Title"]');
      const card4Lbl = document.querySelector('[data-i18n="card4Title"]');
      if (card2Lbl) {
        card2Lbl.textContent = isFinPulse
          ? tUi('card2Title', '02 · Biggest Money Leak')
          : (lang === 'hi' ? '02 · सबसे बड़ी समस्या कहाँ है' : tUi('card2Quality', '02 · Biggest Problem Area'));
      }
      if (card4Lbl) {
        card4Lbl.textContent = isFinPulse
          ? tUi('card4Title', '04 · Money You Can Save')
          : (lang === 'hi' ? '04 · कितने केस सुधार सकते हैं' : tUi('card4Quality', '04 · Cases You Can Improve'));
      }
      if (friendly) {
        const m = friendly.moat || {};
        document.getElementById('pulseMoatBadge').textContent = m.badge || 'Safe';
        document.getElementById('pulseMoatHeadline').textContent = m.title || 'Working Smoothly';
        document.getElementById('pulseMoatDetail').textContent = m.story || '';
        document.getElementById('pulseMoatFooter').textContent = m.footer || '';

        const b = friendly.bottleneck || {};
        document.getElementById('pulseBottleneckBadge').textContent = b.badge || 'Leak';
        document.getElementById('pulseBottleneckHeadline').textContent = b.title || 'Biggest Leak';
        document.getElementById('pulseBottleneckDetail').textContent = b.story || '';
        document.getElementById('pulseBottleneckFooter').textContent = b.footer || '';

        const r = friendly.red_line || {};
        document.getElementById('pulseRedlineBadge').textContent = r.badge || 'Limit';
        document.getElementById('pulseRedlineHeadline').textContent = r.title || 'Warning Limit';
        document.getElementById('pulseRedlineDetail').textContent = r.story || '';
        document.getElementById('pulseRedlineFooter').textContent = r.footer || '';

        const rec = friendly.recovery || {};
        document.getElementById('pulseRecoveryBadge').textContent = rec.badge || 'Savings';
        document.getElementById('pulseRecoveryHeadline').textContent = rec.title || 'Money You Can Save';
        document.getElementById('pulseRecoveryDetail').textContent = rec.story || '';
        document.getElementById('pulseRecoveryFooter').textContent = rec.footer || '';

        renderOwnerPathways(friendly.pathways || []);
      } else {
        const moat = pulse.moat || {};
        document.getElementById('pulseMoatBadge').textContent = moat.value_badge || 'Safe';
        document.getElementById('pulseMoatHeadline').textContent = moat.headline || 'Best Performing Group';
        document.getElementById('pulseMoatDetail').textContent = moat.detail || '';
        document.getElementById('pulseMoatFooter').textContent = `${Number(pulse.total_records || 0).toLocaleString('en-US')} Checked`;

        const bottleneck = pulse.bottleneck || {};
        document.getElementById('pulseBottleneckBadge').textContent = bottleneck.value_badge || 'Leak';
        document.getElementById('pulseBottleneckHeadline').textContent = bottleneck.headline || 'Biggest Leak Area';
        document.getElementById('pulseBottleneckDetail').textContent = bottleneck.detail || '';
        document.getElementById('pulseBottleneckFooter').textContent = 'Fix First';

        const redLine = pulse.red_line || {};
        document.getElementById('pulseRedlineBadge').textContent = redLine.value_badge || 'Limit';
        document.getElementById('pulseRedlineHeadline').textContent = redLine.headline || 'Warning Limit';
        document.getElementById('pulseRedlineDetail').textContent = redLine.detail || '';
        document.getElementById('pulseRedlineFooter').textContent = 'Watch Limit';

        const firstPath = (pulse.pathways && pulse.pathways[0]) || {};
        document.getElementById('pulseRecoveryBadge').textContent = firstPath.roi_range || 'Savings';
        document.getElementById('pulseRecoveryHeadline').textContent =
          pulse.is_financial && pulse.total_capital_drag > 0
            ? `${pulse.formatted_capital_drag} Recoverable`
            : `${Number(pulse.total_adverse_events || 0).toLocaleString('en-US')} Fixable Cases`;
        document.getElementById('pulseRecoveryDetail').textContent = firstPath.action || 'Follow up with priority cases.';
        document.getElementById('pulseRecoveryFooter').textContent = `${Number(appState.worklistRows.length).toLocaleString('en-US')} Action Items`;

        renderStrategicPathways(pulse.pathways || []);
      }
      renderOwnerVisualCockpit(friendly);
      renderCategoryIntelligencePanel(pulse.category_intelligence || null, lang);
      renderGrowthInventoryPanel(pulse.growth_inventory || null, lang);
      renderOmniLeakPanel(pulse.omni_leak_report || appState.omniLeakReport || null);
      if (appState.activeRunId) {
        loadAndRenderRankedLeaks(appState.activeRunId, appState.rankedLeaks);
        loadAndRender200Questions(appState.activeRunId);
      }
    }

    function humanizeRunTitle(runId) {
      const id = String(runId || '').trim();
      const friendlyTitles = {
        nexura_lifestyle_brand: 'Nexura 3-Year D2C Brand',
        nexura_omnichannel_3yr: 'Nexura 3-Year D2C Brand',
        v2_indian_retail_mall: 'Indian Retail Mall Operations',
        reliance_retail_jiomart: 'Omnichannel Retail Logistics',
        hotel_booking_cancellation: 'Hotel Bookings & Cancellations',
        supermarket_retail_operations: 'Supermarket Store Sales',
        credit_card_loan_default: 'Credit & Loan Defaults',
        airline_flight_delays_operations: 'Airline Flight Delays',
        california_housing_real_estate: 'Real Estate Valuation',
        real_opensource_shopkeeper: 'Wholesale Shopkeeper POS'
      };
      if (friendlyTitles[id]) return friendlyTitles[id];
      if (/^job_\d+_[a-f0-9]{6,16}$/i.test(id)) return 'Uploaded Business Data';
      if (/^upload_\d+_[a-f0-9]{6,16}$/i.test(id)) return 'Uploaded Spreadsheet';
      const mConn = id.match(/^conn_(.+?)_[a-f0-9]{6,16}$/i);
      if (mConn) {
        return mConn[1].replace(/[_-]+/g, ' ').replace(/\b\w/g, ch => ch.toUpperCase()).trim();
      }
      const raw = (id || 'Business Report')
        .replace(/_[a-f0-9]{8,16}$/i, '')
        .replace(/^(?:job|run)_\d+_/i, '');
      return raw
        .replace(/[_-]+/g, ' ')
        .replace(/\b\w/g, ch => ch.toUpperCase())
        .trim();
    }

    function renderOwnerVisualCockpit(friendly) {
      const pulse = appState.executivePulse || {};
      const totalRec = Number(pulse.total_records || 0);
      const totalAdv = Number(pulse.total_adverse_events || 0);
      const advRate = Math.max(0, Math.min(100, Number(pulse.overall_adverse_rate_pct || 0)));
      const healthyRate = Math.max(0, Math.min(100, 100 - advRate));
      const healthScore = Math.round(healthyRate);
      const isFin = Boolean(pulse.is_financial && Number(pulse.total_capital_drag || 0) > 0);

      // 1. Animated SVG Business Health Ring Gauge
      const arc = document.getElementById('ownerHealthRingArc');
      const scoreEl = document.getElementById('ownerHealthScoreNum');
      const pillEl = document.getElementById('ownerHealthStatusPill');
      const circ = 314.16;
      const offset = circ * (1 - healthScore / 100);
      const ringColor = healthScore >= 75 ? '#10b981' : (healthScore >= 50 ? '#fbbf24' : '#fb7185');
      if (arc) {
        arc.style.strokeDashoffset = String(offset.toFixed(2));
        arc.style.stroke = ringColor;
      }
      if (scoreEl) scoreEl.textContent = String(healthScore);
      if (pillEl) {
        pillEl.className = healthScore >= 75 ? 'owner-status-pill' : (healthScore >= 50 ? 'owner-status-pill warn' : 'owner-status-pill danger');
        pillEl.textContent = healthScore >= 75
          ? tUi('statusHealthy', 'Strong Health')
          : (healthScore >= 50 ? tUi('statusAttention', 'Needs Attention') : tUi('statusUrgent', 'Urgent Leaks'));
      }

      // 2. Plain-Language Hero Headline & Instant Action Summary
      const bizTag = document.getElementById('ownerBizNameTag');
      const chkTag = document.getElementById('ownerCheckedSubTag');
      const heroBig = document.getElementById('ownerHeroHeadline');
      const heroSub = document.getElementById('ownerHeroActionLine');
      const symHero = pulse.unit_symbol || '$';
      if (bizTag) bizTag.textContent = humanizeRunTitle(appState.activeRunId);
      if (chkTag) chkTag.textContent = `${formatNumberForCurrency(totalRec, symHero)} ${tUi('lblRecordsChecked', 'records checked')}`;

      if (heroBig) {
        if (isFin) {
          heroBig.innerHTML = `<span class="hero-accent-money">${escapeHtml(pulse.formatted_capital_drag || '$0')}</span> ${escapeHtml(tUi('lblAtRiskAcross', 'at risk across'))} <span class="tabular-nums">${formatNumberForCurrency(totalAdv, symHero)}</span> ${escapeHtml(tUi('lblCasesWord', 'cases'))}`;
        } else {
          heroBig.innerHTML = `<span class="hero-accent-money">${formatNumberForCurrency(totalAdv, symHero)}</span> ${escapeHtml(tUi('lblProblemCasesFound', 'problem cases found'))} <span class="tabular-nums">(${advRate.toFixed(1)}%)</span>`;
        }
      }

      const topLeakTitle = (friendly && friendly.bottleneck && friendly.bottleneck.title)
        || (pulse.bottleneck && pulse.bottleneck.headline)
        || '';
      const quickSaveBadge = (friendly && friendly.recovery && friendly.recovery.badge)
        || (isFin ? (pulse.formatted_capital_drag || '--') : `${totalAdv.toLocaleString('en-US')}`);
      if (heroSub) {
        heroSub.textContent = topLeakTitle
          ? `${tUi('lblTopPriorityPrefix', 'Top priority:')} ${topLeakTitle}`
          : '';
      }

      // 3. Three Scannable Right-Side KPI Pills
      const okPctEl = document.getElementById('ownerKpiHealthyPct');
      const badPctEl = document.getElementById('ownerKpiProblemPct');
      const saveLblEl = document.getElementById('ownerKpiSaveLbl');
      const saveValEl = document.getElementById('ownerKpiQuickSaveVal');
      if (okPctEl) okPctEl.textContent = `${healthyRate.toFixed(1)}%`;
      if (badPctEl) badPctEl.textContent = `${advRate.toFixed(1)}%`;
      if (saveLblEl) {
        saveLblEl.textContent = isFin
          ? tUi('kpiQuickSavings', 'Quick Savings')
          : tUi('kpiFixableCases', 'Fixable Cases');
      }
      if (saveValEl) {
        const cleanSave = normalizeIndianRupeesInText(String(quickSaveBadge).replace(/^Save\s+/i, ''));
        saveValEl.textContent = cleanSave.replace(/\s*\(₹[^)]+\)/g, '');
      }

      // 4. Live Visual Horizontal Bar Chart (Top 5 Problem Groups vs Business Avg)
      const barsEl = document.getElementById('ownerVisualBarsList');
      const barTitleEl = document.getElementById('ownerBarChartTitle');
      const barSubEl = document.getElementById('ownerBarChartSub');
      const avgBadgeEl = document.getElementById('ownerBarAvgBadge');
      const breakdowns = pulse.cohort_breakdowns || [];
      const firstDim = breakdowns[0] || null;
      if (avgBadgeEl) avgBadgeEl.textContent = `${tUi('lblAvgPrefix', 'Avg:')} ${advRate.toFixed(1)}%`;
      if (barTitleEl) {
        barTitleEl.textContent = firstDim && firstDim.dimension_label
          ? `${tUi('chartLeaksTitle', 'Where Problems Happen Most')} · ${firstDim.dimension_label}`
          : tUi('chartLeaksTitle', 'Where Problems Happen Most');
      }
      if (barSubEl) barSubEl.textContent = tUi('chartLeaksSub', 'Comparing each group against your business average');

      if (barsEl) {
        const rows = (firstDim && Array.isArray(firstDim.rows)) ? firstDim.rows.slice(0, 5) : [];
        if (!rows.length) {
          barsEl.innerHTML = `<div style="font-size:12.5px;color:var(--text-muted);padding:12px 0;">${escapeHtml(tUi('lblNoChangeNeeded', 'No urgent changes needed — numbers look stable.'))}</div>`;
        } else {
          const maxR = Math.max(advRate * 1.15, ...rows.map(r => Number(r.adverse_rate_pct || 0)), 1);
          const avgLeftPct = Math.min(96, Math.max(4, (advRate / maxR) * 100));
          barsEl.innerHTML = rows.map(r => {
            const rate = Number(r.adverse_rate_pct || 0);
            const widthPct = Math.min(100, Math.max(4, (rate / maxR) * 100));
            const isAboveAvg = rate > advRate + 1.5;
            const fillBg = isAboveAvg
              ? 'linear-gradient(90deg, #be123c, #fb7185)'
              : (rate < advRate - 1.5 ? 'linear-gradient(90deg, #059669, #10b981)' : 'linear-gradient(90deg, #d97706, #fbbf24)');
            const valColor = isAboveAvg ? 'var(--accent-crimson)' : (rate < advRate - 1.5 ? 'var(--accent-emerald)' : 'var(--accent-amber)');
            const cleanLiab = (isFin && r.total_liability && r.total_liability !== '--')
              ? normalizeIndianRupeesInText(String(r.total_liability)).replace(/\s*\(₹[^)]+\)/g, '')
              : '';
            const extraMeta = cleanLiab ? ` · ${cleanLiab}` : ` · ${formatNumberForCurrency(r.adverse_events || 0, symHero)}`;
            return `
              <div class="viz-bar-row">
                <div class="viz-bar-meta">
                  <span class="viz-bar-name" title="${escapeHtml(r.segment)}">${escapeHtml(r.segment)}</span>
                  <span class="viz-bar-val" style="color:${valColor};">${rate.toFixed(1)}%<span style="color:var(--text-muted);font-weight:500;">${escapeHtml(extraMeta)}</span></span>
                </div>
                <div class="viz-bar-track">
                  <div class="viz-bar-fill" style="width:${widthPct.toFixed(1)}%;background:${fillBg};"></div>
                  <div class="viz-avg-marker" style="left:${avgLeftPct.toFixed(1)}%;" title="Business Avg: ${advRate.toFixed(1)}%"></div>
                </div>
              </div>
            `;
          }).join('');
        }
      }

      // 5. Right Chart Card: Healthy-vs-Risky Split Meter + 3 Clickable Improvement Plans
      const okLbl = document.getElementById('ownerSplitOkLabel');
      const riskLbl = document.getElementById('ownerSplitRiskLabel');
      const okBar = document.getElementById('ownerSplitOkBar');
      const riskBar = document.getElementById('ownerSplitRiskBar');
      if (okLbl) okLbl.textContent = `${tUi('lblHealthyShort', 'Healthy:')} ${healthyRate.toFixed(1)}%`;
      if (riskLbl) riskLbl.textContent = `${tUi('lblAtRiskShort', 'At Risk:')} ${advRate.toFixed(1)}%`;
      if (okBar) okBar.style.width = `${healthyRate.toFixed(1)}%`;
      if (riskBar) riskBar.style.width = `${advRate.toFixed(1)}%`;

      const plansEl = document.getElementById('ownerQuickPlansList');
      const plans = (friendly && Array.isArray(friendly.pathways) && friendly.pathways.length)
        ? friendly.pathways.slice(0, 3)
        : (pulse.pathways || []).slice(0, 3);
      if (plansEl) {
        if (!plans.length) {
          plansEl.innerHTML = `<div style="font-size:12.5px;color:var(--text-muted);">${escapeHtml(tUi('lblNoChangeNeeded', 'No urgent changes needed — numbers look stable.'))}</div>`;
        } else {
          plansEl.innerHTML = plans.map((p, idx) => {
            const pTitle = p.title || p.name || `Plan ${idx + 1}`;
            const pBadge = normalizeIndianRupeesInText(String(p.badge || p.roi_range || '')).replace(/\s*\(₹[^)]+\)/g, '');
            const pEffort = p.effort || p.target || '';
            return `
              <button type="button" class="viz-quick-plan-btn" onclick="openOwnerQuickPlan(${idx})">
                <div style="min-width:0;text-align:left;">
                  <div style="font-size:12.8px;font-weight:600;color:var(--text-primary);white-space:normal;line-height:1.35;">${escapeHtml(pTitle)}</div>
                  <div style="font-size:11px;color:var(--text-muted);white-space:normal;line-height:1.3;">${escapeHtml(pEffort)}</div>
                </div>
                <div style="text-align:right;flex-shrink:0;">
                  <div class="tabular-nums" style="font-size:12px;font-weight:700;color:var(--accent-emerald);">${escapeHtml(pBadge)}</div>
                  <div style="font-size:10.5px;color:var(--text-muted);">${escapeHtml(tUi('lblSimulateShort', 'Simulate →'))}</div>
                </div>
              </button>
            `;
          }).join('');
        }
      }
    }

    function openOwnerQuickPlan(idx) {
      const presetReductions = [25, 40, 60];
      const presetCosts = [2500, 10000, 25000];
      const rSl = document.getElementById('simReductionSlider');
      const cSl = document.getElementById('simCostSlider');
      if (rSl) rSl.value = presetReductions[idx] || 25;
      if (cSl) cSl.value = presetCosts[idx] !== undefined ? presetCosts[idx] : 2500;
      recalculateSimulator();
      switchWorkspaceTab('calculator', document.querySelector('[data-tab="calculator"]'));
    }

    function renderOmniLeakPanel(omni) {
      const sec = document.getElementById('omniLeakSection');
      const grid = document.getElementById('omniLeakCardsGrid');
      const titleEl = document.getElementById('omniLeakTitle');
      const badgeEl = document.getElementById('omniLeakBadge');
      if (!sec || !grid) return;
      if (!omni || (!omni.confirmed_leak_dimensions && !omni.pnl_and_coupons)) {
        sec.classList.add('hidden');
        return;
      }
      sec.classList.remove('hidden');
      const lang = appState.briefLanguage === 'hi' ? 'hi' : 'en';
      const sym = omni.unit_symbol || (appState.executivePulse && appState.executivePulse.unit_symbol) || '$';
      if (titleEl) {
        titleEl.textContent = lang === 'hi'
          ? '🔍 360° छुपे हुए नुकसान, वेयरहाउस/कूरियर देरी, कूपन और ग्राहक एक्स-रे (A-to-Z Scan)'
          : '🔍 360° A-to-Z Hidden Profit Leaks, SLA Bottlenecks & Customer Forensics';
      }
      if (badgeEl) {
        badgeEl.textContent = lang === 'hi'
          ? `${omni.audited_dimensions_count || 0} कॉलम + P&L पूरा स्कैन`
          : `${omni.audited_dimensions_count || 0} Dimensions + P&L Scanned`;
      }

      const cards = [];
      const leaks = omni.confirmed_leak_dimensions || [];
      if (leaks.length > 0) {
        const items = leaks.slice(0, 5).map(lk => {
          const cleanDim = String(lk.dimension || '').replace(/_/g, ' ');
          const rawSeg = String(lk.worst_segment || '');
          const segNice = rawSeg === '1' ? `${cleanDim} = High (1)` : (rawSeg === '0' ? `${cleanDim} = Low (0)` : `${cleanDim}: ${rawSeg}`);
          const wInt = Math.round(Number(lk.worst_rate_pct || 0));
          const multVal = Number(lk.risk_multiplier || 1);
          const multTxt = multVal >= 2.65 ? (lang === 'hi' ? 'लगभग 3 गुना ज़्यादा' : 'nearly 3× usual') : (multVal >= 1.75 ? (lang === 'hi' ? 'लगभग दोगुना' : 'nearly double') : `${multVal.toFixed(1)}×`);
          return `<li><strong>${escapeHtml(segNice)}</strong>: ${wInt}% ${lang === 'hi' ? 'में समस्या' : 'have problems'} (${escapeHtml(multTxt)}, ~${Math.round(lk.excess_events)} ${lang === 'hi' ? 'बचाये जा सकने वाले केस' : 'avoidable cases'})</li>`;
        }).join('');
        cards.push({
          tag: lang === 'hi' ? '1. सभी कॉलम के लीकेज' : '1. All Confirmed Leak Areas',
          color: 'var(--accent-crimson)',
          html: `<ul style="margin:6px 0 0 16px;font-size:12.5px;line-height:1.55;">${items}</ul>`
        });
      }

      const ops = omni.operational_sla_and_delay_findings || [];
      if (ops.length > 0) {
        const opItems = ops.slice(0, 3).map(o => {
          const rawHl = lang === 'hi' ? (o.headline_hi || o.headline_en) : o.headline_en;
          const cleanHl = typeof humanizeBusinessText === 'function' ? humanizeBusinessText(rawHl, lang) : rawHl;
          return `<li>${renderMarkdownHtml(cleanHl).replace(/<\/?p>/g, '')}</li>`;
        }).join('');
        cards.push({
          tag: lang === 'hi' ? '2. वेयरहाउस व कूरियर SLA देरी' : '2. Warehouse & Courier SLA Bottlenecks',
          color: 'var(--accent-amber)',
          html: `<ul style="margin:6px 0 0 16px;font-size:12.5px;line-height:1.55;">${opItems}</ul>`
        });
      }

      const cfs = omni.confounder_insights || [];
      const hs = omni.top_2d_hotspots || [];
      if (cfs.length > 0 || hs.length > 0) {
        let body = '';
        if (cfs[0]) {
          body += `<div style="font-size:12.5px;line-height:1.5;margin-bottom:6px;">${renderMarkdownHtml(lang === 'hi' ? cfs[0].explanation_hi : cfs[0].explanation_en).replace(/<\/?p>/g, '')}</div>`;
        }
        if (hs.length > 0) {
          const hStr = hs.slice(0, 2).map(h => `<code>${escapeHtml(h.dim_a)}=${escapeHtml(h.val_a)} × ${escapeHtml(h.dim_b)}=${escapeHtml(h.val_b)}</code> (<strong>${Number(h.rate_pct).toFixed(1)}%</strong>)`).join(', ');
          body += `<div style="font-size:12px;color:var(--text-secondary);"><strong>2x2 Hotspots:</strong> ${hStr}</div>`;
        }
        cards.push({
          tag: lang === 'hi' ? '3. छुपा हुआ सच (2x2 कॉम्बो)' : '3. Confounder Truth & 2x2 Combos',
          color: 'var(--accent-sky)',
          html: body
        });
      }

      const pnl = omni.pnl_and_coupons || {};
      if (pnl.has_margin_ledger || (pnl.toxic_coupons && pnl.toxic_coupons.length > 0)) {
        let pHtml = '';
        if (pnl.has_margin_ledger) {
          pHtml += `<div style="font-size:12.5px;line-height:1.55;">` +
            (lang === 'hi'
              ? `नेट प्रॉफिट मार्जिन: <strong>${formatCurrencyValue(pnl.total_net_margin, sym)}</strong> · जेब से निगेटिव-मार्जिन घाटा: <strong style="color:var(--accent-crimson);">-${formatCurrencyValue(Math.abs(pnl.negative_margin_cash_loss), sym)}</strong> (${Number(pnl.negative_margin_order_count).toLocaleString()} ऑर्डर, रिवर्स शिपिंग: ${formatCurrencyValue(pnl.reverse_shipping_burn, sym)})`
              : `Net Contribution Margin: <strong>${formatCurrencyValue(pnl.total_net_margin, sym)}</strong> · Out-of-Pocket Negative-Margin Loss: <strong style="color:var(--accent-crimson);">-${formatCurrencyValue(Math.abs(pnl.negative_margin_cash_loss), sym)}</strong> (${Number(pnl.negative_margin_order_count).toLocaleString()} orders, Reverse Shipping: ${formatCurrencyValue(pnl.reverse_shipping_burn, sym)})`) +
            `</div>`;
        }
        if (pnl.toxic_coupons && pnl.toxic_coupons[0]) {
          const tc = pnl.toxic_coupons[0];
          pHtml += `<div style="font-size:12.5px;margin-top:6px;color:var(--accent-amber);">` +
            (lang === 'hi'
              ? `⚠️ <strong>डबल नुकसान कूपन '${escapeHtml(tc.coupon_code)}'</strong>: ${tc.orders} ऑर्डर, मुनाफा ${tc.margin_delta_vs_no_coupon_pct}% गिरकर ${sym}${tc.avg_margin_per_order} रह गया और फेलियर ${tc.failure_rate_pct}% बढ़ा!`
              : `⚠️ <strong>Toxic Promo '${escapeHtml(tc.coupon_code)}'</strong>: ${tc.orders} orders, cuts unit profit by ${tc.margin_delta_vs_no_coupon_pct}% (to ${sym}${tc.avg_margin_per_order}) while lifting failure rate to ${tc.failure_rate_pct}%!`) +
            `</div>`;
        }
        cards.push({
          tag: lang === 'hi' ? '4. असली नकद मुनाफा व कूपन घाटा' : '4. True Cash Margin & Promo Erosion',
          color: 'var(--accent-emerald)',
          html: pHtml
        });
      }

      const ent = omni.entities_and_skus || {};
      const seas = omni.seasonal_regimes || {};
      if (ent.has_repeat_entities || seas.has_quarterly_regime_shift) {
        let eHtml = '';
        if (ent.has_repeat_entities) {
          eHtml += `<div style="font-size:12.5px;line-height:1.55;">` +
            (lang === 'hi'
              ? `<strong>${Number(ent.negative_ltv_entity_count).toLocaleString()} निगेटिव-LTV ग्राहक</strong> (-${formatCurrencyValue(Math.abs(ent.negative_ltv_total_cash_loss), sym)} घाटा) और <strong>${ent.serial_abuser_count} सीरियल RTO ग्राहक</strong> (${ent.serial_abuser_total_failures} बार फेल)।`
              : `<strong>${Number(ent.negative_ltv_entity_count).toLocaleString()} Negative-LTV Accounts</strong> (-${formatCurrencyValue(Math.abs(ent.negative_ltv_total_cash_loss), sym)} loss) &amp; <strong>${ent.serial_abuser_count} Serial Repeat Offenders</strong> (${ent.serial_abuser_total_failures} repeat failures).`) +
            `</div>`;
        }
        if (seas.has_quarterly_regime_shift) {
          const ddVal = seas.peak_quarter_dispatch_delay;
          const ddUnit = (ddVal !== null && ddVal !== undefined && Number(ddVal) > 15) ? (lang === 'hi' ? ' घंटे' : ' hrs') : (lang === 'hi' ? ' दिन' : 'd');
          const ddTxt = ddVal !== null && ddVal !== undefined ? `${ddVal}${ddUnit}` : '--';
          eHtml += `<div style="font-size:12.5px;margin-top:6px;color:var(--text-secondary);">` +
            (lang === 'hi'
              ? `📅 <strong>${escapeHtml(seas.peak_quarter)} फेस्टिव लोड अलर्ट</strong>: फेलियर ${seas.rest_of_year_failure_pct}% → <strong>${seas.peak_quarter_failure_pct}%</strong>, SLA ब्रीच <strong>${seas.peak_quarter_sla_breach_pct ?? '--'}%</strong>, डिस्पैच देरी <strong>${ddTxt}</strong>।`
              : `📅 <strong>${escapeHtml(seas.peak_quarter)} Seasonal Surge</strong>: Failure rate jumps ${seas.rest_of_year_failure_pct}% → <strong>${seas.peak_quarter_failure_pct}%</strong>, SLA breach hits <strong>${seas.peak_quarter_sla_breach_pct ?? '--'}%</strong>, dispatch delay <strong>${ddTxt}</strong>.`) +
            `</div>`;
        }
        cards.push({
          tag: lang === 'hi' ? '5. सीरियल RTO ग्राहक व सीज़नल अलर्ट' : '5. Repeat Abusers & Seasonal Spike',
          color: 'var(--accent-crimson)',
          html: eHtml
        });
      }

      grid.innerHTML = cards.map(c => `
        <div style="background:var(--bg-elevated);border:1px solid var(--border-subtle);border-left:4px solid ${c.color};border-radius:10px;padding:12px 14px;">
          <div style="font-size:12px;font-weight:800;color:${c.color};text-transform:uppercase;letter-spacing:0.04em;">${c.tag}</div>
          ${c.html}
        </div>
      `).join('');
    }

    function renderCategoryIntelligencePanel(catIntel, lang) {
      const sec = document.getElementById('categoryIntelSection');
      if (!sec) return;
      const isHi = String(lang || appState.briefLanguage || 'en').toLowerCase().startsWith('hi');
      if (!catIntel || !catIntel.category_id) {
        sec.classList.add('hidden');
        return;
      }
      const kpis = catIntel.computed_kpis || [];
      const unlocks = catIntel.missing_column_unlocks || [];
      if (!kpis.length && !unlocks.length) {
        sec.classList.add('hidden');
        return;
      }
      sec.classList.remove('hidden');

      const eye = document.getElementById('catIntelEyebrow');
      const ttl = document.getElementById('catIntelTitle');
      const sub = document.getElementById('catIntelSubtitle');
      const bdg = document.getElementById('catIntelModeBadge');
      const warnBox = document.getElementById('catIntelWarningBox');
      const packsRow = document.getElementById('catIntelPacksRow');
      const kpiGrid = document.getElementById('catIntelKpiGrid');
      const unlockRow = document.getElementById('catIntelUnlockRow');

      const catName = isHi ? (catIntel.category_name_hi || catIntel.category_name_en) : catIntel.category_name_en;
      const icon = catIntel.icon || '✨';
      if (eye) eye.textContent = isHi ? 'कैटेगरी इकोनॉमिक्स व स्टैटिस्टिक्स पैक' : 'CATEGORY ECONOMICS & STATISTICS PACK';
      if (ttl) ttl.textContent = `${icon} ${catName}`;
      if (sub) {
        sub.textContent = isHi
          ? 'इस बिज़नेस कैटेगरी के लिए 100% सत्यापित इकोनॉमिक्स व स्टैटिस्टिक्स (सिर्फ़ मौजूद कॉलम्स से)।'
          : '100% physically verified Economics & Statistics tailored to this business category (zero fabricated metrics).';
      }
      if (bdg) {
        const mode = catIntel.selection_mode || 'auto_detected';
        const cPct = Number((catIntel.detection && catIntel.detection.confidence_pct) || 0);
        if (mode === 'user_selected') {
          bdg.textContent = isHi ? 'यूज़र द्वारा चुनी गई' : 'User Selected';
        } else if (mode === 'auto_detected') {
          bdg.textContent = isHi ? `ऑटो-डिटेक्ट (${cPct}%)` : `Auto-Detected (${cPct}%)`;
        } else {
          bdg.textContent = isHi ? 'सामान्य यूनिवर्सल मोड' : 'Universal Safe Mode';
        }
      }

      if (warnBox) {
        const wMsg = (isHi ? catIntel.mismatch_warning_hi : catIntel.mismatch_warning_en)
          || (isHi ? catIntel.circuit_breaker_advisory_hi : catIntel.circuit_breaker_advisory_en);
        if (wMsg) {
          warnBox.textContent = `⚠️ ${wMsg}`;
          warnBox.classList.remove('hidden');
        } else {
          warnBox.classList.add('hidden');
          warnBox.textContent = '';
        }
      }

      if (packsRow) {
        const ePacks = (isHi ? catIntel.economics_pack_hi : catIntel.economics_pack_en) || [];
        const sPacks = (isHi ? catIntel.statistics_pack_hi : catIntel.statistics_pack_en) || [];
        packsRow.innerHTML = [
          ...ePacks.slice(0, 3).map(t => `<span class="cat-pack-pill econ">💰 ${escapeHtml(t)}</span>`),
          ...sPacks.slice(0, 3).map(t => `<span class="cat-pack-pill stat">📐 ${escapeHtml(t)}</span>`),
        ].join('');
      }

      if (kpiGrid) {
        kpiGrid.innerHTML = kpis.map(k => {
          const lbl = isHi ? (k.label_hi || k.label_en) : k.label_en;
          const ins = isHi ? (k.insight_hi || k.insight_en) : k.insight_en;
          const kindTxt = k.kind === 'economics'
            ? (isHi ? 'इकोनॉमिक्स' : 'ECONOMICS')
            : (isHi ? 'स्टैटिस्टिक्स' : 'STATISTICS');
          const toneCls = `tone-${k.tone || 'neutral'}`;
          return `
            <article class="cat-kpi-card ${toneCls}" title="${escapeHtml(k.formula_proof || '')}">
              <div class="cat-kpi-top">
                <span class="cat-kpi-label">${escapeHtml(lbl)}</span>
                <span class="cat-kpi-kind">${escapeHtml(kindTxt)}</span>
              </div>
              <div class="cat-kpi-value tabular-nums">${escapeHtml(
                isHi
                  ? String(k.formatted_value || '').replace(/\bdays\b/gi, 'दिन').replace(/\bhours\b/gi, 'घंटे')
                  : String(k.formatted_value || '')
              )}</div>
              <div class="cat-kpi-insight">${escapeHtml(ins)}</div>
            </article>
          `;
        }).join('');
      }

      if (unlockRow) {
        if (unlocks.length) {
          unlockRow.classList.remove('hidden');
          const lead = isHi ? '🔓 अतिरिक्त कॉलम जोड़कर और कैटेगरी KPI अनलॉक करें:' : '🔓 Add columns to unlock more category KPIs:';
          unlockRow.innerHTML = `<strong style="color:var(--text-primary);">${escapeHtml(lead)}</strong> ` + unlocks.slice(0, 3).map(u => {
            const ul = isHi ? (u.label_hi || u.label_en) : u.label_en;
            const uc = isHi ? (u.needed_columns_hi || u.needed_columns_en) : u.needed_columns_en;
            return `<span class="cat-pack-pill">+ ${escapeHtml(ul)} (${escapeHtml(uc)})</span>`;
          }).join('');
        } else {
          unlockRow.classList.add('hidden');
          unlockRow.innerHTML = '';
        }
      }

      // Dynamically tailor Ask AI Quick Chips to active Business Category!
      const chipsWrap = document.getElementById('copilotQuickChips');
      const presets = isHi ? (catIntel.qa_presets_hi || []) : (catIntel.qa_presets_en || []);
      if (chipsWrap && presets.length) {
        const icons = ['🔴', '💰', '📊', '🔍'];
        chipsWrap.innerHTML = presets.slice(0, 4).map((q, i) => `
          <button type="button" class="copilot-chip" onclick="askPresetQuestion(${JSON.stringify(q).replace(/"/g, '&quot;')})">
            ${icons[i % icons.length]} ${escapeHtml(q)}
          </button>
        `).join('');
      }
    }

    function renderGrowthInventoryPanel(gi, lang) {
      const sec = document.getElementById('growthInventorySection');
      if (!sec) return;
      if (!gi || !gi.is_applicable) {
        sec.classList.add('hidden');
        return;
      }
      sec.classList.remove('hidden');
      const isHi = String(lang || appState.briefLanguage || appState.language || 'en').toLowerCase().startsWith('hi');
      const kpis = gi.kpis || {};
      const fc = gi.demand_forecast || {};
      const abc = gi.abc_summary || {};
      const nar = (gi.narratives && (isHi ? gi.narratives.hi : gi.narratives.en)) || {};

      const eyebrow = document.getElementById('giEyebrow');
      const headline = document.getElementById('giHeadline');
      const sub = document.getElementById('giSubtitle');
      const badge = document.getElementById('giModeBadge');
      if (eyebrow) eyebrow.textContent = isHi ? 'बिक्री · मुनाफ़ा · 30-दिन अनुमान · स्टॉक री-ऑर्डर' : 'SALES · PROFIT · 30-DAY FORECAST · STOCK REORDER';
      if (headline) headline.textContent = nar.headline || (isHi ? 'बिक्री, मुनाफ़ा और स्टॉक योजना' : 'Sales, Margin & 30-Day Stock Plan');
      if (sub) {
        sub.textContent = isHi
          ? (gi.is_pure_sales_ledger ? 'शुद्ध बिक्री/स्टॉक रजिस्टर मोड सक्रिय — हर आँकड़ा असली डेटा पर आधारित है।' : 'बिक्री वृद्धि, मार्जिन और स्टॉक योजना का अतिरिक्त विश्लेषण।')
          : (gi.is_pure_sales_ledger ? 'Pure Sales & Stock Register mode active — every forecast and reorder number is physically grounded.' : 'Companion commercial growth, profit margin, and inventory reorder intelligence.');
      }
      if (badge) {
        badge.textContent = gi.is_pure_sales_ledger
          ? (isHi ? 'शुद्ध सेल्स मोड' : 'Pure Sales Mode')
          : (isHi ? 'सेल्स + स्टॉक रडार' : 'Sales + Stock Radar');
      }

      const kpiStrip = document.getElementById('giKpiStrip');
      if (kpiStrip) {
        const cards = [
          {
            lbl: isHi ? 'कुल बिक्री' : 'Total Sales',
            val: kpis.total_revenue_fmt || '--',
            foot: isHi ? `${Number(kpis.total_orders || 0).toLocaleString('en-IN')} बिल · औसत ${kpis.avg_order_value_fmt || '--'}` : `${Number(kpis.total_orders || 0).toLocaleString('en-US')} bills · Avg ${kpis.avg_order_value_fmt || '--'}`
          },
          {
            lbl: isHi ? 'कुल मुनाफ़ा व मार्जिन' : 'Gross Profit & Margin',
            val: kpis.has_profit ? `${kpis.gross_profit_fmt} (${kpis.gross_margin_pct}%)` : (isHi ? 'लागत कॉलम नहीं' : 'No Cost Column'),
            foot: kpis.has_profit
              ? (isHi ? `${(gi.negative_margin_items || []).length} कम/नेगेटिव मार्जिन आइटम` : `${(gi.negative_margin_items || []).length} low/negative margin SKUs`)
              : (isHi ? 'मुनाफ़ा देखने को Cost Price जोड़ें' : 'Add Cost Price to unlock margin audit')
          },
          {
            lbl: isHi ? 'अगले 30 दिन का अनुमान' : 'Next 30-Day Forecast',
            val: fc.forecast_available ? fc.next_30d_revenue_fmt : (isHi ? 'कम इतिहास' : 'Need More Dates'),
            foot: fc.forecast_available
              ? (isHi ? `रेंज: ${fc.next_30d_revenue_low95_fmt} – ${fc.next_30d_revenue_high95_fmt}` : `95% CI: ${fc.next_30d_revenue_low95_fmt} – ${fc.next_30d_revenue_high95_fmt}`)
              : (isHi ? 'कम से कम 3 महीने/10 दिन का डेटा चाहिए' : 'Needs >=3 months or >=10 sales days')
          },
          {
            lbl: isHi ? 'स्टॉक व ABC (80/20)' : 'Stock & ABC Pareto',
            val: (gi.reorder_alerts || []).length > 0
              ? (isHi ? `${gi.reorder_alerts.length} आइटम कम स्टॉक` : `${gi.reorder_alerts.length} Reorder Alerts`)
              : (abc.class_a_skus ? (isHi ? `टॉप ${abc.class_a_skus} आइटम = ${abc.class_a_revenue_share_pct}%` : `Top ${abc.class_a_skus} SKUs = ${abc.class_a_revenue_share_pct}%`) : '--'),
            foot: (gi.dead_stock_items || []).length > 0
              ? (isHi ? `${gi.dead_stock_items.length} फँसा हुआ माल (Dead Stock)` : `${gi.dead_stock_items.length} overstock / slow-moving SKUs`)
              : (isHi ? `कुल ${abc.total_skus || 0} आइटम जाँचे गए` : `${abc.total_skus || 0} SKUs audited`)
          }
        ];
        kpiStrip.innerHTML = cards.map(c => `
          <article class="pulse-card" style="padding:14px;">
            <div>
              <div class="pulse-label" style="margin-bottom:6px;">${escapeHtml(c.lbl)}</div>
              <h3 class="pulse-headline" style="font-size:18px;margin:0 0 6px 0;">${escapeHtml(c.val)}</h3>
            </div>
            <div class="pulse-footer"><span>${escapeHtml(c.foot)}</span></div>
          </article>
        `).join('');
      }

      const actionGrid = document.getElementById('giActionGrid');
      if (actionGrid) {
        const acts = nar.actions || [];
        actionGrid.innerHTML = acts.slice(0, 6).map(txt => `
          <div class="pulse-card" style="padding:12px 14px;font-size:13px;line-height:1.5;color:var(--text-primary);">
            ${escapeHtml(txt)}
          </div>
        `).join('');
      }
    }

    // =========================================================================
    // V7.0 EXECUTIVE QUICK BRIEF, PROACTIVE ANOMALY RADAR & 1-CLICK SHARE PACK
    // =========================================================================
    const v7VoiceState = {
      transcriptOpen: false,
    };

    function renderV7VoiceRadarAndImpact(lang) {
      const isHi = String(lang || appState.briefLanguage || appState.language || 'en').toLowerCase().startsWith('hi');
      const vb = appState.voiceBrief || (appState.executivePulse && appState.executivePulse.voice_brief) || null;
      const radar = appState.proactiveAnomaly || (appState.executivePulse && appState.executivePulse.proactive_anomaly) || null;
      const impact = appState.impactVerifier || null;

      // 1. 1-Click Executive Quick Brief & Share Action Bar (Zero Robotic Audio)
      const vBar = document.getElementById('v7VoiceShareBar');
      const scriptBtn = document.getElementById('btnV7ScriptToggle');
      const statusPill = document.getElementById('v7VoiceStatusPill');
      const pngBtn = document.getElementById('btnV7ShareCardPng');
      const waBtn = document.getElementById('btnV7CopyWhatsApp');
      const pdfLink = document.getElementById('openV7BoardroomPdfLink');

      if (vBar) {
        if (vb && Array.isArray(vb.beats) && vb.beats.length) {
          vBar.classList.remove('hidden');
          if (scriptBtn) {
            scriptBtn.textContent = v7VoiceState.transcriptOpen
              ? (isHi ? '📝 4-पॉइंट ब्रीफ़ बंद करें ▴' : '📝 4-Point Executive Brief ▴')
              : (isHi ? '📝 4-पॉइंट ब्रीफ़ पढ़ें ▾' : '📝 4-Point Executive Brief ▾');
          }
          if (statusPill) {
            statusPill.textContent = isHi
              ? '100% DuckDB-Verified · शेयर करने के लिए तैयार'
              : '100% DuckDB-Verified · Ready to Share';
          }
          if (pngBtn) pngBtn.textContent = isHi ? '📲 शेयर कार्ड PNG' : '📲 Share Card PNG';
          if (waBtn) waBtn.textContent = isHi ? '📋 WhatsApp कॉपी' : '📋 WhatsApp Text';
          if (pdfLink && appState.activeRunId) {
            pdfLink.href = appendApiKeyToUrl(
              `/api/v1/report/${encodeURIComponent(appState.activeRunId)}/boardroom-brief?lang=${isHi ? 'hi' : 'en'}`
            );
            pdfLink.textContent = isHi ? '📄 2-पेज PDF' : '📄 2-Page PDF';
          }
          const beatsGrid = document.getElementById('v7VoiceBeatsGrid');
          if (beatsGrid) {
            beatsGrid.innerHTML = vb.beats.map((b, idx) => `
              <div class="v7-beat-card" data-beat-idx="${idx}">
                <div class="v7-beat-title">${idx + 1}. ${escapeHtml(isHi ? (b.title_hi || b.title_en) : b.title_en)}</div>
                <div class="v7-beat-text">${escapeHtml(isHi ? (b.speech_hi || b.speech_en) : b.speech_en)}</div>
              </div>
            `).join('');
          }
        } else {
          vBar.classList.add('hidden');
        }
      }

      // 2. Proactive Early-Warning Anomaly Radar (Guard R1: auto-hidden if no date axis!)
      const radSec = document.getElementById('v7AnomalyRadarSection');
      if (radSec) {
        if (!radar || !radar.is_applicable) {
          radSec.classList.add('hidden');
        } else {
          radSec.classList.remove('hidden');
          const lvl = String(radar.overall_alert_level || 'ALL_CLEAR').toUpperCase();
          radSec.className = `v7-radar-card level-${lvl.toLowerCase()}`;

          const eb = document.getElementById('v7RadarEyebrow');
          const mt = document.getElementById('v7RadarMetaTag');
          const badge = document.getElementById('v7RadarLevelBadge');
          const hl = document.getElementById('v7RadarHeadline');
          if (eb) eb.textContent = isHi ? 'प्रोएक्टिव अर्ली-वॉर्निंग रडार (आने वाला ख़तरा पहले पकड़ें)' : 'PROACTIVE EARLY-WARNING ANOMALY RADAR';
          if (mt) mt.textContent = `${radar.periods_analyzed || 0} ${radar.bucket_granularity || 'periods'} · ${radar.date_column || ''}`;
          if (badge) {
            badge.className = `v7-level-pill ${lvl === 'CRITICAL' ? 'critical' : (lvl === 'WATCH' ? 'watch' : '')}`;
            badge.textContent = lvl === 'CRITICAL'
              ? (isHi ? '🔴 तुरंत अलर्ट' : '🔴 CRITICAL SPIKE')
              : (lvl === 'WATCH' ? (isHi ? '🟠 निगरानी अलर्ट' : '🟠 WATCH TREND') : (isHi ? '🟢 स्थिति स्थिर' : '🟢 ALL CLEAR'));
          }
          if (hl) hl.textContent = isHi ? (radar.headline_hi || radar.headline_en) : radar.headline_en;

          // Inline Zero-CDN SVG Sparkline
          const spBox = document.getElementById('v7RadarSparkline');
          const series = radar.period_series || [];
          if (spBox && series.length >= 2) {
            const W = 210, H = 48, pad = 6;
            const vals = series.map(p => Number(p.adverse_rate_pct || 0));
            const minV = Math.min(...vals, 0);
            const maxV = Math.max(...vals, minV + 1);
            const pts = series.map((p, idx) => {
              const x = pad + (idx / Math.max(series.length - 1, 1)) * (W - pad * 2);
              const y = H - pad - ((Number(p.adverse_rate_pct || 0) - minV) / Math.max(maxV - minV, 0.01)) * (H - pad * 2);
              return { x, y, spike: !!p.is_spike, lbl: p.period, r: p.adverse_rate_pct };
            });
            const poly = pts.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
            const strokeCol = lvl === 'CRITICAL' ? '#ef4444' : (lvl === 'WATCH' ? '#f59e0b' : '#10b981');
            const dots = pts.filter(p => p.spike).map(p => `<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="3.5" fill="#ef4444"></circle>`).join('');
            const lastP = pts[pts.length - 1];
            spBox.innerHTML = `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="Trend sparkline">
              <polyline fill="none" stroke="${strokeCol}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" points="${poly}"></polyline>
              ${dots}
              <circle cx="${lastP.x.toFixed(1)}" cy="${lastP.y.toFixed(1)}" r="3" fill="${strokeCol}"></circle>
            </svg>`;
          } else if (spBox) {
            spBox.innerHTML = '';
          }

          // Accelerating Cohort Cards
          const cGrid = document.getElementById('v7RadarCohortsGrid');
          const cohorts = radar.accelerating_cohorts || [];
          if (cGrid) {
            if (cohorts.length) {
              cGrid.classList.remove('hidden');
              cGrid.innerHTML = cohorts.slice(0, 3).map(c => `
                <div class="v7-cohort-pill-card ${c.severity === 'CRITICAL' ? 'critical' : ''}">
                  <div style="font-weight:800;color:var(--text-primary);margin-bottom:3px;">
                    ${escapeHtml(c.dimension_label || c.dimension)}: ${escapeHtml(c.segment)}
                    <span style="color:var(--accent-crimson);margin-left:6px;">+${Number(c.delta_pp || 0).toFixed(1)} pp</span>
                  </div>
                  <div>${escapeHtml(isHi ? (c.headline_hi || c.headline_en) : c.headline_en)}</div>
                </div>
              `).join('');
            } else {
              cGrid.classList.add('hidden');
              cGrid.innerHTML = '';
            }
          }

          // Bounded 30-Day Forward Risk Outlook
          const pBar = document.getElementById('v7RadarProjectionBar');
          const proj = radar.forward_risk_projection || null;
          if (pBar) {
            if (proj && (proj.note_en || proj.note_hi)) {
              pBar.classList.remove('hidden');
              pBar.textContent = `⏱️ ${isHi ? (proj.note_hi || proj.note_en) : proj.note_en}`;
            } else {
              pBar.classList.add('hidden');
              pBar.textContent = '';
            }
          }
        }
      }

      // 3. Closed-Loop Before-vs-After Impact Verifier
      const impBan = document.getElementById('v7ImpactVerifierBanner');
      if (impBan) {
        if (impact && impact.has_comparison) {
          impBan.classList.remove('hidden');
          const vbBadge = document.getElementById('v7ImpactVerdictBadge');
          const impHl = document.getElementById('v7ImpactHeadline');
          const impMeta = document.getElementById('v7ImpactMeta');
          if (vbBadge) {
            const v = impact.verdict || 'NO_STATISTICAL_CHANGE';
            vbBadge.className = `v7-level-pill ${v === 'WORSENED' ? 'critical' : (v === 'NO_STATISTICAL_CHANGE' ? 'watch' : '')}`;
            vbBadge.textContent = v === 'VERIFIED_IMPROVEMENT'
              ? (isHi ? '✅ प्लान कामयाब' : '✅ FIX VERIFIED')
              : (v === 'WORSENED' ? (isHi ? '🔴 गिरावट' : '🔴 WORSENED') : (isHi ? '📊 स्थिर' : '📊 FLAT'));
          }
          if (impHl) impHl.textContent = isHi ? (impact.headline_hi || impact.headline_en) : impact.headline_en;
          if (impMeta) impMeta.textContent = `p=${Number(impact.p_value || 1).toFixed(4)} · ${impact.actions_logged || 0} actions`;
        } else {
          impBan.classList.add('hidden');
        }
      }
    }

    function toggleV7VoiceTranscript() {
      v7VoiceState.transcriptOpen = !v7VoiceState.transcriptOpen;
      const panel = document.getElementById('v7VoiceBeatsPanel');
      if (panel) panel.classList.toggle('hidden', !v7VoiceState.transcriptOpen);
      renderV7VoiceRadarAndImpact(appState.briefLanguage || 'en');
    }

    async function copyWhatsAppShareText() {
      const vb = appState.voiceBrief || (appState.executivePulse && appState.executivePulse.voice_brief) || null;
      if (!vb) return;
      const isHi = String(appState.briefLanguage || 'en').toLowerCase().startsWith('hi');
      const txt = isHi ? (vb.whatsapp_share_hi || vb.whatsapp_share_en) : (vb.whatsapp_share_en || '');
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          await navigator.clipboard.writeText(txt);
        } else {
          const ta = document.createElement('textarea');
          ta.value = txt;
          document.body.appendChild(ta);
          ta.select();
          document.execCommand('copy');
          document.body.removeChild(ta);
        }
        showToast(isHi ? 'WhatsApp ब्रीफ़ कॉपी हो गया! अब सीधे ग्रुप में पेस्ट करें।' : 'PII-free WhatsApp brief copied! Paste directly into team chat.', 'success');
      } catch (_e) {
        showToast('Could not copy automatically — open Brief modal to copy.', 'warn');
      }
    }

    function exportWhatsAppStoryCardPng() {
      const vb = appState.voiceBrief || (appState.executivePulse && appState.executivePulse.voice_brief) || null;
      const sc = vb && vb.story_card;
      if (!sc) return;
      const isHi = String(appState.briefLanguage || 'en').toLowerCase().startsWith('hi');
      const canvas = document.createElement('canvas');
      canvas.width = 1200;
      canvas.height = 630;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      // Sleek Obsidian Executive Card (Zero CDN, Zero PII!)
      const grad = ctx.createLinearGradient(0, 0, 1200, 630);
      grad.addColorStop(0, '#0f172a');
      grad.addColorStop(1, '#1e293b');
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, 1200, 630);

      // Accent top bar
      ctx.fillStyle = '#10b981';
      ctx.fillRect(0, 0, 1200, 8);

      // Eyebrow & Title
      ctx.fillStyle = '#38bdf8';
      ctx.font = '700 18px system-ui, -apple-system, sans-serif';
      ctx.fillText(`DATAX-RAY V7.0 · ${(isHi ? sc.category_hi : sc.category_en).toUpperCase()} · 100% VERIFIED TRUTH`, 56, 62);

      ctx.fillStyle = '#f8fafc';
      ctx.font = '800 38px system-ui, -apple-system, sans-serif';
      ctx.fillText(String(sc.title || 'Executive Brief').slice(0, 42), 56, 114);

      // 3 KPI Tiles
      const tiles = [
        { lbl: isHi ? 'कुल रिकॉर्ड' : 'VERIFIED RECORDS', val: sc.records_formatted, col: '#38bdf8' },
        { lbl: isHi ? 'समस्या दर' : 'PROBLEM RATE', val: sc.adverse_rate_formatted, col: '#f59e0b' },
        { lbl: sc.is_financial ? (isHi ? 'खतरे में रकम' : 'AT-RISK EXPOSURE') : (isHi ? 'प्रभावित केस' : 'ADVERSE CASES'), val: sc.at_risk_formatted, col: '#ef4444' },
      ];
      tiles.forEach((t, i) => {
        const x = 56 + i * 372;
        ctx.fillStyle = 'rgba(255,255,255,0.06)';
        ctx.fillRect(x, 148, 344, 112);
        ctx.strokeStyle = 'rgba(255,255,255,0.14)';
        ctx.lineWidth = 1.5;
        ctx.strokeRect(x, 148, 344, 112);
        ctx.fillStyle = '#94a3b8';
        ctx.font = '700 15px system-ui, sans-serif';
        ctx.fillText(t.lbl, x + 20, 182);
        ctx.fillStyle = t.col;
        ctx.font = '800 34px system-ui, sans-serif';
        ctx.fillText(String(t.val || '--').slice(0, 18), x + 20, 234);
      });

      // #1 Leak & Today's Action Box
      ctx.fillStyle = 'rgba(239,68,68,0.12)';
      ctx.fillRect(56, 286, 1088, 114);
      ctx.fillStyle = '#ef4444';
      ctx.fillRect(56, 286, 6, 114);
      ctx.fillStyle = '#fca5a5';
      ctx.font = '700 15px system-ui, sans-serif';
      ctx.fillText(isHi ? '#1 सबसे बड़ा नुकसान' : '#1 TOP PRIORITY LEAK', 80, 318);
      ctx.fillStyle = '#ffffff';
      ctx.font = '700 23px system-ui, sans-serif';
      ctx.fillText(String(isHi ? sc.leak_headline_hi : sc.leak_headline_en).slice(0, 74), 80, 356);
      ctx.fillStyle = '#cbd5e1';
      ctx.font = '600 16px system-ui, sans-serif';
      ctx.fillText(String(isHi ? sc.top_kpi_hi : sc.top_kpi_en).slice(0, 88), 80, 386);

      ctx.fillStyle = 'rgba(16,185,129,0.12)';
      ctx.fillRect(56, 422, 1088, 116);
      ctx.fillStyle = '#10b981';
      ctx.fillRect(56, 422, 6, 116);
      ctx.fillStyle = '#6ee7b7';
      ctx.font = '700 15px system-ui, sans-serif';
      ctx.fillText(isHi ? 'आज का #1 एक्शन और अर्ली-वॉर्निंग स्टेटस' : "TODAY'S #1 ACTION & EARLY-WARNING RADAR", 80, 454);
      ctx.fillStyle = '#ffffff';
      ctx.font = '700 22px system-ui, sans-serif';
      ctx.fillText(String(isHi ? sc.action_hi : sc.action_en).slice(0, 78), 80, 492);
      ctx.fillStyle = '#cbd5e1';
      ctx.font = '600 16px system-ui, sans-serif';
      ctx.fillText(`📡 ${String(isHi ? sc.radar_note_hi : sc.radar_note_en).slice(0, 92)}`, 80, 522);

      // Footer
      ctx.fillStyle = '#64748b';
      ctx.font = '600 15px system-ui, sans-serif';
      ctx.fillText('Generated deterministically by DataX-Ray · Zero Hallucination · PII-Free Share Card', 56, 590);

      const link = document.createElement('a');
      link.download = `DataXRay_Brief_${(appState.activeRunId || 'report').replace(/[^A-Za-z0-9_-]/g, '_')}.png`;
      link.href = canvas.toDataURL('image/png');
      link.click();
      showToast(isHi ? 'शेयर कार्ड PNG डाउनलोड हो गया!' : 'PII-free Share Card PNG downloaded!', 'success');
    }

