"""
Overview
--------
Download MODIS Near-Real-Time (NRT) Level-2 SST and Chla files for the last four days,
then generate 1-day and multi-day composites for both MB (Pacific Ocean) and MW (West Coast) products.

Usage
-----
::

    python newGetModis.py <baseDataDir>

Where:

- ``<baseDataDir>``

  Root directory containing subfolders named ``<YYYY><MM>`` (e.g., “202503”), each holding raw Level-2 NetCDF files.

Description
-----------
1. **Scan the past four days** (lags -3, -2, -1, 0 relative to now):

  - Compute ``YYYY``, ``MM``, ``DDD`` for each lag.

  - Change into ``<baseDataDir>/<YYYY><MM>/``.

  - Call ``retrieve_new_files(..., 'SST', ...)`` to fetch missing SST L2 files.

  - Call ``retrieve_new_files(..., 'OC', ...)`` to fetch missing ocean-color (Chla) L2 files.

2. **Record which days had new data**

  - Two boolean arrays ``newSST`` and ``newOC`` track when new files were downloaded.

3. **Generate 1-day composites**

  - For each day flagged true, run external scripts for MB and MW variants:

    - MB (Pacific Ocean): ``makeSST1daynewMB.py`` / ``makeChla1daynewMB.py``

    - MW (West Coast): ``makeSST1daynewMW.py`` / ``makeChla1daynewMW.py``

4. **Generate multi-day composites**

  - For intervals “3”, “5”, “8”, “14”: if any day in the preceding window had new data, invoke MB composite scripts (``CompMBSST.py``, ``CompMBChla.py``) and MW composite scripts (``CompMWSST.py``, ``CompMWChla.py``).

Dependencies
------------
- **Python 3.x** 

- **Standard library:** ``os``, ``sys``, ``datetime``, ``timedelta``

- **Custom roylib functions:**

  - ``retrieve_new_files(dataDir, param, year, doy, flag_list, lag)`` 

  - ``update_modis_1day(now, baseDir, param, flag_list)`` 

  - ``update_modis_composite(now, baseDir, param, flag_list, composite_interval)``

Directory Structure
-------------------
Assuming ``<baseDataDir>`` is ``/path/to/modis/netcdf/``:

    /path/to/modis/netcdf/

        202501/    # Raw L2 files for January 2025

        202502/    # Raw L2 files for February 2025

        202503/    # Raw L2 files for March 2025
        …

Each ``<YYYYMM>/`` folder contains files like:

    AQUA_MODIS.20250321T000001.L2.SST.NRT.nc
    AQUA_MODIS.20250321T000001.L2.OC.NRT.nc
    …

After running:

- **1-day composites** saved in:
    /path/to/modis/data/modiswc/1day/      # MW-processed SST/Chla
    /path/to/modis/data/modisgf/1day/      # MB-processed SST/Chla

- **Multi-day composites** saved in:
    /path/to/modis/data/modiswc/<N>day/    # MW composites (3,5,8,14)
    /path/to/modis/data/modisgf/<N>day/    # MB composites (3,5,8,14)

Usage Example
-------------
::

   python newGetModis.py /Users/yourname/Roy/modis_data/netcdf

This will:

  - Download missing L2 SST/Chla files for the last four days.

  - Create 1-day SST and Chla products where new data arrived.

  - Produce 3-, 5-, 8-, and 14-day composites for both MW and MB datasets.
"""
from __future__ import print_function
from builtins import str
from builtins import range
if __name__ == "__main__":
    from datetime import date, datetime, timedelta
    import os
    import sys

    # Ensure 'roylib' is on the import path
    sys.path.append('/home/cwatch/pythonLibs')
    from roylib import *

    # Base directory for raw L2 NetCDF files (arg 1)
    basedataDir = sys.argv[1]

    # Current timestamp
    now = datetime.now()

    # Flags to track which of the last 4 days have new SST or OC data
    newSST = ([False, False, False, False])
    newOC = ([False, False, False, False])

    # Loop over the past 4 calendar days: lags -3, -2, -1, 0
    for lag in list(range(-3, 1)):
        myDate1 = now + timedelta(days=lag)
        myYear = str(myDate1.year)
        myMon = str(myDate1.month)
        myMon = myMon.rjust(2, '0')
        doy = myDate1.strftime("%j").zfill(3)
        print('doy: ' + str(doy))

        # Directory where raw L2 files for this YYYYMM live
        dataDir = basedataDir + myYear + myMon
        print(dataDir)
        os.chdir(dataDir)

        # Fetch SST L2 files if missing
        print('start retrieve SST')
        retrieve_new_files(dataDir, 'SST', myYear, doy, newSST, lag)
        print('done retrieve SST')

        # get SST data
        # modisSSTURL = '"https://oceandata.sci.gsfc.nasa.gov/search/file_search.cgi?search=A' + myYear + doy + '*L2_LAC_SST.nc&dtype=L2&sensor=aqua&results_as_file=1"'
        # modisSSTURL = 'search=A' + myYear + doy + '*L2_LAC_SST.nc&dtype=L2&sensor=aqua&results_as_file=1'
        # fileList = url_lines(modisSSTURL)
        # for fName in fileList[2:]:
            # fileTest = os.path.isfile(dataDir + '/' + fName)
            # if(not(fileTest)):
                # newSST[lag + 3] = True
                # print(fName)
                # get_netcdfFile(fName)

        # Fetch Chla (OC) L2 files if missing
        print('start retrieve OC')
        retrieve_new_files(dataDir, 'OC', myYear, doy, newOC, lag)
        print('Done retrieve OC')

        # get OC data
        # modisOCURL = '"https://oceandata.sci.gsfc.nasa.gov/search/file_search.cgi?search=A' + myYear + doy + '*L2_LAC_OC.nc&dtype=L2&sensor=aqua&results_as_file=1"'
        # modisOCURL = 'search=A' + myYear + doy + '*L2_LAC_OC.nc&dtype=L2&sensor=aqua&results_as_file=1'
        # fileList = url_lines(modisOCURL)
        # print(fileList[2:])
        # for fName in fileList[2:]:
            # fileTest = os.path.isfile(dataDir + '/' + fName)
            # if(not(fileTest)):
                # newOC[lag + 3] = True
                # print(fName)
                # get_netcdfFile(fName)

    # Print which days actually had new downloads
    print('newSST')
    print(newSST)
    print('newOC')
    print(newOC)

    # Generate 1-day composties for SST and Chla
    update_modis_1day(now, basedataDir, 'SST', newSST)
    update_modis_1day(now, basedataDir, 'Chla', newOC)

    # Generate 3-day composties for SST and Chla
    update_modis_composite(now, basedataDir, 'SST', newSST, '3')
    update_modis_composite(now, basedataDir, 'Chla', newOC, '3')

    # Generate 5-day composties for SST and Chla
    update_modis_composite(now, basedataDir, 'SST', newSST, '5')
    update_modis_composite(now, basedataDir, 'Chla', newOC, '5')

    # Generate 8-day composties for SST and Chla
    update_modis_composite(now, basedataDir, 'SST', newSST, '8')
    update_modis_composite(now, basedataDir, 'Chla', newOC, '8')

    # Generate 14-day composties for SST and Chla
    update_modis_composite(now, basedataDir, 'SST', newSST, '14')
    update_modis_composite(now, basedataDir, 'Chla', newOC, '14')
