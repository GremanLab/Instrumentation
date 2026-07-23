
class axes_manager:
    """
    This class allow to have an easy access to all coords where the motor should go during a scan :
    axe.x = List of all coords on x
    axe.y = List of all coords on y
    axe.z = List of all coords on z
    
    To create these list, we can use create_axe(self,val_min,val_max,diff) :
    create a list with all value between val_min and val_max with a step of diff
    example :
        axe.x = axe.create_axe(1,5,0.5)
        print(axe.x)
        >>> [1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5]
    """
    def __init__(self):
        self.x=None
        self.y=None
        self.z=None
    
    def create_axe(self,val_min,val_max,diff):
        axe=[val_min]
        pos=val_min
        while pos+diff<val_max:
            pos+=diff
            axe.append(pos)
        if pos!=val_max:
            axe.append(val_max)
        return axe
    
def axes_init(mode:str,
                var1,var2,var3,
                delta_X:float,delta_Y:float,delta_Z:float)->tuple[axes_manager, bool]:
    """
    Create an axes_manager object which have correct axes (axe.x / axe.y / axe.z) 
    in function of settings which are given.

    This function is only used for scan_by_interf.py
    """
    
    
    err=False # if err== True : need to stop the program
    ##on initialise les axes 
    axe=axes_manager() 

    dx = float(delta_X)
    dy = float(delta_Y)
    dz = float(delta_Z)

    if mode=="point":
        xMin = float(var2[0])
        xMax = float(var1[0])
        if xMax<xMin:
            print("[WARNING] : You have probably inversed P1 and P2 on x coords")
            err=True
            return None, err
        
        yMin = float(var2[1])
        yMax = float(var1[1])

        zMin = float(var2[2])
        zMax = float(var3[2])

    elif mode=="length":
        xMin = -float(var1)
        xMax = 0

        yMin = -float(var2)
        yMax = 0

        zMin = 0
        zMax = float(var3)

    else:
        print("ERROR : Uknown mode")
        err=True
        return None, err
    
    axe.x=axe.create_axe(xMin,xMax,dx)

    axe.y=axe.create_axe(yMin,yMax,dy)

    axe.z=axe.create_axe(zMin,zMax,dz)


    return axe, err
