#!/bin/bash
mkdir CompareQuick
#python3 validator.py (range km) (payload kg) (profile Traditional/Hybrid) (cell FELIX_FINGER) > outputfile

echo "----------------------------------------------------------"
echo "next: 2361 550 Hybrid FELIX_FINGER  > Hybrid-Longrange.txt"
echo "----------------------------------------------------------"
python3 validator.py 2361 550 Hybrid FELIX_FINGER 0.1 > Hybrid-Longrange.txt
echo
echo "----------------------------------------------------------"
echo "next: 2361 550 Traditional FELIX_FINGER > Traditional-Longrange.txt"
echo "----------------------------------------------------------"
python3 validator.py 2361 550 Traditional FELIX_FINGER 0 > Traditional-Longrange.txt

mv -f *--Temp.png CompareQuick/
mv -f *--Heat.png CompareQuick/
mv -f *--dTdt.png CompareQuick/
mv -f *.txt CompareQuick/