'''
This module defines a device-independent XRD class.

Authors/Modifications:
----------------------
* Margaret Koker, koker@cars.uchicago.edu
* modeled after MCA class
'''

##########################################################################
# IMPORT PYTHON PACKAGES

import os
import numpy as np

from larch_plugins.xrd.xrd_tools import (d_from_q, d_from_twth, twth_from_d, twth_from_q,
                                       q_from_d, q_from_twth, E_from_lambda)
from larch_plugins.xrd.xrd_pyFAI import integrate_xrd
from larch_plugins.xrd.xrd_bgr import xrd_background
from larch_plugins.xrd.xrd_fitting import peakfinder,peaklocater,peakfilter,peakfitter
from larch_plugins.io import tifffile

HAS_larch = False
try:
    from larch import Group
    grpobjt = Group
    HAS_larch = True
except:
    grpobjt = object

##########################################################################
# CLASSES

class xrd1d(grpobjt):
    '''
    1D XRD data class
    
    --> all length units in m (unless otherwise noted)
    
    Attributes:
    ------------
    * self.filename      = 'CeO2_Allende.xy'      # file containing x-y data
    * self.label         = 'Data: CeO2_Allende'   # name of data set

    # Data parameters
    * self.I             = None or array          # intensity (units: counts)
    * self.q             = None or array          # inverse lattice spacing (units: 1/A)
    * self.d             = None or array          # lattice spacing (units: A)
    * self.twth          = None or array          # 2-theta (units: degrees)

    # Calibration/experiemental parameters
    * self.wavelength    = 0.688801071778         # incident x-ray wavelength (units: A)
    * self.energy        = 18.000                 # incident x-ray energy (units: keV)
    * self.distance      = 0.49212785             # distance from sample to detector
    * self.poni          = [0.2286, 0.2547]       # center/point of normal incidence
    * self.rotation      = [0.010, -0.00857, 0.0] # detector rotations (units: radians)
    * self.pixelsize     = [0.0004, 0.0004]       # size of pixels
    * self.splinefile    = None                   # spline file for detector
    * self.polarization  = None                   # polarization of detector
    * self.normalization = 1.0                    # normalization factor for detector
    
    # Data fitting parameters
    * self.uvw           = [0.313, -0.109, 0.019] # instrumental broadening parameters
    * self.D             = None                   # particle size broadening (units: A)
    * self.pki           = [8, 254, 3664]         # list of peak indecides

    * self.imin          = None                   # range for trimmed data
    * self.imax          = None                   # range for trimmed data
    * self.bkgd          = None                   # fit background for data

    * self.matches       = None                   # list of amcsd matches from database
    
    * self.xrd2d         = None                   # 2D data
    * self.cake          = None                   # 2D cake

    mkak 2017.03.15
    '''

    def __init__(self,file=None,label=None,x=None,xtype=None,I=None,
                 wavelength=None,energy=None):

        self.filename = file
        self.label    = label

        if file is not None:
            self.xrd_from_file(file)
        else:
            self.wavelength = wavelength
            self.energy     = energy

            ## Default values
            self.distance      = None
            self.poni          = None
            self.rotation      = None
            self.pixelsize     = None
            self.splinefile    = None
            self.polarization  = None
            self.normalization = None

            if I is not None:
                if xytq is not None:
                    self.xrd_from_2d([q,I],'q')
                elif twth is not None:
                    self.xrd_from_2d([twth,I],'2th')
                elif d is not None:
                    self.xrd_from_2d([d,I],'d')
        
                self.bkgd = np.zeros(np.shape(self.I))
            else:
                self.q    = None
                self.twth = None
                self.d    = None
                self.I    = None
                self.bkgd = None

        
        ## Analysis parameters - set defaults
        self.uvw = None
        self.D   = None
        self.pki = []

        self.imin = None
        self.imax = None

        self.matches = None
    
        self.xrd2d   = None
        self.cake    = None    

        if HAS_larch:
           Group.__init__(self)

    
    def xrd_from_2d(self,xy,xtype,verbose=True):
        self.set_xy_data(xy,xtype)

    def xrd_from_file(self,filename,verbose=True):
        
        try:
            from larch_plugins.xrmmap import read1DXRDFile
            head,dat = read1DXRDFile(filename)
            if verbose:
                print('Opening xrd data file: %s' % os.path.split(filename)[-1])
        except:
           print('incorrect xy file format: %s' % os.path.split(filename)[-1])
           return
           
        if self.label is None: self.label = os.path.split(filename)[-1]

        ## header info
        for line in head:
            import re
            line = re.sub(',','',line)

            if 'SplineFile' in line:
                self.splinefile = line.split()[-1]
            if 'PixelSize' in line:
                self.pixelsize = [float(line.split()[2]),float(line.split()[3])]
            if 'PONI' in line:
                self.poni = [float(line.split()[2]),float(line.split()[3])]
            if 'Detector' in line:
                self.distance = float(line.split()[-2])
            if 'Rotations' in line:
                self.rotation = [float(line.split()[2]),float(line.split()[3]),float(line.split()[4])]

            if 'Wavelength' in line:
                self.wavelength = float(line.split()[-1])*1e10
                self.energy = E_from_lambda(self.wavelength)
            if 'Polarization' in line:
                if line.split()[-1] != 'None': self.polarization = float(line.split()[-1])
            if 'Normalization' in line:
                self.normalization = float(line.split()[-1])

            if 'q_' in line or '2th_' in line:
                xtype = line.split()[1]
        ## data
        self.set_xy_data(dat,xtype)
        
    def set_xy_data(self,xy,xtype):
        
        if xy is not None:
            xy = np.array(xy)
            if xy.shape[0] > xy.shape[1]:
                x,y = np.split(xy,2,axis=1)        
            else:
                x,y = np.split(xy,2,axis=0)
            self.q,self.twth,self.d = calculate_xvalues(x,xtype,self.wavelength)
            self.I = np.array(y).squeeze()
        
            self.imin,self.imax = 0,len(self.q)
            self.bkgd = np.zeros(np.shape(self.I))

    def plot(self,reset=False,bkgd=False):

        if reset: self.imin,self.imax = 0,len(self.I)
        if bkgd:
            return [self.q[self.imin:self.imax],
                    self.twth[self.imin:self.imax],
                    self.d[self.imin:self.imax],
                    self.I[self.imin:self.imax]-self.bkgd,
                    self.bkgd]
        return [self.q[self.imin:self.imax],
                self.twth[self.imin:self.imax],
                self.d[self.imin:self.imax],
                self.I[self.imin:self.imax],
                self.bkgd]
               
    def reset_bkgd(self):
         self.bkgd = np.zeros(np.shape(self.I))

    def slct_xaxis(self,xtype='',xi=None):
    
        if xtype.startswith('q') or xi == 0:
            x = self.q
        elif xtype.startswith('2th') or xi == 1:
            x = self.twth
        elif xtype.startswith('d') or xi == 2:
            x = self.d
        else:
            print('The provided x-axis label (%s or &i) not correct.' % (xtype,xi))
            return
        
        return x
    
    def set_trim(self,xmin,xmax,xtype='',xi=None):
    
        x = self.slct_xaxis(xtype=xtype,xi=xi)
            
        self.imin,self.imax = 0,len(x)-1
        if xmin > np.min(x):
            self.imin = (np.abs(x-xmin)).argmin()
        if xmax < np.max(x):
            self.imax = (np.abs(x-xmax)).argmin()
            
    def all_data(self,reset=False,bkgd=False):

        if reset: self.imin,self.imax = 0,len(self.I)
        if len(self.I[self.imin:self.imax]) != len(self.bkgd):
            self.bkgd = np.zeros(len(self.I[self.imin:self.imax]))
        if bkgd:
            return [self.q[self.imin:self.imax],
                    self.twth[self.imin:self.imax],
                    self.d[self.imin:self.imax],
                    self.I[self.imin:self.imax]-self.bkgd,
                    self.bkgd]
        return [self.q[self.imin:self.imax],
                self.twth[self.imin:self.imax],
                self.d[self.imin:self.imax],
                self.I[self.imin:self.imax],
                self.bkgd]
            
    def fit_background(self):
    
        x,y = self.q[self.imin:self.imax],self.I[self.imin:self.imax]
        self.bkgd = xrd_background(x,y)
        if len(self.bkgd) < len(y): self.bkgd = np.append(self.bkgd,self.bkgd[-1])
        
    def find_peaks(self,bkgd=False,threshold=None,**kwargs):
    
        all_data = np.array(self.all_data(bkgd=bkgd))

        self.pki = peakfinder(all_data[3],**kwargs)
        if threshold is not None: self.pki = peakfilter(threshold,self.pki,all_data[3])

        pk_data = np.zeros((5,len(self.pki)))
        for i,pki in enumerate(self.pki): pk_data[:,i] = all_data[:,pki]
            
        return pk_data

        
#     def refine_peaks(self,trim=False,bkgd=False):
#     
#         q,twth,d,I = self.trim_all(trim,bkgd)
#         
#         pktwth,pkfwhm,self.Ipks = peakfitter(self.pki,twth,I,fittype='double')
#         #self.peaks = zip(pkfwhm,pkI)
# 
#         self.qpks,self.twthpks,self.dpks = calculate_xvalues(pktwth,'2th',self.wavelength)

#     def fit_pattern(self):
#         ## This isn't written yet
#         ## mkak 2017.04.03
#         fit = np.zeros(len(self.I))
#         for i,j in enumerate(self.pki):
#             a = None
        


        
class XRD(grpobjt):
    '''
    X-Ray Diffraction (XRD) class

    Attributes:
    -----------
    * self.name        = 'xrd'  # Name of the object
    * self.xpix        = 2048   # Number of x pixels
    * self.ypix        = 2048   # Number of y pixels
    * self.data2D      = None   # 2D XRD data
    * self.data1D      = None   # 1D XRD data

    Notes:
    ------

    mkak 2016.08.20
    '''

    def __init__(self, data2D=None, xpixels=2048, ypixels=2048, data1D=None, nwedge=1, 
                 steps=5001, name='xrd', _larch=None, **kws):

        self.name    = name
        self.xpix    = xpixels
        self.ypix    = ypixels
        self.data2D  = data2D
        self.nwedge  = nwedge
        self.steps   = steps
        self.data1D  = data1D
        self.data2D  = data2D
        self.cake    = None
        
        self.energy     = None
        self.wavelength = None
        self.calfile    = None
        
        self.filename = None
        self.title    = None
        self.npixels  = None

        if HAS_larch:
            Group.__init__(self)

    def __repr__(self):
        if self.data2D is not None:
            form = "<2DXRD %s: pixels = %d, %d>"
            return form % (self.name, self.xpix, self.ypix)
        elif self.data1D is not None:
            form = "<1DXRD %s: channels = %d>"
            return form % (self.name, self.steps)
        else:
            form = "<no 1D or 2D XRD pattern given>"
            return form       

    def add_environ(self, desc='', val='', addr=''):
        '''add an Environment setting'''
        if len(desc) > 0 and len(val) > 0:
            self.environ.append(Environment(desc=desc, val=val, addr=addr))
            
            
    def calc_1D(self,save=False,calccake=True,calc1d=True,verbose=False):
    
        kwargs = {'steps':self.steps,'calccake':calccake,'calc1d':calc1d}
        
        if save:
            file = self.save_1D()
            kwargs.update({'file':file}) 
                    
        if os.path.exists(self.calfile):
            if len(self.data2D) > 0:
                self.data1D,self.cake = integrate_xrd(self.data2D,self.calfile,
                                                      verbose=verbose,**kwargs)
            else:
                if verbose:
                    print('No 2D XRD data provided.')
        else:
            if verbose:
                print('Could not locate file %s' % self.calfile)
    
    def save_1D(self):

        pref,fname = os.path.split(self.filename)
        counter = 1
        while os.path.exists('%s/%s-%s-%03d.xy' % (pref,fname,self.title,counter)):
            counter += 1
        return '%s/%s-%s-%03d.xy' % (pref,fname,self.title,counter)

    def save_2D(self,verbose=False):
    
        pref,fname = os.path.split(self.filename)
        
        counter = 1
        while os.path.exists('%s/%s-%s-%03d.tiff' % (pref,fname,self.title,counter)):
            counter += 1
        tiffname = '%s/%s-%s-%03d.tiff' % (pref,fname,self.title,counter)
        
        if verbose:
            print('Saving 2D data in file: %s' % (tiffname))
        tifffile.imsave(tiffname,self.data2D)



##########################################################################
# FUNCTIONS

def calculate_xvalues(x,xtype,wavelength):
    '''
    projects given x-axis onto q-, 2theta-, and d-axes
    
    x            :   list or array (expected units: 1/A, deg, or A)
    xtype        :   options 'q', '2th', or 'd'
    wavelength   :   incident x-ray wavelength (units: A)
    
    q, twth, d   :   returned with same dimensions as x (units: 1/A, deg, A)
    '''

    x = np.array(x).squeeze()
    if xtype.startswith('q'):

        q = x
        d = d_from_q(q)
        if wavelength is not None:
            twth = twth_from_q(q,wavelength)
        else:
            twth = np.zeros(len(q))        
    
    elif xtype.startswith('2th'):

        twth = x
        if wavelength is not None:
            q = q_from_twth(twth,wavelength)
            d = d_from_twth(twth,wavelength)
        else:
            q = np.zeros(len(twth))
            d = np.zeros(len(twth))
    
    elif xtype.startswith('d'):

        d = x
        q = q_from_d(d)
        if wavelength is not None:
            twth = twth_from_d(d,wavelength)
        else:
            twth = np.zeros(len(d))
    
    else:
        print('The provided x-axis label (%s) not correct. Check data.' % xtype)
        return None,None,None
        
    
    return q,twth,d


def create_xrd(data2D=None, xpixels=2048, ypixels=2048,
               data1D=None, nwedge=2, steps=5001, 
               name='xrd', _larch=None, **kws):

    '''
    create an XRD object

     Parameters:
     ------------
      data2D:   2D diffraction patterns
      data1D:   1D diffraction patterns
      xpixels:  number of x pixels
      ypixels:  number of y pixels

     Returns:
     ----------
      an XRD object

    '''
    return XRD(data2D=data2D, data1D=data1D, xpixels=xpixels, ypixels=ypixels,
               name=name, **kws)


def create_xrd1d(file, _larch=None, **kws):

    '''
    create an XRD object

     Parameters:
     ------------
      data2D:   2D diffraction patterns
      data1D:   1D diffraction patterns
      xpixels:  number of x pixels
      ypixels:  number of y pixels

     Returns:
     ----------
      an XRD object

    '''
    return xrd1d(file=file, **kws)

   

def registerLarchPlugin():
    return ('_xrd', {'create_xrd': create_xrd, 'create_xrd1d': create_xrd1d})


def registerLarchGroups():
    return (XRD,xrd1d)