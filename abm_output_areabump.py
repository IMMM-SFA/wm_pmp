# This is a script for post-processing WM-ABM output files and generating a csv that in turn is post-processed
# in Tableau. Tableau is used to generate Figure 1a.

import pandas as pd
import os
import xarray as xr
import numpy as np
import datetime

pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)

# switch to directory with ABM runs
os.chdir('C:\\Users\\yoon644\\OneDrive - PNNL\\Documents\\wm abm data\\wm abm results\\ABM runs\\202104 Mem 02 Corr')

# Load in NLDAS/HUC-2 join table
huc2 = pd.read_csv('NLDAS_HUC2_join.csv')

# Load in states/counties/regions join table
states_etc = pd.read_csv('nldas_states_counties_regions.csv')

# switch to directory with ABM runs
os.chdir('C:\\Users\\yoon644\\Desktop\\corrected test')


# Develop csv file for visualizing crop areas in Tableau
# Load in ABM csv results for cropped areas
for year in range(15): # change back to 70
    print(year)
    abm = pd.read_csv('abm_results_' + str(year+1950))  # change back to 1940
    #abm = abm[(abm.nldas=='x309y67')] ### JY TEMP
    aggregation_functions = {'calc_area': 'sum'}
    if year == 0:
        abm = pd.merge(abm, huc2[['NLDAS_ID', 'NAME']], how='left',left_on='nldas',right_on='NLDAS_ID')
        abm = pd.merge(abm, states_etc[['COUNTYFP','ERS_region','State','NLDAS_ID']],how='left',left_on='nldas',right_on='NLDAS_ID')
        abm_detailed = abm
        abm_detailed['year'] = year+1950  # change back to 1940
        abm_summary = abm.groupby(['crop','NAME'], as_index=False).aggregate(aggregation_functions)
        abm_summary['year'] = year+1950
    else:
        abm = pd.merge(abm, huc2[['NLDAS_ID', 'NAME']], how='left',left_on='nldas',right_on='NLDAS_ID')
        abm = pd.merge(abm, states_etc[['COUNTYFP','ERS_region','State','NLDAS_ID']],how='left',left_on='nldas',right_on='NLDAS_ID')
        abm['year'] = year + 1950
        #abm_detailed = abm_detailed.append(abm)
        abm_summary_to_append = abm.groupby(['crop','NAME'], as_index=False).aggregate(aggregation_functions)
        abm_summary_to_append['year'] = year+1950
        abm_summary = abm_summary.append(abm_summary_to_append)

# Join to sigmoid model
abm_summary['Join'] = 1
sigmoid = pd.read_csv('AreaBumpModelv3.csv')
abm_summary = pd.merge(abm_summary, sigmoid, on='Join', how='inner')
abm_summary = abm_summary.rename(columns={"crop": "Sub-category", "NAME": "_Category", "calc_area": "Total", "year": "Year"})
abm_summary.to_csv('abm_join_sigmoid_corrected_test.csv', index=False)