"""
Overview
--------
Generate a one-day SST grid for the MODIS “MW” (West Coast) region by combining swaths
from Level-2 SST NetCDF files and gridding them with PyGMT. The final product is a CF-compliant
NetCDF file containing daily SST for the MW region (lon 205-255°, lat 22-51°).

Usage
-----
::

    python makeSST1daynewMW.py <dataDir> <workDir> <year> <doy>

Where:

- ``dataDir``

  Directory containing raw Level-2 SST NetCDF swaths for the target date, organized as ``<dataDirBase>/<YYYY><MM>/``. Each file must follow the pattern: ``AQUA_MODIS.<YYYY><MM><DD>T*.L2.SST.NRT.nc``.

- ``workDir`` 

  Temporary working directory. Swath files are copied here, intermediate products are created, and then cleaned up.

- ``year``

  Four-digit year string (e.g., ``"2025"``).

- ``doy``

  Three-digit day-of-year string (zero-padded, e.g., ``"082"`` for March 23).

Description
-----------
1. **Date and Directory Setup**  

   - Convert ``year`` + ``doy`` to a calendar date (``myDate``), then extract zero-padded month (``myMon``) and day (``myDay``).

   - Define ``datadir = dataDirBase + year + myMon + "/"``. This folder must contain all SST swath NetCDF files for the date.

   - Load a static land-mask grid from ``/u00/ref/landmasks/LM_205_255_0.0125_22_51_0.0125_gridline.grd`` into ``my_mask``.

2. **Swath Discovery**  

   - Change directory to ``datadir``.

   - Build a glob pattern: ``AQUA_MODIS.<year><myMon><myDay>*.L2.SST.NRT.nc``.

   - Sort the resulting list of swath filenames (``fileList``).

3. **Data Staging and Cleanup**  

   - Change directory to ``workDir``.

   - Remove any existing temporary files matching ``AQUA_MODIS.*L2.SST*`` or ``MW20*`` to start fresh.

4. **Loop Over Each Swath**  

   For each file ``fName`` in ``fileList``:

   a. **Copy and Open**  

      - Copy the swath from ``datadir`` to ``workDir``.

      - Open with ``netCDF4.Dataset``. If unreadable, skip the swath.

   b. **Extract Navigation (Swath Geometry)**  

      - Read ``latitude`` and ``longitude`` from the ``navigation_data`` group.

      - Convert any negative longitudes to the 0-360° range.

      - Compute swath extents: ``dataLonMin``, ``dataLonMax``, ``dataLatMin``, ``dataLatMax``.

      - Define tests for geographic overlap:

       - Longitude overlaps 205°-255°. 

       - Latitude overlaps 22°-51°.  

      - Check ``day_night_flag == "Day"``.

      - Only if all tests pass, append the swath to ``filesUsed``.

   c. **Extract SST and Quality**  

      - In the ``geophysical_data`` group, read:

        - ``sst`` (sea surface temperature)

        - ``qual_sst`` (quality flag)  

      - Reshape ``sst``, ``latitude``, and ``longitude`` into column vectors using ``myReshape``.

      - Flatten ``qual_sst`` into a 1D mask array (``qual_sst1``).

      - Stack ``longitude``, ``latitude``, and ``sst`` into a 2D ``dataOut`` array.

      - Apply filters to ``dataOut``:

        - Quality flag < 2.  

        - Longitude between 205° and 255°. 

        - Latitude between 22° and 51°.  

        - SST > -2 °C.  

      - Concatenate valid points into a master array ``temp_data``.

   d. **Cleanup Swath File**  

      - Close the NetCDF dataset.

      - Delete the swath file from ``workDir``.

5. **Gridding Swath Point Cloud**  

   - After processing all swaths, define output grid filename: ``MW<year><doy>_<year><doy>_sstd.grd``.

   - Set PyGMT region and spacing:

      - ``region = "205/255/22/51"``  

     - ``spacing = "0.0125/0.0125"``  

     - ``search_radius = "2k"``  

     - ``sectors = "1"``  

   - Then run the following to produce a gridded ``xarray.DataArray`` (``temp_grid``):

   ::

       pygmt.nearneighbor(
           data=temp_data,
           region=region,
           spacing=spacing,
           search_radius=search_radius,
           sectors=sectors
       )

6. **Convert to NetCDF and Send to Server**  

   Invoke:

   ``grd2netcdf1(temp_grid, fileOut, filesUsed, my_mask, "MW")``

   from ``roylib``:

   - Applies ``my_mask`` to zero out land pixels.

   - Computes coverage statistics (# observations, % coverage).

   - Generates a CF-compliant NetCDF skeleton via ``ncgen`` + a CDL template.

   - Populates coordinates, SST data, metadata, and a center-time stamp.

   - Returns the new NetCDF filename (``MW<year><doy>_<year><doy>_sstd.nc``).

   Then run:

   ::

       send_to_servers(ncFile, "/MW/sstd/", "1")

   to copy the NetCDF into ``/MW/sstd/1day/``.

   Finally, remove the local NetCDF copy.

Dependencies
------------
- **Python 3.x**

- **Standard library:**  ``os``, ``glob``, ``re``, ``shutil``, ``sys``, ``datetime``, ``timedelta``

- **Third-party packages:** ``netCDF4.Dataset``, ``numpy``, ``pygmt`` 

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

  ``/u00/ref/landmasks/LM_205_255_0.0125_22_51_0.0125_gridline.grd``

- This mask is applied to the gridded SST to set land pixels to NaN.

Directory Structure
-------------------
- **Input swaths directory** (datadir):

  Must contain all Level-2 NetCDF swath files for the date, named: ``AQUA_MODIS.<YYYY><MM><DD>T*.L2.SST.NRT.nc``

- **Working directory** (workDir):  

  Temporary location where swaths are staged, processed, and removed.

- **Output grid** (fileOut):  

  A GMT “.grd” file named ``MW<year><doy>_<year><doy>_sstd.grd``.

- **Final NetCDF** (returned by grd2netcdf1):  

  Named ``MW<year><doy>_<year><doy>_sstd.nc``, then copied to ``/MW/sstd/1day/``.

Usage Example
-------------
Assume your raw SST swaths are in  ``/Users/you/modis_data/netcdf/202503/`` and your  working directory is ``/Users/you/modis_work/``:

::

    python makeSST1daynewMW.py /Users/you/modis_data/netcdf/202503/  /Users/you/modis_work/  2025 082

This will:

  - Copy all swaths matching ``AQUA_MODIS.20250323*.L2.SST.NRT.nc`` into ``/Users/you/modis_work/``.

  - Build a combined point cloud from valid “Day” pixels within the MW region.

  - Create ``MW2025082_2025082_sstd.grd`` via PyGMT nearneighbor.

  - Convert the grid to ``MW2025082_2025082_sstd.nc`` using ``grd2netcdf1``.

  - Copy the NetCDF to ``/MW/sstd/1day/`` and remove local copies.
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

    outFile = 'modiswcSSTtemp'

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

    # Construct the directory path
    datadir = datadirBase + year + myMon + '/'

    # Load static land mask from GRD
    mask_root = Dataset('/u00/ref/landmasks/LM_205_255_0.0125_22_51_0.0125_gridline.grd')
    my_mask = mask_root.variables['z'][:, :]
    mask_root.close()

    # Now move to the data directory
    os.chdir(datadir)

    # Set up the string for the file search in the data directory
    myString = 'AQUA_MODIS.' + year + myMon + myDay  + '*.L2.SST.NRT.nc'

    # Get list of files in the data directory that match with full path
    fileList = glob.glob(myString)
    # print(fileList)
    fileList.sort()

    # Now move to the work directory and clear old files
    os.chdir(workdir)
    os.system('rm -f AQUA_MODIS.*L2.SST*')
    os.system('rm -f MW20*')

    # Prepare variables to accumulate point-cloud data and track provenance
    filesUsed = ""
    temp_data = None

    # Loop through each swath filename for Day N
    for fName in fileList:
        fileName = fName
        print(fileName)
        shutil.copyfile(datadir + fName, workdir + fName)
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
        if (goodLon and goodLat and dayNightTest):
            # Add filename to provenance list
            if (len(filesUsed) == 0):
                filesUsed = fileName
            else:
                filesUsed = filesUsed + ', ' + fileName

            # Extract geophysical data and reshape
            geoDataGroup = rootgrp.groups['geophysical_data']
            sst = geoDataGroup.variables['sst'][:, :]
            sst = myReshape(sst)
            qual_sst = geoDataGroup.variables['qual_sst'][:, :]
            qual_sst1 = qual_sst.flatten()
            latitude = myReshape(latitude)
            longitude = myReshape(longitude)

            # Stack (lon, lat, sst) into a single 2D array with shape (N, 3)
            dataOut = np.hstack((longitude, latitude, sst))

            # Keep only quality < 2, valid SST > -2°C, and within MW region
            qualTest = qual_sst1 < 2
            dataOut = dataOut[qualTest]
            dataOut = dataOut[dataOut[:, 0] > -400]
            dataOut = dataOut[dataOut[:, 0] >= lonmin]
            dataOut = dataOut[dataOut[:, 0] <= lonmax]
            dataOut = dataOut[dataOut[:, 1] >= latmin]
            dataOut = dataOut[dataOut[:, 1] <= latmax]
            dataOut = dataOut[dataOut[:, 2] > -2]

            # Accumulate into temp_data array
            if (dataOut.shape[0] > 0):
                if (temp_data is None):
                    temp_data = dataOut
                else:
                    temp_data = np.concatenate((temp_data, dataOut), axis=0)

        # Close the NetCDF and remove swath copy from workdir
        rootgrp.close()
        os.remove(fileName)

    # Build and write the GMT grid from the accumulated point cloud
    # Define output grid filename
    fileOut = 'MW' + year + doy + '_' + year + doy + '_sstd.grd'
    range = '205/255/22/51'
    increment = '0.0125/0.0125'
    smooth = '2k'

    # Use PyGMT nearneighbor to interpolate scattered (lon, lat, sst) points onto a grid
    temp_data1 = pygmt.nearneighbor(
        data=temp_data,
        region=range,
        spacing=increment,
        search_radius=smooth,
        sectors='1'
    )

    # Convert the GMT grid to a CF-compliant NetCDF and send to server
    # Apply the land mask, create a NetCDF via a CDL template, and add metadata
    ncFile = grd2netcdf1(temp_data1, fileOut, filesUsed, my_mask, 'MW')

    #myCmd = "mv " + ncFile + " /home/cwatch/pygmt_test/outfiles"
    #os.system(myCmd)

    # Copy the final NetCDF to the "MW" server folder for 1-day products
    send_to_servers(ncFile, '/MW/sstd/', '1')

    # Remove the local NetCDF to copy from workdir
    os.remove(ncFile)
