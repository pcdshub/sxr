import uuid
import logging
import time

import pandas as pd
from bluesky.plan_stubs import one_nd_step, abs_set, wait as plan_wait
from bluesky.plans import scan, inner_product_scan
from bluesky.preprocessors import stub_wrapper

logger = logging.getLogger(__name__)

c = 299792458 * 1000 * 1e-9                           # mm/ns

def delay_scan(daq, vitara, delay, start, stop, num, *args, 
               return_to_start=True, delay_const=1, **kwargs):
    """Performs a delay scan using the vitara phase shifter and a delay stage,
    keeping the delay between them fixed.

    Parameters
    ----------
    daq : Daq
        DAQ instance to use. Must be running and allocated for the scan to work.
        
    vitara : Vitara
        Vitara phase shifter to use for the scan.

    delay : Motor
        Delay stage to use for the scan.

    num : int
        number of steps

    return_to_start : bool, optional
        Return the vitara and the delay stage to their starting positions.

    delay_const : float, optional
        Scale the delay move delta by this amount.
    """
    
    # Get the initial positions of the delay stage and vitara
    delay_init = delay.position
    vitara_init = vitara.position
    
    # Find the difference between the starting and and ending points of the 
    # vitara relative to where it currently is
    vitara_start_diff = start - vitara_init
    vitara_stop_diff = stop - vitara_init

    # Use the vitara position differences to find the delay stage starting and
    # ending positions
    delay_start = delay_init - delay_const * (vitara_start_diff * c) / 2
    delay_stop = delay_init - delay_const * (vitara_stop_diff * c) / 2
    
    # Run the underlying plan
    try:
        yield from a2_daq_scan(daq, num, vitara, start, stop, delay, 
                               delay_start, delay_stop, *args, **kwargs)
    # Move back to the initial positions if specified
    finally:
        if return_to_start:
            print("Returning vitara and delay stage to initial positions.")
            group = str(uuid.uuid4())
            for dev, pos in zip([vitara, delay], [vitara_init, delay_init]):
                yield from abs_set(dev, pos, group=group)
            yield from plan_wait(group=group)

def a2_daq_scan(daq, num, *args, events_per_point=1000, record=False, 
                controls=None, wait=None, md=None, **kwargs):
    """Performs an a2 scan and takes daq events at each step.

    Parameters
    ----------
    daq : Daq
        DAQ instance to use. Must be running and allocated for the scan to work.

    num : int
        number of steps

    ``*args`` : {Positioner, Positioner, int}
        patterned like (``motor1, start1, stop1, ..., motorN, startN, stopN``)
        Motors can be any 'setable' object (motor, temp controller, etc.)

    events_per_point : int, optional
        Number of daq events to take at each step of the scan.
        
    record : bool, optional
        Record the data as a DAQ run.

    controls : dict, optional
        Dictionary containing the EPICS pvs to record in the DAQ. Has the form:
        {"motor_name" : motor.position}

    wait : int, optional
        The amount of time to wait at each step.

    md : dict, optional
        metadata
    """
    events = events_per_point

    # Define what to do at each step
    def per_step(detectors, motor, step):
        for m, pos in motor.items():
            print("Moving '{0}' to {1}".format(m.name, pos))
        yield from one_nd_step([], motor, step)
        if wait is not None:
            print("Step complete! Waiting for {0} second(s)...\n".format(wait))
            time.sleep(wait)
        # Take daq events
        daq.begin(events=events, controls=controls)
        print('Waiting for {} events ...\n'.format(events))
        daq.wait()

    try:
        # Connect and configure the daq
        daq.connect()
        daq.configure(record=record, controls=controls)
        if not daq.connected:
            raise Exception("Could not connect to the Daq!")
        # Run the inner product scan
        print("Established DAQ connection, beginning scan.")
        yield from inner_product_scan([], num, *args, per_step=per_step, md=md,
                                      **kwargs)
    finally:
        print("Completed scan, ending DAQ run.")
        daq.end_run()
        daq.disconnect()

def a2_scan(num, *args, wait=None, md=None, **kwargs):
    """Performs a multi-motor scan on a linear trajectory, waiting the specified 
    amount of time at each step.

    Parameters
    ----------
    num : integer
        number of steps

    ``*args`` : {Positioner, Positioner, int}
        patterned like (``motor1, start1, stop1, ..., motorN, startN, stopN``)
        Motors can be any 'setable' object (motor, temp controller, etc.)

    wait : int, optional
        The amount of time to wait at each step.

    md : dict, optional
        metadata
    """
    # Define what to do at each step
    def per_step(detectors, motor, step):
        for m, pos in motor.items():
            print("Moving '{0}' to {1}".format(m.name, pos))
        yield from one_nd_step([], motor, step)
        if wait is not None:
            print("Step complete! Waiting for {0} second(s)...\n".format(wait))
            time.sleep(wait)

    # Run the inner product scan
    yield from inner_product_scan([], num, *args, per_step=per_step, md=md, 
                                  **kwargs)
