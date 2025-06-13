"""
Overview
--------
Generate a one-day ocean-color (Chla) grid for the MODIS “MB” (Pacific Ocean) product by
combining swaths from Level-2 chlorophyll-a NetCDF files and gridding them with PyGMT. The
script produces a CF-compliant NetCDF file of daily Chla for the Pacific Ocean region (lon 120-320°, lat -45-65°).

Usage
-----
::
  
     python makeChla1daynewMB.py <dataDirBase> <workDir> <year> <doy>

Where:

- ``dataDir``

  Root folder containing raw Level-2 ocean-color NetCDF swath files, organized as ``<dataDirBase>/<YYYY><MM>/``. Each swath must match: ``AQUA_MODIS.<YYYY><MM><DD>*L2.OC.NRT.nc``.

- ``workDir``

  Temporary working directory for staging swath copies and intermediate files.

- ``year``

  Four-digit year string (e.g., ``"2025"``).

- ``doy``

  Three-digit day-of-year string (zero-padded, e.g., ``"082"`` for March 23).

Description
-----------
1. **Date and Directory Setup**  

     - Computes calendar date from ``year`` + ``doy``, zero-pads month/day, and sets ``datadir = dataDirBase + YYYY + MM + "/"``.  
     
     - Also computes the next day's directory for early-morning swaths (``HOD ≤ 10``).

2. **Load Land Mask**  

     - Reads a static GRD land-mask from ``/u00/ref/landmasks/LM_120_320_0.025_-45_65_0.025_gridline.grd`` into ``my_mask``.

3. **Swath Discovery & Staging**

     - Globs ``AQUA_MODIS.<YYYY><MM><DD>*.L2.OC.NRT.nc`` in both current and next-day folders.

     - Copies swaths into ``workDir``, removing any old ``AQUA_MODIS.*L2.OC*`` or ``MB20*`` files.

4. **Swath Processing**

     For each swath:

         - Extracts navigation (``lon``, ``lat``), converts negative longitudes to 0-360°, and tests overlap with the MB region (lon 120-320°, lat -45-65°).

     - Filters only daytime pixels (``day_night_flag == "Day"``).

     - Reads chlorophyll-a (``chlor_a``), reshapes into column vectors, and stacks into ``(lon, lat, Chla)``.

     - Applies sequential filters:  

         • ``Chla > 0``

         • ``lonmin ≤ lon ≤ lonmax``

         • ``latmin ≤ lat ≤ latmax``

         • Discards any obviously invalid longitudes (``> -400``).

     - Accumulates valid points into ``temp_data`` and tracks provenance in ``filesUsed``.

5. **Gridding & NetCDF Generation**  

     - Uses ``pygmt.xyz2grd`` on ``temp_data`` with region ``120/320/-45/65`` and spacing ``0.025/0.025`` to produce a GMT ``.grd`` file named ``MB<YYYY><DDD>_<YYYY><DDD>_chla.grd``.
     
     - Converts the grid to a CF-compliant NetCDF via ``roylib.grd2netcdf1``, applying ``my_mask``.
     
     - Sends the final NetCDF into ``/MB/chla/1day/`` via ``roylib.send_to_servers``.

Dependencies
------------
- **Python 3.x**

- **Standard library**: ``os``, ``sys``, ``datetime``, ``timedelta``, ``glob``, ``re``, ``shutil``

- **Third-party**: ``netCDF4.Dataset``, ``numpy``, ``numpy.ma``, ``pygmt``  

- **Custom roylib functions**:  

     - ``myReshape(array)``

     - ``grd2netcdf1(grd, outName, filesUsed, mask, fType)``

     - ``safe_remove(filePath)``  

     - ``send_to_servers(ncFile, destDir, interval)``

     - ``isleap(year)``

     - ``makeNetcdf(mean, nobs, interval, outFile, filesUsed, workDir)``

     - ``meanVar(mean, num, obs)``

Land Mask
---------
A static GRD mask is required at:

 ``/u00/ref/landmasks/LM_120_320_0.025_-45_65_0.025_gridline.grd``  

to zero-out land pixels in the daily Chla grid.

Directory Structure
-------------------
- **Input directory** (datadir):

  ``<dataDirBase>/<YYYY><MM>/`` containing raw L2 OC files: ``AQUA_MODIS.<YYYY><MM><DD>*.L2.OC.NRT.nc``

- **Working directory** (workDir):

  Temporary staging area; cleared of ``AQUA_MODIS.*L2.OC*`` and ``MB20*`` at start.

- **Output grid** (fileOut):

  GMT “.grd” file named ``MB<YYYY><DDD>_<YYYY><DDD>_chla.grd``

- **Final NetCDF**:

  ``MB<YYYY><DDD>_<YYYY><DDD>_chla.nc``, copied to: ``/path/to/modis_data/modisgf/chla/1day/``

Usage Example
-------------
::  
  
     python makeChla1daynewMB.py /Users/you/modis_data/netcdf/ /Users/you/modis_work/ 2025 082

This will:

  - Download and stage all Level-2 OC swaths for March 23, 2025 (``HOD > 10`` and next day ``HOD ≤ 10``).

  - Build and grid the daily chlorophyll-a point cloud for the MB region.

  - Generate CF-compliant NetCDF and deploy to ``/modisgf/chla/1day/``.
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

    # Geographic bounds for MB region
    latmax = 65.
    latmin = -45.
    lonmax = 320.
    lonmin = 120.

    outFile = 'modisgfChlatemp'

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

    # Construct the directory path where raw swaths are stored for this date
    datadir = datadirBase + year + myMon + '/'

    # Next calendar day (for hours ≤ 10)
    myDate1 = myDate + timedelta(days=1)
    year1 = str(myDate1.year)
    doy1 = myDate1.strftime("%j").zfill(3)
    myMon1 = str(myDate1.month)
    myMon1 = myMon1.rjust(2, '0')
    myDay1 = str(myDate1.day).rjust(2, '0')
    datadir1 = datadirBase + year1 + myMon1 + '/'

    # Load static land mask from GRD
    mask_root = Dataset('/u00/ref/landmasks/LM_120_320_0.025_-45_65_0.025_gridline.grd')
    my_mask = mask_root.variables['z'][:, :]
    mask_root.close()

    # Now move to the data directory
    os.chdir(datadir)

    # Set up the string for the file search in the data directory
    #myString = 'A' + year + doy + '*.L2_LAC_OC.nc'
    myString = 'AQUA_MODIS.' + year + myMon + myDay + '*.L2.OC.NRT.nc'
    print(myString)

    # Get list of files in the data directory that match with full path
    fileList = glob.glob(myString)
    fileList.sort()

    # Now move to the work directory and clear old files
    os.chdir(workdir)
    os.system('rm -f AQUA_MODIS.*L2.OC*')
    os.system('rm -f MB20*')

    # Initialize variables to accumulate data and track provenance
    filesUsed = ""
    temp_data = None

    # Loop over swaths for hod > 10 
    for fName in fileList:
        fileName = fName
        # Extract hour of day from filename
        datetime = re.search('AQUA_MODIS.(.+?).L2.OC.NRT.nc', fileName)
        hodstr = datetime.group(1)[9:11]
        hod = int(hodstr)

        if (hod > 10):
            print(hod)
            print(fileName)

            # Stage the swath in the working directory
            shutil.copyfile(datadir + fName, workdir + fName)

            # Try to open the NetCDF; skip if the file is unreadable
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

            # Determine if swath overlaps our MW region
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
            # if(goodLon and goodLat):
                if (len(filesUsed) == 0):
                    filesUsed = fileName
                else:
                    filesUsed = filesUsed + ', ' + fileName

                # Reshape latitude & longitude arrays into column vectors
                latitude = myReshape(latitude)
                longitude = myReshape(longitude)

                # Access geophysical data group
                geoDataGroup = rootgrp.groups['geophysical_data']

                # Extract chlor_a
                chlor_a = geoDataGroup.variables['chlor_a'][:, :]
                chlor_a = myReshape(chlor_a)

                # Stack (lon, lat, chlor_a) into a single 2D array with shape (N, 3)
                dataOut = np.hstack((longitude, latitude, chlor_a))

                # Filter rows to keep only valid chlor_a (>0)
                dataOut = dataOut[dataOut[:, 2] > 0]
                dataOut = dataOut[dataOut[:, 0] > -400]
                dataOut = dataOut[dataOut[:, 0] >= lonmin]
                dataOut = dataOut[dataOut[:, 0] <= lonmax]
                dataOut = dataOut[dataOut[:, 1] >= latmin]
                dataOut = dataOut[dataOut[:, 1] <= latmax]

                # Accumulate into temp_data
                if(dataOut.shape[0] > 0):
                    if(temp_data is None):
                        temp_data = dataOut
                    else:
                        temp_data = np.concatenate((temp_data, dataOut), axis=0)

            # Clean up this swath
            rootgrp.close()
            safe_remove(fileName)

    # Repeat for hod ≤ 10 on the next day

    # Move back to data dir
    os.chdir(datadir1)

    # Set up the string for file matching of doy+1
    myString = 'AQUA_MODIS.' + year1 + myMon1 + myDay1 + '*.L2.OC.NRT.nc'
    fileList = glob.glob(myString)
    fileList.sort()

    # Change back to work directory
    os.chdir(workdir)

    for fName in fileList:
        fileName = fName

        # Find the datatime group in the filename
        datetime = re.search('AQUA_MODIS.(.+?).L2.OC.NRT.nc', fileName)
        hodstr = datetime.group(1)[9:11]
        hod = int(hodstr)
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

            #rootgrp = Dataset(fileName, 'r')

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

                latitude = myReshape(latitude)
                longitude = myReshape(longitude)

                geoDataGroup = rootgrp.groups['geophysical_data']

                chlor_a = geoDataGroup.variables['chlor_a'][:, :]
                chlor_a = myReshape(chlor_a)

                dataOut = np.hstack((longitude, latitude, chlor_a))

                dataOut = dataOut[dataOut[:, 2] > 0]
                dataOut = dataOut[dataOut[:, 0] > -400]
                dataOut = dataOut[dataOut[:, 0] >= lonmin]
                dataOut = dataOut[dataOut[:, 0] <= lonmax]
                dataOut = dataOut[dataOut[:, 1] >= latmin]
                dataOut = dataOut[dataOut[:, 1] <= latmax]

                if(dataOut.shape[0] > 0):
                    if(temp_data is None):
                        temp_data = dataOut
                    else:
                        temp_data = np.concatenate((temp_data, dataOut), axis=0)

            rootgrp.close()
            safe_remove(fileName)

    # Grid the combined Chla point cloud and write outputs
    fileOut = 'MB' + year + doy + '_' + year + doy + '_chla.grd'
    range = '120/320/-45/65'
    increment = '0.025/0.025'
    temp_data1 = pygmt.xyz2grd(
        data=temp_data,
        region=range,
        spacing=increment,
    )

    # Convert the GMT grid to CF-compliant NetCDF, masking land
    ncFile = grd2netcdf1(temp_data1, fileOut, filesUsed, my_mask, 'MB')

    #myCmd = "mv " + ncFile + " /home/cwatch/pygmt_test/outfiles"
    #os.system(myCmd)

    # Copy to the MB server folder for chla (1-day product)
    send_to_servers(ncFile, '/MB/chla/' , '1')
    os.remove(ncFile)
