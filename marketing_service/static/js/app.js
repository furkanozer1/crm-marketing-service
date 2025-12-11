// =============================================================================
// NEXUS CRM - Marketing Automation Module
// Main JavaScript Application
// =============================================================================

// API Helper
async function api(endpoint, options = {}) {
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json'
        }
    };

    const response = await fetch(endpoint, { ...defaultOptions, ...options });

    if (response.status === 401) {
        window.location.href = '/login';
        return null;
    }

    return response;
}

// Logout function
async function logout() {
    try {
        await fetch('/auth/logout', { method: 'POST' });
    } catch (e) {
        // Ignore errors
    }
    window.location.href = '/login';
}

// Format currency
function formatCurrency(value) {
    return '$' + (value || 0).toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
}

// Format percentage
function formatPercent(value) {
    return (value || 0).toFixed(1) + '%';
}

// Toast notifications
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;

    document.body.appendChild(toast);

    setTimeout(() => toast.classList.add('show'), 10);

    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Confirmation dialog removed to use native window.confirm
// function confirm(message) {
//    return window.confirm(message);
// }

// Date formatting
function formatDate(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

// Debounce function
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
