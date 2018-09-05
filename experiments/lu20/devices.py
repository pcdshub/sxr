


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
from ophyd.device import Device, Component as Cpt
from ophyd.status import Status, wait as status_wait
from pcdsdevices.mv_interface import FltMvInterface
from pcdsdevices.epics_motor import IMS

from sxr.devices import ErrorIMS
from sxr.exceptions import InputError

logger = logging.getLogger(__name__)

class shutter(Device):
    pass

x = IMS(name='SXR:MMS:EXP:25')
x = IMS(name='SXR:MMS:EXP:26')
