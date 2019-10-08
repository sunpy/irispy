# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import pytest

import numpy as np
import numpy.testing as np_test
import astropy.units as u
from astropy.utils.data import download_file
import scipy.io
from sunpy.time import parse_time

import irispy.iris_tools as iris_tools
from irispy.iris_tools import fit_iris_xput
from irispy.iris_tools import get_iris_response

DETECTOR_TYPE_KEY = "detector type"

# Arrays of DN
SOURCE_DATA_DN = np.array([[ 0.563,  1.132, -1.343], [-0.719,  1.441, 1.566]])
SOURCE_DATA_DN_1 = np.array([[1, 2, 3], [4, 5, 6]])

# Arrays relating SOURCE_DATA_DN to photons in NUV and FUV
SOURCE_DATA_PHOTONS_NUV = np.array([[ 10.134, 20.376, -24.174], [-12.942, 25.938, 28.188]])
SOURCE_DATA_PHOTONS_FUV = np.array([[ 2.252, 4.528, -5.372], [-2.876, 5.764, 6.264]])

# Arrays relating SOURCE_DATA_DN_1 and photons in SJI
SOURCE_DATA_PHOTONS_SJI_1 = np.array([[18, 36, 54], [72, 90, 108]])

single_exposure_time = 2.
EXPOSURE_TIME = np.zeros(3)+single_exposure_time

# Arrays for the calcuate_dust_mask method.
data_dust = np.array([[[-1, 2, -3, 4], [2, -200, 5, 3], [0, 1, 2, -300]],
                      [[2, -200, 5, 1], [10, -5, 2, 2], [10, -3, 3, 0]]])
dust_mask_expected = np.array(
    [[[True, True, True, True], [True, True, True, True], [True, True, False, False]],
     [[True, True, True, False], [True, True, True, True], [True, True, True, True]]])

# Arrays for the fit_iris_xput method
response_url = 'https://sohowww.nascom.nasa.gov/solarsoft/iris/response/iris_sra_c_20161022.geny'
r = download_file(response_url)
raw_response_data = scipy.io.readsav(r)
iris_response = dict([(name, raw_response_data["p0"][name][0]) for name in raw_response_data["p0"].dtype.names])
time_obs = parse_time('2013-09-03', format='utime')
time_cal_coeffs0 = iris_response.get('C_F_TIME')
time_cal_coeffs1 = iris_response.get('C_N_TIME')
cal_coeffs0 = iris_response.get('COEFFS_FUV')[0,:,:]
cal_coeffs1 = iris_response.get('COEFFS_FUV')[1,:,:]
cal_coeffs2 = iris_response.get('COEFFS_FUV')[2,:,:]
cal_coeffs3 = iris_response.get('COEFFS_NUV')[0,:,:]
cal_coeffs4 = iris_response.get('COEFFS_NUV')[1,:,:]
cal_coeffs5 = iris_response.get('COEFFS_NUV')[2,:,:]
iris_fit_expected0 = np.array([0.79865301])
iris_fit_expected1 = np.array([2.2495413])
iris_fit_expected2 = np.array([2.2495413])
iris_fit_expected3 = np.array([0.23529011])
iris_fit_expected4 = np.array([0.25203046])
iris_fit_expected5 = np.array([0.25265095])

@pytest.mark.parametrize("test_input, expected_output", [
    ({DETECTOR_TYPE_KEY: "FUV1"}, "FUV"),
    ({DETECTOR_TYPE_KEY: "NUV"}, "NUV"),
    ({DETECTOR_TYPE_KEY: "SJI"}, "SJI")
])

def test_get_detector_type(test_input, expected_output):
    assert iris_tools.get_detector_type(test_input) == expected_output

@pytest.mark.parametrize("data_arrays, old_unit, new_unit, expected_data_arrays, expected_unit", [
    ([SOURCE_DATA_DN, SOURCE_DATA_DN], iris_tools.DN_UNIT["FUV"], u.photon,
     [SOURCE_DATA_PHOTONS_FUV, SOURCE_DATA_PHOTONS_FUV], u.photon),
    ([SOURCE_DATA_DN, SOURCE_DATA_DN], iris_tools.DN_UNIT["NUV"], u.photon,
     [SOURCE_DATA_PHOTONS_NUV, SOURCE_DATA_PHOTONS_NUV], u.photon),
    ([SOURCE_DATA_DN_1, SOURCE_DATA_DN_1], iris_tools.DN_UNIT["SJI"], u.photon,
     [SOURCE_DATA_PHOTONS_SJI_1, SOURCE_DATA_PHOTONS_SJI_1], u.photon),
    ([SOURCE_DATA_PHOTONS_FUV, SOURCE_DATA_PHOTONS_FUV], u.photon, iris_tools.DN_UNIT["FUV"],
    [SOURCE_DATA_DN, SOURCE_DATA_DN], iris_tools.DN_UNIT["FUV"]),
    ([SOURCE_DATA_PHOTONS_NUV, SOURCE_DATA_PHOTONS_NUV], u.photon, iris_tools.DN_UNIT["NUV"],
    [SOURCE_DATA_DN, SOURCE_DATA_DN], iris_tools.DN_UNIT["NUV"]),
    ([SOURCE_DATA_PHOTONS_SJI_1, SOURCE_DATA_PHOTONS_SJI_1], u.photon, iris_tools.DN_UNIT["SJI"],
    [SOURCE_DATA_DN_1, SOURCE_DATA_DN_1], iris_tools.DN_UNIT["SJI"])
])

def test_convert_between_DN_and_photons(data_arrays, old_unit, new_unit,
                                        expected_data_arrays, expected_unit):
    output_arrays, output_unit = iris_tools.convert_between_DN_and_photons(data_arrays,
                                                                           old_unit, new_unit)
    for i, output_array in enumerate(output_arrays):
        np_test.assert_allclose(output_array, expected_data_arrays[i])
    assert output_unit == expected_unit

@pytest.mark.parametrize(
    "input_arrays, old_unit, exposure_time, force, expected_arrays, expected_unit",[
        ([SOURCE_DATA_DN, SOURCE_DATA_DN], u.photon, EXPOSURE_TIME, False,
         [SOURCE_DATA_DN/single_exposure_time, SOURCE_DATA_DN/single_exposure_time],
         u.photon/u.s),
        ([SOURCE_DATA_DN, SOURCE_DATA_DN], iris_tools.DN_UNIT["NUV"], EXPOSURE_TIME, False,
         [SOURCE_DATA_DN/single_exposure_time, SOURCE_DATA_DN/single_exposure_time],
         iris_tools.DN_UNIT["NUV"]/u.s),
        ([SOURCE_DATA_DN, SOURCE_DATA_DN], u.photon/u.s, EXPOSURE_TIME, True,
         [SOURCE_DATA_DN/single_exposure_time, SOURCE_DATA_DN/single_exposure_time],
         u.photon/u.s/u.s),
        ([SOURCE_DATA_DN, SOURCE_DATA_DN], iris_tools.DN_UNIT["NUV"]/u.s, EXPOSURE_TIME, True,
         [SOURCE_DATA_DN/single_exposure_time, SOURCE_DATA_DN/single_exposure_time],
         iris_tools.DN_UNIT["NUV"]/u.s/u.s)
    ])

def test_calculate_exposure_time_correction(input_arrays, old_unit, exposure_time, force,
                                            expected_arrays, expected_unit):
    output_arrays, output_unit = iris_tools.calculate_exposure_time_correction(
        input_arrays, old_unit, exposure_time, force=force)
    for i, output_array in enumerate(output_arrays):
        np_test.assert_allclose(output_array, expected_arrays[i])
    assert output_unit == expected_unit

@pytest.mark.parametrize("input_arrays, old_unit, exposure_time, force", [
    ([SOURCE_DATA_DN, SOURCE_DATA_DN], u.photon/u.s, EXPOSURE_TIME, False),
    ([SOURCE_DATA_DN, SOURCE_DATA_DN], iris_tools.DN_UNIT["NUV"]/u.s, EXPOSURE_TIME, False)
])

def test_calculate_exposure_time_correction_error(input_arrays, old_unit, exposure_time, force):
    assert pytest.raises(ValueError, iris_tools.calculate_exposure_time_correction,
                         input_arrays, old_unit, exposure_time, force)

@pytest.mark.parametrize(
    "input_arrays, old_unit, exposure_time, force, expected_arrays, expected_unit", [
        ([SOURCE_DATA_DN, SOURCE_DATA_DN], u.photon/u.s, EXPOSURE_TIME, False,
         [SOURCE_DATA_DN * single_exposure_time, SOURCE_DATA_DN * single_exposure_time], u.photon),
        ([SOURCE_DATA_DN, SOURCE_DATA_DN], iris_tools.DN_UNIT["NUV"]/u.s, EXPOSURE_TIME, False,
         [SOURCE_DATA_DN * single_exposure_time, SOURCE_DATA_DN * single_exposure_time],
         iris_tools.DN_UNIT["NUV"]),
        ([SOURCE_DATA_DN, SOURCE_DATA_DN], u.photon, EXPOSURE_TIME, True,
         [SOURCE_DATA_DN * single_exposure_time, SOURCE_DATA_DN * single_exposure_time],
         u.photon*u.s),
        ([SOURCE_DATA_DN, SOURCE_DATA_DN], iris_tools.DN_UNIT["FUV"], EXPOSURE_TIME, True,
         [SOURCE_DATA_DN * single_exposure_time, SOURCE_DATA_DN * single_exposure_time],
         iris_tools.DN_UNIT["FUV"]*u.s)
])

def test_uncalculate_exposure_time_correction(input_arrays, old_unit, exposure_time, force,
                                              expected_arrays, expected_unit):
        output_arrays, output_unit = iris_tools.uncalculate_exposure_time_correction(
            input_arrays, old_unit, exposure_time, force=force)
        for i, output_array in enumerate(output_arrays):
            np_test.assert_allclose(output_array, expected_arrays[i])
        assert output_unit == expected_unit

@pytest.mark.parametrize("input_arrays, old_unit, exposure_time, force", [
    ([SOURCE_DATA_DN, SOURCE_DATA_DN], u.photon, EXPOSURE_TIME, False),
    ([SOURCE_DATA_DN, SOURCE_DATA_DN], iris_tools.DN_UNIT["NUV"], EXPOSURE_TIME, False)
])

def test_uncalculate_exposure_time_correction_error(input_arrays, old_unit, exposure_time, force):
    with pytest.raises(ValueError):
        assert iris_tools.uncalculate_exposure_time_correction(input_arrays, old_unit,
                                                               exposure_time, force=force)

def test_get_iris_response_not_equal_to_one():
    assert pytest.raises(KeyError, iris_tools.get_iris_response, time_obs,
                         pre_launch=False, response_version=13)


def test_get_iris_response_response_file():
    assert pytest.raises(KeyError, iris_tools.get_iris_response, time_obs, response_file="hello.py")


# Tests for get_iris_response function
## Version 1
sav_file_path1 = 'irispy/data/idl_iris_get_response_20130903_new_version001.sav'
test_iris_response1 = scipy.io.readsav(sav_file_path1, python_dict=True, verbose=True)
iris_response_load1 = test_iris_response1['iris_response'][0]

lamb_load1 = iris_response_load1.lambda_vars
area_sg_load1 = iris_response_load1.area_sg
name_sg_load1 = iris_response_load1.name_sg
index_el_sg_load1 = iris_response_load1.index_el_sg
area_sji_load1 = iris_response_load1.area_sji
name_sji_load1 = iris_response_load1.name_sji
index_el_sji_load1 = iris_response_load1.index_el_sji
geom_area_load1 = iris_response_load1.geom_area
elements_load1 = iris_response_load1.elements
comment_load1 = iris_response_load1.comment
version_load1 = iris_response_load1.version
date_load1 = iris_response_load1.date

## Version 2
sav_file_path2 = 'irispy/data/idl_iris_get_response_20130903_new_version002.sav'
test_iris_response2 = scipy.io.readsav(sav_file_path2, python_dict=True, verbose=True)
iris_response_load2 = test_iris_response2['iris_response'][0]

lamb_load2 = iris_response_load2.lambda_vars
area_sg_load2 = iris_response_load2.area_sg
name_sg_load2 = iris_response_load2.name_sg
index_el_sg_load2 = iris_response_load2.index_el_sg
area_sji_load2 = iris_response_load2.area_sji
name_sji_load2 = iris_response_load2.name_sji
index_el_sji_load2 = iris_response_load2.index_el_sji
elements_load2 = iris_response_load2.elements
comment_load2 = iris_response_load2.comment
version_load2 = iris_response_load2.version
date_load2 = iris_response_load2.date

## Version 3
sav_file_path3 = 'irispy/data/idl_iris_get_response_20130903_new_version003.sav'
test_iris_response3 = scipy.io.readsav(sav_file_path3, python_dict=True, verbose=True)
iris_response_load3 = test_iris_response3['iris_response'][0]

date_obs_load3 = iris_response_load3.date_obs
lamb_load3 = iris_response_load3.lambda_vars
area_sg_load3 = iris_response_load3.area_sg
name_sg_load3 = iris_response_load3.name_sg
dn2phot_sg_load3 = iris_response_load3.dn2phot_sg
area_sji_load3 = iris_response_load3.area_sji
name_sji_load3 = iris_response_load3.name_sji
dn2phot_sji_load3 = iris_response_load3.dn2phot_sji
comment_load3 = iris_response_load3.comment
version_load3 = iris_response_load3.version
version_date_load3 = iris_response_load3.version_date

## Version 4
sav_file_path4 = 'irispy/data/idl_iris_get_response_20130903_new_version004.sav'
test_iris_response4 = scipy.io.readsav(sav_file_path4, python_dict=True, verbose=True)
iris_response_load4 = test_iris_response4['iris_response'][0]

date_obs_load4 = iris_response_load4.date_obs
lamb_load4 = iris_response_load4.lambda_vars
area_sg_load4 = iris_response_load4.area_sg
name_sg_load4 = iris_response_load4.name_sg
dn2phot_sg_load4 = iris_response_load4.dn2phot_sg
area_sji_load4 = iris_response_load4.area_sji
name_sji_load4 = iris_response_load4.name_sji
dn2phot_sji_load4 = iris_response_load4.dn2phot_sji
comment_load4 = iris_response_load4.comment
version_load4 = iris_response_load4.version
version_date_load4 = iris_response_load4.version_date

# For testing of version 1
iris_response1 = get_iris_response(time_obs=parse_time('2013-09-03', format='utime'),
                                   response_version=1)
@pytest.mark.parametrize("input_quantity, expected_quantity",
[
 (iris_response1["AREA_SG"].value, area_sg_load1),
 (iris_response1["AREA_SJI"].value, area_sji_load1)
 ])

def test_get_iris_response_version1(input_quantity, expected_quantity):
    np_test.assert_almost_equal(input_quantity, expected_quantity, decimal=6)

# For testing of version 2
iris_response2 = get_iris_response(time_obs=parse_time('2013-09-03', format='utime'),
                                   response_version=2)
@pytest.mark.parametrize("input_quantity, expected_quantity",
[
 (iris_response2["AREA_SG"].value, area_sg_load2),
 (iris_response2["AREA_SJI"].value, area_sji_load2)
 ])

def test_get_iris_response_version2(input_quantity, expected_quantity):
    np_test.assert_almost_equal(input_quantity, expected_quantity, decimal=6)

# For testing of version 3
iris_response3 = get_iris_response(time_obs=parse_time('2013-09-03', format='utime'),
                                   response_version=3)
@pytest.mark.parametrize("input_quantity, expected_quantity",
[
 (iris_response3["AREA_SG"].value, area_sg_load3),
 (iris_response3["AREA_SJI"].value, area_sji_load3)
 ])

def test_get_iris_response_version3(input_quantity, expected_quantity):
    np_test.assert_almost_equal(input_quantity, expected_quantity, decimal=6)

# For testing of version 4
iris_response4 = get_iris_response(time_obs=parse_time('2013-09-03', format='utime'),
                                   response_version=4)
@pytest.mark.parametrize("input_quantity, expected_quantity",
[
 (iris_response4["AREA_SG"].value, area_sg_load4),
 (iris_response4["AREA_SJI"].value, area_sji_load4)
 ])

def test_get_iris_response_version4(input_quantity, expected_quantity):
    np_test.assert_almost_equal(input_quantity, expected_quantity, decimal=3)

def test_gaussian1d_on_linear_bg():
    pass

def test_calculate_orbital_wavelength_variation():
    pass

@pytest.mark.parametrize("input_array, expected_array", [
    (data_dust, dust_mask_expected)])

def test_calculate_dust_mask(input_array, expected_array):
    np_test.assert_array_equal(iris_tools.calculate_dust_mask(input_array), expected_array)

@pytest.mark.parametrize("input_arrays, expected_array", [
    ([time_obs.value, time_cal_coeffs0, cal_coeffs0], iris_fit_expected0),
    ([time_obs.value, time_cal_coeffs0, cal_coeffs1], iris_fit_expected1),
    ([time_obs.value, time_cal_coeffs0, cal_coeffs2], iris_fit_expected2),
    ([time_obs.value, time_cal_coeffs1, cal_coeffs3], iris_fit_expected3),
    ([time_obs.value, time_cal_coeffs1, cal_coeffs4], iris_fit_expected4),
    ([time_obs.value, time_cal_coeffs1, cal_coeffs5], iris_fit_expected5)])

def test_fit_iris_xput(input_arrays, expected_array):
    np_test.assert_almost_equal(fit_iris_xput(input_arrays[0], input_arrays[1], input_arrays[2]), expected_array, decimal=6)
