# -*- coding: utf-8 -*-
# Author: Daniel Ryan <ryand5@tcd.ie>

import os.path
import pytest
import copy
import datetime

import numpy as np
import astropy.wcs as wcs
from astropy.io import fits
import astropy.units as u
from ndcube.utils.wcs import WCS
from ndcube.tests.helpers import assert_cubes_equal, assert_cubesequences_equal

from irispy.spectrograph import IRISSpectrogramCube, IRISSpectrogramCubeSequence, IRISSpectrograph, read_iris_spectrograph_level2_fits
import irispy.data.test
from irispy import iris_tools

testpath = irispy.data.test.rootdir

# Arrays of DN
SOURCE_DATA_DN = np.array([[[ 0.563,  1.132, -1.343], [-0.719,  1.441, 1.566]],
                           [[ 0.563,  1.132, -1.343], [-0.719,  1.441, 1.566]]])
SOURCE_UNCERTAINTY_DN = np.sqrt(SOURCE_DATA_DN)

# Arrays relating SOURCE_DATA_DN to photons in NUV and FUV
SOURCE_DATA_PHOTONS_NUV = np.array([[[ 10.134, 20.376, -24.174], [-12.942, 25.938, 28.188]],
                                    [[10.134, 20.376, -24.174], [-12.942, 25.938, 28.188]]])
SOURCE_DATA_PHOTONS_FUV = np.array([[[ 2.252, 4.528, -5.372], [-2.876, 5.764, 6.264]],
                                    [[2.252, 4.528, -5.372], [-2.876, 5.764, 6.264]]])
SOURCE_UNCERTAINTY_PHOTONS_NUV = np.sqrt(SOURCE_DATA_PHOTONS_NUV)
SOURCE_UNCERTAINTY_PHOTONS_FUV = np.sqrt(SOURCE_DATA_PHOTONS_FUV)

time_dim_len = SOURCE_DATA_DN.shape[0]
single_exposure_time = 2.
EXPOSURE_TIME = u.Quantity(np.zeros(time_dim_len)+single_exposure_time, unit=u.s)

# Define an sample wcs object
h0 = {
    'CTYPE1': 'WAVE    ', 'CUNIT1': 'Angstrom', 'CDELT1': 0.2, 'CRPIX1': 0, 'CRVAL1': 10,
    'NAXIS1': 3,
    'CTYPE2': 'HPLT-TAN', 'CUNIT2': 'deg', 'CDELT2': 0.5, 'CRPIX2': 2, 'CRVAL2': 0.5, 'NAXIS2': 2,
    'CTYPE3': 'HPLN-TAN', 'CUNIT3': 'deg', 'CDELT3': 0.4, 'CRPIX3': 2, 'CRVAL3': 1, 'NAXIS3': 2,
}
wcs0 = WCS(header=h0, naxis=3)

# Define sample meta
meta0 = {"detector type": "FUV", "OBSID": 1, "spectral window": "C II 1336"}

# Define sample extra coords
extra_coords0 = [("time", 0,
                  np.array([datetime.datetime(2017, 1, 1)+datetime.timedelta(seconds=i)
                             for i in range(time_dim_len)])),
                ("exposure time", 0, EXPOSURE_TIME)]
extra_coords1 = [("time", 0,
                  np.array([datetime.datetime(2017, 1, 1)+datetime.timedelta(seconds=i)
                             for i in range(time_dim_len, time_dim_len*2)])),
                ("exposure time", 0, EXPOSURE_TIME)]

# Define IRISSpectrogramCubes in various units.
spectrogram_DN0 = IRISSpectrogramCube(
    SOURCE_DATA_DN, wcs0, SOURCE_UNCERTAINTY_DN, iris_tools.DN_UNIT["FUV"],
    meta0, extra_coords0)
spectrogram_photon0 = IRISSpectrogramCube(
    SOURCE_DATA_PHOTONS_FUV, wcs0, SOURCE_UNCERTAINTY_PHOTONS_FUV, u.photon,
    meta0, extra_coords0)
spectrogram_DN_per_s0 = IRISSpectrogramCube(
    SOURCE_DATA_DN/single_exposure_time, wcs0, SOURCE_UNCERTAINTY_DN/single_exposure_time,
    iris_tools.DN_UNIT["FUV"]/u.s, meta0, extra_coords0)
spectrogram_photon_per_s0 = IRISSpectrogramCube(
    SOURCE_DATA_PHOTONS_FUV/single_exposure_time, wcs0,
    SOURCE_UNCERTAINTY_PHOTONS_FUV/single_exposure_time,
    u.photon/u.s, meta0, extra_coords0)
spectrogram_DN1 = IRISSpectrogramCube(
    SOURCE_DATA_DN, wcs0, SOURCE_UNCERTAINTY_DN, iris_tools.DN_UNIT["FUV"],
    meta0, extra_coords1)
spectrogram_photon1 = IRISSpectrogramCube(
    SOURCE_DATA_PHOTONS_FUV, wcs0, SOURCE_UNCERTAINTY_PHOTONS_FUV, u.photon,
    meta0, extra_coords1)
spectrogram_DN_per_s1 = IRISSpectrogramCube(
    SOURCE_DATA_DN/single_exposure_time, wcs0, SOURCE_UNCERTAINTY_DN/single_exposure_time,
    iris_tools.DN_UNIT["FUV"]/u.s, meta0, extra_coords1)
spectrogram_photon_per_s1 = IRISSpectrogramCube(
    SOURCE_DATA_PHOTONS_FUV/single_exposure_time, wcs0,
    SOURCE_UNCERTAINTY_PHOTONS_FUV / single_exposure_time,
    u.photon/u.s, meta0, extra_coords1)
spectrogram_photon_per_s_per_s0 = IRISSpectrogramCube(
    SOURCE_DATA_PHOTONS_FUV/single_exposure_time/single_exposure_time, wcs0,
    SOURCE_UNCERTAINTY_PHOTONS_FUV/single_exposure_time/single_exposure_time,
    u.photon/u.s/u.s, meta0, extra_coords0)
spectrogram_photon_s0 = IRISSpectrogramCube(
    SOURCE_DATA_PHOTONS_FUV*single_exposure_time, wcs0,
    SOURCE_UNCERTAINTY_PHOTONS_FUV*single_exposure_time,
    u.photon*u.s, meta0, extra_coords0)
spectrogram_photon_per_s_per_s1 = IRISSpectrogramCube(
    SOURCE_DATA_PHOTONS_FUV/single_exposure_time/single_exposure_time, wcs0,
    SOURCE_UNCERTAINTY_PHOTONS_FUV/single_exposure_time/single_exposure_time,
    u.photon/u.s/u.s, meta0, extra_coords1)
spectrogram_photon_s1 = IRISSpectrogramCube(
    SOURCE_DATA_PHOTONS_FUV*single_exposure_time, wcs0,
    SOURCE_UNCERTAINTY_PHOTONS_FUV*single_exposure_time,
    u.photon*u.s, meta0, extra_coords1)

# Define meta dict for an IRISSpectrogramCubeSequence
meta_seq = {"detector type": "FUV", "spectral window": "C II 1336",
            "brightest wavelength": 100, "min wavelength": 90, "max wavelength": 110}
# Define IRISSpectrogramCubeSequences
sequence_DN = IRISSpectrogramCubeSequence(
    [spectrogram_DN0, spectrogram_DN1], meta_seq)
sequence_photon = IRISSpectrogramCubeSequence(
    [spectrogram_photon0, spectrogram_photon1], meta_seq)
sequence_DN_per_s = IRISSpectrogramCubeSequence(
    [spectrogram_DN_per_s0, spectrogram_DN_per_s1], meta_seq)
sequence_photon_per_s = IRISSpectrogramCubeSequence(
    [spectrogram_photon_per_s0, spectrogram_photon_per_s1], meta_seq)
sequence_photon_per_s_per_s = IRISSpectrogramCubeSequence(
    [spectrogram_photon_per_s_per_s0, spectrogram_photon_per_s1], meta_seq)
sequence_photon_s = IRISSpectrogramCubeSequence(
    [spectrogram_photon_s0, spectrogram_photon_s1], meta_seq)

@pytest.fixture
def iris_l2_test_raster():
    return read_iris_spectrograph_level2_fits(
        os.path.join(testpath, 'iris_l2_20170222_153635_3690215148_raster_t000_r00000.fits'))


def test_fits_data_comparison(iris_l2_test_raster):
    """Make sure the data is the same in pyfits and irispy"""
    hdulist = fits.open(os.path.join(
        testpath, 'iris_l2_20170222_153635_3690215148_raster_t000_r00000.fits'))
    spectral_window1 = hdulist[0].header["TDESC1"]
    spectral_window2 = hdulist[0].header["TDESC2"]
    spectral_window3 = hdulist[0].header["TDESC3"]

    data1 = copy.deepcopy(hdulist[1].data)
    data2 = copy.deepcopy(hdulist[2].data)
    data3 = copy.deepcopy(hdulist[3].data)

    np.testing.assert_array_almost_equal(
        iris_l2_test_raster.data[spectral_window1].data[0].data, data1)
    np.testing.assert_array_almost_equal(
        iris_l2_test_raster.data[spectral_window2].data[0].data, data2)
    np.testing.assert_array_almost_equal(
        iris_l2_test_raster.data[spectral_window3].data[0].data, data3)


@pytest.mark.parametrize("input_cube, new_unit, expected_cube", [
    (spectrogram_DN0, "DN", spectrogram_DN0),
    (spectrogram_DN0, "photons", spectrogram_photon0),
    (spectrogram_DN_per_s0, "DN", spectrogram_DN_per_s0),
    (spectrogram_DN_per_s0, "photons", spectrogram_photon_per_s0),
    (spectrogram_photon0, "DN", spectrogram_DN0),
    (spectrogram_photon0, "photons", spectrogram_photon0),
    (spectrogram_photon_per_s0, "DN", spectrogram_DN_per_s0),
    (spectrogram_photon_per_s0, "photons", spectrogram_photon_per_s0)
])
def test_IRISSpectrogramCube_convert_to(input_cube, new_unit, expected_cube):
    output_cube = input_cube.convert_to(new_unit)
    assert_cubes_equal(output_cube, expected_cube)


@pytest.mark.parametrize("input_cube, undo, force, expected_cube", [
    (spectrogram_DN0, False, False, spectrogram_DN_per_s0),
    (spectrogram_DN_per_s0, True, False, spectrogram_DN0),
    (spectrogram_photon0, False, False, spectrogram_photon_per_s0),
    (spectrogram_photon_per_s0, True, False, spectrogram_photon0),
    (spectrogram_photon_per_s0, False, True, spectrogram_photon_per_s_per_s0),
    (spectrogram_photon0, True, True, spectrogram_photon_s0)
])
def test_IRISSpectrogramCube_apply_exposure_time_correction(input_cube, undo,
                                                            force, expected_cube):
    output_cube = input_cube.apply_exposure_time_correction(undo=undo, force=force)
    assert_cubes_equal(output_cube, expected_cube)


@pytest.mark.parametrize("input_sequence, new_unit, expected_sequence", [
    (sequence_DN, "DN", sequence_DN),
    (sequence_DN, "photons", sequence_photon),
    (sequence_photon, "DN", sequence_DN),
    (sequence_photon, "photons", sequence_photon),
    (sequence_DN_per_s, "DN", sequence_DN_per_s),
    (sequence_DN_per_s, "photons", sequence_photon_per_s),
    (sequence_photon_per_s, "DN", sequence_DN_per_s),
    (sequence_photon_per_s, "photons", sequence_photon_per_s)
])
def test_IRISSpectrogramCubeSequence_convert_to(input_sequence, new_unit,
                                                expected_sequence):
    output_sequence = input_sequence.convert_to(new_unit, copy=True)
    assert_cubesequences_equal(output_sequence, expected_sequence)


@pytest.mark.parametrize("input_sequence, undo, force, expected_sequence", [
    (sequence_DN, False, False, sequence_DN_per_s),
    (sequence_DN_per_s, True, False, sequence_DN),
    (sequence_photon, False, False, sequence_photon_per_s),
    (sequence_photon, True, True, sequence_photon_s),
    (sequence_photon_per_s, False, True, sequence_photon_per_s_per_s),
    (sequence_photon_per_s, True, True, sequence_photon)
])
def test_IRISSpectrogramCubeSequence_apply_exposure_time_correction(
        input_sequence, undo, force, expected_sequence):
    output_sequence = input_sequence.apply_exposure_time_correction(undo, copy=True,
                                                                    force=force)
    assert_cubesequences_equal(output_sequence, expected_sequence)
