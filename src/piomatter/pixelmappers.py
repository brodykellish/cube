"""Functions to define the layout of complex setups, particularly multi-connector matrices"""

def simple_multilane_mapper(width, height, n_addr_lines, n_lanes):
    """A simple mapper for 4+ pixel lanes

    A framebuffer (width × height) is mapped onto a matrix where the lanes are stacked
    top-to-bottom. Panels within a lane may be cascaded left-to-right.

    Rotation is not supported, and neither are more complicated arrangements of panels
    within a single chain (no support for serpentine or stacked panels within a segment)

    .. code-block::

        0 -> [panel] -> [panel]
        1 -> [panel] -> [panel]
        2 -> [panel] -> [panel]
    """

    calc_height = n_lanes << n_addr_lines
    if height != calc_height:
        raise RuntimeError(f"Calculated height {calc_height} does not match requested height {height}")
    n_addr = 1 << n_addr_lines

    m = []
    for addr in range(n_addr):
        for x in range(width):
            for lane in range(n_lanes):
                y = addr + lane * n_addr
                m.append(x + width * y)
    return m
