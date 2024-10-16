from pathlib import Path
import os
import sys
import json
import seaborn as sns
import matplotlib.pyplot as plt
import pandas as pd
import multiprocessing

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

    #plotData(data,'Time','SOC','SOC vs Time',folder)
    plotData(data,'Time','Beta','Beta vs Time',folder)
    plotData(data,'Time','Fuel Energy','Fuel Energy vs Time',folder)
    plotData(data,'Time','Power','Power vs Time',folder)
    plotData(data,'Time','Battery Energy','Battery Energy vs Time',folder)
    plotData(data,'Time','Altitude','Altitude vs Time',folder)
    plotData(data,'Time','Phi','Phi vs Time',folder)

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
        data.append({X:d[X],Y:d[Y],Z:d[Z]}) #reorganize the data so that it can go into pandas
    df = pd.DataFrame(data) #convert to pandas dataframe for easier use with seaborn
    sns.scatterplot(data=df, x=X, y=Y, hue=Z)
    # Add labels and title
    plt.xlabel(X)
    plt.ylabel(Y)
    plt.title(title)

    # Save the plot as a PDF
    filename = os.path.join(foldername, title+".pdf") #create file inside the output directory
    plt.savefig(filename)
    print(']]=> Saved \'',title,'\' to',filename)
    plt.close()  # Close the plot

def heatMap(dictList,X,Y,Z,title,foldername):
    #searches in the data for flights with the same Z
    #puts them all in a dictionary grouped by Z
    #plots Y against X multiple times with a different line for each Z
    data=[]
    for d in dictList:
        data.append({X:d[X],Y:d[Y],Z:d[Z]}) #reorganize the data so that it can go into pandas
    df = pd.DataFrame(data) #convert to pandas dataframe for easier use with seaborn
    df = df.pivot(index=Y, columns=X, values=Z)
    sns.heatmap(data=df)
    # Add labels and title
    plt.xlabel(X)
    plt.ylabel(Y)
    plt.title(title)

    # Save the plot as a PDF
    filename = os.path.join(foldername, title+".pdf") #create file inside the output directory
    plt.savefig(filename)
    print(']]=> Saved \'',title,'\' to',filename)
    plt.close()  # Close the plot


# = = # = = # = = # = = # = = # = = # = = # = = # = = # = = # = = # = = # = = # = = # = = # = = # = = # = = # = = # = = # = = # = = # = = #
# here begins the chatgpt code hell:

# Function to process a single flight (JSON file)
def process_flight(file, plotsDir):
    flight = loadJSON(file)

    if not flight['Converged']:  # skip unconverged files
        print(f'\nINVALID DESIGN, SKIPPING: {file}')
        return

    # Create folder to store the plots for this flight
    flightDir = os.path.join(plotsDir, flight['Name'])
    os.makedirs(flightDir, exist_ok=True)

    # Run the appropriate plots depending on the powerplant
    powerplant = flight['Inputs']['Powerplant']
    if powerplant == 'Hybrid':
        hybridPlots(flight, flightDir)
    elif powerplant == 'Traditional':
        traditionalPlots(flight, flightDir)
    else:
        raise ValueError('Invalid powerplant')

def plotFlights(directoryIN, directoryOUT):
    # Create the output directory for plots
    plotsDir = createDir(directoryOUT)

    # Find the JSON files containing the flights
    jsons = findJSONs(directoryIN)

    # Set up multiprocessing pool
    num_workers = multiprocessing.cpu_count()  # Use all available CPU cores
    pool = multiprocessing.Pool(processes=num_workers)

    # Process flights in parallel
    pool.starmap(process_flight, [(file, plotsDir) for file in jsons])

    # Close and join the pool
    pool.close()
    pool.join()

# Function to process and plot for a single mission-powerplant combination
def process_mission_powerplant(mission, powerplant, db, voi, outfolder):
    print('++++++++++++++++++++++++++++++++++')
    print('Mission:', mission)
    print('Powerplant:', powerplant)

    # Create folder corresponding to the mission and powerplant combo
    foldername = os.path.join(outfolder, mission, powerplant)
    os.makedirs(foldername, exist_ok=True)

    # Use only successful designs
    data = db[mission][powerplant]['Success']
    X = voi['In'][0]
    Z = voi['In'][1]

    # Plot with either X or Z as the hue
    for Y in voi['To Plot']:
        try:
            title = f"{Y} VS {X} over {Z}"
            multiPlot(data, X, Y, Z, title, foldername)

            title = f"{Y} VS {Z} over {X}"
            multiPlot(data, Z, Y, X, title, foldername)

            title = f"{Y} mapped on {X} vs {Z}"
            heatMap(data, X, Z, Y, title, foldername)

        except KeyError:
            print('ERROR: INVALID KEY, SKIPPING')
            print("KEY:", Y)

def extraPlots(json, voi, outfolder):
    print('Plotting Extras')
    X = voi['In'][0]
    Z = voi['In'][1]
    db = loadJSON(json)

    # Prepare list of tasks (mission, powerplant combinations)
    tasks = []
    for mission in db:
        for powerplant in db[mission]:
            tasks.append((mission, powerplant, db, voi, outfolder))

    # Set up multiprocessing pool
    num_workers = multiprocessing.cpu_count()  # Use all available CPU cores
    pool = multiprocessing.Pool(processes=num_workers)

    # Process each mission-powerplant combination in parallel
    pool.starmap(process_mission_powerplant, tasks)

    # Close and join the pool
    pool.close()
    pool.join()

"""
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

        print('\n>--',i,'-->')
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

# receives a Variables Of Interest argument
# that defines which two parameters are being swept
# and which keys should be automatically plotted for those two
def extraPlots(json,voi,outfolder):
    print('= - = - = - = - = - = - = - = - = - = - = - = - = - = - =')
    print('Plotting Extras')
    X=voi['In'][0]
    Z=voi['In'][1]
    print('Starting extra plots, sweep over',X,'and',Z)
    i=0
    db=loadJSON(json)

    for mission in db:
        print('++++++++++++++++++++++++++++++++++')
        print('Mission:',mission)
        for powerplant in db[mission]:
            print('++++++++++++++++++++++++++++++++++')
            print('Powerplant:',powerplant)
            # Create folder corresponding to the mission and powerplant combo
            foldername=os.path.join(outfolder,mission,powerplant)
            os.makedirs(foldername, exist_ok = True)

            # use only successful designs
            data = db[mission][powerplant]['Success']
            for Y in voi['To Plot']: #plot with either X or Z as the hue
                i+=1
                print('\n>==',i,'==>')
                try:
                    title = f"{Y} VS {X} over {Z}"
                    multiPlot(data, X, Y, Z, title, foldername)

                    title = f"{Y} VS {Z} over {X}"
                    multiPlot(data, Z, Y, X, title, foldername)

                    title = f"{Y} mapped on {X} vs {Z}"
                    heatMap(data, X, Z, Y, title, foldername)
                except KeyError:
                    print('ERROR: INVALID KEY, SKIPPING')
                    print("KEY:",Y)
                print('<==',i,'==<\n')"""