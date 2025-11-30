// ===== SOLAREDGE DASHBOARD - OPTIMIZED v2 =====
class SolarDashboard {
    constructor() {
        this.state = {
            section: 'loop',
            category: 'all',
            devices: {},
            endpoints: {},
            modbus: {},
            config: {},
            loopStatus: null,
            autoScroll: true
        };
        this._optimizersCache = null; // Cache for optimizers list (array)
        this._optimizersSet = null; // Cache for optimizers set (O(1) lookups)

        // API response cache with TTL
        this._apiCache = new Map();
        this._cacheTTL = {
            'loop-status': 5000,      // 5 seconds for loop status
            'devices': 30000,          // 30 seconds for device list
            'endpoints': 30000,        // 30 seconds for endpoint list
            'modbus': 30000,           // 30 seconds for modbus list
            'config': 60000            // 60 seconds for config
        };

        // Cleanup tracking per memory leak prevention
        this.intervals = [];
        this.eventListeners = [];
        this.abortController = new AbortController();

        this.init();
    }

    async init() {
        this.setupEventListeners();
        await this.loadData();
        this.render();
        this.updateConnectionStatus();
        this.startLoopMonitoring();
    }

    // Cleanup method per prevenire memory leak
    destroy() {
        // Clear all intervals
        this.intervals.forEach(id => clearInterval(id));
        this.intervals = [];

        // Abort all pending fetches
        this.abortController.abort();

        // Remove event listeners
        this.eventListeners.forEach(({ element, event, handler }) => {
            element.removeEventListener(event, handler);
        });
        this.eventListeners = [];

        // Clear API cache
        this.clearCache();

        console.log('Dashboard destroyed, resources cleaned up');
    }

    // Unified logging
    async log(level, message, error = null) {
        await logToBackend(level, message, error);
    }

    // Unified error handler
    async handleError(error, context, userMessage = null) {
        // Log the error
        await this.log('error', `Error ${context}`, error);

        // Show user notification
        const message = userMessage || `Errore ${context}`;
        this.notify(message, 'error');

        // Return false to indicate failure
        return false;
    }

    // Unified API call wrapper with error handling
    async apiCall(method, url, options = {}) {
        try {
            const response = await fetch(url, {
                method,
                signal: this.abortController.signal,
                ...options
            });

            if (!response.ok) {
                const data = await response.json().catch(() => ({ error: 'Unknown error' }));
                throw new Error(data.error || `HTTP ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            if (error.name === 'AbortError') {
                throw error; // Re-throw abort errors
            }
            throw error;
        }
    }

    // Get cached API response or fetch if expired
    async getCached(cacheKey, fetchFn, ttl = null) {
        const cached = this._apiCache.get(cacheKey);
        const now = Date.now();

        // Return cached data if fresh
        if (cached && (now - cached.timestamp) < (ttl || this._cacheTTL[cacheKey] || 30000)) {
            return cached.data;
        }

        // Fetch fresh data
        const data = await fetchFn();

        // Store in cache with timestamp
        this._apiCache.set(cacheKey, {
            data,
            timestamp: now
        });

        return data;
    }

    // Invalidate specific cache entry
    invalidateCache(cacheKey) {
        this._apiCache.delete(cacheKey);
    }

    // Invalidate all cache entries
    clearCache() {
        this._apiCache.clear();
    }

    // Memoize a pure function (cache computed values)
    memoize(fn, keyFn = (...args) => JSON.stringify(args)) {
        const cache = new Map();

        return function (...args) {
            const key = keyFn(...args);

            if (cache.has(key)) {
                return cache.get(key);
            }

            const result = fn.apply(this, args);
            cache.set(key, result);
            return result;
        };
    }

    setupEventListeners() {
        // Delegated click handler for navigation buttons
        const clickHandler = e => {
            const btn = e.target.closest('[data-section], [data-category]');
            if (!btn) return;

            if (btn.dataset.section) this.switchView('section', btn.dataset.section);
            if (btn.dataset.category) this.switchView('category', btn.dataset.category);
        };

        document.addEventListener('click', clickHandler, { signal: this.abortController.signal });
        this.eventListeners.push({ element: document, event: 'click', handler: clickHandler });

        // Delegated change handler for all toggle switches
        const toggleHandler = e => {
            const toggle = e.target.closest('.toggle-switch input[type="checkbox"]');
            if (!toggle) return;

            const toggleSwitch = toggle.closest('.toggle-switch');
            const { toggleType, deviceId, metricName, endpointId } = toggleSwitch.dataset;
            const checked = toggle.checked;

            // Route to appropriate handler based on toggle type
            switch (toggleType) {
                case 'device':
                    this.toggleDevice(deviceId, checked);
                    break;
                case 'metric':
                    this.toggleMetric(deviceId, metricName, checked);
                    break;
                case 'optimizer-group':
                    this.toggleGroup(checked);
                    break;
                case 'optimizer-metric':
                    this.toggleGroupMetric(metricName, checked);
                    break;
                case 'endpoint':
                    this.toggleEndpoint(endpointId, checked, e);
                    break;
                case 'modbus-device':
                    this.toggleModbusDevice(deviceId, checked);
                    break;
                case 'modbus-metric':
                    this.toggleModbusMetric(deviceId, metricName, checked);
                    break;
                case 'gme':
                    this.toggleGME();
                    break;
            }
        };

        document.addEventListener('change', toggleHandler, { signal: this.abortController.signal });
        this.eventListeners.push({ element: document, event: 'change', handler: toggleHandler });

        const connectionInterval = setInterval(() => this.updateConnectionStatus(), 30000);
        this.intervals.push(connectionInterval);
    }

    switchView(type, value) {
        const selector = type === 'section' ? '.nav-btn' : '.category-btn';
        const contentSelector = type === 'section' ? '.content-section' : null;

        // Update buttons
        $$(selector).forEach(btn => {
            toggleClass(btn, 'active', btn.dataset[type] === value);
        });

        // Update content sections
        if (contentSelector) {
            $$(contentSelector).forEach(sec => {
                toggleClass(sec, 'active', sec.id === `${value}-section`);
            });
        }

        this.state[type] = value;
        if (type === 'category') {
            this.renderEndpoints();
            this.renderModbus();
        }
    }

    async loadData() {
        try {
            const [devices, endpoints, modbus, config] = await Promise.all([
                this.getCached('devices', () => this.apiCall('GET', '/api/sources?type=web')),
                this.getCached('endpoints', () => this.apiCall('GET', '/api/sources?type=api')),
                this.getCached('modbus', () => this.apiCall('GET', '/api/sources?type=modbus')),
                this.getCached('config', () => this.apiCall('GET', '/api/config'))
            ]);

            Object.assign(this.state, { devices, endpoints, modbus, config });

            // Load GME toggle state
            this.loadGMEState();
            this._invalidateOptimizerCache();

            const editor = $('#yamlEditor');
            if (editor) {
                YAMLConfig.loadFile('main');
            }
        } catch (error) {
            if (error.name === 'AbortError') {
                console.log('Data loading aborted');
                return;
            }
            await this.handleError(error, 'loading data', 'Errore nel caricamento dati');
        }
    }

    render() {
        this.renderDevices();
        this.renderEndpoints();
        this.renderModbus();
    }

    renderDevices() {
        const container = $('#devicesGrid');
        if (!container) return;

        // Use cached optimizer check for O(1) lookups
        const { optimizers, others } = Object.entries(this.state.devices).reduce((acc, [id, data]) => {
            // Skip invalid entries
            if (!id || !data) return acc;
            const key = this.isOptimizer(id) ? 'optimizers' : 'others';
            acc[key][id] = data;
            return acc;
        }, { optimizers: {}, others: {} });

        // Use DocumentFragment for batch DOM insertions (optimized)
        const fragment = document.createDocumentFragment();
        let delay = 0;

        Object.entries(others).forEach(([id, data]) => {
            const card = this.createDeviceCard(id, data);
            animateElement(card, 'slide-in', delay += 100);
            fragment.appendChild(card);
        });

        if (Object.keys(optimizers).length) {
            const card = this.createOptimizersCard(optimizers);
            animateElement(card, 'slide-in', delay += 100);
            fragment.appendChild(card);
        }

        container.replaceChildren(fragment);
    }

    // Helper: Create device header HTML
    createDeviceHeader(id, data, type) {
        return `
            <div class="device-header">
                <div class="device-info">
                    <div class="device-title">${data.device_name || id}</div>
                    <div class="device-type">${type}</div>
                    ${data.device_id ? `<div class="device-id">ID: ${data.device_id}</div>` : ''}
                </div>
                ${this.createToggle(data.enabled, 'device', { deviceId: id }, '', `Abilita device ${data.device_name || id}`)}
            </div>
        `;
    }

    createDeviceCard(id, data) {
        const card = document.createElement('div');
        card.className = 'device-card';
        card.dataset.deviceId = id;

        const type = data.device_type || this.inferDeviceType(id);
        const metrics = Object.entries(data.measurements || {});

        card.innerHTML = `
            ${this.createDeviceHeader(id, data, type)}
            ${metrics.length ? this.createMetricsSection(id, metrics) : ''}
        `;

        return card;
    }

    createOptimizersCard(optimizers) {
        const card = document.createElement('div');
        card.className = 'device-card optimizers-card';
        card.dataset.deviceId = 'optimizers-group';

        const opts = Object.values(optimizers);
        const enabled = opts.filter(o => o.enabled).length;
        const total = opts.length;
        const allEnabled = opts.every(o => o.enabled);
        const metrics = Object.keys(opts[0]?.measurements || {}).map(name => {
            const count = opts.filter(o => o.measurements?.[name]?.enabled).length;
            return { name, enabled: count > 0, count };
        });

        card.innerHTML = `
            <div class="device-header">
                <div class="device-info">
                    <div class="device-title">🔧 Power Optimizers (${total})</div>
                    <div class="device-type">OPTIMIZER GROUP</div>
                    <div class="device-stats"><span class="stat">Attivi: ${enabled}/${total}</span></div>
                </div>
                ${this.createToggle(allEnabled, 'optimizer-group', {}, '', 'Abilita tutti gli optimizer')}
            </div>
            <div class="device-metrics">
                <h4>📊 Metriche Comuni (${metrics.length})</h4>
                <div class="metrics-list">
                    ${metrics.map(m => `
                        <div class="metric-item">
                            <div class="metric-info">
                                <span class="metric-name">${this.formatMetricName(m.name)}</span>
                                <span class="metric-count">${m.count}/${total} optimizer</span>
                            </div>
                            ${this.createToggle(m.enabled, 'optimizer-metric', { metricName: m.name }, 'metric-toggle')}
                        </div>
                    `).join('')}
                </div>
            </div>
        `;

        return card;
    }

    createMetricsSection(deviceId, metrics) {
        return `
            <div class="device-metrics">
                <h4>📊 Metriche (${metrics.length})</h4>
                <div class="metrics-list">
                    ${metrics.map(([name, data]) => `
                        <div class="metric-item" data-metric="${name}">
                            <div class="metric-info">
                                <span class="metric-name">${this.formatMetricName(name)}</span>
                            </div>
                            ${this.createToggle(data.enabled, 'metric', { deviceId, metricName: name }, 'metric-toggle', `Abilita metrica ${name}`)}
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    createToggle(checked, toggleType, dataAttrs = {}, extraClass = '', ariaLabel = 'Toggle') {
        const dataAttrStr = this.generateDataAttrs(dataAttrs);

        return `
            <label class="toggle-switch ${extraClass}" role="switch" aria-checked="${checked}" aria-label="${ariaLabel}" data-toggle-type="${toggleType}" ${dataAttrStr}>
                <input type="checkbox" ${checked ? 'checked' : ''} aria-hidden="true">
                <span class="toggle-slider" aria-hidden="true"></span>
            </label>
        `;
    }

    renderEndpoints() {
        const container = $('#endpointsGrid');
        if (!container) return;

        const filtered = Object.entries(this.state.endpoints).filter(([_, data]) => {
            if (this.state.category === 'all') return true;
            return data.category === this.state.category;
        });

        // Use DocumentFragment for batch DOM insertions (optimized)
        const fragment = document.createDocumentFragment();

        filtered.forEach(([id, data], i) => {
            const card = this.createEndpointCard(id, data);
            animateElement(card, 'slide-in', i * 80);
            fragment.appendChild(card);
        });

        container.replaceChildren(fragment);
    }

    createEndpointCard(id, data) {
        const card = document.createElement('div');
        card.className = 'endpoint-card';

        const category = data.category || 'Info';
        const icon = this.getCategoryIcon(category);

        card.innerHTML = `
            <div class="endpoint-header">
                <div class="endpoint-name">${id}</div>
                <div class="endpoint-format">
                    <span class="format-icon">${icon}</span>
                    <span class="format-label">${category}</span>
                </div>
                ${this.createToggle(data.enabled, 'endpoint', { endpointId: id })}
            </div>
            <div class="endpoint-description">${data.description || 'Nessuna descrizione disponibile'}</div>
            <div class="endpoint-meta">
                <span class="endpoint-category">Formato: ${data.data_format === 'structured' ? 'Strutturato' : 'JSON'}</span>
            </div>
            <div class="endpoint-status ${data.enabled ? 'enabled' : 'disabled'}">
                ${data.enabled ? 'Abilitato' : 'Disabilitato'}
            </div>
        `;

        return card;
    }

    renderModbus() {
        const container = $('#modbusGrid');
        if (!container) return;

        const filtered = Object.entries(this.state.modbus).filter(([_, data]) => {
            if (this.state.category === 'all') return true;
            return data.category === this.state.category;
        });

        // Use DocumentFragment for batch DOM insertions (optimized)
        const fragment = document.createDocumentFragment();

        filtered.forEach(([id, data], i) => {
            const card = this.createModbusCard(id, data);
            animateElement(card, 'slide-in', i * 80);
            fragment.appendChild(card);
        });

        container.replaceChildren(fragment);
    }

    createModbusCard(id, data) {
        const card = document.createElement('div');
        card.className = 'device-card modbus-card';
        card.dataset.deviceId = id;

        const category = data.category || 'Modbus';
        const deviceType = data.device_type || 'Unknown';
        const metrics = Object.entries(data.measurements || {});
        const categoryIcon = this.getModbusCategoryIcon(category);

        card.innerHTML = `
            <div class="device-header">
                <div class="device-info">
                    <div class="device-title">${categoryIcon} ${data.device_name || id}</div>
                    <div class="device-type">${deviceType} - ${category}</div>
                    ${data.device_id ? `<div class="device-id">Unit: ${data.device_id}</div>` : ''}
                </div>
                ${this.createToggle(data.enabled, 'modbus-device', { deviceId: id })}
            </div>
            ${metrics.length ? this.createModbusMetricsSection(id, metrics) : ''}
        `;

        return card;
    }

    createModbusMetricsSection(deviceId, metrics) {
        return `
            <div class="device-metrics">
                <h4>📊 Metriche Modbus (${metrics.length})</h4>
                <div class="metrics-list">
                    ${metrics.map(([name, data]) => `
                        <div class="metric-item" data-metric="${name}">
                            <div class="metric-info">
                                <span class="metric-name">${this.formatMetricName(name)}</span>
                                <span class="metric-description">${data.description || ''}</span>
                                ${data.unit ? `<span class="metric-unit">${data.unit}</span>` : ''}
                            </div>
                            ${this.createToggle(data.enabled, 'modbus-metric', { deviceId, metricName: name }, 'metric-toggle')}
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }



    async toggleDevice(id, enabled) {
        if (!this.validateId(id, 'device')) return;
        try {
            const data = await this.apiCall('POST', `/api/devices/toggle?id=${id}`);
            Object.assign(this.state.devices[id], data);
            this.updateDeviceUI(id, data);
            this.invalidateCache('devices'); // Invalidate cache after modification
            this.notify(`Device ${id} ${enabled ? 'abilitato' : 'disabilitato'}`, 'success');
        } catch (error) {
            if (error.name !== 'AbortError') {
                await this.handleError(error, `toggling device ${id}`);
            }
        }
    }

    async toggleMetric(deviceId, metric, enabled) {
        if (!this.validateId(deviceId, 'device') || !this.validateMetric(metric)) return;
        try {
            const data = await this.apiCall('POST', `/api/devices/metrics/toggle?id=${deviceId}&metric=${metric}`);

            if (!this.state.devices[deviceId].measurements) {
                this.state.devices[deviceId].measurements = {};
            }
            this.state.devices[deviceId].measurements[metric] = { enabled: data.enabled };

            if (data.device_changed) {
                this.state.devices[deviceId].enabled = data.device_enabled;
            }

            this.updateDeviceUI(deviceId, {
                enabled: data.device_enabled,
                measurements: this.state.devices[deviceId].measurements
            });

            this.updateGroupUI();
            this.invalidateCache('devices'); // Invalidate cache after modification

            let message = `Metrica ${metric.replace(/_/g, ' ')} ${enabled ? 'abilitata' : 'disabilitata'}`;
            if (data.device_changed) {
                message += ` (device auto-${data.device_enabled ? 'abilitato' : 'disabilitato'})`;
            }
            this.notify(message, 'success');
        } catch (error) {
            if (error.name !== 'AbortError') {
                await this.handleError(error, `toggling metric ${deviceId}.${metric}`);
            }
        }
    }

    async toggleGroup(enabled) {
        const optimizers = this.getOptimizers();
        await Promise.all(optimizers.map(async id => {
            try {
                const data = await this.apiCall('POST', `/api/devices/toggle?id=${id}`);
                Object.assign(this.state.devices[id], data);
                this.updateDeviceUI(id, data);
            } catch (e) {
                if (e.name !== 'AbortError') {
                    console.warn(`Failed to toggle optimizer ${id}:`, e);
                }
            }
        }));
        this.updateGroupUI();
        this.invalidateCache('devices'); // Invalidate cache after modification
        this.notify(`Gruppo optimizers ${enabled ? 'abilitato' : 'disabilitato'}`, 'success');
    }

    async toggleGroupMetric(metric, enabled) {
        if (!this.validateMetric(metric)) return;
        const optimizers = this.getOptimizers();
        await Promise.all(optimizers.map(async id => {
            if (!this.state.devices[id].measurements?.[metric]) return;
            try {
                const data = await this.apiCall('POST', `/api/devices/metrics/toggle?id=${id}&metric=${metric}`);
                if (data) {
                    if (!this.state.devices[id].measurements) {
                        this.state.devices[id].measurements = {};
                    }
                    this.state.devices[id].measurements[metric] = { enabled: data.enabled };

                    if (data.device_changed) {
                        this.state.devices[id].enabled = data.device_enabled;
                    }

                    this.updateDeviceUI(id, {
                        enabled: data.device_enabled,
                        measurements: this.state.devices[id].measurements
                    });
                }
            } catch (e) {
                if (e.name !== 'AbortError') {
                    console.warn(`Failed to toggle metric ${metric} for optimizer ${id}:`, e);
                }
            }
        }));
        this.updateGroupUI();
        this.invalidateCache('devices'); // Invalidate cache after modification

        const optimizerCount = optimizers.length;
        this.notify(`Metrica ${metric.replace(/_/g, ' ')} ${enabled ? 'abilitata' : 'disabilitata'} su ${optimizerCount} optimizer`, 'success');
    }

    async toggleEndpoint(id, enabled, event) {
        if (!this.validateId(id, 'endpoint')) return;
        try {
            const data = await this.apiCall('POST', `/api/endpoints/toggle?id=${id}`);
            this.state.endpoints[id].enabled = data.enabled;

            const card = event.target.closest('.endpoint-card');
            const status = card.querySelector('.endpoint-status');
            status.textContent = enabled ? 'Abilitato' : 'Disabilitato';
            status.className = `endpoint-status ${enabled ? 'enabled' : 'disabled'}`;

            this.invalidateCache('endpoints'); // Invalidate cache after modification
            this.notify(`Endpoint ${id} ${enabled ? 'abilitato' : 'disabilitato'}`, 'success');
        } catch (error) {
            if (error.name !== 'AbortError') {
                await this.handleError(error, 'toggling endpoint');
            }
        }
    }

    async toggleModbusDevice(id, enabled) {
        if (!this.validateId(id, 'modbus device')) return;
        try {
            const data = await this.apiCall('POST', `/api/modbus/devices/toggle?id=${id}`);
            Object.assign(this.state.modbus[id], data);
            this.updateModbusDeviceUI(id, data);
            this.invalidateCache('modbus'); // Invalidate cache after modification
            this.notify(`Device Modbus ${id} ${enabled ? 'abilitato' : 'disabilitato'}`, 'success');
        } catch (error) {
            if (error.name !== 'AbortError') {
                await this.handleError(error, `toggling modbus device ${id}`);
            }
        }
    }

    async toggleModbusMetric(deviceId, metric, enabled) {
        if (!this.validateId(deviceId, 'modbus device') || !this.validateMetric(metric)) return;
        try {
            const data = await this.apiCall('POST', `/api/modbus/devices/metrics/toggle?id=${deviceId}&metric=${metric}`);

            if (!this.state.modbus[deviceId].measurements) {
                this.state.modbus[deviceId].measurements = {};
            }
            this.state.modbus[deviceId].measurements[metric] = { enabled: data.enabled };
            this.state.modbus[deviceId].enabled = data.device_enabled;

            this.updateModbusDeviceUI(deviceId, {
                enabled: data.device_enabled,
                measurements: { [metric]: { enabled: data.enabled } }
            });

            this.invalidateCache('modbus'); // Invalidate cache after modification

            let message = `Metrica Modbus ${metric.replace(/_/g, ' ')} ${data.enabled ? 'abilitata' : 'disabilitata'}`;
            if (data.device_changed) {
                message += ` (device auto-${data.device_enabled ? 'abilitato' : 'disabilitato'})`;
            }
            this.notify(message, 'success');
        } catch (error) {
            if (error.name !== 'AbortError') {
                await this.handleError(error, `toggling modbus metric ${deviceId}.${metric}`);
            }
        }
    }

    validateId(id, context) {
        if (!id || typeof id !== 'string') {
            this.log('error', `Invalid ID in ${context}: ${id}`);
            this.notify(`ID non valido in ${context}`, 'error');
            return false;
        }
        return true;
    }

    validateMetric(metric) {
        if (!metric || typeof metric !== 'string') {
            this.log('error', `Invalid metric: ${metric}`);
            return false;
        }
        return true;
    }

    // Invalidate optimizer cache when devices change
    _invalidateOptimizerCache() {
        this._optimizersCache = null;
        this._optimizersSet = null;
    }

    // Get optimizers list (cached for performance)
    getOptimizers() {
        if (this._optimizersCache === null) {
            this._optimizersCache = Object.keys(this.state.devices).filter(id =>
                id.includes('optimizer') ||
                this.state.devices[id].device_type === 'OPTIMIZER' ||
                this.state.devices[id].device_type === 'Optimizer'
            );
            // Also build Set for O(1) lookups
            this._optimizersSet = new Set(this._optimizersCache);
        }
        return this._optimizersCache;
    }

    // Check if device is optimizer (O(1) lookup using Set)
    isOptimizer(id) {
        // Safety check for undefined/null IDs
        if (!id || typeof id !== 'string') {
            return false;
        }
        if (this._optimizersSet === null) {
            this.getOptimizers(); // Build cache if needed
        }
        return this._optimizersSet.has(id);
    }

    // Memoized device type inference (pure function)
    inferDeviceType = this.memoize((id) => {
        // Lookup table for device type inference
        const typePatterns = {
            'inverter': 'INVERTER',
            'meter': 'METER',
            'site': 'SITE',
            'weather': 'WEATHER'
        };

        // Find first matching pattern
        const matchedType = Object.entries(typePatterns).find(([pattern]) => id.includes(pattern));
        return matchedType ? matchedType[1] : 'DEVICE';
    });

    // Memoized category icon lookup (pure function)
    getCategoryIcon = this.memoize((category) => {
        const CATEGORY_ICONS = {
            'Info': 'ℹ️',
            'Inverter': '⚡',
            'Meter': '📊',
            'Flusso': '🔄'
        };
        return CATEGORY_ICONS[category] || '❓';
    });

    // Memoized modbus category icon lookup (pure function)
    getModbusCategoryIcon = this.memoize((category) => {
        const MODBUS_CATEGORY_ICONS = {
            'Inverter': '🔋',
            'Meter': '⚡',
            'Battery': '🔋'
        };
        return MODBUS_CATEGORY_ICONS[category] || '⚡';
    });

    // Memoized flow icon lookup (pure function)
    getFlowIcon = this.memoize((flowType) => {
        const FLOW_ICONS = {
            'api': '🌐',
            'web': '🔌',
            'realtime': '⚡',
            'gme': '💰',
            'general': 'ℹ️'
        };
        return FLOW_ICONS[flowType] || 'ℹ️';
    });

    // Memoized filter name lookup (pure function)
    getFilterName = this.memoize((flow) => {
        const FILTER_NAMES = {
            'all': 'Tutti',
            'api': 'API',
            'web': 'Web',
            'realtime': 'Realtime',
            'gme': 'GME',
            'general': 'Sistema'
        };
        return FILTER_NAMES[flow] || flow;
    });

    // Memoized metric name formatting (pure function)
    formatMetricName = this.memoize((name) => {
        return name.replace(/_/g, ' ');
    });

    // Memoized data attribute string generation (pure function)
    generateDataAttrs = this.memoize((dataAttrs) => {
        const toKebabCase = str => str.replace(/([A-Z])/g, '-$1').toLowerCase();
        return Object.entries(dataAttrs)
            .map(([key, value]) => `data-${toKebabCase(key)}="${value}"`)
            .join(' ');
    }, (dataAttrs) => JSON.stringify(dataAttrs));

    // Memoized stats formatting (pure function) - formato verticale con allineamento
    formatStats = this.memoize((stat) => {
        if (!stat) {
            return this.createStatHTML('▶️', 0, '✅', 0, '❌', 0);
        }
        const exec = stat.executed || 0;
        const succ = stat.success || 0;
        const fail = stat.failed || 0;
        return this.createStatHTML('▶️', exec, '✅', succ, '❌', fail);
    }, (stat) => JSON.stringify(stat));

    createStatHTML(icon1, val1, icon2, val2, icon3, val3) {
        return `<span style="display:flex;justify-content:space-between;width:100%"><span>${icon1}</span><span>${val1}</span></span>` +
            `<span style="display:flex;justify-content:space-between;width:100%"><span>${icon2}</span><span>${val2}</span></span>` +
            `<span style="display:flex;justify-content:space-between;width:100%"><span>${icon3}</span><span>${val3}</span></span>`;
    }

    updateDeviceUI(id, data) {
        const card = $(`[data-device-id="${id}"]`);
        if (!card) return;

        // Update device toggle
        const deviceToggle = $('.device-header input', card);
        if (deviceToggle) deviceToggle.checked = data.enabled;

        // Update metric toggles
        if (data.measurements) {
            Object.entries(data.measurements).forEach(([metric, metricData]) => {
                const metricToggle = $(`[data-metric="${metric}"] input`, card);
                if (metricToggle) metricToggle.checked = metricData.enabled;
            });
        }

        // Invalidate cache if this is an optimizer
        if (this.isOptimizer(id)) {
            this._invalidateOptimizerCache();
        }
    }

    updateGroupUI() {
        const card = $('[data-device-id="optimizers-group"]');
        if (!card) return;

        const optimizers = this.getOptimizers();
        const opts = optimizers.map(id => this.state.devices[id]).filter(Boolean);
        const enabled = opts.filter(o => o.enabled).length;
        const total = opts.length;
        const allEnabled = opts.every(o => o.enabled);

        const mainToggle = $('.device-header input', card);
        if (mainToggle) mainToggle.checked = allEnabled;

        const stats = $('.device-stats .stat', card);
        if (stats) setTextContent(stats, `Attivi: ${enabled}/${total}`);

        const metrics = opts.length > 0 ? Object.keys(opts[0].measurements || {}) : [];

        $$('.metric-item', card).forEach((item, index) => {
            if (index >= metrics.length) return;

            const metric = metrics[index];
            const count = opts.filter(o => o.measurements?.[metric]?.enabled).length;

            const input = $('input', item);
            if (input) input.checked = count > 0;

            const counter = $('.metric-count', item);
            if (counter) setTextContent(counter, `${count}/${total} optimizer`);
        });
    }

    updateModbusDeviceUI(id, data) {
        const card = $(`[data-device-id="${id}"]`);
        if (!card) return;

        const deviceToggle = $('.device-header input', card);
        if (deviceToggle) deviceToggle.checked = data.enabled;

        if (data.measurements) {
            Object.entries(data.measurements).forEach(([metric, metricData]) => {
                const metricToggle = $(`[data-metric="${metric}"] input`, card);
                if (metricToggle) metricToggle.checked = metricData.enabled;
            });
        }
    }

    async updateConnectionStatus() {
        try {
            await this.apiCall('GET', '/api/ping');
            const el = $('#connectionStatus');
            updateElement(el, {
                text: 'Online',
                class: 'stat-value online'
            });
            this.state.connectionStatus = 'online';
        } catch (error) {
            // Only log connection errors if we were previously online to avoid spam
            if (this.state.connectionStatus !== 'offline' && error.name !== 'AbortError') {
                console.error('Connection lost:', error);
            }
            const el = $('#connectionStatus');
            updateElement(el, {
                text: 'Offline',
                class: 'stat-value offline'
            });
            this.state.connectionStatus = 'offline';
        }
    }

    notify(message, type = 'info') {
        // Delegate to global notify function from notification-utils.js
        notify(message, type);
    }

    startLoopMonitoring() {
        const baseInterval = 5000;
        let pollMultiplier = 1;
        let timeoutId = null;

        const visibilityHandler = () => {
            pollMultiplier = document.hidden ? 10 : 1;
        };
        document.addEventListener('visibilitychange', visibilityHandler, { signal: this.abortController.signal });
        this.eventListeners.push({ element: document, event: 'visibilitychange', handler: visibilityHandler });

        const poll = async () => {
            try {
                await this.updateLoopStatus();
                pollMultiplier = 1;
            } catch (error) {
                if (error.name === 'AbortError') return;
                pollMultiplier = Math.min(pollMultiplier * 2, 10);
                console.error('Error in loop monitoring, backing off:', error);
            }

            timeoutId = setTimeout(poll, baseInterval * pollMultiplier);
            this.intervals.push(timeoutId);
        };

        poll();
    }

    async updateLoopStatus() {
        try {
            const data = await this.getCached('loop-status', () => this.apiCall('GET', '/api/loop/status'));
            const previousLoopMode = this.state.loopStatus?.loop_mode;

            this.state.loopStatus = data;
            this.renderLoopStatus();

            if (previousLoopMode !== data.loop_mode) {
                console.log(`Loop state changed: ${previousLoopMode} -> ${data.loop_mode}`);
            }
        } catch (error) {
            if (error.name !== 'AbortError') {
                console.error('Error updating loop status:', error);
            }
        }
    }


    renderLoopStatus() {
        if (!this.state.loopStatus) return;

        const { loop_mode, stats } = this.state.loopStatus;

        const statusEl = document.getElementById('loopStatus');
        if (statusEl) {
            statusEl.textContent = loop_mode ? 'Running' : 'Standalone';
            statusEl.className = `stat-value ${loop_mode ? 'running' : 'stopped'}`;
        }

        if (loop_mode && stats) {
            // Calcola totale runs
            const totalRuns = (stats.api_stats?.executed || 0) +
                (stats.web_stats?.executed || 0) +
                (stats.realtime_stats?.executed || 0) +
                (stats.gme_stats?.executed || 0);

            // Scheduling info (intervalli configurati su righe separate)
            const scheduling = 'API/Web: 15m\nRealtime: 5s\nGME: 24h';

            const elements = {
                'loopUptime': stats.uptime_formatted || '--',
                'apiRuns': this.formatStats(stats.api_stats),
                'webRuns': this.formatStats(stats.web_stats),
                'realtimeRuns': this.formatStats(stats.realtime_stats),
                'gmeRuns': this.formatStats(stats.gme_stats),
                'totalRuns': totalRuns,
                'loopScheduling': scheduling
            };

            Object.entries(elements).forEach(([id, value]) => {
                const el = document.getElementById(id);
                if (el) {
                    // Per le stats dei flow, usa innerHTML per supportare HTML
                    if (['apiRuns', 'webRuns', 'realtimeRuns', 'gmeRuns'].includes(id)) {
                        el.innerHTML = value;
                    } else {
                        el.textContent = value;
                    }
                }
            });

            // Update timing (con "next:")
            if (stats.api_next_run) {
                const el = document.getElementById('apiTiming');
                if (el) el.textContent = `next: ${stats.api_next_run}`;
            }

            if (stats.web_next_run) {
                const el = document.getElementById('webTiming');
                if (el) el.textContent = `next: ${stats.web_next_run}`;
            }

            if (stats.gme_next_run) {
                const el = document.getElementById('gmeTiming');
                if (el) el.textContent = `next: ${stats.gme_next_run}`;
            }

            // Realtime next (calcola prossima esecuzione basata su 5s, con "next:")
            const realtimeTimingEl = document.getElementById('realtimeTiming');
            if (realtimeTimingEl) {
                const now = new Date();
                const nextRealtime = new Date(now.getTime() + 5000);
                const nextStr = nextRealtime.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
                realtimeTimingEl.textContent = `next: ${nextStr}`;
            }
        }

        updateLoopButtons(loop_mode);
    }

    // GME Methods
    loadGMEState() {
        const gmeToggle = $('#gmeToggle');
        if (gmeToggle && this.state.config && this.state.config.gme) {
            gmeToggle.checked = this.state.config.gme.enabled || false;
        }
    }

    async toggleGME() {
        const gmeToggle = $('#gmeToggle');
        if (!gmeToggle) return;

        try {
            const response = await this.apiCall('POST', '/api/gme/toggle');

            if (response.status === 'success') {
                gmeToggle.checked = response.enabled;
                this.notify(`GME ${response.enabled ? 'abilitato' : 'disabilitato'}`, 'success');

                // Update config state
                if (!this.state.config.gme) {
                    this.state.config.gme = {};
                }
                this.state.config.gme.enabled = response.enabled;

                // Invalidate config cache
                this.invalidateCache('config');
            } else {
                this.notify('Errore toggle GME', 'error');
                // Revert toggle
                gmeToggle.checked = !gmeToggle.checked;
            }
        } catch (error) {
            console.error('Error toggling GME:', error);
            this.notify('Errore toggle GME', 'error');
            // Revert toggle
            gmeToggle.checked = !gmeToggle.checked;
        }
    }
}

// ===== YAML CONFIG =====
const YAMLConfig = {
    currentFile: 'main',

    async validate() {
        const editor = document.getElementById('yamlEditor');
        try {
            if (this.currentFile === 'env') {
                if (editor.value.trim()) {
                    this.setStatus('✅ File .env valido', 'success');
                } else {
                    this.setStatus('⚠️ File .env vuoto', 'warning');
                }
            } else {
                jsyaml.load(editor.value);
                this.setStatus('✅ YAML valido', 'success');
            }
        } catch (error) {
            this.setStatus(`❌ Errore YAML: ${error.message}`, 'error');
        }
    },

    async refresh() {
        try {
            await this.loadFile(this.currentFile);
            this.setStatus('🔄 Configurazione ricaricata', 'info');
            dashboard.notify('Configurazione ricaricata', 'success');
        } catch (error) {
            console.error('Error refreshing config:', error);
            this.setStatus('❌ Errore nel caricamento', 'error');
            dashboard.notify('Errore nel ricaricamento', 'error');
        }
    },

    async save() {
        try {
            const editor = document.getElementById('yamlEditor');
            const content = editor.value;

            if (this.currentFile !== 'env') jsyaml.load(content);

            const result = await apiPost('/api/config/yaml', {
                file: this.currentFile,
                content: content
            });

            this.setStatus(`✅ ${result.message}`, 'success');
            dashboard.notify(`File ${this.currentFile} salvato`, 'success');
        } catch (error) {
            this.setStatus(`❌ Errore salvataggio: ${error.message}`, 'error');
            dashboard.notify('Errore nel salvataggio', 'error');
        }
    },

    async loadFile(fileType) {
        try {
            const result = await apiGet(`/api/config/yaml?file=${fileType}`);

            const editor = document.getElementById('yamlEditor');
            editor.value = result.content;
            this.currentFile = fileType;
            this.setStatus(`📄 Caricato: ${result.path}`, 'info');
        } catch (error) {
            this.setStatus(`❌ Errore caricamento: ${error.message}`, 'error');
        }
    },

    setStatus(text, type) {
        const status = document.getElementById('configStatus');
        status.textContent = text;
        status.className = `config-status ${type}`;
    }
};

// Global functions for inline handlers
const validateYAML = () => YAMLConfig.validate();
const refreshConfig = () => YAMLConfig.refresh();
const saveConfig = () => YAMLConfig.save();
const loadSelectedYaml = () => {
    const select = document.getElementById('yamlFileSelect');
    YAMLConfig.loadFile(select.value);
};

// Loop control functions
const startLoop = async () => {
    try {
        await apiPost('/api/loop/start');
        dashboard.notify('Loop avviato con successo', 'success');
        updateLoopButtons(true);
        // Non aggiorniamo più i log automaticamente
    } catch (error) {
        dashboard.notify(`Errore avvio loop: ${error.message}`, 'error');
    }
};

const stopLoop = async () => {
    if (!confirm('Sei sicuro di voler fermare il loop?')) {
        return;
    }

    try {
        await apiPost('/api/loop/stop');
        dashboard.notify('Loop fermato con successo', 'success');
        updateLoopButtons(false);
        // Non aggiorniamo più i log automaticamente
    } catch (error) {
        dashboard.notify(`Errore stop loop: ${error.message}`, 'error');
    }
};

const updateLoopButtons = (isRunning) => {
    const startBtn = document.getElementById('startBtn');
    const stopBtn = document.getElementById('stopBtn');

    if (startBtn) startBtn.disabled = isRunning;
    if (stopBtn) stopBtn.disabled = !isRunning;
};

// ===== LOG TAB FILTERING ===== (FIXED: cleanup tracking)
let currentLogFlow = 'all';
let autoScrollEnabled = true;
let logUpdateInterval = null;

// Lookup table for filter names (defined at module level)
const FILTER_NAMES = {
    'all': 'Tutti',
    'api': 'API',
    'web': 'Web',
    'realtime': 'Realtime',
    'gme': 'GME',
    'general': 'Sistema'
};

// Log cache and index for faster filtering (O(1) lookups)
let logCache = {
    logs: [],           // All logs
    byFlow: new Map(),  // Index by flow type for O(1) filtering
    lastUpdate: 0       // Timestamp of last update
};

function switchLogTab(flow) {
    currentLogFlow = flow;

    $$('.log-tab').forEach(tab => {
        toggleClass(tab, 'active', tab.dataset.flow === flow);
    });

    const filterName = dashboard ? dashboard.getFilterName(flow) : (FILTER_NAMES[flow] || flow);
    setTextContent($('#logsFilter'), `Filtro: ${filterName}`);

    // Update log info message based on flow type
    const logsInfoEl = $('#logsInfo');
    if (logsInfoEl) {
        if (flow === 'all') {
            setTextContent(logsInfoEl, '📅 Log ultimi 24h');
        } else if (flow === 'general') {
            setTextContent(logsInfoEl, '♾️ Log mai resettati');
        } else {
            setTextContent(logsInfoEl, '📊 Mostrando ultime 3 run per flow');
        }
    }

    // Always show cached data immediately if available (even if not fresh)
    // This prevents the "Nessun log disponibile" flash when switching tabs
    if (logCache.logs.length > 0) {
        const filteredLogs = getFilteredLogsFromCache(flow);
        renderFilteredLogs(filteredLogs, filteredLogs.length, null);
    }

    // Then fetch fresh data from server (will update the display when ready)
    loadFilteredLogs();

    if (!logUpdateInterval) {
        logUpdateInterval = setInterval(loadFilteredLogs, 3000);
        if (dashboard) {
            dashboard.intervals.push(logUpdateInterval);
        }
    }
}

// Build index for logs by flow type (O(n) build, O(1) lookups)
function indexLogs(logs) {
    const byFlow = new Map();

    // Initialize all flow types
    Object.keys(FILTER_NAMES).forEach(flow => {
        if (flow !== 'all') byFlow.set(flow, []);
    });

    // Index logs by flow type
    logs.forEach(log => {
        const flowType = log.flow_type || 'general';
        if (!byFlow.has(flowType)) {
            byFlow.set(flowType, []);
        }
        byFlow.get(flowType).push(log);
    });

    return byFlow;
}

// Get filtered logs from cache (O(1) lookup using index)
function getFilteredLogsFromCache(flow) {
    if (flow === 'all') {
        return logCache.logs;
    }
    return logCache.byFlow.get(flow) || [];
}

// Check if cache is fresh (less than 3 seconds old)
function isCacheFresh() {
    return (Date.now() - logCache.lastUpdate) < 3000;
}

async function loadFilteredLogs() {
    try {
        const data = await apiGet(`/api/loop/logs?flow=${currentLogFlow}&limit=500`);

        // Update cache with indexed logs for faster future filtering
        logCache.logs = data.logs;
        logCache.byFlow = indexLogs(data.logs);
        logCache.lastUpdate = Date.now();

        renderFilteredLogs(data.logs, data.total, data.run_counts);
    } catch (error) {
        console.error('Error loading filtered logs:', error);
    }
}

// Helper: Create empty log entry
function createEmptyLogEntry() {
    const entry = document.createElement('div');
    entry.className = 'log-entry info';
    const message = document.createElement('span');
    message.className = 'log-message';
    message.textContent = 'Nessun log disponibile per questo filtro';
    entry.appendChild(message);
    return entry;
}

// Lookup table for flow icons (defined at module level for reuse)
const FLOW_ICONS = {
    'api': '🌐',
    'web': '🔌',
    'realtime': '⚡',
    'gme': '💰',
    'general': 'ℹ️'
};

// Helper: Create log entry element (optimized with createTextNode for safety)
function createLogEntry(log) {
    const flowType = log.flow_type || 'general';
    const entry = document.createElement('div');
    entry.className = `log-entry ${log.level.toLowerCase()}`;

    const timestamp = document.createElement('span');
    timestamp.className = 'log-timestamp';
    timestamp.appendChild(document.createTextNode(log.timestamp));

    const level = document.createElement('span');
    level.className = `log-level ${log.level.toLowerCase()}`;
    level.appendChild(document.createTextNode(log.level));

    const flow = document.createElement('span');
    flow.className = 'log-flow';
    flow.dataset.flow = flowType;
    const flowIcon = dashboard ? dashboard.getFlowIcon(flowType) : (FLOW_ICONS[flowType] || 'ℹ️');
    flow.appendChild(document.createTextNode(`${flowIcon} ${flowType.toUpperCase()}`));

    const message = document.createElement('span');
    message.className = 'log-message';
    message.appendChild(document.createTextNode(log.message));

    entry.appendChild(timestamp);
    entry.appendChild(level);
    entry.appendChild(flow);
    entry.appendChild(message);

    return entry;
}

// Helper: Update log count display
function updateLogCount(total, runCounts) {
    let countText = `${total} log visualizzati`;

    // Add context-specific suffix based on current filter
    if (currentLogFlow === 'all') {
        countText += ' (Ultimi 24h)';
    } else if (currentLogFlow === 'general') {
        countText += ' (Mai resettati)';
    } else {
        // For flow-specific tabs (api, web, realtime, gme)
        if (runCounts) {
            const totalRuns = Object.values(runCounts).reduce((sum, count) => sum + count, 0);
            if (totalRuns > 0) {
                countText += ` (Ultime ${totalRuns} run)`;
            }
        }
    }

    setTextContent($('#logsCount'), countText);
}

function renderFilteredLogs(logs, total, runCounts) {
    const container = $('#logsContent');
    if (!container || !logs) return;

    const shouldScroll = autoScrollEnabled ||
        (container.scrollTop + container.clientHeight >= container.scrollHeight - 10);

    // Use DocumentFragment for batch rendering (optimized)
    const fragment = document.createDocumentFragment();

    if (logs.length === 0) {
        fragment.appendChild(createEmptyLogEntry());
    } else {
        logs.forEach(log => fragment.appendChild(createLogEntry(log)));
    }

    // Replace all children at once with the fragment
    container.replaceChildren(fragment);
    updateLogCount(total, runCounts);

    if (shouldScroll) container.scrollTop = container.scrollHeight;
}

async function clearLogs() {
    if (!confirm('Sei sicuro di voler pulire tutti i log?')) {
        return;
    }

    try {
        await apiPost('/api/loop/logs/clear');

        const container = $('#logsContent');
        if (container) {
            setInnerHTML(container, '<div class="log-entry info"><span class="log-message">Log puliti - in attesa di nuovi log...</span></div>');
        }
        setTextContent($('#logsCount'), '0 log visualizzati');
        dashboard.notify('Log puliti con successo', 'success');
    } catch (error) {
        dashboard.notify(`Errore pulizia log: ${error.message}`, 'error');
    }
}

function toggleAutoScroll() {
    autoScrollEnabled = !autoScrollEnabled;
    const btn = document.getElementById('autoScrollBtn');
    btn.textContent = `📌 Auto-scroll: ${autoScrollEnabled ? 'ON' : 'OFF'}`;
    btn.classList.toggle('active', autoScrollEnabled);
}

window.switchLogTab = switchLogTab;
window.clearLogs = clearLogs;
window.toggleAutoScroll = toggleAutoScroll;

let dashboard;
document.addEventListener('DOMContentLoaded', () => {
    dashboard = new SolarDashboard();
    switchLogTab('all');
});
