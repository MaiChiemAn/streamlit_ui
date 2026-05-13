/**
 * Dynamic Chart with Database Integration
 * Fetches data from FastAPI và render Highcharts realtime
 */

// Use API_BASE_URL from config
const API_BASE_URL = CONFIG.API_BASE_URL;
let autoRefreshInterval = null;
let chartInstance1 = null;
let chartInstance2 = null;

// ===== UI Elements =====
const statusElement = document.getElementById('status');
const refreshButton = document.getElementById('refreshButton');
const autoRefreshCheckbox = document.getElementById('autoRefresh');
const refreshIntervalInput = document.getElementById('refreshInterval');
const statsContainer = document.getElementById('stats');

// ===== API Functions =====
async function checkHealth() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/health`);
        
        if (!response.ok) {
            return { 
                status: 'error', 
                message: `HTTP ${response.status}: ${response.statusText}` 
            };
        }
        
        const result = await response.json();
        return result;
    } catch (error) {
        // Network error hoặc JSON parse error
        const message = error.message || 'Không thể kết nối đến API server';
        return { 
            status: 'error', 
            message: message,
            hint: 'Đảm bảo API server đang chạy ở http://localhost:5000'
        };
    }
}

async function fetchData() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/data`);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const result = await response.json();
        
        if (result.status === 'success') {
            return result.data;
        } else {
            throw new Error(result.message || 'Unknown error from API');
        }
    } catch (error) {
        console.error('Error fetching data:', error);
        const message = error.message || 'Không thể lấy dữ liệu từ server';
        throw new Error(message);
    }
}

async function fetchStats() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/stats`);
        
        if (!response.ok) {
            console.warn(`Stats fetch failed: HTTP ${response.status}`);
            return null;
        }
        
        const result = await response.json();
        
        if (result.status === 'success') {
            return result.stats;
        } else {
            console.warn('Stats API returned error:', result.message);
            return null;
        }
    } catch (error) {
        console.error('Error fetching stats:', error);
        return null;
    }
}

// ===== Data Processing =====
function processDataForColumnChart(data) {
    /**
     * Main chart: Count DISTINCT keywords per team (diversity metric)
     * Drilldown: Show SUM of occurrences for each keyword (frequency metric)
     * 
     * Example:
     * - Team A has keyword "python" appearing 5 times, "java" 3 times
     * - Main chart shows: Team A = 2 (distinct keywords)
     * - Drilldown shows: python = 5 occurrences, java = 3 occurrences
     */
    // Group by team_name and count DISTINCT keywords
    const teamMap = {};
    const teamKeywordCounts = {}; // Sum keyword_count for drilldown
    const teamKeywordSet = {}; // Track unique keywords per team
    
    data.forEach(item => {
        const team = item.team_name;
        const keyword = item.keyword;
        const count = item.keyword_count;
        
        if (!teamMap[team]) {
            teamMap[team] = 0;
            teamKeywordCounts[team] = {};
            teamKeywordSet[team] = new Set();
        }
        
        // Count distinct keywords only (không đếm duplicate)
        teamKeywordSet[team].add(keyword);
        teamMap[team] = teamKeywordSet[team].size;
        
        // Sum keyword_count cho drilldown (tổng số lần xuất hiện)
        if (!teamKeywordCounts[team][keyword]) {
            teamKeywordCounts[team][keyword] = 0;
        }
        teamKeywordCounts[team][keyword] += count;
    });
    
    // Prepare series data với id duy nhất cho mỗi team (cho animation)
    const seriesData = Object.keys(teamMap).map(team => ({
        id: team,  // Unique ID cho racing animation
        name: team,
        y: teamMap[team], // Số lượng keywords distinct
        drilldown: team
    }));
    
    // Sort và chỉ lấy top N từ config
    const topN = seriesData.sort((a, b) => b.y - a.y).slice(0, CONFIG.TOP_N_TEAMS);
    
    // Prepare drilldown series với tổng số lần xuất hiện của mỗi keyword
    const drilldownSeries = Object.keys(teamKeywordCounts)
        .filter(team => topN.some(t => t.name === team))
        .map(team => {
            // Convert keyword counts object to array và sort
            const keywordData = Object.entries(teamKeywordCounts[team])
                .map(([keyword, totalCount]) => [keyword, totalCount])
                .sort((a, b) => b[1] - a[1]); // Sort by count descending
            
            return {
                id: team,
                name: `${team} keywords (total occurrences)`,
                type: 'bar',
                data: keywordData
            };
        });
    
    return { seriesData: topN, drilldownSeries };
}

/**
 * Helper function to sort team names (matches app.py _team_sort_key logic)
 * Tries to sort numerically first, falls back to alphabetical
 */
function teamSortKey(name) {
    try {
        const num = parseFloat(name);
        if (!isNaN(num)) {
            return [0, num];  // Numeric sort
        }
        return [1, name.toLowerCase()];  // Alphabetical sort
    } catch (e) {
        return [1, name.toLowerCase()];
    }
}

/**
 * Compare function for sorting teams (matches app.py logic)
 */
function compareTeams(a, b) {
    const keyA = teamSortKey(a);
    const keyB = teamSortKey(b);
    
    // Compare first element (0 for numeric, 1 for alphabetic)
    if (keyA[0] !== keyB[0]) {
        return keyA[0] - keyB[0];
    }
    
    // Compare second element (actual value)
    if (typeof keyA[1] === 'number' && typeof keyB[1] === 'number') {
        return keyA[1] - keyB[1];
    }
    
    return keyA[1].localeCompare(keyB[1]);
}

function processDataForBubbleChart(data) {
    // Group by team_name and keyword, sum keyword_count (matches app.py logic)
    const teamMap = {};
    
    data.forEach(item => {
        const team = item.team_name;
        const keyword = item.keyword;
        const count = item.keyword_count;
        
        if (!teamMap[team]) {
            teamMap[team] = {};
        }
        
        if (!teamMap[team][keyword]) {
            teamMap[team][keyword] = 0;
        }
        
        teamMap[team][keyword] += count;
    });
    
    // Calculate total keyword_count for each team
    const teamTotals = {};
    Object.keys(teamMap).forEach(team => {
        teamTotals[team] = Object.values(teamMap[team]).reduce((sum, count) => sum + count, 0);
    });
    
    // Sort by total count descending, take top 7 (matches app.py logic)
    const topTeams = Object.keys(teamTotals)
        .sort((a, b) => teamTotals[b] - teamTotals[a])
        .slice(0, CONFIG.BUBBLE_CHART_MAX_TEAMS);
    
    // Create series for top teams only
    const series = topTeams.map(team => {
        const keywords = Object.entries(teamMap[team]);
        
        const keywordsData = keywords.map(([keyword, totalCount]) => ({
            name: keyword,
            value: totalCount
        }));
        
        return {
            name: team,
            data: keywordsData
        };
    });
    
    // Sort series by team name (numerically if possible, then alphabetically)
    // This matches app.py: series.sort(key=lambda s: _team_sort_key(s["name"]))
    series.sort((a, b) => compareTeams(a.name, b.name));
    
    return series;
}

// ===== Chart Creation =====
function createColumnChart(data) {
    const { seriesData, drilldownSeries } = processDataForColumnChart(data);
    const currentTime = new Date().toLocaleTimeString();
    
    // Data đã được sort trong processDataForColumnChart (top N from config)
    const sortedData = [...seriesData];
    
    // Calculate min and max values for gradient
    const values = sortedData.map(item => item.y);
    const maxValue = Math.max(...values);
    const minValue = Math.min(...values);
    const valueRange = maxValue - minValue || 1;
    
    // Add gradient colors based on actual values (high = dark, low = light)
    sortedData.forEach((item) => {
        // Normalize value: 0 (min) to 1 (max)
        const normalizedValue = (item.y - minValue) / valueRange;
        
        // High value = darker color, low value = lighter color
        const baseOpacity = 0.4 + (normalizedValue * 0.6); // 0.4 to 1.0
        const endOpacity = 0.3 + (normalizedValue * 0.5);   // 0.3 to 0.8
        
        item.color = {
            linearGradient: { x1: 0, y1: 0, x2: 1, y2: 0 },
            stops: [
                [0, Highcharts.color('#667eea').setOpacity(baseOpacity).get()],
                [1, Highcharts.color('#764ba2').setOpacity(endOpacity).get()]
            ]
        };
    });
    
    // Sort drilldown series và apply gradient theo value thật
    const sortedDrilldown = drilldownSeries.map(series => {
        const sortedItems = [...series.data].sort((a, b) => b[1] - a[1]);
        
        // Calculate min/max for this series
        const drillValues = sortedItems.map(item => item[1]);
        const drillMax = Math.max(...drillValues);
        const drillMin = Math.min(...drillValues);
        const drillRange = drillMax - drillMin || 1;
        
        return {
            ...series,
            data: sortedItems.map((item) => {
                // Normalize based on value, not position
                const normalizedValue = (item[1] - drillMin) / drillRange;
                const baseOpacity = 0.5 + (normalizedValue * 0.5); // 0.5 to 1.0
                const endOpacity = 0.4 + (normalizedValue * 0.4);   // 0.4 to 0.8
                
                return {
                    name: item[0],
                    y: item[1],
                    color: {
                        linearGradient: { x1: 0, y1: 0, x2: 1, y2: 0 },
                        stops: [
                            [0, Highcharts.color('#4ade80').setOpacity(baseOpacity).get()],
                            [1, Highcharts.color('#22c55e').setOpacity(endOpacity).get()]
                        ]
                    }
                };
            })
        };
    });
    
    const options = {
        chart: {
            type: 'bar',  // Horizontal bar chart
            animation: {
                duration: CONFIG.BAR_CHART_ANIMATION_DURATION,
                easing: 'easeInOutQuad'
            },
            backgroundColor: {
                linearGradient: { x1: 0, y1: 0, x2: 0, y2: 1 },
                stops: [
                    [0, '#ffffff'],
                    [1, '#f8f9fa']
                ]
            },
            events: {
                // Smooth redraw on data update
                redraw: function() {
                    // Animation callback
                }
            }
        },
        title: {
            text: `🏆 Top ${CONFIG.TOP_N_TEAMS} Teams Performance - Live Update 🔴`,
            style: { fontSize: '20px', fontWeight: 'bold' }
        },
        subtitle: {
            text: `Cập nhật lần cuối: ${currentTime} | Showing Top ${CONFIG.TOP_N_TEAMS} Teams`,
            style: { fontSize: '14px', color: '#666' }
        },
        xAxis: {
            type: 'category',
            title: { text: 'Team' },
            labels: {
                style: {
                    fontSize: '13px',
                    fontWeight: 'bold'
                }
            },
            // Enable smooth label transition
            opposite: false
        },
        yAxis: {
            min: 0,
            title: { 
                text: 'Number of Distinct Keywords',
                align: 'high'
            },
            labels: {
                overflow: 'justify'
            }
        },
        legend: { enabled: false },
        plotOptions: {
            series: {
                borderWidth: 0,
                dataLabels: {
                    enabled: true,
                    format: '{point.y:.0f}',
                    style: { 
                        fontSize: '14px', 
                        fontWeight: 'bold',
                        textOutline: '1px contrast',
                        color: '#333'
                    },
                    align: 'right',
                    inside: false,
                    x: 5
                },
                animation: { 
                    duration: 1200,
                    easing: 'easeOutQuart'
                },
                states: {
                    hover: {
                        brightness: 0.15,
                        borderColor: '#667eea',
                        borderWidth: 2
                    }
                }
            },
            bar: {
                colorByPoint: false,  // Use custom colors from data
                pointPadding: 0.15,
                groupPadding: 0.15,
                borderRadius: 8,
                shadow: {
                    color: 'rgba(102, 126, 234, 0.3)',
                    offsetX: 2,
                    offsetY: 2,
                    width: 5
                },
                // Enable racing bar animation
                dataSorting: {
                    enabled: true,
                    sortKey: 'y',
                    // Smooth animation khi bars swap positions
                    matchByName: true
                },
                // Point animation config
                point: {
                    events: {}
                }
            }
        },
        tooltip: {
            headerFormat: '<span style="font-size:12px">{series.name}</span><br>',
            pointFormat: '<span style="color:{point.color}">{point.name}</span>: <b>{point.y:.0f}</b> distinct keywords<br/>',
            style: {
                fontSize: '13px'
            }
        },
        series: [{
            name: 'Teams',
            colorByPoint: false,  // Use gradient colors from data
            data: sortedData,
            type: 'bar'
        }],
        drilldown: {
            series: sortedDrilldown,
            drillUpButton: {
                relativeTo: 'spacingBox',
                position: {
                    y: 0,
                    x: 0
                },
                theme: {
                    fill: 'white',
                    'stroke-width': 1,
                    stroke: 'silver',
                    r: 5,
                    states: {
                        hover: {
                            fill: '#f0f0f0'
                        }
                    }
                }
            }
        }
    };
    
    // Nếu chart đã tồn tại, update với racing animation
    if (chartInstance1 && chartInstance1.series && chartInstance1.series[0]) {
        try {
            // Update with smooth racing animation
            // Set data với animation config để bars slide up/down
            chartInstance1.series[0].update({
                data: sortedData,
                dataSorting: {
                    enabled: true,
                    sortKey: 'y',
                    matchByName: true
                }
            }, false);
            
            chartInstance1.setTitle({ text: options.title.text }, false);
            chartInstance1.setSubtitle({ text: options.subtitle.text }, false);
            
            // Redraw với animation để trigger racing effect
            chartInstance1.redraw({
                duration: CONFIG.BAR_CHART_ANIMATION_DURATION,
                easing: 'easeInOutQuad'
            });
        } catch (e) {
            // Nếu update fail, destroy và tạo mới
            console.log('Chart update failed, recreating:', e);
            chartInstance1.destroy();
            chartInstance1 = Highcharts.chart('chart-container-1', options);
        }
    } else {
        // Tạo chart mới lần đầu
        if (chartInstance1) {
            chartInstance1.destroy();
        }
        chartInstance1 = Highcharts.chart('chart-container-1', options);
    }
}

function createBubbleChart(data) {
    const series = processDataForBubbleChart(data);
    const currentTime = new Date().toLocaleTimeString();
    
    // Calculate max value for zMax (matches app.py logic)
    let maxValue = 0;
    series.forEach(s => {
        s.data.forEach(d => {
            if (d.value > maxValue) maxValue = d.value;
        });
    });
    
    // No custom colors - use Highcharts default colors (matches app.py)
    
    const options = {
        chart: {
            type: 'packedbubble'
        },
        title: {
            text: 'Keyword distribution across the top 7 teams'
        },
        tooltip: {
            useHTML: true,
            pointFormat: '<b>{point.name}</b>: {point.value}'
        },
        plotOptions: {
            packedbubble: {
                minSize: '20%',
                maxSize: '60%',
                zMin: 0,
                zMax: maxValue,
                layoutAlgorithm: {
                    gravitationalConstant: 0.05,
                    splitSeries: true,
                    seriesInteraction: false,
                    dragBetweenSeries: true,
                    parentNodeLimit: true,
                    bubblePadding: 5
                },
                dataLabels: {
                    enabled: true,
                    format: '{point.name}',
                    filter: { 
                        property: 'y',
                        operator: '>',
                        value: 0
                    },
                    style: { 
                        textOutline: 'none',
                        fontWeight: 'normal'
                    },
                    align: 'center',
                    verticalAlign: 'middle',
                    allowOverlap: true,
                    crop: false,
                    overflow: 'allow',
                    useHTML: false
                }
            }
        },
        series: series
    };
    
    // Try to update existing chart for smoother transitions (fixed team positions)
    if (chartInstance2 && chartInstance2.series && chartInstance2.series.length > 0) {
        try {
            // Update existing series while keeping positions
            const existingSeries = chartInstance2.series;
            
            // Remove series that no longer exist
            for (let i = existingSeries.length - 1; i >= 0; i--) {
                const existingTeam = existingSeries[i].name;
                if (!series.find(s => s.name === existingTeam)) {
                    existingSeries[i].remove(false);
                }
            }
            
            // Update or add series
            series.forEach((newSeries, idx) => {
                const existingSeries = chartInstance2.series.find(s => s.name === newSeries.name);
                
                if (existingSeries) {
                    // Update existing series data (keeps position)
                    existingSeries.setData(newSeries.data, false);
                } else {
                    // Add new series
                    chartInstance2.addSeries(newSeries, false);
                }
            });
            
            // Update title
            chartInstance2.setTitle({ text: options.title.text }, false);
            
            // Redraw once with animation
            chartInstance2.redraw();
            
            console.log('Bubble chart updated (positions preserved)');
        } catch (e) {
            // If update fails, recreate
            console.log('Bubble chart update failed, recreating:', e);
            chartInstance2.destroy();
            chartInstance2 = Highcharts.chart('chart-container-2', options);
        }
    } else {
        // Create new chart
        if (chartInstance2) {
            chartInstance2.destroy();
        }
        chartInstance2 = Highcharts.chart('chart-container-2', options);
    }
}

// ===== UI Updates =====
function updateStatus(message, type = 'info') {
    statusElement.className = `status ${type}`;
    
    const icon = type === 'success' ? '✅' : 
                 type === 'error' ? '❌' : 
                 type === 'loading' ? '⏳' : 'ℹ️';
    
    statusElement.innerHTML = `${icon} ${message}`;
}

function updateStats(stats) {
    if (!stats) return;
    
    statsContainer.innerHTML = `
        <div class="stat-card">
            <div class="stat-value">${stats.total_teams}</div>
            <div class="stat-label">Total Teams</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">${stats.total_players}</div>
            <div class="stat-label">Total Players</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">${stats.total_keywords}</div>
            <div class="stat-label">Unique Keywords</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">${stats.total_records}</div>
            <div class="stat-label">Total Records</div>
        </div>
    `;
}

// ===== Main Update Function =====
let lastDataHash = null;
let isUpdating = false;

async function updateCharts() {
    // Prevent concurrent updates
    if (isUpdating) {
        console.log('Update already in progress, skipping...');
        return;
    }
    
    try {
        isUpdating = true;
        updateStatus('Đang tải dữ liệu...', 'loading');
        
        // Fetch data - shared for both bar and bubble charts
        const [data, stats] = await Promise.all([
            fetchData(),      // Top N for both charts (bubble filters to top 7)
            fetchStats()
        ]);
        
        // Check if data actually changed (avoid unnecessary updates)
        const dataHash = JSON.stringify(data.map(d => ({ t: d.team_name, k: d.keyword, c: d.keyword_count })));
        
        let updated = false;
        
        // Update both charts if data changed
        if (dataHash !== lastDataHash) {
            createColumnChart(data);
            createBubbleChart(data);
            lastDataHash = dataHash;
            updated = true;
        }
        
        const timestamp = new Date().toLocaleTimeString();
        if (updated) {
            updateStatus(
                `Cập nhật thành công lúc ${timestamp} | ${data.length} records`, 
                'success'
            );
        } else {
            updateStatus(
                `No changes detected at ${timestamp}`, 
                'success'
            );
        }
        
        // Always update stats (lightweight)
        updateStats(stats);
        
    } catch (error) {
        updateStatus(`Lỗi: ${error.message}`, 'error');
    } finally {
        isUpdating = false;
    }
}

// ===== Auto Refresh Control =====
function startAutoRefresh() {
    const interval = parseInt(refreshIntervalInput.value) * 1000;
    
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
    }
    
    autoRefreshInterval = setInterval(updateCharts, interval);
    updateStatus(`🔄 Auto-refresh mỗi ${refreshIntervalInput.value}s`, 'info');
}

function stopAutoRefresh() {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
    }
    updateStatus('⏸️ Auto-refresh đã tắt', 'info');
}

// ===== Event Listeners =====
refreshButton.addEventListener('click', updateCharts);

autoRefreshCheckbox.addEventListener('change', (e) => {
    if (e.target.checked) {
        startAutoRefresh();
        updateCharts(); // Update ngay lập tức
    } else {
        stopAutoRefresh();
    }
});

refreshIntervalInput.addEventListener('change', () => {
    if (autoRefreshCheckbox.checked) {
        startAutoRefresh();
    }
});

// ===== Initialize =====
async function initialize() {
    updateStatus('Đang kiểm tra kết nối...', 'loading');
    
    // Check health
    const health = await checkHealth();
    
    if (health.status === 'healthy') {
        updateStatus('✅ Kết nối database thành công!', 'success');
        
        // Load initial data
        await updateCharts();
        
        // Start auto-refresh if enabled
        if (autoRefreshCheckbox.checked) {
            startAutoRefresh();
        }
    } else {
        const errorMsg = health.message || 'Lỗi không xác định';
        const hint = health.hint ? ` | ${health.hint}` : '';
        updateStatus(`❌ Không thể kết nối: ${errorMsg}${hint}`, 'error');
    }
}

// Run on page load
initialize();
