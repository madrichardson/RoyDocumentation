"""
Overview
--------
Generate multi-day SST composites for the MODIS “MW” (West Coast) dataset by averaging
1-day NetCDF files over a specified interval (e.g., 3, 5, 8, or 14 days).

Usage
-----
::
  
    python CompMWSST.py <dataDir> <workDir> <endYear> <endDoy> <interval>

Where:

- ``dataDir``

  Directory containing the daily MW SST NetCDF files named ``MW<YYYY><DDD>*sstd.nc``.

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
1. **Parse arguments & compute dates**  

  - Read paths and parameters from ``sys.argv``.
  
  - Convert ``endYear``+``endDoy`` to a calendar date ``myDateEnd``.
  
  - Compute ``myDateStart = myDateEnd - (interval-1) days``.
  
  - Zero-pad start and end DOY strings.

2. **Initialize**

  - Change into ``workDir`` and clear old files.

  - Change into ``dataDir``.

  - Preallocate two 2321x4001 arrays:

      - ``mean`` (running sum of SST)

      - ``num``  (count of observations)

3. **Collect 1-day files**

  - If ``startDoy ≤ endDoy`` (same year), gather DOYs ``startDoy…endDoy``.

  - Else, handle year-boundary wrap: DOYs ``startDoy…endOfYear`` and ``1…endDoy``.

4. **Accumulate SST**

  For each matching file:

     - Read and squeeze the 4D SST variable ``"MWsstd"``.
     
     - Update ``mean, num`` via ``meanVar(mean, num, sst)``.

5. **Finalize composite**

  - Mask out cells with zero observations (``num==0``), setting fill value ``-9999999.``.

6. **Write & deploy**

  - Change back to ``workDir``.

  - Call ``makeNetcdf(mean, num, interval, outFile, filesUsed, workDir)`` to create CF-compliant NetCDF.

  - Transfer result via ``send_to_servers(ncFile, "/MW/sstd/", str(interval))``.

Dependencies
------------
- **Python 3.x**

- **Standard library:** ``os``, ``sys``, ``glob``, ``itertools.chain``, ``datetime``, ``timedelta``  

- **Third-party:** ``netCDF4.Dataset``, ``numpy``, ``numpy.ma``  

- **Custom roylib functions:**

  - ``isleap(year)``

  - ``meanVar(sum_array, count_array, data_slice)``

  - ``makeNetcdfmDay(mean, num, interval, outFile, filesUsed, workDir)``

  - ``send_to_servers(ncFile, remote_dir, 'm')``

Directory Structure
-------------------
- **Input Directory** (dataDir):

  ``MW<YYYY><DDD>*sstd.nc`` (1-day SST files)

- **Working directory** (workDir):  

  Temporary staging for intermediate files  

- **Output location** (remote):  

  ``/MW/sstd/<interval>day/`` on the server  

Usage Example
-------------
Generate a 5-day composite ending on 2025 day-of-year 082

::
 
   python CompMWSST.py /Users/you/modis_data/mw/1day/ /Users/you/modis_work/ 2025 082 5

This command will:

  - Read the five daily files MW202508?*sstd.nc for DOY 078-082 

  - Compute the 5-day running average for each grid cell  

  - Write ``MW2025078_2025082_sstd.nc`` in ``/Users/you/modis_work/`` 
   
  - Upload it to ``/MW/sstd/5day/`` on the server 
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

    # Directory with 1-day MW SST NetCDFs
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

    # Composite length as string
    intervalC = sys.argv[5]

    print(dataDir)
    print(intervalC)

    # Composite length as integer
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
    outDir = '/ERDData1/modisa/data/modiswc/' + endyearC + '/' + intervalC + 'day'

    print(dataDir)
    print(workDir)
    print(endyearC)
    print(endDoyC)
    print(intervalC)

    ###
    # dtypeList = ['sstd']
    # for dtype in dtypeList:

    # Data type for SST composites
    dtype = 'sstd'

    # Clear working directory
    os.chdir(workDir)
    os.system('rm -f *')

    # Move to data directory
    os.chdir(dataDir)

    # Preallocate sum (mean) and count arrays matching grid dims
    mean = np.zeros((2321, 4001), np.single)
    num = np.zeros((2321, 4001), dtype=np.int32)

    # Collect all NetCDF files spanning startDoy..endDoy
    if (endDoy > startDoy):
        # Same-year composite
        doyRange = list(range(startDoy, endDoy + 1))
        fileList = []
        for doy in doyRange:
            doyC = str(doy)
            doyC = doyC.rjust(3, '0')
            myString = 'MW' + endyearC + doyC + '*' + dtype + '.nc'
            fileList.append(glob.glob(myString))

        # Flatten nested lists and sort
        fileList = list(chain.from_iterable(fileList))
        fileList.sort()
        print(fileList)

        filesUsed = ""
        for fName in fileList:
            # Build comma-separated list of files used
            if (len(filesUsed) == 0):
                filesUsed = fName
            else:
                filesUsed = filesUsed + ', ' + fName

            # Open NetCDF file and extract 4D SST variable
            sstFile = Dataset(fName)
            sst = sstFile.variables["MWsstd"][:, :, :, :]
            sstFile.close()

            # Squeeze to remove singleton dimensions -> 2D array
            sst = np.squeeze(sst)

            # Update running mean and count arrays
            mean, num = meanVar(mean, num, sst)

    else:
        # Compute directory for start of year by replacing year in path
        dataDir1 = dataDir
        dataDir1 = dataDir1.replace(endyearC, startYearC)

        # Determine end-of-year DOY based on leap year
        if(isleap):
            endday = 366
        else:
            endday = 365

        # From startDoy through end of startYearC
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

        # From DOY=1 of endyearC through endDoy
        os.chdir(dataDir)
        fileList = []
        doyRange= list(range(1, endDoy + 1))
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

    # Mask out any grid cells with zero observations, setting them to the fill value
    mean = ma.array(mean, mask=(num == 0), fill_value=-9999999.)
    print('COmpMWSST finished mean')

    # Switch to the working directory for output operations
    os.chdir(workDir)

    # Construct the output filename with start and end dates plus data types
    outFile = 'MW' + startYearC + startDoyC + '_' + endyearC + endDoyC + '_' + dtype + '.nc'

    # Create multi-day NetCDF file using the mean and count arrays
    ncFile = makeNetcdf(mean, num, interval, outFile, filesUsed, workDir)

    # Directory on the remote server for storing the multi-day SST product
    remote_dir = '/MW/sstd/'

    # Transfer the generated NetCDF file to the remote server directory, labeling it with the interval
    send_to_servers(ncFile, remote_dir , str(interval))
