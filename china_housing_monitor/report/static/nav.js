function toggleNavMobile(event) {
    const container = document.getElementById('nav-container');
    if (!container) return;
    const isToggleBtn = event.target.closest('#toggle-all-cities-btn');
    const isCityBtn = event.target.closest('[id^="nav-btn-"]');
    if (!isToggleBtn && isCityBtn) return;
    container.classList.toggle('is-expanded');
}

function onCityChange(cityId, scrollToTimeline = false) {
    cancelMapAutoClose();
    const drawer = document.getElementById('map-drawer');
    const isDrawerOpen = drawer && !drawer.classList.contains('-translate-x-full');
    if (isDrawerOpen) {
        const city = window.MONITOR_DB.cities[cityId];
        if (city) showToast(`已切换至${city.name}市，关闭地图后即可查看评估详情`);
    }
    localStorage.setItem('selected_city', cityId);
    updateNavButtons(cityId);
    try { renderRankings(window.MONITOR_DB.rankings, cityId); } catch (err) { console.error("Error rendering rankings:", err); }
    try { renderCityDashboard(cityId); } catch (err) { console.error("Error rendering city dashboard:", err); }
    const container = document.getElementById('nav-container');
    if (container) container.classList.remove('is-expanded');
    if (scrollToTimeline) {
        setTimeout(() => { const el = document.getElementById('storageEventsTimeline'); if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' }); }, 100);
    }
}

function updateNavButtons(activeCityId) {
    const db = window.MONITOR_DB;
    const activeTagEl = document.getElementById('nav-active-city-tag');
    activeTagEl.innerHTML = '';
    const activeCity = db.cities[activeCityId];
    if (activeCity) {
        const tag = document.createElement('button');
        tag.className = 'nav-active-city px-3 py-1.5 text-sm rounded-lg border flex-shrink-0 flex items-center gap-1.5 active:scale-95 transition-all';
        tag.innerHTML = `<span>📍 ${activeCity.name}</span><span class="nav-score text-[11px] font-bold opacity-80">[${Number(activeCity.bottom_score).toFixed(1)}]</span>`;
        tag.onclick = (e) => { e.stopPropagation(); };
        activeTagEl.appendChild(tag);
    }

    const compactListEl = document.getElementById('nav-compact-list');
    compactListEl.innerHTML = '';
    const signedStages = ['签约收购', '成交公示', '改造完成/配租配售'];
    const storageCities = [];
    Object.keys(db.cities).forEach(cid => {
        const city = db.cities[cid];
        if (!city.storage_execution_history || city.storage_execution_history.length === 0) return;
        const hasSigned = city.storage_execution_history.some(e => signedStages.includes(e.stage));
        if (hasSigned) storageCities.push({ cid, city, score: Number(city.bottom_score) || 0 });
    });
    storageCities.sort((a, b) => b.score - a.score);
    storageCities.forEach(({ cid, city }) => {
        const btn = document.createElement('button');
        btn.id = `nav-btn-compact-${cid}`;
        btn.onclick = (e) => { e.stopPropagation(); onCityChange(cid, false); };
        const isAlsoActive = (cid === activeCityId);
        btn.className = `nav-storage-btn px-3 py-1.5 text-sm rounded-lg border flex-shrink-0 flex items-center gap-1.5 active:scale-95${isAlsoActive ? ' is-also-active' : ''}`;
        let html = `<span class="font-medium">${city.name}</span><span class="nav-score text-[11px] font-bold opacity-70">[${Number(city.bottom_score).toFixed(1)}]</span>`;
        html += `<span class="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.7)] animate-pulse"></span>`;
        btn.innerHTML = html;
        compactListEl.appendChild(btn);
    });

    const isLight = document.documentElement.getAttribute('data-theme') === 'light';
    const activeClass = isLight
        ? "px-3 py-1.5 text-sm font-bold rounded-lg border transition-all flex-shrink-0 flex items-center gap-1.5 nav-expanded-active cursor-pointer"
        : "px-3 py-1.5 text-sm font-bold rounded-lg border transition-all flex-shrink-0 flex items-center gap-1.5 bg-slate-800 text-white border-slate-500 cursor-pointer shadow-[0_0_8px_rgba(59,130,246,0.15)]";
    const inactiveClass = isLight
        ? "px-3 py-1.5 text-sm font-medium rounded-lg border transition-all flex-shrink-0 flex items-center gap-1.5 nav-expanded-inactive cursor-pointer"
        : "px-3 py-1.5 text-sm font-medium rounded-lg border transition-all flex-shrink-0 flex items-center gap-1.5 bg-slate-900 border-slate-800 text-slate-300 hover:text-white hover:border-slate-600 hover:bg-slate-800 active:scale-95 cursor-pointer";
    Object.keys(db.cities).forEach(cid => {
        const btnExpanded = document.getElementById(`nav-btn-expanded-${cid}`);
        if (btnExpanded) btnExpanded.className = (cid === activeCityId) ? activeClass : inactiveClass;
    });
}

function switchChartTab(tabId) {}

function openMethodologyModal() {
    const modal = document.getElementById('methodology-modal');
    if (modal) { modal.classList.remove('hidden'); modal.classList.add('flex'); document.body.classList.add('overflow-hidden'); switchMethodologyTab('tab-changelog'); }
}
function closeMethodologyModal() {
    const modal = document.getElementById('methodology-modal');
    if (modal) { modal.classList.add('hidden'); modal.classList.remove('flex'); document.body.classList.remove('overflow-hidden'); }
}
function switchMethodologyTab(tabId) {
    const tabs = ['tab-changelog', 'tab-formula', 'tab-statuses'];
    const isLight = document.documentElement.getAttribute('data-theme') === 'light';
    tabs.forEach(t => {
        const el = document.getElementById(t); if (el) el.classList.add('hidden');
        const btn = document.getElementById(`btn-${t}`);
        if (btn) btn.className = isLight
            ? "px-4 py-2.5 text-sm font-semibold border-b-2 border-transparent modal-tab-inactive transition-all cursor-pointer"
            : "px-4 py-2.5 text-sm font-semibold border-b-2 border-transparent text-slate-500 hover:text-slate-350 transition-all cursor-pointer";
    });
    const activeEl = document.getElementById(tabId); if (activeEl) activeEl.classList.remove('hidden');
    const activeBtn = document.getElementById(`btn-${tabId}`);
    if (activeBtn) activeBtn.className = isLight
        ? "px-4 py-2.5 text-sm font-bold border-b-2 modal-tab-active transition-all cursor-pointer"
        : "px-4 py-2.5 text-sm font-bold border-b-2 border-blue-500 text-blue-400 transition-all cursor-pointer";
}

let mapAutoCloseTimer = null;
function openMapDrawer(isAuto = false) {
    const drawer = document.getElementById('map-drawer');
    const overlay = document.getElementById('map-overlay');
    if (drawer && overlay) {
        drawer.classList.remove('-translate-x-full');
        overlay.classList.remove('opacity-0', 'pointer-events-none');
        overlay.classList.add('opacity-100', 'pointer-events-auto');
        setTimeout(() => { if (window.chinaMapChart) window.chinaMapChart.resize(); }, 150);
    }
    if (isAuto) {
        const countdownBar = document.getElementById('map-countdown-bar');
        const countdownContainer = document.getElementById('map-countdown-container');
        if (countdownContainer) countdownContainer.classList.remove('hidden');
        if (countdownBar) { countdownBar.style.transition = 'none'; countdownBar.style.width = '100%'; setTimeout(() => { countdownBar.style.transition = 'width 5000ms linear'; countdownBar.style.width = '0%'; }, 50); }
        mapAutoCloseTimer = setTimeout(() => { closeMapDrawer(); }, 5000);
    } else { cancelMapAutoClose(); }
}
function closeMapDrawer() {
    const drawer = document.getElementById('map-drawer');
    const overlay = document.getElementById('map-overlay');
    if (drawer && overlay) { drawer.classList.add('-translate-x-full'); overlay.classList.add('opacity-0', 'pointer-events-none'); overlay.classList.remove('opacity-100', 'pointer-events-auto'); }
    cancelMapAutoClose();
}
function cancelMapAutoClose() {
    if (mapAutoCloseTimer) { clearTimeout(mapAutoCloseTimer); mapAutoCloseTimer = null; }
    const countdownContainer = document.getElementById('map-countdown-container');
    if (countdownContainer) countdownContainer.classList.add('hidden');
}

let toastTimer = null;
function showToast(message) {
    const container = document.getElementById('toast-container');
    const text = document.getElementById('toast-text');
    if (!container || !text) return;
    text.innerText = message;
    container.classList.remove('opacity-0', '-translate-y-4');
    container.classList.add('opacity-100', 'translate-y-0');
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { container.classList.remove('opacity-100', 'translate-y-0'); container.classList.add('opacity-0', '-translate-y-4'); }, 4000);
}
