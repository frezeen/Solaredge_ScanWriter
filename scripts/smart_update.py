#!/usr/bin/env python3
"""
SolarEdge Data Collector - Smart Update System
Sistema di aggiornamento intelligente che preserva configurazioni e permessi
"""

# Standard library (alphabetical)
import asyncio
import os
import pwd
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

# Local modules (alphabetical)
from app_logging.universal_logger import get_logger
from config.config_manager import ConfigManager

@dataclass(frozen=True)
class UpdateConfig:
    """Configurazione immutabile per il sistema di aggiornamento"""
    preserve_files: Tuple[str, ...] = (
        ".env",
        "config/main.yaml",
        "config/sources/api_endpoints.yaml",
        "config/sources/web_endpoints.yaml", 
        "config/sources/modbus_endpoints.yaml",
    )
    
    preserve_dirs: Tuple[str, ...] = (
        "logs",
        "cache", 
        "scripts",
        "config"
    )
    
    executable_files: Tuple[str, ...] = (
        "update.sh",
        "install.sh", 
        "setup-permissions.sh",
        "scripts/smart_update.py",
        "scripts/cleanup_logs.sh",
        "venv.sh"
    )
    
    possible_services: Tuple[str, ...] = (
        "solaredge-scanwriter", 
        "solaredge-collector", 
        "solaredge", 
        "collector"
    )
    
    service_start_timeout: int = 3
    backup_dir_name: str = ".temp_config_backup"


class SmartUpdater:
    """Sistema di aggiornamento intelligente per SolarEdge Data Collector"""
    
    def __init__(self, project_root: str = ".", config_manager: Optional[ConfigManager] = None):
        self.project_root = Path(project_root).resolve()
        self.logger = get_logger(__name__)
        self.config = UpdateConfig()
        
        # Ensure config has all required attributes
        if not hasattr(self.config, 'preserve_dirs'):
            self.logger.error("UpdateConfig missing preserve_dirs attribute")
            raise AttributeError("UpdateConfig missing preserve_dirs attribute")
            
        try:
            self.config_manager = config_manager or ConfigManager()
        except Exception as e:
            # Fallback if ConfigManager fails to initialize
            self.logger.warning(f"ConfigManager initialization failed: {e}")
            self.config_manager = None
        
    def _log_with_color(self, message: str, level: str = "INFO") -> None:
        """Log con colori per output console (mantiene compatibilità con output esistente)"""
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
        
        # Log anche nel sistema di logging del progetto
        if level == "ERROR":
            self.logger.error(message)
        elif level == "WARNING":
            self.logger.warning(message)
        elif level == "SUCCESS":
            self.logger.info(f"SUCCESS: {message}")
        else:
            self.logger.info(message)
    
    def log(self, message: str, level: str = "INFO") -> None:
        """Wrapper per compatibilità con codice esistente"""
        self._log_with_color(message, level)
        
    async def run_command_async(self, cmd: List[str], capture_output: bool = True, 
                               check: bool = True) -> subprocess.CompletedProcess:
        """Esegue comando asincrono con logging"""
        self.log(f"Executing: {' '.join(cmd)}")
        try:
            # Usa asyncio.create_subprocess_exec per operazioni async
            if capture_output:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=self.project_root
                )
                stdout, stderr = await process.communicate()
                
                # Crea oggetto compatibile con subprocess.CompletedProcess
                result = subprocess.CompletedProcess(
                    cmd, process.returncode, 
                    stdout.decode() if stdout else None,
                    stderr.decode() if stderr else None
                )
            else:
                process = await asyncio.create_subprocess_exec(*cmd, cwd=self.project_root)
                await process.wait()
                result = subprocess.CompletedProcess(cmd, process.returncode)
            
            if check and result.returncode != 0:
                raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
                
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
    
    def run_command(self, cmd: List[str], capture_output: bool = True, 
                   check: bool = True) -> subprocess.CompletedProcess:
        """Wrapper sincrono per compatibilità (deprecato - usa run_command_async)"""
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
        for service in self.config.possible_services:
            try:
                result = self.run_command(
                    ["systemctl", "is-enabled", service],
                    capture_output=True,
                    check=False
                )
                if result.returncode == 0:
                    self.log(f"Found active service: {service}")
                    return service
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                self.logger.debug(f"Service {service} not found or not enabled: {e}")
                continue
        
        self.log("No active systemd service found", "WARNING")
        return None
        
    def stop_service(self, service_name: str) -> bool:
        """Ferma il servizio systemd"""
        try:
            self.log(f"Stopping service {service_name}...")
            self.run_command(["sudo", "systemctl", "stop", service_name])
            self.log(f"Service {service_name} stopped", "SUCCESS")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            self.log(f"Failed to stop service {service_name}: {e}", "WARNING")
            return False
            
    def start_service(self, service_name: str) -> bool:
        """Avvia il servizio systemd"""
        try:
            self.log(f"Starting service {service_name}...")
            self.run_command(["sudo", "systemctl", "start", service_name])
            
            # Verifica che sia attivo con timeout configurabile
            time.sleep(self.config.service_start_timeout)
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
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            self.log(f"Failed to start service {service_name}: {e}", "ERROR")
            return False
            
    def backup_configs(self) -> bool:
        """Backup temporaneo delle configurazioni durante l'aggiornamento"""
        try:
            self.log("Creating temporary backup of configurations...")
            
            # Crea backup temporaneo
            temp_backup = self.project_root / self.config.backup_dir_name
            if temp_backup.exists():
                shutil.rmtree(temp_backup)
            temp_backup.mkdir()
            
            backed_up_count = 0
            # Backup solo file di configurazione essenziali
            for file_path in self.config.preserve_files:
                src = self.project_root / file_path
                if src.exists():
                    dst = temp_backup / file_path
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    self.log(f"Backed up: {file_path}")
                    backed_up_count += 1
                else:
                    self.logger.debug(f"Configuration file not found: {file_path}")
            
            self.log(f"Backed up {backed_up_count} configuration files", "SUCCESS")
            return True
            
        except (OSError, PermissionError) as e:
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
            temp_backup = self.project_root / self.config.backup_dir_name
            if not temp_backup.exists():
                self.log("No temporary backup found", "WARNING")
                return True
                
            self.log("Restoring configurations...")
            
            restored_count = 0
            for file_path in self.config.preserve_files:
                src = temp_backup / file_path
                dst = self.project_root / file_path
                
                if src.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    self.log(f"Restored: {file_path}")
                    restored_count += 1
                else:
                    self.logger.debug(f"Backup file not found: {file_path}")
                    
            # Rimuovi backup temporaneo
            shutil.rmtree(temp_backup)
            
            self.log(f"Restored {restored_count} configuration files", "SUCCESS")
            return True
            
        except (OSError, PermissionError) as e:
            self.log(f"Failed to restore configurations: {e}", "ERROR")
            return False
            
    def fix_permissions(self) -> bool:
        """Ripristina tutti i permessi necessari"""
        try:
            self.log("Fixing permissions...")
            
            # Debug: Check if config and its attributes exist
            if not hasattr(self, 'config'):
                self.log("ERROR: SmartUpdater has no config attribute", "ERROR")
                return False
                
            if not hasattr(self.config, 'preserve_dirs'):
                self.log("ERROR: UpdateConfig has no preserve_dirs attribute", "ERROR")
                self.log(f"Available attributes: {dir(self.config)}", "ERROR")
                return False
            
            # Ripristina permessi eseguibili
            executable_count = 0
            for file_path in self.config.executable_files:
                full_path = self.project_root / file_path
                if full_path.exists():
                    os.chmod(full_path, 0o755)
                    self.log(f"Fixed executable: {file_path}")
                    executable_count += 1
                    
            # Determina utente e gruppo per configurazioni
            if os.getuid() == 0:  # Running as root
                config_user = "solaredge" if self._user_exists("solaredge") else "root"
                config_group = config_user
            else:
                config_user = os.getenv("USER", "root")
                config_group = config_user
                
            # Ripristina permessi directory
            dir_count = 0
            for dir_path in self.config.preserve_dirs:
                full_path = self.project_root / dir_path
                if full_path.exists():
                    try:
                        if config_user != "root":
                            shutil.chown(full_path, config_user, config_group)
                        os.chmod(full_path, 0o755)
                        self.log(f"Fixed directory permissions: {dir_path}")
                        dir_count += 1
                    except PermissionError as e:
                        self.log(f"Cannot change ownership of {dir_path}: {e}", "WARNING")
                        
            # Ripristina permessi file di configurazione
            file_count = 0
            for file_path in self.config.preserve_files:
                full_path = self.project_root / file_path
                if full_path.exists():
                    try:
                        if config_user != "root":
                            shutil.chown(full_path, config_user, config_group)
                        os.chmod(full_path, 0o664)
                        self.log(f"Fixed file permissions: {file_path}")
                        file_count += 1
                    except PermissionError as e:
                        self.log(f"Cannot change ownership of {file_path}: {e}", "WARNING")
                        
            self.log(f"Permissions fixed: {executable_count} executables, {dir_count} directories, {file_count} files", "SUCCESS")
            return True
            
        except (OSError, ValueError) as e:
            self.log(f"Failed to fix permissions: {e}", "ERROR")
            return False
            
    def _user_exists(self, username: str) -> bool:
        """Verifica se un utente esiste nel sistema"""
        try:
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
            
    def _prepare_update(self, force: bool) -> Tuple[bool, Optional[str], bool]:
        """Prepara l'aggiornamento: verifica updates e ferma servizi"""
        # 1. Verifica aggiornamenti disponibili
        has_updates, commits_count = self.check_for_updates()
        if not has_updates and not force:
            self.log("No updates available", "SUCCESS")
            return False, None, False
            
        # 2. Trova e ferma servizio
        service_name = self.find_active_service()
        service_was_running = False
        if service_name:
            service_was_running = self.stop_service(service_name)
            
        return True, service_name, service_was_running
    
    def _execute_update_steps(self) -> bool:
        """Esegue i passi principali dell'aggiornamento"""
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
            
        return True
    
    def _finalize_update(self, service_name: Optional[str], service_was_running: bool) -> bool:
        """Finalizza l'aggiornamento: dipendenze, validazione e riavvio servizi"""
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
            
        return True
    
    def _log_update_completion(self, service_name: Optional[str]) -> None:
        """Log finale dell'aggiornamento completato"""
        self.log("=" * 50, "SUCCESS")
        self.log("🎉 Smart update completed successfully!", "SUCCESS")
        self.log(f"Current commit: {self.get_current_commit()[:8]}", "INFO")
        
        if service_name:
            self.log(f"Monitor logs: sudo journalctl -u {service_name} -f", "INFO")
        else:
            self.log("Start manually: python main.py", "INFO")
    
    def run_update(self, force: bool = False) -> bool:
        """Esegue l'aggiornamento completo"""
        self.log("🚀 Starting Smart Update System", "INFO")
        self.log("=" * 50, "INFO")
        
        try:
            # Preparazione
            should_update, service_name, service_was_running = self._prepare_update(force)
            if not should_update:
                return True
                
            # Esecuzione passi principali
            if not self._execute_update_steps():
                return False
                
            # Finalizzazione
            if not self._finalize_update(service_name, service_was_running):
                return False
                
            # Log completamento
            self._log_update_completion(service_name)
            return True
            
        except Exception as e:
            self.log(f"Update failed with error: {e}", "ERROR")
            self.logger.exception("Detailed error information:")
            return False


async def main_async() -> int:
    """Entry point asincrono per lo script"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Smart Update System for SolarEdge Data Collector")
    parser.add_argument("--force", action="store_true", help="Force update even if no changes detected")
    parser.add_argument("--check-only", action="store_true", help="Only check for updates, don't apply")
    
    args = parser.parse_args()
    
    try:
        # Usa ConfigManager se disponibile
        config_manager = None
        try:
            config_manager = ConfigManager()
        except Exception as e:
            print(f"Warning: Could not load ConfigManager: {e}")
        
        updater = SmartUpdater(config_manager=config_manager)
        
        if args.check_only:
            has_updates, count = updater.check_for_updates()
            if has_updates:
                print(f"Updates available: {count} commits")
                return 0
            else:
                print("No updates available")
                return 1
        else:
            success = updater.run_update(force=args.force)
            return 0 if success else 1
            
    except KeyboardInterrupt:
        print("\nUpdate interrupted by user")
        return 130
    except Exception as e:
        print(f"Critical error: {e}")
        return 1


def main() -> None:
    """Entry point sincrono per compatibilità"""
    try:
        # Prova ad eseguire la versione async se possibile
        exit_code = asyncio.run(main_async())
        sys.exit(exit_code)
    except Exception:
        # Fallback alla versione sincrona
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