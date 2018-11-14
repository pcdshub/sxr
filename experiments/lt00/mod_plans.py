import logging
import time
import datetime

import numpy as np

from experiments.lu20.plans import xy_sequencer

def xyz_sequencer(origin, short_edge_end, long_edge_end, n_strokes):
    """
    Parameters
    ----------

    origin : tuple or np.array
        3-length (x,y,z) iteralbe specifying starting point of the scan.
    
    short_edge_end : tuple or np.array
        3-length (x,y,z) iteralbe specifying the end location of the short
        steps.
    
    long_edge_end : tuple or np.array
        3-length (x,y,z) iteralbe specifying the end location of the long
        sweep.
    
    n_strokes: int
        number of individual strokes to accomplish. Even numbers are STRONGLY
        encouraged.

    Returns
    -------
    np.array
        This two dimensional numpy array lists out the points to visit. 

    """
    
    if type(origin) is not np.ndarray:
        _origin = np.array(origin)
    else:
        _origin = origin
    
    if type(short_edge_end) is not np.ndarray:
        _short_edge_end = np.array(short_edge_end)
    else:
        _short_edge_end = _short_edge_end
    
    if type(long_edge_end) is not np.ndarray:
        _long_edge_end = np.array(long_edge_end)
    else:
        _long_edge_end = long_edge_end

    delta_short = _short_edge_end - _origin # x_end minus origin
    delta_long = _long_edge_end - _origin # y_end minus origin

    print(delta_short)
    print(delta_long)
    
    # Use a dimensionless unitvectors for ez-maths
    xy_unit_sequence = xy_sequencer(
        start_x = 0,
        start_y = 0,
        stroke_height = 1,
        stroke_spacing = 1/n_strokes,
        n_strokes = n_strokes,
        both_directions = True,
    )

    # Don't reset the sample at the end with a return along the long stroke
    # axis if the last sweep (an odd number of sweeps) leaves the laser on the
    # opposite side of the sample
    if n_strokes % 2 != 0:
        xy_unit_sequence = xy_unit_sequence[:-1]
    
    # Convert list of unit vectors into matrix of vectors for the transform
    xy_unit_matrix = np.array(xy_unit_sequence)
    xy_unit_matrix = xy_unit_matrix.T

    # Create the matrix for transforming unit vectors into relevnt space
    conversion_matrix = np.array([delta_short,delta_long]).T    
    
    # Convert from unit to actual vectors
    result_points = np.dot(conversion_matrix, xy_unit_matrix)
    result_points = result_points.T

    return result_points

def xyz_velocities(origin, short_edge_end, long_edge_end, scalar=1.0):
    """
    Parameters
    ----------

    origin : tuple or np.array
        3-length (x,y,z) iteralbe specifying starting point of the scan.
    
    short_edge_end : tuple or np.array
        3-length (x,y,z) iteralbe specifying the end location of the short
        steps.
    
    long_edge_end : tuple or np.array
        3-length (x,y,z) iteralbe specifying the end location of the long
        sweep.
    
    scalar: float
        Scale the velocities by this factor. Defaults to 1.0. E.g. Using the
        sae vectors with a 2.0 instead of 1.0 doubles all velocities. 
        
    Returns
    -------
    np.array, np.array
        This two dimensional numpy array lists out the points to visit. 

    """
    if type(origin) is not np.ndarray:
        _origin = np.array(origin)
    else:
        _origin = origin
    
    if type(short_edge_end) is not np.ndarray:
        _short_edge_end = np.array(short_edge_end)
    else:
        _short_edge_end = _short_edge_end
    
    if type(long_edge_end) is not np.ndarray:
        _long_edge_end = np.array(long_edge_end)
    else:
        _long_edge_end = long_edge_end

    short_vector = (_short_edge_end - _origin) * scalar
    long_vector = (_long_edge_end - _origin) * scalar

    return short_vector, long_vector


def rel_smooth_sweep(mot_x, mot_y, mot_z, shutter, short_edge_end,
        long_edge_end, n_strokes, scalar=1.0):
    """
    rel_smooth_sweep

    This bluesky plan moves a 3-axis actuator across multiple traversals of a
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
    
    mot_z : pcdsdevices.EpcisMotor.IMS
        The y axis sample mover's ophyd instance.
    
    shutter : experiments.lu20.devices.BeamShutter
        The beam shutter's ophyd instance.
    
    short_edge_end : tuple or np.array
        3-length (x,y,z) iteralbe specifying the end location of the short
        steps.
    
    long_edge_end : tuple or np.array
        3-length (x,y,z) iteralbe specifying the end location of the long
        sweep.
    
    n_strokes : int
        Number of strokes to complete.

    scalar : float
        Scale the motor velocities by this factor. Defaults to 1.0.

    """

    # Value for base velocity
    min_base_velocity= .0001
    # Limits on the velocity value (it must be within the max and base)
    min_velocity_val = .0002
    max_velocity_val = 14.9998
    # Value for Maximum velocity
    max_velocity = 15
    both_directions = True
    initiate_str = """Initiating rel_smooth_sweep:
    mot_x = {mot_x}
    mot_y = {mot_y}
    mot_z = {mot_z}
    shutter = {shutter}
    stroke_height = {stroke_height:0.4f}
    stroke_spacing = {stroke_spacing:0.4f}
    n_strokes = {n_strokes}
    both_directions = {both_directions}
    """
    logging.info(initiate_str.format(
        mot_x=mot_x,
        mot_y=mot_y,
        mot_z=mot_z,
        shutter=shutter,
        stroke_height=stroke_height,
        stroke_spacing=stroke_spacing,
        n_strokes=n_strokes,
        both_directions=both_directions,
    ))

    logging.info('Start time: {}'.format(datetime.datetime.now().strftime(
        "%Y/%m/%d %H:%M:%S"
    )))

    # Generate path
    start_x = mot_x.get().user_readback
    start_y = mot_y.get().user_readback
    start_z = mot_z.get().user_readback
    logging.info('Motors starting at: ({x:0.4f},{y:0.4f},{z:0.4f})'.format(
        x=start_x,
        y=start_y,
        z=start_z,
    ))
    # Set velocity limits (This must enclose normal motor velocity, exclusive)
    mot_x.velocity_base = min_base_velocity
    mot_y.velocity_base = min_base_velocity
    mot_z.velocity_base = min_base_velocity
    mot_x.velocity_max = max_velocity
    mot_y.velocity_max = max_velocity
    mot_z.velocity_max = max_velocity
    # Set velocity and apply limits
    short_velocity, long_velocity = xyz_velocities(
        (start_x,start_y,start_z),
        short_edge_end,
        long_edge_end,
        scalar
    )
    short_velocity = np.clip(
        short_velocity, min_velocity_val, max_velocity_val)
    long_velocity = np.clip(
        long_velocity, min_velocity_val, max_velocity_val)



    coord_list = xyz_sequencer(
        origin=(start_x, start_y, start_z),
        short_edge_end=short_edge_end,
        long_edge_end=long_edge_end,
        n_strokes=n_strokes, 
        both_directions=both_directions,
    )
    logging.debug('Target coordinate list: {}'.format(coord_list))

    # Remove shutter
    # logging.debug('Removing shutter')
    # shutter.remove()

    
    # Make the individual moves -- continue working here
    for line_no, line in enumerate(coord_list):
        '''
        if not both_directions:
            if line_no % 3 == 0:
                logging.debug('Removing shutter')
                shutter.remove()
            if line_no % 3 == 2:
                logging.debug('Inserting shutter')
                shutter.insert()
        '''

        if both_directions:
            if line_no % 2 == 0:
                mot_x.velocity = long_velocity[0]
                mot_y.velocity = long_velocity[1]
                mot_z.velocity = long_velocity[2] 
            else:
                mot_x.velocity = short_velocity[0]
                mot_y.velocity = short_velocity[1]
                mot_z.velocity = short_velocity[2] 
                
        
        logging.debug('driving motors to ({:0.4f},{:0.4f})'.format(
            line[0],line[1],line[2],
        ))

        yield from mv(mot_x, line[0], mot_y, line[1], mot_z, line[2])

        logging.debug('motors arrived at ({:0.4f},{:0.4f},{:0.4f)'.format(
            mot_x.user_readback.value,
            mot_y.user_readback.value,
            mot_z.user_readback.value,
        ))

    # Insert shutter - MAYBE DO EARLY FOR ODD N_STROKES?
    # logging.debug('Inserting shutter')
    # shutter.insert()
    

    end_x = mot_x.get().user_readback
    end_y = mot_y.get().user_readback
    end_z = mot_z.get().user_readback
    logging.info('Motors ending at: ({x:0.4f},{y:0.4f},{z:0.4f})'.format(
        x=end_x,
        y=end_y,
        z=end_z,
    ))
    logging.info('End time: {}'.format(datetime.datetime.now().strftime(
        "%Y/%m/%d %H:%M:%S"
    )))
