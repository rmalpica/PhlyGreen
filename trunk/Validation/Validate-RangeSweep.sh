#!/bin/bash
mkdir rangeSweep
#python3 validator.py (range km) (payload kg) (profile Traditional/Hybrid) (cell FELIX_FINGER) (phi ratio) > outputfile
echo "---------0.1---------"
python3 validator.py 500 1000 Hybrid FELIX_FINGER 0.1 > phi-1.txt 
echo "---------0.2---------"
python3 validator.py 1000 1000 Hybrid FELIX_FINGER 0.1 > phi-2.txt 
echo "---------0.3---------"
python3 validator.py 1500 1000 Hybrid FELIX_FINGER 0.1 > phi-3.txt 
echo "---------0.4---------"
python3 validator.py 2000 1000 Hybrid FELIX_FINGER 0.1 > phi-4.txt 
echo "---------0.5---------"
python3 validator.py 2500 1000 Hybrid FELIX_FINGER 0.1 > phi-5.txt 

mv -f *--Temp.png rangeSweep/
mv -f *--Heat.png rangeSweep/
mv -f *--dTdt.png rangeSweep/
mv -f *.txt rangeSweep/