"""
Piomatter display backend for actual LED cube hardware.
"""

from .display_backend import DisplayBackend


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

    def show(self):
        """Display framebuffer via piomatter."""
        self.matrix.show()

    def handle_events(self) -> dict:
        """
        Handle input events via GPIO buttons (if available).
        For now, returns no events - keyboard input would need GPIO button setup.
        """
        # TODO: Implement GPIO button handling for physical cube
        # This would read button states and map them to key events
        return {'quit': False, 'key': None, 'keys': []}

    def cleanup(self):
        """Clean up piomatter resources."""
        # Piomatter handles cleanup automatically
        pass
