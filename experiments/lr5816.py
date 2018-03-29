import time
import logging

import numpy as np

from sxr.plans import mcgrain_scan as _mcgrain_scan
from sxr.devices import ErrorIMS, Sequencer, McgrainPalette

logger = logging.getLogger(__name__)
        

class User(object):
    """User class for the LR58 Mcgrain experiment."""
    # Devices
    _mono = ErrorIMS("SXR:MON:MMS:06", name="Monochrometer Pitch")
    _sequencer = Sequencer("ECS:SYS0:2", name="Event Sequencer")
    _palette = McgrainPalette(name="Mcgrain Palette")

    def __init__(self, *args, **kwargs):
        self._palette.accept_calibration(
            np.array([-9.54519187, -2.99960937, -2.       ]), 
            np.array([ 12.57935063,  -2.89960937,  -2.    ]), 
            np.array([ -9.24544125, -86.26064453,  -2.    ]))

    def mcgrain_scan(self, mono_start, mono_stop, mono_steps, palette_steps, 
                     *args, **kwargs):
        yield from _mcgrain_scan(
            self._mono, self._palette, self._sequencer, 
            mono_start, mono_stop, mono_steps, 
            palette_steps, 
            *args, **kwargs)

