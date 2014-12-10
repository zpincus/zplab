# The MIT License (MIT)
#
# Copyright (c) 2014 WUSTL ZPLAB
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Authors: Zach Pincus, Erik Hvatum

from . import stand

GET_CONVERSION_FACTOR_X = 72034
GET_CONVERSION_FACTOR_Y = 73034
GET_CONVERSION_FACTOR_Z = 71042
POS_ABS_X = 72022
POS_ABS_Y = 73022
POS_ABS_Z = 71022
GET_POS_X = 72023
GET_POS_Y = 73023
GET_POS_Z = 71023
INIT_X = 72020
INIT_Y = 73020
INIT_RANGE_Z = 71044
SET_SPEED_Z = 71032
GET_SPEED_Z = 71033
GET_MIN_SPEED_Z = 71058
GET_MAX_SPEED_Z = 71059

class Stage(stand.DM6000Device):
    def _setup_device(self):
        self._x_mm_per_count = float(self.send_message(GET_CONVERSION_FACTOR_X, async=False).response) / 1000
        self._y_mm_per_count = float(self.send_message(GET_CONVERSION_FACTOR_Y, async=False).response) / 1000
        self._z_mm_per_count = float(self.send_message(GET_CONVERSION_FACTOR_Z, async=False).response) / 1000
        self._z_speed_mm_per_second_per_unit = 0.1430278
        self._z_speed_min = int(self.send_message(GET_MIN_SPEED_Z, async=False).response) * self._z_mm_per_count * self._z_speed_mm_per_second_per_unit
        self._z_speed_max = int(self.send_message(GET_MAX_SPEED_Z, async=False).response) * self._z_mm_per_count * self._z_speed_mm_per_second_per_unit
        x, y, z = self.get_position()
        self._update_property('x', x)
        self._update_property('y', y)
        self._update_property('z', z)

    def set_position(self, xyz):
        """Set x, y, and z position to respective elements of xyz tuple/iterable.
        Any may be None to indicate no motion is requested. Units are in mm."""
        x, y, z = xyz
        self.set_x(x)
        self.set_y(y)
        self.set_z(z)

    def _set_pos(self, value, conversion_factor, command):
        if value is None: return
        counts = int(round(value / conversion_factor))
        response = self.send_message(command, counts, intent="move stage to position")

    def set_x(self, x):
        "Set x-axis position in mm"
        self._set_pos(x, self._x_mm_per_count, POS_ABS_X)
        self._update_property('x', x)

    def set_y(self, y):
        "Set y-axis position in mm"
        self._set_pos(y, self._y_mm_per_count, POS_ABS_Y)
        self._update_property('y', y)

    def set_z(self, z):
        "Set z-axis position in mm"
        self._set_pos(z, self._z_mm_per_count, POS_ABS_Z)
        self._update_property('z', z)

    def get_position(self):
        """Return (x,y,z) positionz in mm."""
        return self.get_x(), self.get_y(), self.get_z()

    def _get_pos(self, conversion_factor, command):
        counts = int(self.send_message(command, async=False, intent="get stage position").response)
        mm = counts * conversion_factor
        return mm

    def get_x(self):
        """Get x-axis position in mm."""
        return self._get_pos(self._x_mm_per_count, GET_POS_X)

    def get_y(self):
        """Get y-axis position in mm."""
        return self._get_pos(self._y_mm_per_count, GET_POS_Y)

    def get_z(self):
        """Get z-axis position in mm."""
        return self._get_pos(self._z_mm_per_count, GET_POS_Z)

    def reinit(self):
        self.reinit_x()
        self.reinit_y()
        self.reinit_z()

    def reinit_x(self):
        """Reinitialize x axis to correct for drift or "stuck" stage. Executes synchronously."""
        self.send_message(INIT_X, async=False, intent="init stage x axis")
        self._update_property('x', self.get_x())

    def reinit_y(self):
        """Reinitialize y axis to correct for drift or "stuck" stage. Executes synchronously."""
        self.send_message(INIT_Y, async=False, intent="init stage y axis")
        self._update_property('y', self.get_y())

    def reinit_z(self):
        """Reinitialize z axis to correct for drift or "stuck" stage. Executes synchronously."""
        self.send_message(INIT_RANGE_Z, async=False, intent="init stage z axis")
        self._update_property('z', self.get_z())

    def get_z_speed_range(self):
        """Return min, max z speed values in mm/second"""
        return self._z_speed_min, self._z_speed_max

    def get_z_speed(self):
        """Get z-axis speed in mm/second"""
        counts = int(self.send_message(GET_SPEED_Z, async=False, intent="get z speed").response)
        return counts * self._z_mm_per_count * self._z_speed_mm_per_second_per_unit

    def set_z_speed(self, speed):
        """Get z-axis speed in mm/second"""
        assert self._z_speed_min <= speed <= self._z_speed_max
        counts = int(round(speed / self._z_mm_per_count / self._z_speed_mm_per_second_per_unit))
        self.send_message(SET_SPEED_Z, counts, intent="set z speed")