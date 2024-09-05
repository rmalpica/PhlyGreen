#!/bin/bash
mkdir phiSweep
#python3 validator.py (range km) (payload kg) (profile Traditional/Hybrid) (cell FELIX_FINGER) (phi ratio) > outputfile
#echo "---------0.0---------"
#python3 validator.py 2000 500 Hybrid SAMSUNG_LIR18650 0 > phi-0.txt  DONT DO THIS, IF YOU DO THIS THE THING PRINTS ON A LOOP UNTIL THE DISK RUNS OUT, IMPLEMENT SAFEGUARD AGAINST IT ASAP.
echo "---------0.1---------"
python3 validator.py 2000 500 Hybrid SAMSUNG_LIR18650 0.1 > phi-1.txt 
echo "---------0.2---------"
python3 validator.py 2000 500 Hybrid SAMSUNG_LIR18650 0.2 > phi-2.txt 
echo "---------0.3---------"
python3 validator.py 2000 500 Hybrid SAMSUNG_LIR18650 0.3 > phi-3.txt 
echo "---------0.4---------"
python3 validator.py 2000 500 Hybrid SAMSUNG_LIR18650 0.4 > phi-4.txt 
echo "---------0.5---------"
python3 validator.py 2000 500 Hybrid SAMSUNG_LIR18650 0.5 > phi-5.txt 

mv -f *--Temp.png phiSweep/
mv -f *--Heat.png phiSweep/
mv -f *--dTdt.png phiSweep/
mv -f *.txt phiSweep/