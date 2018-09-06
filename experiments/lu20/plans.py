import uuid
import logging
import time

import pandas as pd
from bluesky.plan_stubs import mv, one_nd_step, abs_set, wait as plan_wait
from bluesky.plans import scan, inner_product_scan, rel_scan
from bluesky.preprocessors import stub_wrapper

logger = logging.getLogger(__name__)

def rel_smooth_sweep_test(mot_x, target):
    yield from mv(mot_x, target)


def xy_sequencer(start_x, start_y,stroke_height, stroke_spacing, n_strokes,
            both_directions=True):

    coord_list = []
    coord_list.append((start_x,start_y))

    direction = 1
    for x in range(n_strokes):
        # vertical stroke
        new_x = coord_list[-1][0]
        new_y = coord_list[-1][1] + (direction * stroke_height)
        coord_list.append((new_x,new_y))
        # flip direction for the next stroke if both directions are used
        if both_directions:
            direction *= -1

        # second vertical stroke if only one direction is allowed
        if not both_directions:
            new_x = coord_list[-1][0]
            new_y = coord_list[-1][1] - (direction * stroke_height)
            coord_list.append((new_x,new_y))

        # horizontal stroke
        new_x = coord_list[-1][0] + stroke_spacing
        new_y = coord_list[-1][1]
        coord_list.append((new_x,new_y))
        
    # reset move for next set 
    new_x = coord_list[0][0] + n_strokes * stroke_spacing
    new_y = coord_list[0][1]
    coord_list.append((new_x,new_y))
    
    return coord_list


def rel_smooth_sweep(mot_x, mot_y, shutter, stroke_height, stroke_spacing,
            n_strokes, both_directions=True):
    
    start_x = mot_x.get().user_readback
    start_y = mot_y.get().user_readback

    coord_list = xy_sequencer(
        start_x, 
        start_y,
        stroke_height,
        stroke_spacing,
        n_strokes, 
        both_directions
    )

    for line_no, line in enumerate(coord_list):
        if not both_directions:
            if line_no % 3 == 0:
                shutter.remove()
            if line_no % 3 == 2:
                shutter.insert()
        
        yield from mv(mot_x, line[0], mot_y, line[1])

