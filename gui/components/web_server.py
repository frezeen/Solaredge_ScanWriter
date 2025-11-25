#!/usr/bin/env python3
"""
Web Server Component - Separazione responsabilità
"""

from typing import Optional
from dataclasses import dataclass
from pathlib import Path
from aiohttp import web
from app_logging.universal_logger import get_logger


@dataclass(frozen=True)
class ServerConfig:
    """Configurazione immutabile del server"""
    host: str = '0.0.0.0'
    port: int = 8092
    template_dir: Path = Path("gui/templates")
    static_dir: Path = Path("gui/static")


class WebServer:
    """Server web dedicato - Single Responsibility"""
    
    def __init__(self, config: ServerConfig, route_handler):
        self.config = config
        self.route_handler = route_handler
        self.logger = get_logger("WebServer")
        self.app: Optional[web.Application] = None
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None

    def create_app(self) -> web.Application:
        """Crea applicazione web con routes"""
        self.app = web.Application()
        self.route_handler.register_routes(self.app)
        return self.app

    async def start(self) -> tuple[web.AppRunner, web.TCPSite]:
        """Avvia server web"""
        try:
            self.runner = web.AppRunner(self.create_app())
            await self.runner.setup()
            
            self.site = web.TCPSite(self.runner, self.config.host, self.config.port)
            await self.site.start()
            
            self.logger.info(f"Server avviato su {self.config.host}:{self.config.port}")
            return self.runner, self.site
            
        except Exception as e:
            self.logger.error(f"Errore avvio server: {e}")
            raise

    async def stop(self):
        """Ferma server web"""
        if self.runner:
            await self.runner.cleanup()
