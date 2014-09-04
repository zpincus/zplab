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
# Authors: Erik Hvatum

import greenlet
import numpy
from PyQt5 import Qt
import sys
import time



def _brenner(im, direction):
    if direction == 'h':
        xo = 2
        yo = 0
    elif direction == 'v':
        xo = 0
        yo = 2
    else:
        raise ValueError('direction must be h or v.')
    iml = numpy.pad(im[0:im.shape[0]-yo, 0:im.shape[1]-xo], ((yo, 0), (xo, 0)), mode='constant')
    imr = im.copy()
    if direction == 'h':
        imr[:, :xo] = 0
    else:
        imr[:yo, :] = 0
    return iml - imr

def brennerFocusMeasure(im):
    imh = _brenner(im, 'h')
    imv = _brenner(im, 'v')
    return numpy.sqrt(imh**2 + imv**2)



class LinearSearchAutofocuser:
    def __init__(self, camera, zDrive, minZ, maxZ, stepsPerRound, numberOfRounds, focusMeasure=brennerFocusMeasure, rw=None):
        self._running = False
        self._camera = camera
        self._zDrive = zDrive
        self._zRange = (minZ, maxZ)
        self._stepsPerRound = stepsPerRound
        self._numberOfRounds = numberOfRounds
        self._focusMeasure = focusMeasure
        self._rw = rw
        self.idleGt = greenlet.getcurrent()
        self.runGt = greenlet.greenlet(self._run)
        self.bestZ = None

    def abort(self):
        if self._running:
            self.runGt.switch(False)

    def _run(self):
        t0 = time.time()
        self.bestZ = None
        self._zDrive.posChanged.connect(self._zDrivePosChanged)
        self._running = True

        curZRange = self._zRange
        buffers = [self._camera.makeAcquisitionBuffer() for i in range(self._stepsPerRound)]
        
        for roundIdx in range(0, self._numberOfRounds):
            print('Starting autofocus round {}.'.format(roundIdx))
            fmvs = []
            stepIdxsDone = []
            steps = numpy.linspace(*curZRange, num=self._stepsPerRound)
            self._camera._camera.AT_Flush()
            self._camera.shutter = self._camera.Shutter.Rolling
            self._camera.triggerMode = self._camera.TriggerMode.Software
            self._camera.cycleMode = self._camera.CycleMode.Fixed
            self._camera.frameCount = self._stepsPerRound
            print(self._camera.frameCount)

            for buffer in buffers:
                self._camera._camera.AT_QueueBuffer(buffer)
            self._camera._camera.AT_Command(self._camera._camera.Feature.AcquisitionStart)

            for stepIdx, z in enumerate(steps):
                self._zDrive.pos = z
                # Return to main event loop (or whatever was the enclosing greenlet when this class was instantiated) until
                # the stage stops moving, aborting and cleaning up if resumed with switch(False)
                if not self.idleGt.switch():
                    print('Autofocus aborted.')
                    self._camera._camera.AT_Command(self._camera._camera.Feature.AcquisitionStop)
                    self._camera._camera.AT_Flush()
                    self._running = False
                    self._zDrive.posChanged.disconnect(self._zDrivePosChanged)
                    raise greenlet.GreenletExit()
                # Resuming after stage has moved
                actualZ = self._zDrive.pos
                if abs(actualZ - z) > self._zDrive._factor - sys.float_info.epsilon:
                    w = 'Current Z position ({0}) does not match requested Z position ({1}).  '
                    w+= 'The autofocus step for {1} is being skipped.  This can occur if the requested Z position '
                    w+= 'is out of range or if the scope\'s Z position controller has been moved during the '
                    w+= 'auto-focus operation.'
                    print(w.format(actualZ, z))
                    continue
                # Stage Z position is actually what we requested.  Command exposure.
                self._camera.commandSoftwareTrigger()
                print('exposed ', stepIdx)
                stepIdxsDone.append(stepIdx)

            # Retrieve, show, and process resulting exposures
            for bufferIdx, stepIdx in enumerate(stepIdxsDone):
                self._camera._camera.AT_WaitBuffer(1000)
                print('got buffer', bufferIdx)
                buffer = buffers[bufferIdx]
                if self._rw is not None:
                    self._rw.showImage(buffer)
                im = buffer.astype(numpy.float32) / 65535
                fmv = (self._focusMeasure(im)**2).sum()
                print('round={:02}, z={:<10}, focus_measure={}'.format(roundIdx, steps[stepIdx], fmv))
                fmvs.append((steps[stepIdx], fmv))

            self._camera._camera.AT_Command(self._camera._camera.Feature.AcquisitionStop)

            if len(fmvs) == 0:
                print('Failed to move to any of the Z step positions.')
                self._running = False
                self._zDrive.posChanged.disconnect(self._zDrivePosChanged)
                raise greenlet.GreenletExit()
            if len(fmvs) == 1:
                print('Successfully moved to only one of the Z step positions, making that position the best found.')
                self.bestZ = fmvs[0][0]
                self._running = False
                self._zDrive.posChanged.disconnect(self._zDrivePosChanged)
                raise greenlet.GreenletExit()

            bestZIdx = numpy.array([fmv[1] for fmv in fmvs], dtype=numpy.float64).argmax()

            if roundIdx + 1 < self._numberOfRounds:
                # Next round, search the range between the steps adjacent to the best step
                curZRange = ( steps[max(bestZIdx - 1, 0)],
                              steps[min(bestZIdx + 1, len(fmvs) - 1)] )
            else:
                # There is no next round.  Store result.
                self.bestZ = steps[bestZIdx]

        print('Autofocus completed ({}s).'.format(time.time() - t0))
        self._running = False
        self._zDrive.posChanged.disconnect(self._zDrivePosChanged)

    def _zDrivePosChanged(self, _):
        if self._running and not self._zDrive.moving:
            self.runGt.switch(True)

def linearSearchAutofocus(camera, zDrive, minZ, maxZ, stepsPerRound, numberOfRounds, focusMeasure=brennerFocusMeasure, rw=None):
    autofocuser = _Autofocuser(camera, zDrive, minZ, maxZ, stepsPerRound, numberOfRounds, rw)
    # greenlet.run(..) blocks until the greenlet is dead and is the correct call to use when blocking behavior is desired
    autofocuser.runGt.run()
    return autofocuser.bestZ