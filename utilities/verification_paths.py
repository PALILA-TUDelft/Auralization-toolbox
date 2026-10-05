"""Single source of truth for where per-step verification dumps are written.

By default dumps go to ``verification/<step>/`` (unchanged legacy layout).
Call ``set_verification_root`` once (main.py does this) to redirect every dump
to e.g. ``verification/scenarios/<scenario>/<step>/`` so that scenarios do not
overwrite each other.
"""
from pathlib import Path

DEFAULT_ROOT = Path("verification")
_root = DEFAULT_ROOT


def set_verification_root(root):
    """Set the folder under which all ``<step>/`` sub-folders are created."""
    global _root
    _root = Path(root) if root is not None else DEFAULT_ROOT


def get_verification_root():
    return _root


def verif_path(step):
    """Return ``<root>/<step>`` as a Path, creating it if needed."""
    p = _root / step
    p.mkdir(parents=True, exist_ok=True)
    return p
