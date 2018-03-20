import logging

from ophyd.device import Device, Component as C
from ophyd.signal import EpicsSignal, EpicsSignalRO, Signal
from ophyd import PVPositioner

from pcdsdevices.epics_motor import EpicsMotor
from pcdsdevices.mv_interface import FltMvInterface

from utils import retry

logger = logging.getLogger(__name__)


class Vitara(Device, FltMvInterface):
    """
    Class for the Vitara phase shifter system.
    """
    _target = C(EpicsSignal, ":FS_TGT_TIME_DIAL", name="Target time")
    _offset = C(EpicsSignal, ":FS_TGT_TIME_OFFSET", name="Offset")
    _time = C(EpicsSignal, ":FS_TGT_TIME", name="Timing")

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
    home_forward = C(Signal)
    home_reverse = C(Signal)
    offset_freeze_switch = C(Signal)

    #@retry(tries=3)
    def move(self, *args, **kwargs):
        return super().move(*args, **kwargs)


class SeqBase(SndDevice):
    """
    Base sequencer class.
    """
    state_control = Cmp(EpicsSignal, ":PLYCTL")
    
    def __init__(self, prefix, timeout=1, *args, **kwargs):
        super().__init__(prefix, *args, **kwargs)
        self.timeout = timeout

    def start(self):
        """
        Start the sequencer.
        """
        status = self.state_control.set(1, timeout=self.timeout)
        status_wait(status)
        
    def stop(self):
        """
        Stop the sequencer.
        """
        status = self.state_control.set(0, timeout=self.timeout)
        status_wait(status)        
