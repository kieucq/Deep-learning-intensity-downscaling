# DESCRIPTION: 
#       This script is to read a post-processed data in the NETCDF format centered
#       on each TC from the previous script MERRA2tc_domain.py, and then seclect a specific
#       group of variables before writing them out in the Numpy array format. This latter
#       format will help the DL model to read in and train more efficiently without the 
#       memory issues, similar to the CNN-agumentation model system.
#
#       This script initializes all necessary libraries for data handling and defines a 
#       function to process atmospheric data from NetCDF files, structuring it into 
#       NumPy arrays suitable for analysis. It ensures efficient management 
#       of large datasets with an emphasis on maintaining data integrity through robust 
#       error handling and validation steps. The function supports custom configurations 
#       for selective data extraction and transformation, tailored for climate research.
#
# DEPENDENCIES:
#       - xarray: Utilized for data manipulation and accessing NetCDF file content.
#       - matplotlib: Incorporated for plotting capabilities.
#       - numpy: Essential for numerical computations and data structuring.
#       - glob: Facilitates file path handling for navigating directory structures.
#       - npy_append_array: efficient append operations to NumPy arrays, optimizing memory.
#       - math: Provides support for basic mathematical operations.
#
# USAGE: Edit all required input/output location and parameters right below before running 
#
# NOTE: This script selects specific level atmospheric data from the MERRA2 dataset,
#       which may also contain NaN. To add additional data layers, see variable
#       data_array_x for details.
#
# HIST: - May 14, 2024: created by Khanh Luong
#       - May 16, 2024: clean up and added more note by CK
#       - Oct 19, 2024: added a list of vars to be processed by CK
#
# AUTH: Minh Khanh Luong @ Indiana University Bloomington (email: kmluong@iu.edu)
#==========================================================================================
print('Initiating.', flush=True)
import xarray as xr
import os
import matplotlib.pyplot as plt
import numpy as np
import glob
from npy_append_array import NpyAppendArray
import math
from datetime import datetime
#
# Edit the input data path and parameters before running this script.
# Note that all output will be stored under the same exp name.
#
inputpath='/N/project/Typhoon-deep-learning/output/TC_domain/'
workdir='/N/project/Typhoon-deep-learning/output/'
windowsize=[19,19]
force_rewrite = True    # overwrite previous dataset option
print('Initiation completed.', flush=True)
list_vars = [('U', 850), ('V', 850), ('T', 850), ('RH', 850), 
             ('U', 950), ('V', 950), ('T', 950), ('RH', 950),
	     ('U', 750), ('V', 750), ('T', 750), ('RH', 750),
             ('SLP', 750)]
var_num = len(list_vars)
#####################################################################################
# DO NOT EDIT BELOW UNLESS YOU WANT TO MODIFY THE SCRIPT
#####################################################################################
def convert_date_to_cyclic(date_str):
    """
    Convert a date in 'YYYYMMDD' format to a cyclic representation using sine and cosine.
    
    Args:
    date_str (str): Date string in 'YYYYMMDD' format.
    
    Returns:
    tuple: A tuple containing the sine and cosine representations of the day of the year.
    """
    # Parse the date string to datetime object
    date = datetime.strptime(date_str, "%Y%m%d")
    
    # Calculate the day of the year
    day_of_year = date.timetuple().tm_yday
    
    # Number of days in the year (handling leap years)
    days_in_year = 366 if date.year % 4 == 0 and (date.year % 100 != 0 or date.year % 400 == 0) else 365
    
    # Convert to cyclic
    sin_component = np.sin(2 * np.pi * day_of_year / days_in_year)
    cos_component = np.cos(2 * np.pi * day_of_year / days_in_year)
    
    return sin_component, cos_component

def cold_delete(filepath):
    try:
        os.remove(filepath)
        print(f"File {filepath} has been successfully removed.")
    except FileNotFoundError:
        print("The file does not exist.")
    except PermissionError:
        print("You do not have permission to remove the file.")
    except Exception as e:
        print(f"An error occurred: {e}")

def get_file_year_and_month(filename, id1):
    position = filename.find(id1)
    if position != -1:
        filedate = filename[position + len(id1): position + len(id1) + 8]
        #print(filedate)
        year = int(filedate[:4])
        month = int(filedate[4:6])
        return year, month

def check_date_within_range(date_str):
    # Convert string to date object
    date = datetime.strptime(date_str, '%Y%m%d')
    
    # Create start and end date objects for May 1st and November 30th of the same year
    start_date = datetime(year=date.year, month=5, day=1)
    end_date = datetime(year=date.year, month=11, day=30)
    
    # Check if the date falls within the range
    return start_date <= date <= end_date

def dumping_data(root='', outdir='', outname=['features', 'labels'],
                 regionize=True, omit_percent=5, windowsize=[18,18], cold_start=False):
    """
    Select and convert data from NetCDF files to NumPy arrays organized by months.

    Parameters:
    - root (str): The root directory containing NetCDF files.
    - outdir (str): The output directory for the NumPy arrays.
    - outname (list): List containing the output names for features and labels.
    - regionize (bool): If True, output data for each basin separately, 
                    with output files named outname{basin}.npy
    - omit_percent (float, percentage): Defines the upper limit of acceptable NaN (missing data) 
                    percentage in the 850mb band.
    - windowsize (list of floats): Specifies the size of the rectangular domain for Tropical Cyclone 
                    data extraction in degrees. The function selects a domain with dimensions closest 
                    to, but not smaller than, the specified window size.

    Returns:
    None
    """
    i = 0
    omit = 0
    if not os.path.exists(outdir):
        os.makedirs(outdir)

    for filename in glob.iglob(root + '*/**/*.nc', recursive=True):
        id1 = (str(windowsize[0]) + 'x' + str(windowsize[1]))
        if id1 in filename:
            position = filename.find(id1)
        else:
            continue
        filedate = filename[position + len(id1): position + len(id1) + 8]  # Adjust to capture YYYYMM
        month = filedate[-4:-2]  # Extract the month from filedate
        if cold_start and i == 0:
            # Clear previous data if cold start is enabled
            for m in range(1, 13):
                month_str = f"{m:02d}"
                cold_delete(outdir + outname[0] + month_str + '.npy')
                cold_delete(outdir + outname[1] + month_str + '.npy')
                cold_delete(outdir + outname[2] + month_str + '.npy')
        data = xr.open_dataset(filename)
        #
        # make loop below with a list of var/level, with the list given from namelist
        #
        data_array_x = np.array(data[['U', 'V', 'T', 'RH']].sel(lev=850).to_array())
        data_array_x = np.append(data_array_x, np.array(data[['U', 'V', 'T', 'RH']].sel(lev=950).to_array()), axis=0)
        data_array_x = np.append(data_array_x, np.array(data[['U', 'V', 'T', 'RH', 'SLP']].sel(lev=750).to_array()), axis=0)
        """
        for i,(var,vlev) in enumerate(list_vars):
            print(f"Extract variable {var[0]} at level {var[1]}")
            if i == 0:
                data_array_x = np.array(data[[var]].sel(lev=vlev))
            else:
                data_array_x = np.append(data_array_x, np.array(data[[var]].sel(lev=vlev)), axis=0)
        """ 
        if np.sum(np.isnan(data_array_x[0:4])) / 4 > omit_percent / 100 * math.prod(data_array_x[0].shape):
            i += 1
            omit += 1
            continue
        sin_day, cos_day = convert_date_to_cyclic(filedate)
        data_array_x = data_array_x.reshape([1, data_array_x.shape[0], data_array_x.shape[1], data_array_x.shape[2]])
        data_array_z = np.array([sin_day, cos_day, data.CLAT, data.CLON]) #day in year to sincos, central lat lon
        data_array_y = np.array([data.VMAX, data.PMIN, data.RMW])  # knots, mb, nmile
        data_array_z = data_array_z.reshape([1, data_array_z.shape[0]])
        data_array_y = data_array_y.reshape([1, data_array_y.shape[0]])

        with NpyAppendArray(outdir + outname[0] + month + '.npy') as npaax:
            npaax.append(data_array_x)
        with NpyAppendArray(outdir + outname[1] + month + '.npy') as npaay:
            npaay.append(data_array_y)
        with NpyAppendArray(outdir + outname[2] + month + '.npy') as npaay:
            npaay.append(data_array_z)
        i += 1
        if i % 1000 == 0:
            print(str(i) + ' dataset processed.', flush=True)
            print(str(omit) + ' dataset omitted due to NaNs.', flush=True)

    print('Total ' + str(i) + ' dataset processed.', flush=True)
    print('With ' + str(omit) + ' dataset omitted due to NaNs.', flush=True)

# MAIN CALL:
outputpath = workdir+'/exp_'+str(var_num)+'features_'+str(windowsize[0])+'x'+str(windowsize[1])+'/data/' 
if not os.path.exists(inputpath):
    print("Must have the input data from Step 1 by now....exit", inputpath)
    exit

second_check = False
try:
    for entry in os.scandir(outputpath):
        if entry.is_file():
            print(f"Output directory '{outputpath}' is not empty. Data is processed before.", flush=True)
            second_check = True
            break
except:
    second_check = False
if second_check:
    if force_rewrite:
        print('Force rewrite is True, rewriting the whole dataset.', flush=True)
    else:
        print('Will use the processed dataset, terminating this step.', flush=True)
        exit()
outname=['CNNfeatures'+str(var_num)+'_'+str(windowsize[0])+'x'+str(windowsize[1]),
         'CNNlabels'+str(var_num)+'_'+str(windowsize[0])+'x'+str(windowsize[1]),
         'CNNspace_time_info'+str(var_num)+'_'+str(windowsize[0])+'x'+str(windowsize[1])]
dumping_data(root=inputpath, outdir=outputpath, windowsize=windowsize, 
             outname=outname, cold_start = force_rewrite)
