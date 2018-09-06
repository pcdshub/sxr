import uuid
import logging
import time
import datetime

import pandas as pd
from bluesky.plan_stubs import mv, one_nd_step, abs_set, wait as plan_wait
from bluesky.plans import scan, inner_product_scan, rel_scan
from bluesky.preprocessors import stub_wrapper

logger = logging.getLogger(__name__)

def rel_smooth_sweep_test(mot_x, target):
    """
    rel_smooth_sweep_test is a test method.
    """
    logging.info('driving motor to {:0.4f}'.format(target))
    yield from mv(mot_x, target)
    logging.info('motor arrived at {:0.4f}'.format(target))


def xy_sequencer(start_x, start_y, stroke_height, stroke_spacing, n_strokes,
            both_directions=True):
    """
    xy_sequencer generates a list of tuples specifying the x,y coordinates of
    the path that the LU20 sampler must follow. 

    This path has two forms. The first form, where both_directions=True is a
    sideways "S" shape in which the sample moves in vertical strokes and at the
    end of each stroke, increments in the horizontal axes. 

    The second form, where both_directions=False looks like a comb. In this
    form, the sample moves vertically (following the magnitude and direction of
    stroke height) first. It then reverses this motion, returning to the
    original height BEFORE incrementing horizontally and beginning the next
    stroke.

    The last coordinate in the sequence guarantees that the sample returns to
    its original y axis position, with its x axis prepped for the next vertical
    stroke.

    Parameters
    ----------
    start_x : float
        Initial X coordinate of the motion. The first stroke will begin
        immediately from this point.

    start_y : float
        Initial Y coordinate of the motion. The first stroke will begin
        immediately from this point.

    stroke_height : float
        Set the distance of the total y-axis stroke.

    stroke_spacing : float
        Set the horicontal (x-axis) distance between vertical strokes.

    n_strokes : float
        Number of vertical strokes to complete.

    both_directions : bool, optional
        Defaults to True. If this is True, follow the "S" shaped motion path.
        Otherwise follow the comb shaped motion path. 
    
    Returns
    -------
    list of tuples
        This is the list of (x,y) coordinates defining the path for the sample.
        The 0th indexed coordinate is the initial position.

    """
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
    """
    rel_smooth_sweep

    This bluesky plan moves a 2-axis actuator across multiple traversals of a
    sample. The plan traverses the entirety of the stroke_height (y-axis) and
    after each traversal, steps in the x-axis by the stroke_spacing.It may be
    configured to scan in only a single direction and shutter the beam for the
    opposite direction. This removes the shutter at the beginning of the plan
    and reinserts it at the end. At the end of the plan, the sample is moved to
    its original y-axis position but with an x-axis posiiton ready for the next
    run. For more details about the path, see the xy_sequencer, the method
    responsible for generating the path. 

    Parameters
    ---------
    mot_x : pcdsdevices.EpicsMotor.IMS
        The x axis sample mover's ophyd instance.

    mot_y : pcdsdevices.EpcisMotor.IMS
        The y axis sample mover's ophyd instance.
    
    shutter : experiments.lu20.devices.BeamShutter
        The beam shutter's ophyd instance.

    stroke_height : float
        Vertical distance (y-axs) of each stroke.

    stroke_spacing : float
        Horizontal distance between individual strokes.
    
    n_strokes : int
        Number of strokes to complete.

    both_directions : bool, optional
        Defaults to True. If this value is true the beam will be scanned across
        the sample while moving in both vertical directions. If false, the beam
        is only scanned in a single direction. See xy_sequencer for details
        about the motion. 
    """
    
    initiate_str = """Initiating rel_smooth_sweep:
    mot_x = {mot_x}
    mot_y = {mot_y}
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

    logging.info('Start time: {}'.format(datetime.datetime.now().strftime(
        "%Y/%m/%d %H:%M:%S"
    )))
 
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
    logging.debug('Target coordinate list: {}'.format(coord_list))

    logging.debug('Removing shutter')
    shutter.remove()
    
    for line_no, line in enumerate(coord_list):
        if not both_directions:
            if line_no % 3 == 0:
                logging.debug('Removing shutter')
                shutter.remove()
            if line_no % 3 == 2:
                logging.debug('Inserting shutter')
                shutter.insert()
        
        logging.debug('driving motors to ({:0.4f},{:0.4f})'.format(
            line[0],line[1]
        ))
        yield from mv(mot_x, line[0], mot_y, line[1])
        logging.debug('motors arrived at ({:0.4f},{:0.4f})'.format(
            mot_x.user_readback.value,
            mot_y.user_readback.value
        ))

    logging.debug('Inserting shutter')
    shutter.insert()

    end_x = mot_x.get().user_readback
    end_y = mot_y.get().user_readback
    logging.info('Motors ending at: ({x:0.4f},{y:0.4f})'.format(
        x=end_x,
        y=end_y
    ))
    logging.info('End time: {}'.format(datetime.datetime.now().strftime(
        "%Y/%m/%d %H:%M:%S"
    )))
