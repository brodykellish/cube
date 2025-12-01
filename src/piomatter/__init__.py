"""
HUB75 matrix driver for Raspberry Pi 5 using PIO
------------------------------------------------

.. currentmodule:: piomatter

.. autosummary::
    :toctree: _generate
    :recursive:
    :class: Orientation Pinout Colorspace Geometry PioMatter

    Orientation
    Pinout
    Colorspace
    Geometry
    PioMatter
"""

# Try to import C extension (only available on Raspberry Pi)
try:
    from ._piomatter import (
        Colorspace,
        Geometry,
        Orientation,
        Pinout,
        PioMatter,
    )
    _PIOMATTER_AVAILABLE = True
except ImportError as e:
    # Not on Raspberry Pi, C extension not built
    _PIOMATTER_AVAILABLE = False
    Colorspace = None
    Geometry = None
    Orientation = None
    Pinout = None
    PioMatter = None
    print(f"WARNING: piomatter C extension not available: {e}")

__all__ = [
    'Colorspace',
    'Geometry',
    'Orientation',
    'Pinout',
    'PioMatter',
    '_PIOMATTER_AVAILABLE',
]
