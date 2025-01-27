from pyomo.environ import *
from pyomo.opt import SolverFactory
import os
import pandas as pd
import numpy as np
import xarray as xr
try:
    import cPickle as pickle
except ImportError:  # python 3.x
    import pickle
import shutil
import netCDF4
import logging
import sys

pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)

logging.basicConfig(filename='/local_debug/app.log', level=logging.INFO)

logging.info('Successfully loaded all Python modules')

#sys.stdout = open('C:\\Users\\yoon644\\OneDrive - PNNL\\Documents\\PyProjects\\wm_pmp\\local_debug\\python_stdout.log', 'w')

import pyutilib.subprocess.GlobalData
pyutilib.subprocess.GlobalData.DEFINE_SIGNAL_HANDLERS_DEFAULT = False

year = '2001'
month = '01'

logging.info(sys.version_info)
logging.info(pd.__version__)

logging.info('Trying to run ABM calc for month, year: ' + month + ' ' + year)
logging.info('Entering month 1 calculations: ' + month)

with open('/local_debug/pmp_input_files_PIC_copy/nldas_ids.p', 'rb') as fp:
    nldas_ids = pickle.load(fp)

nldas = pd.read_csv('/local_debug/pmp_input_files_PIC_copy/nldas.txt')

#!!!JY


year_int = int(year)
months = ['01','02','03','04','05','06','07','08','09','10','11','12']

with open('/local_debug/pmp_input_files_PIC_copy/water_constraints_by_farm_pyt278.p', 'rb') as fp:
    water_constraints_by_farm = pickle.load(fp)
# water_constraints_by_farm = pd.read_pickle('/pic/projects/im3/wm/Jim/pmp_input_files/water_constraints_by_farm_v2.p')
water_constraints_by_farm = dict.fromkeys(water_constraints_by_farm, 9999999999)


## Read in Water Availability Files from MOSART-PMP

### !!! Run this section if testing first year (2000)
water_constraints_by_farm = pd.read_csv('/local_debug/pmp_input_files_PIC_copy/hist_avail_bias_correction.csv')
water_constraints_by_farm = water_constraints_by_farm[['NLDAS_ID','sw_irrigation_vol']].reset_index()
water_constraints_by_farm = water_constraints_by_farm['sw_irrigation_vol'].to_dict()

#water_constraints_by_farm.update((x, y*0.8) for x, y in water_constraints_by_farm.items()) #!JY temp test to reduce water availability by 80 percent

### !!! Run this section if testing after first year (2001 and beyond)
#pic_output_dir = '/pic/scratch/yoon644/csmruns/jimtest2/run/'
pic_input_dir = '/local_debug/demand_input\\'  #JY debug - need to modify for runs

# loop through .nc files and extract data
first = True
for m in months:
    #dataset_name = 'jim_abm_integration.mosart.h0.' + str(year-1) + '-' + m + '.nc'
    logging.info('Trying to load WM output for month, year: ' + month + ' ' + year)
    dataset_name = 'wm_abm_run.mosart.h0.' + str(year_int - 1) + '-' + m + '.nc' # currently assumes 1-year agent memory
    logging.info('Successfully load WM output for month, year: ' + month + ' ' + year)
    ds = xr.open_dataset(pic_input_dir+dataset_name)
    df = ds.to_dataframe()
    logging.info('Successfully converted to df for month, year: ' + month + ' ' + year)
    df = df.reset_index()
    df_merge = pd.merge(df, nldas, how='left', left_on=['lat', 'lon'], right_on=['CENTERY', 'CENTERX'])
    logging.info('Successfully merged df for month, year: ' + month + ' ' + year)
    df_select = df_merge[['NLDAS_ID', 'WRM_DEMAND0', 'WRM_SUPPLY', 'WRM_DEFICIT','WRM_STORAGE','GINDEX','RIVER_DISCHARGE_OVER_LAND_LIQ']]
    logging.info('Successfully subsetted df for month, year: ' + month + ' ' + year)
    df_select['year'] = year_int
    df_select['month'] = int(m)
    if first:
        df_all = df_select
        first = False
    else:
        df_all = pd.concat([df_all, df_select])
    logging.info('Successfully concatenated df for month, year: ' + month + ' ' + year)

# calculate average across timesteps
# df_pivot = pd.pivot_table(df_all, index=['NLDAS_ID','GINDEX'], values=['WRM_SUPPLY','WRM_STORAGE','RIVER_DISCHARGE_OVER_LAND_LIQ'],
#                           aggfunc=np.mean)  # units will be average monthly (m3/s)
df_pivot = pd.pivot_table(df_all, index=['NLDAS_ID','GINDEX'], values=['WRM_SUPPLY','WRM_STORAGE','RIVER_DISCHARGE_OVER_LAND_LIQ'],
                          aggfunc=np.mean)  # units will be average monthly (m3/s)
df_pivot = df_pivot.reset_index()
df_pivot = df_pivot[df_pivot['NLDAS_ID'].isin(nldas_ids)].reset_index()
df_pivot.fillna(0)
logging.info('Successfully pivoted df for month, year: ' + month + ' ' + year)

# calculate dependent storage
ds = xr.open_dataset('C:\\Users\\yoon644\\OneDrive - PNNL\\Documents\\IM3\\WM Flag Tests\\US_reservoir_8th_NLDAS3_updated_CERF_Livneh_naturalflow.nc')
dams = ds["DamInd_2d"].to_dataframe()
dams = dams.reset_index()
dep = ds["gridID_from_Dam"].to_dataframe()
dep = dep.reset_index()
dep_id = ds["unit_ID"].to_dataframe()
dep_merge = pd.merge(dep, dams, how='left', left_on=['Dams'], right_on=['DamInd_2d'])
df_pivot = pd.merge(df_pivot, nldas, how='left', on='NLDAS_ID')
dep_merge = pd.merge(dep_merge, df_pivot[['NLDAS_ID','CENTERX','CENTERY','WRM_STORAGE','RIVER_DISCHARGE_OVER_LAND_LIQ']], how='left', left_on=['lat','lon'], right_on=['CENTERY','CENTERX'])
dep_merge['WRM_STORAGE'] = dep_merge['WRM_STORAGE'].fillna(0)

aggregation_functions = {'WRM_STORAGE': 'sum'}
dep_merge = dep_merge.groupby(['gridID_from_Dam'], as_index=False).aggregate(aggregation_functions)
dep_merge.rename(columns={'WRM_STORAGE': 'STORAGE_SUM'}, inplace=True)

wm_results = pd.merge(df_pivot, dep_merge, how='left', left_on=['GINDEX'], right_on=['gridID_from_Dam'])
abm_supply_avail = wm_results[wm_results['NLDAS_ID'].isin(nldas_ids)].reset_index()
abm_supply_avail = abm_supply_avail[['WRM_SUPPLY','NLDAS_ID','STORAGE_SUM','RIVER_DISCHARGE_OVER_LAND_LIQ']]
abm_supply_avail = abm_supply_avail.fillna(0)

# convert units from m3/s to acre-ft/yr
mu = 0.2 # mu defines the agents "memory decay rate" - higher mu values indicate higher decay (e.g., 1 indicates that agent only remembers previous year)

if year == '2001':
    hist_avail_bias = pd.read_csv('/data_inputs/hist_avail_bias_correction_20201102.csv')
    hist_avail_bias['WRM_SUPPLY_acreft_prev'] = hist_avail_bias['WRM_SUPPLY_acreft_OG']
else:
    hist_avail_bias = pd.read_csv('/data_inputs/hist_avail_bias_correction_live.csv')

hist_storage = pd.read_csv('/data_inputs/hist_dependent_storage.csv')
hist_avail_bias = pd.merge(hist_avail_bias, hist_storage, how='left', on='NLDAS_ID')

abm_supply_avail = pd.merge(abm_supply_avail, hist_avail_bias[['NLDAS_ID','sw_avail_bias_corr','WRM_SUPPLY_acreft_OG','WRM_SUPPLY_acreft_prev','RIVER_DISCHARGE_OVER_LAND_LIQ_OG','STORAGE_SUM_OG']], on=['NLDAS_ID'])
abm_supply_avail['demand_factor'] = abm_supply_avail['STORAGE_SUM'] / abm_supply_avail['STORAGE_SUM_OG']
abm_supply_avail['demand_factor'] = np.where(abm_supply_avail['STORAGE_SUM_OG'] > 0, abm_supply_avail['STORAGE_SUM'] / abm_supply_avail['STORAGE_SUM_OG'],
                                             np.where(abm_supply_avail['RIVER_DISCHARGE_OVER_LAND_LIQ_OG'] >= 0.1,
                                                      abm_supply_avail['RIVER_DISCHARGE_OVER_LAND_LIQ'] / abm_supply_avail['RIVER_DISCHARGE_OVER_LAND_LIQ_OG'],
                                                      1))

abm_supply_avail['WRM_SUPPLY_acreft_newinfo'] = abm_supply_avail['demand_factor'] * abm_supply_avail['WRM_SUPPLY_acreft_OG']

abm_supply_avail['WRM_SUPPLY_acreft_updated'] = ((1 - mu) * abm_supply_avail['WRM_SUPPLY_acreft_prev']) + (mu * abm_supply_avail['WRM_SUPPLY_acreft_newinfo'])

abm_supply_avail['WRM_SUPPLY_acreft_prev'] = abm_supply_avail['WRM_SUPPLY_acreft_updated']
abm_supply_avail[['NLDAS_ID','WRM_SUPPLY_acreft_OG','WRM_SUPPLY_acreft_prev','sw_avail_bias_corr','demand_factor']].to_csv('C:\\Users\\yoon644\\OneDrive - PNNL\\Documents\\PyProjects\\wm_pmp\\data_inputs\\hist_avail_bias_correction_live.csv')
abm_supply_avail['WRM_SUPPLY_acreft_bias_corr'] = abm_supply_avail['WRM_SUPPLY_acreft_updated'] + abm_supply_avail['sw_avail_bias_corr']
water_constraints_by_farm = abm_supply_avail['WRM_SUPPLY_acreft_bias_corr'].to_dict()
logging.info('Successfully converted units df for month, year: ' + month + ' ' + year)

### !!! Resume here (run regardless of year)
logging.info('I have successfully loaded water availability files for month, year: ' + month + ' ' + year)

## Read in PMP calibration files
data_file=pd.ExcelFile("/data_inputs/MOSART_WM_PMP_inputs_20201005.xlsx")
data_profit = data_file.parse("Profit")
water_nirs=data_profit["nir_corrected"]
nirs=dict(water_nirs)

logging.info('I have successfully loaded PMP calibration files for month, year: ' + month + ' ' + year)

## C.1. Preparing model indices and constraints:
#ids = range(592185) # total number of crop and nldas ID combinations
ids = range(538350) # total number of crop and nldas ID combinations
farm_ids = range(53835) # total number of farm agents / nldas IDs
with open('/local_debug/pmp_input_files_PIC_copy/crop_ids_by_farm.p', 'rb') as fp:
    crop_ids_by_farm = pickle.load(fp)
with open('/local_debug/pmp_input_files_PIC_copy/crop_ids_by_farm_and_constraint.p', 'rb') as fp:
    crop_ids_by_farm_and_constraint = pickle.load(fp)
with open('/data_inputs/max_land_constr.p', 'rb') as fp:
    land_constraints_by_farm = pickle.load(fp, encoding='latin1')

#Revise to account for removal of "Fodder_Herb category"
crop_ids_by_farm_new = {}
for i in crop_ids_by_farm:
    crop_ids_by_farm_new[i] = crop_ids_by_farm[i][0:10]
crop_ids_by_farm = crop_ids_by_farm_new
crop_ids_by_farm_and_constraint = crop_ids_by_farm_new

# Load gammas and alphas
with open('/data_inputs/gammas_new_20201006.p', 'rb') as fp:
    gammas = pickle.load(fp, encoding='latin1')
with open('/data_inputs/net_prices_new_20201006.p', 'rb') as fp:
    net_prices = pickle.load(fp, encoding='latin1')

# !JY! replace net_prices with zero value for gammas that equal to zero
for n in range(len(net_prices)):
    if gammas[n] == 0:
        net_prices[n] = 0

x_start_values=dict(enumerate([0.0]*3))

logging.info('I have loaded constructed model indices,constraints for month, year: ' + month + ' ' + year)

## C.2. 2st stage: Quadratic model included in JWP model simulations
## C.2.a. Constructing model inputs:
##  (repetition to be safe - deepcopy does not work on PYOMO models)
fwm_s = ConcreteModel()
fwm_s.ids = Set(initialize=ids)
fwm_s.farm_ids = Set(initialize=farm_ids)
fwm_s.crop_ids_by_farm = Set(fwm_s.farm_ids, initialize=crop_ids_by_farm)
fwm_s.crop_ids_by_farm_and_constraint = Set(fwm_s.farm_ids, initialize=crop_ids_by_farm_and_constraint)
fwm_s.net_prices = Param(fwm_s.ids, initialize=net_prices, mutable=True)
fwm_s.gammas = Param(fwm_s.ids, initialize=gammas, mutable=True)
fwm_s.land_constraints = Param(fwm_s.farm_ids, initialize=land_constraints_by_farm, mutable=True)
fwm_s.water_constraints = Param(fwm_s.farm_ids, initialize=water_constraints_by_farm, mutable=True) #JY here need to read calculate new water constraints
fwm_s.xs = Var(fwm_s.ids, domain=NonNegativeReals, initialize=x_start_values)
fwm_s.nirs = Param(fwm_s.ids, initialize=nirs, mutable=True)

## C.2.b. 2nd stage model: Constructing functions:
def obj_fun(fwm_s):
    return 0.00001*sum(sum((fwm_s.net_prices[i] * fwm_s.xs[i] - 0.5 * fwm_s.gammas[i] * fwm_s.xs[i] * fwm_s.xs[i]) for i in fwm_s.crop_ids_by_farm[f]) for f in fwm_s.farm_ids)
fwm_s.obj_f = Objective(rule=obj_fun, sense=maximize)


def land_constraint(fwm_s, ff,):
    return sum(fwm_s.xs[i] for i in fwm_s.crop_ids_by_farm_and_constraint[ff]) <= fwm_s.land_constraints[ff]
fwm_s.c1 = Constraint(fwm_s.farm_ids, rule=land_constraint)

def water_constraint(fwm_s, ff):
    return sum(fwm_s.xs[i]*fwm_s.nirs[i] for i in fwm_s.crop_ids_by_farm_and_constraint[ff]) <= fwm_s.water_constraints[ff]
fwm_s.c2 = Constraint(fwm_s.farm_ids, rule=water_constraint)

logging.info('I have successfully constructed pyomo model for month, year: ' + month + ' ' + year)

## C.2.c Creating and running the solver:
try:
    opt = SolverFactory("ipopt", solver_io='nl')
    results = opt.solve(fwm_s, keepfiles=False, tee=True)
    print(results.solver.termination_condition)
except:
    logging.info('Pyomo model solve has failed for month, year: ' + month + ' ' + year)

logging.info('I have successfully solved pyomo model for month, year: ' + month + ' ' + year)

## D.1. Storing main model outputs:
result_xs = dict(fwm_s.xs.get_values())

# JY store results into a pandas dataframe
results_pd = data_profit
results_pd = results_pd.assign(calc_area=result_xs.values())
results_pd = results_pd.assign(nir=nirs.values())
results_pd['calc_water_demand'] = results_pd['calc_area'] * results_pd['nir'] / 25583.64
results_pivot = pd.pivot_table(results_pd, index=['nldas'], values=['calc_water_demand'], aggfunc=np.sum) #JY demand is order of magnitude low, double check calcs

# JY export results to csv
results_pd = results_pd[['nldas','crop','calc_area']]
#results_pd.to_csv('C:\\Users\\yoon644\\OneDrive - PNNL\\Documents\\PyProjects\\wm_pmp\\local_debug\\run_output\\abm_results_'+ str(year_int))
results_pd.to_csv('C:\\Users\\yoon644\\OneDrive - PNNL\\Documents\\PyProjects\\wm_pmp\\local_debug\\run_output\\abm_results_baseline.csv')

# read a sample water demand input file
file = '/local_debug/pmp_input_files_PIC_copy/RCP8.5_GCAM_water_demand_1980_01_copy.nc'
with netCDF4.Dataset(file, 'r') as nc:
    # for key, var in nc.variables.items():
    #     print(key, var.dimensions, var.shape, var.units, var.long_name, var._FillValue)

    lat = nc['lat'][:]
    lon = nc['lon'][:]
    demand = nc['totalDemand'][:]

# read NLDAS grid reference file
df_grid = pd.read_csv('/local_debug/pmp_input_files_PIC_copy/NLDAS_Grid_Reference.csv')

df_grid = df_grid[['CENTERX', 'CENTERY', 'NLDAS_X', 'NLDAS_Y', 'NLDAS_ID']]

df_grid = df_grid.rename(columns={"CENTERX": "longitude", "CENTERY": "latitude"})
df_grid['longitude'] = df_grid.longitude + 360

# match netCDF demand file and datagrame
mesh_lon, mesh_lat = np.meshgrid(lon, lat)
df_nc = pd.DataFrame({'lon':mesh_lon.reshape(-1,order='C'),'lat':mesh_lat.reshape(-1,order='C')})
df_nc['NLDAS_ID'] = ['x'+str(int((row['lon']-235.0625)/0.125+1))+'y'+str(int((row['lat']-25.0625)/0.125+1)) for _,row in df_nc.iterrows()]
df_nc['totalDemand'] = 0

# use NLDAS_ID as index for both dataframes
df_nc = df_nc.set_index('NLDAS_ID',drop=False)
try:
    results_pivot = results_pivot.set_index('nldas',drop=False)
except KeyError:
    pass

# read ABM values into df_nc basing on the same index
df_nc.loc[results_pivot.index,'totalDemand'] = results_pivot.calc_water_demand.values

for month in months:
    str_year = str(year_int)
    new_fname = 'C:\\Users\\yoon644\\OneDrive - PNNL\\Documents\\PyProjects\\wm_pmp\\local_debug\\demand_input\\RCP8.5_GCAM_water_demand_'+ str_year + '_' + month + '.nc' # define ABM demand input directory
    shutil.copyfile(file, new_fname)
    demand_ABM = df_nc.totalDemand.values.reshape(len(lat),len(lon),order='C')
    with netCDF4.Dataset(new_fname,'a') as nc:
        nc['totalDemand'][:] = np.ma.masked_array(demand_ABM,mask=nc['totalDemand'][:].mask)

logging.info('I have successfully written out new demand files for month, year: ' + month + ' ' + year)
