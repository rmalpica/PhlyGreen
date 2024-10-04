from pathlib import Path
import os
import sys
import json
import seaborn as sns
import matplotlib.pyplot as plt
import pandas as pd
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

def writeJSON(data,file):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

# grab all the designs from the jsons folder and condense them into a sinlge json
# listing out all the parameters of the different flights to be plotted
def scanDesigns(directory, flights):
    jsons = findJSONs(directory)
    i=0
    for file in jsons:
        i+=1
        print('------------\nFound:\n',file,'\n')

        design = loadJSON(file)

        arch = design['Inputs']['Powerplant']
        miss = design['Inputs']['Mission Name']

        if miss not in flights:
            flights[miss]={}
        if arch not in flights[miss]:
            flights[miss][arch]={'Success':[],'Fail':[]}

        inputs = design['Inputs']
        del inputs['Mission Profile']
        del inputs['Mission Name']
        del inputs['Powerplant']

        if design['Converged']:
            print('Writing',design['Name'], 'to',miss,'-',arch,'- Success')
            outputs = design['Outputs']['Parameters']
            flights[miss][arch]['Success'].append(inputs|outputs)

        else:
            print('Writing',design['Name'],'to',miss,'-',arch,'- Fail')
            flights[miss][arch]['Fail'].append(inputs)
    print('Processed',i,'designs')        
    return flights



# list of plots to be made from the collected data
def traditionalPlots(flight):
    # outputDir is a global variable and the name is already in the json
    filename = os.path.join(outputDir, flight['Name'])  
    data = flight['Outputs']
    try:
        os.mkdir(filename)
    except:
        pass
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
    try:
        os.mkdir(filename)
    except:
        pass
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
# receives a dictionary that contains the keys X and Y pointing to ordered lists
# and plots the Y list over the X list
def plotData(data, X , Y, title, foldername):
    x_data = data[X]
    y_data = data[Y]
    # Create a plot using Seaborn
    sns.lineplot(x=x_data, y=y_data)

    # Add labels and title
    plt.xlabel(X)
    plt.ylabel(Y)
    plt.title(title)

    # Save the plot as a PDF
    filename = os.path.join(foldername, title+".pdf") #create file inside the output directory
    plt.savefig(filename)
    print('||>- Saved \'',title,'\' to',filename)
    plt.close()  # Close the plot

# makes directories as needed
def createDir(dirname):
    srcdir = os.path.dirname(__file__) #script directory
    outdir = os.path.join(srcdir, dirname) #new relative directory
    if not os.path.exists(outdir): # make directory if it doesnt exist already
        os.makedirs(outdir)

    return outdir

# main plots of flight data
def flightPlots(directoryIN, directoryOUT):
    jsons = findJSONs(directoryIN)
    i=0
    for file in jsons:
        i+=1
        flight = loadJSON(file)

        print('>--',i,'-->\n')
        print('Plot nr',i)
        print('Plotting from', file,'\n')
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

# function to plot graphs with three variables at once
# receives a list of dictionaries where each dictionary
# has the keys X Y Z corresponding to a single value
def multiPlot(dictList,X,Y,Z,title,foldername):
    #searches in the data for flights with the same Z
    #puts them all in a dictionary grouped by Z
    #plots Y against X multiple times with a different line for each Z
    data=[]
    for d in dictList:
        data.append({x:d[X],Y:d[Y],Z:d[Z]}) #reorganize the data so that it can go into pandas
    df = pd.DataFrame(data) #convert to pandas dataframe for easier use with seaborn
    sns.scatterplot(data=df, x=X, y=Y, hue=Z)
    # Add labels and title
    plt.xlabel(X)
    plt.ylabel(Y)
    plt.title(title)

    # Save the plot as a PDF
    filename = os.path.join(foldername, title+".pdf") #create file inside the output directory
    plt.savefig(filename)
    print('||>- Saved \'',title,'\' to',filename)
    plt.close()  # Close the plot


# add here whatever plots between two interesting variables coming from the design space json
# plots should cover sweeps of one or two inputs while the rest are constant
def extraPlots(designspace):
    # outputDir is a global variable and the name is already in the json
    filename = os.path.join(outputDir, 'DesignSpace') 
    print(designspace)
    # plots the data
    #plotData(designspace,'Range','','SOC vs Time',filename)

# pick which folder to plot
jsonFolder = 'JSONs' #which folder the jsons should be read from
outputDir = 'Plots' # which folder plots should be stored in
designsJSON = 'designspace.json' # which file the aircraft designs should be writen to and read from

outputDir  = createDir(outputDir)
flightPlots(jsonFolder, outputDir)
try:
    flights=loadJSON(designsJSON)
except:
    flights={}
designspace=scanDesigns(jsonFolder,flights)
writeJSON(designspace,designsJSON)

extraPlots(designspace)