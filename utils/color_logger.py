#!/usr/bin/env python3
"""Color Logger - Utility per log colorati cross-platform"""

try:
    from colorama import Fore, Style, init
    init(autoreset=True)  # Auto-reset dopo ogni print
    COLORS_AVAILABLE = True
except ImportError:
    COLORS_AVAILABLE = False
    # Fallback senza colori
    class Fore:
        RED = GREEN = YELLOW = BLUE = CYAN = MAGENTA = WHITE = RESET = ""
    class Style:
        BRIGHT = DIM = RESET_ALL = ""


class ColorLogger:
    """Wrapper per aggiungere colori ai log"""
    
    @staticmethod
    def success(msg: str) -> str:
        """Verde per successi"""
        return f"{Fore.GREEN}{msg}{Style.RESET_ALL}"
    
    @staticmethod
    def error(msg: str) -> str:
        """Rosso per errori"""
        return f"{Fore.RED}{msg}{Style.RESET_ALL}"
    
    @staticmethod
    def warning(msg: str) -> str:
        """Giallo per warning"""
        return f"{Fore.YELLOW}{msg}{Style.RESET_ALL}"
    
    @staticmethod
    def info(msg: str) -> str:
        """Ciano per info"""
        return f"{Fore.CYAN}{msg}{Style.RESET_ALL}"
    
    @staticmethod
    def highlight(msg: str) -> str:
        """Magenta per highlight"""
        return f"{Fore.MAGENTA}{Style.BRIGHT}{msg}{Style.RESET_ALL}"
    
    @staticmethod
    def dim(msg: str) -> str:
        """Grigio per dettagli secondari"""
        return f"{Style.DIM}{msg}{Style.RESET_ALL}"
    
    @staticmethod
    def bold(msg: str) -> str:
        """Bianco brillante per titoli"""
        return f"{Style.BRIGHT}{msg}{Style.RESET_ALL}"


# Istanza globale
color = ColorLogger()
