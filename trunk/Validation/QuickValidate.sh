#!/bin/bash
mkdir quickValidate
#python3 validator.py (range km) (payload kg) (profile Traditional/Hybrid) (cell FELIX_FINGER) > outputfile
python3 validator.py 1500 2000 Hybrid SAMSUNG_LIR18650 > quickValidate.txt 

mv -f *--Temp.png quickValidate/
mv -f *--Heat.png quickValidate/
mv -f *--dTdt.png quickValidate/
mv -f *.txt quickValidate/