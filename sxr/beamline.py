from hutch_python.utils import safe_load
from ophyd.sim import SynAxis

from .devices import McgrainPalette, ErrorIMS, Sequencer

# Test axes that may come in handy
with safe_load('Virtual Motors'):
    virtual_motor_1 = SynAxis(name='Virtual Motor 1')
    virtual_motor_2 = SynAxis(name='Virtual Motor 2')
    virtual_motor_3 = SynAxis(name='Virtual Motor 3')

with safe_load('Mcgrain Palette'):
    palette = McgrainPalette(name="Mcgrain Palette")

with safe_load('Monochrometer'):
    mono = ErrorIMS("SXR:MON:MMS:06", name="Monochrometer")

with safe_load('Event Sequencer'):
    sequencer = Sequencer("ECS:SYS0:2", name="Event Sequencer")
