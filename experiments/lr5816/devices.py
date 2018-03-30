import IPython
import logging
import time
import os
from pathlib import Path
from functools import reduce
from glob import glob
from inspect import getdoc, getframeinfo, currentframe

import json
import numpy as np
from ophyd.device import Device, Component as Cpt
from ophyd.status import Status, wait as status_wait
from pcdsdevices.mv_interface import FltMvInterface
from pcdsdevices.epics_motor import IMS

from sxr.devices import ErrorIMS
from sxr.exceptions import InputError

from .exceptions import InvalidSampleError
from .utils import calibrated

logger = logging.getLogger(__name__)


class McgranePalette(Device, FltMvInterface):
    x_motor = Cpt(ErrorIMS, "SXR:EXP:MMS:08", name='LJE Sample X')
    y_motor = Cpt(IMS, "SXR:EXP:MMS:10", name='LJE Sample Y')
    z_motor = Cpt(IMS, "SXR:EXP:MMS:11", name='LJE Sample Z')
    rot_motor = Cpt(IMS, "SXR:EXP:MMS:12", name='LJE Sample Rotation')

    def __init__(self, N=(24*3 + 8), M=23, chip_spacing=2.4, sample_spacing=1.0,
                 timeout=1, chip_dims=[8,24,24,24], dir_calib=None, *args, 
                 **kwargs):
        """Base device for the mcgrane paddle.

        The Mcgrane palette is a virtual motor consisting of three motors moving
        an array of samples arranged into a 2D grid. The samples are seperated 
        into four groups called chips, indexed from zero to three. Chip 0 
        contains 8x23 samples, while the rest of them contain 24x23 samples, 
        giving a global dimension size of 80x23, and 1840 samples.

        To accurately move to and from samples, a calibration routine was 
        implemented that guides the user through the process of finding the 
        three corners of the palette, which will then be used to interpolate the
        positions of the remaining samples. To run the calibration routine, 
        simply run:

            In [1]: palette.calibrate()

        Once calibrated, it can be saved using the `save_calibration()` method,
        which saves it as a json file in the calibrations folder. If a 
        particular calibration needs to be reloaded, the `load_calibration()` 
        method will load the most recent calibration file by default, but can 
        load by a filename if it's passed.

        Once calibrated, the palette can now perform motions parameterized by 
        the sample number and the sample index, in addition to the motor 
        coordinates, using the `mv()` method. 

        As for readbacks, `.position` returns the sample number, `.index`
        returns the sample index, `.coordinates` returns all the motor
        positions, `.chip` returns the chip number, and `.remaining` returns the
        number of remaining samples in the entire palette.
        """
        super().__init__('', *args, **kwargs)
        self.timeout = timeout
        self.N = N
        self.M = M

        self.chip_dims = chip_dims
        # Make sure the dimensions passed match N
        if self.N != sum(self.chip_dims):
            raise InputError('Inputted differing number of samples in M as the '
                             'number of samples in the chip dimensions. Got '
                             '{0} and {1} (sum {2}).'.format(
                                 self.N, self.chip_dims, sum(self.chip_dims)))
        # Percent of the sample traversed at each chip. This will be used to
        # perform the chip readback
        self.chip_dims_percents = [sum(self.chip_dims[:i+1]) / self.N
                                   for i in range(len(self.chip_dims))]
        # Sample spacings
        self.chip_spacing = chip_spacing
        self.sample_spacing = sample_spacing
        # Number of chips, zero indexed
        self.num_chips = len(self.chip_dims) - 1
        # Calculate the length of the palette in mm
        self.length = ((self.N - self.num_chips - 1)*self.sample_spacing 
                       + self.num_chips * self.chip_spacing)
        # Percent of each extra chip spacing of the total length
        self.chip_factor = (self.chip_spacing - self.sample_spacing)/self.length

        # Total number of samples
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
        # Internal indicator for whether there is a calibration
        self.calibrated = False

        # Experiment paths
        self.dir_sxropr = Path('/reg/neh/operator/sxropr')
        self.dir_experiment = self.dir_sxropr / 'experiments/sxrlr5816'
        self.dir_calib = dir_calib or self.dir_experiment / 'calibrations'

    @calibrated
    def save_calibration(self, name=None):
        """Save the current calibration to the calibration folder.

        If there is a calibration being used, this method saves it in a json
        file in the calibration folder, using the inputted name or a default
        one. It will raise an error if this method is called when the motor is
        not calibrated.

        Parameters
        ----------
        name : str, optional
            Filename to save the calibration as

        Raises
        ------
        NotCalibratedError
            If this method is called but the motor is not using a calibration
        """ 
        # Create the calibration file
        name = name or 'calibration_{0}.json'.format(
            time.strftime("%Y%m%d_%H%M%S"))
        calib_path = self.dir_calib / name
        # Make the file if it doesn't exist 
        if not calib_path.exists():
            calib_path.touch()
            calib_path.chmod(0o777)
        
        # Write the calibration coordinates
        with open(str(calib_path), 'w') as calib:
            json.dump([list(pt) for pt in self.calibration_coordinates], calib)
        logger.info('Saved calibration as "{0}"'.format(name))

    def load_calibration(self, name=None, confirm_overwrite=True):
        """Load a palette calibration from a file.
        
        From the calibration directory, load a calibration json file to use for
        sample motion. If no name is inputted, the most recently modified file
        is loaded.

        Parameters
        ----------
        name : str, optional
            Name of the desird calibration file

        confirm_overwrite : bool, optional
            Prompt the user to confirm they want to overwrite the calibration
        """
        if not name:
            # Grab the most recent file if a name wasn't passed
            calib_path = Path(max(glob(str(self.dir_calib / '*')), 
                                  key=os.path.getctime))
        else:
            # Make sure the file exists before proceeding
            calib_path = self.dir_calib / name
            if not calib_path.exists():
                raise FileNotFoundError('Calibration "{0}" does not exist!'
                                        ''.format(str(calib_path)))

        # Load the calibration file
        logger.info('Loading calibration from "{0}"'.format(calib_path.name))
        with open(str(calib_path), 'r') as calib:
            calibration_coordinates = [np.array(pt) for pt in json.load(calib)]

        # Accept the calibration
        self._accept_calibration(*calibration_coordinates,
                                 confirm_overwrite=confirm_overwrite)

    def _accept_calibration(self, start_pt, n_pt, m_pt, 
                            confirm_overwrite=False):
        """Performs the internal calibration of the palette.

        Takes in three coordinates, representing the [0,0], [N,0], and [0,M]
        indices of the sample, in that order. The coordinates passed should 
        correspond to the positions of the x, y, and z motors of the palette. 
        The positions of all the other samples are then interpolated from these 
        points, compensating for the chip spacings.

        Parameters
        ---------- 
        start_pt : np.array or pd.Series
            3-length iterable (x,y,z) specifying spatial coordinate if the [0,0]
            sample

        n_pt : np.array or pd.Series
            3-length iterable (x,y,z) specifying spatial coordinate if the [N,0]
            sample
        
        m_pt : np.array or pd.Series
            3-length iterable (x,y,z) specifying spatial coordinate if the [0,M]
            sample
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

        # Define the N sample spacing by finding the vector between the [0,0]
        # point and the [N,0] point, then scale it by the theoretical distance 
        # betwen them if the chip spacing was the same length as the sample
        # spacing, and then divide by the number of samples in N
        self.N_hat = (((self.n_pt - self.start_pt) 
                       * (1 - self.num_chips*self.chip_factor))
                      / (self.N - 1))

        # Define the M sample spacing by finding the vector between teh [0,0]
        # point and the [0,M] point and dividing by the number of samples in M.
        # There is no scaling here because there is no extra chip spacing in M.
        self.M_hat = (self.m_pt - self.start_pt) / (self.M - 1)

        # Put both N_hat and M_hat in an array for future use
        self.NM_hat = np.concatenate((self.N_hat.reshape(len(self.motors), 1), 
                                      self.M_hat.reshape(len(self.motors), 1)), 
                                     axis=1)

        # The actual measured distance between the [0,0] and [N,0] samples
        self.length_calibrated = np.sqrt(np.sum((self.n_pt - self.start_pt)**2))
        logger.info('Successfully calibrated "{0}"'.format(self.name))
        # Always save the calibration
        self.save_calibration()

    def locate_2d(self, i, j):
        """Return (x,y,z) coordinates of sample (i,j).

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

    @calibrated
    def locate_1d(self, k):
        """Return (i,j) coordinates of sample k.

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
        """Move to given (x,y,z) coordinate."""
        # Move each motor to the corresponding position and collect the status
        # objects in a list
        status_list = [motor.move(val, timeout=timeout, wait=False)
                       for motor, val in zip(self.motors, (x, y, z))]

        # Reduce the list to a single AndStatus
        status = reduce(lambda s1, s2: s1 & s2, status_list)
        
        if wait:
            status_wait(status)
        return status

    @calibrated
    def move_2d(self, i ,j, *, timeout=None, wait=False):
        """Move to point (i,j) in NM space."""
        if not 0 <= i < self.N or not 0 <= j < self.M:
            raise InvalidSampleError('Invalid index inputted. Minimum value is '
                                     '[0,0] and maximum is [{0},{1}], but got '
                                     '[{2},{3}]'.format(self.N-1, self.M-1, 
                                                        i, j))
        return self.move_3d(*self.locate_2d(i, j), timeout=timeout, wait=wait)

    @calibrated
    def move_1d(self, k, *, timeout=None, wait=False):
        """Move to point K in the sampling path space."""
        if not 0 <= k < self.samples:
            raise InvalidSampleError('Invalid sample number inputted. Minimum '
                                     'value is 0 and maximum is {0}, but got '
                                     '{1}'.format(self.samples-1, k))
        return self.move_2d(*self.locate_1d(k), timeout=timeout, wait=wait)
            
    def move(self, *args, timeout=None, wait=False):
        """Move to the sample number (k), sample index (i,j), or motor 
        coordinate (x,y,z) position depending on the number of arguments passed.

        This method sends the passed arguments to one of the three move methods,
        assuming that the number of arguments corresponds to the type of motion
        desired.

        Parameters
        ----------
        *args : ints or floats
            Position to move the palette to. One, two, or three arguments 
            correspond to absolute motion to sample number, sample index, or
            motor positions respectively.

        timeout : float, optional
            Timeout for the motion
            
        wait : bool, optional
            Wait for the motion to complete
        """
        num_args = len(args)
        # Make sure we get the right number of arguments
        if num_args > 3:
            raise ValueError('Cannot pass more than three inputs to move '
                             'command, got {0}'.format(len(args)))

        # Select the move function based on the number of arguments passed
        return self.move_funcs[num_args-1](*args, timeout=timeout, wait=wait)

    def stop(self):
        """Stop all the motors."""
        for motor in self.motors:
            motor.stop()

    def set(self, *args, **kwargs):
        """Add compatibility with the abs_set plan in bluesky."""
        return self.move(*args, **kwargs)

    def mv(self, *args, timeout=None, wait=True):
        """Move to the sample number (k), sample index (i,j), or motor 
        coordinate (x,y,z) position depending on the number of arguments passed.

        To perform a move by sample number, simply pass the desired sample 
        number into the move method like so:

            In [1]: palette.mv(22)

        This will perform an absolute move to sample number 22. Please note that
        the samples are indexed in a snake-unravel. For example, moving from 
        sample 22 to 23 then 24 will move the palette from sample [0, 22] to 
        [1, 22] then [1, 21] in array notation.

        If motions in array notation are desired, the indices are passed rather
        than the sample number. From the previous example, to move to [1, 21]:

            In [2]: palette.mv(1, 21)

        Lastly, if moving to exact motor positions is desired, passing three
        arguments will move each of the motors to the inputted position. For
        example:
        
            In [3]: palette.mv(5, 10, 15)

        Will move the x motor to 5, the y motor to 10, and the z motor to 15. 

        By default, the shell will wait for the motion to complete before 
        allowing new motions to be requested. During this time, if a 
        `KeyboardInterrupt` is raised, the motion will stop.

        Parameters
        ----------
        *args : ints or floats
            Position to move the palette to. One, two, or three arguments 
            correspond to absolute motion to sample number, sample index, or
            motor positions respectively

        timeout : float, optional
            Amount of time to wait for moves to complete

        wait : bool, optional
            Wait for the motion to complete
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
        """Move relative to the current position in the appropriate manner
        depending on the number of arguments passed.
        
        See `mv()` documentation for more details.

        Parameters
        ----------
        *args : ints or floats
            Realtive position to move the palette by. One, two, or three 
            arguments correspond to relative motion in sample number, sample 
            index, or motor positions respectively.
        """
        all_positions = [self.position, self.index, self.coordinates]
        position = all_positions[len(args)-1]
        return self.mv(*(args + position), timeout=timeout, wait=wait)

    def calibrate(self):
        """Perform the calibration by moving the x, y, and z motors to each of 
        the calibration coordinates.

        The routine launches a shell with a limited number of permitted
        operations in the namespace. To move the motors, they have been made
        avaiable as `x`, `y`, and `z`, aptly named after the coresponding axes.
        The motors feature their full functionality, but the following methods 
        properties should be particularly useful:

            `motor.mv()` - Move the desired motor to the inputted absolute
                           position.
            `motor.mvr()` - Move the desired motor using the inputted relative
                            position.
            `motor.position` - Print the current position of the motor.

        Additionally, functions available to assist in the process:

            `move()` - Moves all three motors at the same time. Takes the 
                       desired positions of all three motors as arguments.
            `stop()` - Stops the motion of all the motors.
            `positions()` - Returns the positions of all three motors.
            'h()` - Prints this docstring as a help message.

        To end the calibration routine, simply raise a KeyboardInterrupt by
        hitting ctrl + c.
        """
        # Gets a nicely formatted docstring
        docstring = getdoc(getattr(self, getframeinfo(currentframe()).function))
        new_calibration = []
        
        def shell():
            # Provide the functions outlined in the docstring
            move = lambda x, y, z, *a, **kw: self.mv(x, y, z, *a, **kw)
            stop = self.stop
            positions = lambda : self.coordinates
            h = lambda : print(docstring)
            # Make the motors more accessible
            x, y, z = self.x_motor, self.y_motor, self.z_motor
            # Embed the shell
            IPython.embed()

        # This will make things loopable
        calibration_coordinate_str = ['[0, 0]', 
                                      '[{0}, 0]'.format(self.N-1), 
                                      '[0, {0}]'.format(self.M-1)]

        try:
            # Show the docstring the first time we start this routine
            print(docstring)
            # Begin going through each of the calibration coordinates
            for i, coordinate in enumerate(calibration_coordinate_str):
                # If there is an existing calibration, move there as a first
                # check
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
                                'exit the shell. For a help string, enter '
                                '`h()`.\n'.format(coordinate))
                    # Launch the shell
                    shell()

                    # User exited, so confirm with them that we are in the right
                    # position
                    current_position_str = 'Use current position {0} in ' \
                      '(x,y,z) for the {1} calibration point ([y]/n)? '.format(
                          list(self.coordinates), coordinate)
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
            self._accept_calibration(*new_calibration, confirm_overwrite=True)

        except KeyboardInterrupt:
            logger.info('Exitting calibration routine.')

    @property
    def coordinates(self):
        """Returns the x,y,z coordinates of the palette."""
        return np.array([motor.position for motor in self.motors])

    @property
    @calibrated
    def index(self):
        """Returns the (i,j) palette position based on the current coordinates.
        
        The index ranges from (0,0) to (N-1,M-1) and is calculated based on the
        current coordinates.

        Returns
        -------
        index : array
            An array of with the i,j indices of the sample.
        """
        self.start_diff = self.coordinates - self.start_pt
        self.raw_index = np.round(
            np.dot(self.start_diff, self.NM_hat) 
            - np.array([self.chip*self.chip_factor*self.length_calibrated, 0]))
        
        # The returned index should never exceed the total number of samples
        return np.minimum(self.raw_index, [self.N-1, self.M-1]).astype(int)

    @property
    @calibrated
    def position(self):
        """Returns the current sample number.
        
        Sample number ranges from 0 to `.samples - 1` is calculated in an
        unraveled-snaking fashion.

        Returns
        -------
        position : int
            The sample position from 0 to `.samples - 1`
        """
        i, j = self.index
        return i*self.M + (self.M - j - 1 if i%2 else j)

    @property
    @calibrated
    def remaining(self):
        """Returns the remaining number of samples.
        
        Based on the current position, this calculates the number of samples
        remaining in the palette. Simply performs the calculation of
        `.samples - .position - 1`.

        Returns
        -------
        remaining : int
            Number of samples left in the palette.
        """
        return int(self.samples - self.position - 1)

    @calibrated
    def _chip_from_i(self, i):
        """Returns the chip number based on the inputted column."""
        for idx, val in enumerate(self.chip_dims):
            if i < sum(self.chip_dims[:idx+1]):
                return idx

    @calibrated
    def _chip_from_xyz(self, coordinates):
        """Returns the chip number based on the inputted coordinates."""
        self.start_diff = coordinates - self.start_pt
        self.percent_complete = (np.dot(self.start_diff, self.N_hat)
                            / np.sqrt(np.sum((self.n_pt - self.start_pt)**2)))
        
        for i, val in enumerate(self.chip_dims_percents[::-1]):
            if self.percent_complete > val:
                return min(self.num_chips - i + 1, self.num_chips)
        return 0
        
    @property
    @calibrated
    def chip(self):
        """Returns the current chip position.
        
        Groups of samples are separated into chips, and the returned value 
        ranges from 0 to 3 depending on the current position. Chip 0 contains
        8 samples, while all proceeding chips contains 24 samples.

        Returns
        -------
        chip : int
            Chip number ranging from 0 to 3 depending on the current position.
        """
        return int(self._chip_from_xyz(self.coordinates))

    @property
    def settle_time(self):
        """Returns the settle time of the x motor."""
        return self.x_motor.settle_time

    @settle_time.setter
    def settle_time(self, value):
        """Sets the settle time for all the motors."""
        for motor in self.motors:
            motor.settle_time = value
