import csv
import numpy as np
def save_data(name,data):
    """
    Write a csv file from data.
    data is defined by : 
    data[0] -> [[ps.X.pos,ps.Y.pos,ps.Z.pos]]
    data[1] -> T
    data[2] -> Y
    """
    with open(f"{name}_({data[0][0]},{data[0][1]},{data[0][2]},{data[0][3]}).csv", mode="w",newline='') as f:
        writer = csv.writer(f)
        writer.writerow(data[0]) # write first row wich contains coords
        for t,y in zip(data[1],data[2]):
            writer.writerow([float(np.format_float_scientific(t, precision=4, unique=False, trim='k', sign=False)),float(np.format_float_scientific(y, precision=4, unique=False, trim='k', sign=False))])

def save_excitation(name,data):
    """
    Write a csv file from data.
    data is defined by : 
    data[0] -> T
    data[1] -> Y
    """
    with open(f"{name}_excitation.csv", mode="w",newline='') as f:
        writer = csv.writer(f)
        for t,y in zip(data[0],data[1]):
            # we use scientific notation to avoid writing too many digits in the csv file, which can be a problem for large files
            writer.writerow([float(np.format_float_scientific(t, precision=4, unique=False, trim='k', sign=False)),float(np.format_float_scientific(y, precision=4, unique=False, trim='k', sign=False))])
        
