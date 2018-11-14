import pytest


import numpy as np
from bluesky import RunEngine
from bluesky.preprocessors import run_wrapper
from ophyd.sim import SynAxis

#from experiments.lu20.plans import rel_smooth_sweep, xy_sequencer
from experiments.lt00.mod_plans import xyz_sequencer

def test_bad():
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


    

"""
def test_xy_sequencer():
    result = xy_sequencer(0, 0, 3, 1, 4, True)
    assert result == [
        (0,0),
        (0,3),
        (1,3),
        (1,0),
        (2,0),
        (2,3),
        (3,3),
        (3,0),
        (4,0),
        (4,0),
    ]
    
    result = xy_sequencer(0, 0, 3, 1, 4, False)
    assert result == [
        (0,0),
        (0,3),
        (0,0),
        (1,0),
        (1,3),
        (1,0),
        (2,0),
        (2,3),
        (2,0),
        (3,0),
        (3,3),
        (3,0),
        (4,0),
        (4,0),
    ]


def test_rel_smooth_sweep():
    RE = RunEngine({})

"""
