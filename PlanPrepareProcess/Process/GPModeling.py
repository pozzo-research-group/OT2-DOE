import numpy as np
import pandas as pd

import matplotlib.pyplot as plt
import matplotlib.colors as colors
import matplotlib.cm as cm
from matplotlib import animation
from matplotlib.patches import Polygon
from matplotlib.path import Path
from mpl_toolkits.mplot3d import Axes3D

from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel as C
from sklearn import preprocessing

from itertools import product
from scipy import interpolate, stats
from scipy.spatial import ConvexHull, convex_hull_plot_2d
import math

from random import randrange
from collections import Counter

def load_datadf(path):
    df = pd.read_csv(path) 
    return df

def apply_column_filter(df, column_name, min=None, max=None): 
    pass

def standardize_training(data_list):
    data_reshaped = data_list[:, np.newaxis]
    scaler = preprocessing.RobustScaler().fit(data_reshaped)
    data_scaled = scaler.transform(data_reshaped)
    
    return data_scaled, scaler

def create_product_mesh(x1,x2):
    x1x2 = np.array(list(product(x1, x2)))
    x1_expanded = x1x2[:,0][:,0]
    x2_expanded = x1x2[:,1][:,0]
    return x1x2

def create_hull(x1,x2, graph = False):# inputs must be (1,n)
    hull_1 = x1[:,0]
    hull_2 = x2[:,0]
    hull_2d_points = np.asarray([hull_1, hull_2]).T
    hull = ConvexHull(hull_2d_points)
    
    if graph == True:
        for simplex in hull.simplices:
            plt.plot(hull_2d_points[simplex, 0], hull_2d_points[simplex, 1], 'k-', c='k')
    
    return hull

def point_in_hull(hull, hull_2d_points,x1,x2,graph=False):
    hull_path = Path(hull_2d_points[hull.vertices])
    if hull_path.contains_point((x1,x2)) == True:
        if graph == True:
            plt.plot(x1,x2,'o',c='r')
        return True
    else:
        return False
    
def xyz_in_between_z(min_value, max_value, xl,yl,zl):
    x = []
    y = []
    z = []
    for xi,yi,zi in zip(xl, yl, zl):
        if min_value < zi < max_value:
            x.append(xi)
            y.append(yi)
            z.append(zi)
    x=np.asarray(x)
    y=np.asarray(y)
    z=np.asarray(z)[:, np.newaxis]
    
    return x[:, np.newaxis],y[:, np.newaxis],z[:, np.newaxis]

def series_to_list(series):
