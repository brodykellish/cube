#!/usr/bin/python3
# SPDX-FileCopyrightText: 2025 Tim Cocks for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""
Display a simple test pattern of 3 shapes on a single 64x32 matrix panel.

Run like this:

$ python simpletest.py

"""

import numpy as np
from PIL import Image, ImageDraw

import adafruit_blinka_raspberry_pi5_piomatter as piomatter

width = 64
height = 64

x = 0
y = 0
size = 10

geometry = piomatter.Geometry(width=width, height=height, n_addr_lines=5,
                                                     rotation=piomatter.Orientation.Normal)

canvas = Image.new('RGB', (width, height), (0, 0, 0))
draw = ImageDraw.Draw(canvas)

framebuffer = np.asarray(canvas) + 0  # Make a mutable copy
matrix = piomatter.PioMatter(colorspace=piomatter.Colorspace.RGB888Packed,
                             pinout=piomatter.Pinout.AdafruitMatrixHat,
                             framebuffer=framebuffer,
                             geometry=geometry)

draw.rectangle((x, y, x+size, y+size), fill=0x008800)
draw.circle((18, 6), 4, fill=0x880000)
draw.polygon([(28, 2), (32, 10), (24, 10)], fill=0x000088)

framebuffer[:] = np.asarray(canvas)
matrix.show()

input("Press enter to exit")
