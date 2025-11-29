#!/usr/bin/python3
# SPDX-FileCopyrightText: 2025 Tim Cocks for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""
Display a simple test pattern of 3 shapes on three 64x64 matrix panels
using Active3 compatible connections.

Run like this:

$ python triple_matrix_active3_simpletest.py

"""

import numpy as np
from PIL import Image, ImageDraw

import adafruit_blinka_raspberry_pi5_piomatter as piomatter

width = 64
height = 64

canvas = Image.new('RGB', (width, height), (0, 0, 0))
draw = ImageDraw.Draw(canvas)

geometry = piomatter.Geometry(width=width, height=height, n_addr_lines=5,
                                                     rotation=piomatter.Orientation.Normal)
framebuffer = np.asarray(canvas) + 0  # Make a mutable copy
matrix = piomatter.PioMatter(colorspace=piomatter.Colorspace.RGB888Packed,
                             pinout=piomatter.Pinout.AdafruitMatrixHat,
                             framebuffer=framebuffer,
                             geometry=geometry)


draw.rectangle((8, 8, width-8, height-8), fill=0x008800)
draw.circle((32, 32), 10, fill=0x880000)
draw.polygon([(32, 45), (42, 55), (22, 55)], fill=0x000088)

framebuffer[:] = np.asarray(canvas)
matrix.show()

input("Press enter to exit")
