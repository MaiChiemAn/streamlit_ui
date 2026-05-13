/**
 * Configuration file for Frontend Charts
 * Centralized settings for chart behavior and appearance
 */

// ===== API Configuration =====
const CONFIG = {
    // API Base URL
    API_BASE_URL: 'http://localhost:5000',
    
    // ===== Chart Limits =====
    TOP_N_TEAMS: 30,  // Number of top teams to show in bar chart
    
    // ===== Bubble Chart Configuration =====
    BUBBLE_CHART_MAX_TEAMS: 7,        // Max teams to display in bubble chart (top 7 like app.py)
    
    // ===== Cache & Refresh =====
    DEFAULT_REFRESH_INTERVAL: 5,  // seconds
    
    // ===== Animation Settings =====
    BAR_CHART_ANIMATION_DURATION: 1000  // ms
};

// Freeze config to prevent modifications
Object.freeze(CONFIG);
