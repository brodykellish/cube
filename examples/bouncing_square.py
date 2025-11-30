import piomatter as piomatter
import PIL.Image as Image
import PIL.ImageDraw as ImageDraw
import numpy as np
import pathlib 
import time

width = 64
height = 64
square_size = 10

geometry = piomatter.Geometry(width=width, height=height, n_addr_lines=5,
                              rotation=piomatter.Orientation.Normal)

canvas = Image.new('RGB', (width, height), (0, 0, 0))
draw = ImageDraw.Draw(canvas)

framebuffer = np.asarray(canvas) + 0  # Make a mutable copy
matrix = piomatter.PioMatter(colorspace=piomatter.Colorspace.RGB888Packed,
                             pinout=piomatter.Pinout.AdafruitMatrixHat,
                             framebuffer=framebuffer,
                             geometry=geometry)

# Starting position and velocity
x = 0
y = 0
vx = 1  # velocity in x direction
vy = 1  # velocity in y direction

# Square color (green)
square_color = 0x00FF00

try:
    while True:
        # Clear canvas
        draw.rectangle((0, 0, width, height), fill=0x000000)

        # Draw square at current position
        draw.rectangle((x, y, x + square_size, y + square_size), fill=square_color)

        # Update display
        framebuffer[:] = np.asarray(canvas)
        matrix.show()

        # Update position
        x += vx
        y += vy

        # Bounce off walls
        if x <= 0 or x >= width - square_size:
            vx = -vx
            x = max(0, min(x, width - square_size))  # Clamp to bounds

        if y <= 0 or y >= height - square_size:
            vy = -vy
            y = max(0, min(y, height - square_size))  # Clamp to bounds

        # Small delay to control animation speed
        time.sleep(0.02)

except KeyboardInterrupt:
    print("\nExiting")
