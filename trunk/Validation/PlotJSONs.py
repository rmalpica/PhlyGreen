from pathlib import Path
import os
import sys
import json
import seaborn as sns
import matplotlib.pyplot as plt
import pandas as pd


# makes directories as needed on the script directory
def createDir(dirname):
    srcdir = os.path.dirname(__file__) #script directory
    outdir = os.path.join(srcdir, dirname) #new relative directory
    try:
        os.makedirs(outdir)
    except: #if it already exists, ignore the error
        pass
    return outdir

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

#write data to json
def writeJSON(data,file):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

# grab all the designs from the jsons folder and condense them into a sinlge json
# listing out all the parameters of the different flights to be plotted
# directory is the folder where the flight jsons are
# designsJSON is the filename of the json where all the different design parameters will be saved
def scanDesigns(directory, designsJSON):
    try:
        flights=loadJSON(designsJSON)
    except:
        print(designsJSON,"not found and will be created")
        flights={}

    jsons = findJSONs(directory)
    i=0
    for file in jsons:
        i+=1
        print('- - - - - - - -\nFound:\n',file,'\n')

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
    writeJSON(flights,designsJSON)
    return flights



# list of plots to be made from the collected data
def traditionalPlots(flight,folder):

    data = flight['Outputs']

    plotData(data,'Time','Beta','Beta vs Time',folder)
    plotData(data,'Time','Fuel Energy','Fuel Energy vs Time',folder)
    plotData(data,'Time','Power','Power vs Time',folder)
    plotData(data,'Time','Altitude','Altitude vs Time',folder)

# extra plots that are made only when the configuration is hybrid
def hybridPlots(flight,folder):

    # plots the data
    data = flight['Outputs']
    dataHeat = data['Battery Heating']

    plotData(data,'Time','SOC','SOC vs Time',folder)
    plotData(data,'Time','Beta','Beta vs Time',folder)
    plotData(data,'Time','Fuel Energy','Fuel Energy vs Time',folder)
    plotData(data,'Time','Power','Power vs Time',folder)
    plotData(data,'Time','Battery Energy','Battery Energy vs Time',folder)
    plotData(data,'Time','Altitude','Altitude vs Time',folder)
    plotData(data,'Time','Phi','Phi vs Time',folder)

    # battery heat stuff
    plotData(dataHeat,'Time','Temperature','Temperature vs Time',folder)
    plotData(dataHeat,'Time','dTdt','Change in Temperature vs Time',folder)
    plotData(dataHeat,'Time','Heat','Heating Power vs Time',folder)

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

# main plots of flight data
def plotFlights(directoryIN,directoryOUT):

    # start by creating the folder for the plots
    plotsDir = createDir(directoryOUT)
    #find the jsons containing the flights
    jsons = findJSONs(directoryIN)

    i=0
    for file in jsons:
        i+=1
        flight = loadJSON(file)

        print('>--',i,'-->\n')
        print('Plot nr',i)
        print('Plotting from', file,'\n')
        if not flight['Converged']: # skip any unconverged file as those dont have data to plot
            print('\nINVALID DESIGN, SKIPPING') # in the future this can be useful for gathering where in the design space an input leads to failure

        else:
            # create folder to store the plots of this flight
            flightDir = os.path.join(plotsDir, flight['Name'])
            try:
                os.mkdir(flightDir)
            except:
                pass
            #run the appropriate plots depending on the powerplant
            powerplant = flight['Inputs']['Powerplant']
            if  powerplant == 'Hybrid':
                hybridPlots(flight,flightDir)
            elif powerplant == 'Traditional':
                traditionalPlots(flight,flightDir)
            else:
                raise ValueError('invalid powerplant')
        print('\n<--',i,'--<')

# add here whatever plots between two interesting variables coming from the design space json
# plots should cover sweeps of one or two inputs while the rest are constant
def extraPlots(designspace,filename):
    print(loadJSON(designspace))
    # plots the data
    #plotData(designspace,'Range','','SOC vs Time',filename)
