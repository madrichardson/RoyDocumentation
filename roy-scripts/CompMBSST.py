"""
Overview
--------
Compute multi-day SST composites for the MODIS “MB” (Pacific Ocean) dataset by averaging
daily 1-day NetCDF SST files over a specified interval of days (e.g., 3, 5, 8, or 14).

Usage
-----
::
  
    python CompMBSST.py <dataDir> <workDir> <endYear> <endDoy> <interval>

Where:

- ``dataDir``

  Directory containing daily 1-day SST NetCDF files named ``MB<YYYY><DDD>*sstd.nc``.

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

  - Compute ``startDoy = endDoy - interval + 1`` and zero-pad DOY strings.

2. **Compute calendar dates**

  - Convert ``endYear`` + ``endDoy`` to a ``datetime`` (``myDateEnd``).
  
  - Compute ``myDateStart = myDateEnd - (interval - 1)`` days.

3. **Initialize accumulators**

  - Clear ``workDir`` of old files.

  - Preallocate ``mean`` and ``num`` arrays of shape (4401, 8001) for running sum and counts.

4. **Gather daily files**

  - If ``startDoy ≤ endDoy``, collect files for DOYs ``startDoy…endDoy``; else handle wrap-around at year end by collecting ``startDoy…yearEnd`` and ``1…endDoy``.

5. **Accumulate SST**

  - For each NetCDF:

     - Open via ``Dataset()``.

     - Read 4-D variable ``MBsstd``, squeeze to 2-D array.

     - Update ``mean, num`` with ``meanVar(mean, num, sst)``.

6. **Mask and finalize**

  - Mask cells with zero observations (``num == 0``), fill with ``-9999999.``.

7. **Write & deploy**

  - Change back to ``workDir``.

  - Build ``outFile = MB<startYear><startDoy>_<endYear><endDoy>_sstd.nc``.

  - Call ``makeNetcdf(mean, num, interval, outFile, filesUsed, workDir)`` to write CF-compliant NetCDF.

  - Upload via ``send_to_servers(ncFile, '/MB/sstd/', str(interval))``.

Dependencies
------------
- **Python 3.x**

- **Standard library:** ``os``, ``sys``, ``glob``, ``itertools.chain``, ``datetime``, ``timedelta``

- **Third-party:** ``numpy``, ``numpy.ma``, ``netCDF4.Dataset``

- **Custom roylib functions:**

  - ``isleap(year)``

  - ``meanVar(mean, num, array)``

  - ``makeNetcdf(mean, num, interval, outFile, filesUsed, workDir)``

  - ``send_to_servers(ncFile, remote_dir, interval_flag)``

Directory Structure
-------------------
- **Input Directory** (``dataDir``):

  Contains daily files ``MB<YYYY><DDD>*sstd.nc``.

- **Working Directory** (``workDir``):

  Temporary staging and output location.

- **Output location** (remote):

  Copied to ``/MB/sstd/`` with the interval flag.

Usage Example
-------------
Create a 5-day SST composite from DOY 001 to 005 of 2025:

::
 
   python CompMBSST.py /data/modisgf/1day/ /tmp/mw_work/ 2025 005 5

This will average files MB2025001*… through MB2025005*, write ``MB2025001_2025005_sstd.nc`` in ``/tmp/mw_work/``, and upload to ``/MB/sstd/``.
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

    # Directory with 1-day SST NetCDFs
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
    outDir = '/ERDData1/modisa/data/modisgf/' + endyearC + '/' + intervalC + 'day'

    print(dataDir)
    print(workDir)
    print(endyearC)
    print(endDoyC)
    print(intervalC)
    print(startYearC)
    print(startDoyC)

    ###
    #cdtypeList = ['sstd']
    # for dtype in dtypeList:

    # Data type for SST composites
    dtype = 'sstd'

    # Clean working directory
    os.chdir(workDir)
    os.system('rm -f *')

    # Change to data directory
    os.chdir(dataDir)

    # Preallocate sum (mean) and count arrays matching grid dims
    mean =np.zeros((4401, 8001), np.single)
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

        # Loop through files and accumulate SST
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

        # A DOY from startDoy to end of start year
        fileList = []
        print(dataDir1)
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

            sstFile = Dataset(fName)
            sst = sstFile.variables["MBsstd"][:, :, :, :]
            sstFile.close()
            sst = np.squeeze(sst)
            mean, num = meanVar(mean, num, sst)

        # DOY from 1 to endDoy of end year
        os.chdir(dataDir)
        fileList = []
        doyRange = list(range(1, endDoy + 1))
        print(doyRange)
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
            mean, num = meanVar(mean, num, sst)

    # Mask out any grid cells with zero observations, setting them to the fill value
    mean = ma.array(mean, mask=(num == 0), fill_value=-9999999.)

    # Switch to the working directory for output operations
    os.chdir(workDir)

    # Construct the output filename with start and end dates plus data types
    outFile = 'MB' + startYearC + startDoyC + '_' + endyearC + endDoyC + '_' + dtype + '.nc'
    print(interval)

    # Create multi-day NetCDF file using the mean and count arrays
    ncFile = makeNetcdf(mean, num, interval, outFile, filesUsed, workDir)

    # Upload composite NetCDF to remote MB SST directory, labeling it with the interval
    send_to_servers(ncFile, '/MB/sstd/', str(interval))
