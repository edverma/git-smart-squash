"""Git Smart Squash - Automatically reorganize messy git commit histories."""

import os

# Read version from VERSION file
_version_file = os.path.join(os.path.dirname(__file__), 'VERSION')
with open(_version_file, 'r') as f:
    __version__ = f.read().strip()