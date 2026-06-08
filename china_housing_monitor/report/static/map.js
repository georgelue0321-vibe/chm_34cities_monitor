function getMapThemeColors() {
    const isLight = document.documentElement.getAttribute('data-theme') === 'light';
    return {
        isLight,
        areaColor: isLight ? '#e2e8f0' : '#1e293b',
        borderColor: isLight ? '#cbd5e1' : '#334155',
        emphasisArea: isLight ? '#f1f5f9' : '#1e293b',
        tooltipBg: isLight ? 'rgba(255, 255, 255, 0.95)' : 'rgba(15, 23, 42, 0.95)',
        tooltipBorder: isLight ? '#cbd5e1' : '#334155',
        tooltipText: isLight ? '#0f172a' : '#e2e8f0',
        labelColor: isLight ? '#475569' : '#94a3b8',
        emphasisLabel: isLight ? '#0f172a' : '#ffffff',
        hintColor: isLight ? '#94a3b8' : '#94a3b8',
        regionColors: isLight ? {
            '华北': '#e8eef5', '东北': '#ece8f0', '华东': '#e5f0ea',
            '华中': '#f0ede5', '华南': '#f0e8e0', '西南': '#e0efed', '西北': '#eee8e2'
        } : null
    };
}

const REGION_MAP = {
    '北京': '华北', '天津': '华北', '河北': '华北', '山西': '华北', '内蒙古': '华北',
    '辽宁': '东北', '吉林': '东北', '黑龙江': '东北',
    '上海': '华东', '江苏': '华东', '浙江': '华东', '安徽': '华东', '福建': '华东', '江西': '华东', '山东': '华东',
    '河南': '华中', '湖北': '华中', '湖南': '华中',
    '广东': '华南', '广西': '华南', '海南': '华南',
    '重庆': '西南', '四川': '西南', '贵州': '西南', '云南': '西南', '西藏': '西南',
    '陕西': '西北', '甘肃': '西北', '青海': '西北', '宁夏': '西北', '新疆': '西北',
    '台湾': '华东', '香港': '华南', '澳门': '华南'
};

function renderChinaMap(cities) {
    const mapContainer = document.getElementById('chinaMap');
    if (!mapContainer) { console.error('Map container not found'); return; }
    const chart = echarts.init(mapContainer);
    window.chinaMapChart = chart;
    echarts.registerMap('china', chinaGeoJSON);
    const mc = getMapThemeColors();
    const cityData = [];
    Object.keys(cities).forEach(cid => {
        const city = cities[cid];
        if (city.lat && city.lng) {
            cityData.push({
                name: city.name, value: [city.lng, city.lat, city.bottom_score || 0],
                cityId: cid, score: city.bottom_score || 0, level: city.level,
                itemStyle: { color: getScoreColor(city.bottom_score || 0), shadowBlur: city.bottom_score > 70 ? 15 : 0, shadowColor: getScoreColor(city.bottom_score || 0) }
            });
        }
    });
    const option = {
        backgroundColor: 'transparent', title: { show: false },
        tooltip: {
            trigger: 'item',
            backgroundColor: mc.tooltipBg, borderColor: mc.tooltipBorder,
            textStyle: { color: mc.tooltipText, fontSize: 12 },
            formatter: function(params) {
                if (params.seriesType === 'scatter' || params.seriesType === 'effectScatter') {
                    const city = params.data; const score = city.score.toFixed(1); const status = getScoreStatus(city.score); const color = getScoreColor(city.score);
                    return `<div style="font-weight:bold;margin-bottom:4px;">${city.name}</div><div>底部信号: <span style="color:${color};font-weight:bold;">${score}</span></div><div>状态: ${status}</div><div style="font-size:10px;color:${mc.hintColor};margin-top:4px;">点击查看详细数据</div>`;
                }
                return null;
            }
        },
        geo: {
            map: 'china', roam: false, zoom: 1.5, center: [104, 35],
            label: { show: false },
            itemStyle: { areaColor: mc.areaColor, borderColor: mc.borderColor, borderWidth: 1 },
            emphasis: { disabled: true, label: { show: false }, itemStyle: { areaColor: mc.emphasisArea } },
            select: { disabled: true },
            regions: mc.regionColors
                ? chinaGeoJSON.features.map(f => {
                    const name = f.properties && f.properties.name;
                    const region = REGION_MAP[name];
                    const color = region ? mc.regionColors[region] : mc.areaColor;
                    return { name, itemStyle: { areaColor: color }, emphasis: { itemStyle: { areaColor: mc.emphasisArea } } };
                }).concat([{ name: '南海诸岛', itemStyle: { opacity: 0 }, label: { show: false } }])
                : [{ name: '南海诸岛', itemStyle: { opacity: 0 }, label: { show: false } }]
        },
        series: [
            {
                type: 'scatter', coordinateSystem: 'geo', data: cityData,
                symbolSize: function(val) { return Math.max(8, Math.min(20, (val[2] || 0) / 5)); },
                label: { show: true, formatter: '{b}', position: 'right', color: mc.labelColor, fontSize: 11 },
                emphasis: { label: { show: true, color: mc.emphasisLabel, fontSize: 13, fontWeight: 'bold' } },
                animationDurationUpdate: 500, animationEasingUpdate: 'cubicInOut'
            },
            {
                type: 'effectScatter', coordinateSystem: 'geo',
                data: cityData.filter(d => d.score > 70),
                symbolSize: function(val) { return Math.max(12, Math.min(25, val[2] / 4)); },
                showEffectOn: 'render', rippleEffect: { brushType: 'stroke', scale: 3, period: 4 },
                label: { show: false },
                itemStyle: { color: function(params) { return getScoreColor(params.data.score); }, shadowBlur: 20, shadowColor: 'rgba(239, 68, 68, 0.5)' },
                zlevel: 1
            }
        ]
    };
    chart.setOption(option);
    chart.on('click', function(params) { if (params.componentType === 'series' && params.data && params.data.cityId) onCityChange(params.data.cityId); });
    window.addEventListener('resize', function() { chart.resize(); });
    return chart;
}

function getScoreColor(score) {
    if (score >= 85) return '#3b82f6';
    if (score >= 70) return '#eab308';
    if (score >= 50) return '#f97316';
    return '#ef4444';
}
function getScoreStatus(score) {
    if (score >= 85) return '强信号观察';
    if (score >= 70) return '政策价格共振';
    if (score >= 50) return '价格止跌观察';
    if (score >= 30) return '政策底观察';
    return '下跌通道';
}

function rerenderMapForTheme() {
    const db = window.MONITOR_DB;
    if (!db || !db.cities) return;
    if (window.chinaMapChart) {
        window.chinaMapChart.dispose();
        window.chinaMapChart = null;
    }
    renderChinaMap(db.cities);
}

document.addEventListener('DOMContentLoaded', function() {
    const db = window.MONITOR_DB;
    if (db && db.cities) {
        setTimeout(function() {
            if (typeof echarts !== 'undefined') renderChinaMap(db.cities);
            else console.error('ECharts not loaded');
        }, 500);
    }
});
