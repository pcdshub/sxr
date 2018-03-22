import logging

from ophyd.device import Device, Component as Cpt, FormattedComponent as FCpt
from ophyd.signal import EpicsSignal, EpicsSignalRO, Signal
from ophyd import PVPositioner
from ophyd.status import wait as status_wait

from pcdsdevices.epics_motor import EpicsMotor, IMSMotor
from pcdsdevices.mv_interface import FltMvInterface

from utils import retry

logger = logging.getLogger(__name__)


class Vitara(Device, FltMvInterface):
    """
    Class for the Vitara phase shifter system.
    """
    _target = Cpt(EpicsSignal, ":FS_TGT_TIME_DIAL", name="Target time")
    _offset = Cpt(EpicsSignal, ":FS_TGT_TIME_OFFSET", name="Offset")
    _time = Cpt(EpicsSignal, ":FS_TGT_TIME", name="Timing")

    def set(self, value, *args, **kwargs):
        return self.move(value, *args, **kwargs)

    def move(self, value, *args, **kwargs):
        return self._time.set(value, *args, **kwargs)

    @property
    def position(self):
        return self.time

    @property
    def target(self):
        return self._target.get()

    @target.setter
    def target(self, value):
        return self._target.set(value)

    @property
    def offset(self):
        return self._offset.get()

    @offset.setter
    def offset(self, value):
        return self._offset.set(value)

    @property
    def time(self):
        return self._time.get()

    @time.setter
    def time(self, value):
        return self._time.set(value)  


class Newport(EpicsMotor):
    """
    Basic class for the newport motors.
    """

    home_forward = Cpt(Signal)
    home_reverse = Cpt(Signal)
    offset_freeze_switch = Cpt(Signal)

    #@retry(tries=3)
    def move(self, *args, **kwargs):
        return super().move(*args, **kwargs)


class Sequencer(Device):
    """
    Base sequencer class.
    
    Attributes
    ----------
    state_control : Component
        start and stop the sequencer with a binary signal. Use Start/Stop
        methods.

    set_run_count_pattern : Component
        Epics enum for defining whether to run the sequence once, n times or
        forever.
    
    set_run_count : Component
        If running n times, set n.

    sequence_owner : Component
        Numeric sequence owner

    sequence_owner_name : Component
        Enum sequence owner

    photon_beam_owner : Component
        Numberic beam owner

    photon_beam_owner_name : Component
        Enum beam owner
    
    """

    # left-most column
    state_control = Cpt(EpicsSignal, ":PLYCTL")
    set_run_count_pattern = Cpt(EpicsSignal, ":PLYMOD")
    set_run_count = Cpt(EpicsSignal, ":REPCNT")

    # top row
    sequence_owner = Cpt(EpicsSignal, ":HUTCH_ID")
    sequence_owner_name = Cpt(EpicsSignal, ":HUTCH_NAME")
    photon_beam_owner = FCpt(
        EpicsSignal, "{self._beam_owner_prefix}:BEAM_OWNER_ID")
    photon_beam_owner_name = FCpt(
        EpicsSignal, "{self._beam_owner_prefix}:BEAM_OWNER_NAME")
    
    # center column
    beam_rate = FCpt(EpicsSignalRO, "{self._beam_rate_pv}")
    play_count = Cpt(EpicsSignalRO, ":PLYCNT")
    total_play_count = Cpt(EpicsSignalRO, ":TPLCNT")
    play_status = Cpt(EpicsSignalRO, ":PLSTAT")
    current_step = Cpt(EpicsSignalRO, ":CURSTP")

    # right column
    sync_marker = Cpt(EpicsSignal,":SYNCMARKER")
    next_sync = Cpt(EpicsSignal,":SYNCNEXTTICK")
    run_using = Cpt(EpicsSignal,":BEAMPULSEREQ")

    # add some properties 
    # learn about hints methods 

    def __init__(self, prefix, timeout=1, *args, **kwargs):
        self._beam_rate_pv = "EVNT:SYS0:1:LCLSBEAMRATE"
        self._beam_owner_prefix = "ECS:SYS0:0"
        super().__init__(prefix, *args, **kwargs)
        self.timeout = timeout

    def start(self,wait=True):
        """
        Start the sequencer.
        """
        status = self.state_control.set(1, timeout=self.timeout)
        if wait:
            status_wait(status)
        
    def stop(self,wait=True):
        """
        Stop the sequencer.
        """ls
        status = self.state_control.set(0, timeout=self.timeout)
        if wait:
            status_wait(status)        


class ConsolidatedSamplePalette(Device):
    '''

    '''
    '''
    x_motor = Cmp(IMS,"")
    y_motor = Cmp(IMS,"")
    z_motor = Cmp(IMS,"")

    '''
    pass

