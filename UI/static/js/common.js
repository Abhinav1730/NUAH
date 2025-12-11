/**
 * NUAH Trading Dashboard - Common JavaScript Utilities
 */

// API Base URL
const API_BASE = '';

/**
 * Fetch data from API endpoint
 * @param {string} endpoint - API endpoint path
 * @returns {Promise<object>} - Response data
 */
async function fetchAPI(endpoint) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error(`Error fetching ${endpoint}:`, error);
        throw error;
    }
}

/**
 * Format number as currency (N-Dollar)
 * @param {number} value - Numeric value
 * @param {boolean} showSign - Whether to show +/- sign
 * @returns {string} - Formatted string
 */
function formatCurrency(value, showSign = false) {
    const num = parseFloat(value) || 0;
    const formatted = Math.abs(num).toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 4
    });
    
    if (showSign && num !== 0) {
        return num > 0 ? `+${formatted}` : `-${formatted}`;
    }
    return num < 0 ? `-${formatted}` : formatted;
}

/**
 * Format number with sign and appropriate CSS class
 * @param {number} value - Numeric value
 * @returns {object} - {text, className}
 */
function formatPnL(value) {
    const num = parseFloat(value) || 0;
    const text = formatCurrency(num, true);
    let className = 'neutral';
    
    if (num > 0) className = 'positive';
    else if (num < 0) className = 'negative';
    
    return { text: `${text} N$`, className };
}

/**
 * Format percentage
 * @param {number} value - Percentage value
 * @returns {string} - Formatted percentage
 */
function formatPercent(value) {
    const num = parseFloat(value) || 0;
    return `${num.toFixed(1)}%`;
}

/**
 * Format timestamp to readable time
 * @param {string} timestamp - ISO timestamp
 * @returns {string} - Formatted time string
 */
function formatTime(timestamp) {
    if (!timestamp) return '-';
    try {
        const date = new Date(timestamp);
        return date.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
        });
    } catch {
        return '-';
    }
}

/**
 * Format timestamp to readable date
 * @param {string} timestamp - ISO timestamp
 * @returns {string} - Formatted date string
 */
function formatDate(timestamp) {
    if (!timestamp) return '-';
    try {
        const date = new Date(timestamp);
        return date.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    } catch {
        return '-';
    }
}

/**
 * Truncate token symbol/address
 * @param {string} token - Token mint address
 * @param {number} length - Max length
 * @returns {string} - Truncated string
 */
function truncateToken(token, length = 12) {
    if (!token) return '-';
    // Extract symbol from denom format (factory/creator/SYMBOL)
    if (token.includes('/')) {
        return token.split('/').pop();
    }
    if (token.length <= length) return token;
    return `${token.slice(0, length)}...`;
}

/**
 * Get action badge HTML
 * @param {string} action - Trade action (buy/sell/hold)
 * @returns {string} - HTML string
 */
function getActionBadge(action) {
    const normalizedAction = (action || 'unknown').toLowerCase();
    const icons = {
        buy: '↑',
        sell: '↓',
        hold: '•'
    };
    return `<span class="cell-action ${normalizedAction}">${icons[normalizedAction] || '?'} ${normalizedAction.toUpperCase()}</span>`;
}

/**
 * Get status indicator HTML
 * @param {string} status - Trade status
 * @returns {string} - HTML string
 */
function getStatusIndicator(status) {
    const normalizedStatus = (status || 'unknown').toLowerCase();
    return `<span class="cell-status ${normalizedStatus}">${normalizedStatus}</span>`;
}

/**
 * Show loading state in element
 * @param {HTMLElement} element - Target element
 */
function showLoading(element) {
    element.innerHTML = `
        <div class="loading">
            <div class="loading-spinner"></div>
            <span>Loading...</span>
        </div>
    `;
}

/**
 * Show empty state in element
 * @param {HTMLElement} element - Target element
 * @param {string} message - Message to display
 */
function showEmpty(element, message = 'No data available') {
    element.innerHTML = `
        <div class="empty-state">
            <div class="empty-state-icon">📊</div>
            <div class="empty-state-title">No Trades Today</div>
            <div class="empty-state-text">${message}</div>
        </div>
    `;
}

/**
 * Show error state in element
 * @param {HTMLElement} element - Target element
 * @param {string} message - Error message
 */
function showError(element, message = 'Failed to load data') {
    element.innerHTML = `
        <div class="empty-state">
            <div class="empty-state-icon">⚠️</div>
            <div class="empty-state-title">Error</div>
            <div class="empty-state-text">${message}</div>
        </div>
    `;
}

/**
 * Chart.js default configuration for dark theme
 */
const chartDefaults = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: {
            labels: {
                color: '#8b949e',
                font: {
                    family: "'Sora', sans-serif",
                    size: 12
                },
                padding: 20
            }
        },
        tooltip: {
            backgroundColor: '#21262d',
            titleColor: '#f0f6fc',
            bodyColor: '#8b949e',
            borderColor: '#30363d',
            borderWidth: 1,
            cornerRadius: 8,
            padding: 12,
            titleFont: {
                family: "'Sora', sans-serif",
                size: 13,
                weight: 600
            },
            bodyFont: {
                family: "'JetBrains Mono', monospace",
                size: 12
            }
        }
    },
    scales: {
        x: {
            grid: {
                color: '#21262d',
                drawBorder: false
            },
            ticks: {
                color: '#6e7681',
                font: {
                    family: "'Sora', sans-serif",
                    size: 11
                }
            }
        },
        y: {
            grid: {
                color: '#21262d',
                drawBorder: false
            },
            ticks: {
                color: '#6e7681',
                font: {
                    family: "'JetBrains Mono', monospace",
                    size: 11
                }
            }
        }
    }
};

/**
 * Color palette for charts
 */
const chartColors = {
    cyan: '#00d4aa',
    cyanDim: 'rgba(0, 212, 170, 0.2)',
    red: '#ff6b6b',
    redDim: 'rgba(255, 107, 107, 0.2)',
    yellow: '#ffd93d',
    yellowDim: 'rgba(255, 217, 61, 0.2)',
    blue: '#58a6ff',
    blueDim: 'rgba(88, 166, 255, 0.2)',
    purple: '#a371f7',
    purpleDim: 'rgba(163, 113, 247, 0.2)',
    gray: '#8b949e',
    grayDim: 'rgba(139, 148, 158, 0.2)'
};

/**
 * Get gradient for chart
 * @param {CanvasRenderingContext2D} ctx - Canvas context
 * @param {string} color - Color value
 * @returns {CanvasGradient} - Gradient object
 */
function getChartGradient(ctx, color) {
    const gradient = ctx.createLinearGradient(0, 0, 0, 300);
    gradient.addColorStop(0, color.replace(')', ', 0.4)').replace('rgb', 'rgba'));
    gradient.addColorStop(1, color.replace(')', ', 0)').replace('rgb', 'rgba'));
    return gradient;
}

/**
 * Auto-refresh data at interval
 * @param {Function} callback - Function to call
 * @param {number} intervalMs - Interval in milliseconds
 * @returns {number} - Interval ID
 */
function autoRefresh(callback, intervalMs = 60000) {
    // Call immediately
    callback();
    // Then set interval
    return setInterval(callback, intervalMs);
}

/**
 * Update current time display
 */
function updateCurrentTime() {
    const el = document.getElementById('current-time');
    if (el) {
        const now = new Date();
        el.textContent = now.toLocaleString('en-US', {
            weekday: 'short',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
        });
    }
}

// Update time every second
setInterval(updateCurrentTime, 1000);
updateCurrentTime();


