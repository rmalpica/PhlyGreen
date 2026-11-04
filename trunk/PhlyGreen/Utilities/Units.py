def NMtoM(distance):
    return distance * 1825

def MtoNM(distance):
    """Inverse of :func:`NMtoM` (same 1825 m/nm factor, so ranges round-trip)."""
    return distance / 1825

def MtoKN(velocity):
    return velocity * 1.94384 

def KNtoM(velocity):
    return velocity * 0.5144456333854638

def mToft(length):
    return length*3.28084

def ftTom(length):
    return length*0.3048

def kgTolb(weight):
    return weight*2.20462

def lbTokg(weight):
    return weight*0.453592

def m2toft2(area):
    return area*10.7639

def ft2tom2(area):
    return area*0.092903

def wTohp(power):
    return power*0.001341021859

def hpTow(power):
    return power*745.7