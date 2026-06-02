function renderRankings(rankings, activeCityId) {
    const container = document.getElementById('rankingsContainer');
    container.innerHTML = '';

    rankings.forEach((item, index) => {
        const isSelected = item.city_id === activeCityId;
        const row = document.createElement('div');
        row.onclick = () => onCityChange(item.city_id, false);

        const selectedClass = "bg-slate-800/80 border-slate-600 text-white shadow-[0_0_12px_rgba(59,130,246,0.1)]";
        const unselectedClass = "surface-inset border-slate-800/60 hover:border-slate-700 hover:bg-slate-800/50 text-slate-300";
        row.className = `p-3 rounded-lg border flex items-center justify-between cursor-pointer transition-all duration-150 ${isSelected ? selectedClass : unselectedClass}`;

        let rankBadge = '';
        if (index === 0) rankBadge = 'bg-rose-950 text-rose-400 border border-rose-900';
        else if (index === 1) rankBadge = 'bg-amber-950 text-amber-400 border border-amber-900';
        else if (index === 2) rankBadge = 'bg-slate-800 text-slate-300 border border-slate-700';
        else rankBadge = 'bg-slate-900 border border-slate-800 text-slate-600';

        let statusBadgeColor = '';
        if (item.status === '底数据强信号观察') statusBadgeColor = 'bg-emerald-950 text-emerald-400 border-emerald-900';
        else if (item.status === '政策价格共振') statusBadgeColor = 'bg-slate-800 text-slate-300 border-slate-700';
        else if (item.status === '价格止跌观察') statusBadgeColor = 'bg-slate-800 text-slate-400 border-slate-700';
        else if (item.status === '政策底观察') statusBadgeColor = 'bg-amber-950 text-amber-400 border-amber-900';
        else statusBadgeColor = 'bg-slate-900 text-slate-600 border-slate-800';

        const changeText = item.change > 0 ? `<span class="text-rose-500 text-[10px] font-medium ml-auto"><i class="fas fa-arrow-up"></i>+${item.change}</span>` :
                          (item.change < 0 ? `<span class="text-emerald-500 text-[10px] font-medium ml-auto"><i class="fas fa-arrow-down"></i>${item.change}</span>` : `<span class="text-slate-700 text-[10px] ml-auto">-</span>`);

        row.innerHTML = `
            <div class="flex items-center gap-2 w-full text-xs font-medium">
                <span class="w-5 h-5 rounded flex items-center justify-center text-[10px] font-semibold ${rankBadge} flex-shrink-0">${index + 1}</span>
                <div class="flex items-center gap-1.5 flex-wrap w-full">
                    <span class="text-slate-200 font-semibold text-xs">${item.name}</span>
                    <span class="text-slate-600">|</span>
                    <span class="text-white font-extrabold">${Number(item.score).toFixed(2)}</span>
                    <span class="text-slate-600">|</span>
                    <span class="px-1.5 py-0.5 rounded text-[8px] font-bold border ${statusBadgeColor}">${item.status}</span>
                    <span class="text-slate-600">|</span>
                    <span class="text-amber-400 font-bold text-[9px]">证据${item.evidence_grade}</span>
                    <span class="text-slate-600">|</span>
                    <span class="text-indigo-400 font-semibold text-[9px]">${item.highest_storage_stage}</span>
                </div>
                ${changeText}
            </div>
        `;
        container.appendChild(row);
    });
}
