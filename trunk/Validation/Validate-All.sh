#!/bin/bash
mkdir dTdt
mkdir Power
mkdir TXT
mkdir Temp
#python3 validator.py (range km) (payload kg) (profile Traditional/Hybrid) (cell FELIX_FINGER) > outputfile
echo "----------------------------------------------------------"
echo "doing hybrid vs traditional range comparisons"
echo
echo "----------------------------------------------------------"
echo "next: 2361 550 Hybrid FELIX_FINGER > Hybrid-Longrange.txt"
echo "----------------------------------------------------------"
python3 validator.py 2361 550 Hybrid FELIX_FINGER 0.1 > Hybrid-Longrange.txt
echo
echo "----------------------------------------------------------"
echo "next: 2361 550 Traditional FELIX_FINGER > Traditional-Longrange.txt"
echo "----------------------------------------------------------"
python3 validator.py 2361 550 Traditional FELIX_FINGER 0.1 > Traditional-Longrange.txt
echo
echo "----------------------------------------------------------"
echo "next: 1280 1330 Hybrid FELIX_FINGER > Hybrid-Medrange.txt"
echo "----------------------------------------------------------"
python3 validator.py 1280 1330 Hybrid FELIX_FINGER 0.1 > Hybrid-Medrange.txt
echo
echo "----------------------------------------------------------"
echo "next: 1280 1330 Traditional FELIX_FINGER > Traditional-Medrange.txt"
echo "----------------------------------------------------------"
python3 validator.py 1280 1330 Traditional FELIX_FINGER 0.1 > Traditional-Medrange.txt
echo
echo "----------------------------------------------------------"
echo "next: 396 1960 Hybrid FELIX_FINGER > Hybrid-Shortrange.txt"
echo "----------------------------------------------------------"
python3 validator.py 396 1960 Hybrid FELIX_FINGER 0.1 > Hybrid-Shortrange.txt
echo
echo "----------------------------------------------------------"
echo "next: 396 1960 Traditional FELIX_FINGER > Traditional-Shortrange.txt"
echo "----------------------------------------------------------"
python3 validator.py 396 1960 Traditional FELIX_FINGER 0.1 > Traditional-Shortrange.txt

mv -f *--Temp.png Temp/
mv -f *--Heat.png Power/
mv -f *--dTdt.png dTdt/
mv -f *.txt TXT/