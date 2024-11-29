import pandas as pd
import numpy as np

# Read the CSV file
df = pd.read_csv('temperature.csv', header=[0,1])

# Create a dictionary to store temperature data
temperatures = {
    '0': {'time': df[('0', 'X')].dropna().values, 
           'temperature': df[('0', 'Y')].dropna().values},
    '10': {'time': df[('10', 'X')].dropna().values, 
            'temperature': df[('10', 'Y')].dropna().values},
    '23': {'time': df[('23', 'X')].dropna().values, 
            'temperature': df[('23', 'Y')].dropna().values},
    '45': {'time': df[('45', 'X')].dropna().values, 
            'temperature': df[('45', 'Y')].dropna().values}
}

for key in temperatures:
    print(key,temperatures[key])