


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

from enum import Enum

logger = logging.getLogger(__name__)

class BeamShutter(InOutRecordPositioner):
    state = Cpt(EpicsSignal, ':CMD', kind='omitted')
    states_list = ['IN', 'OUT']
    in_states = ['IN']
    out_states = ['OUT']
    _unknown = False
    states_enum = Enum('ShutterStatesEnum',['IN','OUT'],start=0)

shutter = BeamShutter('SXR:SPS:MPA:01', name='shutter')
rsxs_sample_x = IMS(prefix='SXR:EXP:MMS:25',name='rsxs_sample_x')
rsxs_sample_y = IMS(prefix='SXR:EXP:MMS:26',name='rsxs_sample_y')
tst_23 = x = IMS(prefix='SXR:EXP:MMS:23',name='test_motor')
