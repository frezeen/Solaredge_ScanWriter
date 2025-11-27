# 🚀 Piano di Ottimizzazione Frontend

## Priorità 1: CRITICHE (Performance & Memory)

### 1.1 Refactoring Python Backend

**Problema**: File I/O sincrono blocca event loop
```python
# ❌ PRIMA (blocking)
def _get_web_devices(self):
    content = web_file.read_text(encoding='utf-8')
    
# ✅ DOPO (async)
async def _get_web_devices(self):
    async with aiofiles.open(web_file, 'r', encoding='utf-8') as f:
        content = await f.read()
```

**Problema**: Codice duplicato per caricamento YAML
```python
# ✅ SOLUZIONE: Metodo unificato
async def _load_source_config(self, source_type: str) -> dict:
    """Carica configurazione da file sources/ in modo unificato"""
    config_map = {
        'web': 'config/sources/web_endpoints.yaml',
        'api': 'config/sources/api_endpoints.yaml',
        'modbus': 'config/sources/modbus_endpoints.yaml'
    }
    # ... implementazione unica
```

**Problema**: Toggle handlers duplicati
```python
# ✅ SOLUZIONE: Handler generico con strategy pattern
async def _handle_toggle(self, source_type: str, toggle_type: str, **params):
    """Handler unificato per tutti i toggle"""
    strategy = self.toggle_strategies[source_type][toggle_type]
    return await strategy.execute(**params)
```

### 1.2 Ottimizzazione JavaScript

**Problema**: Polling senza cleanup
```javascript
// ❌ PRIMA
setInterval(() => this.updateLoopStatus(), 5000);

// ✅ DOPO
class SolarDashboard {
    constructor() {
        this.intervals = [];
    }
    
    startPolling() {
        this.intervals.push(
            setInterval(() => this.updateLoopStatus(), 5000)
        );
    }
    
    destroy() {
        this.intervals.forEach(clearInterval);
        this.intervals = [];
    }
}
```

**Problema**: Rendering inefficiente
```javascript
// ✅ SOLUZIONE: Virtual DOM o debouncing
const debouncedRender = debounce(() => {
    this.renderDevices();
}, 300);

// ✅ SOLUZIONE: Batch updates
requestAnimationFrame(() => {
    this.renderDevices();
    this.renderEndpoints();
});
```

**Problema**: Cache non invalidata
```javascript
// ✅ SOLUZIONE: Invalidazione automatica
updateDeviceUI(id, data) {
    Object.assign(this.state.devices[id], data);
    this._optimizersCache = null; // Invalida cache
    this.updateDeviceCard(id); // Update solo card specifica
}
```

### 1.3 Gestione Memoria

**Problema**: Log buffer illimitato
```python
# ✅ SOLUZIONE: LRU Cache con limite
from collections import deque

class SimpleWebGUI:
    def __init__(self):
        self.log_buffer = deque(maxlen=1000)  # Auto-evict oldest
        self.flow_runs = {
            'api': deque(maxlen=3),  # Max 3 run per flow
            'web': deque(maxlen=3),
            'realtime': deque(maxlen=3),
            'general': deque(maxlen=3)
        }
```

## Priorità 2: ARCHITETTURA

### 2.1 Separazione Responsabilità

**Refactoring SimpleWebGUI** (1630 righe → 4 classi):

```python
# gui/core/web_server.py
class WebServer:
    """Gestisce solo HTTP server e routing"""
    
# gui/core/state_manager.py
class StateManager:
    """Gestisce stato applicazione e cache"""
    
# gui/core/config_handler.py
class ConfigHandler:
    """Gestisce caricamento/salvataggio config"""
    
# gui/core/loop_controller.py
class LoopController:
    """Gestisce loop monitoring e controllo"""
```

### 2.2 Utilizzo Componenti Esistenti

**Attivare loop_orchestrator.py e web_server.py**:
```python
# ✅ Usare architettura già presente
from gui.components.web_server import WebServer, ServerConfig
from gui.components.loop_orchestrator import LoopOrchestrator

class SimpleWebGUI:
    def __init__(self):
        self.server = WebServer(ServerConfig(), self)
        self.orchestrator = LoopOrchestrator(...)
```

## Priorità 3: SICUREZZA

### 3.1 XSS Protection

```javascript
// ❌ PRIMA
container.innerHTML = logs.map(log => `
    <span>${log.message}</span>
`).join('');

// ✅ DOPO
const fragment = document.createDocumentFragment();
logs.forEach(log => {
    const span = document.createElement('span');
    span.textContent = log.message; // Auto-escape
    fragment.appendChild(span);
});
container.replaceChildren(fragment);
```

### 3.2 CSRF Protection

```python
# ✅ Aggiungere middleware CSRF
from aiohttp_csrf import CsrfProtect

app = web.Application()
CsrfProtect.setup(app, secret='...')
```

### 3.3 Rate Limiting

```python
# ✅ Aggiungere rate limiter
from aiohttp_ratelimit import RateLimiter

limiter = RateLimiter(max_requests=100, time_window=60)
app.middlewares.append(limiter.middleware)
```

## Priorità 4: UX & ACCESSIBILITÀ

### 4.1 ARIA Labels

```html
<!-- ✅ Toggle accessibile -->
<label class="toggle-switch" role="switch" aria-checked="true">
    <input type="checkbox" checked>
    <span class="toggle-slider" aria-hidden="true"></span>
    <span class="sr-only">Abilita device</span>
</label>
```

### 4.2 Keyboard Navigation

```javascript
// ✅ Focus trap per modal
class Modal {
    open() {
        this.previousFocus = document.activeElement;
        this.element.focus();
        this.trapFocus();
    }
    
    close() {
        this.previousFocus?.focus();
    }
}
```

### 4.3 Loading States

```javascript
// ✅ Skeleton screens
async loadData() {
    this.showSkeleton();
    try {
        const data = await fetch(...);
        this.render(data);
    } finally {
        this.hideSkeleton();
    }
}
```

### 4.4 Responsive Motion

```css
/* ✅ Rispetta preferenze utente */
@media (prefers-reduced-motion: reduce) {
    * {
        animation-duration: 0.01ms !important;
        transition-duration: 0.01ms !important;
    }
}
```

## Priorità 5: CSS Optimization

### 5.1 CSS Variables Dinamiche

```css
/* ✅ Usa rem invece di px */
:root {
    --font-size-base: 1rem;
    --font-size-lg: 1.125rem;
    --spacing-unit: 0.5rem;
}

.device-card {
    padding: calc(var(--spacing-unit) * 4);
    font-size: var(--font-size-base);
}
```

### 5.2 Critical CSS

```html
<!-- ✅ Inline critical CSS -->
<style>
    /* Above-the-fold styles */
    .header { ... }
    .navigation { ... }
</style>
<link rel="stylesheet" href="/static/style.css" media="print" onload="this.media='all'">
```

## Metriche di Successo

### Performance
- **Time to Interactive**: < 2s (attuale: ~4s)
- **First Contentful Paint**: < 1s (attuale: ~2s)
- **Memory usage**: < 50MB (attuale: ~120MB dopo 1h)
- **Bundle size**: < 100KB (attuale: 150KB)

### Code Quality
- **Cyclomatic complexity**: < 10 per metodo (attuale: max 25)
- **Code duplication**: < 5% (attuale: ~30%)
- **Test coverage**: > 80% (attuale: 0%)

### Accessibility
- **WCAG 2.1 Level AA**: 100% compliance (attuale: ~40%)
- **Lighthouse Accessibility**: > 95 (attuale: 72)
- **Keyboard navigation**: 100% (attuale: 60%)

## Timeline Implementazione

**Settimana 1-2**: Priorità 1 (Performance critiche)
**Settimana 3-4**: Priorità 2 (Architettura)
**Settimana 5**: Priorità 3 (Sicurezza)
**Settimana 6**: Priorità 4-5 (UX/CSS)
**Settimana 7**: Testing e ottimizzazione finale
