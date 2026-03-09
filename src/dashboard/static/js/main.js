/**
 * 主JavaScript文件
 * 仪表盘通用功能
 */

// 当前激活的导航项
document.addEventListener('DOMContentLoaded', function() {
    highlightCurrentNav();
});

// 高亮当前导航项
function highlightCurrentNav() {
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('nav a');
    
    navLinks.forEach(link => {
        link.classList.remove('active');
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
        }
    });
}

// 格式化数字
function formatNumber(num, decimals = 0) {
    if (num === null || num === undefined) return '--';
    return num.toFixed(decimals);
}

// 格式化百分比
function formatPercent(num) {
    if (num === null || num === undefined) return '--';
    return (num > 0 ? '+' : '') + num.toFixed(1) + '%';
}

// 格式化货币
function formatCurrency(num, currency = 'USD') {
    if (num === null || num === undefined) return '--';
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: currency
    }).format(num);
}

// 防抖函数
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// 显示加载状态
function showLoading(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.classList.add('loading');
    }
}

// 隐藏加载状态
function hideLoading(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.classList.remove('loading');
    }
}

// 显示错误消息
function showError(message, containerId = null) {
    const errorHtml = `
        <div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4" role="alert">
            <strong class="font-bold">错误!</strong>
            <span class="block sm:inline">${message}</span>
        </div>
    `;
    
    if (containerId) {
        const container = document.getElementById(containerId);
        if (container) {
            container.insertAdjacentHTML('afterbegin', errorHtml);
        }
    } else {
        document.body.insertAdjacentHTML('afterbegin', errorHtml);
    }
}

// 获取颜色（基于索引）
function getColor(index) {
    const colors = [
        '#3B82F6', // blue
        '#10B981', // green
        '#F59E0B', // yellow
        '#EF4444', // red
        '#8B5CF6', // purple
        '#EC4899', // pink
        '#06B6D4', // cyan
        '#84CC16', // lime
    ];
    return colors[index % colors.length];
}

// 导出全局函数
window.formatNumber = formatNumber;
window.formatPercent = formatPercent;
window.formatCurrency = formatCurrency;
window.debounce = debounce;
window.showLoading = showLoading;
window.hideLoading = hideLoading;
window.showError = showError;
window.getColor = getColor;
