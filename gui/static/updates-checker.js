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
                    <span class="updates-text" id="updatesBannerText">Aggiornamenti disponibili!</span>
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
        const { updates_available, remote_commits, message, restart_required } = data;
        
        if (restart_required) {
            // Riavvia automaticamente se necessario
            this.restartService();
        } else if (updates_available) {
            console.log(`📦 Aggiornamenti disponibili: ${remote_commits} commit`);
            this.showUpdatesBanner(remote_commits);
            this.notify(`${message}`, 'info');
        } else {
            console.log('✅ Sei già aggiornato');
            this.hideUpdatesBanner();
            this.notify('✅ Sei già aggiornato', 'success');
        }
    }
    
    showUpdatesBanner(commits = 0) {
        if (this.updatesBanner) {
            // Aggiorna il testo con il numero di commit
            const textElement = this.updatesBanner.querySelector('#updatesBannerText');
            if (textElement) {
                const commitText = commits === 1 ? '1 commit' : `${commits} commit`;
                textElement.textContent = `Aggiornamenti disponibili: ${commitText}`;
            }
            this.updatesBanner.classList.remove('hidden');
        }
    }
    
    hideUpdatesBanner() {
        if (this.updatesBanner) {
            this.updatesBanner.classList.add('hidden');
        }
    }
    
    async runUpdate() {
        try {
            // Prima controlla se ci sono aggiornamenti
            this.notify('🔍 Controllo aggiornamenti...', 'info');
            
            const checkResponse = await fetch('/api/updates/check');
            const checkData = await checkResponse.json();
            
            if (checkData.status === 'success' && !checkData.updates_available) {
                console.log('✅ Nessun aggiornamento disponibile');
                this.notify('✅ Sei già aggiornato, nessun aggiornamento da applicare', 'success');
                this.hideUpdatesBanner();
                return;
            }
            
            // Ci sono aggiornamenti, chiedi conferma
            if (!confirm('Sei sicuro di voler eseguire l\'aggiornamento?\n\nIl servizio verrà riavviato automaticamente.')) {
                return;
            }
            
            this.notify('⏳ Aggiornamento in corso...', 'info');
            
            const response = await fetch('/api/updates/run', {
                method: 'POST'
            });
            
            const data = await response.json();
            
            if (data.status === 'success') {
                console.log('✅ Aggiornamento completato');
                this.hideUpdatesBanner();
                
                // Riavvia automaticamente il servizio
                this.notify('✅ Aggiornamento completato! Riavvio servizio...', 'success');
                setTimeout(() => {
                    this.restartService();
                }, 1500);
            } else {
                console.error('❌ Errore aggiornamento:', data.message);
                this.notify(`Errore: ${data.message}`, 'error');
            }
        } catch (error) {
            console.error('❌ Errore durante l\'aggiornamento:', error);
            this.notify('Errore durante l\'aggiornamento', 'error');
        }
    }
    
    async restartService() {
        try {
            this.notify('🔄 Riavvio servizio in corso... La pagina si ricaricherà automaticamente.', 'info');
            
            // Invia richiesta di riavvio (potrebbe disconnettersi)
            fetch('/api/updates/restart', {
                method: 'POST'
            }).catch(() => {
                // Ignora errori di connessione (normale durante riavvio)
                console.log('Servizio in riavvio...');
            });
            
            // Attendi 5 secondi e prova a riconnettersi
            setTimeout(() => {
                this.waitForReconnection();
            }, 5000);
            
        } catch (error) {
            console.error('❌ Errore durante il riavvio:', error);
            // Prova comunque a riconnettersi
            setTimeout(() => {
                this.waitForReconnection();
            }, 5000);
        }
    }
    
    async waitForReconnection() {
        console.log('🔄 Tentativo di riconnessione...');
        
        let attempts = 0;
        const maxAttempts = 20; // 20 tentativi = 1 minuto
        
        const tryReconnect = async () => {
            attempts++;
            
            try {
                const response = await fetch('/api/ping', {
                    method: 'GET',
                    cache: 'no-cache'
                });
                
                if (response.ok) {
                    console.log('✅ Riconnesso!');
                    this.notify('✅ Servizio riavviato! Ricaricamento...', 'success');
                    setTimeout(() => {
                        location.reload();
                    }, 1000);
                    return;
                }
            } catch (error) {
                // Server non ancora disponibile
            }
            
            if (attempts < maxAttempts) {
                console.log(`Tentativo ${attempts}/${maxAttempts}...`);
                setTimeout(tryReconnect, 3000); // Riprova ogni 3 secondi
            } else {
                console.error('❌ Timeout riconnessione');
                this.notify('⚠️ Timeout riconnessione. Ricarica manualmente la pagina.', 'warning');
            }
        };
        
        tryReconnect();
    }
    
    notify(message, type = 'info') {
        // Usa il sistema di notifiche globale
        if (typeof notify === 'function') {
            notify(message, type);
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
