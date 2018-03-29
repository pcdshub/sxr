import time
import logging
from pathlib import Path

import numpy as np

from sxr.plans import mcgrain_scan as _mcgrain_scan
from sxr.devices import ErrorIMS, Sequencer, McgrainPalette
from sxr.exceptions import InputError

logger = logging.getLogger(__name__)
        

class User(object):
    """User class for the LR58 Mcgrain experiment."""
    # Devices
    mono = ErrorIMS("SXR:MON:MMS:06", name="Monochrometer Pitch")
    sequencer = Sequencer("ECS:SYS0:2", name="Event Sequencer")
    palette = McgrainPalette(name="Mcgrain Palette")

    def __init__(self, *args, **kwargs):
        self.palette.accept_calibration(
            np.array([-9.54519187, -86.26064453,  -2.       ]),
            np.array([ -9.24544125, -2.99960937,  -2.    ]),
            np.array([ 12.57935063,  -86.26064453,  -2.    ]))

    def mcgrain_scan(self, mono_start, mono_stop, mono_steps, palette_steps, 
                     df_name=None, *args, **kwargs):
        # Make sure df_name is a string  if it was passed
        if df_name and not isinstance(df_name, str):
            raise InputError('df_name must be a string. Got {0}'.format(
                type(df_name)))

        # Perform the mcgrain scan
        df = yield from _mcgrain_scan(
            self.mono, self.palette, self.sequencer, 
            mono_start, mono_stop, mono_steps, 
            palette_steps, 
            *args, **kwargs)
        logger.info('Scan complete!')
        
        # Save the dataframe
        if df_name:
            df_path = Path(
                '~sxropr/experiments/sxrlr5816/mcgrain_scans') / df_name
            # Make the parent directory if it doesnt exist 
            if not df_path.parent.exists():
                df_path.parent.mkdir()
                df_path.parent.chmod(0o777)

            # Create the directories if they dont exist
            logger.info('Saving scan to "{0}"'.format(str(df_path)))
            df.to_csv(str(df_path))
            # Set permissions to be accessible to everyone
            df_path.chmod(0o777)

