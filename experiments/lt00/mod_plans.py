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
    
    xy_unit_matrix = np.array(xy_unit_sequence)
    
    
    print("**************************")
    #for row in xy_matrix:
    #    print(row)
    xy_unit_matrix = xy_unit_matrix.T
    print(xy_unit_matrix)
    
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~")
    #print(np.array([delta_short,delta_long]))    
    conversion_matrix = np.array([delta_short,delta_long]).T    
    print(conversion_matrix) 


    print("##########################")
    result_points = np.dot(conversion_matrix, xy_unit_matrix)
    result_points = result_points.T
    return result_points

