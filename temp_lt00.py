#
#   Adding this note on behalf of Sioan. This script is a last minute fix to
#   start and stop the DAQ for the LT00 experiment.
#
#   This code is being included for organization's sake. DO NOT build upon this
#   script.
#


from experiments.lt00.mod_macros import * 
import subprocess

def caput(pv,value):
	
	myString = subprocess.check_output(["caput",pv,str(value)])
	
	return

def test_a(*args,**kwargs):
	test_b(*args,**kwargs)
	return 0

def test_b(*args,**kwargs):
	print(*args)
	print(kwargs.keys())

	return 0

def do_scan(*args,**kwargs):

	caput("ECS:SYS0:2:PLYCTL","1")		
	RE = macro_VT50_smooth_sweep(*args,**kwargs) 
	caput("ECS:SYS0:2:PLYCTL","0")

	#RE = macro_VT50_smooth_sweep((16, 110.5, 0), (15, 119.5, 0), 4, 10.0,min_base=0.3,min_v=0.55) 
	
	#do_scan((15.5, 74.0, 0.0954), (25.0, 84, 0.0954), 4, 10.0,min_base=0.3,min_v=0.55) 
