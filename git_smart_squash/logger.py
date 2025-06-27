"""Logging configuration for git-smart-squash."""

import logging
import sys
from enum import Enum
from typing import Optional
from rich.console import Console
from rich.logging import RichHandler


class LogLevel(Enum):
    """Log levels for the application."""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


class GitSmartSquashLogger:
    """Custom logger for git-smart-squash with rich console integration."""
    
    _instance: Optional['GitSmartSquashLogger'] = None
    _console: Optional[Console] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self._setup_logger()
    
    def _setup_logger(self):
        """Set up the logger with rich handler."""
        self.logger = logging.getLogger('git_smart_squash')
        self.logger.setLevel(logging.INFO)  # Default to INFO level
        
        # Remove any existing handlers
        self.logger.handlers.clear()
        
        # Create rich handler
        handler = RichHandler(
            console=self._console or Console(stderr=True),
            show_time=False,
            show_path=False,
            markup=True,
            rich_tracebacks=True,
            tracebacks_show_locals=False
        )
        
        # Set format
        handler.setFormatter(logging.Formatter('%(message)s'))
        self.logger.addHandler(handler)
    
    def set_console(self, console: Console):
        """Set the console instance to use for logging."""
        self._console = console
        self._setup_logger()  # Reconfigure with new console
    
    def set_level(self, level: LogLevel):
        """Set the logging level."""
        self.logger.setLevel(level.value)
    
    def debug(self, message: str, *args, **kwargs):
        """Log a debug message."""
        self.logger.debug(f"[dim]{message}[/dim]", *args, **kwargs)
    
    def info(self, message: str, *args, **kwargs):
        """Log an info message."""
        self.logger.info(message, *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs):
        """Log a warning message."""
        self.logger.warning(f"[yellow]{message}[/yellow]", *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs):
        """Log an error message."""
        self.logger.error(f"[red]{message}[/red]", *args, **kwargs)
    
    def critical(self, message: str, *args, **kwargs):
        """Log a critical message."""
        self.logger.critical(f"[bold red]{message}[/bold red]", *args, **kwargs)
    
    def hunk_debug(self, message: str, *args, **kwargs):
        """Log detailed hunk application debug info."""
        self.logger.debug(f"[cyan]HUNK: {message}[/cyan]", *args, **kwargs)
    
    def patch_debug(self, patch_content: str):
        """Log patch content for debugging."""
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug("[dim]===== PATCH CONTENT =====[/dim]")
            for line in patch_content.split('\n')[:50]:  # Limit to first 50 lines
                self.logger.debug(f"[dim]{line}[/dim]")
            if len(patch_content.split('\n')) > 50:
                self.logger.debug(f"[dim]... ({len(patch_content.split('\n')) - 50} more lines)[/dim]")
            self.logger.debug("[dim]========================[/dim]")


# Global logger instance
logger = GitSmartSquashLogger()


def get_logger() -> GitSmartSquashLogger:
    """Get the global logger instance."""
    return logger