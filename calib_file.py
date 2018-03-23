import numpy as np
import pandas as pd

class CalibFile:
    '''
    CalibFile stores calibration points.

    The data is stored in a pandas data frame for easy r/w. 90% of this class
    is just properties so the rows and columns can be r/w'ed in python as if 
    they were just normal variables.

    Properties
    ----------

    start_pt : pd.Series
        Vector storing the location of the first calibration point. Can be set
        with np array or pd series indexed ['x','y','z'].

    n_pt : pd.Series
        Vector storing the location of the calibration point on the N axis. Can
        be set with np array or pd series indexed ['x','y','z'].


    m_pt : pd.Series
        Vector storing the location of the calibration point on the M axis. Can
        be set with np array or pd series indexed ['x','y','z'].


    N : int
        number of samples traversed from start_pt to reach n_pt

    M : int
        number of samples traversed from start_pt to reach m_pt

    '''
    def __init__(self,from_file_name=None):
        '''
        Create an empty calibration instance or construct one from the given
        file.
        '''
        self.axis = ['x','y','z']
        if from_file_name != None:
            self.data = self._read_from_file(from_file_name)
        else:
            start_pt_row = pd.Series([np.nan],index=self.axis)
            n_pt_row = pd.Series([np.nan],index=self.axis + ['n'])
            m_pt_row = pd.Series([np.nan],index=self.axis + ['m'])
            self.data = pd.DataFrame(
                [start_pt_row,n_pt_row,m_pt_row],
                index = ['start_pt','n_pt','m_pt']
            )
    
    def save(self,file_name):
        '''
        Store this calibration as a file
        '''
        self.data.to_csv(file_name)

    def _read_from_file(self,file_name):
        data = pd.read_csv(file_name,header=0,index_col=0)
        return data

    def load_file(self,file_name):
        self.data = self._read_from_file(file_name)

    def set_vector(self,row,vector):
        self.data.loc[row,self.axis] = pd.Series(
            vector,index=self.axis
        )
    
    def get_vector(self,row):
        return self.data.loc[row,self.axis]

    def _get_N(self):
        return self.data.loc['n_pt','n']
        
    def _set_N(self,value):
        self.data.loc['n_pt','n'] = value
    
    N = property(_get_N,_set_N)
    
    def _get_M(self):
        return self.data.loc['m_pt','m']
        
    def _set_M(self,value):
        self.data.loc['m_pt','m'] = value

    M = property(_get_M,_set_M)
    
    def _get_start_pt(self):
        return self.get_vector('start_pt')

    def _set_start_pt(self,vector):
        self.set_vector('start_pt',vector)

    start_pt = property(_get_start_pt, _set_start_pt)
    
    def _get_n_pt(self):
        return self.get_vector('n_pt')

    def _set_n_pt(self,vector):
        self.set_vector('n_pt',vector)
    
    n_pt = property(_get_n_pt, _set_n_pt)
    
    def _get_m_pt(self):
        return self.get_vector('m_pt')

    def _set_m_pt(self,vector):
        self.set_vector('m_pt',vector)
    
    m_pt = property(_get_m_pt, _set_m_pt)
