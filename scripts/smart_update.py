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

# Add project root to Python path for imports
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Now we can import project modules
try:
    from app_logging.universal_logger import get_logger
    from config.config_manager import ConfigManager
    USE_PROJECT_MODULES = True
except ImportError:
    # Silent fallback to basic logging
    import logging
    USE_PROJECT_MODULES = False

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
        "cookies",
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
    
    # Timeout configurations
    service_start_timeout: int = 3
    command_timeout: int = 300  # 5 minutes default for commands
    git_timeout: int = 600      # 10 minutes for git operations
    backup_dir_name: str = ".temp_config_backup"


class SmartUpdater:
    """Sistema di aggiornamento intelligente per SolarEdge Data Collector"""
    
    def __init__(self, project_root: str = ".", config_manager=None):
        self.project_root = Path(project_root).resolve()
        
        # Setup logging - use project logger if available, fallback to basic
        if USE_PROJECT_MODULES:
            self.logger = get_logger(__name__)
            try:
                self.config_manager = config_manager or ConfigManager()
            except Exception:
                self.config_manager = None
        else:
            # Silent logging for fallback
            logging.basicConfig(level=logging.ERROR)  # Only show errors
            self.logger = logging.getLogger(__name__)
            self.config_manager = None
        
        self.config = UpdateConfig()
        self.update_metrics = {
            'start_time': None,
            'end_time': None,
            'steps_completed': [],
            'errors_encountered': []
        }
        
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
                               check: bool = True, timeout: Optional[int] = 300) -> subprocess.CompletedProcess:
        """Esegue comando asincrono con logging e timeout"""
        try:
            # Usa asyncio.create_subprocess_exec per operazioni async
            if capture_output:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=self.project_root
                )
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
                
                # Crea oggetto compatibile con subprocess.CompletedProcess
                result = subprocess.CompletedProcess(
                    cmd, process.returncode, 
                    stdout.decode() if stdout else None,
                    stderr.decode() if stderr else None
                )
            else:
                process = await asyncio.create_subprocess_exec(*cmd, cwd=self.project_root)
                await asyncio.wait_for(process.wait(), timeout=timeout)
                result = subprocess.CompletedProcess(cmd, process.returncode)
            
            if check and result.returncode != 0:
                raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
                
            return result
            
        except asyncio.TimeoutError:
            self.log(f"Command timed out after {timeout}s", "ERROR")
            raise
        except subprocess.CalledProcessError as e:
            self.log(f"Command failed: {e}", "ERROR")
            if e.stdout:
                self.log(f"Stdout: {e.stdout}", "ERROR")
            if e.stderr:
                self.log(f"Stderr: {e.stderr}", "ERROR")
            raise
    
    def run_command(self, cmd: List[str], capture_output: bool = True, 
                   check: bool = True) -> subprocess.CompletedProcess:
        """Wrapper sincrono per compatibilità"""
        try:
            result = subprocess.run(
                cmd, 
                capture_output=capture_output,
                text=True,
                check=check,
                cwd=self.project_root
            )
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
                    return service
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                self.logger.debug(f"Service {service} not found or not enabled: {e}")
                continue
        
        self.log("No active systemd service found", "WARNING")
        return None
        
    def stop_service(self, service_name: str) -> bool:
        """Ferma il servizio systemd"""
        try:
            self.run_command(["sudo", "systemctl", "stop", service_name])
            return True
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            self.log(f"Failed to stop service {service_name}: {e}", "WARNING")
            return False
            
    def start_service(self, service_name: str) -> bool:
        """Avvia il servizio systemd"""
        try:
            self.run_command(["sudo", "systemctl", "start", service_name])
            
            # Verifica che sia attivo con timeout configurabile
            time.sleep(self.config.service_start_timeout)
            result = self.run_command(
                ["systemctl", "is-active", service_name],
                capture_output=True,
                check=False
            )
            
            if result.returncode == 0:
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
            self.run_command(["git", "fetch", "origin"])
            
            result = self.run_command([
                "git", "rev-list", "HEAD...origin/main", "--count"
            ])
            
            commits_behind = int(result.stdout.strip())
            has_updates = commits_behind > 0
            
            if has_updates:
                pass  # Found updates - will be handled by caller
            else:
                self.log("Repository is up to date", "SUCCESS")
                
            return has_updates, commits_behind
            
        except Exception as e:
            self.log(f"Failed to check for updates: {e}", "ERROR")
            return False, 0
            
    def apply_git_update(self) -> bool:
        """Applica aggiornamento Git in modo sicuro con timeout configurabile"""
        try:
            # Stash modifiche locali
            self.run_command(["git", "stash", "push", "-m", f"Auto-stash before update {datetime.now()}"])
            
            # Configura strategia di merge se necessario
            try:
                self.run_command(["git", "config", "pull.rebase", "false"])
            except subprocess.CalledProcessError:
                # Non critico se fallisce
                pass
                
            # Prova pull normale con timeout esteso per operazioni Git
            try:
                result = subprocess.run(
                    ["git", "pull", "origin", "main"],
                    capture_output=True,
                    text=True,
                    timeout=self.config.git_timeout,
                    cwd=self.project_root
                )
                if result.returncode == 0:
                    self.log("Git pull successful", "SUCCESS")
                    return True
                else:
                    raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout, result.stderr)
                
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                self.log("Git pull failed, trying reset strategy...", "WARNING")
                
                # Backup aggiuntivo delle modifiche locali
                try:
                    self.run_command([
                        "git", "stash", "push", "-m", 
                        f"Additional changes before reset {datetime.now()}"
                    ])
                except subprocess.CalledProcessError:
                    # Non critico se fallisce
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
                
            restored_count = 0
            for file_path in self.config.preserve_files:
                src = temp_backup / file_path
                dst = self.project_root / file_path
                
                if src.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
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
            # Ripristina permessi eseguibili
            executable_count = 0
            for file_path in self.config.executable_files:
                full_path = self.project_root / file_path
                if full_path.exists():
                    os.chmod(full_path, 0o755)
                    executable_count += 1
                    
            # Determina utente e gruppo per configurazioni
            if os.getuid() == 0:  # Running as root
                config_user = "solaredge" if self._user_exists("solaredge") else "root"
                config_group = config_user
            else:
                config_user = os.getenv("USER", "root")
                config_group = config_user
                
            # Ripristina permessi directory (crea se non esistono)
            dir_count = 0
            for dir_path in self.config.preserve_dirs:
                full_path = self.project_root / dir_path
                try:
                    # Crea directory se non esiste
                    full_path.mkdir(parents=True, exist_ok=True)
                    
                    # Sistema permessi
                    if config_user != "root":
                        shutil.chown(full_path, config_user, config_group)
                    os.chmod(full_path, 0o755)
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
            
        # Check for virtual environment
        venv_pip = self.project_root / "venv" / "bin" / "pip"
        if venv_pip.exists():
            pip_cmd = str(venv_pip)
        else:
            pip_cmd = sys.executable
            
        try:
            if venv_pip.exists():
                # Use venv pip directly
                self.run_command([pip_cmd, "install", "-r", "requirements.txt", "--upgrade"])
            else:
                # Use system python with pip module
                self.run_command([pip_cmd, "-m", "pip", "install", "-r", "requirements.txt", "--upgrade"])
            self.log("Dependencies updated successfully", "SUCCESS")
            return True
        except Exception as e:
            self.log(f"Failed to update dependencies: {e}", "ERROR")
            return False
            
    def validate_configuration(self) -> bool:
        """Valida la configurazione dopo l'aggiornamento seguendo le linee guida del progetto"""
        try:
            # 1. Test import del config manager (pattern del progetto)
            validation_script = """
import sys
try:
    from config.config_manager import get_config_manager
    config_manager = get_config_manager()
    
    # Test basic configuration access
    api_config = config_manager.get_solaredge_api_config()
    print("Configuration validation: SUCCESS")
    sys.exit(0)
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"Configuration error: {e}")
    sys.exit(2)
"""
            
            # Use venv python if available, fallback to system python
            venv_python = self.project_root / "venv" / "bin" / "python3"
            
            if venv_python.exists():
                python_cmd = str(venv_python)
            else:
                python_cmd = sys.executable
            
            result = self.run_command([
                python_cmd, "-c", validation_script
            ])
            
            # 2. Verifica file di configurazione essenziali
            missing_files = []
            for config_file in self.config.preserve_files:
                if not (self.project_root / config_file).exists():
                    missing_files.append(config_file)
            
            if missing_files:
                self.log(f"Missing configuration files: {missing_files}", "WARNING")
                # Non è critico se alcuni file mancano
            
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
        self.log("🎉 Smart update completed successfully!", "SUCCESS")
    
    def _log_update_metrics(self) -> None:
        """Log delle metriche dell'aggiornamento per monitoraggio"""
        # Metrics logging removed for cleaner output
        pass
            
        if self.update_metrics['errors_encountered']:
            self.log(f"Errors encountered: {len(self.update_metrics['errors_encountered'])}", "WARNING")
    
    def run_update(self, force: bool = False) -> bool:
        """Esegue l'aggiornamento completo con metriche"""
        self.update_metrics['start_time'] = datetime.now()
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
            self.update_metrics['end_time'] = datetime.now()
            self._log_update_completion(service_name)
            self._log_update_metrics()
            return True
            
        except Exception as e:
            self.update_metrics['end_time'] = datetime.now()
            self.update_metrics['errors_encountered'].append(str(e))
            self.log(f"Update failed with error: {e}", "ERROR")
            self.logger.exception("Detailed error information:")
            self._log_update_metrics()
            return False


async def main_async() -> int:
    """Entry point asincrono per lo script"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Smart Update System for SolarEdge Data Collector")
    parser.add_argument("--force", action="store_true", help="Force update even if no changes detected")
    parser.add_argument("--check-only", action="store_true", help="Only check for updates, don't apply")
    
    args = parser.parse_args()
    
    try:
        # Create updater with ConfigManager if available
        config_manager = None
        if USE_PROJECT_MODULES:
            try:
                config_manager = ConfigManager()
            except Exception:
                pass  # Silent fallback
        
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