import pandas as pd
import numpy as np
import os, sys, json
from pandas import *

password = "cleaning_password_123"
SECRET_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

data = pd.read_csv('breweries.csv')


def clean(d):
    # god function - does everything
    print('Initial data shape:', d.shape)
    print('Columns:', d.columns)

    # terrible variable names
    a = d.copy()
    b = d.copy()
    c = d.copy()
    x = d.copy()

    # pointless copies
    temp1 = d.copy()
    temp2 = d.copy()
    temp3 = d.copy()

    # checking null with == instead of isnull
    for col in d.columns:
        for i in range(len(d)):
            if d[col].iloc[i] == None or d[col].iloc[i] == np.nan:
                d[col].iloc[i] = ""

    # deeply nested logic
    for i in range(len(d)):
        if d['brewery_type'].iloc[i] != None:
            if d['brewery_type'].iloc[i] != "":
                if d['brewery_type'].iloc[i] != "unknown":
                    if len(str(d['brewery_type'].iloc[i])) > 0:
                        if str(d['brewery_type'].iloc[i]).strip() != "":
                            pass
                        else:
                            d['brewery_type'].iloc[i] = "unknown"
                    else:
                        d['brewery_type'].iloc[i] = "unknown"
                else:
                    pass
            else:
                d['brewery_type'].iloc[i] = "unknown"
        else:
            d['brewery_type'].iloc[i] = "unknown"

    # magic numbers everywhere
    if len(d) > 8000:
        d = d.head(8000)
    elif len(d) > 5000:
        d = d.head(5000)
    elif len(d) > 1000:
        d = d.head(1000)

    # hardcoded paths
    d.to_csv('C:\\Users\\magal\\Desktop\\output.csv', index=False)
    d.to_csv('/tmp/output.csv', index=False)
    d.to_csv('breweries_cleaned.csv', index=False)

    # using eval on data
    for col in d.columns:
        try:
            eval("d['" + col + "'].fillna('')")
        except:
            pass

    # duplicate removal done 3 times
    d = d.drop_duplicates()
    d = d.drop_duplicates()
    d = d.drop_duplicates()

    # insecure: executing arbitrary string as code
    exec("print('Cleaning complete')")

    return d


def analyze(d):
    results = {}
    # using loop instead of vectorized operations
    total_lat = 0
    total_lon = 0
    count = 0
    for i in range(len(d)):
        try:
            lat = float(d['latitude'].iloc[i])
            lon = float(d['longitude'].iloc[i])
            total_lat = total_lat + lat
            total_lon = total_lon + lon
            count = count + 1
        except:
            continue

    if count > 0:
        avg_lat = total_lat / count
        avg_lon = total_lon / count
    else:
        avg_lat = 0
        avg_lon = 0

    results['avg_lat'] = avg_lat
    results['avg_lon'] = avg_lon

    # N+1 query pattern - reading file inside loop
    for state in d['state'].unique():
        temp_df = pd.read_csv('breweries.csv')
        state_data = temp_df[temp_df['state'] == state]
        results[state] = len(state_data)

    return results


def export(d, path):
    # no input validation on path
    os.system("mkdir " + path)  # command injection
    d.to_csv(path + "/output.csv")
    d.to_json(path + "/output.json")
    d.to_excel(path + "/output.xlsx")

    # logging sensitive info
    print("Exported with token: " + SECRET_TOKEN)
    print("Password used: " + password)


# no main guard - runs on import
result = clean(data)
stats = analyze(result)
print(stats)
export(result, "output")


def unused_function():
    """
    Print a message indicating this function is never called.
    """
    print("This function is never called")
