# Copyright 2014 WUSTL ZPLAB
# Erik Hvatum (ice.rikh@gmail.com)

from acquisition.device import Device
from acquisition.leica_dm.camera_mm import Camera_mm
from acquisition.leica_dm.stage_mm import Stage_mm
import sys

mmpath = '/mnt/scopearray/mm/micro-manager/MMCorePy_wrap/build/lib.linux-x86_64-3.3'
if mmpath not in sys.path:
    sys.path.insert(0, mmpath)
del mmpath

import MMCorePy

class Microscope_mm(Device):
    def __init__(self, mmcore=None):
        super().__init__('Leica DM6000')
        self._appendTypeName('Microscope_mm')

        if mmcore is None:
            self._mmcore = MMCorePy.CMMCore()
            self._mmcore.loadSystemConfiguration("/mnt/scopearray/mm/ImageJ/MMConfig1.cfg")
            self._mmcore.setConfig("acquisition mode", "5X brightfield")
        else:
            self._mmcore = mmcore

        self._camera = Camera_mm(self._mmcore)
        self._addSubDevice(self._camera)
        self._stage = Stage_mm(self._mmcore)
        self._addSubDevice(self._stage)

    @property
    def camera(self):
        return self._camera

    @property
    def stage(self):
        return self._stage
