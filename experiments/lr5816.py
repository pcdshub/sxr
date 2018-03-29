import time
import logging

import numpy as np
from ophyd.sim import SynAxis

from sxr.plans import mcgrain_scan as _mcgrain_scan
from sxr.devices import ErrorIMS, Sequencer, McgrainPalette

logger = logging.getLogger(__name__)
        

class User(object):
    """User class for the LR58 Mcgrain experiment."""
    # Devices
    mono = ErrorIMS("SXR:MON:MMS:06", name="Monochrometer")
    sequencer = Sequencer("ECS:SYS0:2", name="sequencer")
    palette = McgrainPalette(name="Mcgrain Palette")
    syn_motor_1 = SynAxis(name="Syn Motor 1")

    def __init__(self, *args, **kwargs):
        self.palette.accept_calibration(
            np.array([-9.54519187, -2.99960937, -2.       ]), 
            np.array([ 12.57935063,  -2.89960937,  -2.    ]), 
            np.array([ -9.24544125, -86.26064453,  -2.    ]))

    def mcgrain_scan(self, mono_start, mono_stop, mono_steps, palette_steps, 
                     *args, **kwargs):
        yield from _mcgrain_scan(
            self.mono, self.palette, self.sequencer, 
            mono_start, mono_stop, mono_steps, 
            palette_steps, 
            *args, **kwargs)

