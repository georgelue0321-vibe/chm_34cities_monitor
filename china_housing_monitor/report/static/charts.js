function getThemeColors() {
    const isLight = document.documentElement.getAttribute('data-theme') === 'light';
    return {
        isLight,
        gridBorder: isLight ? '#e2e8f0' : '#1e293b',
        axisLabel: isLight ? '#64748b' : '#475569',
        legendLabel: isLight ? '#475569' : '#64748b',
        annotationBorder: isLight ? '#cbd5e1' : '#334155',
        tooltipTheme: isLight ? 'light' : 'dark',
        line1: isLight ? '#475569' : '#94a3b8',
        line2: isLight ? '#94a3b8' : '#475569',
        tooltipBg: isLight ? '#ffffff' : undefined,
        tooltipBorder: isLight ? '#e2e8f0' : undefined,
        tooltipText: isLight ? '#0f172a' : undefined,
        tooltipMuted: isLight ? '#64748b' : '#94a3b8',
    };
}

function renderNbsIndexChart(history, range) {
    try {
        const effectiveRange = range || 'all';
        const filteredHistory = filterHistoryByRange(history, effectiveRange);
        currentNbsRange = effectiveRange;
        updateResetButtons('nbs', effectiveRange);
        const dates = filteredHistory.map(h => h.date);
        const resaleMom = history.map(h => h.resale_home_mom != null ? Number((h.resale_home_mom - 100).toFixed(1)) : null);
        const resaleYoy = history.map(h => h.resale_home_yoy != null ? Number((h.resale_home_yoy - 100).toFixed(1)) : null);
        const resaleMomRaw = history.map(h => h.resale_home_mom);
        const resaleYoyRaw = history.map(h => h.resale_home_yoy);
        const tc = getThemeColors();
        var options = {
            series: [
                { name: '环比偏离 (上月=100)', data: resaleMom },
                { name: '同比偏离 (上年同月=100)', data: resaleYoy }
            ],
            chart: { height: 200, type: 'line', toolbar: { show: false }, background: 'transparent', zoom: { enabled: false } },
            stroke: { width: [2, 1.5], curve: 'smooth' },
            colors: [tc.line1, tc.line2],
            labels: dates,
            markers: { size: 2, hover: { size: 4 } },
            xaxis: { type: 'category', labels: { style: { colors: tc.axisLabel, fontWeight: 500, fontSize: '11px' } }, axisBorder: { show: false }, axisTicks: { show: false } },
            yaxis: { labels: { style: { colors: tc.axisLabel, fontWeight: 500, fontSize: '11px' }, formatter: function (v) { if (v == null) return ''; return (v > 0 ? '+' : '') + v.toFixed(1) + '%'; } } },
            annotations: { yaxis: [{ y: 0, borderColor: tc.annotationBorder, strokeDashArray: 4 }] },
            tooltip: {
                theme: tc.tooltipTheme, style: { fontSize: '13px' },
                custom: function({ seriesIndex, dataPointIndex, w }) {
                    const date = dates[dataPointIndex];
                    const momRaw = resaleMomRaw[dataPointIndex]; const yoyRaw = resaleYoyRaw[dataPointIndex];
                    const momDev = resaleMom[dataPointIndex]; const yoyDev = resaleYoy[dataPointIndex];
                    const momColor = momDev > 0 ? '#10b981' : (momDev < 0 ? '#f87171' : tc.tooltipMuted);
                    const yoyColor = yoyDev > 0 ? '#10b981' : (yoyDev < 0 ? '#f87171' : tc.tooltipMuted);
                    const momLabel = momDev > 0 ? '价格上涨' : (momDev < 0 ? '价格下跌' : '价格持平');
                    const yoyLabel = yoyDev > 0 ? '价格上涨' : (yoyDev < 0 ? '价格下跌' : '价格持平');
                    const headColor = tc.isLight ? '#0f172a' : '#cbd5e1';
                    const labelColor = tc.isLight ? '#475569' : '#94a3b8';
                    return `<div class="px-2 py-1.5 text-[12px]">
                        <div class="font-semibold mb-1" style="color:${headColor}">${date}</div>
                        <div class="flex justify-between gap-4"><span style="color:${labelColor}">环比:</span><span style="color:${momColor}">${momRaw} (${momDev > 0 ? '+' : ''}${momDev}%) ${momLabel}</span></div>
                        <div class="flex justify-between gap-4"><span style="color:${labelColor}">同比:</span><span style="color:${yoyColor}">${yoyRaw} (${yoyDev > 0 ? '+' : ''}${yoyDev}%) ${yoyLabel}</span></div>
                    </div>`;
                }
            },
            grid: { borderColor: tc.gridBorder, strokeDashArray: 4, yaxis: { lines: { show: true } } },
            legend: { labels: { colors: tc.legendLabel }, fontSize: '12px' }
        };
        try { if (nbsIndexChart) nbsIndexChart.destroy(); } catch (e) {}
        nbsIndexChart = new ApexCharts(document.querySelector("#nbsIndexChart"), options);
        nbsIndexChart.render();
    } catch (err) { console.error("Error rendering NBS Index Chart:", err); }
}

function renderTransactionChart(history, city, range) {
    try {
        const container = document.querySelector("#transactionChart");
        if (!container) return;
        if (!city || !city.chart_visibility || !city.chart_visibility.transaction) {
            try { if (transactionChart) { transactionChart.destroy(); transactionChart = null; } } catch (e) {}
            container.innerHTML = `<div class="flex flex-col items-center justify-center h-full text-center p-4"><i class="fas fa-eye-slash text-slate-600 mb-2 text-lg"></i><span class="text-slate-400 text-[12px] font-medium leading-relaxed">本指标因有效数据点不足（少于 3 个有效点），已启动安全抑噪，不予绘制趋势曲线。</span></div>`;
            return;
        }
        container.innerHTML = '';
        const effectiveRange = range || 'all';
        const filteredHistory = filterHistoryByRange(history, effectiveRange);
        currentTxRange = effectiveRange;
        updateResetButtons('tx', effectiveRange);
        const dates = filteredHistory.map(h => h.date);
        const resaleUnits = history.map(h => { const v = h.resale_online_sign_units; return (v && v > 0) ? v : null; });
        const resaleArea = history.map(h => { const v = h.resale_sales_area; return (v && v > 0) ? v : null; });
        const tc = getThemeColors();
        var options = {
            series: [{ name: '二手房交易面积 (万㎡)', type: 'area', data: resaleArea }, { name: '二手住宅网签套数 (套)', type: 'line', data: resaleUnits }],
            chart: { height: 200, type: 'line', stacked: false, toolbar: { show: false }, background: 'transparent', zoom: { enabled: false } },
            stroke: { width: [1, 2], curve: 'smooth' },
            colors: [tc.line2, tc.line1],
            fill: { opacity: [0.05, 1], gradient: { inverseColors: false, shade: tc.isLight ? 'light' : 'dark', type: "vertical", stops: [0, 100] } },
            labels: dates, markers: { size: 2 },
            xaxis: { type: 'category', labels: { style: { colors: tc.axisLabel, fontWeight: 500, fontSize: '11px' } }, axisBorder: { show: false }, axisTicks: { show: false } },
            yaxis: [
                { title: { text: '交易面积 (万㎡)', style: { color: tc.legendLabel, fontWeight: 500, fontSize: '11px' } }, labels: { style: { colors: tc.axisLabel, fontWeight: 500, fontSize: '11px' } } },
                { opposite: true, title: { text: '网签套数 (套)', style: { color: tc.line1, fontWeight: 500, fontSize: '11px' } }, labels: { style: { colors: tc.legendLabel, fontWeight: 600, fontSize: '11px' } } }
            ],
            tooltip: { theme: tc.tooltipTheme, shared: true },
            grid: { borderColor: tc.gridBorder, strokeDashArray: 4, yaxis: { lines: { show: true } } },
            legend: { show: false }
        };
        try { if (transactionChart) transactionChart.destroy(); } catch (e) {}
        transactionChart = new ApexCharts(container, options);
        transactionChart.render();
    } catch (err) { console.error("Error in renderTransactionChart:", err); }
}

function renderScoreHistoryChart(history) {
    try {
        const dates = history.map(h => h.date);
        const scores = history.map(h => h.score);
        const tc = getThemeColors();
        var options = {
            series: [{ name: '底部信号指数 (Bottom Signal Score)', data: scores }],
            chart: { height: 160, type: 'area', toolbar: { show: false }, background: 'transparent' },
            stroke: { width: 2, curve: 'smooth' }, colors: [tc.line2],
            fill: { type: 'gradient', gradient: { shade: tc.isLight ? 'light' : 'dark', shadeIntensity: 1, opacityFrom: 0.1, opacityTo: 0.02, stops: [0, 100] } },
            labels: dates, markers: { size: 2, hover: { size: 4 } },
            xaxis: { type: 'category', labels: { style: { colors: tc.legendLabel, fontWeight: 600, fontSize: '11px' } }, axisBorder: { show: false }, axisTicks: { show: false } },
            yaxis: { max: 100, min: 0, labels: { style: { colors: tc.legendLabel, fontWeight: 600, fontSize: '11px' } } },
            tooltip: { theme: tc.tooltipTheme },
            grid: { borderColor: tc.gridBorder, strokeDashArray: 4, yaxis: { lines: { show: true } } },
            legend: { show: false }
        };
        try { if (scoreHistoryChart) scoreHistoryChart.destroy(); } catch (e) {}
        scoreHistoryChart = new ApexCharts(document.querySelector("#scoreHistoryChart"), options);
        scoreHistoryChart.render();
    } catch (err) { console.error("Error rendering Score History Chart:", err); }
}

function renderScrapedCharts(history, cityId, city) {
    try {
        const dates = history.map(h => h.date);
        const listings = history.map(h => h.listings);
        const prices = history.map(h => h.price_sqm);
        const isListingsSuppressed = !city || !city.chart_visibility || !city.chart_visibility.listings;
        const isPriceSuppressed = !city || !city.chart_visibility || !city.chart_visibility.price;
        const listingsContainer = document.querySelector("#listingsChart");
        const priceContainer = document.querySelector("#priceChart");
        const tc = getThemeColors();

        if (listingsContainer) {
            if (isListingsSuppressed) {
                try { if (listingsChart) { listingsChart.destroy(); listingsChart = null; } } catch (e) {}
                const officialLinks = { "sh": "http://www.fangdi.com.cn/", "cd": "https://zjj.chengdu.gov.cn/", "cq": "http://www.cq315house.com/", "wh": "http://fgj.wuhan.gov.cn/", "nj": "http://www.njhouse.com.cn/" };
                const oLink = officialLinks[cityId] || "https://www.stats.gov.cn/";
                listingsContainer.className = "w-full min-h-[120px] flex items-center justify-center surface-inset border border-slate-800/60 rounded-lg mt-2";
                listingsContainer.innerHTML = `<div class="flex flex-col items-center text-center p-4"><i class="fas fa-eye-slash text-slate-600 mb-2 text-lg"></i><span class="text-slate-400 text-[12px] font-medium leading-relaxed">本指标因有效数据点不足（少于 3 个有效点），已启动安全抑噪，不予绘制趋势曲线。</span><a href="${oLink}" target="_blank" rel="noopener noreferrer" class="text-blue-400 hover:text-blue-300 font-medium text-[12px] hover:underline flex items-center gap-1 mt-2">访问住建局大厅 <i class="fas fa-external-link-alt text-[10px]"></i></a></div>`;
            } else {
                listingsContainer.className = "h-36 w-full mt-2";
                listingsContainer.innerHTML = '';
                const listingsQualities = history.map(h => h.listings_status === 'estimated' ? 5 : 0);
                var lOptions = {
                    series: [{ name: '挂牌量 (套)', data: listings }],
                    chart: { height: 135, type: 'line', toolbar: { show: false } },
                    stroke: { width: 2.5, curve: 'smooth', dashArray: listingsQualities },
                    colors: [tc.isLight ? '#4f46e5' : '#6366f1'], labels: dates, markers: { size: 2 },
                    xaxis: { labels: { style: { colors: tc.legendLabel, fontSize: '10px' } } },
                    yaxis: { labels: { style: { colors: tc.legendLabel, fontSize: '10px' } } },
                    tooltip: { theme: tc.tooltipTheme },
                    grid: { borderColor: tc.gridBorder, strokeDashArray: 4 }
                };
                try { if (listingsChart) listingsChart.destroy(); } catch (e) {}
                listingsChart = new ApexCharts(listingsContainer, lOptions);
                listingsChart.render();
            }
        }

        if (priceContainer) {
            if (isPriceSuppressed) {
                try { if (priceChart) { priceChart.destroy(); priceChart = null; } } catch (e) {}
                priceContainer.className = "w-full min-h-[120px] flex items-center justify-center surface-inset border border-slate-800/60 rounded-lg mt-2";
                priceContainer.innerHTML = `<div class="flex flex-col items-center text-center p-4"><i class="fas fa-eye-slash text-slate-600 mb-2 text-lg"></i><span class="text-slate-400 text-[12px] font-medium leading-relaxed">本指标因有效数据点不足（少于 3 个有效点），已启动安全抑噪，不予绘制趋势曲线。</span></div>`;
            } else {
                priceContainer.className = "h-36 w-full mt-2";
                priceContainer.innerHTML = '';
                const priceQualities = history.map(h => h.price_status === 'estimated' ? 5 : 0);
                var pOptions = {
                    series: [{ name: '挂牌均价 (元/㎡)', data: prices }],
                    chart: { height: 135, type: 'line', toolbar: { show: false } },
                    stroke: { width: 2, curve: 'smooth', dashArray: priceQualities },
                    colors: [tc.line2], labels: dates, markers: { size: 2 },
                    xaxis: { labels: { style: { colors: tc.axisLabel, fontSize: '10px' } } },
                    yaxis: { labels: { style: { colors: tc.axisLabel, fontSize: '10px' } } },
                    tooltip: { theme: tc.tooltipTheme },
                    grid: { borderColor: tc.gridBorder, strokeDashArray: 4 }
                };
                try { if (priceChart) priceChart.destroy(); } catch (e) {}
                priceChart = new ApexCharts(priceContainer, pOptions);
                priceChart.render();
            }
        }
    } catch (err) { console.error("Error in renderScrapedCharts:", err); }
}

function rerenderChartsForTheme() {
    const db = window.MONITOR_DB;
    if (!db) return;
    const cityId = localStorage.getItem('selected_city') || 'cd';
    const city = db.cities[cityId];
    if (!city) return;
    try { renderNbsIndexChart(city.price_index_history); } catch (e) {}
    try { renderTransactionChart(city.transaction_history, city); } catch (e) {}
    try { renderScoreHistoryChart(city.score_history); } catch (e) {}
    try { renderScrapedCharts(city.market_history, cityId, city); } catch (e) {}
    try { rerenderMapForTheme(); } catch (e) {}
}

let currentNbsRange = 'all';
let currentTxRange = 'all';

function setChartRange(chart, range) {
    if (chart === 'nbs') {
        currentNbsRange = range;
        const db = window.MONITOR_DB;
        const cityId = localStorage.getItem('selected_city') || 'cd';
        const city = db.cities[cityId];
        if (city) renderNbsIndexChart(city.price_index_history, range);
    } else {
        currentTxRange = range;
        const db = window.MONITOR_DB;
        const cityId = localStorage.getItem('selected_city') || 'cd';
        const city = db.cities[cityId];
        if (city) renderTransactionChart(city.transaction_history, city, range);
    }
}

function resetChartRange(chart) {
    setChartRange(chart, 'all');
    const btnClass = chart === 'nbs' ? '.nbs-reset-btn' : '.tx-reset-btn';
    document.querySelectorAll(btnClass).forEach(btn => btn.classList.add('hidden'));
}

function updateResetButtons(chart, range) {
    const btnClass = chart === 'nbs' ? '.nbs-reset-btn' : '.tx-reset-btn';
    if (range === 'all') {
        document.querySelectorAll(btnClass).forEach(btn => btn.classList.add('hidden'));
    } else {
        document.querySelectorAll(btnClass).forEach(btn => btn.classList.remove('hidden'));
    }
}

function filterHistoryByRange(history, range) {
    if (range === 'all' || !history) return history;
    const months = range === '1y' ? 12 : 12;
    const seen = new Map();
    for (const h of history) {
        if (h.date && !seen.has(h.date)) {
            seen.set(h.date, h);
        }
    }
    const unique = Array.from(seen.values());
    return unique.slice(-months);
}
