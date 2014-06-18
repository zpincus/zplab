# Copyright 2014 WUSTL ZPLAB
# Erik Hvatum (ice.rikh@gmail.com)

from acquisition.andor.andor import Camera
from acquisition.brightfield_led.brightfield_led import BrightfieldLed
from acquisition.device import Device, DeviceException
from acquisition.dm6000b.dm6000b import Dm6000b
from acquisition.lumencor.lumencor import Lumencor
from acquisition.peltier.peltier import Peltier

class Root(Device):
    '''The Device representing the root of the device hierarchy.  At the moment, it is convenient for the
    root device to represent zplab-scope, which is the computer running the show.  All device are currently
    directly or indirectly attached to zplab-scope.  It may make sense to abstract the root device into
    a virtual device that has individual computers as its subdevices at some point in the future.'''
    def __init__(self):
        super().__init__(deviceName='zplab-scope Linux system')

#       self._peltier = Peltier(self)
        self._brightfieldLed = BrightfieldLed(self)
        self._dm6000b = Dm6000b(self)
        self._lumencor = Lumencor(self)
        self._camera = Camera(self, andorDeviceIndex=0)

    # Properties for accessing devices are in approximate ascending order of vertical position.  The Peltier controller box happened to be below
    # everything else when this was written.

#   @property
#   def peltier(self):
#       return self._peltier

    @property
    def brightfieldLed(self):
        return self._brightfieldLed

    @property
    def dm6000b(self):
        return self._dm6000b

    @property
    def lumencor(self):
        return self._lumencor

    @property
    def camera(self):
        return self._camera
