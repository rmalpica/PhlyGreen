mkdir JSON 2>/dev/null
mkdir TXTlogs 2>/dev/null

python3 FlightSweeps.py

mv *.json JSON/
mv *_log.txt TXTlogs/

# function that plots the json files is missing here