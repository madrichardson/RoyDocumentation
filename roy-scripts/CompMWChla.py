"""
Overview
--------
Generate multi-day composites for MODIS “MW” (West Coast) products:
chlorophyll-a (Chla), Kd490, PAR0, and fluorescence line height (CFLH).

Usage
-----
::

    python CompMWChla.py <dataDir> <workDir> <endYear> <endDoy> <interval>

Where:

- ``dataDir``

  Directory containing daily 1-day NetCDFs named ``MW<YYYY><DDD>_<param>.nc``.

- ``workDir``

  Temporary working directory for intermediate files.

- ``endYear`` 

  Four-digit year of the last day in the composite (e.g., ``2025``).

- ``endDoy``

  Three-digit day-of-year of the last day (e.g., ``082``).

- ``interval``

  Composite length in days (`3`, `5`, `8`, or `14`)

Description
-----------
1. **Parse arguments & compute date range** 

  - Read ``dataDir``, ``workDir``, ``endYear``, ``endDoy``, ``interval``.

  - Compute start day = end day minus (``interval``-1), zero-pad ``startDoy``.

2. **Loop over each variable** (``chla``, ``k490``, ``par0``, ``cflh``):  

  - Clear ``workDir``.

  - Initialize ``mean`` and ``num`` arrays for sum and count.

  - Gather daily files over the date range (handles year wrap).

  - For each file, read 4D ``MW<dtype>``, squeeze to 2D, update ``mean``, ``num``.

  - Mask out pixels with zero count (fill = -9999999).

  - Write composite via ``makeNetcdf(...)`` and send via ``send_to_servers(...)``.

Dependencies
------------
- **Python 3.x**

- **Standard library:** ``os``, ``sys``, ``glob``, ``itertools.chain``, ``datetime``

- **Third-party:** ``numpy``, ``numpy.ma``, ``netCDF4``

- **Custom roylib functions:**

  - ``isleap(year)``

  - ``meanVar(mean, num, obs)``

  - ``makeNetcdf(mean, nobs, interval, outFile, filesUsed, workDir)``

  - ``send_to_servers(ncFile, destDir, interval)``

Directory Structure
-------------------
- **Input Directory** (``dataDir``):

  ``MW<YYYY><DDD>*<dtype>.nc``

- **Working Directory** (``workDir``):

  Temporary staging for intermediate files

- **Output Location** (remote):

  ``/MW/<dtype>/`` on the server

Usage Example
-------------
5-day composite (DOY 100-104 of 2025):

::
  
   python CompMWChla.py /data/MW/1day /tmp/mw_work 2025 104 5

This command will:

  - Read all daily files ``MW2025100*...MW2025104*`` from ``/data/MW/1day``.

  - Compute the 5-day composite for Chla, Kd490, PAR0, and CFLH.

  - Write the output files to ``/tmp/mw_work/`` and upload them to ``/MW/<dtype>/`` on the server.
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

    # Directory with 1-day MW NetCDFs
    dataDir = sys.argv[1]

    # Temporary working directory
    workDir = sys.argv[2]

    # Composite end year (YYYY)
    endyearC = sys.argv[3]

    # Composite end day-of-year (DDD)
    endDoyC = sys.argv[4]
    endDoyC = endDoyC.rjust(3, '0')

    # Integer form of end day-of-year
    endDoy = int(endDoyC)

    # Composite length
    intervalC = sys.argv[5]
    interval = int(intervalC)

    # Convert end Doy to calendar date
    myDateEnd = datetime(int(endyearC), 1, 1) + timedelta(int(endDoyC) - 1)

    # Start date = end date minus (interval-1) days
    myDateStart = myDateEnd + timedelta(days=-(interval - 1))

    # Zero-padded start Doy and year
    startDoyC = myDateStart.strftime("%j").zfill(3)
    startDoy = int(startDoyC)
    startYearC = str(myDateStart.year)

    # Prepare output directory 
    outDir = '/ERDData1/modisa/data/modsiwc/' + endyearC + '/' + intervalC + 'day'

    print(dataDir)
    print(workDir)
    print(endyearC)
    print(endDoyC)
    print(intervalC)

    # List of parameters to composite
    dtypeList = ['chla', 'k490', 'par0', 'cflh']

    # Loop over each variable type
    for dtype in dtypeList:
        # Clear working directory
        os.chdir(workDir)
        os.system('rm -f *')

        # Move to data directory
        os.chdir(dataDir)

        # Preallocate sum (mean) and count arrays matching grid dims
        mean = np.zeros((2321, 4001), np.single)
        num = np.zeros((2321, 4001), dtype=np.int32)

        # If composite does not cross year boundary
        if (endDoy > startDoy):
            doyRange = list(range(startDoy, endDoy+1))
            fileList = []
            # Gather matching files for each day in range
            for doy in doyRange:
                doyC = str(doy)
                doyC = doyC.rjust(3, '0')
                myString = 'MW' + endyearC + doyC + '*' + dtype + '.nc'
                fileList.append(glob.glob(myString))
            
            # Flatten and sort list of lists
            fileList=list(chain.from_iterable(fileList))
            fileList.sort()

            filesUsed = ""
            print(fileList)
            for fName in fileList:
                # Build comma-separated provenance string
                if (len(filesUsed) == 0):
                    filesUsed = fName
                else:
                    filesUsed = filesUsed + ', ' + fName

                # Read the variable from NetCDF and accumulate
                chlaFile = Dataset(fName)
                param = 'MW' + dtype
                chla = chlaFile.variables[param][:, :, :, :]
                chlaFile.close()
                chla = np.squeeze(chla)

                # Update running mean and count arrays
                mean, num = meanVar(mean, num, chla)

        else:
            # Composite spans year boundary: first part in startYearC
            dataDir1 = dataDir
            dataDir1 = dataDir1.replace(endyearC, startYearC)
            if (isleap):
                endday = 366
            else:
                endday = 365

            fileList = []
            os.chdir(dataDir1)
            # Days from startDoy to end of start year
            doyRange = list(range(startDoy, endday + 1))
            for doy in doyRange:
                doyC = str(doy)
                doyC = doyC.rjust(3, '0')
                myString = 'MW' + startYearC + doyC + '*' + dtype + '.nc'
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
                param = 'MW' + dtype
                chla = chlaFile.variables[param][:, :, :, :]
                chlaFile.close()
                chla = np.squeeze(chla)
                mean, num = meanVar(mean, num, chla)

            # Days from DOY=1 of end year to endDoy
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

                chlaFile = Dataset(fName)
                param = 'MW' + dtype
                chla = chlaFile.variables[param][:, :, :, :]
                chlaFile.close()
                chla = np.squeeze(chla)
                mean, num = meanVar(mean, num, chla)

        # Mask out any grid cells with zero observations, setting them to the fill value
        mean = ma.array(mean, mask=(num == 0), fill_value=-9999999.)

        # Switch to the working directory for output operations
        os.chdir(workDir)

        # Construct the output filename with start and end dates plus data types
        outFile = 'MW' + startYearC + startDoyC + '_' + endyearC + endDoyC + '_' + dtype + '.nc'

        # Create multi-day NetCDF file using the mean and count arrays
        ncFile = makeNetcdf(mean, num, interval, outFile, filesUsed, workDir)

        # Directory on the remote server for storing the multi-day data product
        remote_dir = '/MW/' + dtype + '/'

        # Transfer the generated NetCDF file to the remote server directory
        send_to_servers(ncFile, remote_dir , str(interval))
