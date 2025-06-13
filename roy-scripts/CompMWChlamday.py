"""
Overview
--------
Generate monthly composites of chlorophyll-a, Kd_490, PAR0, and CFLH
for the MODIS “MW” (West Coast) region by accumulating 1-day NetCDF products.

Usage
-----
::
 
     python CompMWChlamday.py <dataDir> <workDir> <endYear> <endDoy> <startDoy>

Description
-----------
1. **Parse arguments & compute interval** 

  - Read ``dataDir``, ``workDir``, ``endYear``, ``endDoy``, and ``startDoy``.  
  
  - Compute the number of days ``interval = endDoy - startDoy + 1``.

2. **Compute calendar dates**

  - Convert ``startDoy``/``endDoy`` to ``datetime`` for logging/output paths.

3. **Loop over each parameter**

  For each in ``['chla','k490','par0','cflh']``:

     - **Initialize sum & count arrays** of shape 2321x4001.

     - **Gather all matching 1-day NetCDF files** between ``startDoy``…``endDoy``, handling both same-year and wrap-around cases.

     - **For each file**:

         - Open with ``netCDF4.Dataset``, read 4D variable ``MW<param>``, squeeze to 2D.

         - Update running totals (``mean``) and counts (``num``) via ``meanVar()``.

     - **Mask out** grid cells with zero observations (``num==0``), fill with -9999999.0.

     - **Write** composite via ``makeNetcdfmDay()``.

     - **Send** result to ``/MW/<param>/mday/`` on the server.

Dependencies
------------
- **Python 3.x**

- **Standard library:** ``os``, ``sys``, ``glob``, ``itertools.chain``, ``datetime``, ``timedelta``

- **Third-party:** ``numpy``, ``numpy.ma``, ``netCDF4``

- **Custom roylib functions:**

  - ``isleap(year)``

  - ``meanVar(sum_array, count_array, data_slice)``

  - ``makeNetcdfmDay(mean, num, interval, outFile, filesUsed, workDir)``

  - ``send_to_servers(ncFile, remote_dir, 'm')``

Directory Structure
-------------------
- **Input Directory (dataDir):**

  Contains 1-day NetCDFs named ``MW<YYYY><DDD>_<param>.nc``.

- **Working Directory (workDir):**

  Scratch space; cleared each loop.

- **Output location (remote):**

  ``/MW/chla/mday/``, ``/MW/k490/mday/``, etc.

Usage Example
-------------
Generate a composite for the month of January 2025 (DOY 001-031):

::
 
     python CompMWChlamday.py /data/mw/1day/ /tmp/mwwork/ 2025 031 001

This command will:

  - Read daily files ``MB2025001..Mb2025031``, computes the January composite.

  - Writes MB2025001_2025031_chla.nc in ``/tmp/mw_work/``.

  - Uploads it to ``/MB/chla/`` on the server.

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

    # Composite end year
    endyearC = sys.argv[3]
    endyear = int(endyearC)

    # Start year 
    startYearC = endyearC
    startyear = int(startYearC)

    # Composite end day-of-year
    endDoyC = sys.argv[4]
    endDoyC = endDoyC.rjust(3, '0')
    endDoy = int(endDoyC)

    # Composite start day-of-year
    startDoyC = sys.argv[5]
    startDoyC = startDoyC.rjust(3, '0')
    startDoy = int(startDoyC)

    # Number of days in the composite
    interval = endDoy - startDoy + 1

    # Compute calendar dats for logging or directory creation
    myDateEnd = datetime(endyear, 1, 1) + timedelta(endDoy - 1)
    myDateStart = datetime(startyear, 1, 1) + timedelta(startDoy - 1)

    # Output directory on server
    outDir = '/ERDData1/modisa/data/modsiwc/' + endyearC + '/mday'

    print(dataDir)
    print(workDir)
    print(endyearC)
    print(endDoyC)
    print(interval)

    # List of variables to composite
    dtypeList = ['chla', 'k490', 'par0', 'cflh']
    for dtype in dtypeList:
        # Clear working directory
        os.chdir(workDir)
        os.system('rm -f *')

        # Move to input directory
        os.chdir(dataDir)

        # Initialize sum and count arrays
        mean = np.zeros((2321, 4001), np.single)
        num = np.zeros((2321, 4001), dtype=np.int32)

        # Composite within same calendar year
        if (endDoy > startDoy):
            doyRange = list(range(startDoy, endDoy + 1))
            fileList = []
            # Gather all matching NetCDF filenames for each DOY
            for doy in doyRange:
                doyC = str(doy)
                doyC = doyC.rjust(3, '0')
                myString = 'MW' + endyearC + doyC + '*' + dtype + '.nc'
                fileList.append(glob.glob(myString))

            # Flatten and sort the list
            fileList = list(chain.from_iterable(fileList))
            fileList.sort()

            filesUsed = ""
            print(fileList)

            # Loop over each file, accumulate the variable
            for fName in fileList:
                if (len(filesUsed) == 0):
                    filesUsed = fName
                else:
                    filesUsed = filesUsed + ', ' + fName

                chlaFile = Dataset(fName)
                param = 'MW' + dtype
                chla = chlaFile.variables[param][:, :, :, :]
                chlaFile.close()

                # Remove singleton dimensions -> 2D (lat x lon)
                chla = np.squeeze(chla)

                # Update running mean and count
                mean, num = meanVar(mean, num, chla)

        else:
            # Composite spans year boundary
            dataDir1 = dataDir
            dataDir1 = dataDir1.replace(endyearC, startYearC)
            # Determine days in start year
            if (isleap):
                endday = 366
            else:
                endday = 365

            # DOY startDoy -> end of startYearC
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

            # DOY 1 -> endDoy in endYearC
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

        # Mask out pixels with zero observations and set fill value for missing data 
        mean = ma.array(mean, mask=(num == 0), fill_value=-9999999.)

        # Return to working directory for output
        os.chdir(workDir)

        # Construct output filename
        outFile = 'MW' + startYearC + startDoyC + '_' + endyearC + endDoyC + '_' + dtype + '.nc'

        # Create multi-day NetCDF
        ncFile = makeNetcdfmDay(mean, num, interval, outFile, filesUsed, workDir)

        # Send to server folder for this parameter
        remote_dir = '/MW/' + dtype + '/'
        send_to_servers(ncFile, remote_dir , 'm')

        #intervalDay = str(interval) + 'day'
        # myCmd = 'scp ' + ncFile  + ' cwatch@192.168.31.15:/u00/satellite/MW/' + dtype + '/mday'
        #myCmd = 'rsync -tvh ' + ncFile  + ' cwatch@192.168.31.15:/u00/satellite/MW/' + dtype + '/mday/' + ncFile
        #os.system(myCmd)
        # myCmd = 'scp ' + ncFile  + ' cwatch@192.168.31.15:/u00/satelliteNAS/MW/' + dtype + '/mday'
        #myCmd = 'rsync -tvh ' + ncFile  + ' cwatch@192.168.31.15:/u00/satelliteNAS/MW/' + dtype + '/mday/' + ncFile
        #os.system(myCmd)
        # myCmd = 'scp ' + ncFile  + ' cwatch@161.55.17.28:/u00/satellite/MW/' + dtype +  '/mday'
        # myCmd = 'rsync -tvh ' + ncFile  + ' /u00/satellite/MW/' + dtype +  '/mday/' + ncFile
        #myCmd = 'rsync -tvh ' + ncFile  + ' cwatch@161.55.17.28:/u00/satellite/MW/' + dtype +  '/mday/' + ncFile
        #os.system(myCmd)
