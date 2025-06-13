"""
Overview
--------
Compute monthly composites of chlorophyll-a (Chla) for the MODIS “MB” (Pacific Ocean)
dataset by averaging daily 1-day NetCDF files over a specified interval of days.

Usage
-----
::
  
    python CompMBChlamday.py <dataDir> <workDir> <endYear> <endDoy> <startDoy>

Where:

- ``dataDir``

  Directory containing daily 1-day NetCDF files named ``MB<YYYY><DDD>*chla.nc``.

- ``workDir``

  Temporary working directory for intermediate files

- ``endYear`` 

  Four-digit year of the last day in the composite (e.g., ``2025``).

- ``endDoy``

  Three-digit day-of-year of the last composite day (e.g., ``031``).

- ``startDoy``

  Three-digit day-of-year of the first composite day (e.g., ``001``).

Description
-----------
1. **Parse arguments & compute interval**

  - Read ``dataDir``, ``workDir``, ``endYear``, ``endDoy``, and ``startDoy``.

  - Compute ``interval = endDoy - startDoy + 1``.

2. **Compute calendar dates**

  - Convert ``endYear`` + ``endDoy`` to a ``datetime`` (``myDateEnd``).

  - Derive ``myDateStart = myDateEnd - (interval - 1) days``.

3. **Initialize accumulators**

  - Clear ``workDir``.

  - Preallocate two arrays of shape (4401x8001):

     - ``mean`` (float32) for the running sum of Chla.

     - ``num``  (int32) for the count of observations.

4. **Gather daily files**

  - Build a list of all ``MB<YYYY><DDD>*chla.nc`` files from ``startDoy`` to ``endDoy``.

  - Handle year-boundary spans by splitting into two date ranges if necessary.

5. **Accumulate daily Chla**

  - For each file:

     - Open via ``Dataset()``.

     - Read the 4-D variable ``MBchla``, squeeze to 2-D.

     - Update ``mean`` and ``num`` via ``meanVar(mean, num, data2d)``.

6. **Mask & finalize**

  - Create a masked array: mask cells where ``num == 0`` (no observations) and set fill value ``-9999999.``.

7. **Write & deploy**

  - Change to ``workDir``.

  - Construct output filename ``MB<startYear><startDoy>_<endYear><endDoy>_chla.nc``.

  - Call ``makeNetcdfmDay(mean, num, interval, outFile, filesUsed, workDir)`` to produce a CF-compliant NetCDF.

  - Transfer it to ``/MB/chla/`` on the remote server via ``send_to_servers()``.

Dependencies
------------
- Python 3.x

- Standard library: ``os``, ``sys``, ``glob``, ``itertools.chain``, ``datetime``, ``timedelta``

- Third-party: ``numpy``, ``numpy.ma``, ``netCDF4.Dataset``

- Custom roylib functions:

  - ``isleap(year)``

  - ``meanVar(mean, num, data)``

  - ``makeNetcdfmDay(mean, num, interval, outFile, filesUsed, workDir)``

  - ``send_to_servers(ncFile, remote_dir, interval_flag)``


Directory Structure
-------------------
- **Input Directory** (dataDir):

  Contains daily files ``MB<YYYY><DDD>*chla.nc``.

- **Working Directory** (workDir):

  Temporary space cleared and reused each run.

- **Output Location**:

  Final monthly composite sent to ``/MB/chla/``.

Usage Example
-------------
Generate a January 2025 composite (DOY 001-031):

::
 
   python CompMBChlamday.py /data/modisgf/1day/ /tmp/mw_work/ 2025 031 001

This will average daily Chla for DOY 001…031 of 2025, write ``MB2025001_2025031_chla.nc`` in ``/tmp/mw_work/``, and upload to ``/MB/chla/``.
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

    # Directory with 1-day MB chl files
    dataDir = sys.argv[1]

    # Temporary working directory
    workDir = sys.argv[2]

    # Composite end year
    endyearC = sys.argv[3]

    # Same year for start
    startYearC = endyearC

    # Zero-padded end DOY
    endDoyC = sys.argv[4]
    endDoyC = endDoyC.rjust(3, '0')
    endDoy = int(endDoyC)

    # Zero-padded start DOY
    startDoyC = sys.argv[5]
    startDoyC = startDoyC.rjust(3, '0')
    startDoy = int(startDoyC )

    # Number of days in the composite
    interval = endDoy - startDoy + 1

    # Convert end date to calendar dates
    myDateEnd = datetime(int(endyearC), 1, 1) + timedelta(endDoy - 1)
    myDateStart = myDateEnd + timedelta(days=-(interval - 1))

    # Prepare output directory
    outDir = '/ERDData1/modisa/data/modisgf/' + endyearC + '/mday'

    print(dataDir)
    print(workDir)
    print(endyearC)
    print(endDoyC)
    print(interval)

    ###
    # dtypeList = ['chla']
    # for dtype in dtypeList:

    # Data type for this composite run
    dtype = 'chla'

    # Clear the working directory
    os.chdir(workDir)
    os.system('rm -f *')

    # Move to data directory
    os.chdir(dataDir)

    # Preallocate sum (mean) and count arrays matching grid dims
    mean = np.zeros((4401, 8001), np.single)
    num = np.zeros((4401, 8001), dtype=np.int32)

    # Composite entirely within the same year
    if (endDoy > startDoy):
        doyRange = list(range(startDoy, endDoy + 1))
        fileList = []
        # Collect all matching files for each DOY
        for doy in doyRange:
            doyC = str(doy)
            doyC = doyC.rjust(3, '0')
            myString = 'MB' + endyearC + doyC + '*' + dtype + '.nc'
            fileList.append(glob.glob(myString))

        # Flatten and sort the list of lists
        fileList = list(chain.from_iterable(fileList))
        fileList.sort()
        filesUsed = ""
        print(fileList)

        # Loop through each file
        for fName in fileList:
            if (len(filesUsed) == 0):
                filesUsed = fName
            else:
                filesUsed = filesUsed + ', ' + fName

            chlaFile = Dataset(fName)
            chla = chlaFile.variables["MBchla"][:, :, :, :]
            chlaFile.close()
            chla = np.squeeze(chla)

            # Update running mean and count arrays
            mean, num = meanVar(mean, num, chla)
    else:
        # Composite wraps across year boundary
        dataDir1 = dataDir
        dataDir1 = dataDir1.replace(endyearC, startYearC)
        # Determine last DOY of start year based on leap year
        if(isleap):
            endday = 366
        else:
            endday = 365

        # From startDoy through end of start year  
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

        # From DOY 1 of end year through endDoy
        os.chdir(dataDir)
        fileList = []
        doyRange= list(range(1, endDoy + 1))
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

            chlaFile = Dataset(fName)
            chla = chlaFile.variables["MBchla"][:, :, :, :]
            chlaFile.close()
            chla = np.squeeze(chla)
            mean, num = meanVar(mean, num, chla)

    # Mask out pixels with zero observations and set fill value for missing data
    mean = ma.array(mean, mask=(num == 0), fill_value=-9999999.)

    # Switch to the working directory
    os.chdir(workDir)

    # Construct output filename
    outFile = 'MB' + startYearC + startDoyC + '_' + endyearC + endDoyC + '_' + dtype + '.nc'

    # Generate the monthly NetCDF file
    ncFile = makeNetcdfmDay(mean, num, interval, outFile, filesUsed, workDir)

    # Upload the composite to remote MB chla directory
    send_to_servers(ncFile, '/MB/chla/', 'm')
