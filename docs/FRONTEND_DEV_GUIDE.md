# Frontend Developer Guide

## 🎯 Quick Start

### Struttura Frontend
```
gui/
├── simple_web_gui.py          # Main GUI class (1480 righe)
├── components/
│   ├── loop_orchestrator.py   # Loop management (non ancora usato)
│   └── web_server.py          # Web server component (non ancora usato)
├── static/
│   ├── dashboard.js           # Frontend logic (1127 righe)
│   └── style.css              # Styling (800+ righe)
└── templates/
    └── index.html             # Main template
```

## 🔧 Best Practices Implementate

### 1. Async I/O (Python)

**✅ DO**: Usa async/await per file operations
```python
async def _load_source_config(self, source_type: str) -> dict:
    async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
        content = await f.read()
    return yaml.safe_load(content)
```

**❌ DON'T**: Usa sync I/O che blocca event loop
```python
def _get_web_devices(self):
    content = web_file.read_text(encoding='utf-8')  # BLOCKING!
```

---

### 2. Memory Management (JavaScript)

**✅ DO**: Traccia e pulisci risorse
```javascript
class SolarDashboard {
    constructor() {
        this.intervals = [];
        this.abortController = new AbortController();
    }
    
    startPolling() {
        const id = setInterval(() => this.update(), 5000);
        this.intervals.push(id); // Track it!
    }
    
    destroy() {
        this.intervals.forEach(clearInterval);
        this.abortController.abort();
    }
}
```

**❌ DON'T**: Crea interval senza cleanup
```javascript
setInterval(() => this.update(), 5000); // MEMORY LEAK!
```

---

### 3. XSS Prevention (JavaScript)

**✅ DO**: Usa textContent per dati utente
```javascript
const message = document.createElement('span');
message.textContent = log.message; // Auto-escape!
container.appendChild(message);
```

**❌ DON'T**: Usa innerHTML con dati non sanitizzati
```javascript
container.innerHTML = `<span>${log.message}</span>`; // XSS RISK!
```

---

### 4. Accessibility (HTML/JS)

**✅ DO**: Aggiungi ARIA labels
```javascript
createToggle(checked, onChange, extraClass, ariaLabel) {
    return `
        <label role="switch" aria-checked="${checked}" aria-label="${ariaLabel}">
            <input type="checkbox" ${checked ? 'checked' : ''}>
        </label>
    `;
}
```

**❌ DON'T**: Ignora screen reader support
```html
<label class="toggle-switch">
    <input type="checkbox">
</label>
```

---

### 5. CSS Animations

**✅ DO**: Rispetta prefers-reduced-motion
```css
@media (prefers-reduced-motion: reduce) {
    * {
        animation-duration: 0.01ms !important;
        transition-duration: 0.01ms !important;
    }
}
```

**❌ DON'T**: Forza animazioni sempre
```css
.card {
    animation: slideIn 0.4s ease-out; /* Ignora preferenze utente */
}
```

---

## 🚀 Performance Tips

### Caricamento Config
```python
# ✅ Usa metodo unificato
sources = await self._load_source_config('web')

# ❌ Non duplicare codice
def _get_web_devices(self): ...
def _get_api_endpoints(self): ...  # 90% identico!
```

### Rendering Ottimizzato
```javascript
// ✅ Usa DocumentFragment per batch updates
const fragment = document.createDocumentFragment();
items.forEach(item => {
    const el = document.createElement('div');
    el.textContent = item.name;
    fragment.appendChild(el);
});
container.replaceChildren(fragment); // Single reflow!

// ❌ Non modificare DOM in loop
items.forEach(item => {
    container.innerHTML += `<div>${item.name}</div>`; // Multiple reflows!
});
```

### Cache Invalidation
```javascript
// ✅ Invalida cache quando necessario
updateDeviceUI(id, data) {
    Object.assign(this.state.devices[id], data);
    if (this.isOptimizer(id)) {
        this._optimizersCache = null; // Invalida!
    }
}

// ❌ Non dimenticare di invalidare
updateDeviceUI(id, data) {
    Object.assign(this.state.devices[id], data);
    // Cache stale!
}
```

---

## 🔍 Debugging

### Memory Leaks
```javascript
// Chrome DevTools → Memory → Take Heap Snapshot
// 1. Snapshot iniziale
// 2. Usa app per 1h
// 3. Snapshot finale
// 4. Confronta: detached DOM nodes, event listeners
```

### Performance Profiling
```javascript
// Chrome DevTools → Performance
// 1. Start recording
// 2. Esegui azione (es: render 1000 log)
// 3. Stop recording
// 4. Analizza: scripting time, rendering time, painting
```

### Accessibility Testing
```bash
# Lighthouse audit
npm install -g lighthouse
lighthouse http://localhost:8092 --only-categories=accessibility

# Screen reader test
# Windows: NVDA (free)
# Mac: VoiceOver (built-in)
# Linux: Orca
```

---

## 📚 API Reference

### Python Backend

#### `_load_source_config(source_type: str) -> dict`
Carica configurazione da file sources/ in modo unificato.

**Args**:
- `source_type`: Tipo sorgente ('web', 'api', 'modbus')

**Returns**:
- `dict`: Endpoints/devices della sorgente

**Example**:
```python
web_devices = await self._load_source_config('web')
api_endpoints = await self._load_source_config('api')
```

---

### JavaScript Frontend

#### `dashboard.destroy()`
Pulisce tutte le risorse (intervals, event listeners, fetch).

**Example**:
```javascript
window.addEventListener('beforeunload', () => {
    dashboard.destroy();
});
```

#### `createToggle(checked, onChange, extraClass, ariaLabel)`
Crea toggle switch accessibile.

**Args**:
- `checked`: Stato iniziale
- `onChange`: Handler change event
- `extraClass`: Classi CSS aggiuntive
- `ariaLabel`: Label per screen reader

**Returns**:
- `string`: HTML del toggle

---

## 🧪 Testing Checklist

### Prima di Commit
- [ ] `getDiagnostics` passa senza errori
- [ ] Memory leak test (1h utilizzo)
- [ ] XSS test (inietta `<script>alert('XSS')</script>`)
- [ ] Lighthouse Accessibility > 85
- [ ] Screen reader test (NVDA/VoiceOver)
- [ ] Reduced motion test (DevTools → Rendering → Emulate)

### Performance Benchmarks
- [ ] Config loading < 100ms
- [ ] Log rendering (1000 entries) < 150ms
- [ ] Memory usage (1h) < 80MB
- [ ] First Contentful Paint < 1s

---

## 🔗 Risorse

### Documentazione
- [FRONTEND_OPTIMIZATION_PLAN.md](./FRONTEND_OPTIMIZATION_PLAN.md) - Piano completo
- [FRONTEND_OPTIMIZATIONS_APPLIED.md](./FRONTEND_OPTIMIZATIONS_APPLIED.md) - Step 1 completato
- [CHANGELOG_FRONTEND.md](../CHANGELOG_FRONTEND.md) - Changelog

### Standard
- [WCAG 2.1](https://www.w3.org/WAI/WCAG21/quickref/) - Accessibility guidelines
- [MDN Web Docs](https://developer.mozilla.org/) - Web API reference
- [aiohttp docs](https://docs.aiohttp.org/) - Async HTTP server

### Tools
- [Lighthouse](https://developers.google.com/web/tools/lighthouse) - Audit tool
- [axe DevTools](https://www.deque.com/axe/devtools/) - Accessibility testing
- [Chrome DevTools](https://developer.chrome.com/docs/devtools/) - Debugging
