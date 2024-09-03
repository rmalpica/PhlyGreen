#!/bin/bash

#python3 validator.py (range km) (payload kg) (profile Traditional/Hybrid) (Phi) > outputfile
mkdir TXT
echo
echo "----------------------------------------------------------"
echo "next: 2361 550 Hybrid 0.1 > Simple-Hybrid-Longrange.txt"
echo "----------------------------------------------------------"
python3 validator.py 2361 550 Hybrid 0.1 > Simple-Hybrid-Longrange.txt
echo
echo "----------------------------------------------------------"
echo "next: 2361 550 Traditional 0 > Simple-Traditional-Longrange.txt"
echo "----------------------------------------------------------"
python3 validator.py 2361 550 Traditional 0 > Simple-Traditional-Longrange.txt
echo
echo "----------------------------------------------------------"
echo "next: 1280 1330 Hybrid 0.1 > Simple-Hybrid-Medrange.txt"
echo "----------------------------------------------------------"
python3 validator.py 1280 1330 Hybrid 0.1 > Simple-Hybrid-Medrange.txt
echo
echo "----------------------------------------------------------"
echo "next: 1280 1330 Traditional 0 > Simple-Traditional-Medrange.txt"
echo "----------------------------------------------------------"
python3 validator.py 1280 1330 Traditional 0 > Simple-Traditional-Medrange.txt
echo
echo "----------------------------------------------------------"
echo "next: 396 1960 Hybrid 0.1 > Simple-Hybrid-Shortrange.txt"
echo "----------------------------------------------------------"
python3 validator.py 396 1960 Hybrid 0.1 > Simple-Hybrid-Shortrange.txt
echo
echo "----------------------------------------------------------"
echo "next: 396 1960 Traditional 0 > Simple-Traditional-Shortrange.txt"
echo "----------------------------------------------------------"
python3 validator.py 396 1960 Traditional 0 > Simple-Traditional-Shortrange.txt

mv -f *.txt TXT/