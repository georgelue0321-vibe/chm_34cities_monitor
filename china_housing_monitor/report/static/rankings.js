function getRankingsTheme() {
    const isLight = document.documentElement.getAttribute('data-theme') === 'light';
    return {
        isLight,
        // Row states
        selected: isLight ? 'bg-blue-50 border-blue-400 text-slate-900 shadow-[0_0_12px_rgba(59,130,246,0.1)]' : 'bg-slate-800/80 border-slate-600 text-white shadow-[0_0_12px_rgba(59,130,246,0.1)]',
        unselected: isLight ? 'bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50 text-slate-700' : 'surface-inset border-slate-800/60 hover:border-slate-700 hover:bg-slate-800/50 text-slate-300',
        // Rank badges
        rank1: isLight ? 'bg-rose-100 text-rose-700 border border-rose-300' : 'bg-rose-950 text-rose-400 border border-rose-900',
        rank2: isLight ? 'bg-amber-100 text-amber-700 border border-amber-300' : 'bg-amber-950 text-amber-400 border border-amber-900',
        rank3: isLight ? 'bg-slate-200 text-slate-800 border border-slate-300' : 'bg-slate-800 text-slate-300 border border-slate-700',
        rankN: isLight ? 'bg-slate-100 border border-slate-300 text-slate-500' : 'bg-slate-900 border border-slate-800 text-slate-600',
        // Status badges
        statusStrong: isLight ? 'bg-emerald-100 text-emerald-800 border-emerald-300' : 'bg-emerald-950 text-emerald-400 border-emerald-900',
        statusResonance: isLight ? 'bg-blue-100 text-blue-800 border-blue-300' : 'bg-slate-800 text-slate-300 border-slate-700',
        statusObserve: isLight ? 'bg-slate-200 text-slate-800 border-slate-300' : 'bg-slate-800 text-slate-400 border-slate-700',
        statusPolicy: isLight ? 'bg-amber-100 text-amber-800 border-amber-300' : 'bg-amber-950 text-amber-400 border-amber-900',
        statusDown: isLight ? 'bg-slate-200 text-slate-600 border-slate-300' : 'bg-slate-900 text-slate-600 border-slate-800',
        // Text
        name: isLight ? 'text-slate-800' : 'text-slate-200',
        score: isLight ? 'text-slate-900' : 'text-white',
        divider: isLight ? 'text-slate-300' : 'text-slate-600',
        grade: isLight ? 'text-amber-600' : 'text-amber-400',
        stage: isLight ? 'text-indigo-600' : 'text-indigo-400',
        changeNeutral: isLight ? 'text-slate-400' : 'text-slate-700',
    };
}

function renderRankings(rankings, activeCityId) {
    const container = document.getElementById('rankingsContainer');
    container.innerHTML = '';
    const rt = getRankingsTheme();
    rankings.forEach((item, index) => {
        const isSelected = item.city_id === activeCityId;
        const row = document.createElement('div');
        row.onclick = () => onCityChange(item.city_id, false);
        row.className = `p-3 rounded-lg border flex items-center justify-between cursor-pointer transition-all duration-150 ${isSelected ? rt.selected : rt.unselected}`;

        let rankBadge = '';
        if (index === 0) rankBadge = rt.rank1;
        else if (index === 1) rankBadge = rt.rank2;
        else if (index === 2) rankBadge = rt.rank3;
        else rankBadge = rt.rankN;

        let statusBadgeColor = '';
        if (item.status === '底数据强信号观察') statusBadgeColor = rt.statusStrong;
        else if (item.status === '政策价格共振') statusBadgeColor = rt.statusResonance;
        else if (item.status === '价格止跌观察') statusBadgeColor = rt.statusObserve;
        else if (item.status === '政策底观察') statusBadgeColor = rt.statusPolicy;
        else statusBadgeColor = rt.statusDown;

        const changeText = item.change > 0 ? `<span class="text-rose-500 text-[12px] font-medium ml-auto"><i class="fas fa-arrow-up"></i>+${item.change}</span>` :
                          (item.change < 0 ? `<span class="text-emerald-500 text-[12px] font-medium ml-auto"><i class="fas fa-arrow-down"></i>${item.change}</span>` : `<span class="${rt.changeNeutral} text-[12px] ml-auto">-</span>`);
        row.innerHTML = `
            <div class="flex items-center gap-2 w-full text-sm font-medium">
                <span class="w-5 h-5 rounded flex items-center justify-center text-[12px] font-semibold ${rankBadge} flex-shrink-0">${index + 1}</span>
                <div class="flex items-center gap-1.5 flex-wrap w-full">
                    <span class="${rt.name} font-semibold text-sm">${item.name}</span>
                    <span class="${rt.divider}">|</span>
                    <span class="${rt.score} font-extrabold">${Number(item.score).toFixed(2)}</span>
                    <span class="${rt.divider}">|</span>
                    <span class="px-1.5 py-0.5 rounded text-[10px] font-bold border ${statusBadgeColor}">${item.status}</span>
                    <span class="${rt.divider}">|</span>
                    <span class="${rt.grade} font-bold text-[11px]">证据${item.evidence_grade}</span>
                    <span class="${rt.divider}">|</span>
                    <span class="${rt.stage} font-semibold text-[11px]">${item.highest_storage_stage}</span>
                </div>
                ${changeText}
            </div>
        `;
        container.appendChild(row);
    });
}
