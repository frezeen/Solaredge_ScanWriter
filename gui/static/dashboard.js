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
        this._optimizersCache = null; // Cache for optimizers list
        
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
        
        console.log('Dashboard destroyed, resources cleaned up');
    }

    // Unified logging
    async log(level, message, error = null) {
        try {
            await fetch('/api/log', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    level,
                    message,
                    error: error?.message,
                    timestamp: new Date().toISOString()
                })
            });
        } catch { }
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

    setupEventListeners() {
        const clickHandler = e => {
            const btn = e.target.closest('[data-section], [data-category]');
            if (!btn) return;

            if (btn.dataset.section) this.switchView('section', btn.dataset.section);
            if (btn.dataset.category) this.switchView('category', btn.dataset.category);
        };
        
        document.addEventListener('click', clickHandler, { signal: this.abortController.signal });
        this.eventListeners.push({ element: document, event: 'click', handler: clickHandler });

        const connectionInterval = setInterval(() => this.updateConnectionStatus(), 30000);
        this.intervals.push(connectionInterval);
    }

    switchView(type, value) {
        const selector = type === 'section' ? '.nav-btn' : '.category-btn';
        const contentSelector = type === 'section' ? '.content-section' : null;

        // Update buttons
        document.querySelectorAll(selector).forEach(btn => {
            btn.classList.toggle('active', btn.dataset[type] === value);
        });

        // Update content sections
        if (contentSelector) {
            document.querySelectorAll(contentSelector).forEach(sec => {
                sec.classList.toggle('active', sec.id === `${value}-section`);
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
                this.apiCall('GET', '/api/sources?type=web'),
                this.apiCall('GET', '/api/sources?type=api'),
                this.apiCall('GET', '/api/sources?type=modbus'),
                this.apiCall('GET', '/api/config')
            ]);

            Object.assign(this.state, { devices, endpoints, modbus, config });
            this._optimizersCache = null;

            const editor = document.getElementById('yamlEditor');
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
        const container = document.getElementById('devicesGrid');
        if (!container) return;

        const { optimizers, others } = Object.entries(this.state.devices).reduce((acc, [id, data]) => {
            const key = id.includes('optimizer') || data.device_type === 'OPTIMIZER' || data.device_type === 'Optimizer' ? 'optimizers' : 'others';
            acc[key][id] = data;
            return acc;
        }, { optimizers: {}, others: {} });

        container.innerHTML = '';
        let delay = 0;

        Object.entries(others).forEach(([id, data]) => {
            const card = this.createDeviceCard(id, data);
            this.animateCard(card, delay += 100);
            container.appendChild(card);
        });

        if (Object.keys(optimizers).length) {
            const card = this.createOptimizersCard(optimizers);
            this.animateCard(card, delay += 100);
            container.appendChild(card);
        }
    }

    createDeviceCard(id, data) {
        const card = document.createElement('div');
        card.className = 'device-card';
        card.dataset.deviceId = id;

        const type = data.device_type || this.inferDeviceType(id);
        const metrics = Object.entries(data.measurements || {});

        card.innerHTML = `
            <div class="device-header">
                <div class="device-info">
                    <div class="device-title">${data.device_name || id}</div>
                    <div class="device-type">${type}</div>
                    ${data.device_id ? `<div class="device-id">ID: ${data.device_id}</div>` : ''}
                </div>
                ${this.createToggle(data.enabled, `dashboard.toggle('device','${id}',this.checked)`, '', `Abilita device ${data.device_name || id}`)}
            </div>
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
                ${this.createToggle(allEnabled, 'dashboard.toggleGroup(this.checked)', '', 'Abilita tutti gli optimizer')}
            </div>
            <div class="device-metrics">
                <h4>📊 Metriche Comuni (${metrics.length})</h4>
                <div class="metrics-list">
                    ${metrics.map(m => `
                        <div class="metric-item">
                            <div class="metric-info">
                                <span class="metric-name">${m.name.replace(/_/g, ' ')}</span>
                                <span class="metric-count">${m.count}/${total} optimizer</span>
                            </div>
                            ${this.createToggle(m.enabled, `dashboard.toggleGroupMetric('${m.name}',this.checked)`, 'metric-toggle')}
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
                                <span class="metric-name">${name.replace(/_/g, ' ')}</span>
                            </div>
                            ${this.createToggle(data.enabled, `dashboard.toggle('metric','${deviceId}','${name}',this.checked)`, 'metric-toggle', `Abilita metrica ${name}`)}
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    createToggle(checked, onChange, extraClass = '', ariaLabel = 'Toggle') {
        return `
            <label class="toggle-switch ${extraClass}" role="switch" aria-checked="${checked}" aria-label="${ariaLabel}">
                <input type="checkbox" ${checked ? 'checked' : ''} onchange="${onChange}" aria-hidden="true">
                <span class="toggle-slider" aria-hidden="true"></span>
            </label>
        `;
    }

    renderEndpoints() {
        const container = document.getElementById('endpointsGrid');
        if (!container) return;

        const filtered = Object.entries(this.state.endpoints).filter(([_, data]) => {
            if (this.state.category === 'all') return true;
            return data.category === this.state.category;
        });

        container.innerHTML = '';
        filtered.forEach(([id, data], i) => {
            const card = this.createEndpointCard(id, data);
            this.animateCard(card, i * 80);
            container.appendChild(card);
        });
    }

    createEndpointCard(id, data) {
        const card = document.createElement('div');
        card.className = 'endpoint-card';

        const category = data.category || 'Info';
        const categoryIcons = {
            'Info': 'ℹ️',
            'Inverter': '⚡',
            'Meter': '📊',
            'Flusso': '🔄'
        };
        const icon = categoryIcons[category] || '❓';

        card.innerHTML = `
            <div class="endpoint-header">
                <div class="endpoint-name">${id}</div>
                <div class="endpoint-format">
                    <span class="format-icon">${icon}</span>
                    <span class="format-label">${category}</span>
                </div>
                ${this.createToggle(data.enabled, `dashboard.toggleEndpoint('${id}',this.checked,event)`)}
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
        const container = document.getElementById('modbusGrid');
        if (!container) return;

        const filtered = Object.entries(this.state.modbus).filter(([_, data]) => {
            if (this.state.category === 'all') return true;
            return data.category === this.state.category;
        });

        container.innerHTML = '';
        filtered.forEach(([id, data], i) => {
            const card = this.createModbusCard(id, data);
            this.animateCard(card, i * 80);
            container.appendChild(card);
        });
    }

    createModbusCard(id, data) {
        const card = document.createElement('div');
        card.className = 'device-card modbus-card';
        card.dataset.deviceId = id;

        const category = data.category || 'Modbus';
        const deviceType = data.device_type || 'Unknown';
        const metrics = Object.entries(data.measurements || {});
        const categoryIcon = {
            'Inverter': '🔋',
            'Meter': '⚡',
            'Battery': '🔋'
        }[category] || '⚡';

        card.innerHTML = `
            <div class="device-header">
                <div class="device-info">
                    <div class="device-title">${categoryIcon} ${data.device_name || id}</div>
                    <div class="device-type">${deviceType} - ${category}</div>
                    ${data.device_id ? `<div class="device-id">Unit: ${data.device_id}</div>` : ''}
                </div>
                ${this.createToggle(data.enabled, `dashboard.toggleModbus('device','${id}',this.checked)`)}
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
                                <span class="metric-name">${name.replace(/_/g, ' ')}</span>
                                <span class="metric-description">${data.description || ''}</span>
                                ${data.unit ? `<span class="metric-unit">${data.unit}</span>` : ''}
                            </div>
                            ${this.createToggle(data.enabled, `dashboard.toggleModbus('metric','${deviceId}','${name}',this.checked)`, 'metric-toggle')}
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    // Unified toggle handler
    async toggle(type, ...args) {
        const handlers = {
            device: () => this.toggleDevice(...args),
            metric: () => this.toggleMetric(...args)
        };
        await handlers[type]?.();
    }

    // Modbus toggle handler
    async toggleModbus(type, ...args) {
        const handlers = {
            device: () => this.toggleModbusDevice(...args),
            metric: () => this.toggleModbusMetric(...args)
        };
        await handlers[type]?.();
    }

    async toggleDevice(id, enabled) {
        if (!this.validateId(id, 'device')) return;
        try {
            const data = await this.apiCall('POST', `/api/devices/toggle?id=${id}`);
            Object.assign(this.state.devices[id], data);
            this.updateDeviceUI(id, data);
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

    getOptimizers() {
        if (this._optimizersCache === null) {
            this._optimizersCache = Object.keys(this.state.devices).filter(id =>
                id.includes('optimizer') ||
                this.state.devices[id].device_type === 'OPTIMIZER' ||
                this.state.devices[id].device_type === 'Optimizer'
            );
        }
        return this._optimizersCache;
    }

    inferDeviceType(id) {
        const types = { inverter: 'INVERTER', meter: 'METER', site: 'SITE', weather: 'WEATHER' };
        for (const [key, value] of Object.entries(types)) {
            if (id.includes(key)) return value;
        }
        return 'DEVICE';
    }

    animateCard(card, delay) {
        Object.assign(card.style, { animationDelay: `${delay}ms` });
        card.classList.add('slide-in');
    }

    updateDeviceUI(id, data) {
        const card = document.querySelector(`[data-device-id="${id}"]`);
        if (!card) return;

        // Update device toggle
        const deviceToggle = card.querySelector('.device-header input');
        if (deviceToggle) deviceToggle.checked = data.enabled;

        // Update metric toggles
        if (data.measurements) {
            Object.entries(data.measurements).forEach(([metric, metricData]) => {
                const metricToggle = card.querySelector(`[data-metric="${metric}"] input`);
                if (metricToggle) metricToggle.checked = metricData.enabled;
            });
        }
        
        const isOptimizer = id.includes('optimizer') || 
                           data.device_type === 'OPTIMIZER' || 
                           data.device_type === 'Optimizer';
        if (isOptimizer) this._optimizersCache = null;
    }

    updateGroupUI() {
        const card = document.querySelector('[data-device-id="optimizers-group"]');
        if (!card) return;

        const optimizers = this.getOptimizers();
        const opts = optimizers.map(id => this.state.devices[id]).filter(Boolean);
        const enabled = opts.filter(o => o.enabled).length;
        const total = opts.length;
        const allEnabled = opts.every(o => o.enabled);

        const mainToggle = card.querySelector('.device-header input');
        if (mainToggle) mainToggle.checked = allEnabled;

        const stats = card.querySelector('.device-stats .stat');
        if (stats) stats.textContent = `Attivi: ${enabled}/${total}`;

        const metrics = opts.length > 0 ? Object.keys(opts[0].measurements || {}) : [];

        card.querySelectorAll('.metric-item').forEach((item, index) => {
            if (index >= metrics.length) return;

            const metric = metrics[index];
            const count = opts.filter(o => o.measurements?.[metric]?.enabled).length;

            const input = item.querySelector('input');
            if (input) input.checked = count > 0;

            const counter = item.querySelector('.metric-count');
            if (counter) counter.textContent = `${count}/${total} optimizer`;
        });
    }

    updateModbusDeviceUI(id, data) {
        const card = document.querySelector(`[data-device-id="${id}"]`);
        if (!card) return;

        const deviceToggle = card.querySelector('.device-header input');
        if (deviceToggle) deviceToggle.checked = data.enabled;

        if (data.measurements) {
            Object.entries(data.measurements).forEach(([metric, metricData]) => {
                const metricToggle = card.querySelector(`[data-metric="${metric}"] input`);
                if (metricToggle) metricToggle.checked = metricData.enabled;
            });
        }
    }

    async updateConnectionStatus() {
        try {
            await this.apiCall('GET', '/api/ping');
            const el = document.getElementById('connectionStatus');
            el.textContent = 'Online';
            el.className = 'stat-value online';
            this.state.connectionStatus = 'online';
        } catch (error) {
            // Only log connection errors if we were previously online to avoid spam
            if (this.state.connectionStatus !== 'offline' && error.name !== 'AbortError') {
                console.error('Connection lost:', error);
            }
            const el = document.getElementById('connectionStatus');
            el.textContent = 'Offline';
            el.className = 'stat-value offline';
            this.state.connectionStatus = 'offline';
        }
    }

    notify(message, type = 'info') {
        const el = document.createElement('div');
        const colors = { success: 'var(--accent-green)', error: 'var(--accent-red)', info: 'var(--accent-blue)' };

        Object.assign(el.style, {
            position: 'fixed', top: '20px', right: '20px',
            background: colors[type], color: 'white',
            padding: '1rem 1.5rem', borderRadius: '8px',
            boxShadow: 'var(--shadow-lg)', zIndex: '1000',
            fontWeight: '500', transform: 'translateX(100%)',
            transition: 'transform 0.3s ease', maxWidth: '400px'
        });

        el.textContent = message;
        document.body.appendChild(el);

        setTimeout(() => el.style.transform = 'translateX(0)', 100);
        setTimeout(() => {
            el.style.transform = 'translateX(100%)';
            setTimeout(() => el.remove(), 300);
        }, type === 'error' ? 8000 : 3000);
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
            const data = await this.apiCall('GET', '/api/loop/status');
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
            const formatStats = (stat) => {
                if (!stat) return '0/0/0';
                return `${stat.executed || 0}/${stat.success || 0}/${stat.failed || 0}`;
            };

            const elements = {
                'loopUptime': stats.uptime_formatted || '--',
                'apiRuns': formatStats(stats.api_stats),
                'webRuns': formatStats(stats.web_stats),
                'realtimeRuns': formatStats(stats.realtime_stats),
                'gmeRuns': formatStats(stats.gme_stats),
                'lastUpdate': stats.last_update_formatted || '--'
            };

            Object.entries(elements).forEach(([id, value]) => {
                const el = document.getElementById(id);
                if (el) el.textContent = value;
            });

            if (stats.api_last_run && stats.api_next_run) {
                const apiTimingEl = document.getElementById('apiTiming');
                if (apiTimingEl) {
                    apiTimingEl.innerHTML = `last: ${stats.api_last_run}<br>next: ${stats.api_next_run}`;
                }
            }

            if (stats.web_last_run && stats.web_next_run) {
                const webTimingEl = document.getElementById('webTiming');
                if (webTimingEl) {
                    webTimingEl.innerHTML = `last: ${stats.web_last_run}<br>next: ${stats.web_next_run}`;
                }
            }

            if (stats.gme_last_run && stats.gme_next_run) {
                const gmeTimingEl = document.getElementById('gmeTiming');
                if (gmeTimingEl) {
                    gmeTimingEl.innerHTML = `last: ${stats.gme_last_run}<br>next: ${stats.gme_next_run}`;
                }
            }
        }

        updateLoopButtons(loop_mode);
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

            const response = await fetch('/api/config/yaml', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    file: this.currentFile,
                    content: content
                })
            });

            const result = await response.json();

            if (response.ok) {
                this.setStatus(`✅ ${result.message}`, 'success');
                dashboard.notify(`File ${this.currentFile} salvato`, 'success');
            } else {
                this.setStatus(`❌ ${result.error}`, 'error');
                dashboard.notify('Errore nel salvataggio', 'error');
            }
        } catch (error) {
            this.setStatus(`❌ Errore salvataggio: ${error.message}`, 'error');
            dashboard.notify('Errore nel salvataggio', 'error');
        }
    },

    async loadFile(fileType) {
        try {
            const response = await fetch(`/api/config/yaml?file=${fileType}`);
            const result = await response.json();

            if (response.ok) {
                const editor = document.getElementById('yamlEditor');
                editor.value = result.content;
                this.currentFile = fileType;
                this.setStatus(`📄 Caricato: ${result.path}`, 'info');
            } else {
                this.setStatus(`❌ ${result.error}`, 'error');
            }
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
        const response = await fetch('/api/loop/start', { method: 'POST' });
        const result = await response.json();

        if (response.ok) {
            dashboard.notify('Loop avviato con successo', 'success');
            updateLoopButtons(true);
            // Non aggiorniamo più i log automaticamente
        } else {
            dashboard.notify(`Errore avvio loop: ${result.error}`, 'error');
        }
    } catch (error) {
        dashboard.notify(`Errore di connessione: ${error.message}`, 'error');
    }
};

const stopLoop = async () => {
    if (!confirm('Sei sicuro di voler fermare il loop?')) {
        return;
    }

    try {
        const response = await fetch('/api/loop/stop', { method: 'POST' });
        const result = await response.json();

        if (response.ok) {
            dashboard.notify('Loop fermato con successo', 'success');
            updateLoopButtons(false);
            // Non aggiorniamo più i log automaticamente
        } else {
            dashboard.notify(`Errore stop loop: ${result.error}`, 'error');
        }
    } catch (error) {
        dashboard.notify(`Errore di connessione: ${error.message}`, 'error');
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

function switchLogTab(flow) {
    currentLogFlow = flow;

    document.querySelectorAll('.log-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.flow === flow);
    });

    const filterNames = {
        'all': 'Tutti',
        'api': 'API',
        'web': 'Web',
        'realtime': 'Realtime',
        'gme': 'GME',
        'general': 'Sistema'
    };
    document.getElementById('logsFilter').textContent = `Filtro: ${filterNames[flow]}`;

    loadFilteredLogs();

    if (!logUpdateInterval) {
        logUpdateInterval = setInterval(loadFilteredLogs, 3000);
        if (dashboard) {
            dashboard.intervals.push(logUpdateInterval);
        }
    }
}

async function loadFilteredLogs() {
    try {
        const response = await fetch(`/api/loop/logs?flow=${currentLogFlow}&limit=500`);
        const data = await response.json();

        renderFilteredLogs(data.logs, data.total, data.run_counts);
    } catch (error) {
        console.error('Error loading filtered logs:', error);
    }
}

function renderFilteredLogs(logs, total, runCounts) {
    const container = document.getElementById('logsContent');
    if (!container || !logs) return;

    const shouldScroll = autoScrollEnabled ||
        (container.scrollTop + container.clientHeight >= container.scrollHeight - 10);

    const fragment = document.createDocumentFragment();
    
    if (logs.length === 0) {
        const emptyEntry = document.createElement('div');
        emptyEntry.className = 'log-entry info';
        const message = document.createElement('span');
        message.className = 'log-message';
        message.textContent = 'Nessun log disponibile per questo filtro';
        emptyEntry.appendChild(message);
        fragment.appendChild(emptyEntry);
    } else {
        const flowIcons = {
            'api': '🌐',
            'web': '🔌',
            'realtime': '⚡',
            'gme': '💰',
            'general': 'ℹ️'
        };
        
        logs.forEach(log => {
            const flowType = log.flow_type || 'general';
            const entry = document.createElement('div');
            entry.className = `log-entry ${log.level.toLowerCase()}`;
            
            // Timestamp
            const timestamp = document.createElement('span');
            timestamp.className = 'log-timestamp';
            timestamp.textContent = log.timestamp;
            
            // Level
            const level = document.createElement('span');
            level.className = `log-level ${log.level.toLowerCase()}`;
            level.textContent = log.level;
            
            const flow = document.createElement('span');
            flow.className = 'log-flow';
            flow.dataset.flow = flowType;
            flow.textContent = `${flowIcons[flowType]} ${flowType.toUpperCase()}`;
            
            const message = document.createElement('span');
            message.className = 'log-message';
            message.textContent = log.message;
            
            entry.appendChild(timestamp);
            entry.appendChild(level);
            entry.appendChild(flow);
            entry.appendChild(message);
            fragment.appendChild(entry);
        });
    }
    
    container.replaceChildren(fragment);

    let countText = `${total} log visualizzati`;
    if (runCounts) {
        const totalRuns = Object.values(runCounts).reduce((sum, count) => sum + count, 0);
        if (totalRuns > 0) {
            countText += ` (ultime ${totalRuns} run)`;
        }
    }
    document.getElementById('logsCount').textContent = countText;

    if (shouldScroll) container.scrollTop = container.scrollHeight;
}

async function clearLogs() {
    if (!confirm('Sei sicuro di voler pulire tutti i log?')) {
        return;
    }

    try {
        const response = await fetch('/api/loop/logs/clear', { method: 'POST' });
        const result = await response.json();

        if (response.ok) {
            const container = document.getElementById('logsContent');
            if (container) {
                container.innerHTML = '<div class="log-entry info"><span class="log-message">Log puliti - in attesa di nuovi log...</span></div>';
            }
            document.getElementById('logsCount').textContent = '0 log visualizzati';
            dashboard.notify('Log puliti con successo', 'success');
        } else {
            dashboard.notify(`Errore pulizia log: ${result.error}`, 'error');
        }
    } catch (error) {
        dashboard.notify(`Errore di connessione: ${error.message}`, 'error');
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
