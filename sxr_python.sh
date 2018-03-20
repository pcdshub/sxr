#!/bin/bash

# Get the directory of this script resolving soft links
FILE=`readlink -f $0`
DIRPATH=`dirname $FILE`

source $DIRPATH/sxrpy_env.sh

# Start the ipython shell using the snd environment
ipython -i $DIRPATH/sxr_python.py
