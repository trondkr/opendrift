import os
import numpy as np
from datetime import datetime

from opendrift import OpenDriftSimulation
from elements import LagrangianArray
from collections import OrderedDict

RIGHT = 0
LEFT = 1

# Defining the leeway element properties
class LeewayObj(LagrangianArray):
    """Extending LagrangianArray with variables relevant for leeway objects.

    """
    variables = LagrangianArray.add_variables([
        ('objectType', {'dtype': np.int16,
                     'unit': '1',
                     'default': 0}),
        ('orientation', {'dtype': np.int16,
                     'unit': '1',
                     'default': 1}),
        ('jibeProbability', {'dtype': np.float32,
                     'unit': '1/h',
                     'default': 0.04}),
        ('downwindSlope', {'dtype': np.float32,
                            'unit': '%',
                            'default': 1}),
        ('crosswindSlope', {'dtype': np.float32,
                            'unit': '1',
                            'default': 1}),
        ('downwindOffset', {'dtype': np.float32,
                          'unit': 'cm/s',
                          'default': 0}),
        ('crosswindOffset', {'dtype': np.float32,
                          'unit': 'cm/s',
                          'default': 0}),
        ('downwindEps', {'dtype': np.float32,
                          'unit': 'cm/s',
                          'default': 0}),
        ('crosswindEps', {'dtype': np.float32,
                          'unit': 'cm/s',
                          'default': 0}),
        ('age_seconds', {'dtype': np.float32,
                         'units': 's',
                         'default': 0})
        ])

class Leeway(OpenDriftSimulation):
    """The Leeway model in the OpenDrift framework.

        Advects a particle (a drifting object) with the ambient current and
        as a function of the wind vector according to the drift properties
        of the object.
    """

    ElementType = LeewayObj

    required_variables = ['x_wind', 'y_wind', 
                          'x_sea_water_velocity', 'y_sea_water_velocity', 
                          'land_binary_mask']

    fallback_values = {'x_wind': 0.0,
                       'y_wind': 0.0,
                       'x_sea_water_velocity': 0.0,
                       'y_sea_water_velocity': 0.0}

    # Default colors for plotting
    status_colors = {'initial': 'green', 'active': 'blue',
                     'missing_data': 'gray', 'stranded': 'red',
                     'evaporated': 'yellow', 'dispersed': 'magenta'}

    # Configuration
    def __init__(self, d=None, *args, **kwargs):

        # Read leeway object properties from file 
        if d is None:
            d = os.path.dirname(os.path.realpath(__file__))
            objprop_file = open(d + '/OBJECTPROP.DAT', 'r')
        else:
            objprop_file = open(d, 'r')

        #objprop_file=open('/home/oyvindb/Pro/opendrift/OBJECTPROP.DAT','r')
        objproptxt=objprop_file.readlines()
        objprop_file.close()
        MAXOBJ=85 # CCC must fix
        self.leewayprop=OrderedDict({})
        for i in xrange(len(objproptxt)//3+1):
            # Stop at first blank line
            if not objproptxt[i*3].strip():
                break
            elems = objproptxt[i*3].split()[0]

            objKey = objproptxt[i*3].split()[0]
            arr = [float(x) for x in objproptxt[i*3+2].split()]
            props = {'OBJNUMBER':i}
            props['Description'] = objproptxt[i*3+1]
            props['DWSLOPE']  = arr[0]
            props['DWOFFSET'] = arr[1]
            props['DWSTD']    = arr[2]
            props['CWRSLOPE'] = arr[3]
            props['CWROFFSET']= arr[4]
            props['CWRSTD']   = arr[5]
            props['CWLSLOPE'] = arr[6]
            props['CWLOFFSET']= arr[7]
            props['CWLSTD']   = arr[8]
            self.leewayprop[objKey] = props

        # Calling general constructor of parent class
        super(Leeway, self).__init__(*args, **kwargs)

    def seed_leeway(self, lon, lat, radius=0, number=1, time=None, radius1=None, lon1=None, lat1=None, time1=None, objectType=0):
        """Seed a given number of particles in a cone-shaped area over a time period.
        """
        # All particles carry their own objectType (number), but so far we only use one for each sim
        # objtype = np.ones(number)*objectType
        
        # Probability of jibing (4 % per hour)
        pjibe = 0.04
         
        if time is None:
            # Use first time of first reader if time is not given for seeding
            try:
                for reader in self.readers.items():
                    if reader[1].start_time is not None:
                        firstReader = reader[1]
                        break
            except:
                raise ValueError('Time must be specified when no '
                                 'reader is added')
            logging.info('Using start time (%s) of reader %s' %
                         (firstReader.start_time, firstReader.name))
            self.start_time = firstReader.start_time
        else:
            self.start_time = time

        if radius1 is None:
            radius1 = radius

        if time1 is None:
            time1 = time

        if lon1 is None:
            lon1 = lon
            lat1 = lat

        # Drift orientation of particles.  0 is right of downwind, 1 is left of downwind
        # orientation = 1*(np.random.rand(number)>=0.5)
        # Odd numbered particles are left-drifting, even are right of downwind.
        orientation = np.r_[:number]%2

        # Downwind leeway properties.
        # Generate normal, N(0,1), random perturbations for leeway coeffs. 
        # Negative downwind slope must be avoided as particles should drift downwind. 
        # The problem arises because of high error variances (see e.g. PIW-1).
        downwindSlope=self.leewayprop.values()[objectType]['DWSLOPE']
        downwindOffset=self.leewayprop.values()[objectType]['DWOFFSET']
        dwstd=self.leewayprop.values()[objectType]['DWSTD']
        rdw = np.zeros(number)
        epsdw = np.zeros_like(rdw)
        for i in xrange(number):
            rdw[i] = np.random.randn(1)
            epsdw[i] = rdw[i]*dwstd
            # Avoid negative downwind slopes
            while dwslo+epsdw[i]/20.0 < 0.0:
                rdw[i] = np.random.randn(1)
                epsdw[i] = rdw[i]*dwstd
        downwindEps = epsdw

        # Crosswind leeway properties
        rcw = np.random.randn(number)
        crosswindSlope[orientation==RIGHT] = self.leewayprop.values()[objectType]['CWRSLOPE']
        crosswindSlope[orientation==LEFT] = self.leewayprop.values()[objectType]['CWLSLOPE']
        crosswindOffset[orientation==RIGHT] = self.leewayprop.values()[objectType]['CWROFFSET']
        crosswindOffset[orientation==LEFT] = self.leewayprop.values()[objectType]['CWLOFFSET']
        crosswindEps[orientation==RIGHT] = rcw[orientation==RIGHT]*self.leewayprop.values()[objectType]['CWRSTD']
        crosswindEps[orientation==LEFT] = rcw[orientation==LEFT]*self.leewayprop.values()[objectType]['CWLSTD']

        # Jibe probability
        jibeProbability = np.ones_like(orientation)*pjibe

        # Calculate the great circle line from lon,lat to lon1,lat1 
        geod = pyproj.Geod(ellps='WGS84')
        clonlats = np.array(geod.npts(lon, lat, lon1, lat1, number, radians=False))
        clons = clonlats[:,0]
        clats = clonlats[:,1]

        # The radius varies linearly from radius to radius1
        radii = np.r_[radius:radius1:number*1j]

        # time is a now vector of length number
        dt = (time1-time)/(number-1)
        times = [time+i*dt for i in range(number)]

        self.seed_point(clons, clats, radii, number, times,
            orientation=orientation, objectType=objectType,
            downwindSlope=downwindSlope, crosswindSlope=crosswindSlope,
            downwindOffset=downwindOffset, crosswindOffset=crosswindOffset,
            downwindEps=downwindEps, crosswindEps=crosswindEps, jibeProbability=jibeProbability)


    def update(self):
        """Update positions and properties of leeway particles."""

        self.elements.age_seconds += self.time_step.total_seconds()

        windspeed = np.sqrt(self.environment.x_wind**2 +
                            self.environment.y_wind**2)
        # CCC update wind direction
        winddir = np.arctan2(self.environment.x_wind, self.environment.y_wind)
        
        # Move particles with the leeway CCC TODO
        dwl_leeway = (self.elements.downwindSlope+self.elements.epsilon/20.0)*windspeed + \
                     self.elements.downwindOffset + self.elements.downwindEpsilon/2.0
        cwl_leeway = self.elements.orientation * \
                     (self.elements.crosswindLeeway*windspeed + \
                      self.elements.crosswindOffset)
        x_leeway = dwl_leeway*np.cos(winddir)+cwl_leeway*np.sin(winddir)
        y_leeway = -dwl_leeway*np.sin(winddir)+cwl_leeway*np.cos(winddir)
        self.update_positions(x_leeway, y_leeway)

        # Deactivate elements on land
        self.deactivate_elements(self.environment.land_binary_mask == 1,
                                 reason='stranded')

        # Move particles with ambient current
        self.update_positions(self.environment.x_sea_water_velocity,
                              self.environment.y_sea_water_velocity)