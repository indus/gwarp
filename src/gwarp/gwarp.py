"""
Run ``pip install .`` (or ``pip install -e .`` for editable mode)
which will install the command ``gwarp`` inside your current environment.
"""

import argparse
import logging
import sys
import os
import glob
import numpy as np
from osgeo import gdal

from gwarp import __version__

__author__ = "Keim, Stefan"
__copyright__ = "Keim, Stefan"
__license__ = "MIT"

_logger = logging.getLogger(__name__)


# ---- Python API ----
# The functions defined in this section can be imported by users in their
# Python scripts/interactive interpreter, e.g. via
# `from gwarp.gwarp import gwarp`,
# when using this Python module as a library.


def gwarp(args):

    if args.vips:
        os.environ['PATH'] = args.vips + ';' + os.environ['PATH']
    
    import pyvips

    src_names = glob.glob(args.src,recursive=True)

    src_count = len(src_names)
    if src_count == 0:
        print(f'{args.src}: No such file or directory')
        return

    src_multi = src_count > 1

    
    srcNodataDic = None if args.srcNodata is not None else {} 

    if args.vii == None:
        # gdal read files; get max size and projection/geotransform

        xSize = ySize = -1

        for name in src_names:
            print(name)
            dataset = gdal.Open(name, gdal.GA_ReadOnly)
            if (dataset.RasterXSize > xSize or dataset.RasterYSize > ySize ):
                xSize = dataset.RasterXSize
                ySize = dataset.RasterYSize
                projection   = dataset.GetProjection()
                geotransform = dataset.GetGeoTransform()
            if srcNodataDic is not None:
                srcNodataDic[name] = dataset.GetRasterBand(1).GetNoDataValue()
           

        if args.vs:
            xSize = args.vs[0]
            ySize = args.vs[1]
      
        if projection == '' or geotransform == (0.0, 1.0, 0.0, 0.0, 0.0, 1.0):
            print('src is missing a projection and/or geotransform')
            return 

        # select proper types and interpolation methods for GDAL, Numpy & VIPS
        maxUInt16 = 2**16-1
        ltMaxUInt16 = (xSize < maxUInt16 and ySize < maxUInt16)

        maxUInt = maxUInt16 if ltMaxUInt16 else 2**32-1

        np_index_type = 'uint16' if ltMaxUInt16 else 'uint32'
        gdal_index_type = gdal.GDT_UInt16 if ltMaxUInt16 else gdal.GDT_UInt32
        gdal_index_warp_type = gdal.GDT_Float32
        vips_index_type = 'float'

        if args.resampleAlg == 'near' or args.resampleAlg == None:
            gdal_index_warp_type = gdal_index_type
            vips_index_type = 'ushort' if ltMaxUInt16 else 'uint'
            

        # create vips index
        _logger.info(f'Creating index: {xSize}x{ySize} type:{vips_index_type}')
        
        index = pyvips.Image.xyz(xSize, ySize)
        
        if ltMaxUInt16:
            index = index.cast('ushort')
            
         # vips2np
        np_index = np.ndarray(buffer=index.write_to_memory(), shape=[ySize, xSize, 2], dtype=np_index_type)

        # np2gdal
        gdal_index = gdal.GetDriverByName('MEM').Create('', xSize, ySize, 2, gdal_index_type)

        gdal_index.GetRasterBand(1).WriteArray(np_index[:, :, 0])
        gdal_index.GetRasterBand(2).WriteArray(np_index[:, :, 1])

        # slower
        # band1.WriteArray(np.tile(np.linspace(0, xSize, xSize, dtype= np_index_type,endpoint=False), (ySize, 1)))
        # band2.WriteArray(np.tile(np.linspace(0, ySize, ySize, dtype= np_index_type,endpoint=False).reshape((-1, 1)), (1, xSize)))

        # gdal set metadata
        
        gdal_index.SetProjection( projection )
        gdal_index.SetGeoTransform( geotransform )

        gdal_resample = {
            'near': gdal.GRA_NearestNeighbour,
            'bilinear': gdal.GRA_Bilinear,
            'cubic': gdal.GRA_Cubic,
            'cubicspline': gdal.GRA_CubicSpline,
            'lanczos': gdal.GRA_CubicSpline,
        }[args.resampleAlg]

        _logger.info('Warping index')
        # gdal warp
        gdal_index = gdal.Warp('', gdal_index,
                                    format='MEM',
                                    outputType = gdal_index_warp_type,
                                    resampleAlg = gdal_resample,
                                    #srcNodata = maxUInt,
                                    dstNodata = maxUInt,
                                    outputBounds = args.outputBounds,
                                    outputBoundsSRS = args.outputBoundsSRS,
                                    xRes = args.xyRes[0] if args.xyRes != None else None,
                                    yRes = args.xyRes[1] if args.xyRes != None else None,
                                    targetAlignedPixels = args.targetAlignedPixels,
                                    width = args.widthHeight[0] if args.widthHeight != None else None,
                                    height = args.widthHeight[1] if args.widthHeight != None else None,
                                    srcSRS = args.srcSRS,
                                    dstSRS = args.dstSRS,
                                    multithread = args.multithread)


        # gdal read new metadata
        projection   = gdal_index.GetProjection()
        geotransform = gdal_index.GetGeoTransform()

        # gdal2np
        band1 = gdal_index.GetRasterBand(1)
        band2 = gdal_index.GetRasterBand(2)

        band1 = band1.ReadAsArray()
        band2 = band2.ReadAsArray()
        
        np_index = np.moveaxis(np.array([band1,band2]), 0, -1)
        height, width, bands = np_index.shape
        np_index = np_index.reshape(width * height * bands)

        # np2vips
        index = pyvips.Image.new_from_memory(np_index.data, width, height, bands, vips_index_type)
        

        # write the index file
        if args.vio:
            _logger.info(f'Writing index: {args.vio}')
            dst_folder = os.path.dirname(args.vio)
            if not os.path.exists(dst_folder):
                os.makedirs(dst_folder)
            write_to_file(index, args.vio, args.co, projection, geotransform,{'SrcXSize':str(xSize),'SrcYSize':str(ySize)})

    else: #args.vii != None
        _logger.info(f'Reading index: {args.vii}')
        index = gdal.Open(args.vii, gdal.GA_ReadOnly)
        projection   = index.GetProjection()
        geotransform = index.GetGeoTransform()
        if projection == '' or geotransform == (0.0, 1.0, 0.0, 0.0, 0.0, 1.0):
            _logger.warning('The index is missing a projection and/or geotransform')
    
        if args.vs:
            xSize = args.vs[0]
            ySize = args.vs[1]
        else:
            metadata = index.GetMetadata()
    
            xSize = int(metadata["SrcXSize"])
            ySize = int(metadata["SrcYSize"])

        if srcNodataDic is not None:
            for name in src_names:
                dataset = gdal.Open(name, gdal.GA_ReadOnly)
                srcNodataDic[name] = dataset.GetRasterBand(1).GetNoDataValue()

        index = pyvips.Image.new_from_file(args.vii)


    vips_resample = args.v_inter if args.v_inter != None else {
        'near':'nearest',
        'bilinear':'bilinear',
        'cubic':'bicubic',
        'cubicspline':'vsqbs',
        'lanczos':'vsqbs'
    }[args.resampleAlg] if args.resampleAlg != None else 'nearest'
    
    interp = pyvips.vinterpolate.Interpolate.new(vips_resample)

    dst_suffix = '_gwarp'
    dst_folder = dst_name = dst_ext = None 

    # define dst defaults for single and multi src
    if args.dst:
        name_split = os.path.splitext(os.path.basename(args.dst))
        dst_name = name_split[0]
        dst_suffix = f'_{name_split[0]}' if name_split[0] != '' and src_multi else ''
        dst_ext = name_split[1]
        dst_folder = os.path.dirname(args.dst)
        if dst_folder == '':
            dst_folder = '.'

        if not os.path.exists(dst_folder):
            os.makedirs(dst_folder)

    idx_mask = None

    # START LOOP on src files
    for name in src_names:
        name_split = os.path.splitext(os.path.basename(name))
        
        if not dst_folder:
            dst_folder = os.path.dirname(name)
        
        if not dst_name or src_multi:
            dst_name = name_split[0]
        
        if not dst_ext:
            dst_ext = name_split[1] 
            
        output = f'{dst_folder}/{dst_name}{dst_suffix}{dst_ext}'
        
        if os.path.exists(output) and not args.overwrite:
            _logger.warning(f'Output dataset {output} exists,\ndelete the file or use -overwrite and run again')
            continue

        _logger.info(f'Reading file: {name}')
        image = pyvips.Image.new_from_file(name)

        if (image.width == xSize and image.height == ySize ):
            idx = index 
        else:
            wfac = image.width/xSize
            hfac = image.height/ySize
            idx = index * [wfac, hfac]

        noData = None
        flattenAlpha = False

        if args.srcNodata is not None:
            srcNodata = args.srcNodata
        else:
            srcNodata = [srcNodataDic[name]] if srcNodataDic[name] is not None else None

        if srcNodata is not None:
            srcNodataSingle = len(srcNodata) == 1
            noData = srcNodata[0] if srcNodataSingle else 0
            #if image.hasalpha():
            #    image = image[0:image.bands -1]
            if srcNodataSingle:
                alpha = (image != srcNodata).bandor()
            else:
                alpha = image[0] != srcNodata[0]
                for i, srcNodata in enumerate(srcNodata[1:], start=1):
                    alpha = alpha and (image[i] != srcNodata)
                    
            if noData != 0:
                flattenAlpha = image.bands
                image = image.bandjoin(alpha)
        if args.dstNodata is not None:
            noData = args.dstNodata
            if srcNodata is None:
                if  noData != 0 and flattenAlpha == False:
                    flattenAlpha = image.bands
                    image = image.addalpha()


        _logger.info(f'Warping file: {name}')
        image = image.mapim( idx, interpolate=interp)
        
        if flattenAlpha:
            idx_mask = idx_mask if idx_mask is not None else (idx > [image.width, image.height]).bandor()
            image =  idx_mask.ifthenelse(noData,image.flatten(background=noData))

        write_to_file(image, output, args.co, projection, geotransform, noData=noData)



def write_to_file(image, dst, co, projection, geotransform, metadata = None, noData = None ):
    _logger.info(f'Writing file: {dst}')
    image.write_to_file(dst, **co)

    if dst.endswith(('.tif','.tiff')):
        # write metadata
        dataset = gdal.Open( dst, gdal.GA_Update )
        dataset.SetProjection( projection )
        dataset.SetGeoTransform( geotransform )

        if metadata is not None:
            dataset.SetMetadata( metadata )

        if noData is not None:
            band = dataset.GetRasterBand(1)
            band.SetNoDataValue(noData)
            band.FlushCache()
        
    else:
        _logger.warning(f'WARNING: {dst} has no geoinformation. Consider using GeoTIFF as output format.')

def parse_nif(nif):
    if nif == 'None':
        return None
    f = float(nif)
    i = int(f)
    return i if i == f else f


# ---- CLI ----
# The functions defined in this section are wrappers around the main Python
# API allowing them to be called directly from the terminal as a CLI
# executable/script.


def parse_args(args):
    epilog = """
Additional info on resampling and interpolation methods
-------------------------------------------------------
-r <resampling_method>:
    The GDAL stage will use the provided resampling method,
    but the following VIPS stage may use a different method
    (and therefore may produce sighly different results).

    Default mapping:

        GDAL        : VIPS
        ----------------------
        near        : nearest
        bilinear    : bilinear
        cubic       : bicubic
        cubicspline : vsqbs
        lanczos     : vsqbs

-vi <interpolation_method>:
    If the above mapping is insufficent the VIPS interpolator can be set explictly:

        nearest     : nearest-neighbour interpolation
        bilinear    : bilinear interpolation
        bicubic     : bicubic interpolation (Catmull-Rom)
        lbb         : reduced halo bicubic
        nohalo      : edge sharpening resampler with halo reduction
        vsqbs       : B-Splines with antialiasing smoothing

-co <create_options>:
    use the parameters of the file save functions of vips. e.g. for TIFF:

        compression=<none|jpeg|deflate|packbits|ccittfax4|lzw|webp|zstd>
        predictor=<none|horizontal|float> (used for 'deflate' and 'lzw' compression, default is 'horizontal')
        level=<number> (used for 'webp' and 'zstd' compression, default is 9)
        bigtiff=<0|1>
        tile=<0|1>
        tile_width=<int>
        tile_height=<int>

        (complete list: https://libvips.github.io/pyvips/vimage.html#pyvips.Image.tiffsave)

        if the <create_options> has no '=' it gets applied to 'compression' ('-co lzw' = '-co compression=lzw')
 
"""


    parser = argparse.ArgumentParser(description="gdalwarp batch processor (vips accelerated)",
        formatter_class=argparse.RawTextHelpFormatter, epilog=epilog)
    parser.add_argument(
        "--version",
        action="version",
        version="gwarp {ver}".format(ver=__version__),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        dest="loglevel",
        help="set loglevel to INFO",
        action="store_const",
        const=logging.INFO,
    )
    parser.add_argument(
        "-q",
        "--quite",
        dest="loglevel",
        help="set loglevel to ERROR",
        action="store_const",
        const=logging.ERROR,
    )
    parser.add_argument(dest="src", help="the input glob pattern", metavar="srcfile")
    parser.add_argument(dest="dst", help='the output file or folder', metavar="dstfile", nargs='?')
    gdal_group = parser.add_argument_group('GDAL')
    gdal_group.add_argument('-te', dest='outputBounds', metavar=("<xmin>", "<ymin>", "<xmax>", "<ymax>"), type=float, nargs=4)
    gdal_group.add_argument('-te_srs', dest='outputBoundsSRS', metavar='<srs_def>')
    gdal_group.add_argument('-tr', dest='xyRes', metavar=('<xres>', '<yres>'), type=float, nargs=2)
    gdal_group.add_argument('-tap', dest='targetAlignedPixels', default=False,  action='store_true')
    gdal_group.add_argument('-ts', dest='widthHeight', metavar=('<width>', '<height>'), type=int, nargs=2)
    gdal_group.add_argument('-s_srs', dest='srcSRS', metavar='<srs_def>')
    gdal_group.add_argument('-t_srs', dest='dstSRS', metavar='<srs_def>')
    gdal_group.add_argument('-multi',  dest='multithread', default=False,  action='store_true')
    gdal_group.add_argument('-srcnodata', dest='srcNodata', metavar='value', nargs='*')
    gdal_group.add_argument('-dstnodata', dest='dstNodata', metavar='value') # ,nargs='*' GeoTIFF only allows for a single nodata value for all bands
    gdal_group.add_argument('-r', dest='resampleAlg', default='near', choices=["near","bilinear","cubic","cubicspline","lanczos"],help="resampling method (more info in the epilog)")
    gdal_group.add_argument('-overwrite', dest='overwrite', default=False, action='store_true')
    gdal_group.add_argument('-co', dest="co", metavar='<NAME=VALUE>*', action='append',  help='create options (more info in the epilog)')
    vips_group = parser.add_argument_group('VIPS')
    vips_group.add_argument('--vips', help='path to the VIPS bin directory (usefull if VIPS is not added to PATH; e.g. on Windows)')
    vips_group.add_argument('--vio', dest="vio", help='index file output', metavar='dstindex')
    vips_group.add_argument('--vii', dest="vii", help='index file input', metavar='srcindex')
    gdal_group.add_argument('--vs', dest="vs", metavar=('<width>', '<height>'), type=int, nargs=2, help='explicitly set src width and height of index')
    vips_group.add_argument('--vi', dest='v_inter', choices=['nearest', 'bilinear', 'bicubic', 'lbb', 'nohalo', 'vsqbs'], help="interpolation method (more info in the epilog)")
    args = parser.parse_args(args)

    if args.srcNodata is not None:
        args.srcNodata = list(map(parse_nif, tuple(args.srcNodata)))

    if args.dstNodata is not None:
        args.dstNodata = parse_nif(args.dstNodata)

    coDict = {}
    if args.co:
        for co in args.co:
            cosp = co.lower().split("=")
            if len(cosp) == 2:
                coDict[cosp[0]] = int(cosp[1]) if cosp[1].isnumeric() else cosp[1]
            else:
                coDict['compression'] = cosp[0]
    args.co = coDict

    return args


def setup_logging(loglevel):
    """Setup basic logging

    Args:
      loglevel (int): minimum loglevel for emitting messages
    """
    logging.getLogger("pyvips").setLevel(logging.ERROR)
    logformat = "[%(asctime)s] %(levelname)s:%(name)s: %(message)s"
    logging.basicConfig(
        level=loglevel, stream=sys.stdout, format=logformat, datefmt="%Y-%m-%d %H:%M:%S"
    )


def main(args):
    """Wrapper allowing :func:`gwarp` to be called with string arguments in a CLI fashion

    Args:
      args (List[str]): command line parameters as list of strings
    """
    args = parse_args(args)
    setup_logging(args.loglevel)
    gwarp(args)


def run():
    """Calls :func:`main` passing the CLI arguments extracted from :obj:`sys.argv`

    This function can be used as entry point to create console scripts with setuptools.
    """
    main(sys.argv[1:])


if __name__ == "__main__":
    # ^  This is a guard statement that will prevent the following code from
    #    being executed in the case someone imports this file instead of
    #    executing it as a script.
    #    https://docs.python.org/3/library/__main__.html

    # After installing your project with pip, users can also run your Python
    # modules as scripts via the ``-m`` flag, as defined in PEP 338::
    #
    #     python -m gwarp.gwarp
    #
    run()
