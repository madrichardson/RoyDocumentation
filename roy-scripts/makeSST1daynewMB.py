"""
Overview
--------
Generate a one-day SST grid for the MODIS “MB” (Pacific Ocean) dataset by combining swaths
from Level-2 SST NetCDF files over a two-day interval (current day and early hours of the
next day). The output is a CF-compliant NetCDF file containing daily SST on a regular grid
(lon 120-320°, lat -45-65°).

Usage
-----
::

    python makeSST1daynewMB.py <dataDir> <workDir> <year> <doy>

Where:

- ``dataDir``

  Base directory containing raw Level-2 SST NetCDF swaths, organized as ``<dataDirBase>/<YYYY><MM>/``. Each file must match ``AQUA_MODIS.<YYYY><MM><DD>T*.L2.SST.NRT.nc``.

- ``workDir``

  Temporary working directory. Swaths are copied here, intermediate files are created, and then cleaned up.

- ``year``

  Four-digit year string (e.g., ``"2025"``).

- ``doy``

  Three-digit day-of-year string (zero-padded, e.g., ``"082"`` for March 23).

Description
-----------
1. **Date and Directory Setup**

     - Convert ``year`` + ``doy`` to a calendar date (``myDate``), then extract zero-padded month (``myMon``) and day (``myDay``).
     
     - Compute next-day date (``myDate1``) and its year/month/day-of-year (``year1``, ``myMon1``, ``doy1``).
     
     Define:

         - ``datadir = dataDirBase + year + myMon + "/"``  
         - ``datadir1 = dataDirBase + year1 + myMon1 + "/"``

     These folders must contain the SST swath files for the current day and next day, respectively.
     
     - Load a static land-mask grid from ``/u00/ref/landmasks/LM_120_320_0.025_-45_65_0.025_gridline.grd`` into ``my_mask``.

2. **Swath Discovery (Day N, HOD > 10)**  

     - Change directory to ``datadir``.
     
     - Build glob pattern: ``AQUA_MODIS.<year><myMon><myDay>*.L2.SST.NRT.nc``
     
     - Sort matching files into ``fileList``.
     
     - Change into ``workDir``, then remove any stale files matching ``AQUA_MODIS.*L2.SST*`` or ``MB20*``.

3. **Loop Over Each Swath for Day N (HOD > 10)**  

     For each ``fName`` in ``fileList``:

     a. Extract hour-of-day (HOD) from the filename.
     
     b. If ``HOD > 10``, copy the swath from ``datadir`` to ``workDir`` and open with ``netCDF4.Dataset`` (skip if unreadable).
      
     c. Read ``navigation_data`` (``latitude``, ``longitude``), convert negative longitudes to 0-360°. Compute swath extents and test geographic overlap:  

         - Longitude overlaps [120°, 320°]
         
         - Latitude overlaps [-45°, 65°]
         
         - ``day_night_flag == "Day"``
         
         If all true, append the filename to ``filesUsed``.

      d. Reshape variables using ``myReshape`` and read from ``geophysical_data``:

         - ``sst`` (sea surface temperature)
         
         - ``qual_sst`` (quality flag)
        
         Flatten quality flags, stack ``longitude``, ``latitude``, ``sst`` into ``dataOut``, and filter:
         
           - ``qual_sst < 3``
         
           - SST > -2 °C
         
           - Longitude between 120° and 320°
         
           - Latitude ≤ 65°
         
         Accumulate valid points into ``temp_data``.

   e. Close the NetCDF and remove the copied swath from ``workDir`` using ``safe_remove``.

4. **Swath Discovery (Day N+1, HOD ≤ 10)**

     - Change directory to ``datadir1``.
     
     - Build glob pattern: ``AQUA_MODIS.<year1><myMon1><myDay1>*.L2.SST.NRT.nc``
     
     - Sort into ``fileList``.
     
     - Change back into ``workDir``.

5. **Loop Over Each Swath for Day N+1 (HOD ≤ 10)**

     For each ``fName`` in ``fileList``:
     
       - Extract HOD; if ``HOD ≤ 10``, copy swath from ``datadir1`` to ``workDir`` and repeat steps 3b-3e (navigation, quality/filter, accumulate into ``temp_data``).

6. **Gridding Swath Point Cloud**

     - After processing both sets of swaths, define output grid filename: ``MB<year><doy>_<year><doy>_sstd.grd``

     - Set PyGMT region and spacing:

         - ``region = "120/320/-45/65"``

         - ``spacing = "0.025/0.025"``

     - Call:

     ::

         pygmt.xyz2grd(
             data=temp_data,
             region=region,
             spacing=spacing
         )

     to produce a gridded ``xarray.DataArray`` (``temp_data1``).

7. **Convert to NetCDF and Send to Server**

     - Invoke: ``ncFile = grd2netcdf1(temp_data1, fileOut, filesUsed, my_mask, "MB")`` from ``roylib``: 

     - Masks out land using ``my_mask`` (set land to NaN).

     - Computes coverage metrics (# observations, % coverage).

     - Uses a CDL template to generate an empty CF-compliant NetCDF via ``ncgen``.

     - Populates coordinates, SST values, metadata, and a center-time stamp.

     - Returns the final NetCDF filename (``MB<year><doy>_<year><doy>_sstd.nc``).

   - Call:

     ::

          send_to_servers(ncFile, "/MB/sstd/", "1")

     to copy the NetCDF into ``/MB/sstd/1day/``.

     Finally, remove the local NetCDF copy.

Dependencies
------------
- **Python 3.x**

- **Standard library:** ``os``, ``glob``, ``re``, ``shutil``, ``sys``, ``datetime``, ``timedelta``, ``chain``

- **Third-party**: ``netCDF4.Dataset``, ``numpy``, ``numpy.ma``, ``pygmt``  

- **Custom roylib functions:**

   - ``myReshape(array)``
  
   - ``grd2netcdf1(grd, outName, filesUsed, mask, fType)``

   - ``safe_remove(filePath)``  

   - ``send_to_servers(ncFile, destDir, interval)``

   - ``isleap(year)``

   - ``makeNetcdf(mean, nobs, interval, outFile, filesUsed, workDir)``

   - ``meanVar(mean, num, obs)``

Land Mask
---------
- A static GRD file is required at:

  ``/u00/ref/landmasks/LM_120_320_0.025_-45_65_0.025_gridline.grd``

Directory Structure
-------------------
- **Input swaths directory (Day N)**:

  ``<dataDirBase>/<YYYY><MM>/`` containing files named ``AQUA_MODIS.<YYYY><MM><DD>T*.L2.SST.NRT.nc``.

- **Input swaths directory (Day N+1)**:
  
  ``<dataDirBase>/<YYYY1><MM1>/`` containing the early-hour swaths.

- **Working directory** (workDir): 
  
  Temporary location where swaths are copied, processed, and removed.

- **Output grid** (fileOut):  
  
  A GMT “.grd” file named ``MB<year><doy>_<year><doy>_sstd.grd``.

- **Final NetCDF** (returned by ``grd2netcdf1``): 
  
  Named ``MB<year><doy>_<year><doy>_sstd.nc``, then copied to ``/MB/sstd/1day/``.

Usage Example
-------------
Assume your raw SST swaths are in ``/Users/you/modis_data/netcdf/202503/`` and your working directory is ``/Users/you/modis_work/``

::

    python makeSST1daynewMB.py /Users/you/modis_data/netcdf/ \
                              /Users/you/modis_work/ \
                              2025 082

This will:

  - Copy all swaths from March 23 with HOD > 10 into “/Users/you/modis_work/”.

  - Copy early swaths from March 24 with HOD ≤ 10 into “/Users/you/modis_work/”.

  - Build a combined point cloud from valid “Day” pixels from lon 120-320°, lat -45-65°.

  - Create “MB2025082_2025082_sstd.grd” via PyGMT ``xyz2grd``.

  - Convert the grid to “MB2025082_2025082_sstd.nc” using ``grd2netcdf1``.

  - Copy the NetCDF to “/MB/sstd/1day/” and remove local copies.
"""
from __future__ import print_function
from builtins import str

if __name__ == "__main__":
    from datetime import datetime, timedelta
    import glob
    from itertools import chain
    from netCDF4 import Dataset
    import numpy as np
    import numpy.ma as ma
    import pygmt
    import os
    import re
    import shutil
    import sys

    # Ensure 'roylib' is on the import path
    sys.path.append('/home/cwatch/pythonLibs')
    from roylib import *

    # Geographic bounds for MW region
    latmax = 65.
    latmin = -45.
    lonmax = 320.
    lonmin = 120.

    outFile = 'modisgfSSTtemp'

    # Set data directory
    datadirBase = sys.argv[1]

    # Set work directory
    workdir = sys.argv[2]

    # Get the year and doy from the command line
    year = sys.argv[3]
    doy = sys.argv[4]
    print(year)
    print(doy)

    # Convert year/doy to a calendar date and zero-pad month/day
    myDate = datetime(int(year), 1, 1) + timedelta(int(doy) - 1)
    myMon = str(myDate.month)
    myMon = myMon.rjust(2, '0')
    myDay = str(myDate.day).rjust(2, '0')

    # Directory for day N's raw swaths: <datadirBase>/<year>/<myMon>/
    datadir = datadirBase + year + myMon + '/'

    # Compute actual calendar date from year + day
    myDate1 = myDate + timedelta(days=1)
    year1 = str(myDate1.year)
    doy1 = myDate1.strftime("%j").zfill(3)
    myMon1 = str(myDate1.month)
    myMon1 = myMon1.rjust(2, '0')
    myDay1 = str(myDate1.day).rjust(2, '0')
    print(myDate)
    print(myDate1)
    print(year1)
    print(myMon1)

    # Directory for day N + 1's raw swaths: <datadirBase>/<year1>/<myMon1>/
    datadir1 = datadirBase + year1 + myMon1 + '/'

    # Load static land mask grid from GRD
    mask_root = Dataset('/u00/ref/landmasks/LM_120_320_0.025_-45_65_0.025_gridline.grd')
    my_mask = mask_root.variables['z'][:, :]
    mask_root.close()

    # Now move to the data directory
    os.chdir(datadir)

    # Set up the string for the file search in the data directory
    myString = 'AQUA_MODIS.' + year + myMon + myDay + '*.L2.SST.NRT.nc'
    print(myString)

    # Get list of files in the data directory that match with full path
    fileList = glob.glob(myString)
    # print(fileList)
    fileList.sort()

    # Now move to the work directory and clear old files
    os.chdir(workdir)
    os.system('rm -f AQUA_MODIS.*L2.SST*')
    os.system('rm -f MB20*')

    # Prepare variables to accumulate point-cloud data and track provenance
    temp_data = None
    filesUsed = ""

    # Loop through each swath filename for Day N
    for fName in fileList:
        fileName = fName

        # Extract Hour-Of-Day (hod) from filename via
        datetime = re.search('AQUA_MODIS.(.+?).L2.SST.NRT.nc', fileName)
        hodstr = datetime.group(1)[9:11]
        hod = int(hodstr)

        # Only process swaths acquired after hod > 10 
        if (hod > 10):
            print(hod)
            print(fileName)

            # Copy swath from datadir into workdir for processing
            shutil.copyfile(datadir + fName, workdir + fName)

            # Attempt to open the NetCDF; skip if unreadable
            try:
                rootgrp = Dataset(fileName, 'r')
            except IOError:
                print("bad file " + fileName)
                continue

            # Extract navigation-group data
            navDataGroup = rootgrp.groups['navigation_data']
            latitude = navDataGroup.variables['latitude'][:, :]
            longitude = navDataGroup.variables['longitude'][:, :]

            # Convert any negative longitudes to the 0-360° domain
            longitude[longitude < 0] = longitude[longitude < 0] + 360

            # Compute swath extents (min/max) for geographic filtering
            dataLonMin = np.nanmin(longitude[longitude >= 0])
            dataLonMax = np.nanmax(longitude[longitude <= 360])
            dataLatMin = np.nanmin(latitude[latitude >= -90])
            dataLatMax = np.nanmax(latitude[latitude <= 90])

            # Determine if swath overlaps our MB region (lon 120-320, lat -45-65)
            goodLon1 = (dataLonMin < lonmin) and (dataLonMax >= lonmin)
            goodLon2 = (dataLonMin >= lonmin) and (dataLonMin <= lonmax)
            goodLon = goodLon1 or goodLon2

            goodLat1 = (dataLatMin < latmin) and (dataLatMax >= latmin)
            goodLat2 = (dataLatMin >= latmin) and (dataLatMin <= latmax)
            goodLat = goodLat1 or goodLat2

            # Check if swath is daytime (only keep "Day" pixels)
            dayNightTest = (rootgrp.day_night_flag == 'Day')

            # Only proceed if geography and day-night tests pass
            if (goodLon and goodLat and dayNightTest):
                # Add filename to provenance list
                if (len(filesUsed) == 0):
                    filesUsed = fileName
                else:
                    filesUsed = filesUsed + ', ' + fileName

                # Extract geophysical data and reshape
                longitude = myReshape(longitude)
                latitude = myReshape(latitude)
                geoDataGroup = rootgrp.groups['geophysical_data']
                sst = geoDataGroup.variables['sst'][:, :]
                sst = myReshape(sst)
                qual_sst = geoDataGroup.variables['qual_sst'][:, :]
                qual_sst = myReshape(qual_sst)

                # Filter out low-quality pixels (qual_sst < 3)
                qualTest = qual_sst < 3
                qualTest = qual_sst < 3
                qualTest = qualTest.flatten()

                # Stack (lon, lat, sst) into a single 2D array with shape (N, 3)
                dataOut = np.hstack((longitude, latitude, sst))

                # Apply quality mask, valid SST > -2°C and geographic bounds
                dataOut = dataOut[qualTest]
                dataOut = dataOut[dataOut[:, 2] > -2]
                dataOut = dataOut[dataOut[:, 0] > -400]
                dataOut = dataOut[dataOut[:, 0] >= lonmin]
                dataOut = dataOut[dataOut[:, 0] <= lonmax]
                dataOut = dataOut[dataOut[:, 1] <= latmax]

                # Accumulate into temp_data array
                if (dataOut.shape[0] > 0):
                    if (temp_data is None):
                        temp_data = dataOut
                    else:
                        temp_data = np.concatenate((temp_data, dataOut), axis=0)

            # Close the NetCDF and remove swath from workdir
            rootgrp.close()
            safe_remove(fileName)

    # Process swaths for Day N+1 (hod ≤ 10)
    # Move back to data dir
    print(datadir1)
    os.chdir(datadir1)

    # Set up the string for file matching of doy+1
    myString = 'AQUA_MODIS.' + year1 + myMon1 + myDay1  + '*.L2.SST.NRT.nc'
    fileList = glob.glob(myString)
    fileList.sort()

    # Switch back to workdir for processing
    os.chdir(workdir)
    for fName in fileList:
        fileName = fName

        # Extract hod again
        datetime = re.search('AQUA_MODIS.(.+?).L2.SST.NRT.nc', fileName)
        hodstr = datetime.group(1)[9:11]
        hod = int(hodstr)

        # Only process early swaths (hod ≤ 10) from Day N+1
        if (hod <= 10):
            print(hod)
            print(fileName)

            # cp file from work directory to
            shutil.copyfile(datadir1 + fName, workdir + fName)
            try:
                rootgrp = Dataset(fileName, 'r')
            except IOError:
                print("bad file " + fileName)
                continue

            navDataGroup = rootgrp.groups['navigation_data']
            latitude = navDataGroup.variables['latitude'][:, :]
            longitude = navDataGroup.variables['longitude'][:, :]
            longitude[longitude < 0] = longitude[longitude < 0] + 360
            dataLonMin = np.nanmin(longitude[longitude >= 0])
            dataLonMax = np.nanmax(longitude[longitude <= 360])
            dataLatMin = np.nanmin(latitude[latitude >= -90] )
            dataLatMax = np.nanmax(latitude[latitude <= 90] )

            goodLon1 = (dataLonMin < lonmin) and ( dataLonMax >= lonmin)
            goodLon2 = (dataLonMin >= lonmin) and (dataLonMin <= lonmax)
            goodLon = goodLon1 or goodLon2
            goodLat1 = (dataLatMin < latmin) and (dataLatMax >= latmin)
            goodLat2 = (dataLatMin >= latmin) and (dataLatMin <= latmax)
            goodLat = goodLat1 or goodLat2

            dayNightTest = (rootgrp.day_night_flag == 'Day')

            if (goodLon and goodLat and dayNightTest):
                if (len(filesUsed) == 0):
                    filesUsed = fileName
                else:
                    filesUsed = filesUsed + ', ' + fileName

                longitude = myReshape(longitude)
                latitude = myReshape(latitude)
                geoDataGroup = rootgrp.groups['geophysical_data']
                sst = geoDataGroup.variables['sst'][:, :]
                sst = myReshape(sst)
                qual_sst = geoDataGroup.variables['qual_sst'][:, :]
                qual_sst = myReshape(qual_sst)
                qualTest = qual_sst < 3
                qualTest = qualTest.flatten()

                dataOut = np.hstack((longitude, latitude, sst))
                dataOut = dataOut[qualTest]
                dataOut = dataOut[dataOut[:, 2] > -2]
                dataOut = dataOut[dataOut[:, 0] > -400]
                dataOut = dataOut[dataOut[:, 0] >= lonmin]
                dataOut = dataOut[dataOut[:, 0] <= lonmax]
                dataOut = dataOut[dataOut[:, 1] >= latmin]
                dataOut = dataOut[dataOut[:, 1] <= latmax]
    
                if (dataOut.shape[0] > 0):
                    if (temp_data is None):
                        temp_data = dataOut
                    else:
                        temp_data = np.concatenate((temp_data, dataOut), axis=0)

            # Close the NetCDF and remove swath from workdir
            rootgrp.close()
            safe_remove(fileName)

    # Build GMT grid from accumulated point cloud
    # Define output grid filename for PyGMT
    fileOut = 'MB' + year + doy + '_' + year + doy + '_sstd.grd'
    range = '120/320/-45/65'
    increment = '0.025/0.025'

    # Use PyGMT xyz2grd to interpolate scattered (lon, lat, sst) into a regular grid
    temp_data1 = pygmt.xyz2grd(
        data=temp_data,
        region=range,
        spacing=increment,
    )

    # Convert GMT grid to CF-compliant NetCDF and send to server
    ncFile = grd2netcdf1(temp_data1, fileOut, filesUsed, my_mask, 'MB')

    #myCmd = "mv " + ncFile + " /home/cwatch/pygmt_test/outfiles"
    #os.system(myCmd)

    # Copy the resulting NetCDF to the "MB" server folder for 1-day products
    send_to_servers(ncFile, '/MB/sstd/', '1')

    # Remove local NetCDF copy from working directory
    os.remove(ncFile)
