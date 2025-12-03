"""
Piomatter display backend for actual LED cube hardware.
"""

import numpy as np
from .display_backend import DisplayBackend
from ..input.ssh_keyboard import SSHKeyboard

class PiomatterBackend(DisplayBackend):
    """Piomatter backend for actual LED cube."""

    def __init__(self, width: int, height: int, **kwargs):
        super().__init__(width, height)

        import piomatter as piomatter

        # Extract piomatter-specific arguments
        pinout_name = kwargs.get('pinout', 'AdafruitMatrixBonnet')
        pinout = getattr(piomatter.Pinout, pinout_name)

        # Create geometry
        geometry = piomatter.Geometry(
            width=width,
            height=height,
            n_planes=kwargs.get('num_planes', 10),
            n_addr_lines=kwargs.get('num_address_lines', 4),
            n_temporal_planes=kwargs.get('num_temporal_planes', 0),
            rotation=piomatter.Orientation.Normal,
            serpentine=kwargs.get('serpentine', True)
        )

        # Create matrix
        self.matrix = piomatter.PioMatter(
            colorspace=piomatter.Colorspace.RGB888Packed,
            pinout=pinout,
            framebuffer=self.framebuffer,
            geometry=geometry
        )

        print(f"Piomatter backend initialized: {width}×{height}")

        # Initialize SSH keyboard for remote control
        # Use longer hold duration for smoother input over SSH (accounts for network latency)
        key_hold_duration = kwargs.get('ssh_key_hold_duration', 0.15)
        self.keyboard = SSHKeyboard(key_hold_duration=key_hold_duration)

    def show_framebuffer(self, framebuffer: np.ndarray):
        """
        Display a complete framebuffer via piomatter.

        Handles slicing and re-indexing for cube panel orientations.
        For now, crops/fits framebuffer to display size.

        Args:
            framebuffer: Complete framebuffer to display (any size)
        """
        fb_height, fb_width = framebuffer.shape[:2]

        # Crop or fit framebuffer to matrix dimensions
        h = min(fb_height, self.height)
        w = min(fb_width, self.width)
        self.framebuffer[:h, :w] = framebuffer[:h, :w]

        # TODO: Add orientation/slicing logic for multi-panel cube layouts
        # This would handle re-indexing framebuffer pixels based on panel orientation

        # Display via piomatter
        self.matrix.show()

    def handle_events(self) -> dict:
        """Handle input events via SSH keyboard."""
        # Poll keyboard for input
        keyboard_state = self.keyboard.poll()

        # Convert KeyboardState to old dict format for backward compatibility
        result = {
            'quit': keyboard_state.quit,
            'key': keyboard_state.key_press,
            'keys': keyboard_state.keys_held
        }

        return result

    def cleanup(self):
        """Clean up piomatter and keyboard resources."""
        self.keyboard.cleanup()
        # Piomatter handles cleanup automatically
