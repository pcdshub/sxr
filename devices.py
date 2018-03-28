from functools import reduce
import logging
import numpy as np

from ophyd.status import Status
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

    def set(self, value, *args, **kwargs):
        self.state_control.set(1, timeout=self.timeout)
        status = SubscriptionStatus(self.play_count, 
                                    self.play_count.get() + 1)
        return status

    def start(self, wait=True):
        """
        Start the sequencer.
        """
        status = self.state_control.set(1, timeout=self.timeout)
        if wait:
            status_wait(status)
        
    def stop(self, wait=True):
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

    def __init__(self, N=23, M=(24*3 + 8), chip_spacing=2.4, sample_spacing=1.0,
                 timeout=1,  samples_per_chip=24, invert=False, 
                 *args, **kwargs):
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
        self.M = M

        self.samples_per_chip = samples_per_chip 
        self.chip_spacing = chip_spacing
        self.sample_spacing = sample_spacing
        self.num_chips = self.M // self.samples_per_chip
        self.length = ((self.M - self.num_chips - 1)*self.sample_spacing 
                       + self.num_chips * self.chip_spacing)

        self.chip_factor = (self.chip_spacing - self.sample_spacing)/self.length

        # if the number of samples on the pallete is not given, presume full
        # matrix allotment 
        self.samples = self.N * self.M

        # This will be convenient
        self.motors = [self.x_motor, self.y_motor, self.z_motor]

        # Create a list of the different move functions we could use
        self.move_funcs = [self.move_1d, self.move_2d, self.move_3d]

        # 
        if invert:
            self.invert()

    def calibrate_from_file(self, file_name):
        """Set calibration using a CalibFile or .csv saved from a CalibFile

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

    def accept_calibration(self, start_pt, n_pt, m_pt):
        """
        Notes on coordinates:
        
        Z points upstream along the beam, X points horizontally, Y points
        vertically

        N,M coordinates represent points on the sample palette. N roughly
        parallels the X axis and M roughly parallels Y. 

        I,J coordinates are used to reference specific samples using the N,M
        system.

        K represents samples along the snake-shaped scanning path. 


        n_steps : int
            Number of samples stepped over in the N axis for calibration

        m_steps : int 
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
        self.n_pt = n_pt
        self.m_pt = m_pt

        # Define unit vectors on the NM plane in XYZ space
        self.N_hat = (self.n_pt - self.start_pt) / (self.N - 1)
        # Correct for the chip spacing when calculating the M_hat
        self.M_hat = (((self.m_pt - self.start_pt)
                       * (1 - self.num_chips*self.chip_factor))
                      / (self.M - 1))
        # Put both N_hat and M_hat in an array
        self.NM_hat = np.concatenate((self.N_hat.reshape(len(self.motors), 1), 
                                      self.M_hat.reshape(len(self.motors), 1)), 
                                     axis=1)

        self.length_calibrated = np.sqrt(np.sum((self.m_pt - self.start_pt)**2))

    def locate_2d(self, i, j):
        """Return XYZ coordinates of sample i, j

        Parameters
        ----------
        i : int
            The i coordinate to move to on the palette

        j : int
            The j coordinate to move to on the palette
        """
        return (self.start_pt + i*self.N_hat + j*self.M_hat 
                + self._chip_from_j(j)*self.chip_factor
                * (self.m_pt - self.start_pt))

    def locate_1d(self, k):
        """Return NM coordinates of sample k

        Parameters
        ----------
        k : int
            The 1D position to move the motor to
        """
        # calculate the horizontal row
        j = int(np.floor(k / (self.N)))
        # calculate the column w/o snake-wrapping
        i = k % (self.N)
        # apply snake-wrapping to odd columns by reversing pathing order 
        if j % 2:
            i = (self.N - i) - 1
        return np.array([i, j])

    def move_3d(self, x, y, z, *, timeout=None, wait=False):
        """Move to given XYZ coordinate

        x : float

        y : float

        z : float 

        timeout : int

        wait : bool
        """
        # Move each motor to the corresponding position and collect the status
        # objects in a list
        status_list = [motor.move(val, timeout=timeout, wait=False)
                       for motor, val in zip(self.motors, (x, y, z))]

        # Reduce the list to a single AndStatus
        status = reduce(lambda s1, s2: s1 & s2, status_list)
        
        if wait:
            status_wait(status)
        return status

    def move_2d(self, i ,j, *, timeout=None, wait=False):
        """Move to point IJ in NM space.
        
        i : int
        
        j : int

        timeout : int

        wait : bool
        """
        return self.move_3d(*self.locate_2d(i, j), timeout=timeout, wait=wait)

    def move_1d(self, k, *, timeout=None, wait=False):
        """Move to point K in the sampling path space
        
        k : int

        timeout : int

        wait : bool
        """
        return self.move_2d(*self.locate_1d(k), timeout=timeout, wait=wait)
            
    def move(self, *args, timeout=None, wait=False):
        """Wrap move_1d under a common name.
        
        k : int

        timeout : int

        wait : bool
        """
        num_args = len(args)
        # Make sure we get the right number of arguments
        if num_args > 3:
            raise ValueError('Cannot pass more than three inputs to move '
                             'command, got {0}'.format(len(args)))

        # Select the move function based on the number of arguments passed
        return self.move_funcs[num_args-1](*args, timeout=timeout, wait=wait)

    def stop(self):
        for motor in self.motors:
            motor.stop()

    def set(self, *args, **kwargs):
        """Add compatibility with the abs_set plan in bluesky."""
        return self.move(*args, **kwargs)

    def mv(self, *args, wait=True, timeout=None):
        """Performs the standard mv but stops the motors on KeyboardInturrupts
        if waiting for the move to complete.
        """
        self.move(*args, timeout=timeout, wait=wait)

    def mvr(self, *args, timeout=None, wait=True):
        all_positions = [self.position, self.index, self.coordinates]
        position = all_positions[len(args)-1]
        return self.mv(*(args + position), timeout=timeout, wait=wait)

    @property
    def coordinates(self):
        """Returns the x,y,z coordinates of the palette."""
        return np.array([motor.position for motor in self.motors])

    @property
    def index(self):
        """Returns the i,j palette position based on the current coordinates."""
        start_diff = self.coordinates - self.start_pt
        raw_index = np.round(
            np.dot(start_diff, self.NM_hat)
            - np.array([0, 
                        self.chip*self.chip_factor*self.length_calibrated]))
        return raw_index.astype(int)

    @property
    def position(self):
        """Returns the current sample number."""
        i, j = self.index
        return j*self.N + (self.N - i - 1 if j%2 else i)

    @property
    def remaining(self):
        """Returns the remaining number of samples."""
        return self.samples - self.position - 1

    def _chip_from_j(self, j):
        """Returns the chip number based on the inputted column."""
        return j // self.samples_per_chip

    def _chip_from_xyz(self, coordinates):
        start_diff = coordinates - self.start_pt
        percent_complete = (np.dot(start_diff, self.M_hat)
                            / np.sqrt(np.sum((self.m_pt - self.start_pt)**2)))
        return self.M * percent_complete // self.samples_per_chip
        
    @property
    def chip(self):
        """Returns the current chip position."""
        return int(self._chip_from_xyz(self.coordinates))

    # def invert(self):
    #     self.N, self.M = self.M, self.N
    #     if hasattr(self, 'N_hat'):
    #         self.N_hat, self.M_hat = self.M_hat, self.N_hat
    #         self.NM_hat = np.flip(self.NM_hat, axis=1)
