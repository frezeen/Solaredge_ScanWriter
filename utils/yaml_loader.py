#!/usr/bin/env python3
"""
YAML Loader Utility - Consolidated YAML loading logic
Requirement 2.2: Extract common YAML loading pattern to utility function
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from functools import lru_cache


class YAMLLoader:
    """
    Centralized YAML loading utility with caching and error handling.

    Features:
    - Unified loading interface
    - LRU caching to avoid redundant file reads
    - Environment variable substitution support
    - Consistent error handling
    - Both sync and async support
    """

    def __init__(self):
        # Use basic logging to avoid circular imports with config_manager
        import logging
        self.logger = logging.getLogger("YAMLLoader")
        self._cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}

    def load_yaml(self, file_path: str | Path,
                  substitute_env: bool = True,
                  use_cache: bool = True) -> Dict[str, Any]:
        """
        Load YAML file with optional environment variable substitution and caching.

        Args:
            file_path: Path to YAML file
            substitute_env: Whether to substitute environment variables (${VAR})
            use_cache: Whether to use cached result if available

        Returns:
            Parsed YAML content as dictionary

        Raises:
            FileNotFoundError: If file doesn't exist
            yaml.YAMLError: If YAML parsing fails
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"YAML file not found: {path}")

        # Check cache
        cache_key = str(path.absolute())
        if use_cache and cache_key in self._cache:
            mtime, cached_data = self._cache[cache_key]
            current_mtime = path.stat().st_mtime

            # Return cached data if file hasn't been modified
            if mtime == current_mtime:
                self.logger.debug(f"Cache hit for {path}")
                return cached_data.copy()

        # Load file
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Substitute environment variables if requested
            if substitute_env:
                content = self._substitute_env_vars(content)

            # Parse YAML
            data = yaml.safe_load(content) or {}

            # Cache result
            if use_cache:
                self._cache[cache_key] = (path.stat().st_mtime, data.copy())

            self.logger.debug(f"Loaded YAML from {path}")
            return data

        except yaml.YAMLError as e:
            self.logger.error(f"YAML parsing error in {path}: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error loading YAML from {path}: {e}")
            raise

    def save_yaml(self, file_path: str | Path, data: Dict[str, Any],
                  invalidate_cache: bool = True) -> bool:
        """
        Save dictionary to YAML file.

        Args:
            file_path: Path to save YAML file
            data: Dictionary to save
            invalidate_cache: Whether to invalidate cache for this file

        Returns:
            True if successful, False otherwise
        """
        path = Path(file_path)

        try:
            # Create parent directories if needed
            path.parent.mkdir(parents=True, exist_ok=True)

            # Write YAML
            with open(path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True, indent=2)

            # Invalidate cache
            if invalidate_cache:
                cache_key = str(path.absolute())
                self._cache.pop(cache_key, None)

            self.logger.debug(f"Saved YAML to {path}")
            return True

        except Exception as e:
            self.logger.error(f"Error saving YAML to {path}: {e}")
            return False

    def _substitute_env_vars(self, text: str) -> str:
        """
        Substitute environment variables in format ${VAR_NAME}.

        Args:
            text: Text containing environment variable placeholders

        Returns:
            Text with variables substituted
        """
        import os
        import re

        def replace_var(match):
            var_name = match.group(1)
            return os.environ.get(var_name, match.group(0))

        return re.sub(r'\$\{([^}]+)\}', replace_var, text)

    def invalidate_cache(self, file_path: Optional[str | Path] = None):
        """
        Invalidate cache for specific file or all files.

        Args:
            file_path: Specific file to invalidate, or None for all
        """
        if file_path:
            cache_key = str(Path(file_path).absolute())
            self._cache.pop(cache_key, None)
            self.logger.debug(f"Invalidated cache for {file_path}")
        else:
            self._cache.clear()
            self.logger.debug("Cleared all YAML cache")

    def validate_yaml(self, content: str) -> Tuple[bool, Optional[str]]:
        """
        Validate YAML content without loading to file.

        Args:
            content: YAML content as string

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            yaml.safe_load(content)
            return True, None
        except yaml.YAMLError as e:
            return False, str(e)


# Global singleton instance
_yaml_loader: Optional[YAMLLoader] = None


def get_yaml_loader() -> YAMLLoader:
    """Get singleton instance of YAMLLoader."""
    global _yaml_loader
    if _yaml_loader is None:
        _yaml_loader = YAMLLoader()
    return _yaml_loader


# Convenience functions for common operations
def load_yaml(file_path: str | Path, **kwargs) -> Dict[str, Any]:
    """Convenience function to load YAML file."""
    return get_yaml_loader().load_yaml(file_path, **kwargs)


def save_yaml(file_path: str | Path, data: Dict[str, Any], **kwargs) -> bool:
    """Convenience function to save YAML file."""
    return get_yaml_loader().save_yaml(file_path, data, **kwargs)


def invalidate_yaml_cache(file_path: Optional[str | Path] = None):
    """Convenience function to invalidate YAML cache."""
    get_yaml_loader().invalidate_cache(file_path)


__all__ = [
    'YAMLLoader',
    'get_yaml_loader',
    'load_yaml',
    'save_yaml',
    'invalidate_yaml_cache'
]
