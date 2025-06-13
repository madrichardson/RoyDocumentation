"""
Overview
--------
Compute multi-day (m-day) chlorophyll-a composites for the MODIS “MB” (Pacific Ocean)
dataset by averaging daily 1-day NetCDF files over a specified range of days.

Usage
-----
::
  
      python CompMBChla.py <dataDir> <workDir> <endYear> <endDoy> <interval>

Where:

- ``dataDir``

  Directory containing daily 1-day NetCDFs named ``MB<YYYY><DDD>*chla.nc``.

- ``workDir``

  Temporary working directory for intermediate files.

- ``endYear``

  Four-digit year of the last day in the composite (e.g., ``2025``).

- ``endDoy``

  Three-digit day-of-year of the last day (e.g., ``082``).

- ``interval``

  Number of days to include (e.g., `3`, `5`, `8`, `14`).


Description
-----------
1. **Parse arguments & compute interval**

  - Read ``dataDir``, ``workDir``, ``endYear``, ``endDoy``, and ``interval`` from ``sys.argv``.

  - Compute ``startDoy = endDoy - interval + 1``.

2. **Compute start/end dates**

  - Convert ``endYear`` + ``endDoy`` to a ``datetime``.

  - Derive ``startDoy`` date by subtracting ``interval - 1`` days.

3. **Initialize accumulators**

  - Change to ``workDir`` and clear any old files.

  - Preallocate two arrays of shape (4401x8001):

     - ``mean`` (float32) for the running sum of chlorophyll-a.

     - ``num``  (int32) for the count of valid observations.

4. **Gather daily files**

  - Build a list of all ``MB<YYYY><DDD>*chla.nc`` files from ``startDoy`` to ``endDoy``.

  - Handle wrap-around year boundaries by splitting into two ranges if needed.

5. **Accumulate daily Chla**
  
  - For each file:

     - Open with ``Dataset()``, read the 4-D variable ``MBchla``, squeeze to 2-D.

     - Update ``mean`` and ``num`` via ``meanVar(mean, num, data2d)``.

6. **Mask & finalize**

  - Create a masked array where ``num == 0`` (no observations), fill value ``-9999999.``.

7. **Write & deploy** 

  - Change to ``workDir``.
  
  - Construct output filename ``MB<startYear><startDDD>_<endYear><endDDD>_chla.nc``.
  
  - Call ``makeNetcdf(mean, num, interval, outFile, filesUsed, workDir)`` to write the CF-compliant NetCDF.
  
  - Transfer it to ``/MB/chla/`` on the server via ``send_to_servers()``.

Dependencies
------------
- Python 3.x

- Standard library: ``os``, ``sys``, ``glob``, ``itertools.chain``, ``datetime``, ``timedelta``

- Third-party: ``numpy``, ``numpy.ma``, ``netCDF4``

- Custom roylib functions:

  - ``isleap(year)``

  - ``meanVar(mean, num, array)``

  - ``makeNetcdf(mean, num, interval, outFile, filesUsed, workDir)``

  - ``send_to_servers(ncFile, remote_dir, interval_flag)``

Directory Structure
-------------------
- **Input Directory** (``dataDir``):

  ``MB<YYYY><DDD>*chla.nc`` daily files.

- **Working Directory** (``workDir``):

  Temporary staging and output location.

- **Output location**:

  Copied to ``/MB/chla/`` with the interval flag.

Usage Example
-------------
Create a 5-day chlorophyll composite DOY 001-005 of 2025
::
 
   python CompMBChla.py /data/modisgf/1day/ /tmp/mw_work/ 2025 005 5

This averages files for DOY 001…005, writes ``MB2025001_2025005_chla.nc`` in /tmp/mw_work/, and uploads to /MB/chla/.
"""
from __future__ import print_function
from builtins import str
from builtins import range

if __name__ == "__main__":
    from datetime import datetime, timedelta
    import glob
    from itertools import chain
    from netCDF4 import Dataset
    import numpy as np
    import numpy.ma as ma
    import os
    import sys

    # Ensure 'roylib' is on the import path
    sys.path.append('/home/cwatch/pythonLibs')
    from roylib import *

    dataDir = sys.argv[1]

    # Temporary working directory
    workDir = sys.argv[2]

    # Composite end year (YYYY)
    endyearC = sys.argv[3]

    # Composite end day-of-year (DDD)
    endDoyC = sys.argv[4]
    endDoyC = endDoyC.rjust(3, '0')
    endDoy = int(endDoyC)

    # Composite length
    intervalC = sys.argv[5]
    interval = int(intervalC)

    # Convert end Doy to calendar date
    myDateEnd = datetime(int(endyearC), 1, 1) + timedelta(int(endDoyC)-1)

    # Start date = end date minus (interval-1) days
    myDateStart = myDateEnd + timedelta(days=-(interval - 1))

    # Zero-padded start Doy and year
    startDoyC = myDateStart.strftime("%j").zfill(3)
    startDoy = int(startDoyC)
    startYearC = str(myDateStart.year)

    # Prepare output directory
    outDir = '/ERDData1/modisa/data/modisgf/' + endyearC + '/'+ intervalC + 'day'

    print(dataDir)
    print(workDir)
    print(endyearC)
    print(endDoyC)
    print(intervalC)

    ###
    # dtypeList = ['chla']
    # for dtype in dtypeList:

    # Data type for composites
    dtype = 'chla'

    # Clean working directory
    os.chdir(workDir)
    os.system('rm -f *')

    # Change to data directory
    os.chdir(dataDir)

    # Preallocate sum (mean) and count arrays matching grid dims
    mean = np.zeros((4401, 8001), np.single)
    num = np.zeros((4401, 8001), dtype=np.int32)

    # Composite within the same calendar year
    if (endDoy > startDoy):
        # Build range of Doys
        doyRange = list(range(startDoy, endDoy + 1))
        fileList = []
        # Gather filenames for each DOY
        for doy in doyRange:
            doyC = str(doy)
            doyC = doyC.rjust(3, '0')
            myString = 'MB' + endyearC + doyC + '*' + dtype + '.nc'
            fileList.append(glob.glob(myString))

        # Flatten and sort file list
        fileList = list(chain.from_iterable(fileList))
        fileList.sort()
        filesUsed = ""
        print(fileList)

        # Loop through files and accumulate data
        for fName in fileList:
            if (len(filesUsed) == 0):
                filesUsed = fName
            else:
                filesUsed = filesUsed + ', ' + fName

            chlaFile = Dataset(fName)
            chla = chlaFile.variables["MBchla"][:, :, :, :]
            chlaFile.close()
            chla = np.squeeze(chla)
            mean, num = meanVar(mean, num, chla)
    else:
        # Composite spans year boundary
        # Determine directory for the start year
        dataDir1 = dataDir
        dataDir1 = dataDir1.replace(endyearC, startYearC)
        # Determine end of start year based on start year
        if (isleap):
            endday = 366
        else:
            endday = 365

        fileList = []
        os.chdir(dataDir1)
        doyRange = list(range(startDoy, endday + 1))
        for doy in doyRange:
            doyC = str(doy)
            doyC = doyC.rjust(3, '0')
            myString = 'MB' + startYearC + doyC + '*' + dtype + '.nc'
            fileList.append(glob.glob(myString))

        fileList = list(chain.from_iterable(fileList))
        fileList.sort()
        filesUsed = ""
        print(fileList)
        for fName in fileList:
            if (len(filesUsed) == 0):
                filesUsed = fName
            else:
                filesUsed = filesUsed + ', ' + fName

            chlaFile = Dataset(fName)
            chla = chlaFile.variables["MBchla"][:, :, :, :]
            chlaFile.close()
            chla = np.squeeze(chla)
            mean, num = meanVar(mean, num, chla)

        # DOY from 1 to endDoy of end year
        os.chdir(dataDir)
        fileList = []
        doyRange = list(range(1, endDoy + 1))
        for doy in doyRange:
            doyC = str(doy)
            doyC = doyC.rjust(3, '0')
            myString = 'MB' + endyearC + doyC + '*' + dtype + '.nc'
            fileList.append(glob.glob(myString))

        fileList = list(chain.from_iterable(fileList))
        fileList.sort()
        print(fileList)
        for fName in fileList:
            if (len(filesUsed) == 0):
                filesUsed = fName
            else:
                filesUsed = filesUsed + ', ' + fName

            # Read the NetCDF, variable 'MBchla' and squeeze to make 2D array (lat x lon)
            chlaFile = Dataset(fName)
            chla = chlaFile.variables["MBchla"][:, :, :, :]
            chlaFile.close()
            chla = np.squeeze(chla)

            # Update running sum and count arrays
            mean, num = meanVar(mean, num, chla)

    # Mask out any grid cells with zero observations, setting them to the fill value
    mean = ma.array(mean, mask=(num==0), fill_value=-9999999.)

    # Switch to the working directory for output operations
    os.chdir(workDir)

    # Construct the output filename with start and end dates plus data types
    outFile = 'MB' + startYearC + startDoyC + '_' + endyearC + endDoyC + '_' + dtype + '.nc'

    # Create multi-day NetCDF file using the mean and count arrays
    ncFile = makeNetcdf(mean, num, interval, outFile, filesUsed, workDir)

    # Upload composite NetCDF to remote MB chla directory, labeling it with the interval
    send_to_servers(ncFile, '/MB/chla/', str(interval))
