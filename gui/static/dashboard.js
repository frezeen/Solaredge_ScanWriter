// ===== SOLAREDGE DASHBOARD - OPTIMIZED =====
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
        this.init();
    }

    async init() {
        this.setupEventListeners();
        await this.loadData();
        this.render();
        this.updateConnectionStatus();
        this.startLoopMonitoring();
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
        } catch {}
    }

    setupEventListeners() {
        // Delegate event handling
        document.addEventListener('click', e => {
            const btn = e.target.closest('[data-section], [data-category]');
            if (!btn) return;
            
            if (btn.dataset.section) this.switchView('section', btn.dataset.section);
            if (btn.dataset.category) this.switchView('category', btn.dataset.category);
        });

        setInterval(() => this.updateConnectionStatus(), 30000);
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
                fetch('/api/sources?type=web').then(r => r.json()),
                fetch('/api/sources?type=api').then(r => r.json()),
                fetch('/api/sources?type=modbus').then(r => r.json()),
                fetch('/api/config').then(r => r.json())
            ]);
            
            Object.assign(this.state, { devices, endpoints, modbus, config });
            
            // Carica il file YAML principale nell'editor
            const editor = document.getElementById('yamlEditor');
            if (editor) {
                YAMLConfig.loadFile('main');
            }
        } catch (error) {
            this.log('error', 'Error loading data', error);
            this.notify('Errore nel caricamento dati', 'error');
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
        
        // Render regular devices
        Object.entries(others).forEach(([id, data]) => {
            const card = this.createDeviceCard(id, data);
            this.animateCard(card, delay += 100);
            container.appendChild(card);
        });
        
        // Render optimizer group
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
                ${this.createToggle(data.enabled, `dashboard.toggle('device','${id}',this.checked)`)}
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
        
        // Get common metrics
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
                ${this.createToggle(allEnabled, 'dashboard.toggleGroup(this.checked)')}
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
                            ${this.createToggle(data.enabled, `dashboard.toggle('metric','${deviceId}','${name}',this.checked)`, 'metric-toggle')}
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    createToggle(checked, onChange, extraClass = '') {
        return `
            <label class="toggle-switch ${extraClass}">
                <input type="checkbox" ${checked ? 'checked' : ''} onchange="${onChange}">
                <span class="toggle-slider"></span>
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
        try {
            const res = await fetch(`/api/devices/toggle?id=${id}`, { method: 'POST' });
            if (res.ok) {
                const data = await res.json();
                Object.assign(this.state.devices[id], data);
                this.updateDeviceUI(id, data);
                this.notify(`Device ${id} ${enabled ? 'abilitato' : 'disabilitato'}`, 'success');
            }
        } catch (error) {
            this.log('error', `Error toggling device ${id}`, error);
            this.notify('Errore nel toggle device', 'error');
        }
    }

    async toggleMetric(deviceId, metric, enabled) {
        try {
            const res = await fetch(`/api/devices/metrics/toggle?id=${deviceId}&metric=${metric}`, { method: 'POST' });
            if (res.ok) {
                const data = await res.json();
                
                // Update state with new metric state
                if (!this.state.devices[deviceId].measurements) {
                    this.state.devices[deviceId].measurements = {};
                }
                this.state.devices[deviceId].measurements[metric] = { enabled: data.enabled };
                
                // Update device state if it changed
                if (data.device_changed) {
                    this.state.devices[deviceId].enabled = data.device_enabled;
                }
                
                // Update UI to reflect all changes
                this.updateDeviceUI(deviceId, {
                    enabled: data.device_enabled,
                    measurements: this.state.devices[deviceId].measurements
                });
                
                // If this device belongs to the optimizer group, refresh group UI counts
                this.updateGroupUI();
                
                // Show notification with device auto-toggle info
                let message = `Metrica ${metric.replace(/_/g, ' ')} ${enabled ? 'abilitata' : 'disabilitata'}`;
                if (data.device_changed) {
                    message += ` (device auto-${data.device_enabled ? 'abilitato' : 'disabilitato'})`;
                }
                this.notify(message, 'success');
            }
        } catch (error) {
            this.log('error', `Error toggling metric ${deviceId}.${metric}`, error);
            this.notify('Errore nel toggle metrica', 'error');
        }
    }

    async toggleGroup(enabled) {
        const optimizers = this.getOptimizers();
        // Fallback to toggling each optimizer individually (original behavior)
        await Promise.all(optimizers.map(async id => {
            try {
                const res = await fetch(`/api/devices/toggle?id=${id}`, { method: 'POST' });
                if (res.ok) {
                    const data = await res.json();
                    Object.assign(this.state.devices[id], data);
                    this.updateDeviceUI(id, data);
                }
            } catch (e) { /* ignore per-device errors */ }
        }));
        this.updateGroupUI();
        this.notify(`Gruppo optimizers ${enabled ? 'abilitato' : 'disabilitato'}`, 'success');
    }

    async toggleGroupMetric(metric, enabled) {
        const optimizers = this.getOptimizers();
        const allDisabled = optimizers.every(id => !this.state.devices[id].enabled);
        await Promise.all(optimizers.map(id => {
            if (!this.state.devices[id].measurements?.[metric]) return Promise.resolve();
            return fetch(`/api/devices/metrics/toggle?id=${id}&metric=${metric}`, { method: 'POST' })
                .then(r => r.ok ? r.json() : null)
                .then(data => {
                    if (data) {
                        // Update state with new metric state (same logic as toggleMetric)
                        if (!this.state.devices[id].measurements) {
                            this.state.devices[id].measurements = {};
                        }
                        this.state.devices[id].measurements[metric] = { enabled: data.enabled };
                        
                        // Update device state if it changed
                        if (data.device_changed) {
                            this.state.devices[id].enabled = data.device_enabled;
                        }
                        
                        // Update UI to reflect all changes
                        this.updateDeviceUI(id, {
                            enabled: data.device_enabled,
                            measurements: this.state.devices[id].measurements
                        });
                    }
                }).catch(()=>{});
        }));
        // Recompute and refresh optimizer group UI after all per-device updates
        this.updateGroupUI();
        
        // Show notification for group metric toggle
        const optimizerCount = optimizers.length;
        this.notify(`Metrica ${metric.replace(/_/g, ' ')} ${enabled ? 'abilitata' : 'disabilitata'} su ${optimizerCount} optimizer`, 'success');
    }

    async toggleEndpoint(id, enabled, event) {
        try {
            const res = await fetch(`/api/endpoints/toggle?id=${id}`, { method: 'POST' });
            if (res.ok) {
                const data = await res.json();
                this.state.endpoints[id].enabled = data.enabled;
                
                const card = event.target.closest('.endpoint-card');
                const status = card.querySelector('.endpoint-status');
                status.textContent = enabled ? 'Abilitato' : 'Disabilitato';
                status.className = `endpoint-status ${enabled ? 'enabled' : 'disabled'}`;
                
                this.notify(`Endpoint ${id} ${enabled ? 'abilitato' : 'disabilitato'}`, 'success');
            }
        } catch (error) {
            this.log('error', 'Error toggling endpoint', error);
            this.notify('Errore nel toggle endpoint', 'error');
        }
    }

    async toggleModbusDevice(id, enabled) {
        try {
            const res = await fetch(`/api/modbus/devices/toggle?id=${id}`, { method: 'POST' });
            if (res.ok) {
                const data = await res.json();
                Object.assign(this.state.modbus[id], data);
                this.updateModbusDeviceUI(id, data);
                this.notify(`Device Modbus ${id} ${enabled ? 'abilitato' : 'disabilitato'}`, 'success');
            }
        } catch (error) {
            this.log('error', `Error toggling modbus device ${id}`, error);
            this.notify('Errore nel toggle device Modbus', 'error');
        }
    }

    async toggleModbusMetric(deviceId, metric, enabled) {
        try {
            const res = await fetch(`/api/modbus/devices/metrics/toggle?id=${deviceId}&metric=${metric}`, { method: 'POST' });
            if (res.ok) {
                const data = await res.json();
                
                // Update state with new metric state
                if (!this.state.modbus[deviceId].measurements) {
                    this.state.modbus[deviceId].measurements = {};
                }
                this.state.modbus[deviceId].measurements[metric] = { enabled: data.enabled };
                this.state.modbus[deviceId].enabled = data.device_enabled;
                
                // Update UI
                this.updateModbusDeviceUI(deviceId, {
                    enabled: data.device_enabled,
                    measurements: { [metric]: { enabled: data.enabled } }
                });
                
                // Show notification with cascade info
                let message = `Metrica Modbus ${metric.replace(/_/g, ' ')} ${data.enabled ? 'abilitata' : 'disabilitata'}`;
                if (data.device_changed) {
                    message += ` (device auto-${data.device_enabled ? 'abilitato' : 'disabilitato'})`;
                }
                this.notify(message, 'success');
            }
        } catch (error) {
            this.log('error', `Error toggling modbus metric ${deviceId}.${metric}`, error);
            this.notify('Errore nel toggle metrica Modbus', 'error');
        }
    }

    // Helpers
    getOptimizers() {
        return Object.keys(this.state.devices).filter(id => 
            id.includes('optimizer') || this.state.devices[id].device_type === 'OPTIMIZER' || this.state.devices[id].device_type === 'Optimizer'
        );
    }

    inferDeviceType(id) {
        const types = { inverter: 'INVERTER', meter: 'METER', site: 'SITE', weather: 'WEATHER' };
        return Object.entries(types).find(([key]) => id.includes(key))?.[1] || 'DEVICE';
    }

    animateCard(card, delay) {
        card.style.animationDelay = `${delay}ms`;
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
    }

    updateGroupUI() {
        const card = document.querySelector('[data-device-id="optimizers-group"]');
        if (!card) return;
        
        const optimizers = this.getOptimizers();
        const opts = optimizers.map(id => this.state.devices[id]).filter(Boolean);
        const enabled = opts.filter(o => o.enabled).length;
        const total = opts.length;
        const allEnabled = opts.every(o => o.enabled);
        
        // Aggiorna toggle principale
        const mainToggle = card.querySelector('.device-header input');
        if (mainToggle) mainToggle.checked = allEnabled;
        
        // Aggiorna contatore
        const stats = card.querySelector('.device-stats .stat');
        if (stats) stats.textContent = `Attivi: ${enabled}/${total}`;
        
        // Ottieni metriche comuni
        const metrics = opts.length > 0 ? Object.keys(opts[0].measurements || {}) : [];
        
        // Aggiorna metriche usando indice
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
    }

    parseYAML(text) {
        const result = { sources: { web_scraping: { endpoints: {} } } };
        const lines = text.split('\n');
        let current = { device: null, measurement: null };
        let flags = { web: false, endpoints: false, measurements: false };
        
        for (const line of lines) {
            if (line.match(/^  web_scraping:/)) flags.web = true;
            if (flags.web && line.match(/^    endpoints:/)) flags.endpoints = true;
            
            if (flags.endpoints && line.match(/^      ([\w_-]+):/)) {
                current.device = line.match(/^      ([\w_-]+):/)[1];
                result.sources.web_scraping.endpoints[current.device] = {};
                flags.measurements = false;
            }
            
            if (current.device) {
                if (line.includes('measurements:')) {
                    flags.measurements = true;
                    result.sources.web_scraping.endpoints[current.device].measurements = {};
                } else if (line.includes('device_type:')) {
                    result.sources.web_scraping.endpoints[current.device].device_type = line.split(':')[1].trim();
                } else if (line.includes('enabled:')) {
                    const enabled = line.includes('true');
                    const target = flags.measurements && current.measurement 
                        ? result.sources.web_scraping.endpoints[current.device].measurements[current.measurement]
                        : result.sources.web_scraping.endpoints[current.device];
                    target.enabled = enabled;
                } else if (flags.measurements && line.match(/^          (\w+):/)) {
                    current.measurement = line.match(/^          (\w+):/)[1];
                    result.sources.web_scraping.endpoints[current.device].measurements[current.measurement] = {};
                }
            }
        }
        
        return result;
    }

    async updateConnectionStatus() {
        try {
            const res = await fetch('/api/ping');
            const el = document.getElementById('connectionStatus');
            el.textContent = res.ok ? 'Online' : 'Offline';
            el.className = `stat-value ${res.ok ? 'online' : 'offline'}`;
        } catch {
            const el = document.getElementById('connectionStatus');
            el.textContent = 'Offline';
            el.className = 'stat-value offline';
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

    // ===== LOOP MONITORING =====
    startLoopMonitoring() {
        // Aggiorna stato loop ogni 5 secondi
        setInterval(() => this.updateLoopStatus(), 5000);
        // Prima chiamata immediata
        this.updateLoopStatus();
        // Non aggiorniamo più i log automaticamente
    }

    async updateLoopStatus() {
        try {
            const response = await fetch('/api/loop/status');
            const data = await response.json();
            
            // Rileva cambio di stato del loop
            const previousLoopMode = this.state.loopStatus?.loop_mode;
            const currentLoopMode = data.loop_mode;
            
            this.state.loopStatus = data;
            this.renderLoopStatus();
            
            // Log del cambio di stato senza aggiornare i log
            if (previousLoopMode !== currentLoopMode) {
                console.log(`Loop state changed: ${previousLoopMode} -> ${currentLoopMode}`);
            }
        } catch (error) {
            console.error('Error updating loop status:', error);
        }
    }

    async updateLoopLogs() {
        try {
            const response = await fetch('/api/loop/logs?limit=50');
            const data = await response.json();
            this.renderLoopLogs(data.logs);
        } catch (error) {
            console.error('Error updating loop logs:', error);
        }
    }

    renderLoopStatus() {
        if (!this.state.loopStatus) return;

        const { loop_mode, stats, message } = this.state.loopStatus;

        // Aggiorna stato
        const statusEl = document.getElementById('loopStatus');
        if (statusEl) {
            statusEl.textContent = loop_mode ? 'Running' : 'Standalone';
            statusEl.className = `stat-value ${loop_mode ? 'running' : 'stopped'}`;
        }

        if (loop_mode && stats) {
            // Aggiorna statistiche con nuovo formato eseguite/successi/fallimenti
            const formatStats = (stat) => {
                if (!stat) return '0/0/0';
                return `${stat.executed || 0}/${stat.success || 0}/${stat.failed || 0}`;
            };
            
            const elements = {
                'loopUptime': stats.uptime_formatted || '--',
                'apiRuns': formatStats(stats.api_stats),
                'webRuns': formatStats(stats.web_stats),
                'realtimeRuns': formatStats(stats.realtime_stats),
                'lastUpdate': stats.last_update_formatted || '--'
            };

            Object.entries(elements).forEach(([id, value]) => {
                const el = document.getElementById(id);
                if (el) el.textContent = value;
            });

            // Aggiorna timing information
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
        }
        
        // Aggiorna stato dei tasti
        updateLoopButtons(loop_mode);
    }

    renderLoopLogs(logs) {
        const container = document.getElementById('logsContent');
        if (!container || !logs) return;

        // Mantieni scroll position se auto-scroll è disabilitato
        const shouldScroll = this.state.autoScroll || 
            (container.scrollTop + container.clientHeight >= container.scrollHeight - 10);

        // Genera HTML per i log
        const logsHtml = logs.map(log => `
            <div class="log-entry">
                <span class="log-timestamp">${log.timestamp}</span>
                <span class="log-level ${this.getLogLevelClass(log.level)}">${log.level.toUpperCase()}</span>
                <span class="log-message">${this.escapeHtml(log.message)}</span>
            </div>
        `).join('');

        container.innerHTML = logsHtml;

        // Auto-scroll se abilitato
        if (shouldScroll) {
            container.scrollTop = container.scrollHeight;
        }
    }

    getLogLevelClass(level) {
        const levelMap = {
            'info': 'info',
            'error': 'error',
            'warning': 'warning',
            'success': 'success'
        };
        return levelMap[level.toLowerCase()] || 'info';
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// ===== YAML CONFIG =====
const YAMLConfig = {
    currentFile: 'main',
    
    async validate() {
        const editor = document.getElementById('yamlEditor');
        const status = document.getElementById('configStatus');
        try {
            if (this.currentFile === 'env') {
                // Per file .env, verifica solo che non sia vuoto
                if (editor.value.trim()) {
                    this.setStatus('✅ File .env valido', 'success');
                } else {
                    this.setStatus('⚠️ File .env vuoto', 'warning');
                }
            } else {
                // Per file YAML, valida la sintassi
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
        } catch {
            this.setStatus('❌ Errore nel caricamento', 'error');
            dashboard.notify('Errore nel ricaricamento', 'error');
        }
    },
    
    async save() {
        try {
            const editor = document.getElementById('yamlEditor');
            const content = editor.value;
            
            // Valida il contenuto prima di salvare (solo per file YAML)
            if (this.currentFile !== 'env') {
                jsyaml.load(content);
            }
            
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

// Initialize
let dashboard;
document.addEventListener('DOMContentLoaded', () => {
    dashboard = new SolarDashboard();
});
/
/ ===== LOG TAB FILTERING =====
let currentLogFlow = 'all';
let autoScrollEnabled = true;
let logUpdateInterval = null;

function switchLogTab(flow) {
    currentLogFlow = flow;
    
    // Aggiorna UI dei tab
    document.querySelectorAll('.log-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.flow === flow);
    });
    
    // Aggiorna filtro display
    const filterNames = {
        'all': 'Tutti',
        'api': 'API',
        'web': 'Web',
        'realtime': 'Realtime',
        'general': 'Sistema'
    };
    document.getElementById('logsFilter').textContent = `Filtro: ${filterNames[flow]}`;
    
    // Carica log filtrati
    loadFilteredLogs();
    
    // Avvia polling se non già attivo
    if (!logUpdateInterval) {
        logUpdateInterval = setInterval(loadFilteredLogs, 3000);
    }
}

async function loadFilteredLogs() {
    try {
        const response = await fetch(`/api/loop/logs?flow=${currentLogFlow}&limit=100`);
        const data = await response.json();
        
        renderFilteredLogs(data.logs, data.total);
    } catch (error) {
        console.error('Error loading filtered logs:', error);
    }
}

function renderFilteredLogs(logs, total) {
    const container = document.getElementById('logsContent');
    if (!container || !logs) return;
    
    // Mantieni scroll position se auto-scroll è disabilitato
    const shouldScroll = autoScrollEnabled || 
        (container.scrollTop + container.clientHeight >= container.scrollHeight - 10);
    
    // Genera HTML per i log con flow badge
    const logsHtml = logs.map(log => {
        const flowType = log.flow_type || 'general';
        const flowIcons = {
            'api': '🌐',
            'web': '🔌',
            'realtime': '⚡',
            'general': 'ℹ️'
        };
        
        return `
            <div class="log-entry ${log.level.toLowerCase()}">
                <span class="log-timestamp">${log.timestamp}</span>
                <span class="log-level ${log.level.toLowerCase()}">${log.level}</span>
                <span class="log-flow" data-flow="${flowType}">${flowIcons[flowType]} ${flowType.toUpperCase()}</span>
                <span class="log-message">${escapeHtml(log.message)}</span>
            </div>
        `;
    }).join('');
    
    container.innerHTML = logsHtml || '<div class="log-entry info"><span class="log-message">Nessun log disponibile per questo filtro</span></div>';
    
    // Aggiorna contatore
    document.getElementById('logsCount').textContent = `${total} log visualizzati`;
    
    // Auto-scroll se abilitato
    if (shouldScroll) {
        container.scrollTop = container.scrollHeight;
    }
}

function clearLogs() {
    const container = document.getElementById('logsContent');
    if (container) {
        container.innerHTML = '<div class="log-entry info"><span class="log-message">Log puliti - in attesa di nuovi log...</span></div>';
    }
    document.getElementById('logsCount').textContent = '0 log visualizzati';
}

function toggleAutoScroll() {
    autoScrollEnabled = !autoScrollEnabled;
    const btn = document.getElementById('autoScrollBtn');
    btn.textContent = `📌 Auto-scroll: ${autoScrollEnabled ? 'ON' : 'OFF'}`;
    btn.classList.toggle('active', autoScrollEnabled);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Avvia il caricamento dei log quando la pagina è pronta
document.addEventListener('DOMContentLoaded', () => {
    // Carica log iniziali
    switchLogTab('all');
});
