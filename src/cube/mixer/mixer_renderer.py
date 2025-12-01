"""
Mixer Renderer - composites A/B channels based on crossfader.
"""

import numpy as np
from .mixer_state import MixerState


class MixerRenderer:
    """
    Stateless mixer renderer.

    Takes MixerState and produces composited framebuffer.
    """

    def __init__(self, width: int, height: int):
        """
        Initialize mixer renderer.

        Args:
            width: Render width
            height: Render height
        """
        self.width = width
        self.height = height

    def render(self, state: MixerState) -> np.ndarray:
        """
        Render mixer output.

        Renders the active pair of channels and crossfades between them.

        Args:
            state: MixerState containing channels and crossfader

        Returns:
            Composited framebuffer (height, width, 3) uint8
        """
        # Get the active pair
        left_channel, right_channel = state.get_active_pair()

        # Get left channel output
        left_pixels = None
        if left_channel.has_shader():
            left_channel.render()
            left_pixels = left_channel.read_pixels()

        # Get right channel output
        right_pixels = None
        if right_channel.has_shader():
            right_channel.render()
            right_pixels = right_channel.read_pixels()

        # Crossfade between channels
        return self._crossfade(left_pixels, right_pixels, state.crossfader)

    def _crossfade(self, pixels_a: np.ndarray, pixels_b: np.ndarray, crossfader: float) -> np.ndarray:
        """
        Crossfade between two framebuffers.

        Args:
            pixels_a: Channel A pixels (or None)
            pixels_b: Channel B pixels (or None)
            crossfader: 0.0 = full A, 1.0 = full B

        Returns:
            Composited framebuffer
        """
        # If neither channel has content, return black
        if pixels_a is None and pixels_b is None:
            return np.zeros((self.height, self.width, 3), dtype=np.uint8)

        # If only A has content
        if pixels_a is not None and pixels_b is None:
            # Fade out A as crossfader increases
            alpha = 1.0 - crossfader
            result = (pixels_a.astype(np.float32) * alpha).astype(np.uint8)
            return result

        # If only B has content
        if pixels_a is None and pixels_b is not None:
            # Fade in B as crossfader increases
            alpha = crossfader
            result = (pixels_b.astype(np.float32) * alpha).astype(np.uint8)
            return result

        # Both channels have content - crossfade
        alpha_a = 1.0 - crossfader
        alpha_b = crossfader

        # Linear crossfade
        result = (
            pixels_a.astype(np.float32) * alpha_a +
            pixels_b.astype(np.float32) * alpha_b
        ).astype(np.uint8)

        return result
