import IPython
import logging
import time
import os
from pathlib import Path
from functools import reduce
from glob import glob
from inspect import getdoc, getframeinfo, currentframe

import json
import numpy as np
from ophyd import EpicsSignal
from ophyd.device import Device, Component as Cpt
from ophyd.status import Status, wait as status_wait
from pcdsdevices.mv_interface import FltMvInterface
from pcdsdevices.epics_motor import IMS
from pcdsdevices.inout import InOutRecordPositioner

from sxr.devices import ErrorIMS
from sxr.exceptions import InputError
from experiments.lu20.devices import BeamShutter

from enum import Enum

logger = logging.getLogger(__name__)


class LT00BeamShutter(BeamShutter):
    """
    Add pause, stop, resume methods to the BeamShutter used for LU00. This
    allows intermediate cancellation.
    """
    def stop(self):
        self.insert()

    def pause(self):
        self.stop()

    def resume(self):
        self.remove()

shutter = LT00BeamShutter('SXR:SPS:MPA:01', name='SXR shutter')



