#!/usr/bin/env python3
"""
SolarEdge Data Collector - Smart Update System
Sistema di aggiornamento intelligente che preserva configurazioni e permessi
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Tuple

class SmartUpdater:
    """Sistema di aggiornamento intelligente per SolarEdge Data Collector"""
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root).resolve()
        
        # File e directory critici da preservare
        self.preserve_files = [
            ".env",
            "config/main.yaml",
            "config/sources/api_endpoints.yaml",
            "config/sources/web_endpoints.yaml", 
            "config/sources/modbus_endpoints.yaml",
        ]
        
        # Directory da preservare i permessi
        self.preserve_dirs = [
            "logs",
            "cache", 
            "scripts",
            "config"
        ]

        
        # File che devono essere eseguibili
        self.executable_files = [
            "update.sh",
            "install.sh", 
            "setup-permissions.sh",
            "scripts/smart_update.py",
            "scripts/cleanup_logs.sh",
            "venv.sh"
        ]
        
        # Servizi systemd possibili
        self.possible_services = ["solaredge-collector", "solaredge", "collector"]
        
    def log(self, message: str, level: str = "INFO"):
        """Log con timestamp e colori"""
        colors = {
            "INFO": "\033[0;34m",    # Blue
            "SUCCESS": "\033[0;32m", # Green  
            "WARNING": "\033[1;33m", # Yellow
            "ERROR": "\033[0;31m",   # Red
            "RESET": "\033[0m"       # Reset
        }
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        color = colors.get(level, colors["INFO"])
        reset = colors["RESET"]
        
        icons = {
            "INFO": "ℹ️",
            "SUCCESS": "✅", 
            "WARNING": "⚠️",
            "ERROR": "❌"
        }
        
        icon = icons.get(level, "•")
        print(f"{color}[{timestamp}] {icon} {message}{reset}")
        
    def run_command(self, cmd: List[str], capture_output: bool = True, 
                   check: bool = True) -> subprocess.CompletedProcess:
        """Esegue comando con logging"""
        self.log(f"Executing: {' '.join(cmd)}")
        try:
            result = subprocess.run(
                cmd, 
                capture_output=capture_output,
                text=True,
                check=check,
                cwd=self.project_root
            )
            if result.stdout and capture_output:
                self.log(f"Output: {result.stdout.strip()}")
            return result
        except subprocess.CalledProcessError as e:
            self.log(f"Command failed: {e}", "ERROR")
            if e.stdout:
                self.log(f"Stdout: {e.stdout}", "ERROR")
            if e.stderr:
                self.log(f"Stderr: {e.stderr}", "ERROR")
            raise
            

            
    def find_active_service(self) -> Optional[str]:
        """Trova il servizio systemd attivo"""
        for service in self.possible_services:
            try:
                result = self.run_command(
                    ["systemctl", "is-enabled", service],
                    capture_output=True,
                    check=False
                )
                if result.returncode == 0:
                    return service
            except:
                continue
        return None
        
    def stop_service(self, service_name: str) -> bool:
        """Ferma il servizio systemd"""
        try:
            self.log(f"Stopping service {service_name}...")
            self.run_command(["sudo", "systemctl", "stop", service_name])
            self.log(f"Service {service_name} stopped", "SUCCESS")
            return True
        except:
            self.log(f"Failed to stop service {service_name}", "WARNING")
            return False
            
    def start_service(self, service_name: str) -> bool:
        """Avvia il servizio systemd"""
        try:
            self.log(f"Starting service {service_name}...")
            self.run_command(["sudo", "systemctl", "start", service_name])
            
            # Verifica che sia attivo
            import time
            time.sleep(3)
            result = self.run_command(
                ["systemctl", "is-active", service_name],
                capture_output=True,
                check=False
            )
            
            if result.returncode == 0:
                self.log(f"Service {service_name} started successfully", "SUCCESS")
                return True
            else:
                self.log(f"Service {service_name} may not be active", "WARNING")
                return False
        except:
            self.log(f"Failed to start service {service_name}", "ERROR")
            return False
            
    def backup_configs(self) -> bool:
        """Backup temporaneo delle configurazioni durante l'aggiornamento"""
        try:
            self.log("Creating temporary backup of configurations...")
            
            # Crea backup temporaneo
            temp_backup = self.project_root / ".temp_config_backup"
            if temp_backup.exists():
                shutil.rmtree(temp_backup)
            temp_backup.mkdir()
            
            # Backup solo file di configurazione essenziali
            for file_path in self.preserve_files:
                src = self.project_root / file_path
                if src.exists():
                    dst = temp_backup / file_path
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    self.log(f"Backed up: {file_path}")
                    
            return True
            
        except Exception as e:
            self.log(f"Failed to backup configurations: {e}", "ERROR")
            return False
        
    def get_current_commit(self) -> str:
        """Ottiene l'hash del commit corrente"""
        try:
            result = self.run_command(["git", "rev-parse", "HEAD"])
            return result.stdout.strip()
        except:
            return "unknown"
            
    def check_for_updates(self) -> Tuple[bool, int]:
        """Controlla se ci sono aggiornamenti disponibili"""
        try:
            self.log("Checking for updates...")
            self.run_command(["git", "fetch", "origin"])
            
            result = self.run_command([
                "git", "rev-list", "HEAD...origin/main", "--count"
            ])
            
            commits_behind = int(result.stdout.strip())
            has_updates = commits_behind > 0
            
            if has_updates:
                self.log(f"Found {commits_behind} new commits", "INFO")
            else:
                self.log("Repository is up to date", "SUCCESS")
                
            return has_updates, commits_behind
            
        except Exception as e:
            self.log(f"Failed to check for updates: {e}", "ERROR")
            return False, 0
            
    def apply_git_update(self) -> bool:
        """Applica aggiornamento Git in modo sicuro"""
        try:
            # Stash modifiche locali
            self.log("Stashing local changes...")
            self.run_command(["git", "stash", "push", "-m", f"Auto-stash before update {datetime.now()}"])
            
            # Configura strategia di merge se necessario
            try:
                self.run_command(["git", "config", "pull.rebase", "false"])
            except:
                pass
                
            # Prova pull normale
            try:
                self.log("Attempting git pull...")
                self.run_command(["git", "pull", "origin", "main"])
                self.log("Git pull successful", "SUCCESS")
                return True
                
            except subprocess.CalledProcessError:
                self.log("Git pull failed, trying reset strategy...", "WARNING")
                
                # Backup aggiuntivo delle modifiche locali
                try:
                    self.run_command([
                        "git", "stash", "push", "-m", 
                        f"Additional changes before reset {datetime.now()}"
                    ])
                except:
                    pass
                    
                # Reset hard
                self.run_command(["git", "reset", "--hard", "origin/main"])
                self.log("Git reset successful", "SUCCESS")
                return True
                
        except Exception as e:
            self.log(f"Git update failed: {e}", "ERROR")
            return False
            
    def restore_configs(self) -> bool:
        """Ripristina configurazioni dal backup temporaneo"""
        try:
            temp_backup = self.project_root / ".temp_config_backup"
            if not temp_backup.exists():
                self.log("No temporary backup found", "WARNING")
                return True
                
            self.log("Restoring configurations...")
            
            restored_count = 0
            for file_path in self.preserve_files:
                src = temp_backup / file_path
                dst = self.project_root / file_path
                
                if src.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    self.log(f"Restored: {file_path}")
                    restored_count += 1
                    
            # Rimuovi backup temporaneo
            shutil.rmtree(temp_backup)
            
            self.log(f"Restored {restored_count} configuration files", "SUCCESS")
            return True
            
        except Exception as e:
            self.log(f"Failed to restore configurations: {e}", "ERROR")
            return False
            
    def fix_permissions(self) -> bool:
        """Ripristina tutti i permessi necessari"""
        try:
            self.log("Fixing permissions...")
            
            # Ripristina permessi eseguibili
            for file_path in self.executable_files:
                full_path = self.project_root / file_path
                if full_path.exists():
                    os.chmod(full_path, 0o755)
                    self.log(f"Fixed executable: {file_path}")
                    
            # Determina utente e gruppo per configurazioni
            if os.getuid() == 0:  # Running as root
                config_user = "solaredge" if self.user_exists("solaredge") else "root"
                config_group = config_user
            else:
                config_user = os.getenv("USER", "root")
                config_group = config_user
                
            # Ripristina permessi directory
            for dir_path in self.preserve_dirs:
                full_path = self.project_root / dir_path
                if full_path.exists():
                    try:
                        if config_user != "root":
                            shutil.chown(full_path, config_user, config_group)
                        os.chmod(full_path, 0o755)
                        self.log(f"Fixed directory permissions: {dir_path}")
                    except PermissionError:
                        self.log(f"Cannot change ownership of {dir_path}", "WARNING")
                        
            # Ripristina permessi file di configurazione
            for file_path in self.preserve_files:
                full_path = self.project_root / file_path
                if full_path.exists():
                    try:
                        if config_user != "root":
                            shutil.chown(full_path, config_user, config_group)
                        os.chmod(full_path, 0o664)
                        self.log(f"Fixed file permissions: {file_path}")
                    except PermissionError:
                        self.log(f"Cannot change ownership of {file_path}", "WARNING")
                        
            self.log("Permissions fixed successfully", "SUCCESS")
            return True
            
        except Exception as e:
            self.log(f"Failed to fix permissions: {e}", "ERROR")
            return False
            
    def user_exists(self, username: str) -> bool:
        """Verifica se un utente esiste nel sistema"""
        try:
            import pwd
            pwd.getpwnam(username)
            return True
        except KeyError:
            return False
            
    def update_dependencies(self) -> bool:
        """Aggiorna dipendenze Python"""
        requirements_file = self.project_root / "requirements.txt"
        if not requirements_file.exists():
            self.log("requirements.txt not found, skipping dependency update")
            return True
            
        try:
            self.log("Updating Python dependencies...")
            self.run_command([
                sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "--upgrade"
            ])
            self.log("Dependencies updated successfully", "SUCCESS")
            return True
        except Exception as e:
            self.log(f"Failed to update dependencies: {e}", "ERROR")
            return False
            
    def validate_configuration(self) -> bool:
        """Valida la configurazione dopo l'aggiornamento"""
        try:
            self.log("Validating configuration...")
            
            # Test import del config manager
            result = self.run_command([
                sys.executable, "-c", 
                "from config.config_manager import get_config_manager; get_config_manager()"
            ])
            
            self.log("Configuration validation successful", "SUCCESS")
            return True
            
        except Exception as e:
            self.log(f"Configuration validation failed: {e}", "ERROR")
            return False
            
    def run_update(self, force: bool = False) -> bool:
        """Esegue l'aggiornamento completo"""
        self.log("🚀 Starting Smart Update System", "INFO")
        self.log("=" * 50, "INFO")
        
        try:
            # 1. Verifica aggiornamenti disponibili
            has_updates, commits_count = self.check_for_updates()
            if not has_updates and not force:
                self.log("No updates available", "SUCCESS")
                return True
                
            # 2. Trova e ferma servizio
            service_name = self.find_active_service()
            service_was_running = False
            if service_name:
                service_was_running = self.stop_service(service_name)
                
            # 3. Backup temporaneo configurazioni
            if not self.backup_configs():
                self.log("Configuration backup failed, aborting", "ERROR")
                return False
            
            # 4. Applica aggiornamento Git
            if not self.apply_git_update():
                self.log("Git update failed, aborting", "ERROR")
                return False
                
            # 5. Ripristina configurazioni
            if not self.restore_configs():
                self.log("Configuration restore failed", "ERROR")
                return False
                
            # 6. Ripristina permessi
            if not self.fix_permissions():
                self.log("Permission fix failed", "ERROR")
                return False
                
            # 7. Aggiorna dipendenze
            if not self.update_dependencies():
                self.log("Dependency update failed", "WARNING")
                # Non è critico, continua
                
            # 8. Valida configurazione
            if not self.validate_configuration():
                self.log("Configuration validation failed", "ERROR")
                self.log("Consider running rollback", "WARNING")
                return False
                
            # 9. Riavvia servizio
            if service_was_running and service_name:
                self.start_service(service_name)
                
            self.log("=" * 50, "SUCCESS")
            self.log("🎉 Smart update completed successfully!", "SUCCESS")
            self.log(f"Current commit: {self.get_current_commit()[:8]}", "INFO")
            
            if service_name:
                self.log(f"Monitor logs: sudo journalctl -u {service_name} -f", "INFO")
            else:
                self.log("Start manually: python main.py", "INFO")
                
            return True
            
        except Exception as e:
            self.log(f"Update failed with error: {e}", "ERROR")
            return False


def main():
    """Entry point per lo script"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Smart Update System for SolarEdge Data Collector")
    parser.add_argument("--force", action="store_true", help="Force update even if no changes detected")
    parser.add_argument("--check-only", action="store_true", help="Only check for updates, don't apply")
    
    args = parser.parse_args()
    
    updater = SmartUpdater()
    
    if args.check_only:
        has_updates, count = updater.check_for_updates()
        if has_updates:
            print(f"Updates available: {count} commits")
            sys.exit(0)
        else:
            print("No updates available")
            sys.exit(1)
    else:
        success = updater.run_update(force=args.force)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()