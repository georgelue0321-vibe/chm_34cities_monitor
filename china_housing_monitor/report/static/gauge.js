function renderNationalGauge(pboc) {
    // 1. Official Balance Progress Bar
    var officialPct = pboc.pboc_official_percentage;
    var officialBar = document.getElementById('nationalProgressBar');
    if (officialBar) {
        var scaledWidth = Math.min(100, Math.max(3, Math.sqrt(officialPct) * 6));
        officialBar.style.width = scaledWidth + '%';
    }

    var pctEl = document.getElementById('nationalPercentageStr');
    if (pctEl) pctEl.innerText = officialPct.toFixed(1) + "%";

    var balanceEl = document.getElementById('pbocBalanceStr');
    if (balanceEl) balanceEl.innerText = pboc.pboc_official_latest.toFixed(1) + " 亿";

    // 2. Project Landed Progress Bar
    var landedPct = Number((pboc.pboc_implied_landed / 3000 * 100).toFixed(2));
    var landedBar = document.getElementById('landedProgressBar');
    if (landedBar) {
        var scaledWidth2 = Math.min(100, Math.max(3, Math.sqrt(landedPct) * 6));
        landedBar.style.width = scaledWidth2 + '%';
    }

    var landedPctEl = document.getElementById('landedPercentageStr');
    if (landedPctEl) landedPctEl.innerText = landedPct.toFixed(2) + "%";

    var landedStrEl = document.getElementById('pbocLandedStr');
    if (landedStrEl) landedStrEl.innerText = pboc.pboc_implied_landed.toFixed(2) + " 亿";

    // 3. Metadata
    var dateEl = document.getElementById('pbocOfficialDateStr');
    if (dateEl) dateEl.innerText = "数据截至 " + pboc.pboc_official_date;

    if (!pboc.pboc_is_stale && pboc.quarter_increase > 0) {
        var qiEl = document.getElementById('pbocQuarterIncreaseStr');
        if (qiEl) qiEl.innerText = "+" + pboc.quarter_increase.toFixed(1) + " 亿";
    }
    // Stale note for quarter increase
    var staleNote = document.getElementById('pbocStaleNote');
    if (staleNote) {
        if (pboc.pboc_is_stale) {
            staleNote.classList.remove('hidden');
            staleNote.innerText = "数据冻结" + (pboc.pboc_stale_months > 0 ? pboc.pboc_stale_months + "月" : "");
        } else {
            staleNote.classList.add('hidden');
        }
    }
    var acEl = document.getElementById('pbocActiveCitiesStr');
    if (acEl) acEl.innerText = pboc.active_cities_count + " 城";
    // Ratio bar for active cities (out of 34 total)
    var ratioBar = document.getElementById('activeCitiesRatioBar');
    if (ratioBar) {
        var ratio = Math.min(100, (pboc.active_cities_count / 34) * 100);
        ratioBar.style.width = ratio.toFixed(0) + '%';
    }
    var ratioStr = document.getElementById('activeCitiesRatioStr');
    if (ratioStr) {
        ratioStr.innerText = (pboc.active_cities_count / 34 * 100).toFixed(0) + '%';
    }
    var crEl = document.getElementById('pbocConversionRateStr');
    if (crEl) crEl.innerText = pboc.units_acquired ? (pboc.units_acquired.toLocaleString() + " 套") : "-";
}
