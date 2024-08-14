#!/bin/bash

#python3 validator.py (range km) (payload kg) (profile Traditional/Hybrid) > outputfile

python3 validator.py 2361 550 Hybrid  > Simple-Hybrid-Longrange.txt
echo "Simple-Hybrid-Longrange.txt done"
python3 validator.py 2361 550 Traditional  > Simple-Traditional-Longrange.txt
echo "Simple-Traditional-Longrange.txt done"

python3 validator.py 1280 1330 Hybrid  > Simple-Hybrid-Medrange.txt
echo "Simple-Hybrid-Medrange.txt"
python3 validator.py 1280 1330 Traditional  > Simple-Traditional-Medrange.txt
echo "Simple-Traditional-Medrange.txt"

python3 validator.py 396 1960 Hybrid  > Simple-Hybrid-Shortrange.txt
echo "Simple-Hybrid-Shortrange.txt"
python3 validator.py 396 1960 Traditional  > Simple-Traditional-Shortrange.txt
echo "Simple-Traditional-Shortrange.txt"