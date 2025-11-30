// ===== DOM MANIPULATION UTILITIES =====
// Reusable DOM utilities with batching support for better performance

/**
 * Batch append multiple elements to a container using DocumentFragment
 * This is more efficient than individual appendChild calls
 * @param {HTMLElement} container - Target container element
 * @param {Array<HTMLElement>} elements - Array of elements to append
 */
function batchAppend(container, elements) {
    const fragment = document.createDocumentFragment();
    elements.forEach(el => fragment.appendChild(el));
    container.appendChild(fragment);
}

/**
 * Replace all children of a container with new elements (batched)
 * @param {HTMLElement} container - Target container element
 * @param {Array<HTMLElement>} elements - Array of new elements
 */
function replaceChildren(container, elements) {
    const fragment = document.createDocumentFragment();
    elements.forEach(el => fragment.appendChild(el));
    container.replaceChildren(fragment);
}

/**
 * Create an element with attributes and optional children
 * @param {string} tag - HTML tag name
 * @param {Object} attributes - Object with attribute key-value pairs
 * @param {Array<HTMLElement|string>} children - Optional array of child elements or text
 * @returns {HTMLElement} Created element
 */
function createElement(tag, attributes = {}, children = []) {
    const element = document.createElement(tag);

    // Set attributes
    Object.entries(attributes).forEach(([key, value]) => {
        if (key === 'className') {
            element.className = value;
        } else if (key === 'dataset') {
            Object.entries(value).forEach(([dataKey, dataValue]) => {
                element.dataset[dataKey] = dataValue;
            });
        } else if (key.startsWith('on') && typeof value === 'function') {
            // Event listeners
            const eventName = key.substring(2).toLowerCase();
            element.addEventListener(eventName, value);
        } else {
            element.setAttribute(key, value);
        }
    });

    // Add children
    children.forEach(child => {
        if (typeof child === 'string') {
            element.appendChild(document.createTextNode(child));
        } else if (child instanceof HTMLElement) {
            element.appendChild(child);
        }
    });

    return element;
}

/**
 * Safely set text content (prevents XSS)
 * @param {HTMLElement} element - Target element
 * @param {string} text - Text content to set
 */
function setTextContent(element, text) {
    element.textContent = text;
}

/**
 * Safely set HTML content (use with caution - sanitize input first)
 * @param {HTMLElement} element - Target element
 * @param {string} html - HTML content to set
 */
function setInnerHTML(element, html) {
    element.innerHTML = html;
}

/**
 * Toggle element visibility
 * @param {HTMLElement} element - Target element
 * @param {boolean} visible - Whether element should be visible
 */
function toggleVisibility(element, visible) {
    element.style.display = visible ? '' : 'none';
}

/**
 * Add or remove a class based on condition
 * @param {HTMLElement} element - Target element
 * @param {string} className - Class name to toggle
 * @param {boolean} condition - Whether to add (true) or remove (false) the class
 */
function toggleClass(element, className, condition) {
    element.classList.toggle(className, condition);
}

/**
 * Query selector with optional parent element
 * @param {string} selector - CSS selector
 * @param {HTMLElement} parent - Optional parent element (defaults to document)
 * @returns {HTMLElement|null} Found element or null
 */
function $(selector, parent = document) {
    return parent.querySelector(selector);
}

/**
 * Query selector all with optional parent element
 * @param {string} selector - CSS selector
 * @param {HTMLElement} parent - Optional parent element (defaults to document)
 * @returns {Array<HTMLElement>} Array of found elements
 */
function $$(selector, parent = document) {
    return Array.from(parent.querySelectorAll(selector));
}

/**
 * Remove all children from an element
 * @param {HTMLElement} element - Target element
 */
function clearChildren(element) {
    element.replaceChildren();
}

/**
 * Animate element with CSS class
 * @param {HTMLElement} element - Target element
 * @param {string} animationClass - CSS animation class
 * @param {number} delay - Optional delay in milliseconds
 */
function animateElement(element, animationClass, delay = 0) {
    if (delay > 0) {
        element.style.animationDelay = `${delay}ms`;
    }
    element.classList.add(animationClass);
}

/**
 * Batch update multiple element properties
 * @param {HTMLElement} element - Target element
 * @param {Object} updates - Object with property updates
 */
function updateElement(element, updates) {
    Object.entries(updates).forEach(([key, value]) => {
        if (key === 'text') {
            element.textContent = value;
        } else if (key === 'html') {
            element.innerHTML = value;
        } else if (key === 'class') {
            element.className = value;
        } else if (key === 'style') {
            Object.assign(element.style, value);
        } else if (key === 'dataset') {
            Object.assign(element.dataset, value);
        } else {
            element[key] = value;
        }
    });
}
