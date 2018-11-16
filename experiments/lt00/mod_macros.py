import logging

from bluesky import RunEngine
from bluesky.preprocessors import run_wrapper

from experiments.lt00.mod_devices import shutter
from experiments.lt00.mod_plans import rel_smooth_sweep
from bluesky.callbacks.best_effort import BestEffortCallback
from bluesky.utils import ProgressBarManager

from pcdsdevices.epics_motor import IMS


logger = logging.getLogger(__name__)

def macro_sweep_test(target):
    logging.info('macro_sweep_test initiated with target {:0.4f}'.format(
        target
    ))
    RE = RunEngine({})
    bec = BestEffortCallback()
    RE.subscribe(bec)
    RE.waiting_hook = ProgressBarManager()
    RE(run_wrapper(rel_smooth_sweep_test(tst_23,target)))

sample_x = IMS(
    prefix='SXR:EXP:MMS:43',
    name='Sample X axis VT50 motor'
)

sample_y = IMS(
    prefix='SXR:EXP:MMS:44',
    name='Sample Y axis VT50 motor'
)

sample_z = IMS(
    prefix='SXR:EXP:MMS:45',
    name='Sample Z axis VT50 motor'
)

def macro_VT50_smooth_sweep(short_edge_end, long_edge_end, n_strokes,
            scalar=1.0, min_base=.05, min_v=.07,  both_directions=True):
    """
    macro_RSXS_smooth_sweep

    This method wraps up the bluesky/ophyd codeand allows users to drive
    the LT00 experiment with minimal code overhead. It contains the following
    bluesky plan.

    This bluesky plan moves a 3-axis actuator across multiple traversals of a
    sample. The plan traverses the space enclosed in a plane defined by the
    motors' starting location and the two positions short_edge_end and
    long_edge_end. 
    

    Parameters 
    ----------
    short_edge_end : tuple or np.array
        3-length (x,y,z) iteralbe specifying the end location of the short
        steps.
    
    long_edge_end : tuple or np.array
        3-length (x,y,z) iteralbe specifying the end location of the long
        sweep.
    
    n_strokes : int
        Number of strokes to complete.

    scalar : float
        Scale the motor velocities by this factor. Defaults to 1.0.

    min_base : float
        Set motor's Base velocity. Larger numbers means the motor accelerates
        and decelerates more quickly. This value must be less than min_v.
        Values larger than 2 are not recommended.

    min_v : float 
        Set the motor's minimum velocity. Must be larger than min_base. Larger
        numbers means the motor accelerates and decelerates more quickly.
        Values larger than 2 are not recommended. 
    """

    RE = RunEngine({})
    bec = BestEffortCallback()
    RE.subscribe(bec)
    RE.waiting_hook = ProgressBarManager()
    RE(run_wrapper(rel_smooth_sweep(
            mot_x=sample_x,
            mot_y=sample_y,
            mot_z=sample_z,
            shutter=shutter,
            short_edge_end=short_edge_end,
            long_edge_end=long_edge_end,
            n_strokes=n_strokes,
            scalar=scalar,
            min_base=min_base,
            min_v=min_v
    )))


