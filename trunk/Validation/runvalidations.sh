#!/bin/bash

#python3 validator.py (range km) (payload kg) (profile Traditional/Hybrid) (cell FELIX_FINGER) > outputfile

#python3 validator.py 2361 550 Hybrid FELIX_FINGER > Hybrid-Longrange.txt
#echo "Hybrid-Longrange.txt done"
#python3 validator.py 2361 550 Traditional FELIX_FINGER > Traditional-Longrange.txt
#echo "Traditional-Longrange.txt done"

#python3 validator.py 1280 1330 Hybrid FELIX_FINGER > Hybrid-Medrange.txt
#echo "Hybrid-Medrange.txt"
#python3 validator.py 1280 1330 Traditional FELIX_FINGER > Traditional-Medrange.txt
#echo "Traditional-Medrange.txt"

#python3 validator.py 396 1960 Hybrid FELIX_FINGER > Hybrid-Shortrange.txt
#echo "Hybrid-Shortrange.txt"
#python3 validator.py 396 1960 Traditional FELIX_FINGER > Traditional-Shortrange.txt
#echo "Traditional-Shortrange.txt"

python3 validator.py 1000 700 Hybrid FELIX_FINGER > Hybrid-1.txt
echo
echo "----------------------------------------------------------"
echo "next"
echo "----------------------------------------------------------"
echo
python3 validator.py 1500 700 Hybrid FELIX_FINGER > Hybrid-2.txt
echo
echo "----------------------------------------------------------"
echo "next"
echo "----------------------------------------------------------"
echo
python3 validator.py 2000 700 Hybrid FELIX_FINGER > Hybrid-3.txt
echo
echo "----------------------------------------------------------"
echo "next"
echo "----------------------------------------------------------"
echo
python3 validator.py 2500 700 Hybrid FELIX_FINGER > Hybrid-4.txt
echo
echo "----------------------------------------------------------"
echo "next"
echo "----------------------------------------------------------"
echo
python3 validator.py 500 700 Hybrid FELIX_FINGER > Hybrid-5.txt