import pytest


import numpy as np
from bluesky import RunEngine
from bluesky.preprocessors import run_wrapper
from ophyd.sim import SynAxis

#from experiments.lu20.plans import rel_smooth_sweep, xy_sequencer
from experiments.lt00.mod_plans import xyz_sequencer, xyz_velocities
from experiments.lt00.mod_macros import macro_VT50_smooth_sweep
def test_xyz_sequencer():
    # sequence of tuples
    m = xyz_sequencer(
        (0, 0, 1),
        (4.0, .4, 5.0),
        (.6, 3.0, 1.75),
        4,
    )

    target_result = [
        (0.0, 0.0, 1.0),
        (0.6, 3.0, 1.75),
        (1.6, 3.1, 2.75),
        (1.0, 0.1, 2.0),
        (2.0, 0.2, 3.0),
        (2.6, 3.2, 3.75),
        (3.6, 3.3, 4.75),
        (3.0, 0.3, 4.0),
        (4.0, 0.4, 5.0),
        (4.0, 0.4, 5.0),
    ]

    assert np.all((m - target_result) < .0001)

def test_xyz_velocities():
    result_short, result_long = xyz_velocities(
        (0, 0, 1),
        (4.0, .4, 5.0),
        (.6, 3.0, 1.75),
        1
    )

    target_result_short = np.array([4.0,.4,4.0])
    target_result_long = np.array([.6,3.0,.75])

    assert np.all((result_short - target_result_short) < .0001)
    assert np.all((result_long - target_result_long) < .0001)
    
