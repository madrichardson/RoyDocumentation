"""
Overview
--------
Generate one-day chlorophyll-a (Chla) and related ocean-color products for the “MW” (West Coast) region by combining MODIS Level-2 swath granules and gridding them with PyGMT. This script produces CF-compliant NetCDF files for Chla, Kd490, PAR(0), and fluorescence line height (cflh), then copies them into the appropriate server directories.

Usage
-----
::
 
     python makeChla1daynewMW.py <dataDir> <workDir> <year> <doy>

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
1. **Parse command-line arguments**

     - Read ``dataDir``, ``workDir``, ``year``, and ``doy`` from ``sys.argv``.

     - Print ``year`` and ``doy`` for logging.

2. **Convert ``year`` + ``doy`` to calendar date**

     - Compute a ``datetime`` object for the specified day of year.

     - Zero-pad month and day to form ``MM`` and ``DD``.

     - Construct ``datadir = dataDir + year + MM + "/"``, which must contain all raw L2 OC swath files for that date.

3. **Load static land mask**

     - Open GRD mask file at: ``/u00/ref/landmasks/LM_205_255_0.0125_22_51_0.0125_gridline.grd``

     - Read the 2D mask array ``my_mask`` (1 = ocean, other = land).

     - Close the mask dataset.

4. **List all swath granules for the given date**

     - Change into ``datadir``.

     - Build a glob pattern: ``"AQUA_MODIS.<year><MM><DD>*.L2.OC.NRT.nc"``.

     - Retrieve and sort all matching filenames.

5. **Prepare working directory**

     - Change into `workDir`.

     - Remove any stale files matching:

         - ``AQUA_MODIS.*L2.OC*``

         - ``MW20*``

6. **Initialize data accumulators**

     - ``filesUsed``: comma-separated string for provenance of processed swaths.

     - ``temp_data_Chla``, ``temp_data_k490``, ``temp_data_par0``, ``temp_data_flh``: accumulate (lon, lat, value) rows for each parameter.

7. **Loop over each OC swath granule**

     For each ``fName`` in the sorted list:

     a. **Copy swath to work directory & open NetCDF**

         - Copy from ``datadir`` to ``workDir``.

         - Attempt ``Dataset(fileName, 'r')``; skip if IOError.

     b. **Extract navigation data**

         - Read ``latitude`` and ``longitude`` from ``rootgrp.groups['navigation_data']``.

         - Convert negative longitudes (< 0) to 0-360°.

         - Compute ``dataLonMin``, ``dataLonMax``, ``dataLatMin``, ``dataLatMax`` for geographic filtering.

     c. **Determine if swath overlaps the MW region**

         - Region bounds: ``lon ∈ [205, 255]`` and ``lat ∈ [22, 51]``.

         - ``goodLon = True`` if any longitudes fall within [205, 255].

         - ``goodLat = True`` if any latitudes fall within [22, 51].

         - Proceed only if ``goodLon and goodLat``.

     d. **Record filename for provenance**

         - Append ``fileName`` to ``filesUsed`` (comma-separated).

     e. **Reshape navigation arrays**

         - Call ``myReshape(latitude)`` → column vector (Nx1).

         - Call ``myReshape(longitude)``.

     f. **Extract and filter each parameter**

      For each variable in ``geophysical_data``:

        1. **Chlorophyll-a (chlor_a)**

             - Read and reshape: ``chlor_a = myReshape(rootgrp.groups['geophysical_data'].variables['chlor_a'][:, :])``

             - Stack: ``dataOut = np.hstack((longitude, latitude, chlor_a))``

             - Filter:

                 - ``dataOut[:, 0] > -400``

                 - ``lonmin ≤ dataOut[:, 0] ≤ lonmax``

                 - ``latmin ≤ dataOut[:, 1] ≤ latmax``

                 - ``chlor_a > 0``

             - Accumulate into ``temp_data_Chla``.

         2. **Kd490 (Kd_490)**

             - Read, optionally scale, reshape, and stack with (lon, lat).

             - Filter:

                 - valid lon/lat as above,

                 - ``0 < Kd490 < 6.3``

             - Accumulate into ``temp_data_k490``.

         3. **PAR(0) (par)**
    
             - Read, optionally scale, reshape, and stack.

             - Filter:

                 - valid lon/lat,

                 - ``PAR > 0``

             - Accumulate into ``temp_data_par0``.

         4. **Fluorescence Line Height (cflh)**

             - Read, optionally scale, reshape, and stack.

             - Filter:

                 - valid lon/lat,

                 - ``cflh > 0``

            - Accumulate into ``temp_data_flh``.

     g. **Cleanup**

         - ``rootgrp.close()``

         - ``os.remove(fileName)`` from ``workDir``.

8. **Grid each parameter's point cloud with PyGMT**

     For each of ``temp_data_Chla``, ``temp_data_k490``, ``temp_data_par0``, ``temp_data_flh``:

     - Set:
         - ``region = "205/255/22/51"``

         - ``spacing = "0.0125/0.0125"``

         - ``search_radius = "2k"``

         - ``sectors = "1"``

     - Call:

     ::

         temp_data1 = pygmt.nearneighbor(
             data=temp_data_<param>,
             region=region,
             spacing=spacing,
             search_radius=search_radius,
             sectors="1"
         )

     - This returns a PyGMT grid (xarray.DataArray) covering the specified region.

9. **Convert grid(s) to CF-compliant NetCDF & send to server**

     - Call:

     ::

         ncFile = grd2netcdf1(temp_data1, fileOut, filesUsed, my_mask, "MW")

     - Masks land, computes coverage, builds CF NetCDF via CDL, and returns the NetCDF path.

     - Call:

     ::

         send_to_servers(ncFile, "/MW/<param>/", "1")

         - E.g. `send_to_servers(ncFile, "/MW/chla/", "1")`

     - Delete local NetCDF:

     ::

         os.remove(ncFile)

Dependencies
------------
- **Python 3.x**

- **Standard library:** ``sys``, ``os``, ``glob``, ``shutil``, ``re``, ``itertools.chain``, ``datetime``, ``timedelta``

- **Third-party packages:** ``netCDF4.Dataset``, ``numpy``, ``pygmt``

- **Custom roylib functions:**

  - ``myReshape(array)``
  
  - ``grd2netcdf1(grd, outName, filesUsed, mask, fType)``
  
  - ``send_to_servers(ncFile, destDir, interval)``
  
  - ``isleap(year)``
  
  - ``makeNetcdf(mean, nobs, interval, outFile, filesUsed, workDir)``
  
  - ``meanVar(mean, num, obs)``

Land Mask
---------
- A static GRD file is required at:

 ``/u00/ref/landmasks/LM_205_255_0.0125_22_51_0.0125_gridline.grd``
 
- This mask is applied to each gridded output to set land pixels to NaN.

Directory Structure
-------------------
- **Input swaths directory** (datadir):

  Directory for raw Level-2 OC NetCDF swath files for the given date, organized as ``<dataDirBase>/<YYYY><MM>/``. Each file must be named: ``AQUA_MODIS.<YYYY><MM><DD>*L2.OC.NRT.nc``

- **Working directory** (workDir):

  Temporary staging area where swaths are copied for processing and then deleted.

- **Output grid** (fileOut):

  GMT “.grd” file created by PyGMT nearneighbor, named: ``MW<YYYY><DDD>_<YYYY><DDD>_<param>.grd`` (e.g. ``MW2025082_2025082_chla.grd``).

- **Final NetCDF** (returned by ``grd2netcdf1``):

  CF-compliant NetCDF file named: ``MW<YYYY><DDD>_<YYYY><DDD>_<param>.nc`` Copied into the MW 1-day product directories, for example: ``/path/to/modis_data/modiswc/chla/1day/MW2025082_2025082_chla.nc``

Usage Example
-------------
Assume your raw OC swaths live in:

::

     /Users/you/modis_data/netcdf/202503/

and your working directory is:

::
 
     /Users/you/modis_work/

Then to produce March 23, 2025 products:

::

    python makeChla1daynewMW.py /Users/you/modis_data/netcdf/ \
                                /Users/you/modis_work/ \
                                2025 082

This will:

  - Copy all swaths matching ``AQUA_MODIS.20250323*.L2.OC.NRT.nc`` into ``/Users/you/modis_work/``.

  - Build combined point clouds for Chla, Kd490, PAR(0), and cflh.

  - Create PyGMT grids over lon 205-255°, lat 22-51° via ``nearneighbor``.

  - Convert each grid to a CF-compliant NetCDF using ``grd2netcdf1``, masked by the static GRD.

  - Copy the final NetCDFs to the appropriate MW 1-day product folders.
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
    latmax = 51.
    latmin = 22.
    lonmax = 255.
    lonmin = 205.

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

    # Construct the directory path where raw OC swaths are stored for this date
    datadir = datadirBase + year + myMon + '/'

    # Load static land mask from GRD
    mask_root = Dataset('/u00/ref/landmasks/LM_205_255_0.0125_22_51_0.0125_gridline.grd')
    my_mask = mask_root.variables['z'][:, :]
    mask_root.close()

    # Now move to the data directory
    os.chdir(datadir)

    # Set up the string for the file search in the data directory
    myString = 'AQUA_MODIS.' + year + myMon + myDay  + '*.L2.OC.NRT.nc'
    print(myString)

    # Get list of files in the data directory that match with full path
    fileList = glob.glob(myString)
    # print(fileList)
    fileList.sort()

    # Now move to the work directory and clear old files
    os.chdir(workdir)
    os.system('rm -f AQUA_MODIS.*L2.OC*')
    os.system('rm -f MW20*')

    # Do the whole thing for chla
    outFileChla = 'modiswcChlatemp'
    outFilek490 = 'modiswck490temp'
    outFilepar0 = 'modiswcpar0temp'
    outFilecflh = 'modiswccflhtemp'
    
    # Initialize variables to accumulate data and track provenance
    filesUsed = ""
    temp_data_Chla = None
    temp_data_k490 = None
    temp_data_par0 = None
    temp_data_flh = None

    # Loop over each OC swath granule for the given day
    for fName in fileList:
        fileName = fName
        # find the datatime group in the filename
        # check on what to search for
        #datetime = re.search('AQUA_MODIS(.+?).L2.NRT.OC', fileName)
        # will want elements 8,9 of datatime.group(1)
        print(fileName)

        # Copy the swath from datadir into the workdir
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

        # Determine if swath overlaps our global MW region
        goodLon1 = (dataLonMin < lonmin) and (dataLonMax >= lonmin)
        goodLon2 = (dataLonMin >= lonmin) and (dataLonMin <= lonmax)
        goodLon = goodLon1 or goodLon2

        goodLat1 = (dataLatMin < latmin) and (dataLatMax >= latmin)
        goodLat2 = (dataLatMin >= latmin) and (dataLatMin <= latmax)
        goodLat = goodLat1 or goodLat2

        # Check if swath is daytime (only keep "Day" pixels)
        dayNightTest = (rootgrp.day_night_flag == 'Day')

        # Only proceed if geography and day-night tests pass
        if (goodLon and goodLat):
            # Add filename to provenance list
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

            # Filter out-of-range lon/lat and non-positive chlor_a
            dataOut = dataOut[dataOut[:, 0] > -400]
            dataOut = dataOut[dataOut[:, 0] >= lonmin]
            dataOut = dataOut[dataOut[:, 0] <= lonmax]
            dataOut = dataOut[dataOut[:, 1] >= latmin]
            dataOut = dataOut[dataOut[:, 1] <= latmax]
            dataOut = dataOut[dataOut[:, 2] > 0]

            # Accumulate into temp_data_Chla
            if (dataOut.shape[0] > 0):
                if (temp_data_Chla is None):
                    temp_data_Chla = dataOut
                else:
                    temp_data_Chla = np.concatenate((temp_data_Chla, dataOut), axis=0)

            # Extract Kd490
            k490 = geoDataGroup.variables['Kd_490'][:, :]
            # k490 = k490 * 2.0E-4
            k490 = myReshape(k490)

            dataOut = np.hstack((longitude, latitude, k490))
            dataOut = dataOut[dataOut[:, 0] > -400]
            dataOut = dataOut[dataOut[:, 0] >= lonmin]
            dataOut = dataOut[dataOut[:, 0] <= lonmax]
            dataOut = dataOut[dataOut[:, 1] >= latmin]
            dataOut = dataOut[dataOut[:, 1] <= latmax]
            dataOut = dataOut[dataOut[:, 2] < 6.3]
            dataOut = dataOut[dataOut[:, 2] > 0]

            if (dataOut.shape[0] > 0):
                if (temp_data_k490 is None):
                    temp_data_k490 = dataOut
                else:
                    temp_data_k490 = np.concatenate((temp_data_k490, dataOut), axis=0)

            # Extract PAR0
            par0 = geoDataGroup.variables['par'][:, :]
            # par0 = (0.002 * par0) + 65.5
            par0 = myReshape(par0)

            dataOut = np.hstack((longitude, latitude, par0))
            dataOut = dataOut[dataOut[:, 0] > -400]
            dataOut = dataOut[dataOut[:, 0] >= lonmin]
            dataOut = dataOut[dataOut[:, 0] <= lonmax]
            dataOut = dataOut[dataOut[:, 1] >= latmin]
            dataOut = dataOut[dataOut[:, 1] <= latmax]
            dataOut = dataOut[dataOut[:, 2] > 0]

            if (dataOut.shape[0] > 0):
                if (temp_data_par0 is None):
                    temp_data_par0 = dataOut
                else:
                    temp_data_par0 = np.concatenate((temp_data_par0, dataOut), axis=0)

            # Extract Fluorescence Line Height (cflh)
            cflh = geoDataGroup.variables['nflh'][:, :]
            # cflh = 1.0E-5 * cflh
            cflh = myReshape(cflh)

            dataOut = np.hstack((longitude, latitude, cflh))
            dataOut = dataOut[dataOut[:, 2] > 0]
            dataOut = dataOut[dataOut[:, 0] > -400]
            dataOut = dataOut[dataOut[:, 0] >= lonmin]
            dataOut = dataOut[dataOut[:, 0] <= lonmax]
            dataOut = dataOut[dataOut[:, 1] >= latmin]
            dataOut = dataOut[dataOut[:, 1] <= latmax]
            dataOut = dataOut[dataOut[:, 2] > 0]

            if (dataOut.shape[0] > 0):
                if (temp_data_flh is None):
                    temp_data_flh = dataOut
                else:
                    temp_data_flh = np.concatenate((temp_data_flh, dataOut), axis=0)

        # Close the NetCDF and remove the swath file from workdir
        rootgrp.close()
        os.remove(fileName)

    # Grid and write each parameter's point cloud via PyGMT,
    #  then convert to NetCDF and send to server

    # chlor_a composite
    fileOut = 'MW' + year + doy + '_' + year + doy + '_chla.grd'
    range = '205/255/22/51'
    increment = '0.0125/0.0125'
    smooth = '2k'

    # Create a gridded dataset from the chlor_a point cloud
    temp_data1 = pygmt.nearneighbor(
        data=temp_data_Chla,
        region=range,
        spacing=increment,
        search_radius=smooth,
        sectors='1'
    )

    # Convert the GMT grid to CF-compliant NetCDF, masking land
    ncFile = grd2netcdf1(temp_data1, fileOut, filesUsed, my_mask, 'MW')

    #myCmd = "mv " + ncFile + " /home/cwatch/pygmt_test/outfiles"
    #os.system(myCmd)

    # Copy to the MW server folder for chla (1-day product)
    send_to_servers(ncFile, '/MW/chla/' , '1')
    os.remove(ncFile)

    # Kd490 composite
    #fileIn = outFilek490
    fileOut = 'MW' + year + doy + '_' + year + doy + '_k490.grd'
    range = '205/255/22/51'
    increment = '0.0125/0.0125'
    smooth = '2k'

    # Create a gridded dataset from the Kd490 point cloud
    temp_data1 = pygmt.nearneighbor(
        data=temp_data_k490,
        region=range,
        spacing=increment,
        search_radius=smooth,
        sectors='1'
    )

    # Convert the GMT grid to CF-compliant NetCDF, masking land
    ncFile = grd2netcdf1(temp_data1, fileOut, filesUsed, my_mask, 'MW')

    #myCmd = "mv " + ncFile + " /home/cwatch/pygmt_test/outfiles"
    #os.system(myCmd)

    # Copy to the MW server folder for k490 (1-day product)
    send_to_servers(ncFile, '/MW/k490/' , '1')
    os.remove(ncFile)

    # PAR(0) composite
    fileOut = 'MW' + year + doy + '_' + year + doy + '_par0.grd'
    range = '205/255/22/51'
    increment = '0.0125/0.0125'
    smooth = '2k'

    # Create a gridded dataset from the PAR(0) point cloud
    temp_data1 = pygmt.nearneighbor(
        data=temp_data_par0,
        region=range,
        spacing=increment,
        search_radius=smooth,
        sectors='1'
    )

    # Convert the GMT grid to CF-compliant NetCDF, masking land
    ncFile = grd2netcdf1(temp_data1, fileOut, filesUsed, my_mask, 'MW')

    #myCmd = "mv " + ncFile + " /home/cwatch/pygmt_test/outfiles"
    #os.system(myCmd)

    # Copy to the MW server folder for PAR(0) (1-day product)
    send_to_servers(ncFile, '/MW/k490/' , '1')  # Note: likely intended for '/MW/par0/'
    os.remove(ncFile)

    # cflh composite
    #fileIn = outFilecflh
    fileOut = 'MW' + year + doy + '_' + year + doy + '_cflh.grd'
    range = '205/255/22/51'
    increment = '0.0125/0.0125'
    smooth = '2k'

    # Create a gridded dataset from the cflh point cloud
    temp_data1 = pygmt.nearneighbor(
        data=temp_data_flh,
        region=range,
        spacing=increment,
        search_radius=smooth,
        sectors='1'
    )

    # Convert the GMT grid to CF-compliant NetCDF, masking land
    ncFile = grd2netcdf1(temp_data1, fileOut, filesUsed, my_mask, 'MW')

    #myCmd = "mv " + ncFile + " /home/cwatch/pygmt_test/outfiles"
    #os.system(myCmd)

    # Copy to the MW server folder for cflh (1-day product)
    send_to_servers(ncFile, '/MW/k490/' , '1')  # Note: likely intended for '/MW/cflh/'
    os.remove(ncFile)
