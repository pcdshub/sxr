import time
import logging
from imp import reload
from pathlib import Path

from bluesky import RunEngine
from bluesky.preprocessors import run_wrapper
from ophyd.sim import SynAxis

from pcdsdevices.daq import Daq, make_daq_run_engine

from plans import delay_scan as _delay_scan
from devices import Newport, Vitara, Sequencer
from exceptions import InputError


logger = logging.getLogger(__name__)

def delay_scan(start, stop, num=None, step_size=None, events_per_point=1000, 
               record=True, controls=None, wait=None, return_to_start=True, 
               delay_const=1):
    """
    Perform a scan using the AMO delay stage and SXR vitara timing system.

    For this function to interface with the DAQ properly, it must be run from
    the same machine the DAQ session is running from (usually sxr-daq). Also,
    the DAQ must be allocated before the function is run.

    Parameters
    ----------
    start : float
        Starting delay for the scan in ns.

    stop : float
        Stopping delay for the scan in ns.
        
    num : int
        Number of steps to take, including the endpoints.

    step_size : float
        Step size to use for the scan.

    events_per_point : int, optional
        Number of daq events to take at each step of the scan.
        
    record : bool, optional
        Record the data as a DAQ run.

    controls : dict, optional
        Dictionary containing the EPICS pvs to record in the DAQ. Has the form:
        {"motor_name" : motor.position}

    wait : int, optional
        The amount of time to wait at each step.

    return_to_start : bool, optional
        Return the vitara and the delay stage to their starting positions.

    delay_const : float, optional
        Scale the delay move delta by this amount.

    Raises
    ------
    InputError
        If neither the number of the steps or the step_size is provided.

    ValueError
        If the step_size provided does not yield an whole number of steps.
    """
    # Check to make sure a number of steps or step size is provided
    if num is None and step_size is None:
        raise InputError("Must specify either the number of steps to take or "
                         "the step size to use for the scan.")
    # Check that the step size is valid
    elif num is None and step_size is not None:
        num = (stop - start + 1) / step_size
        if num % 1:
            raise ValueError("Step size '{0}' does not produce an integer "
                             "number of steps for starting delay '{1}' and "
                             "stopping delay '{2}'".format(step_size, start,
                                                           stop))
    plan = _delay_scan(daq, vitara, delay, start, stop, num, controls=controls,
                       return_to_start=return_to_start, record=record, 
                       wait=wait, events_per_point=events_per_point, 
                       delay_const=delay_const)
    RE(plan)

def delay_scan_rel(start_rel, stop_rel, *args, **kwargs):
    """
    Performs a scan relative to the current delay of the system. See 
    `delay_scan` for full documentation on other parameters.

    Parameters
    ----------
    start_rel : float
        Relative starting delay for the scan in ns.

    stop_rel : float
        Relative stopping delay for the scan in ns.
    """
    pos = vitara.position
    return delay_scan(pos + start_rel, pos + stop_rel, *args, **kwargs)
    
# Devices
vitara = Vitara("LAS:FS2:VIT", name="Vitara")
delay = Newport("SXR:LAS:H1:DLS:01", name="Delay Stage")
testMotor = SynAxis(name="Blah")
sequencer = Sequencer("ECS:SYS0:2",name="sequencer")

# DAQ
daq = Daq(None, platform=0)

# Run Engine
RE = RunEngine({})


