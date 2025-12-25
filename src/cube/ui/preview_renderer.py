"""
Preview renderer for displaying scaled visualization preview in menu.
"""
import numpy as np
from typing import Optional


def render_preview(
    layer_height: int,
    layer_width: int,
    preview_source: Optional[np.ndarray],
    max_size_ratio: float = 0.25,
) -> np.ndarray:
    """
    Create a preview layer with a scaled preview of the visualization in the bottom-right corner.
    
    Args:
        layer_height: Height of the output layer
        layer_width: Width of the output layer
        preview_source: Source framebuffer to preview (from visualization)
        max_size_ratio: Maximum size as ratio of screen (default 0.25 = 25%)
    
    Returns:
        Preview layer (same size as menu layer) with preview in bottom-right, black elsewhere
    """
    # Create empty layer (black = transparent in compositing)
    preview_layer = np.zeros((layer_height, layer_width, 3), dtype=np.uint8)
    
    # Calculate preview size (max 25% of screen, maintain aspect ratio)
    # Use default dimensions if no source provided
    if preview_source is None:
        # Show placeholder border when no visualization is running
        default_width = 256
        default_height = 128
        preview_width = default_width
        preview_height = default_height
    else:
        # Check if preview_source has any content (not all zeros)
        if not np.any(preview_source):
            # Show placeholder border when source is empty
            default_width = 256
            default_height = 128
            preview_width = default_width
            preview_height = default_height
        else:
            preview_height, preview_width = preview_source.shape[:2]
    
    # Calculate preview size (max 25% of screen, maintain aspect ratio)
    max_preview_width = int(layer_width * max_size_ratio)
    max_preview_height = int(layer_height * max_size_ratio)
    
    # Calculate scale to fit within max size while maintaining aspect ratio
    scale_w = max_preview_width / preview_width
    scale_h = max_preview_height / preview_height
    scale = min(scale_w, scale_h, 1.0)  # Don't scale up, only down
    
    scaled_width = int(preview_width * scale)
    scaled_height = int(preview_height * scale)
    
    # Position in bottom-right corner with small margin
    margin = 4
    x_pos = layer_width - scaled_width - margin
    y_pos = layer_height - scaled_height - margin
    
    # Ensure preview fits within layer bounds
    if x_pos < 0 or y_pos < 0:
        return preview_layer
    
    # Scale the preview source using simple downsampling (if source exists)
    if preview_source is not None and np.any(preview_source):
        if scale < 1.0:
            # Use numpy linspace for nearest-neighbor resize
            y_indices = np.linspace(0, preview_height - 1, scaled_height).astype(int)
            x_indices = np.linspace(0, preview_width - 1, scaled_width).astype(int)
            scaled_preview = preview_source[np.ix_(y_indices, x_indices)]
        else:
            # No scaling needed, just crop to size
            scaled_preview = preview_source[:scaled_height, :scaled_width, :]
    else:
        # Create placeholder (black rectangle) when no source
        scaled_preview = np.zeros((scaled_height, scaled_width, 3), dtype=np.uint8)
    
    # Draw border around preview (2px border)
    border_color = (100, 100, 100)
    border_width = 2
    
    # Calculate border bounds
    border_x1 = x_pos
    border_y1 = y_pos
    border_x2 = x_pos + scaled_width + border_width * 2
    border_y2 = y_pos + scaled_height + border_width * 2
    
    # Ensure border fits within layer bounds
    border_x2 = min(border_x2, layer_width)
    border_y2 = min(border_y2, layer_height)
    
    # Draw border (outline)
    # Top border
    if border_y1 < layer_height:
        preview_layer[border_y1:border_y1 + border_width, border_x1:border_x2] = border_color
    # Bottom border
    if border_y2 - border_width >= 0:
        preview_layer[border_y2 - border_width:border_y2, border_x1:border_x2] = border_color
    # Left border
    if border_x1 < layer_width:
        preview_layer[border_y1:border_y2, border_x1:border_x1 + border_width] = border_color
    # Right border
    if border_x2 - border_width >= 0:
        preview_layer[border_y1:border_y2, border_x2 - border_width:border_x2] = border_color
    
    # Copy scaled preview into preview layer (inside border)
    preview_x = x_pos + border_width
    preview_y = y_pos + border_width
    if preview_x + scaled_preview.shape[1] <= layer_width and preview_y + scaled_preview.shape[0] <= layer_height:
        preview_layer[preview_y:preview_y + scaled_preview.shape[0],
                      preview_x:preview_x + scaled_preview.shape[1]] = scaled_preview
    
    return preview_layer

