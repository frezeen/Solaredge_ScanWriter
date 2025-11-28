// ===== UPDATE CHECKER =====
class UpdateChecker {
    constructor() {
        this.checkInterval = 3600000; // 1 ora in millisecondi
        this.intervalId = null;
        this.isChecking = false;
        this.updatesBanner = null;
        
        this.init();
    }
    
    init() {
        this.createUpdatesBanner();
        this.startAutoCheck();
        // Controlla subito al caricamento
        this.checkForUpdates();
    }
    
    createUpdatesBanner() {
        // Crea il banner degli aggiornamenti
        const banner = document.createElement('div');
        banner.id = 'updatesBanner';
        banner.className = 'updates-banner hidden';
        banner.innerHTML = `
            <div class="updates-banner-content">
                <div class="updates-message">
                    <span class="updates-icon">📦</span>
                    <span class="updates-text">Aggiornamenti disponibili!</span>
                </div>
                <div class="updates-actions">
                    <button class="btn btn-secondary btn-sm" onclick="updateChecker.checkForUpdates()">
                        🔄 Controlla
                    </button>
                    <button class="btn btn-success btn-sm" onclick="updateChecker.runUpdate()">
                        ⬆️ Aggiorna
                    </button>
                </div>
            </div>
        `;
        
        // Inserisci il banner all'inizio del body
        document.body.insertBefore(banner, document.body.firstChild);
        this.updatesBanner = banner;
    }
    
    startAutoCheck() {
        // Controlla ogni ora
        this.intervalId = setInterval(() => {
            this.checkForUpdates();
        }, this.checkInterval);
        
        console.log('✅ Auto-check aggiornamenti avviato (ogni ora)');
    }
    
    async checkForUpdates() {
        if (this.isChecking) {
            console.log('⏳ Controllo aggiornamenti già in corso...');
            return;
        }
        
        this.isChecking = true;
        
        try {
            const response = await fetch('/api/updates/check');
            const data = await response.json();
            
            if (data.status === 'success') {
                this.handleCheckResult(data);
            } else {
                console.error('❌ Errore controllo aggiornamenti:', data.message);
                this.notify('Errore durante il controllo degli aggiornamenti', 'error');
            }
        } catch (error) {
            console.error('❌ Errore durante il controllo:', error);
            this.notify('Errore di connessione durante il controllo', 'error');
        } finally {
            this.isChecking = false;
        }
    }
    
    handleCheckResult(data) {
        const { updates_available, remote_commits, message } = data;
        
        if (updates_available) {
            console.log(`📦 Aggiornamenti disponibili: ${remote_commits} commit`);
            this.showUpdatesBanner();
            this.notify(`${message} - Clicca il banner per aggiornare`, 'info');
        } else {
            console.log('✅ Sei già aggiornato');
            this.hideUpdatesBanner();
        }
    }
    
    showUpdatesBanner() {
        if (this.updatesBanner) {
            this.updatesBanner.classList.remove('hidden');
        }
    }
    
    hideUpdatesBanner() {
        if (this.updatesBanner) {
            this.updatesBanner.classList.add('hidden');
        }
    }
    
    async runUpdate() {
        if (!confirm('Sei sicuro di voler eseguire l\'aggiornamento? L\'applicazione potrebbe riavviarsi.')) {
            return;
        }
        
        try {
            this.notify('⏳ Aggiornamento in corso...', 'info');
            
            const response = await fetch('/api/updates/run', {
                method: 'POST'
            });
            
            const data = await response.json();
            
            if (data.status === 'success') {
                console.log('✅ Aggiornamento completato');
                this.notify('✅ Aggiornamento completato con successo!', 'success');
                this.hideUpdatesBanner();
                
                // Ricarica la pagina dopo 2 secondi
                setTimeout(() => {
                    location.reload();
                }, 2000);
            } else {
                console.error('❌ Errore aggiornamento:', data.message);
                this.notify(`Errore: ${data.message}`, 'error');
            }
        } catch (error) {
            console.error('❌ Errore durante l\'aggiornamento:', error);
            this.notify('Errore durante l\'aggiornamento', 'error');
        }
    }
    
    notify(message, type = 'info') {
        // Usa il sistema di notifiche globale se disponibile
        if (typeof showNotification === 'function') {
            showNotification(message, type);
        } else {
            console.log(`[${type.toUpperCase()}] ${message}`);
        }
    }
    
    destroy() {
        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }
        if (this.updatesBanner) {
            this.updatesBanner.remove();
            this.updatesBanner = null;
        }
    }
}

// Istanza globale
let updateChecker = null;

// Inizializza quando il DOM è pronto
document.addEventListener('DOMContentLoaded', () => {
    updateChecker = new UpdateChecker();
});

// Cleanup quando la pagina si chiude
window.addEventListener('beforeunload', () => {
    if (updateChecker) {
        updateChecker.destroy();
    }
});
