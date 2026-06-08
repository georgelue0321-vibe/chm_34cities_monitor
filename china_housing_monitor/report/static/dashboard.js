let cityRadialScoreChart = null;
let nationalRadialChart = null;
let landedRadialChart = null;

let nbsIndexChart = null;
let transactionChart = null;
let scoreHistoryChart = null;
let listingsChart = null;
let priceChart = null;

function getDashboardTheme() {
    const isLight = document.documentElement.getAttribute('data-theme') === 'light';
    return {
        isLight,
        // Status badge (light: darker text for 4.5:1+ contrast)
        statusStrong: isLight ? 'bg-emerald-100 text-emerald-800 border border-emerald-300' : 'bg-emerald-950 text-emerald-400 border border-emerald-900',
        statusResonance: isLight ? 'bg-blue-100 text-blue-800 border border-blue-300' : 'bg-slate-800 text-slate-300 border border-slate-700',
        statusObserve: isLight ? 'bg-slate-200 text-slate-800 border border-slate-300' : 'bg-slate-800 text-slate-400 border border-slate-700',
        statusPolicy: isLight ? 'bg-amber-100 text-amber-800 border border-amber-300' : 'bg-amber-950 text-amber-400 border border-amber-900',
        statusDown: isLight ? 'bg-slate-200 text-slate-700 border border-slate-300' : 'bg-slate-900 text-slate-600 border border-slate-800',
        // Radial chart
        trackBg: isLight ? '#f1f5f9' : '#111827',
        gradientShade: isLight ? 'light' : 'dark',
        // Warning cards
        warnDefault: isLight ? 'border-slate-300 bg-slate-50 text-slate-700' : 'border-slate-800/60 bg-slate-950/60 text-slate-300',
        warnDanger: isLight ? 'border-rose-300 bg-rose-50 text-rose-700' : 'border-rose-800/60 bg-rose-950/30 text-rose-300',
        warnCaution: isLight ? 'border-amber-300 bg-amber-50 text-amber-700' : 'border-amber-800/60 bg-amber-950/30 text-amber-300',
        warnPositive: isLight ? 'border-emerald-300 bg-emerald-50 text-emerald-700' : 'border-emerald-800/60 bg-emerald-950/30 text-emerald-300',
        warnTitle: isLight ? 'text-slate-900' : 'text-white',
        warnEmpty: isLight ? 'bg-emerald-50 border border-emerald-300 text-emerald-700' : 'bg-emerald-950/30 border border-emerald-800/50 text-emerald-300',
        warnEmptyIcon: isLight ? 'text-emerald-500' : 'text-emerald-400',
        warnDesc: isLight ? 'text-slate-600' : 'text-slate-300',
        // Timeline
        stageDefault: isLight ? 'bg-slate-200 border-slate-300 text-slate-700' : 'bg-slate-900 border-slate-800 text-slate-500',
        stageComplete: isLight ? 'bg-emerald-100 text-emerald-800 border-emerald-300' : 'bg-emerald-950 text-emerald-400 border-emerald-900',
        stageSign: isLight ? 'bg-blue-100 text-blue-800 border-blue-300' : 'bg-slate-800 text-slate-300 border-slate-700',
        stagePublic: isLight ? 'bg-slate-200 text-slate-800 border-slate-300' : 'bg-slate-800 text-slate-400 border-slate-700',
        stageBid: isLight ? 'bg-amber-100 text-amber-800 border-amber-300' : 'bg-amber-950 text-amber-400 border-amber-900',
        timelineTitle: isLight ? 'text-slate-900' : 'text-white',
        timelineMuted: isLight ? 'text-slate-500' : 'text-slate-600',
        timelineGrid: isLight ? 'text-slate-500' : 'text-slate-600',
        timelineDate: isLight ? 'text-slate-500' : 'text-slate-600',
        timelineCard: isLight ? 'bg-white border-slate-200 hover:border-slate-300' : 'surface-inset border-slate-800/60 hover:border-slate-700',
        // Evidence grade
        gradeAB: isLight ? 'grade-ab' : 'bg-emerald-950 text-emerald-400 border-emerald-900',
        gradeC: isLight ? 'grade-c' : 'bg-amber-950 text-amber-400 border-amber-900',
        gradeDE: isLight ? 'grade-de' : 'bg-rose-950 text-rose-400 border-rose-900',
        // Factor bar
        factorBarBg: isLight ? 'factor-bar-bg' : 'bg-slate-950',
        factorScoreText: isLight ? 'factor-score-text' : 'text-white',
        // Interpretation text
        interpText: isLight ? 'text-slate-600' : 'text-slate-300',
        interpMuted: isLight ? 'text-slate-500' : 'text-slate-500',
        // Tooltip content text
        tooltipContentText: isLight ? 'text-slate-700' : 'text-slate-300',
        tooltipContentMuted: isLight ? 'text-slate-500' : 'text-slate-400',
    };
}

function renderCityDashboard(cityId) {
    const db = window.MONITOR_DB;
    const city = db.cities[cityId];

    document.getElementById('cityNameHeader').innerText = city.name + "市房产评估终端";
    document.getElementById('cityLevelBadge').innerText = city.level === "二线核心" ? "二线核心城" : city.level + "核心城";
    const consensusEl = document.getElementById('cityConsensusStr');
    if (city.consensus_institution) {
        consensusEl.innerHTML = `<span class="text-slate-500 text-[12px] font-medium">[${city.consensus_institution}]</span> ${city.consensus}`;
    } else {
        consensusEl.innerText = city.consensus;
    }

    document.getElementById('paramPositiveDrivers').innerText = city.positive_drivers || "无明显拉动项";
    document.getElementById('paramNegativeDrivers').innerText = city.negative_drivers || "无明显拖累项";

    const capReasonContainer = document.getElementById('capReasonContainer');
    if (city.cap_reason) {
        document.getElementById('paramCapReason').innerText = city.cap_reason;
        capReasonContainer.classList.remove('hidden');
    } else {
        capReasonContainer.classList.add('hidden');
    }

    const statusBadge = document.getElementById('cityStatusBadge');
    statusBadge.innerText = city.bottom_status;
    const dt = getDashboardTheme();
    let statusClass = '';
    if (city.bottom_status === '底数据强信号观察') statusClass = dt.statusStrong;
    else if (city.bottom_status === '政策价格共振') statusClass = dt.statusResonance;
    else if (city.bottom_status === '价格止跌观察') statusClass = dt.statusObserve;
    else if (city.bottom_status === '政策底观察') statusClass = dt.statusPolicy;
    else statusClass = dt.statusDown;
    statusBadge.className = `px-2.5 py-1 rounded-md text-[12px] font-bold ` + statusClass;

    document.getElementById('paramStatus').innerText = city.bottom_status;

    const statusExplanations = {
        '下跌通道': '价格持续下跌，尚未出现止跌信号，观望为主',
        '政策底观察': '政策端已出手托底，但价格尚未企稳，需等待传导',
        '价格止跌观察': '价格跌幅收窄或环比转正，止跌迹象初现，仍需确认',
        '政策价格共振': '政策托底+价格企稳双重信号，底部特征较明显',
        '底数据强信号观察': '数据不完整但已有强信号，需补充验证后确认'
    };
    document.getElementById('tooltipStatusText').innerText = statusExplanations[city.bottom_status] || '综合研判当前所处阶段';

    const riskEl = document.getElementById('paramRisk');
    riskEl.innerText = city.risk_level;

    const riskExplanations = {
        '极高风险': '数据严重缺失或信号矛盾，参考价值有限',
        '高风险': '政策底已现但价格未稳，不确定性较大',
        '中高风险': '信号初现但验证不足，需持续跟踪',
        '中等风险': '多项信号趋同，风险可控但仍需观察',
        '较低风险': '信号较强且数据较全，底部特征明显',
        '低风险': '数据完整信号强劲，确认度高'
    };
    document.getElementById('tooltipRiskText').innerText = riskExplanations[city.risk_level] || '数据缺失与信号不确定性的综合评估';

    if (city.risk_level === "极高风险") riskEl.className = "text-rose-500 text-sm font-extrabold mt-1.5 block";
    else if (city.risk_level === "高风险") riskEl.className = "text-red-400 text-sm font-extrabold mt-1.5 block";
    else if (city.risk_level === "中等风险") riskEl.className = "text-amber-400 text-sm font-extrabold mt-1.5 block";
    else if (city.risk_level === "较低风险") riskEl.className = "text-blue-400 text-sm font-extrabold mt-1.5 block";
    else riskEl.className = "text-emerald-400 text-sm font-extrabold mt-1.5 block";

    document.getElementById('paramStrength').innerText = city.signal_strength;

    const strengthExplanations = {
        '极强': '三因子得分均高，信号高度一致，可信度最高',
        '强': '多数因子得分较高，信号较为集中',
        '中等': '因子得分分化，部分信号较强部分偏弱',
        '弱': '多数因子得分偏低，信号分散',
        '极弱': '三因子得分均低，缺乏有效支撑信号'
    };
    document.getElementById('tooltipStrengthText').innerText = strengthExplanations[city.signal_strength] || '三因子得分的集中度与一致性';

    const q = city.quality_stats;
    document.getElementById('paramCredibility').innerText = `价格指数: ${q.official_price_ratio}%, 缺失: ${q.missing_ratio}%`;

    const officialRatio = q.official_price_ratio;
    const missingRatio = q.missing_ratio;
    let credibilityExplanation = '';
    if (missingRatio >= 20) credibilityExplanation = `缺失数据达${missingRatio}%，评分可信度受限，仅作参考`;
    else if (officialRatio >= 80) credibilityExplanation = `官方数据占比${officialRatio}%，数据质量高，可信度强`;
    else if (officialRatio >= 50) credibilityExplanation = `官方数据占比${officialRatio}%，数据质量中等`;
    else credibilityExplanation = `官方数据占比仅${officialRatio}%，估算数据较多，谨慎参考`;
    document.getElementById('tooltipCredibilityText').innerText = credibilityExplanation;

    var scoreOptions = {
        series: [city.bottom_score],
        chart: { type: 'radialBar', width: '100%', height: '100%', sparkline: { enabled: true } },
        plotOptions: {
            radialBar: {
                hollow: { size: '65%' },
                track: { background: dt.trackBg, strokeWidth: '100%' },
                dataLabels: { name: { show: false }, value: { show: false } }
            }
        },
        fill: {
            type: 'gradient',
            gradient: {
                shade: dt.gradientShade, type: 'horizontal',
                gradientToColors: [city.bottom_score >= 75 ? '#10b981' : (city.bottom_score >= 60 ? '#6366f1' : '#f59e0b')],
                stops: [0, 100]
            }
        },
        stroke: { lineCap: 'round' },
        colors: [city.bottom_score >= 75 ? '#3b82f6' : (city.bottom_score >= 60 ? '#a855f7' : '#ef4444')]
    };

    try { if (cityRadialScoreChart) cityRadialScoreChart.destroy(); } catch (e) {}
    try {
        cityRadialScoreChart = new ApexCharts(document.querySelector("#cityRadialScoreChart"), scoreOptions);
        cityRadialScoreChart.render();
    } catch (e) { console.error("Error rendering City Radial Score dial:", e); }
    document.getElementById('cityScoreStr').innerText = city.bottom_score;
    document.getElementById('tooltipScoreText').innerText = `底部信号: ${city.bottom_score}分`;

    const factorsContainer = document.getElementById('factorsBreakdownContainer');
    factorsContainer.innerHTML = '';
    const factorDefs = [
        { key: "price", label: "S_Price 价格", color: "bg-blue-500" },
        { key: "storage", label: "S_Storage 收储", color: "bg-amber-500" },
        { key: "pboc", label: "S_PBOC 资金", color: "bg-emerald-500" }
    ];
    factorDefs.forEach(f => {
        let val = city.factors[f.key];
        if (f.key === 'storage' && (val === undefined || val === null)) val = city.factors['policy'];
        if (val === undefined || val === null) val = 0;
        let scoreText = typeof val === 'number' ? val.toFixed(1) : "-";
        const item = document.createElement('div');
        item.innerHTML = `
            <div class="flex items-center gap-2 text-[12px]">
                <span class="text-slate-400 w-24 flex-shrink-0 truncate">${f.label}</span>
                <div class="flex-grow h-1.5 ${dt.factorBarBg} rounded-full overflow-hidden">
                    <div class="h-full ${f.color} rounded-full" style="width: ${val}%"></div>
                </div>
                <span class="${dt.factorScoreText} font-bold w-10 text-right flex-shrink-0">${scoreText}</span>
            </div>
        `;
        factorsContainer.appendChild(item);
    });

    const interp = city.signal_interpretation || {};
    const rankEl = document.getElementById('interpRank');
    if (rankEl) rankEl.innerText = interp.rank_str || "";

    const gradeBadge = document.getElementById('interpGrade');
    const grade = interp.evidence_grade || "E";
    gradeBadge.innerText = "证据" + grade;
    let gradeClass = '';
    if (grade === 'A' || grade === 'B') gradeClass = dt.gradeAB;
    else if (grade === 'C') gradeClass = dt.gradeC;
    else gradeClass = dt.gradeDE;
    gradeBadge.className = 'px-1.5 py-0.5 rounded-md text-[11px] font-bold border ' + gradeClass;

    const positivesEl = document.getElementById('interpPositives');
    positivesEl.innerHTML = '';
    (interp.positives || []).forEach(p => {
        const item = document.createElement('p');
        item.className = `${dt.interpText} text-[13px] font-medium flex items-start gap-1.5`;
        item.innerHTML = `<i class="fas fa-check text-emerald-500 text-[11px] mt-0.5 flex-shrink-0"></i><span>${p}</span>`;
        positivesEl.appendChild(item);
    });

    const negativesEl = document.getElementById('interpNegatives');
    negativesEl.innerHTML = '';
    (interp.negatives || []).forEach(n => {
        const item = document.createElement('p');
        item.className = `${dt.interpText} text-[13px] font-medium flex items-start gap-1.5`;
        item.innerHTML = `<i class="fas fa-times text-rose-500 text-[11px] mt-0.5 flex-shrink-0"></i><span>${n}</span>`;
        negativesEl.appendChild(item);
    });

    const nextStepsEl = document.getElementById('interpNextSteps');
    nextStepsEl.innerHTML = '';
    (interp.next_steps || []).forEach((s, i) => {
        const item = document.createElement('p');
        item.className = `${dt.interpText} text-[13px] font-medium flex items-start gap-2`;
        item.innerHTML = `<span class="${dt.interpMuted} font-bold text-sm flex-shrink-0">${i + 1}.</span><span>${s}</span>`;
        nextStepsEl.appendChild(item);
    });

    const warningsEl = document.getElementById('warningsContainer');
    warningsEl.innerHTML = '';
    if (city.warnings.length === 0) {
        warningsEl.innerHTML = `
            <div class="flex items-center gap-2.5 p-3.5 rounded-lg ${dt.warnEmpty} text-sm font-medium leading-relaxed">
                <i class="fas fa-check-circle text-sm flex-shrink-0 ${dt.warnEmptyIcon}"></i>
                <span class="${dt.warnDesc}">数据流匹配稳健。本月指标流正常，成交、价格底座与收储执行未见明显拟测失真。</span>
            </div>
        `;
    } else {
        city.warnings.forEach(w => {
            let borderClass = dt.warnDefault;
            let iconClass = 'fa-info-circle text-slate-400';
            if (w.type === 'warning') { borderClass = dt.warnDanger; iconClass = 'fa-ban text-rose-400'; }
            else if (w.type === 'caution') { borderClass = dt.warnCaution; iconClass = 'fa-exclamation-triangle text-amber-400'; }
            else if (w.type === 'positive') { borderClass = dt.warnPositive; iconClass = 'fa-check-circle text-emerald-400'; }
            const card = document.createElement('div');
            card.className = `p-3.5 rounded-lg border flex gap-2.5 leading-normal text-sm ${borderClass}`;
            card.innerHTML = `
                <i class="fas ${iconClass} text-sm flex-shrink-0 mt-0.5"></i>
                <div>
                    <strong class="font-semibold ${dt.warnTitle} block mb-0.5">${w.title}</strong>
                    <span class="${dt.warnDesc}">${w.desc}</span>
                </div>
            `;
            warningsEl.appendChild(card);
        });
    }

    try {
        const timelineEl = document.getElementById('storageEventsTimeline');
        if (timelineEl) {
            timelineEl.innerHTML = '';
            const history = city.storage_execution_history || [];
            if (history.length === 0) {
                timelineEl.innerHTML = `
                    <div class="flex flex-col items-center justify-center p-6 text-center surface-inset border border-slate-800/60 rounded-lg min-h-[160px]">
                        <i class="fas fa-search-location text-xl text-slate-600 mb-2.5"></i>
                        <h4 class="text-slate-300 text-sm font-semibold mb-1.5">未见真实的国企收储签约或公示</h4>
                        <p class="text-slate-500 text-[12px] max-w-xs leading-relaxed">该市尚无保障房再贷款签约、公示或改造配租落地，资金防线尚未建立，房价有继续寻底阴跌压力。</p>
                    </div>
                `;
            } else {
                history.forEach(st => {
                    const isValidUrl = st.source_url && st.source_url.startsWith('http');
                    const linkHtml = isValidUrl ? `
                        <a href="${st.source_url}" target="_blank" class="text-slate-400 hover:text-slate-300 font-medium transition-all flex items-center gap-1 hover:underline ml-auto flex-shrink-0 text-[12px]">
                            信源公示 <i class="fas fa-external-link-alt text-[11px]"></i>
                        </a>` : (st.source_url ? `
                        <span class="text-slate-500 text-[12px] ml-auto flex-shrink-0" title="${st.source_url}">
                            <i class="fas fa-file-alt text-[11px] mr-0.5"></i>${st.source_url}
                        </span>` : '');
                    const stageWeights = { "政策表态": 10, "房源征集": 25, "正式招标": 45, "成交公示": 70, "签约收购": 90, "改造完成/配租配售": 100 };
                    const sWeight = stageWeights[st.stage] || 0;
                    let stageBadgeColor = dt.stageDefault;
                    if (st.stage === '改造完成/配租配售') stageBadgeColor = dt.stageComplete;
                    else if (st.stage === '签约收购') stageBadgeColor = dt.stageSign;
                    else if (st.stage === '成交公示') stageBadgeColor = dt.stagePublic;
                    else if (st.stage === '正式招标') stageBadgeColor = dt.stageBid;
                    const item = document.createElement('div');
                    item.className = `${dt.timelineCard} border rounded-lg p-4 transition-all duration-150 flex flex-col gap-2`;
                    item.innerHTML = `
                        <div class="flex items-center gap-2">
                            <span class="px-2.5 py-0.5 rounded text-[11px] font-semibold border ${stageBadgeColor}">${st.stage} (权重:${sWeight})</span>
                            <span class="${dt.timelineDate} text-[12px] font-medium"><i class="far fa-calendar-alt mr-1"></i>${st.date}</span>
                            ${linkHtml}
                        </div>
                        <h4 class="${dt.timelineTitle} text-sm font-semibold">${st.title}</h4>
                        <p class="${dt.timelineMuted} text-[12px] leading-relaxed">${st.details}</p>
                        <div class="grid grid-cols-2 md:grid-cols-4 gap-2 border-t border-slate-800 pt-2.5 mt-1 text-[12px] font-medium ${dt.timelineGrid}">
                            <div>收储套数: <span class="${dt.timelineTitle} font-semibold block mt-0.5">${st.units_acquired > 0 ? st.units_acquired + " 套" : "征集/计划"}</span></div>
                            <div>收储单价: <span class="${dt.timelineTitle} font-semibold block mt-0.5">${st.price_sqm > 0 ? st.price_sqm + " 元/㎡" : "待招标评估"}</span></div>
                            <div>折扣率(折二手价): <span class="text-emerald-500 font-semibold block mt-0.5">${st.discount > 0 ? (st.discount * 10).toFixed(1) + " 折" : "合理评估折价"}</span></div>
                            <div>资金通道: <span class="${dt.timelineMuted} font-semibold block mt-0.5">${st.funding_type}</span></div>
                        </div>
                    `;
                    timelineEl.appendChild(item);
                });
            }
        }
    } catch (e) { console.error("Error rendering storage events timeline:", e); }

    try { renderNbsIndexChart(city.price_index_history); } catch (e) { console.error("Error rendering NBS Index Chart:", e); }
    try { renderTransactionChart(city.transaction_history, city); } catch (e) { console.error("Error rendering Transaction Chart:", e); }
    try { renderScoreHistoryChart(city.score_history); } catch (e) { console.error("Error rendering Score History Chart:", e); }
    try { renderScrapedCharts(city.market_history, cityId, city); } catch (e) { console.error("Error rendering Scraped Charts:", e); }
}
