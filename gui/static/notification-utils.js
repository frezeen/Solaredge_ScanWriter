// ===== NOTIFICATION UTILITIES =====
// Unified notification system with consistent interface

// Lookup table for notification colors
const NOTIFICATION_COLORS = {
    'success': 'var(--accent-green)',
    'error': 'var(--accent-red)',
    'info': 'var(--accent-blue)',
    'warning': 'var(--accent-yellow, #f59e0b)'
};

// Lookup table for notification durations (in milliseconds)
const NOTIFICATION_DURATIONS = {
    'error': 8000,
    'success': 3000,
    'info': 3000,
    'warning': 5000
};

/**
 * Show a notification toast message
 * @param {string} message - Message to display
 * @param {string} type - Notification type: 'success', 'error', 'info', 'warning'
 */
function notify(message, type = 'info') {
    const el = document.createElement('div');
    
    // Apply styles
    Object.assign(el.style, {
        position: 'fixed',
        top: '20px',
        right: '20px',
        background: NOTIFICATION_COLORS[type] || NOTIFICATION_COLORS.info,
        color: 'white',
        padding: '1rem 1.5rem',
        borderRadius: '8px',
        boxShadow: 'var(--shadow-lg)',
        zIndex: '1000',
        fontWeight: '500',
        transform: 'translateX(100%)',
        transition: 'transform 0.3s ease',
        maxWidth: '400px'
    });

    el.textContent = message;
    document.body.appendChild(el);

    // Animate in
    setTimeout(() => el.style.transform = 'translateX(0)', 100);
    
    // Animate out and remove
    const duration = NOTIFICATION_DURATIONS[type] || NOTIFICATION_DURATIONS.info;
    setTimeout(() => {
        el.style.transform = 'translateX(100%)';
        setTimeout(() => el.remove(), 300);
    }, duration);
}

/**
 * Show a success notification
 * @param {string} message - Success message to display
 */
function showSuccess(message) {
    notify(message, 'success');
}

/**
 * Show an error notification
 * @param {string} message - Error message to display
 */
function showError(message) {
    notify(message, 'error');
}

/**
 * Show an info notification
 * @param {string} message - Info message to display
 */
function showInfo(message) {
    notify(message, 'info');
}

/**
 * Show a warning notification
 * @param {string} message - Warning message to display
 */
function showWarning(message) {
    notify(message, 'warning');
}
