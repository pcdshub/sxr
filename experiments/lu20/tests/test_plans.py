import pytest

from bluesky import RunEngine
from bluesky.preprocessors import run_wrapper
from ophyd.sim import SynAxis

from experiments.lu20.plans import rel_smooth_sweep, xy_sequencer

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
