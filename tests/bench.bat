:: run pytest before benchmark
::for %%s in (16192, 24288) do (
::    if not exist ./in/modis_%%s.tif (
::        gdal_translate -outsize %%s %%s -co compress=lzw -co predictor=2 ./in/modis_8192.tif ./in/modis_%%s.tif
::    )
::)

::for %%f in (./in/nodata/*.tif) do (
::    gdalwarp -t_srs EPSG:3857 -overwrite -co compression=lzw ./in/nodata/%%~f ./out/nodata/%%~nf_nochange_ref.tif
::    gdalwarp -t_srs EPSG:3857 -overwrite -co compression=lzw -dstnodata 0  ./in/nodata/%%~f ./out/nodata/%%~nf_dstnodata0_ref.tif
::    gdalwarp -t_srs EPSG:3857 -overwrite -co compression=lzw -dstnodata 50 ./in/nodata/%%~f ./out/nodata/%%~nf_dstnodata50_ref.tif
::    gdalwarp -t_srs EPSG:3857 -overwrite -co compression=lzw -srcnodata 0  ./in/nodata/%%~f ./out/nodata/%%~nf_srcnodata0_ref.tif
::    gdalwarp -t_srs EPSG:3857 -overwrite -co compression=lzw -srcnodata 50 ./in/nodata/%%~f ./out/nodata/%%~nf_srcnodata50_ref.tif
::)

hyperfine.exe --export-csv ./out/modis0_single.csv -r 4 ^
-L r near,bilinear -L s 8192,16192,24288 ^
"gwarp -t_srs EPSG:3857 -overwrite -r {r} -multi -ts 2048 2048 -co lzw ./in/modis_{s}.tif ./out/bench0/_single{s}_{r}" "gdalwarp -t_srs EPSG:3857 -overwrite -r {r} -multi -ts 2048 2048 -co compression=lzw -co predictor=2 ./in/modis_{s}.tif ./out/bench0/gdal_modis_single{s}_{r}.tif"

hyperfine.exe --export-csv ./out/modis1_multi.csv -r 2 ^
-L r near,bilinear ^
"gwarp -t_srs EPSG:3857 -overwrite -r {r} -multi -ts 2048 2048 -co lzw ./in/modis* ./out/bench1/{r}" "for %%f in (./in/modis*) do (gdalwarp -t_srs EPSG:3857 -overwrite -r {r} -multi -ts 2048 2048 -co compression=lzw -co predictor=2 ./in/%%~f ./out/bench1/gdal_%%~nf_{r}.tif)"


