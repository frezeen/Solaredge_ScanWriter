// ===== API UTILITIES =====
// Reusable API call utilities with error handling and response parsing

/**
 * Make an API call with automatic error handling and JSON parsing
 * @param {string} method - HTTP method (GET, POST, etc.)
 * @param {string} url - API endpoint URL
 * @param {Object} options - Additional fetch options
 * @returns {Promise<Object>} Parsed JSON response
 * @throws {Error} On network or HTTP errors
 */
async function apiCall(method, url, options = {}) {
    try {
        const response = await fetch(url, {
            method,
            ...options
        });
        
        if (!response.ok) {
            const data = await response.json().catch(() => ({ error: 'Unknown error' }));
            throw new Error(data.error || `HTTP ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        // Re-throw to let caller handle
        throw error;
    }
}

/**
 * Make a GET request
 * @param {string} url - API endpoint URL
 * @param {Object} options - Additional fetch options
 * @returns {Promise<Object>} Parsed JSON response
 */
async function apiGet(url, options = {}) {
    return apiCall('GET', url, options);
}

/**
 * Make a POST request with JSON body
 * @param {string} url - API endpoint URL
 * @param {Object} body - Request body to be JSON stringified
 * @param {Object} options - Additional fetch options
 * @returns {Promise<Object>} Parsed JSON response
 */
async function apiPost(url, body = null, options = {}) {
    const postOptions = {
        headers: { 'Content-Type': 'application/json' },
        ...options
    };
    
    if (body !== null) {
        postOptions.body = JSON.stringify(body);
    }
    
    return apiCall('POST', url, postOptions);
}

/**
 * Log a message to the backend
 * @param {string} level - Log level (info, warning, error)
 * @param {string} message - Log message
 * @param {Error} error - Optional error object
 */
async function logToBackend(level, message, error = null) {
    try {
        await apiPost('/api/log', {
            level,
            message,
            error: error?.message,
            timestamp: new Date().toISOString()
        });
    } catch {
        // Silently fail - don't want logging errors to break the app
    }
}
