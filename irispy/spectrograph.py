# -*- coding: utf-8 -*-
# Author: Daniel Ryan <ryand5@tcd.ie>

import copy

import numpy as np
import astropy.units as u
from astropy.io import fits
from astropy.table import Table
from astropy.time import Time, TimeDelta
from ndcube import NDCube, NDCubeSequence
from ndcube.utils.wcs import WCS
from ndcube.utils.cube import convert_extra_coords_dict_to_input_format

from irispy import iris_tools

__all__ = ['IRISSpectrograph']

class IRISSpectrograph(object):
    """
    An object to hold data from multiple IRIS raster scans.

    The Interface Region Imaging Spectrograph (IRIS) small explorer spacecraft
    provides simultaneous spectra and images of the photosphere, chromosphere,
    transition region, and corona with 0.33 to 0.4 arcsec spatial resolution,
    2-second temporal resolution and 1 km/s velocity resolution over a
    field-of- view of up to 175 arcsec by 175 arcsec.  IRIS consists of a 19-cm
    UV telescope that feeds a slit-based dual-bandpass imaging spectrograph.

    IRIS was launched into a Sun-synchronous orbit on 27 June 2013.

    Parameters
    ----------
    data: `dict` of `irispy.spectrograph.IRISSpectrogramCubeSequence`.
        Spectral data from same OBS in IRISSpectrogramCubeSequence objects, one for each
        spectral window. Dict keys give names of spectral windows.

    meta: `dict` (Optional)
        Metadata associated with overall OBS rather than specific spectral window.

    References
    ----------
    * `IRIS Mission Page <http://iris.lmsal.com>`_
    * `IRIS Analysis Guide <https://iris.lmsal.com/itn26/itn26.pdf>`_
    * `IRIS Instrument Paper <https://www.lmsal.com/iris_science/doc?cmd=dcur&proj_num=IS0196&file_type=pdf>`_
    * `IRIS FITS Header keywords <https://www.lmsal.com/iris_science/doc?cmd=dcur&proj_num=IS0077&file_type=pdf>`_
    """

    def __init__(self, data, meta=None):
        self.data = data
        self.meta = meta

    def __repr__(self):
        spectral_window = self.spectral_windows["spectral window"][0]
        spectral_windows_info = "".join(
            ["\n{0:>15} : {1:20} pix".format(name,
                str([int(dim.value) for dim in self.data[name].dimensions]))
                for name in self.spectral_windows["spectral window"]])
        roll = self.meta.get("SAT_ROT", None)
        obs_start = self.meta["STARTOBS"]
        obs_end = self.meta["ENDOBS"]
        time_start = self.data[spectral_window][0].extra_coords["time"]["value"].min()
        time_end = self.data[spectral_window][-1].extra_coords["time"]["value"].max()
        result = []
        # If starting and ending times in same day, print date only once
        for start, end in zip([obs_start, time_start], [obs_end, time_end]):
            if start.strftime("%j") == end.strftime("%j"):
                result.append("{0} {1} -- {2}".format(
                    start.strftime("%Y-%m-%d"), start.strftime("%H:%M:%S.%f"),
                    end.strftime("%H:%M:%S.%f")))
            else:
                result.append("{0} -- {1}".format(start, end))
        obs_period, instance_period = result
        return ("<iris.IRISSpectrograph instance\nOBS ID: {obsid}\n"
           "OBS Description: {obsdesc}\n"
           "OBS Period: {obs_period}\n"
           "Instance period: {inst_period}\n"
           "Roll: {roll}\n"
           "OBS Number unique raster positions: {nraster}\n"
           "Spectral windows: dimensions [repeats axis, raster axis, slit axis, spectral axis]:"
           "{spec}>").format(obsid=self.meta["OBSID"], obsdesc=self.meta["OBS_DESC"],
                             obs_period=obs_period, roll=roll, inst_period=instance_period,
                             nraster=self.meta["NRASTERP"], spec=spectral_windows_info)

    @property
    def spectral_windows(self):
        """Returns a table of info on the spectral windows."""
        colnames = ("spectral window", "detector type", "brightest wavelength", "min wavelength",
                    "max wavelength")
        spectral_window_list = []
        for key in list(self.data.keys()):
            if type(self.data[key]) == IRISSpectrogramCubeSequence:
                spectral_window_list.append([self.data[key].meta[colname] for colname in colnames])
        return Table(rows=spectral_window_list, names=colnames)


class IRISSpectrogramCubeSequence(NDCubeSequence):
    """Class for holding, slicing and plotting IRIS spectrogram data.

    This class contains all the functionality of its super class with
    some additional functionalities.

    Parameters
    ----------
    data_list: `list`
        List of `IRISSpectrogramCube` objects from the same spectral window and OBS ID.
        Must also contain the 'detector type' in its meta attribute.

    meta: `dict` or header object
        Metadata associated with the sequence.

    common_axis: `int`
        The axis of the NDCubes corresponding to time.

    """
    def __init__(self, data_list, meta=None, common_axis=0):
        detector_type_key = "detector type"
        # Check that meta contains required keys.
        required_meta_keys = [detector_type_key, "spectral window",
                              "brightest wavelength", "min wavelength", "max wavelength"]
        if not all([key in list(meta) for key in required_meta_keys]):
            raise ValueError("Meta must contain following keys: {0}".format(required_meta_keys))
        # Check that all spectrograms are from same specral window and OBS ID.
        if len(np.unique([cube.meta["OBSID"] for cube in data_list])) != 1:
            raise ValueError("Constituent IRISSpectrogramCube objects must have same "
                             "value of 'OBSID' in its meta.")
        if len(np.unique([cube.meta["spectral window"] for cube in data_list])) != 1:
            raise ValueError("Constituent IRISSpectrogramCube objects must have same "
                             "value of 'spectral window' in its meta.")
        # Initialize Sequence.
        super(IRISSpectrogramCubeSequence, self).__init__(
            data_list, meta=meta, common_axis=common_axis)

    def __repr__(self):
        roll = self[0].meta.get("SAT_ROT", None)
        return """IRISSpectrogramCubeSequence
---------------------
{obs_repr}

Sequence period: {inst_start} -- {inst_end}
Sequence Shape: {seq_shape}
Axis Types: {axis_types}
Roll: {roll}

""".format(obs_repr=_produce_obs_repr_string(self.data[0].meta),
           inst_start=self[0].extra_coords["time"]["value"][0],
           inst_end=self[-1].extra_coords["time"]["value"][-1],
           seq_shape=self.dimensions, axis_types=self.world_axis_physical_types,
           roll=roll)

    def convert_to(self, new_unit_type, copy=False):
        """
        Converts data, uncertainty and unit of each spectrogram in sequence to new unit.

        Parameters
        ----------
        new_unit_type: `str`
           Unit type to convert data to.  Three values are accepted:
           "DN": Relevant IRIS data number based on detector type.
           "photons": photon counts
           "radiance": Perorms radiometric calibration conversion.

        copy: `bool`
            If True a new instance with the converted data values is return.
            If False, the current instance is overwritten.
            Default=False

        """
        converted_data_list = []
        for cube in self.data:
            converted_data_list.append(cube.convert_to(new_unit_type))
        if copy is True:
            return IRISSpectrogramCubeSequence(
                converted_data_list, meta=self.meta, common_axis=self._common_axis)
        else:
            self.data = converted_data_list

    def apply_exposure_time_correction(self, undo=False, copy=False, force=False):
        """
        Applies or undoes exposure time correction to data and uncertainty and adjusts unit.

        Correction is only applied (undone) if the object's unit doesn't (does)
        already include inverse time.  This can be overridden so that correction
        is applied (undone) regardless of unit by setting force=True.

        Parameters
        ----------
        undo: `bool`
            If False, exposure time correction is applied.
            If True, exposure time correction is removed.
            Default=False

        copy: `bool`
            If True a new instance with the converted data values is returned.
            If False, the current instance is overwritten.
            Default=False

        force: `bool`
            If not True, applies (undoes) exposure time correction only if unit
            doesn't (does) already include inverse time.
            If True, correction is applied (undone) regardless of unit.  Unit is still
            adjusted accordingly.

        Returns
        -------
        result: `None` or `IRISSpectrogramCubeSequence`
            If copy=False, the original IRISSpectrogramCubeSequence is modified with the
            exposure time correction applied (undone).
            If copy=True, a new IRISSpectrogramCubeSequence is returned with the correction
            applied (undone).

        """
        converted_data_list = []
        for cube in self.data:
            converted_data_list.append(cube.apply_exposure_time_correction(undo=undo,
                                                                           force=force))
        if copy is True:
            return IRISSpectrogramCubeSequence(
                converted_data_list, meta=self.meta, common_axis=self._common_axis)
        else:
            self.data = converted_data_list

class IRISSpectrogramCube(NDCube):
    """
    Class representing IRISSpectrogramCube data described by a single WCS.

    Parameters
    ----------
    data: `numpy.ndarray`
        The array holding the actual data in this object.

    wcs: `ndcube.wcs.wcs.WCS`
        The WCS object containing the axes' information

    unit : `astropy.unit.Unit` or `str`
        Unit for the dataset. Strings that can be converted to a Unit are allowed.

    meta : dict-like object
        Additional meta information about the dataset. Must contain at least the
        following keys:
            detector type: str, (FUV1, FUV2 or NUV)
            OBSID: int
            spectral window: str

    uncertainty : any type, optional
        Uncertainty in the dataset. Should have an attribute uncertainty_type
        that defines what kind of uncertainty is stored, for example "std"
        for standard deviation or "var" for variance. A metaclass defining
        such an interface is NDUncertainty - but isn’t mandatory. If the uncertainty
        has no such attribute the uncertainty is stored as UnknownUncertainty.
        Defaults to None.

    mask : any type, optional
        Mask for the dataset. Masks should follow the numpy convention
        that valid data points are marked by False and invalid ones with True.
        Defaults to None.

    extra_coords : iterable of `tuple`s, each with three entries
        (`str`, `int`, `astropy.units.quantity` or array-like)
        Gives the name, axis of data, and values of coordinates of a data axis not
        included in the WCS object.

    copy : `bool`, optional
        Indicates whether to save the arguments as copy. True copies every attribute
        before saving it while False tries to save every parameter as reference.
        Note however that it is not always possible to save the input as reference.
        Default is False.
    """

    def __init__(self, data, wcs, uncertainty, unit, meta, extra_coords,
                 mask=None, copy=False, missing_axes=None):
        # Check required meta data is provided.
        required_meta_keys = ["detector type"]
        if not all([key in list(meta) for key in required_meta_keys]):
                raise ValueError("Meta must contain following keys: {0}".format(required_meta_keys))
        # Check extra_coords contains required coords.
        required_extra_coords_keys = ["time", "exposure time"]
        extra_coords_keys = [coord[0] for coord in extra_coords]
        if not all([key in extra_coords_keys for key in required_extra_coords_keys]):
            raise ValueError("The following extra coords must be supplied: {0} vs. {1} from {2}".format(
                required_extra_coords_keys, extra_coords_keys, extra_coords))
        # Initialize IRISSpectrogramCube.
        super(IRISSpectrogramCube, self).__init__(
            data, wcs, uncertainty=uncertainty, mask=mask, meta=meta,
            unit=unit, extra_coords=extra_coords, copy=copy, missing_axes=missing_axes)

    def __getitem__(self, item):
        result = super(IRISSpectrogramCube, self).__getitem__(item)
        return IRISSpectrogramCube(
            result.data, result.wcs, result.uncertainty, result.unit, result.meta,
            convert_extra_coords_dict_to_input_format(result.extra_coords, result.missing_axes),
            mask=result.mask, missing_axes=result.missing_axes)

    def __repr__(self):
        roll = self.meta.get("SAT_ROT", None)
        if self.extra_coords["time"]["axis"] is None:
            axis_missing = True
        else:
            axis_missing = self.missing_axes[::-1][self.extra_coords["time"]["axis"]]
        if axis_missing is True:
            instance_start = instance_end = self.extra_coords["time"]["value"]
        else:
            instance_start = self.extra_coords["time"]["value"][0].isot
            instance_end = self.extra_coords["time"]["value"][-1].isot
        return """IRISSpectrogramCube
---------------------
{obs_repr}

Spectrogram period: {inst_start} -- {inst_end}
Data shape: {shape}
Axis Types: {axis_types}
Roll: {roll}
""".format(obs_repr=_produce_obs_repr_string(self.meta),
           inst_start=instance_start, inst_end=instance_end,
           shape=self.dimensions, axis_types=self.world_axis_physical_types,
           roll=roll)

    def convert_to(self, new_unit_type, time_obs=None, response_version=4):
        """
        Converts data, unit and uncertainty attributes to new unit type.

        Takes into consideration also the observation time and response version.

        The presence or absence of the exposure time correction is
        preserved in the conversions.

        Parameters
        ----------
        new_unit_type: `str`
           Unit type to convert data to.  Three values are accepted:
           "DN": Relevant IRIS data number based on detector type.
           "photons": photon counts
           "radiance": Perorms radiometric calibration conversion.

        time_obs: an `astropy.time.Time` object, as a kwarg, valid for version > 2
           Observation times of the datapoints.
           Must be in the format of, e.g.,
           time_obs=Time('2013-09-03', format='utime'),
           which yields 1094169600.0 seconds in value.
           The argument time_obs is ignored for versions 1 and 2.

        response_version: `int`
            Version number of effective area file to be used. Cannot be set
            simultaneously with response_file or pre_launch kwarg. Default=4.

        Returns
        -------
        result: `IRISSpectrogramCube`
            New IRISSpectrogramCube in new units.

        """
        detector_type = iris_tools.get_detector_type(self.meta)
        time_obs = time_obs
        response_version = response_version # Should default to latest
        if new_unit_type == "radiance" or self.unit.is_equivalent(iris_tools.RADIANCE_UNIT):
            # Get spectral dispersion per pixel.
            spectral_wcs_index = np.where(np.array(self.wcs.wcs.ctype) == "WAVE")[0][0]
            spectral_dispersion_per_pixel = self.wcs.wcs.cdelt[spectral_wcs_index] * \
                self.wcs.wcs.cunit[spectral_wcs_index]
            # Get solid angle from slit width for a pixel.
            lat_wcs_index = ["HPLT" in c for c in self.wcs.wcs.ctype]
            lat_wcs_index = np.arange(len(self.wcs.wcs.ctype))[lat_wcs_index]
            lat_wcs_index = lat_wcs_index[0]
            solid_angle = self.wcs.wcs.cdelt[lat_wcs_index] * \
                          self.wcs.wcs.cunit[lat_wcs_index] * iris_tools.SLIT_WIDTH
            # Get wavelength for each pixel.
            spectral_data_index = (-1) * (np.arange(len(self.dimensions)) + 1)[spectral_wcs_index]
            obs_wavelength = self.axis_world_coords(2)

        if new_unit_type == "DN" or new_unit_type == "photons":
            if self.unit.is_equivalent(iris_tools.RADIANCE_UNIT):
                # Convert from radiance to counts/s
                new_data_quantities = iris_tools.convert_or_undo_photons_per_sec_to_radiance(
                    (self.data * self.unit, self.uncertainty.array * self.unit),
                     time_obs, response_version, obs_wavelength, detector_type,
                     spectral_dispersion_per_pixel, solid_angle,
                    undo=True)
                new_data = new_data_quantities[0].value
                new_uncertainty = new_data_quantities[1].value
                new_unit = new_data_quantities[0].unit
                self = IRISSpectrogramCube(
                    new_data, self.wcs, new_uncertainty, new_unit, self.meta,
                    convert_extra_coords_dict_to_input_format(self.extra_coords, self.missing_axes),
                    mask=self.mask, missing_axes=self.missing_axes)
            if new_unit_type == "DN":
                new_unit = iris_tools.DN_UNIT[detector_type]
            else:
                new_unit = u.photon
            new_data_arrays, new_unit = iris_tools.convert_between_DN_and_photons(
                (self.data, self.uncertainty.array), self.unit, new_unit)
            new_data = new_data_arrays[0]
            new_uncertainty = new_data_arrays[1]
        elif new_unit_type == "radiance":
            if self.unit.is_equivalent(iris_tools.RADIANCE_UNIT):
                new_data = self.data
                new_uncertainty = self.uncertainty
                new_unit = self.unit
            else:
                # Ensure spectrogram is in units of counts/s.
                cube = self.convert_to("photons")
                try:
                    cube = cube.apply_exposure_time_correction()
                except ValueError(iris_tools.APPLY_EXPOSURE_TIME_ERROR):
                    pass
                # Convert to radiance units.
                new_data_quantities = iris_tools.convert_or_undo_photons_per_sec_to_radiance(
                        (cube.data*cube.unit, cube.uncertainty.array*cube.unit),
                         time_obs, response_version, obs_wavelength, detector_type,
                         spectral_dispersion_per_pixel, solid_angle)
                new_data = new_data_quantities[0].value
                new_uncertainty = new_data_quantities[1].value
                new_unit = new_data_quantities[0].unit
        else:
            raise ValueError("Input unit type not recognized.")
        return IRISSpectrogramCube(
            new_data, self.wcs, new_uncertainty, new_unit, self.meta,
            convert_extra_coords_dict_to_input_format(self.extra_coords, self.missing_axes),
            mask=self.mask, missing_axes=self.missing_axes)

    def apply_exposure_time_correction(self, undo=False, force=False):
        """
        Applies or undoes exposure time correction to data and uncertainty and adjusts unit.

        Correction is only applied (undone) if the object's unit doesn't (does)
        already include inverse time.  This can be overridden so that correction
        is applied (undone) regardless of unit by setting force=True.

        Parameters
        ----------
        undo: `bool`
            If False, exposure time correction is applied.
            If True, exposure time correction is undone.
            Default=False

        force: `bool`
            If not True, applies (undoes) exposure time correction only if unit
            doesn't (does) already include inverse time.
            If True, correction is applied (undone) regardless of unit.  Unit is still
            adjusted accordingly.

        Returns
        -------
        result: `IRISSpectrogramCube`
            New IRISSpectrogramCube in new units.

        """
        # Get exposure time in seconds and change array's shape so that
        # it can be broadcast with data and uncertainty arrays.
        exposure_time_s = self.extra_coords["exposure time"]["value"].to(u.s).value
        if not self.extra_coords["exposure time"]["value"].isscalar:
            if len(self.dimensions) == 1:
                pass
            elif len(self.dimensions) == 2:
                exposure_time_s = exposure_time_s[:, np.newaxis]
            elif len(self.dimensions) == 3:
                exposure_time_s = exposure_time_s[:, np.newaxis, np.newaxis]
            else:
                raise ValueError(
                    "IRISSpectrogramCube dimensions must be 2 or 3. Dimensions={0}".format(
                        len(self.dimensions.shape)))
        # Based on value on undo kwarg, apply or remove exposure time correction.
        if undo is True:
            new_data_arrays, new_unit = iris_tools.uncalculate_exposure_time_correction(
                (self.data, self.uncertainty.array), self.unit, exposure_time_s, force=force)
        else:
            new_data_arrays, new_unit = iris_tools.calculate_exposure_time_correction(
                (self.data, self.uncertainty.array), self.unit, exposure_time_s, force=force)
        # Return new instance of IRISSpectrogramCube with correction applied/undone.
        return IRISSpectrogramCube(
            new_data_arrays[0], self.wcs, new_data_arrays[1], new_unit, self.meta,
            convert_extra_coords_dict_to_input_format(self.extra_coords, self.missing_axes),
            mask=self.mask, missing_axes=self.missing_axes)


def read_iris_spectrograph_level2_fits(filenames, spectral_windows=None, uncertainty=True, memmap=False):
    """
    Reads IRIS level 2 spectrograph FITS from an OBS into an IRISSpectrograph instance.

    Parameters
    ----------
    filenames: `list` of `str` or `str`
        Filename of filenames to be read.  They must all be associated with the same
        OBS number.

    spectral_windows: iterable of `str` or `str`
        Spectral windows to extract from files.  Default=None, implies, extract all
        spectral windows.

    uncertainty : `bool`
        Default value is `True`.
        If `True`, will compute the uncertainty for the data (slower and
        uses more memory). If `memmap=True`, the uncertainty is never computed.

    memmap : `bool`
        Default value is `False`.
        If `True`, will not load arrays into memory, and will only read from
        the file into memory when needed. This option is faster and uses a
        lot less memory. However, because FITS scaling is not done on-the-fly,
        the data units will be unscaled, not the usual data numbers (DN).

    Returns
    -------
    result: `irispy.spectrograph.IRISSpectrograph`

    """
    if type(filenames) is str:
        filenames = [filenames]
    for f, filename in enumerate(filenames):
        hdulist = fits.open(filename, memmap=memmap, do_not_scale_image_data=memmap)
        hdulist.verify('fix')
        if f == 0:
            # Determine number of raster positions in a scan
            raster_positions_per_scan = int(hdulist[0].header["NRASTERP"])
            # Collecting the window observations.
            windows_in_obs = np.array([hdulist[0].header["TDESC{0}".format(i)]
                                       for i in range(1, hdulist[0].header["NWIN"]+1)])
            # If spectral_window is not set then get every window.
            # Else take the appropriate windows
            if not spectral_windows:
                spectral_windows_req = windows_in_obs
                window_fits_indices = range(1, len(hdulist)-2)
            else:
                if type(spectral_windows) is str:
                    spectral_windows_req = [spectral_windows]
                else:
                    spectral_windows_req = spectral_windows
                spectral_windows_req = np.asarray(spectral_windows_req, dtype="U")
                window_is_in_obs = np.asarray(
                    [window in windows_in_obs for window in spectral_windows_req])
                if not all(window_is_in_obs):
                    missing_windows = window_is_in_obs == False
                    raise ValueError("Spectral windows {0} not in file {1}".format(
                        spectral_windows[missing_windows], filenames[0]))
                window_fits_indices = np.nonzero(np.in1d(windows_in_obs,
                                                         spectral_windows))[0]+1
            # Generate top level meta dictionary from first file
            # main header.
            top_meta = {"TELESCOP": hdulist[0].header["TELESCOP"],
                        "INSTRUME": hdulist[0].header["INSTRUME"],
                        "DATA_LEV": hdulist[0].header["DATA_LEV"],
                        "OBSID": hdulist[0].header["OBSID"],
                        "OBS_DESC": hdulist[0].header["OBS_DESC"],
                        "STARTOBS": Time(hdulist[0].header["STARTOBS"]),
                        "ENDOBS": Time(hdulist[0].header["ENDOBS"]),
                        "SAT_ROT": hdulist[0].header["SAT_ROT"] * u.deg,
                        "AECNOBS": int(hdulist[0].header["AECNOBS"]),
                        "FOVX": hdulist[0].header["FOVX"] * u.arcsec,
                        "FOVY": hdulist[0].header["FOVY"] * u.arcsec,
                        "SUMSPTRN": hdulist[0].header["SUMSPTRN"],
                        "SUMSPTRF": hdulist[0].header["SUMSPTRF"],
                        "SUMSPAT": hdulist[0].header["SUMSPAT"],
                        "NEXPOBS": hdulist[0].header["NEXPOBS"],
                        "NRASTERP": hdulist[0].header["NRASTERP"],
                        "KEYWDDOC": hdulist[0].header["KEYWDDOC"]}
            # Initialize meta dictionary for each spectral_window
            window_metas = {}
            for i, window_name in enumerate(spectral_windows_req):
                if "FUV" in hdulist[0].header["TDET{0}".format(window_fits_indices[i])]:
                    spectral_summing = hdulist[0].header["SUMSPTRF"]
                else:
                    spectral_summing = hdulist[0].header["SUMSPTRN"]
                window_metas[window_name] = {
                    "detector type":
                        hdulist[0].header["TDET{0}".format(window_fits_indices[i])],
                    "spectral window":
                        hdulist[0].header["TDESC{0}".format(window_fits_indices[i])],
                    "brightest wavelength":
                        hdulist[0].header["TWAVE{0}".format(window_fits_indices[i])],
                    "min wavelength":
                        hdulist[0].header["TWMIN{0}".format(window_fits_indices[i])],
                    "max wavelength":
                        hdulist[0].header["TWMAX{0}".format(window_fits_indices[i])],
                    "SAT_ROT": hdulist[0].header["SAT_ROT"],
                    "spatial summing": hdulist[0].header["SUMSPAT"],
                    "spectral summing": spectral_summing
                }
            # Create a empty list for every spectral window and each
            # spectral window is a key for the dictionary.
            data_dict = dict([(window_name, list())
                              for window_name in spectral_windows_req])
        # Determine extra coords for this raster.
        times = (Time(hdulist[0].header["STARTOBS"]) +
                 TimeDelta(hdulist[-2].data[:, hdulist[-2].header["TIME"]], format='sec'))
        raster_positions = np.arange(int(hdulist[0].header["NRASTERP"]))
        pztx = hdulist[-2].data[:, hdulist[-2].header["PZTX"]] * u.arcsec
        pzty = hdulist[-2].data[:, hdulist[-2].header["PZTY"]] * u.arcsec
        xcenix = hdulist[-2].data[:, hdulist[-2].header["XCENIX"]] * u.arcsec
        ycenix = hdulist[-2].data[:, hdulist[-2].header["YCENIX"]] * u.arcsec
        obs_vrix = hdulist[-2].data[:, hdulist[-2].header["OBS_VRIX"]] * u.m/u.s
        ophaseix = hdulist[-2].data[:, hdulist[-2].header["OPHASEIX"]]
        exposure_times_fuv = hdulist[-2].data[:, hdulist[-2].header["EXPTIMEF"]] * u.s
        exposure_times_nuv = hdulist[-2].data[:, hdulist[-2].header["EXPTIMEN"]] * u.s
        # If OBS is raster, include raster positions.  Otherwise don't.
        if top_meta["NRASTERP"] > 1:
            general_extra_coords = [("time", 0, times),
                                    ("raster position", 0, np.arange(top_meta["NRASTERP"])),
                                    ("pztx", 0, pztx), ("pzty", 0, pzty),
                                    ("xcenix", 0, xcenix), ("ycenix", 0, ycenix),
                                    ("obs_vrix", 0, obs_vrix), ("ophaseix", 0, ophaseix)]
        else:
            general_extra_coords = [("time", 0, times),
                                    ("pztx", 0, pztx), ("pzty", 0, pzty),
                                    ("xcenix", 0, xcenix), ("ycenix", 0, ycenix),
                                    ("obs_vrix", 0, obs_vrix), ("ophaseix", 0, ophaseix)]
        for i, window_name in enumerate(spectral_windows_req):
            # Determine values of properties dependent on detector type.
            if "FUV" in hdulist[0].header["TDET{0}".format(window_fits_indices[i])]:
                exposure_times = exposure_times_fuv
                DN_unit = iris_tools.DN_UNIT["FUV"]
                readout_noise = iris_tools.READOUT_NOISE["FUV"]
            elif "NUV" in hdulist[0].header["TDET{0}".format(window_fits_indices[i])]:
                exposure_times = exposure_times_nuv
                DN_unit = iris_tools.DN_UNIT["NUV"]
                readout_noise = iris_tools.READOUT_NOISE["NUV"]
            else:
                raise ValueError("Detector type in FITS header not recognized.")
            # Derive WCS, data and mask for NDCube from file.
            # Sit-and-stare have a CDELT of 0 which causes issues in astropy WCS.
            # In this case, set CDELT to a tiny non-zero number.
            if hdulist[window_fits_indices[i]].header["CDELT3"] == 0:
                hdulist[window_fits_indices[i]].header["CDELT3"] = 1e-10
            wcs_ = WCS(hdulist[window_fits_indices[i]].header)
            if not memmap:
                data_mask = hdulist[window_fits_indices[i]].data == -200.
            else:
                data_mask = None
            # Derive extra coords for this spectral window.
            window_extra_coords = copy.deepcopy(general_extra_coords)
            window_extra_coords.append(("exposure time", 0, exposure_times))
            # Collect metadata relevant to single files.
            try:
                date_obs = Time(hdulist[0].header["DATE_OBS"])
            except ValueError:
                date_obs = None
            try:
                date_end = Time(hdulist[0].header["DATE_END"])
            except ValueError:
                date_end = None
            single_file_meta = {"SAT_ROT": hdulist[0].header["SAT_ROT"] * u.deg,
                                "DATE_OBS": date_obs,
                                "DATE_END": date_end,
                                "HLZ": bool(int(hdulist[0].header["HLZ"])),
                                "SAA": bool(int(hdulist[0].header["SAA"])),
                                "DSUN_OBS": hdulist[0].header["DSUN_OBS"] * u.m,
                                "IAECEVFL": hdulist[0].header["IAECEVFL"],
                                "IAECFLAG": hdulist[0].header["IAECFLAG"],
                                "IAECFLFL": hdulist[0].header["IAECFLFL"],
                                "KEYWDDOC": hdulist[0].header["KEYWDDOC"],
                                "detector type":
                                     hdulist[0].header["TDET{0}".format(window_fits_indices[i])],
                                "spectral window": window_name,
                                "OBSID": hdulist[0].header["OBSID"],
                                "OBS_DESC": hdulist[0].header["OBS_DESC"],
                                "STARTOBS": Time(hdulist[0].header["STARTOBS"]),
                                "ENDOBS": Time(hdulist[0].header["ENDOBS"])
                                }
            # Derive uncertainty of data
            if uncertainty:
                out_uncertainty = u.Quantity(np.sqrt(
                    (hdulist[window_fits_indices[i]].data*DN_unit).to(u.photon).value +
                    readout_noise.to(u.photon).value**2), unit=u.photon).to(DN_unit).value
            else:
                out_uncertainty = None
            # Appending NDCube instance to the corresponding window key in dictionary's list.
            data_dict[window_name].append(
                IRISSpectrogramCube(hdulist[window_fits_indices[i]].data, wcs_, out_uncertainty,
                                    DN_unit, single_file_meta, window_extra_coords,
                                    mask=data_mask))
        hdulist.close()
    # Construct dictionary of IRISSpectrogramCubeSequences for spectral windows
    data = dict([(window_name, IRISSpectrogramCubeSequence(data_dict[window_name],
                                                           window_metas[window_name],
                                                           common_axis=0))
                 for window_name in spectral_windows_req])
    # Initialize an IRISSpectrograph object.
    return IRISSpectrograph(data, meta=top_meta)



def _produce_obs_repr_string(meta):
    obs_info = [meta.get(key, "Unknown") for key in ["OBSID", "OBS_DESC", "STARTOBS", "ENDOBS"]]
    return """OBS ID: {obs_id}
OBS Description: {obs_desc}
OBS period: {obs_start} -- {obs_end}""".format(obs_id=obs_info[0], obs_desc=obs_info[1],
                                               obs_start=obs_info[2], obs_end=obs_info[3])


def _try_parse_time_on_meta(meta):
    result = None
    try:
        result = Time(meta)
    except ValueError as err:
        if "not a valid time string!" not in err.args[0]:
            raise err
        else:
            pass
    return result
