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

import numpy
from pathlib import Path
import skimage.measure
import skimage.io as skio
import scipy.ndimage.morphology as ndmo
import time

def makeMaskFromFluorescence(fluoImage, erosionDivisor=2, propagationDivisor=3):
    eroded = ndmo.binary_erosion(fluoImage > fluoImage.max()/erosionDivisor, iterations=5)
    propagated = ndmo.binary_propagation(eroded, mask= fluoImage > fluoImage.max()/propagationDivisor)
    dilated = ndmo.binary_dilation(propagated, iterations=5)
    filled = ndmo.binary_fill_holes(dilated)
    return filled

def makeExperiment00FluoMasks(rw, tryDivisors=None):
    imFPaths = sorted(list(Path('/Volumes/coalsack/experiment00').glob('**/*oxIs*/**/fluo_image.png')), key=lambda p:str(p), reverse=False)
    if tryDivisors is None:
        tryDivisors = ((3, 5),
                       (3, 4),
                       (2.5, 3),
                       (2, 3),
                       (2, 2.5),
                       (1.5, 1.8))
    for imFPath in imFPaths:
        maskFPath = imFPath.parent / 'fluo_worm_mask.png'
        runNumber = 1 + int(imFPath.parts[-2].split('_')[1])
        im = skio.imread(str(imFPath))
        rw.showImage(im)
        ok = False
        for erosionDivisor, propagationDivisor in tryDivisors:
            imm = makeMaskFromFluorescence(im, erosionDivisor, propagationDivisor)
            rw.showImage(imm)
            litCount = imm.sum()
            pixelCount = len(im.flat)
            litFrac = litCount / pixelCount
            print(str(imFPath), litFrac, runNumber, 0.002 + runNumber * 7.4347826086956524e-05)
            if litFrac > 0 and litFrac < 0.002 + runNumber * 7.4347826086956524e-05:
                # Throw away all but the biggest labeled region under the assumption that it is the worm
                immlabels = skimage.measure.label(imm)
                immregions = skimage.measure.regionprops(immlabels)
                immregions.sort(key=lambda region: region.area, reverse=True)
                r = immregions[0]
                immm = numpy.zeros(imm.shape).astype(numpy.bool)
                a, b = r.bbox[0], r.bbox[1]
                aw, bw = r.bbox[2] - r.bbox[0], r.bbox[3] - r.bbox[1]
                immm[a:a+aw, b:b+bw] = r.image
                rw.showImage(immm)
                print(str(maskFPath))
                skio.imsave(str(maskFPath), immm.astype(numpy.uint8)*255)
                break

from misc.manually_score_images import ManualImageScorer

class AutomaskedManualImageScorer(ManualImageScorer):
    def _getImage(self, imageFPath):
        image = skio.imread(str(imageFPath))
        mask = skio.imread(str(imageFPath.parent / 'fluo_worm_mask.png')).astype(numpy.bool)
        image[~mask] = 0
        labels = skimage.measure.label(mask)
        regions = skimage.measure.regionprops(labels)
        if len(regions) == 0:
            print('warning: mask is empty')
        else:
            if len(regions) > 1:
                print('warning: mask contains multiple regions')
            else:
                bb = regions[0].bbox
                return numpy.copy(image[bb[0]:bb[2]+1, bb[1]:bb[3]+1])
