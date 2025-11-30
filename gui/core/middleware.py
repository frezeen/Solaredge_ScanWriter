#!/usr/bin/env python3
"""
Middleware Components - Centralized HTTP middleware
"""

import time
from typing import Callable
from aiohttp import web
from app_logging.universal_logger import get_logger


class ErrorHandlerMiddleware:
    """
    Gestisce errori HTTP con logging centralizzato

    Cattura tutte le eccezioni non gestite e restituisce risposte JSON appropriate.
    """

    def __init__(self, logger=None):
        self.logger = logger or get_logger("ErrorHandler")

    @web.middleware
    async def middleware(self, request: web.Request, handler: Callable) -> web.Response:
        """Middleware per gestione errori"""
        try:
            return await handler(request)
        except web.HTTPException as e:
            # HTTP exceptions (404, 500, etc.) - passa attraverso
            raise
        except Exception as e:
            # Errori non gestiti - logga e restituisci 500
            self.logger.error(f"[ErrorHandler] Unhandled error on {request.path}: {e}", exc_info=True)
            return web.json_response(
                {
                    "error": "Internal server error",
                    "message": str(e),
                    "path": request.path
                },
                status=500
            )


class RequestLoggingMiddleware:
    """
    Logga tutte le richieste HTTP con timing

    Registra metodo, path, status code e tempo di esecuzione per ogni richiesta.
    """

    def __init__(self, logger=None):
        self.logger = logger or get_logger("RequestLogger")

    @web.middleware
    async def middleware(self, request: web.Request, handler: Callable) -> web.Response:
        """Middleware per logging richieste"""
        start_time = time.time()

        # Log richiesta in arrivo (solo per API, non per static files)
        if request.path.startswith('/api/'):
            self.logger.debug(f"[→] {request.method} {request.path}")

        try:
            response = await handler(request)

            # Log risposta con timing (solo per API)
            if request.path.startswith('/api/'):
                elapsed = (time.time() - start_time) * 1000  # ms
                self.logger.debug(
                    f"[←] {request.method} {request.path} → {response.status} ({elapsed:.1f}ms)"
                )

            return response

        except Exception as e:
            # Log errore con timing
            elapsed = (time.time() - start_time) * 1000  # ms
            self.logger.error(
                f"[✗] {request.method} {request.path} → ERROR ({elapsed:.1f}ms): {e}"
            )
            raise


class CORSMiddleware:
    """
    Gestisce CORS headers per accesso cross-origin

    Permette richieste da qualsiasi origine (utile per sviluppo locale).
    In produzione, configurare allowed_origins specifici.
    """

    def __init__(self, allowed_origins='*', allowed_methods='*', allowed_headers='*'):
        self.allowed_origins = allowed_origins
        self.allowed_methods = allowed_methods
        self.allowed_headers = allowed_headers
        self.logger = get_logger("CORS")

    @web.middleware
    async def middleware(self, request: web.Request, handler: Callable) -> web.Response:
        """Middleware per CORS"""

        # Handle preflight OPTIONS request
        if request.method == 'OPTIONS':
            response = web.Response()
        else:
            response = await handler(request)

        # Aggiungi CORS headers
        response.headers['Access-Control-Allow-Origin'] = self.allowed_origins
        response.headers['Access-Control-Allow-Methods'] = self.allowed_methods
        response.headers['Access-Control-Allow-Headers'] = self.allowed_headers
        response.headers['Access-Control-Allow-Credentials'] = 'true'

        return response


class SecurityHeadersMiddleware:
    """
    Aggiunge security headers per protezione base

    Headers inclusi:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - X-XSS-Protection: 1; mode=block
    - Content-Security-Policy: default-src 'self'
    """

    def __init__(self):
        self.logger = get_logger("SecurityHeaders")

    @web.middleware
    async def middleware(self, request: web.Request, handler: Callable) -> web.Response:
        """Middleware per security headers"""
        response = await handler(request)

        # Aggiungi security headers
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'

        # CSP permissivo per dashboard (inline scripts necessari)
        # Permette Google Fonts e jsDelivr CDN per librerie esterne
        # In produzione, considerare CSP più restrittivo con nonce
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "img-src 'self' data:; "
            "font-src 'self' data: https://fonts.gstatic.com; "
            "connect-src 'self';"
        )

        return response


# Factory function per creare middleware stack
def create_middleware_stack(logger=None):
    """
    Crea stack di middleware in ordine corretto

    Ordine importante:
    1. ErrorHandler - cattura errori da tutti i middleware successivi
    2. RequestLogging - logga tutte le richieste
    3. CORS - gestisce cross-origin
    4. SecurityHeaders - aggiunge headers di sicurezza

    Args:
        logger: Logger opzionale da passare ai middleware

    Returns:
        Lista di middleware pronti per app.middlewares.extend()
    """
    error_handler = ErrorHandlerMiddleware(logger)
    request_logger = RequestLoggingMiddleware(logger)
    cors = CORSMiddleware()
    security = SecurityHeadersMiddleware()

    return [
        error_handler.middleware,
        request_logger.middleware,
        cors.middleware,
        security.middleware
    ]
