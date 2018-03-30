import logging
import time
from pathlib import Path

from pcdsdevices.epics_motor import IMS

from sxr.devices import Sequencer
from sxr.exceptions import InputError

from .devices import McgranePalette
from .exceptions import InvalidSampleError
from .plans import mcgrane_scan as _mcgrane_scan
from .utils import calibrated

logger = logging.getLogger(__name__)

# Devices        

class User(object):
    # Devices
    monochrometer = IMS("SXR:MON:MMS:06", name="Monochrometer Pitch")
    sequencer = Sequencer("ECS:SYS0:2", name="Event Sequencer")
    palette = McgranePalette(name="Mcgrane Palette")

    def __init__(self, *args, **kwargs):
        """User class for the LR58 Mcgrane experiment.

        For the LR58 Mcgrane experiment, an abstracted class for the sample 
        palette and scheme for scanning through this palette were implemented. 
        The palette device is provided here as class attribute named `palette`. 
        Additionally, there are two other class attribute devices provided, 
        `monochrometer` for the monochrometer pitch motor, and `sequencer` for 
        the SXR event sequencer.

        For the most part, these three devices are not meant to be interacted 
        with directly except for sample palette for when calibrations need to be
        performed, or position introspection is desired. Instead, most of the
        interfacing with these devices is supposed to be done using the 
        `mcgrane_scan` plan, which will perform the desired experiment scan.
        """
        # Paths
        self.dir_sxropr = Path('/reg/neh/operator/sxropr')
        self.dir_experiment = self.dir_sxropr / 'experiments/sxrlr5816'
        self.dir_scans = self.dir_experiment / 'mcgrane_scans'
        self.dir_calibrations = self.dir_experiment / 'calibrations'

        logger.info('Mcgrane scan results will be stored in "{0}"'.format(
            str(self.dir_scans)))
        logger.info('Palette calibrations will be stored in "{0}"'.format(
            str(self.dir_calibrations)))

        self.palette.load_calibration(confirm_overwrite=False)

    def mcgrane_scan(self, mono_start, mono_stop, mono_steps, palette_steps, 
                     mono=None, palette=None, seq=None, df_name=None, *args, 
                     **kwargs):
        """Performs the Mcgrane scan using the sample palette, monochrometer,
        and sequencer.

        The scan consists of an outer scan using the monochrometer and an inner
        scan using the sample palette. More concisely, at every monochrometer
        step, the sample palette moves forward by `palette_steps` steps, 
        starting the sequencer at every sample.

        Within every sample palette step, the sequencer is (optionally) started
        and run exactly once. The sequencer implementation provided here assumes
        that the executed sequence is pre-configured by the user before running 
        this scan, only controlling when it is executed. If a sequence has been
        started, the scan will wait until the "Play Status" PV returns to the 
        "stopped" state. Upon sequence completion, there is a final (optional)
        sleep before proceeding to the next step.

        Once the scan is complete, a csv file is written to the mcgrane_scan
        folder. This csv contains the sample number, chip number, (i,j) 
        coordinates, and (x,y,z) coordinates of the palette at every scan step.

        It should be noted that this method returns a plan and does *NOT* 
        perform the scan itself. To actually execute the scan, the returned plan
        must be passed to an instantiated `RunEngine` object, usually named `RE`
        like so:

            In [1]: RE(x.mcgrane_scan(1.8102, 1.8471, 2, 6))
        
        Parameters
        ----------
        mono_start : float
            Starting position for the outer scan using the monochrometer
            
        mono_stop : float
            Stopping position for the outer scan using the monochrometer
            
        mono_steps : int
            Number of points in the scan, including the endpoints. (i.e passing
            2 for this parameter will result in a two step scan with just the
            endpoints)

        palette_steps : int
            Number of samples to move through at each monochrometer step

        df_name : str, optional
            Name to use for the outputted scan csv

        use_sequencer : bool, optional
            Start the sequencer at every step of the scan

        wait : float, optional
            Perform an additional sleep at every sample
        """
        # Make sure df_name is a string  if it was passed
        if df_name and not isinstance(df_name, str):
            raise InputError('df_name must be a string. Got {0}'.format(
                type(df_name)))
        
        # Get the devices we will actually use
        mono = mono or self.monochrometer
        palette = palette or self.palette

        # Perform the mcgrane scan
        df = yield from _mcgrane_scan(
            mono or self.monochrometer, 
            palette or self.palette, 
            seq or self.sequencer, 
            mono_start, mono_stop, mono_steps, 
            palette_steps, 
            *args, **kwargs)
        logger.info('Scan complete!')
        
        # Save the dataframe
        df_name = df_name or 'scan_{0}.json'.format(
            time.strftime("%Y%m%d_%H%M%S"))
        df_path = self.dir_scans / df_name

        # Make the parent directory if it doesnt exist 
        if not df_path.parent.exists():
            df_path.parent.mkdir()
            df_path.parent.chmod(0o777)

        # Create the directories if they dont exist
        logger.info('Saving scan to "{0}"'.format(str(df_path)))
        df.to_csv(str(df_path))
        # Set permissions to be accessible to everyone
        df_path.chmod(0o777)
