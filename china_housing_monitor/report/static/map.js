/**
 * China Map Module for CHM v0.8
 * Uses ECharts to render interactive map with city markers
 * City markers blink based on bottom signal score
 */

function renderChinaMap(cities) {
    const mapContainer = document.getElementById('chinaMap');
    if (!mapContainer) {
        console.error('Map container not found');
        return;
    }

    // Initialize ECharts
    const chart = echarts.init(mapContainer);
    window.chinaMapChart = chart;
    
    // Register China map
    echarts.registerMap('china', chinaGeoJSON);
    
    // Prepare city data for scatter series
    const cityData = [];
    Object.keys(cities).forEach(cid => {
        const city = cities[cid];
        if (city.lat && city.lng) {
            cityData.push({
                name: city.name,
                value: [city.lng, city.lat, city.bottom_score || 0],
                cityId: cid,
                score: city.bottom_score || 0,
                level: city.level,
                itemStyle: {
                    color: getScoreColor(city.bottom_score || 0),
                    shadowBlur: city.bottom_score > 70 ? 15 : 0,
                    shadowColor: getScoreColor(city.bottom_score || 0)
                }
            });
        }
    });
    
    // ECharts option
    const option = {
        backgroundColor: 'transparent',
        title: {
            show: false
        },
        tooltip: {
            trigger: 'item',
            backgroundColor: 'rgba(15, 23, 42, 0.95)',
            borderColor: '#334155',
            textStyle: {
                color: '#e2e8f0',
                fontSize: 12
            },
                formatter: function(params) {
                if (params.seriesType === 'scatter' || params.seriesType === 'effectScatter') {
                    const city = params.data;
                    const score = city.score.toFixed(1);
                    const status = getScoreStatus(city.score);
                    const color = getScoreColor(city.score);
                    return `<div style="font-weight:bold;margin-bottom:4px;">${city.name}</div>
                            <div>底部信号: <span style="color:${color};font-weight:bold;">${score}</span></div>
                            <div>状态: ${status}</div>
                            <div style="font-size:10px;color:#94a3b8;margin-top:4px;">点击查看详细数据</div>`;
                }
                return null;
            }
        },
        geo: {
            map: 'china',
            roam: false,
            zoom: 1.5,
            center: [104, 35],
            label: {
                show: false
            },
            itemStyle: {
                areaColor: '#1e293b',
                borderColor: '#334155',
                borderWidth: 1
            },
            emphasis: {
                disabled: true,
                label: {
                    show: false
                },
                itemStyle: {
                    areaColor: '#1e293b'
                }
            },
            select: {
                disabled: true
            },
            regions: [{
                name: '南海诸岛',
                itemStyle: {
                    opacity: 0
                },
                label: {
                    show: false
                }
            }]
        },
        series: [
            {
                type: 'scatter',
                coordinateSystem: 'geo',
                data: cityData,
                symbolSize: function(val) {
                    // Size based on score: higher score = larger dot
                    const score = val[2] || 0;
                    return Math.max(8, Math.min(20, score / 5));
                },
                label: {
                    show: true,
                    formatter: '{b}',
                    position: 'right',
                    color: '#94a3b8',
                    fontSize: 10
                },
                emphasis: {
                    label: {
                        show: true,
                        color: '#ffffff',
                        fontSize: 12,
                        fontWeight: 'bold'
                    }
                },
                animationDurationUpdate: 500,
                animationEasingUpdate: 'cubicInOut'
            },
            // Blinking effect layer for high-score cities
            {
                type: 'effectScatter',
                coordinateSystem: 'geo',
                data: cityData.filter(d => d.score > 70),
                symbolSize: function(val) {
                    return Math.max(12, Math.min(25, val[2] / 4));
                },
                showEffectOn: 'render',
                rippleEffect: {
                    brushType: 'stroke',
                    scale: 3,
                    period: 4
                },
                label: {
                    show: false
                },
                itemStyle: {
                    color: function(params) {
                        return getScoreColor(params.data.score);
                    },
                    shadowBlur: 20,
                    shadowColor: 'rgba(239, 68, 68, 0.5)'
                },
                zlevel: 1
            }
        ]
    };
    
    // Set option
    chart.setOption(option);
    
    // Click event
    chart.on('click', function(params) {
        if (params.componentType === 'series' && params.data && params.data.cityId) {
            onCityChange(params.data.cityId);
        }
    });
    
    // Responsive resize
    window.addEventListener('resize', function() {
        chart.resize();
    });
    
    return chart;
}

// Helper functions
function getScoreColor(score) {
    if (score >= 85) return '#3b82f6';  // Blue - strong signal (avoid green conflict with storage cities)
    if (score >= 70) return '#eab308';  // Yellow - moderate signal
    if (score >= 50) return '#f97316';  // Orange - weak signal
    return '#ef4444';                    // Red - no signal
}

function getScoreStatus(score) {
    if (score >= 85) return '强信号观察';
    if (score >= 70) return '政策价格共振';
    if (score >= 50) return '价格止跌观察';
    if (score >= 30) return '政策底观察';
    return '下跌通道';
}

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    const db = window.MONITOR_DB;
    if (db && db.cities) {
        // Wait a bit for ECharts to load
        setTimeout(function() {
            if (typeof echarts !== 'undefined') {
                renderChinaMap(db.cities);
            } else {
                console.error('ECharts not loaded');
            }
        }, 500);
    }
});
