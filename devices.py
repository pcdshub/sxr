import logging
import numpy as np

from ophyd.device import Device, Component as Cpt, FormattedComponent as FCpt
from ophyd.signal import EpicsSignal, EpicsSignalRO, Signal
from ophyd import PVPositioner
from ophyd.status import wait as status_wait

from pcdsdevices.epics_motor import EpicsMotor, IMS
from pcdsdevices.mv_interface import FltMvInterface

from utils import retry
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
        """
        status = self.state_control.set(0, timeout=self.timeout)
        if wait:
            status_wait(status)        


class ConsolidatedSamplePalette(Device):
    '''
    
    '''
    # x_motor = Cpt(IMS,"{self._xmotor_prefix}:{self._xmotor_suffix}")
    # y_motor = Cpt(IMS,"{self._ymotor_prefix}:{self._ymotor_suffix}")
    # z_motor = Cpt(IMS,"{self._zmotor_prefix}:{self._zmotor_suffix}")


    def __init__(self, prefix, N_dim=1, M_dim=1, timeout=1, motor_timeout=5,
                samples=None, *args, **kwargs):
        '''
        N_dim : int
            specify the number of samples in the N direction

        M_dim : int
            specify the number of samples in the M direction
        '''
        
        self._xmotor_prefix = None
        self._ymotor_prefix = None
        self._zmotor_prefix = None
        self._xmotor_suffix = None
        self._ymotor_suffix = None        
        self._zmotor_suffix = None       

        super().__init__(prefix, *args, **kwargs)
        self.timeout = timeout
        self.motor_timeout = motor_timeout

        self.calibrated = False

        # How many samples are there in the N and M directions
        self.N_dim = N_dim
        self.M_dim = M_dim

        # if the number of samples on the pallete is not given, presume full
        # matrix allotment 
        if samples == None:
            self.samples = self.N_dim * self.M_dim
        else:
            self.samples = samples

    def calibrate_from_file(self,file_name):
        '''
        Set calibration using a CalibFile or .csv saved from a CalibFile

        Parameters
        ----------
        file_name : str or CalibFile
            Either pass the name of the .csv saved from a CalibFile or pass the
            CalibFile direcly.
        '''
        data_file = CalibFile(file_name)
        self.accept_calibration(
            N = data_file.N,
            M = data_file.M,
            start_pt = data_file.start_pt,
            n_pt = data_file.n_pt,
            m_pt = data_file.m_pt
        )

    def accept_calibration(self,N,M,start_pt,n_pt,m_pt):
        '''
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
        '''
        if self.calibrated:
            logger.warning("WARNING: Overriding existing calibration!")
        
        self.calibrated = True

        # save the origin point in XYZ space
        self.start_pt = start_pt

        # Define unit vectors on the NM plane in XYZ space
        self.N_hat = (n_pt - self.start_pt) / N
        self.M_hat = (m_pt - self.start_pt) / M

    def locate_2d(self, i, j):
        '''
        return XYZ coordinates of sample i,j

        i : int

        j : int
        '''
        target_pt = self.start_pt + i * self.N_hat + j * self.M_hat
        return target_pt

    def locate_1d(self, k):
        '''
        return NM coordinates of sample k

        k : int
        '''

        # calculate the horizontal row
        j = int(np.floor(k/self.N_dim))

        # calculate the column w/o snake-wrapping
        i = k % self.N_dim

        # apply snake-wrapping to odd columns by reversing pathing order 
        if j % 2 :
            i = (self.N_dim - i) - 1  

        return np.array([i,j])

    def move_to_sample_2d(self, i ,j, timeout=None, wait=True):
        '''
        Move to point IJ in NM space.
        
        i : int
        
        j : int

        timeout : int

        wait : bool
        '''
        if timeout == None:
            timeout = self.timeout

        XYZ_target = self.locate_2d(i,j)
        status = self.mv(*XYZ_target,timeout=timeout,wait=wait)
        return status

    def move_to_sample_1d(self, k, timeout=None, wait=True):
        '''
        Move to point K in the sampling path space
        
        k : int

        timeout : int

        wait : bool
        '''
        if timeout == None:
            timeout = self.timeout

        IJ_target = self.locate_1d(k)
        status = self.move_to_sample_2d(*IJ_target,timeout=timeout,wait=wait)
        return status

    def move(self, k, timeout=None, wait=True):
        '''
        Wrap move_to_sample_1d under a common name.
        
        k : int

        timeout : int

        wait : bool
        '''
        if timeout == None:
            timeout = self.timeout

        status = self.move_to_sample_1d(self, k, timeout=timeout,wait=wait)
        return status

    def set(self, k, timeout=None, wait=True):
        '''
        Add compatibility with the abs_set plan in bluesky
        '''
        if timeout == None:
            timeout = self.timeout
        return self.move(k,timeout=timeout,wait=wait) 
    
    def mv(self, x, y, z, timeout=None,wait=True):
        '''
        Move to given XYZ coordinate

        x : float

        y : float

        z : float 

        timeout : int

        wait : bool
        '''
        if timeout == None:
            timeout = self.timeout

        status_x = self.x_motor.move(x, timeout=timeout)
        status_y = self.y_motor.move(y, timeout=timeout)
        status_z = self.z_motor.move(z, timeout=timeout)

        all_status = status_x & status_y & status_z

        if wait:
            try:
                status_wait(all_status)
            except KeyboardInterrupt:
                self.x_motor.stop()
                self.y_motor.stop()
                self.z_motor.stop()
                raise

        return all_status
            
        

