"""CLI interfaces for git-smart-squash."""

from .main import main
from .zero_friction import ZeroFrictionEngine, ZeroFrictionCLI, main as zero_friction_main

__all__ = [
    'main',
    'ZeroFrictionEngine',
    'ZeroFrictionCLI',
    'zero_friction_main'
]