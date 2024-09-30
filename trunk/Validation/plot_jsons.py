from pathlib import Path
import os
import sys
import json
import seaborn as sns
import matplotlib.pyplot as plt

# this way directories can be made relative to the script in an OS agnostic way
def findJSONs(directory):
    srcdir = os.path.dirname(__file__) #script directory
    directory = os.path.join(srcdir, directory) #directory relative to script
    return Path(directory).glob('*.json') #returns every json file in directory

#load the json
def loadJSON(file):
    with open(file, 'r') as f:
        data = json.load(f)
    return data

# list of plots to be made from the collected data
def traditionalPlots(flight):
    # outputDir is a global variable and the name is already in the json
    filename = os.path.join(outputDir, flight['Name'])  
    data = flight['Outputs']

    plotData(data,'Time','Beta','Beta vs Time',filename)
    plotData(data,'Time','Fuel Energy','Fuel Energy vs Time',filename)
    plotData(data,'Time','Power','Power vs Time',filename)
    plotData(data,'Time','Altitude','Altitude vs Time',filename)

# extra plots that are made only when the configuration is hybrid
def hybridPlots(flight):
    # outputDir is a global variable and the name is already in the json
    filename = os.path.join(outputDir, flight['Name']) 
    
    data = flight['Outputs']
    dataHeat = data['Battery Heating']

    # plots the data
    plotData(data,'Time','SOC','SOC vs Time',filename)
    plotData(data,'Time','Beta','Beta vs Time',filename)
    plotData(data,'Time','Fuel Energy','Fuel Energy vs Time',filename)
    plotData(data,'Time','Power','Power vs Time',filename)
    plotData(data,'Time','Battery Energy','Battery Energy vs Time',filename)
    plotData(data,'Time','Altitude','Altitude vs Time',filename)
    plotData(data,'Time','Phi','Phi vs Time',filename)

    # battery heat stuff
    plotData(dataHeat,'Time','Temperature','Temperature vs Time',filename)
    plotData(dataHeat,'Time','dTdt','Change in Temperature vs Time',filename)
    plotData(dataHeat,'Time','Heat','Heating Power vs Time',filename)

# function to plot the data in a generic way so that all plots have the same formatting
def plotData(data, X , Y, title, filename):
    x_data = data[X]  # Assuming 'x' is a list of values
    y_data = data[Y]  # Assuming 'y' is a list of values
    # Create a plot using Seaborn
    #plt.figure(figsize=(10, 6))  # Set the figure size
    sns.lineplot(x=x_data, y=y_data)

    # Add labels and title
    plt.xlabel(X)
    plt.ylabel(Y)
    plt.title(title)

    # Save the plot as a PDF
    filename = filename+title+".pdf"
    plt.savefig(filename)
    print('Saved \'',title,'\' to',filename)
    plt.close()  # Close the plot to avoid overwriting issues

# makes directories as needed
def createDir(dirname):
    srcdir = os.path.dirname(__file__) #script directory
    outdir = os.path.join(srcdir, dirname) #new relative directory
    if not os.path.exists(outdir): # make directory if it doesnt exist already
        os.makedirs(outdir)

    return outdir

# main function that runs the plotting
def runPlots(directoryIN, directoryOUT):
    jsons = findJSONs(directoryIN)
    i=0
    for file in jsons:
        i+=1
        flight = loadJSON(file)

        print('>--',i,'-->\n')
        print('Plot nr',i)
        print('Plotting ', file)
        if not flight['Converged']:
            print('\nINVALID DESIGN, SKIPPING') # in the future this can be useful for gathering where in the design space an input leads to failure

        else:
            powerplant = flight['Inputs']['Powerplant']
            if  powerplant == 'Hybrid':
                hybridPlots(flight)
            elif powerplant == 'Traditional':
                traditionalPlots(flight)
            else:
                raise ValueError('invalid powerplant')
        print('\n<--',i,'--<')

# pick which folder to plot
jsonFolder = 'JSONs'
outputDir = 'Plots'
outputDir  = createDir(outputDir)
runPlots(jsonFolder, outputDir)