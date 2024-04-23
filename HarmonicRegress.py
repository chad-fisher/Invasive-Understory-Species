#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import pandas as pd
import numpy as np
import scipy
import geopandas as gpd
from datetime import datetime
import matplotlib.pyplot as plt
import seaborn as sns
import pyogrio
from sklearn.metrics import mean_squared_error


# In[ ]:


cd "C:/Users/Chad/Desktop/CRWA Project/Working_Data"


# In[ ]:


mygdf=gpd.read_file('2023BandsIndicesCleaned.shp',engine="pyogrio")


# In[ ]:


def harmonicfunc(mult,one,two,x):
    w=2*np.pi/365.25
    return one*np.cos(mult*w*x)+two*np.sin(mult*w*x)


# In[ ]:


def myobj(x,a,b,c,d,e,f,g,h,i):  
    return a+harmonicfunc(1,b,c,x)+harmonicfunc(2,d,e,x)+harmonicfunc(3,f,g,x)+harmonicfunc(4,h,i,x)


# In[ ]:


def curvefit(PtID,band):
    x=mygdf[mygdf['PtID']==PtID]['DOY']
    y=mygdf[mygdf['PtID']==PtID][band]
    popt,pcov=scipy.optimize.curve_fit(myobj, x,y)
    yhat=myobj(x,popt[0],popt[1],popt[2],popt[3],popt[4],popt[5],popt[6],popt[7],popt[8])
    RMSE=np.sqrt(mean_squared_error(y, yhat))
    return RMSE,popt


# In[ ]:


for band in ['B2','B3','B4','B5','B6','B7','B8','B8A','B11','B12','NDVI','NBR','SAVI','RENDVI','EVI']:
    output_df=mygdf[['PtID']]
    RMSE_res=np.zeros((output_df.size,1))
    popt_res=np.zeros((output_df.size,9))
    for i in mygdf['PtID']:
        RMSE_res[i,:],popt_res[i,:]=curvefit(i,band)
    output_df['RMSE']=RMSE_res
    output_df[band+'a']=popt_res[:,0]
    output_df


# In[ ]:


output_df.to_file('HarmonicResults.shp')

