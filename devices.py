from functools import reduce
import logging
import numpy as np

from ophyd.device import Device, Component as Cpt, FormattedComponent as FCpt
from ophyd.signal import EpicsSignal, EpicsSignalRO, Signal
from ophyd import PVPositioner
from ophyd.status import wait as status_wait

from pcdsdevices.epics_motor import EpicsMotor, IMS
from pcdsdevices.mv_interface import FltMvInterface

from calib_file import CalibFile

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
        """
        status = self.state_control.set(0, timeout=self.timeout)
        if wait:
            status_wait(status)        


class McgrainPalette(Device, FltMvInterface):
    """Base device for the mcgrain  paddle"""
    x_motor = Cpt(IMS, "SXR:EXP:MMS:08", name='LJE Sample X')
    y_motor = Cpt(IMS, "SXR:EXP:MMS:10", name='LJE Sample Y')
    z_motor = Cpt(IMS, "SXR:EXP:MMS:11", name='LJE Sample Z')

    def __init__(self, N=24, M=(24*3 + 8), timeout=1, *args, **kwargs):
        """
        N : int
            specify the number of samples in the N direction

        M : int
            specify the number of samples in the M direction
        """
        super().__init__('', *args, **kwargs)
        self.timeout = timeout

        self.calibrated = False

        # How many samples are there in the N and M directions
        self.N = N
        self.M = M - 1

        # if the number of samples on the pallete is not given, presume full
        # matrix allotment 
        self.samples = self.N * self.M

        # This will be convenient
        self.motors = [self.x_motor, self.y_motor, self.z_motor]

    def calibrate_from_file(self, file_name):
        """
        Set calibration using a CalibFile or .csv saved from a CalibFile

        Parameters
        ----------
        file_name : str or CalibFile
            Either pass the name of the .csv saved from a CalibFile or pass the
            CalibFile direcly.
        """
        data_file = CalibFile(file_name)
        self.accept_calibration(
            N=data_file.N,
            M=data_file.M,
            start_pt=data_file.start_pt,
            n_pt=data_file.n_pt,
            m_pt=data_file.m_pt
        )

    def accept_calibration(self, n_steps, m_steps, start_pt, n_pt, m_pt):
        """
        Notes on coordinates:
        
        Z points upstream along the beam, X points horizontally, Y points
        vertically

        N,M coordinates represent points on the sample palette. N roughly
        parallels the X axis and M roughly parallels Y. 

        I,J coordinates are used to reference specific samples using the N,M
        system.

        K represents samples along the snake-shaped scanning path. 


        n : int
            Number of samples stepped over in the N axis for calibration

        m : int 
            Number of samples stepped over in the M axis for calibration

        start_pt : np.array or pd.Series
            3-length iterable (x,y,z) specifying spatial coordinate of bottom
            left (facing downstream) sample where the scan will start from 

        n_pt : np.array or pd.Series
            3-length iterable (x,y,z) specifying spatial coordinate of the
            fiducail sample on the N axis
        
        m_pt : np.array or pd.Series
            3-length iterable (x,y,z) specifying spatial coordinate of the
            fiducial smaple on the M ais
        """
        if self.calibrated:
            logger.warning("WARNING: Overriding existing calibration!")
        
        self.calibrated = True

        # save the origin point in XYZ space
        self.start_pt = start_pt

        # Define unit vectors on the NM plane in XYZ space
        self.N_hat = (n_pt - self.start_pt) / self.N
        self.M_hat = (m_pt - self.start_pt) / self.M

    def locate_2d(self, i, j):
        """Return XYZ coordinates of sample i, j

        Parameters
        ----------
        i : int
            The i coordinate to move to on the palette

        j : int
            The j coordinate to move to on the palette
        """
        return self.start_pt + i * self.N_hat + j * self.M_hat

    def locate_1d(self, k):
        """
        return NM coordinates of sample k

        k : int
        """
        # calculate the horizontal row
        j = int(np.floor(k / self.N))

        # calculate the column w/o snake-wrapping
        i = k % self.N

        # apply snake-wrapping to odd columns by reversing pathing order 
        if j % 2 :
            i = (self.N - i) - 1

        return np.array([i, j])

    def move_3d(self, x, y, z, *, timeout=None, wait=False):
        """
        Move to given XYZ coordinate

        x : float

        y : float

        z : float 

        timeout : int

        wait : bool
        """
        # Move each motor to the corresponding position and collect the status
        # objects in a list
        status_list = [motor.move(val, timeout=timeout, wait=wait)
                       for motor, val in zip(self.motors, (x,y,z))]
        # Reduce the list to a single AndStatus
        return reduce(lambda s1, s2: s1 & s2, status_list)

    def move_2d(self, i ,j, *, timeout=None, wait=False):
        """
        Move to point IJ in NM space.
        
        i : int
        
        j : int

        timeout : int

        wait : bool
        """
        return self.move_3d(*self.locate_2d(i, j), timeout=timeout, wait=wait)

    def move_1d(self, k, *, timeout=None, wait=False):
        """
        Move to point K in the sampling path space
        
        k : int

        timeout : int

        wait : bool
        """
        return self.move_2d(*self.locate_1d(k), timeout=timeout, wait=wait)
            
    def move(self, *args, timeout=None, wait=False):
        """
        Wrap move_1d under a common name.
        
        k : int

        timeout : int

        wait : bool
        """
        num_args = len(args)
        if num_args > 3:
            raise ValueError('Cannot pass more than three inputs to move '
                             'command, got {0}'.format(len(args)))

        move_funcs = [self.move_1d, self.move_2d, self.move_3d]
        return move_funcs[num_args-1](*args, timeout=timeout, wait=wait)

    def set(self, *args, **kwargs):
        """
        Add compatibility with the abs_set plan in bluesky
        """
        return self.move(*args, **kwargs)     

    def mv(self, *args, wait=True, **kwargs):
        status = super().mv(*args, **kwargs)

        if wait:
            try:
                status_wait(status)
            except KeyboardInterrupt:
                for motor in self.motors:
                    motor.stop()
                raise

        return status

    @property
    def position(self):
        return tuple(motor.position for motor in self.motors)

