# -*- coding: utf-8 -*-
"""ExtractEEData.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/github/chad-fisher/CRWA-Regional-Tree-Planting-and-Protection-Plan/blob/main/ExtractEEData.ipynb
"""

!pip install matplotlib_scalebar
!pip install contextily
!pip install wget
!pip install pyinaturalist
!pip install geetools

#Import packages
import numpy as np
import pandas as pd
import seaborn as sns
import geopandas as gpd
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib_scalebar.scalebar import ScaleBar
import contextily as cx
import ee
import geemap
import geemap.foliumap as geemapf
import rasterio as rio
from rasterio.plot import show
from rasterio.mask import mask
import wget
import zipfile
from datetime import datetime
import pyinaturalist
from scipy import ndimage
import urllib
import geetools
from geetools import batch

#Authenticate to Earth Engine
ee.Authenticate()

#Initialize earth engine project
ee.Initialize(project='ee-cefisher20')

#Set working directory
cd '???????'

#HUC codes from https://apps.nationalmap.gov/viewer/
Charles=ee.FeatureCollection("USGS/WBD/2017/HUC10").filter("huc10 == '0109000107' or huc10 == '0109000106'")

#Convert earth engine feature collections to geopandas data frames
Charles_gdf = ee.data.computeFeatures({
    'expression': Charles,
    'fileFormat': 'GEOPANDAS_GEODATAFRAME'
})
Charles_gdf.crs = 'EPSG:4326'

def Charclip(image):
    return image.clip(Charles)

#Extract Sentinel 2 bands and indices of interest
def extractBandsIndices(image):
    return image.select(['B2','B3','B4','B5_10m','B6_10m','B7_10m','B8','B8A_10m','B11_10m','B12_10m',
                         'NDVI','NBR','SAVI','RENDVI','EVI'])

#Resample Sentinel 2 bands to 10 m
def resample10m(image):
    proj_10m=image.select('B4').projection()
    B5_res=image.select('B5').resample('bicubic').reproject(proj_10m).rename('B5_10m')
    B6_res=image.select('B6').resample('bicubic').reproject(proj_10m).rename('B6_10m')
    B7_res=image.select('B7').resample('bicubic').reproject(proj_10m).rename('B7_10m')
    B8A_res=image.select('B8A').resample('bicubic').reproject(proj_10m).rename('B8A_10m')
    B11_res=image.select('B11').resample('bicubic').reproject(proj_10m).rename('B11_10m')
    B12_res=image.select('B12').resample('bicubic').reproject(proj_10m).rename('B12_10m')
    return image.addBands([B5_res,B6_res,B7_res,B8A_res,B11_res,B12_res])

#Add 5 vegetation indices of interest
def addIndices(image):
    NDVI = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
    NBR = image.normalizedDifference(['B12_10m','B8']).rename('NBR')
    SAVI = image.expression(
        '1.5 * ((NIR - RED)) / (NIR + RED + 0.5)', {
            'NIR' : image.select('B8'),
            'RED' : image.select('B4'),
        }).rename('SAVI')
    RENDVI = image.normalizedDifference(['B6_10m','B5_10m']).rename('RENDVI')
    EVI = image.expression(
        '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))', {
            'NIR' : image.select('B8'),
            'RED' : image.select('B4'),
            'BLUE': image.select('B2')}).rename('EVI')
    return image.addBands([NDVI,NBR,SAVI,RENDVI,EVI])

#Cloud mask function
def mask_s2_clouds(image):
    qa = image.select('QA60')
    cloud_bit_mask = 1 << 10
    cirrus_bit_mask = 1 << 11
    mask = (
        qa.bitwiseAnd(cloud_bit_mask)
        .eq(0)
        .And(qa.bitwiseAnd(cirrus_bit_mask).eq(0))
    )
    return image.updateMask(mask).divide(10000)

#Land cover mask function
def mask_forests(image):
    mask=(NLCD2019lc.eq(41))
    return image.updateMask(mask)

def preprocess(img):
  return extractBandsIndices(addIndices(resample10m(Charclip(img))))

#Pre-processing sentinel-2 data
S2_All=ee.ImageCollection(("COPERNICUS/S2_SR_HARMONIZED")).filterDate('2019-01-01','2020-01-01').filterBounds(Charles.geometry()).filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 50)).map(preprocess)

S2_raw=ee.ImageCollection(("COPERNICUS/S2_SR_HARMONIZED")).filterDate('2019-01-01','2020-01-01').filterBounds(Charles.geometry()).filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 50))

def dateFormat(img):
  return ee.Image(img).date().format().split('T').get(0)

def mosaicBy(d):
  return ee.ImageCollection(("COPERNICUS/S2_SR_HARMONIZED")).filterBounds(Charles.geometry()).filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 50)).filterDate(d,ee.Date(d).advance(1,'day')).mosaic()

dates_list=ee.List(S2_raw.toList(S2_raw.size()).map(dateFormat)).distinct()

NLCD2019lc=ee.Image('USGS/NLCD_RELEASES/2019_REL/NLCD/2019').clip(Charles).select('landcover')

S2_fix=ee.ImageCollection(dates_list.map(mosaicBy)).map(mask_s2_clouds).map(preprocess)
S2_for_export=S2_fix.map(mask_forests)

#Getting Boston city boundary
towns=gpd.read_file('/content/CENSUS2020TOWNS_POLY.shp').to_crs(epsg=4326).dissolve('NAMELSAD20')
Boston_gdf=towns[towns.index=='Boston city']
Boston=geemap.geopandas_to_ee(Boston_gdf)

#Extract forest areas
d_forest=NLCD2019lc.updateMask(NLCD2019lc.eq(41)).select('landcover').clip(Boston)
d_forest_vec=d_forest.reduceToVectors(geometry=Charles,crs=d_forest.projection())

d_forest_gdf = ee.data.computeFeatures({
    'expression': d_forest_vec,
    'fileFormat': 'GEOPANDAS_GEODATAFRAME'
})
d_forest_gdf.crs = 'EPSG:4326'
forest_list=d_forest_vec.toList(10000)

for band in ['B2','B3','B4','B5_10m','B6_10m','B7_10m','B8','B8A_10m','B11_10m','B12_10m',
                         'NDVI','NBR','SAVI','RENDVI','EVI']:
    current_IC=S2_for_export.select(band)
    current_df=pd.DataFrame(data=current_IC.getRegion(ee.Feature(forest_list.get(0)).geometry(),10).getInfo()[1:],columns=current_IC.getRegion(ee.Feature(forest_list.get(0)).geometry(),10).getInfo()[0])
    for i in np.arange(1,169):
      print(i)
      print(current_df.size)
      current_df=pd.concat([current_df,pd.DataFrame(data=current_IC.getRegion(ee.Feature(forest_list.get(int(i))).geometry(),10).getInfo()[1:],columns=current_IC.getRegion(ee.Feature(forest_list.get(int(i))).geometry(),10).getInfo()[0])])
    current_df.to_csv(band+'.csv')