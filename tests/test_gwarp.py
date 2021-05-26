import pytest

from gwarp.gwarp import main, run, parse_args, parse_nif
import os
import sys
import subprocess
import glob
import shutil
import urllib.request
from osgeo import gdal
    
    

__author__ = "Keim, Stefan"
__copyright__ = "Keim, Stefan"
__license__ = "MIT"


os.environ['PATH'] =  'C:/Program Files/vips-dev-8.10/bin' + ';' + os.environ['PATH']

import pyvips

path_in =  './tests/in/'
path_out =  './tests/out/'

@pytest.fixture(scope="session", autouse=True)
def prepare_files(request):

    # remove output folder
    if os.path.exists(path_out):
        shutil.rmtree(path_out)

    # create input folder
    if not os.path.exists(path_in):
        os.makedirs(path_in)

    # download test images
    test_images= {
        "basemap.tif":"https://geoservice.dlr.de/eoc/basemap/wms?VERSION=1.1.1&REQUEST=GetMap&SRS=epsg:4326&BBOX=-180,-90,180,90&WIDTH=4096&HEIGHT=2048&FORMAT=image/geotiff&LAYERS=basemap",
        "baseoverlay.tif":"https://geoservice.dlr.de/eoc/basemap/wms?VERSION=1.1.1&REQUEST=GetMap&SRS=epsg:4326&BBOX=-180,-90,180,90&WIDTH=3072&HEIGHT=1536&FORMAT=image/geotiff&TRANSPARENT=true&LAYERS=baseoverlay",
        "combNO2.tif":"https://geoservice.dlr.de/eoc/atmosphere/wms?VERSION=1.1.1&REQUEST=GetMap&SRS=epsg:4326&BBOX=-180,-90,180,90&WIDTH=4096&HEIGHT=2048&FORMAT=image/geotiff&LAYERS=METOP_GOME-2_L2C_P1D_COMB_NO2&TIME=2021-01-01",
        "modis_8192.tif": "https://geoservice.dlr.de/eoc/imagery/wms?VERSION=1.1.1&REQUEST=GetMap&SRS=epsg:25832&BBOX=110000,5130000,1110000,6130000&WIDTH=8192&HEIGHT=8192&FORMAT=image/geotiff&LAYERS=Modis-Deutschlandmosaik_RGB_ETRS89_32N"
    }

    for file in test_images.items():
        if not os.path.exists(path_in + file[0]):
            with urllib.request.urlopen(file[1]) as response, open(path_in + file[0], 'wb') as out_file:
                shutil.copyfileobj(response, out_file)

    # create additional images

    file_org = path_in + 'basemap.tif'
    file = path_in +'gen/basebw.tif'
    if True or not os.path.isfile(file): 
        basemap_bw = pyvips.Image.new_from_file(file_org)
        basemap_bw = basemap_bw.colourspace("b-w").addalpha().resize(0.5)
        basemap_bw.write_to_file(file, compression='lzw')

    if not os.path.exists(path_in +'gen'):
            os.makedirs(path_in +'gen')

    file = path_in +'gen/basebw.tif'
    if not os.path.isfile(file): # name collision
        basemap_bw = pyvips.Image.new_from_file(file_org)
        basemap_bw = basemap_bw.colourspace("b-w").resize(0.5)
        basemap_bw.write_to_file(file, compression='lzw')

    if not os.path.exists(path_in +'nodata'):
        os.makedirs(path_in +'nodata')

    file_org = path_in + 'modis_8192.tif'
    file = path_in +'nodata/modis_allvalid.tif'
    if not os.path.isfile(file):
        modis = pyvips.Image.new_from_file(file_org)
        modis = modis.resize(1/32)
        modis.write_to_file(file, compression='lzw')
        
        org = gdal.Open(file_org)
        dataset = gdal.Open(file, gdal.GA_Update)
        dataset.SetProjection(org.GetProjection())
        trans = list(org.GetGeoTransform())
        trans[1] *= 32
        trans[5] *= 32
        dataset.SetGeoTransform(tuple(trans))

    file_org = file
    file = path_in +'nodata/modis_alpha.tif'
    if not os.path.isfile(file):
        modis = pyvips.Image.new_from_file(file_org)
        modis = modis.addalpha()
        modis.write_to_file(file, compression='lzw')
        org = gdal.Open(file_org)
        dataset = gdal.Open(file, gdal.GA_Update)
        dataset.SetProjection(org.GetProjection())
        dataset.SetGeoTransform(org.GetGeoTransform())

    file = path_in +'nodata/modis_nodata0.tif'
    if not os.path.isfile(file):
        modis = pyvips.Image.new_from_file(file_org)
        modis.write_to_file(file, compression='lzw')
        org = gdal.Open(file_org)
        dataset = gdal.Open(file, gdal.GA_Update)
        dataset.SetProjection(org.GetProjection())
        dataset.SetGeoTransform(org.GetGeoTransform())
        band = dataset.GetRasterBand(1)
        band.SetNoDataValue(0)
        band.FlushCache()

    file = path_in +'nodata/modis_nodata50.tif'
    if not os.path.isfile(file):
        modis = pyvips.Image.new_from_file(file_org)
        modis.write_to_file(file, compression='lzw')
        org = gdal.Open(file_org)
        dataset = gdal.Open(file, gdal.GA_Update)
        dataset.SetProjection(org.GetProjection())
        dataset.SetGeoTransform(org.GetGeoTransform())
        band = dataset.GetRasterBand(1)
        band.SetNoDataValue(50)
        band.FlushCache()


## --- TESTS

def test_parse_args(capsys):
    
    args0 = parse_args(['srcfile'])
    assert args0.co != None
    
    args1 = parse_args(['-co', 'compression=lzw', 'srcfile'])
    assert args1.co['compression'] == 'lzw'
    
    args2 = parse_args(['-co', 'compression=lzw', '-co', 'predictor=horizontal', 'srcfile'])
    assert args2.co['compression'] == 'lzw' and args2.co['predictor'] == 'horizontal'

def test_parse_nif(capsys):
    
    assert parse_nif('None') == None
    assert parse_nif('0') == 0
    assert parse_nif('1') == 1
    assert parse_nif('-1') == -1
    assert parse_nif('1.2') == 1.2
    


def test_run(capsys):

    args = ['', '-v','--vips','some/path/to/vipis/bin', 'does_not_exist.tif']
    print('\nargs:  '+' '.join(args))
    sys.argv = args
    run()
    captured = capsys.readouterr()
    assert 'does_not_exist.tif: No such file or directory' in captured.out
    assert 'some/path/to/vipis/bin;' in os.environ['PATH']


index = None
path_index = path_out + 'index_base.tif'

def test_main_multi(capsys):
    
    args = ['-t_srs', 'EPSG:3857', '-co', 'lzw','-srcnodata','235', '--vio', path_index, path_in + '../**/base*', path_out + 'base/epsg3857']
    print('\nargs:  '+' '.join(args))
    main(args)
    
    assert os.path.isfile(path_index)

    index = gdal.Open(path_index)
    assert index.GetProjection() != None
    assert index.GetGeoTransform() != None
    assert index.RasterXSize == 3177
    assert index.RasterYSize == 3298
    
    outfiles = glob.glob(path_out+'base/base*.*')
    assert len(outfiles) == 3
    for file in outfiles:
        assert file.endswith('_epsg3857.tif')
        index = gdal.Open(path_index)
        dataset = gdal.Open(file, gdal.GA_ReadOnly)
        assert dataset.GetProjection() == index.GetProjection()
        assert dataset.GetGeoTransform() == index.GetGeoTransform()
        assert dataset.RasterXSize == index.RasterXSize
        assert dataset.RasterYSize == index.RasterYSize

    if not os.path.isfile(path_in+'index_base_nogeo_nometa.tif'):
        index = pyvips.Image.new_from_file(path_index)
        index.write_to_file(path_in+'index_base_nogeo_nometa.tif', compression='lzw', predictor='horizontal')

def test_main_vii(capsys):
    path_fileNO2 = path_out+'combNO2_3857.tif'
    args = ['-co', 'lzw','--vii', path_index, path_in+'combNO2.tif', path_fileNO2]
    print('\nargs:  '+' '.join(args))
    main(args)
    assert os.path.isfile(path_fileNO2)
    index = gdal.Open(path_index, gdal.GA_ReadOnly)
    dataset = gdal.Open(path_fileNO2, gdal.GA_ReadOnly)
    assert dataset.GetProjection() == index.GetProjection()
    assert dataset.GetGeoTransform() == index.GetGeoTransform()
    assert dataset.RasterXSize == index.RasterXSize
    assert dataset.RasterYSize == index.RasterYSize


def test_main_idxnogeo(capsys):
    path_fileNO2 = path_out+'CombNO2_3857.png'
    args = ['-srcnodata','255','--vii', path_in+'index_base_nogeo_nometa.tif', '--vs', '4096', '2048', path_in+'combNO2.tif', path_fileNO2]
    print('\nargs:  '+' '.join(args))
    main(args)
    assert os.path.isfile(path_fileNO2)
    index = gdal.Open(path_index, gdal.GA_ReadOnly)
    dataset = gdal.Open(path_fileNO2, gdal.GA_ReadOnly)
    assert dataset.GetProjection() == ''
    assert dataset.GetGeoTransform() == (0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
    assert dataset.RasterXSize == index.RasterXSize 
    assert dataset.RasterYSize == index.RasterYSize


def test_main_nodst(capsys):
    path_fileNO2 = path_out+'CombNO2_3857_gwarp.tif'
    args = ['-t_srs', 'EPSG:4326', '-co', 'lzw','-srcnodata','0','0','0','-dstnodata','123','-r', 'bilinear','--vs', '3177', '3298', path_out+'combNO2_3857.tif']
    print('\nargs:  '+' '.join(args))
    main(args)
    assert os.path.isfile(path_fileNO2)
    dataset = gdal.Open(path_fileNO2, gdal.GA_ReadOnly)
    assert dataset.RasterXSize == 4135
    assert dataset.RasterYSize == 1967

def test_main_nonogeo(capsys):
    args = ["-v", path_in +'basebw.tif']
    print('\nargs:  '+' '.join(args))
    main(args)
    captured = capsys.readouterr()
    assert 'src is missing a projection and/or geotransform' in captured.out

def test_main_noData_nochange(capsys):
    args = ['-t_srs', 'EPSG:3857', '-co', 'lzw', path_in+'nodata/*.tif', path_out+'nodata/nochange']
    print('\nargs:  '+' '.join(args))
    main(args)

    outfiles = glob.glob(path_out+'nodata/*nochange.*')
    assert len(outfiles) == 4
    
    outfiles = glob.glob(path_out+'nodata/*_allvalid.*')
    for file in outfiles:
        assert gdal.Open(file, gdal.GA_ReadOnly).GetRasterBand(1).GetNoDataValue() == None
    outfiles = glob.glob(path_out+'nodata/*_nodata0*.*')
    for file in outfiles:
        assert gdal.Open(file, gdal.GA_ReadOnly).GetRasterBand(1).GetNoDataValue() == 0
    outfiles = glob.glob(path_out+'nodata/*_nodata50*.*')
    for file in outfiles:
        assert gdal.Open(file, gdal.GA_ReadOnly).GetRasterBand(1).GetNoDataValue() == 50
    outfiles = glob.glob(path_out+'nodata/*_alpha*.*')
    for file in outfiles:
        assert gdal.Open(file, gdal.GA_ReadOnly).GetRasterBand(1).GetNoDataValue() == None

def test_main_noData_dstnodata0(capsys):
    args = ['-t_srs', 'EPSG:3857', '-co', 'lzw','-dstnodata','0','--', path_in+'nodata/*.tif', path_out+'nodata/dstnodata0']
    print('\nargs:  '+' '.join(args))
    main(args)
    outfiles = glob.glob(path_out+'nodata/*dstnodata0.*')
    assert len(outfiles) == 4
    for file in outfiles:
        assert gdal.Open(file, gdal.GA_ReadOnly).GetRasterBand(1).GetNoDataValue() == 0

def test_main_noData_dstnodata50(capsys):
    args = ['-t_srs', 'EPSG:3857', '-co', 'lzw','-dstnodata','50','--', path_in+'nodata/*.tif', path_out+'nodata/dstnodata50']
    print('\nargs:  '+' '.join(args))
    main(args)
    outfiles = glob.glob(path_out+'nodata/*dstnodata50.*')
    assert len(outfiles) == 4
    for file in outfiles:
        assert gdal.Open(file, gdal.GA_ReadOnly).GetRasterBand(1).GetNoDataValue() == 50

def test_main_noData_srcnodata0(capsys):
    args = ['-t_srs', 'EPSG:3857', '-co', 'lzw','-srcnodata','0','--', path_in+'nodata/*.tif', path_out+'nodata/srcnodata0']
    print('\nargs:  '+' '.join(args))
    main(args)
    outfiles = glob.glob(path_out+'nodata/*srcnodata0.*')
    assert len(outfiles) == 4
    for file in outfiles:
        assert gdal.Open(file, gdal.GA_ReadOnly).GetRasterBand(1).GetNoDataValue() == 0

def test_main_noData_srcnodata50(capsys):
    args = ['-t_srs', 'EPSG:3857', '-co', 'lzw','-srcnodata','50','--', path_in+'nodata/*.tif', path_out+'nodata/srcnodata50']
    print('\nargs:  '+' '.join(args))
    main(args)
    outfiles = glob.glob(path_out+'nodata/*srcnodata50.*')
    assert len(outfiles) == 4
    for file in outfiles:
        assert gdal.Open(file, gdal.GA_ReadOnly).GetRasterBand(1).GetNoDataValue() == 50

def test_main_noData_bands(capsys):
    outfiles = glob.glob(path_out+'nodata/*_allvalid.*')
    for file in outfiles:
        assert gdal.Open(file, gdal.GA_ReadOnly).RasterCount == 3
    outfiles = glob.glob(path_out+'nodata/*_nodata0*.*')
    for file in outfiles:
        assert gdal.Open(file, gdal.GA_ReadOnly).RasterCount == 3
    outfiles = glob.glob(path_out+'nodata/*_nodata50*.*')
    for file in outfiles:
        assert gdal.Open(file, gdal.GA_ReadOnly).RasterCount == 3
    outfiles = glob.glob(path_out+'nodata/*_alpha*.*')
    for file in outfiles:
        assert gdal.Open(file, gdal.GA_ReadOnly).RasterCount == 4

