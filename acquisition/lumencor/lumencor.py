# Copyright 2014 WUSTL ZPLAB

import copy
import serial
import time
from acquisition.device import Device
from acquisition.lumencor.lumencor_exception import LumencorException

class Lumencor(Device):
    class LampState:
        def __init__(self, enabled, power, idx):
            self.enabled = enabled
            self.power = power
            self._idx = idx

        def __str__(self):
            return 'enabled={} power={}'.format(self._enabled, self._power)

        def __repr__(self):
            return 'Lumencor.LampState(enabled={}, power={}, idx={})'.format(self._enabled, self._power, self._idx)

        @property
        def enabled(self):
            return self._enabled

        @enabled.setter
        def enabled(self, enabled):
            self._enabled = bool(enabled)

        @property
        def power(self):
            return self._power

        @power.setter
        def power(self, power):
            if power < 0 or power > 255:
                raise ValueError('power argument must be in the range [0, 255].')
            self._power = int(power)

        @property
        def idx(self):
            return self._idx

    _lampNames = [
        'red',
        'green',
        'cyan',
        'UV',
        'blue',
        'teal' ]
#   _lampNamesToIndexes = dict(zip(Lumencor._lampNames, range(len(Lumencor._lampNames))))
    _lampDisableMasks = bytearray((0x01, 0x02, 0x04, 0x08, 0x20, 0x40))
    _lampDisableCommandBase = bytearray((0x4f, 0x00, 0x50))
    _lampPowerMasks = bytearray((0x08, 0x04, 0x02, 0x01, 0x01, 0x02))
    _lampRgcuPowerCommandBase = bytearray((0x53, 0x18, 0x03, 0x00, 0xF0, 0x00, 0x50))
    _lampBtPowerCommandBase = bytearray((0x53, 0x1A, 0x03, 0x00, 0xF0, 0x00, 0x50))

    def __init__(self, serialPortDescriptor='/dev/ttySptrx', name='Lumencor Spectra-X'):
        super().__init__(name)
        self._appendTypeName('Lumencor')
        self._serialPort = serial.Serial(serialPortDescriptor, 9600, timeout=1)
        if not self._serialPort.isOpen():
            raise LumencorException('Failed to open {}.'.format(serialPortDescriptor))
        # RS232 Lumencor docs state: "The [following] two commands MUST be issued after every power cycle to properly configure controls for further commands."
        # "Set GPIO0-3 as open drain output"
        self._write(bytearray((0x57, 0x02, 0xFF, 0x50)))
        # "Set GPI05-7 push-pull out, GPIO4 open drain out"
        self._write(bytearray((0x57, 0x03, 0xAB, 0x50)))
        # The lumencor box replies with nonsense to the first get temperature request.  We issue a get temperature request and ignore the result so that the next
        # get temperature request returns useful data.
        ignored = self.temperature
        del ignored
        self._lampStates = {name : Lumencor.LampState(False, 0, idx) for idx, name in enumerate(Lumencor._lampNames)}
        self._disablement = 0x0f
        # We don't know what state the Lumencor box was when we started, and we have no way of querying it.  However, we want its state to match our idea of its
        # state, which is all lamps disabled and at zero power, as set by the previous line of code.
        # First, all red, green, cyan, and UV lamps are set to zero power.
        c = Lumencor._lampRgcuPowerCommandBase.copy()
        c[3] = 0x0F
        self._applyPower(c, 0)
        self._write(c)
        # Next, blue and teal are set to zero power
        c = Lumencor._lampBtPowerCommandBase.copy()
        c[3] = 0x03
        self._applyPower(c, 0)
        self._write(c)
        # Finally, all lamps are disabled
        c = Lumencor._lampDisableCommandBase.copy()
        c[1] |= 0x7f
        self._write(c)

    def _write(self, byteArray):
        print(''.join('{:02x} '.format(x) for x in byteArray))
        byteCountWritten = self._serialPort.write(byteArray)
        byteCount = len(byteArray)
        if byteCountWritten != byteCount:
            raise LumencorException('Attempted to write {} bytes to Lumencor serial port, but only {} bytes were written.'.format(byteCount, byteCountWritten))

    def _applyPower(self, command, power):
        if power < 0 or power > 0xff:
            raise ValueError('power < 0 or power > 0xff.')
        power = 0xff - power
        command[4] |= (power & 0xf0) >> 4
        command[5] |= (power & 0x0f) << 4

    def _updateDisablement(self):
        disablement = self._disablement
        for lampName, lampState in self._lampStates.items():
            if not lampState.enabled:
                disablement |= Lumencor._lampDisableMasks[lampState.idx]
            else:
                disablement &= 0x7f ^ Lumencor._lampDisableMasks[lampState.idx]
        # Only issue disablement command if disablement state has changed
        if disablement != self._disablement:
            print('updating')
            c = Lumencor._lampDisableCommandBase.copy()
            c[1] = disablement
            self._write(c)
            self._disablement = disablement

    @property
    def temperature(self):
        self._write(bytearray((0x53, 0x91, 0x02, 0x50)))
        r = self._serialPort.read(2)
        if len(r) == 2:
            return ((r[0] << 3) | (r[1] >> 5)) * 0.125

    @property
    def lampStates(self):
        '''Returns a copy of the dict containing lamp names -> current lamp states.'''
        return copy.deepcopy(self._lampStates)

    @lampStates.setter
    def lampStates(self, lampStates):
        '''Apply new lamp states contained in the lampStates argument, which should be a dict of lamp names to LampState objects.  The state of any lamp
        not appearing in the lampStates argument dict is not modified.  So, lumencoreinstance.lampStates = {} is a no-op.  The specified state changes
        are consolidated into the fewest number of serial commands required before being dispatched to the Lumencor hardware.'''
        from IPython.core.debugger import Tracer; breakpoint1 = Tracer();
        power_rgcu = {}
        power_bt = {}
        for lampName, newLampState in lampStates.items():
            curPower = self._lampStates[lampName].power
            newPower = newLampState.power
            if newPower != curPower:
#               if lampName in ['red', 'green', 'cyan', 'uv']:
                if newLampState.idx in range(4): # Same effect as line above, but faster
                    powerdict = power_rgcu
                else:
                    powerdict = power_bt

                if newPower in powerdict:
                    lampIdxs = powerdict[newPower]
                    lampIdxs.append(newLampState.idx)
                else:
                    powerdict[newPower] = [newLampState.idx]
            lampState = self._lampStates[lampName]
            lampState.enabled = newLampState.enabled
            lampState.power = newLampState.power

        def updatePowers(commandBase, powerdict):
            if len(powerdict) > 0:
                c = commandBase.copy()
                for power, lampIdxs in powerdict.items():
                    self._applyPower(c, power)
                    for lampIdx in lampIdxs:
                        c[3] |= Lumencor._lampPowerMasks[lampIdx]
                self._write(c)

        updatePowers(Lumencor._lampRgcuPowerCommandBase, power_rgcu)
        updatePowers(Lumencor._lampBtPowerCommandBase, power_bt)
        self._updateDisablement()
