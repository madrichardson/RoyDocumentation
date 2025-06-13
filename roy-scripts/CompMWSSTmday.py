"""
Overview
--------
Compute monthly SST composites for the MODIS “MW” (West Coast) region by averaging
daily 1-day SST NetCDF products over a specified interval.

Usage
-----
::
  
    python CompMWSSTmday.py <dataDir> <workDir> <endYear> <endDoy> <startDoy>

Where:

- ``dataDir``

  Directory containing 1-day NetCDF files named ``MW<YYYY><DDD>*sstd.nc``

- ``workDir``

  Temporary working directory for intermediate files

- ``endYear``   

  Four-digit year of the last day in the composite (e.g., ``2025``)

- ``endDoy``

  Three-digit day-of-year of the last day (e.g., ``082``)

- ``startDoy``

  Three-digit day-of-year of the first day (e.g., ``075``)

Description
-----------
1. **Parse command-line arguments** and compute the composite length:

  - Read ``dataDir``, ``workDir``, ``endYear``, ``endDoy``, ``startDoy``.

  - Zero-pad ``endDoy`` and ``startDoy``, compute ``interval = endDoy - startDoy + 1``.

2. **Convert endDoy to a calendar date** (``myDateEnd``) for logging or output paths.

3. **Gather all 1-day SST files** spanning ``startDoy..endDoy``:

  - Build glob patterns ``MW<year><DDD>*sstd.nc``

  - Handles same-year and year-boundary wrap-around cases.

4. **Initialize accumulators**:

  - ``mean`` (float32) and ``num`` (int32) arrays of shape 2321x4001.

5. **Loop over each NetCDF**:

  - Open with ``Dataset()``.

  - Read the 4D variable ``MWsstd``, squeeze to 2D.

  - Update running ``mean`` and ``num`` via ``meanVar(mean, num, sst)``.

6. **Mask unobserved cells** (``num ==0``) and set fill value ``-9999999``.

7. **Write composite**:

  - Call ``makeNetcdfmDay(mean, num, interval, outFile, filesUsed, workDir)`` to produce a CF-compliant NetCDF.

8. **Transfer result**:

  - Use ``send_to_servers(ncFile, '/MW/sstd/', 'm')`` to copy the composite to the remote directory.

Dependencies
------------
- **Python 3.x**

- **Standard library:** ``os``, ``sys``, ``glob``, ``itertools.chain``, ``datetime``, ``timedelta``

- **Third-party:** ``numpy``, ``numpy.ma``, ``netCDF4.Dataset``

- **Custom roylib functions:**

  - ``isleap(year)``

  - ``meanVar(sum_array, count_array, data_slice)``

  - ``makeNetcdfmDay(mean, num, interval, outFile, filesUsed, workDir)``

  - ``send_to_servers(ncFile, remote_dir, 'm')``

Directory Structure
-------------------
- **Input directory** (dataDir):

  Contains files like ``MWYYYYDDD*sstd.nc``, one per day.

- **Working directory** (workDir):

  Cleared and used for any temporary artifacts (none persisted).

- **Output Location** (via ``makeNetcdfmDay``):

  Writes ``MW<startYYYY><startDDD>_<endYYYY><endDDD>_sstd.nc`` in ``<workDir>`` and then copies it to ``/MW/sstd/``.

Usage Example
-------------
Create a January 2025 composite (DOY 001-031):

::
 
   python CompMWSSTmday.py /path/to/MW/1day/ /path/to/tmp/ 2025 031 001

This command will:

  - Read daily SST files ``MW2025001*…MW2025031*`` from ``/path/to/MW/1day/``.

  - Compute the 31-day average for each grid cell.

  - Write ``MW2025001_2025031_sstd.nc`` in ``/path/to/tmp/``. 

  - Upload the composite to ``/MW/sstd/`` on the server.
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

    # Directory containing daily MW NetCDF files
    dataDir = sys.argv[1]

    # Temporary working directory
    workDir = sys.argv[2]

    # End date (year, day-of-year)
    endyearC = sys.argv[3]
    endDoyC = sys.argv[4]
    endDoyC = endDoyC.rjust(3, '0')

    # Start day-of-year (same year)
    startYearC = endyearC
    endDoy = int(endDoyC)
    startDoyC = sys.argv[5]
    startDoyC = startDoyC.rjust(3, '0')
    startDoy = int(startDoyC)

    # Number of days in the composite
    interval = endDoy - startDoy + 1

    # Convert end date to calendar dates
    myDateEnd = datetime(int(endyearC), 1, 1) + timedelta(endDoy - 1)
    myDateStart = myDateEnd + timedelta(startDoy - 1)

    # Prepare output directory
    outDir = '/ERDData1/modisa/data/modiswc/' + endyearC + '/mday'
    print(dataDir)
    print(workDir)
    print(endyearC)
    print(endDoyC)
    print(interval)

    ###
    # dtypeList = ['sstd']
    # for dtype in dtypeList:

    # Set up for reading MB SST variable ("MWsstd") across multiple days
    dtype = 'sstd'

    # Clear working directory
    os.chdir(workDir)
    os.system('rm -f *')

    # Move to data directory
    os.chdir(dataDir)

    # Preallocate sum (mean) and count arrays matching grid dims
    mean = np.zeros((2321, 4001), np.single)
    num = np.zeros((2321, 4001), dtype=np.int32)

    # Build list of NetCDF files spanning startDoy..endDoy
    if (endDoy > startDoy):
        # Composite within the same calendar year
        doyRange = list(range(startDoy, endDoy + 1))
        fileList = []
        for doy in doyRange:
            doyC = str(doy)
            doyC = doyC.rjust(3, '0')
            myString = 'MW' + endyearC + doyC + '*' + dtype + '.nc'
            # find all files matching MWYYYYDD*<dtype>.nc
            fileList.append(glob.glob(myString))

        # Flatten list of lists and sort alphabetically
        fileList = list(chain.from_iterable(fileList))
        fileList.sort()
        print(fileList)

        # Track which files were used
        filesUsed = ""
        for fName in fileList:
            if (len(filesUsed) == 0):
                filesUsed = fName
            else:
                filesUsed = filesUsed + ', ' + fName

            # Open NetCDF, extract the 4D SST array, then squeeze to 2D
            sstFile = Dataset(fName)
            sst = sstFile.variables["MWsstd"][:, :, :, :]
            sstFile.close()
            sst = np.squeeze(sst)

            # Update running mean and count arrays
            mean, num = meanVar(mean, num, sst)

    else:
        # Compute directory for start of year by replacing year in path
        dataDir1 = dataDir
        dataDir1 = dataDir1.replace(endyearC, startYearC)

        # Determine end-of-year DOY based on leap year
        if (isleap):
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
            myString = 'MW' + startYearC + doyC + '*' + dtype + '.nc'
            fileList.append(glob.glob(myString))

        fileList = list(chain.from_iterable(fileList))
        fileList.sort()
        print(fileList)
        filesUsed = ''
        for fName in fileList:
            if (len(filesUsed) == 0):
                filesUsed = fName
            else:
                filesUsed = filesUsed + ', ' + fName

            sstFile = Dataset(fName)
            sst = sstFile.variables["MWsstd"][:, :, :, :]
            sstFile.close()
            sst = np.squeeze(sst)
            mean, num = meanVar(mean, num, sst)

        # From DOY 1 of end year through endDoy
        os.chdir(dataDir)
        fileList = []
        doyRange = list(range(1, endDoy + 1))
        for doy in doyRange:
            doyC = str(doy)
            doyC = doyC.rjust(3, '0')
            myString = 'MW' + endyearC + doyC + '*' + dtype + '.nc'
            fileList.append(glob.glob(myString))

        fileList = list(chain.from_iterable(fileList))
        fileList.sort()
        print(fileList)

        for fName in fileList:
            if (len(filesUsed) == 0):
                filesUsed = fName
            else:
                filesUsed = filesUsed + ', ' + fName

            sstFile = Dataset(fName)
            sst = sstFile.variables["MWsstd"][:, :, :, :]
            sstFile.close()
            sst = np.squeeze(sst)
            mean, num = meanVar(mean, num, sst)

    # Mask out pixels with zero observations and set fill value for missing data
    mean = ma.array(mean, mask=(num == 0), fill_value=-9999999.)

    # Switch to the working directory
    os.chdir(workDir)

    # Construct output filename
    outFile = 'MW' + startYearC + startDoyC + '_' + endyearC + endDoyC + '_' + dtype + '.nc'

    # Generate the multi-day NetCDF file
    ncFile = makeNetcdfmDay(mean, num, interval, outFile, filesUsed, workDir)

    # Directory on the remote server where multi-day SST files are stored
    remote_dir = '/MW/sstd/'

    # Send the NetCDF to the remote server directory
    send_to_servers(ncFile, remote_dir , 'm')
