from functools import reduce
import logging
import numpy as np
import time
from inspect import getdoc, getframeinfo, currentframe
import IPython

from ophyd.status import Status
from ophyd.device import Device, Component as Cpt, FormattedComponent as FCpt
from ophyd.signal import EpicsSignal, EpicsSignalRO, Signal
from ophyd import PVPositioner
from ophyd.status import wait as status_wait, SubscriptionStatus

from pcdsdevices.epics_motor import EpicsMotor, IMS
from pcdsdevices.mv_interface import FltMvInterface

from .calib_file import CalibFile

logger = logging.getLogger(__name__)


class ErrorIMS(IMS):
    def move(self, *args, **kwargs):
        try:
            status = super().move(*args, **kwargs)
        except RuntimeError:
            pass
        def cb(*args, **kwargs):
            time.sleep(0.0125)
            return np.isclose(self.user_setpoint.get(), 
                              self.user_readback.get(), atol=0.01)
        return SubscriptionStatus(self.user_readback, cb)


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
        status = self.set(1)
        if wait:
            status_wait(status)
        return status
        
    def stop(self, wait=False):
        """
        Stop the sequencer.
        """
        status = self.set(0)
        if wait:
            status_wait(status)        
        return status


class McgrainPalette(Device, FltMvInterface):
    """Base device for the mcgrain  paddle"""
    x_motor = Cpt(IMS, "SXR:EXP:MMS:08", name='LJE Sample X')
    y_motor = Cpt(IMS, "SXR:EXP:MMS:10", name='LJE Sample Y')
    z_motor = Cpt(IMS, "SXR:EXP:MMS:11", name='LJE Sample Z')

    def __init__(self, N=(24*3 + 8), M=23, chip_spacing=2.4, sample_spacing=1.0,
                 timeout=1,  chip_dims=[8,24,24,24], *args, **kwargs):
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

        # Dimensions of the chips
        self.chip_dims = chip_dims

        if self.N != sum(self.chip_dims):
            raise InputError('Inputted differing number of samples in M as the '
                             'number of samples in the chip dimensions. Got '
                             '{0} and {1} (sum {2}).'.format(
                                 self.N, self.chip_dims, sum(self.chip_dims)))
        self.chip_dims_percents = [sum(self.chip_dims[:i+1]) / self.N
                                   for i in range(len(self.chip_dims))]

        self.chip_spacing = chip_spacing
        self.sample_spacing = sample_spacing

        self.num_chips = len(self.chip_dims) - 1
        self.length = ((self.N - self.num_chips - 1)*self.sample_spacing 
                       + self.num_chips * self.chip_spacing)

        self.chip_factor = (self.chip_spacing - self.sample_spacing)/self.length

        # if the number of samples on the pallete is not given, presume full
        # matrix allotment 
        self.samples = self.N * self.M

        # This will be convenient
        self.motors = [self.x_motor, self.y_motor, self.z_motor]

        # Create a list of the different move functions we could use
        self.move_funcs = [self.move_1d, self.move_2d, self.move_3d]

        # Calibration attributes
        self.start_pt = None
        self.n_pt = None
        self.m_pt = None
        self.calibration_coordinates = None
        self.N_hat = None
        self.M_hat = None
        self.NM_hat = None
        self.length_calibrated = None

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

    def accept_calibration(self, start_pt, n_pt, m_pt, confirm_overwrite=False):
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
        if self.calibrated and confirm_overwrite:
            # Get input from the user if they really want to calibrate
            prompt_str = 'Are you sure you want to overwrite the current ' \
              'calibration ([y]/n)? '
            response = input(prompt_str)
            while response.lower() not in set(['y', 'n']):
                # Keep probing until they enter y or n
                response = input('Invalid input "{0}". ' + prompt_str) 
                # If they are happy with the position, move on to the next point
            if response.lower() == 'n':
                logger.info('Canceling calibration.')
                return
        
        self.calibrated = True
        # save the origin point in XYZ space
        self.start_pt = start_pt
        self.n_pt = n_pt
        self.m_pt = m_pt
        self.calibration_coordinates = [self.start_pt, self.n_pt, self.m_pt]

        # Define unit vectors on the NM plane in XYZ space
        self.N_hat = (((self.n_pt - self.start_pt) 
                       * (1 - self.num_chips*self.chip_factor))
                      / (self.N - 1))

        # Correct for the chip spacing when calculating the M_hat
        self.M_hat = (self.m_pt - self.start_pt) / (self.M - 1)
        # Put both N_hat and M_hat in an array
        self.NM_hat = np.concatenate((self.N_hat.reshape(len(self.motors), 1), 
                                      self.M_hat.reshape(len(self.motors), 1)), 
                                     axis=1)

        self.length_calibrated = np.sqrt(np.sum((self.n_pt - self.start_pt)**2))
        logger.info('Successfully calibrated "{0}"'.format(self.name))

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
                + self._chip_from_i(i)*self.chip_factor
                * (self.n_pt - self.start_pt))

    def locate_1d(self, k):
        """Return NM coordinates of sample k

        Parameters
        ----------
        k : int
            The 1D position to move the motor to
        """
        # calculate the horizontal row
        i = int(np.floor(k / (self.M)))
        # calculate the column w/o snake-wrapping
        j = k % (self.M)
        # apply snake-wrapping to odd columns by reversing pathing order 
        if i % 2:
            j = (self.M - j) - 1

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

    def mv(self, *args, timeout=None, wait=True):
        """Performs the standard mv but stops the motors on KeyboardInturrupts
        if waiting for the move to complete.
        """
        try:
            prior = (self.index, self.position)
            self.move(*args, timeout=timeout, wait=wait)
            logger.info('Moved {0} from {1} (Sample {2}) to {3} (Sample {4})'
                        ''.format(self.name, *prior, self.index, self.position))
        except KeyboardInterrupt:
            logger.info('KeyboardInterrupt raised. Stopping palette.')
            self.stop()

    def mvr(self, *args, timeout=None, wait=True):
        all_positions = [self.position, self.index, self.coordinates]
        position = all_positions[len(args)-1]
        return self.mv(*(args + position), timeout=timeout, wait=wait)

    def calibrate(self):
        """Perform the calibration by moving the x, y, and z motors to each of 
        the calibration coordinates.

        The routine launches a shell with a limited number of permitted
        operations in the namespace. To move the motors, they have been made
        avaiable as 'x', 'y', and 'z', aptly named after the coresponding axes.
        To operate the motors, use the following methods and properties:

            `motor.mv()` - Move the desired motor to the inputted absolute
                           position.
            `motor.mvr()` - Move the desired motor using the inputted relative
                            position.
            `motor.position` - Print the current position of the motor.

        Additionally, there are several variables and functions available to 
        assist in the process:

            `move()` - Moves all three motors at the same time. Takes the 
                       desired positions of all three motors as arguments.
            `stop()` - Stops the motion of all the motors.
            `positions()` - Returns the positions of all three motors.
            'h()` - Prints this docstring as a help message.

        To exit the calibration routine, simply raise a KeyboardInterrupt by
        hitting ctrl + c.
        """
        # Gets a nicely formatted docstring
        docstring = getdoc(getattr(self, getframeinfo(currentframe()).function))
        new_calibration = []
        
        def shell():
            # Provide the x, y, and z motors
            move = self.move_3d
            positions = lambda : self.coordinates
            h = lambda : print(docstring)
            x, y, z = self.x_motor, self.y_motor, self.z_motor
            IPython.embed()

        calibration_coordinate_str = ['[0, 0]', 
                                      '[{0}, 0]'.format(self.N-1), 
                                      '[0, {0}]'.format(self.M-1)]

        try:
            print(docstring)
            for i, coordinate in enumerate(calibration_coordinate_str):
                if self.calibrated:
                    logger.info('Moving to the previous {0} calibration '
                                'point... Raise KeyboardInterrupt to stop the '
                                'motion.\n'.format(coordinate))
                    try: 
                        self.move(*self.calibration_coordinates[i], wait=True)
                    except KeyboardInterrupt:
                        logger.info('Stopping motor.')
                        self.stop()

                # Allow the user to perform any new moves
                while True:
                    # Drop into the shell to make the moves
                    logger.info('Please set the center of the {0} sample to be '
                                'in the middle of the beampath. Once complete, '
                                'exit the shell. Enter `h()` for a help string.'
                                '\n'.format(coordinate))
                    shell()

                    current_position_str = 'Use current position {0} for the ' \
                      '{1} calibration point ([y]/n)? '.format(
                          self.coordinates, coordinate)
                    # Get input from the user if this is a good point
                    response = input(current_position_str)
                    while response.lower() not in set(['y', 'n']):
                        # Keep probing until they enter y or n
                        response = input('Invalid input "{0}". ' 
                                         + current_position_str)
                    # If they are happy with the position, move on to the next 
                    # point
                    if response.lower() == 'y':
                        new_calibration.append(self.coordinates)
                        break

            # Always prompt the user about overwriting the calibration
            self.accept_calibration(*new_calibration, confirm_overwrite=True)

        except KeyboardInterrupt:
            logger.info('Exitting calibration routine.')

    @property
    def coordinates(self):
        """Returns the x,y,z coordinates of the palette."""
        return np.array([motor.position for motor in self.motors])

    @property
    def index(self):
        """Returns the i,j palette position based on the current coordinates."""
        self.start_diff = self.coordinates - self.start_pt
        self.raw_index = np.round(
            np.dot(self.start_diff, self.NM_hat) 
            - np.array([self.chip*self.chip_factor*self.length_calibrated, 0]))
        
        # The returned index should never exceed the total number of samples
        return np.minimum(self.raw_index, [self.N-1, self.M-1]).astype(int)

    @property
    def position(self):
        """Returns the current sample number."""
        i, j = self.index
        return i*self.M + (self.M - j - 1 if i%2 else j)

    @property
    def remaining(self):
        """Returns the remaining number of samples."""
        return self.samples - self.position - 1

    def _chip_from_i(self, i):
        """Returns the chip number based on the inputted column."""
        for idx, val in enumerate(self.chip_dims):
            if i < sum(self.chip_dims[:idx+1]):
                return idx

    def _chip_from_xyz(self, coordinates):
        self.start_diff = coordinates - self.start_pt
        self.percent_complete = (np.dot(self.start_diff, self.N_hat)
                            / np.sqrt(np.sum((self.n_pt - self.start_pt)**2)))
        
        for i, val in enumerate(self.chip_dims_percents[::-1]):
            if self.percent_complete > val:
                return min(self.num_chips - i + 1, self.num_chips)
        return 0
        
    @property
    def chip(self):
        """Returns the current chip position."""
        return int(self._chip_from_xyz(self.coordinates))
