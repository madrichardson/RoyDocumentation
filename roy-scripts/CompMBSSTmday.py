"""
Overview
--------
Generate **monthly** SST composites for the MODIS “MB” (Pacific Ocean) dataset by averaging
daily 1-day NetCDF files over a user-defined range of days (typically a calendar month).

Usage
-----
::

    python CompMBSSTmday.py <dataDir> <workDir> <endYear> <endDoy> <startDoy>

Where:

- ``dataDir``

  Directory containing the daily 1-day SST NetCDFs named ``MB<YYYY><DDD>*sstd.nc``.

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

  - Read ``dataDir``, ``workDir``, ``endYear``, ``endDoy``, and ``startDoy`` from ``sys.argv``.

  - Compute ``interval = endDoy - startDoy + 1``, the number of days in the composite.

2. **Compute start/end dates**

  - Convert ``endYear`+`endDoy`` to a ``datetime`` for logging.

  - Derive ``startDoy`` date by subtracting ``interval - 1`` days.

3. **Initialize accumulators**

  - Change to ``workDir`` and clear any old files.

  - Preallocate two arrays of shape 4401x8001:

     - ``mean`` (float32) for the running sum of SST.

     - ``num``  (int32) for the count of observations.

4. **Gather daily files**

  - Build a sorted list of all ``MB<YYYY><DDD>*sstd.nc`` files from ``startDoy`` to ``endDoy``, handling wrap-around at year boundaries if needed.

5. **Accumulate daily SST**

  - For each file:

     - Open via ``Dataset()``, read the 4-D variable ``MBsstd``, squeeze to 2-D.

     - Update ``mean`` and ``num`` via ``meanVar(mean, num, sst2d)``.

6. **Mask and finalize**

  - Create a masked array: mask cells where ``num==0`` (no observations) and set fill value ``-9999999.``.

7. **Write & deploy**

  - Change to ``workDir``.

  - Construct an output filename ``MB<YYYY><startDDD>_<YYYY><endDDD>_sstd_mday.nc``.

  - Call ``makeNetcdfmDay(mean, num, interval, outFile, filesUsed, workDir)`` to produce a CF-compliant NetCDF.
  
  - Transfer the file to ``/MB/sstd/`` on the remote server via ``send_to_servers()``.

Dependencies
------------
- **Python 3.x**

- **Standard library:** ``os``, ``sys``, ``glob``, ``itertools.chain``, ``datetime``, ``timedelta``

- **Third-party:** ``numpy``, ``numpy.ma``, ``netCDF4.Dataset``

- **Custom roylib functions:**

  - ``isleap(year)``

  - ``meanVar(mean, num, data)``

  - ``makeNetcdfmDay(mean, num, interval, outFile, filesUsed, workDir)``

  - ``send_to_servers(ncFile, remote_dir, interval_flag)``

Directory Structure
-------------------
- **Input Directory** (``dataDir``):

  ``MB<YYYY><DDD>*sstd.nc`` daily SST files for the year.

- **Working Directory**  (``workDir``):

  Temporary staging for intermediate and final files.

- **Output Location**:

  Monthly composite written to ``workDir`` then copied to ``/MB/sstd/``.

Usage Example
-------------
Create a January 2025 composite (DOY 001-031):
::
 
   python CompMBSSTmday.py /data/modisgf/1day/ /tmp/mb_work/ 2025 031 001

This averages daily SST files DOY 001…031 of 2025, writes ``MB2025001_2025031_sstd_mday.nc`` in ``/tmp/mb_work/``, and uploads to ``/MB/sstd/``.
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

    # Directory of daily 1-day NetCDFs
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
    #cdtypeList = ['sstd']
    # for dtype in dtypeList:

    # Only SST variable for MB composites
    dtype = 'sstd'

    # Clean working directory
    os.chdir(workDir)
    os.system('rm -f *')

    # Move to data directory
    os.chdir(dataDir)

    # Preallocate sum (mean) and count arrays matching grid dims
    mean = np.zeros((4401, 8001), np.single)
    num = np.zeros((4401, 8001), dtype=np.int32)

    # Build list of NetCDF files spanning startDoy..endDoy
    if (endDoy > startDoy):
        # Composite entirely within the same year
        doyRange = list(range(startDoy, endDoy + 1))
        print(doyRange)

        # Build list matching files for each DOY
        fileList = []
        for doy in doyRange:
            doyC = str(doy)
            doyC = doyC.rjust(3, '0')
            myString = 'MB' + endyearC + doyC + '*' + dtype + '.nc'
            fileList.append(glob.glob(myString))

        # Flatten and sort
        fileList = list(chain.from_iterable(fileList))
        fileList.sort()
        filesUsed = ""
        print(fileList)

        # Loop through each file
        for fName in fileList:
            # Build provenance string
            if (len(filesUsed) == 0):
                filesUsed = fName
            else:
                filesUsed = filesUsed + ', ' + fName

            # Read SST variable and accumulate
            sstFile = Dataset(fName)
            sst = sstFile.variables["MBsstd"][:, :, :, :]
            sstFile.close()
            sst = np.squeeze(sst)

            # Update running mean and count arrays
            mean, num = meanVar(mean, num, sst)
    else:
        # Composite spans year boundary
        dataDir1 = dataDir
        dataDir1 = dataDir1.replace(endyearC, startYearC)

        # Determine last day of start year
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
            myString = 'MB' + startYearC + doyC + '*' + dtype + '.nc'
            fileList.append(glob.glob(myString))

        fileList = list(chain.from_iterable(fileList))
        fileList.sort()
        fileUsed = ""
        print(fileList)
        for fName in fileList:
            if (len(filesUsed) == 0):
                filesUsed = fName
            else:
                filesUsed = filesUsed + ', ' + fName

            sstFile = Dataset(fName)
            sst = sstFile.variables["MBsstd"][:, :, :, :]
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

            sstFile = Dataset(fName)
            sst = sstFile.variables["MBsstd"][:, :, :, :]
            sstFile.close()
            sst = np.squeeze(sst)
            mean, num = meanVar(mean,num,sst)

    # Mask out pixels with zero observations and set fill value for missing data
    mean = ma.array(mean, mask=(num == 0), fill_value=-9999999.)

    # Switch to the working directory
    os.chdir(workDir)

    # Construct output filename
    outFile = 'MB' + startYearC + startDoyC + '_' + endyearC + endDoyC + '_' + dtype + '.nc'

    # Generate the multi-day NetCDF file
    ncFile = makeNetcdfmDay(mean, num, interval, outFile, filesUsed, workDir)

    # Send the NetCDF to the remote server directory
    send_to_servers(ncFile, '/MB/sstd/' , 'm')
