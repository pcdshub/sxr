import numpy as np
from hutch_python.utils import safe_load
from ophyd.sim import SynAxis

from .devices import McgrainPalette, ErrorIMS, Sequencer

# Test axes that may come in handy
with safe_load('Virtual Motors'):
    virtual_motor_1 = SynAxis(name='Virtual Motor 1')
    virtual_motor_2 = SynAxis(name='Virtual Motor 2')
    virtual_motor_3 = SynAxis(name='Virtual Motor 3')

with safe_load('Mcgrain Palette'):
    palette = McgrainPalette(name="Mcgrain Palette")

    palette.accept_calibration(
        np.array([-9.54519187, -2.99960937, -2.       ]), 
        np.array([ 12.57935063,  -2.89960937,  -2.    ]), 
        np.array([ -9.24544125, -86.26064453,  -2.    ]))
