import logging
import numpy as np
import time
from pathlib import Path

import json
from ophyd.utils.epics_pvs import fmt_time
from ophyd.device import Device, Component as Cpt, FormattedComponent as FCpt
from ophyd.signal import EpicsSignal, EpicsSignalRO, Signal
from ophyd.status import Status, wait as status_wait, SubscriptionStatus
from pcdsdevices.epics_motor import EpicsMotor, IMS
from pcdsdevices.mv_interface import FltMvInterface

logger = logging.getLogger(__name__)


class ErrorIMS(IMS):
    """IMS motor that has a constant error on moves."""
    def _move_changed(self, timestamp=None, value=None, sub_type=None,
                      **kwargs):        
        '''Callback from EPICS, indicating that movement status has changed'''
        was_moving = self._moving
        self._moving = (value != 1)

        started = False
        if not self._started_moving:
            started = self._started_moving = (not was_moving and self._moving)

        logger.debug('[ts=%s] %s moving: %s (value=%s)', fmt_time(timestamp),
                     self, self._moving, value)

        if started:
            self._run_subs(sub_type=self.SUB_START, timestamp=timestamp,
                           value=value, **kwargs)

        if was_moving and not self._moving:
            success = True
            # Check if we are moving towards the low limit switch
            if self.direction_of_travel.get() == 0:
                if self.low_limit_switch.get() == 1:
                    success = False
            # No, we are going to the high limit switch
            else:
                if self.high_limit_switch.get() == 1:
                    success = False

            # This is the one change necessary to make this work. We need to
            # stop the motor from checking the severity of the readback

            # severity = self.user_readback.alarm_severity
            # if severity != AlarmSeverity.NO_ALARM:
            #     status = self.user_readback.alarm_status
            #     logger.error('Motion failed: %s is in an alarm state '
            #                  'status=%s severity=%s',
            #                  self.name, status, severity)
            #     success = False

            self._done_moving(success=success, timestamp=timestamp,
                              value=value)
    

class Vitara(Device, FltMvInterface):
    """Class for the Vitara phase shifter system."""
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


class Sequencer(Device):
    """Class for controlling the event sequencer.
    
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
        self._cb_sleep = 0.0125

    def set(self, value, *args, **kwargs):
        """Set the sequencer start PV to the inputted value."""
        def cb(*args, **kwargs):
            time.sleep(self._cb_sleep)
            return self.play_status.get() == 0
        self.state_control.put(value)
        return SubscriptionStatus(self.play_status, cb)

    def start(self, wait=False):
        """
        Start the sequencer.
        """
        self.status = self.set(1)
        if wait:
            self.wait(self.status)
        return self.status
        
    def stop(self, wait=False):
        """
        Stop the sequencer.
        """
        self.status = self.set(0)
        if wait:
            self.wait(self.status)
        return self.status

    def wait(self, status=None):
        """Wait for the inputted status to complete."""
        try:
            status = status or self.status
            status_wait(status)
        except KeyboardInterrupt:
            pass
            
