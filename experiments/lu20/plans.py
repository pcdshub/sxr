import uuid
import logging
import time

import pandas as pd
from bluesky.plan_stubs import mv, one_nd_step, abs_set, wait as plan_wait
from bluesky.plans import scan, inner_product_scan, rel_scan
from bluesky.preprocessors import stub_wrapper

logger = logging.getLogger(__name__)

def rel_smooth_sweep_test(mot_x, target):
    logging.info('driving motor to {:0.4f}'.format(target))
    yield from mv(mot_x, target)
    logging.info('motor arrived at {:0.4f}'.format(target))


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
    
    initiate_str = """Initiating rel_smooth_sweep:
    mot_x = {mot_x:0.4f}
    mot_y = {mot_y:0.4f}
    shutter = {shutter}
    stroke_height = {stroke_height:0.4f}
    stroke_spacing = {stroke_spacing:0.4f}
    n_strokes = {n_strokes}
    both_directions = {both_directions}
    """
    logging.info(initiate_str.format(
        mot_x=mot_x,
        mot_y=mot_y,
        shutter=shutter,
        stroke_height=stroke_height,
        stroke_spacing=stroke_spacing,
        n_strokes=n_strokes,
        both_directions=both_directions,
    ))
 
    start_x = mot_x.get().user_readback
    start_y = mot_y.get().user_readback
    logging.info('Motors starting at: ({x:0.4f},{y:0.4f})'.format(
        x=start_x,
        y=start_y
    ))

    coord_list = xy_sequencer(
        start_x, 
        start_y,
        stroke_height,
        stroke_spacing,
        n_strokes, 
        both_directions
    )
    logging.info('Target coordinate list: {}'.format(coord_list))

    for line_no, line in enumerate(coord_list):
        if not both_directions:
            if line_no % 3 == 0:
                logging.info('Removing shutter')
                shutter.remove()
            if line_no % 3 == 2:
                logging.info('Inserting shutter')
                shutter.insert()
        
        logging.info('driving motors to ({:0.4f},{:0.4f})'.format(
            line[0],line[1]
        ))
        yield from mv(mot_x, line[0], mot_y, line[1])
        logging.info('motors arrived at ({:0.4f},{:0.4f})'.format(
            mot_x.user_readback.value,
            mot_y.user_readback.value
        ))

    logging.info('Inserting shutter')
    shutter.insert()
