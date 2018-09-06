import logging

from bluesky import RunEngine
from bluesky.preprocessors import run_wrapper

from experiments.lu20.devices import (shutter, rsxs_sample_x, rsxs_sample_y,
    tst_23)
from experiments.lu20.plans import rel_smooth_sweep_test, rel_smooth_sweep
from bluesky.callbacks.best_effort import BestEffortCallback
from bluesky.utils import ProgressBarManager

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

def macro_RSXS_smooth_sweep(stroke_height, stroke_spacing, n_strokes,
            both_directions=True):
    """
    macro_RSXS_smooth_sweep

    This method wraps up the bluesky/ophyd codeand allows users to drive
    the LU20 experiment with minimal code overhead. It contains the following
    bluesky plan.

    This bluesky plan moves a 2-axis actuator across multiple traversals of a
    sample. The plan traverses the entirety of the stroke_height (y-axis) and
    after each traversal, steps in the x-axis by the stroke_spacing.It may be
    configured to scan in only a single direction and shutter the beam for the
    opposite direction. This removes the shutter at the beginning of the plan
    and reinserts it at the end. At the end of the plan, the sample is moved to
    its original y-axis position but with an x-axis posiiton ready for the next
    run. For more details about the path, see the documentation of the
    xy_sequencer, the method that generates the sample's path. 

    Parameters 
    ----------
    stroke_height : float
        Vertical distance (y-axs) of each stroke.

    stroke_spacing : float
        Horizontal distance between individual strokes.
    
    n_strokes : int
        Number of strokes to complete.

    both_directions : bool, optional
        Defaults to True. If this value is true the beam will be scanned across
        the sample while moving in both vertical directions. If false, the beam
        is only scanned in a single direction.
    """

    RE = RunEngine({})
    bec = BestEffortCallback()
    RE.subscribe(bec)
    RE.waiting_hook = ProgressBarManager()
    RE(run_wrapper(rel_smooth_sweep(
        mot_x=rsxs_sample_x,
        mot_y=rsxs_sample_y,
        shutter=shutter,
        stroke_height=stroke_height,
        stroke_spacing=stroke_spacing,
        n_strokes=n_strokes,
        both_directions=both_directions
    )))


