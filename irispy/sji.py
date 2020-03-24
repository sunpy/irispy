'''
This module provides movie tools for level 2 IRIS SJI fits file
'''

import warnings

import numpy as np
from astropy.io import fits
import astropy.units as u
from astropy.wcs import WCS
from sunpy.time import parse_time
import sunpy.cm
from astropy.time import Time, TimeDelta
from sunpy.map import GenericMap
from ndcube import NDCube
from ndcube.utils.cube import convert_extra_coords_dict_to_input_format
from ndcube.ndcube_sequence import NDCubeSequence

from irispy import iris_tools

__all__ = ['IRISMapCube', 'IRISMapCubeSequence', 'read_iris_sji_level2_fits']

# the following value is only appropriate for byte scaled images
BAD_PIXEL_VALUE_SCALED = -200
# the following value is only appropriate for unscaled images
BAD_PIXEL_VALUE_UNSCALED = -32768


class IRISMapCube(NDCube):
    """
    IRISMapCube

    Class representing SJI Images described by a single WCS

    Parameters
    ----------
    data: `numpy.ndarray`
        The array holding the actual data in this object.

    wcs: `ndcube.wcs.wcs.WCS`
        The WCS object containing the axes' information

    unit : `astropy.unit.Unit` or `str`
        Unit for the dataset.
        Strings that can be converted to a Unit are allowed.

    meta : dict-like object
        Additional meta information about the dataset.

    uncertainty : any type, optional
        Uncertainty in the dataset. Should have an attribute uncertainty_type
        that defines what kind of uncertainty is stored, for example "std"
        for standard deviation or "var" for variance. A metaclass defining
        such an interface is NDUncertainty - but isn’t mandatory. If the
        uncertainty has no such attribute the uncertainty is stored as
        UnknownUncertainty.
        Defaults to None.

    mask : any type, optional
        Mask for the dataset. Masks should follow the numpy convention
        that valid data points are marked by False and invalid ones with True.
        Defaults to None.

    extra_coords : iterable of `tuple`s, each with three entries
        (`str`, `int`, `astropy.units.quantity` or array-like)
        Gives the name, axis of data, and values of coordinates of a data axis
        not included in the WCS object.

    copy : `bool`, optional
        Indicates whether to save the arguments as copy. True copies every
        attribute before saving it while False tries to save every parameter
        as reference. Note however that it is not always possible to save the
        input as reference.
        Default is False.

    scaled : `bool`, optional
        Indicates if datas has been scaled.

    Examples
    --------
    >>> from irispy import sji
    >>> from irispy.data import sample
    >>> sji = read_iris_sji_level2_fits(sample.SJI_CUBE_1400)
    """

    def __init__(self, data, wcs, uncertainty=None, unit=None, meta=None,
                 mask=None, extra_coords=None, copy=False, missing_axes=None,
                 scaled=None):
        """
        Initialization of Slit Jaw Imager
        """
        warnings.warn("This class is still in early stages of development. API not stable.")
        # Set whether SJI data is scaled or not.
        self.scaled = scaled
        # Dust_masked variable shows whether the dust pixels are set to True in the data mask.
        self.dust_masked = False
        # Initialize IRISMapCube.
        super().__init__(data, wcs, uncertainty=uncertainty, mask=mask,
                         meta=meta, unit=unit, extra_coords=extra_coords,
                         copy=copy, missing_axes=missing_axes)

    def __repr__(self):
        roll = self.meta.get("SAT_ROT", None)
        # Conversion of the start date of OBS
        startobs = self.meta.get("STARTOBS", None)
        startobs = startobs.isot if startobs else None
        # Conversion of the end date of OBS
        endobs = self.meta.get("ENDOBS", None)
        endobs = endobs.isot if endobs else None
        # Conversion of the instance start and end of OBS
        if isinstance(self.extra_coords["time"]["value"], Time):
            instance_start = self.extra_coords["time"]["value"].min().isot
            instance_end = self.extra_coords["time"]["value"].max().isot
        else:
            instance_start = None
            instance_end = None
        # Representation of IRISMapCube object
        return (
            """
    IRISMapCube
    ---------
    Observatory:\t\t {obs}
    Instrument:\t\t\t {instrument}
    Bandpass:\t\t\t {bandpass}
    Obs. Start:\t\t\t {startobs}
    Obs. End:\t\t\t {endobs}
    Instance Start:\t\t {instance_start}
    Instance End:\t\t {instance_end}
    Roll:\t\t\t {roll}
    Total Frames in Obs.:\t {frame_num}
    IRIS Obs. id:\t\t {obs_id}
    IRIS Obs. Description:\t {obs_desc}
    Cube dimensions:\t\t {dimensions}
    Axis Types:\t\t\t {axis_types}
    """.format(obs=self.meta.get('TELESCOP', None),
               instrument=self.meta.get('INSTRUME', None),
               bandpass=self.meta.get('TWAVE1', None),
               startobs=startobs,
               endobs=endobs,
               instance_start=instance_start,
               instance_end=instance_end,
               roll=roll,
               frame_num=self.meta.get("NBFRAMES", None),
               obs_id=self.meta.get('OBSID', None),
               obs_desc=self.meta.get('OBS_DESC', None),
               axis_types=self.world_axis_physical_types,
               dimensions=self.dimensions))

    def __getitem__(self, item):
        # Use parent method to slice item.
        sliced_self = super().__getitem__(item)
        # Ensure value of scaled property is maintained.
        sliced_self.scaled = self.scaled
        return sliced_self

    def plot(self, *args, **kwargs):
        """See parent class for docstring. To Do: Inherit parent docstring."""
        # If colormap not set, load one default sunpy colormap based on SJI passband.
        cmap = kwargs.pop("cmap", None)
        if not cmap:
            cmap = sunpy.cm.get_cmap(name="irissji{0}".format(int(self.meta["TWAVE1"])))

        # Call parent plot function
        return super().plot(*args, cmap=cmap, **kwargs)

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
            If True, exposure time correction is removed.
            Default=False

        force: `bool`
            If not True, applies (undoes) exposure time correction only if unit
            doesn't (does) already include inverse time.
            If True, correction is applied (undone) regardless of unit.  Unit is still
            adjusted accordingly.

        Returns
        -------
        result: `IRISMapCube`
            A new IRISMapCube is returned with the correction applied (undone).

        """
        # Raise an error if this method is called while memmap is used
        if not self.scaled:
            raise ValueError("This method is not available as you are using memmap")
        # Get exposure time in seconds and change array's shape so that
        # it can be broadcast with data and uncertainty arrays.
        exposure_time_s = u.Quantity(self.extra_coords["exposure time"]["value"], unit='s').value
        if not np.isscalar(self.extra_coords["exposure time"]["value"]):
            if self.data.ndim == 1:
                pass
            elif self.data.ndim == 2:
                exposure_time_s = exposure_time_s[:, np.newaxis]
            elif self.data.ndim == 3:
                exposure_time_s = exposure_time_s[:, np.newaxis, np.newaxis]
            else:
                raise ValueError(
                    "IRISMapCube dimensions must be 2 or 3. Dimensions={0}".format(
                        self.data.ndim))
        # Based on value on undo kwarg, apply or remove exposure time correction.
        if undo is True:
            new_data_arrays, new_unit = iris_tools.uncalculate_exposure_time_correction(
                (self.data, self.uncertainty.array), self.unit, exposure_time_s, force=force)
        else:
            new_data_arrays, new_unit = iris_tools.calculate_exposure_time_correction(
                (self.data, self.uncertainty.array), self.unit, exposure_time_s, force=force)
        # Return new instance of IRISMapCube with correction applied/undone.
        return IRISMapCube(
            data=new_data_arrays[0], wcs=self.wcs, uncertainty=new_data_arrays[1],
            unit=new_unit, meta=self.meta, mask=self.mask, missing_axes=self.missing_axes,
            scaled=self.scaled,
            extra_coords=convert_extra_coords_dict_to_input_format(self.extra_coords,
                                                                   self.missing_axes))

    def apply_dust_mask(self, undo=False):
        """
        Applies or undoes an update of the mask with the dust particles positions.

        Parameters
        ----------
        undo: `bool`
            If False, dust particles positions mask will be applied.
            If True, dust particles positions mask will be removed.
            Default=False

        Returns
        -------
        result :
            Rewrite self.mask with/without the dust positions.
        """
        # Calculate position of dust pixels
        dust_mask = iris_tools.calculate_dust_mask(self.data)
        if undo:
            # If undo kwarg IS set, unmask dust pixels.
            self.mask[dust_mask] = False
            self.dust_masked = False
        else:
            # If undo kwarg is NOT set, mask dust pixels.
            self.mask[dust_mask] = True
            self.dust_masked = True


class IRISMapCubeSequence(NDCubeSequence):
    """Class for holding, slicing and plotting IRIS SJI data.

    This class contains all the functionality of its super class with
    some additional functionalities.

    Parameters
    ----------
    data_list: `list`
        List of `IRISMapCube` objects from the same OBS ID.
        Each cube must contain the same 'detector type' in its meta attribute.

    meta: `dict` or header object
        Metadata associated with the sequence.

    common_axis: `int`
        The axis of the NDCubes corresponding to time.

    """
    def __init__(self, data_list, meta=None, common_axis=0):
        # Initialize IRISMapCubeSequence.
        super().__init__(data_list, meta=meta, common_axis=common_axis)

    def __repr__(self):
        roll = self.meta.get("SAT_ROT", None)
        # Conversion of the start date of OBS
        startobs = self.meta.get("STARTOBS", None)
        startobs = startobs.isot if startobs else None
        # Conversion of the end date of OBS
        endobs = self.meta.get("ENDOBS", None)
        endobs = endobs.isot if endobs else None
        # Conversion of the instance start of OBS
        instance_start = self[0].extra_coords["time"]["value"]
        instance_start = instance_start.isot if instance_start else None
        # Conversion of the instance end of OBS
        instance_end = self[-1].extra_coords["time"]["value"]
        instance_end = instance_end.isot if instance_end else None
        # Representation of IRISMapCube object
        return """
IRISMapCubeSequence
---------------------
Observatory:\t\t {obs}
Instrument:\t\t {instrument}

OBS ID:\t\t\t {obs_id}
OBS Description:\t {obs_desc}
OBS period:\t\t {obs_start} -- {obs_end}

Sequence period:\t {inst_start} -- {inst_end}
Sequence Shape:\t\t {seq_shape}
Roll:\t\t\t {roll}
Axis Types:\t\t {axis_types}

""".format(obs=self.meta.get('TELESCOP', None),
           instrument=self.meta.get('INSTRUME', None),
           obs_id=self.meta.get("OBSID", None),
           obs_desc=self.meta.get("OBS_DESC", None),
           obs_start=startobs,
           obs_end=endobs,
           inst_start=instance_start,
           inst_end=instance_end,
           seq_shape=self.dimensions,
           roll=roll,
           axis_types=self.world_axis_physical_types)

    def __getitem__(self, item):
        return self.index_as_cube[item]

    @property
    def dimensions(self):
        return self.cube_like_dimensions

    @property
    def world_axis_physical_types(self):
        return self.cube_like_world_axis_physical_types

    def plot(self, axes=None, plot_axis_indices=None, axes_coordinates=None,
             axes_units=None, data_unit=None, **kwargs):
        """
        Visualizes data in the IRISMapCubeSequence with the sequence axis folded
        into the common axis.

        Based on the cube-like dimensionality of the sequence and value of plot_axis_indices
        kwarg, a Line/Image Plot/Animation is produced.

        Parameters
        ----------
        axes: `astropy.visualization.wcsaxes.core.WCSAxes` or ??? or None.
            The axes to plot onto. If None the current axes will be used.

        plot_axis_indices: `int` or iterable of one or two `int`.
            If two axis indices are given, the sequence is visualized as an image or
            2D animation, assuming the sequence has at least 2 cube-like dimensions.
            The cube-like dimension indicated by the 0th element of plot_axis indices is
            displayed on the x-axis while the cube-like dimension indicated by the 1st
            element of plot_axis_indices is displayed on the y-axis. If only one axis
            index is given (either as an int or a list of one int), then a 1D line
            animation is produced with the indicated cube-like dimension on the x-axis
            and other cube-like dimensions represented by animations sliders.
            Default=[-1, -2]. If sequence only has one cube-like dimension,
            plot_axis_indices is ignored and a static 1D line plot is produced.

        axes_coordinates: `None` or `list` of `None` `astropy.units.Quantity` `numpy.ndarray` `str`
            Denotes physical coordinates for plot and slider axes.
            If None coordinates derived from the WCS objects will be used for all axes.
            If a list, its length should equal either the number cube-like dimensions or
            the length of plot_axis_indices.
            If the length equals the number of cube-like dimensions, each element describes
            the coordinates of the corresponding cube-like dimension.
            If the length equals the length of plot_axis_indices,
            the 0th entry describes the coordinates of the x-axis
            while (if length is 2) the 1st entry describes the coordinates of the y-axis.
            Slider axes are implicitly set to None.
            If the number of cube-like dimensions equals the length of plot_axis_indices,
            the latter convention takes precedence.
            The value of each entry should be either
            `None` (implies derive the coordinates from the WCS objects),
            an `astropy.units.Quantity` or a `numpy.ndarray` of coordinates for each pixel,
            or a `str` denoting a valid extra coordinate.

        axes_units: `None or `list` of `None`, `astropy.units.Unit` and/or `str`
            If None units derived from the WCS objects will be used for all axes.
            If a list, its length should equal either the number cube-like dimensions or
            the length of plot_axis_indices.
            If the length equals the number of cube-like dimensions, each element gives the
            unit in which the coordinates along the corresponding cube-like dimension should
            displayed whether they be a plot axes or a slider axes.
            If the length equals the length of plot_axis_indices,
            the 0th entry describes the unit in which the x-axis coordinates should be displayed
            while (if length is 2) the 1st entry describes the unit in which the y-axis should
            be displayed.  Slider axes are implicitly set to None.
            If the number of cube-like dimensions equals the length of plot_axis_indices,
            the latter convention takes precedence.
            The value of each entry should be either
            `None` (implies derive the unit from the WCS object of the 0th sub-cube),
            `astropy.units.Unit` or a valid unit `str`.

        data_unit: `astropy.unit.Unit` or valid unit `str` or None
            Unit in which data be displayed.  If the length of plot_axis_indices is 2,
            a 2D image/animation is produced and data_unit determines the unit represented by
            the color table.  If the length of plot_axis_indices is 1,
            a 1D plot/animation is produced and data_unit determines the unit in which the
            y-axis is displayed.

        Returns
        -------
        return : ndcube.mixins.sequence_plotting.plot_as_cube

        """
        return self.plot_as_cube(axes=axes, plot_axis_indices=plot_axis_indices,
                                 axes_coordinates=axes_coordinates,
                                 axes_units=axes_units, data_unit=data_unit, **kwargs)

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
        result: `IRISMapCubeSequence`
            If copy=False, the original IRISMapCubeSequence is modified with the exposure
            time correction applied (undone).
            If copy=True, a new IRISMapCubeSequence is returned with the correction
            applied (undone).

        """
        corrected_data = [cube.apply_exposure_time_correction(undo=undo, force=force)
                          for cube in self.data]
        if copy is True:
            return IRISMapCubeSequence(data_list=corrected_data, meta=self.meta,
                                       common_axis=self._common_axis)
        else:
            self.data = corrected_data

    def apply_dust_mask(self, undo=False):
        """
        Applies or undoes an update of all the masks with the dust particles positions.

        Parameters
        ----------
        undo: `bool`
            If False, dust particles positions masks will be applied.
            If True, dust particles positions masks will be removed.
            Default=False

        Returns
        -------
        result :
            Rewrite all self.data[i] mask with/without the dust positions.

        """
        for cube in self.data:
            cube.apply_dust_mask(undo=undo)


def read_iris_sji_level2_fits(filenames, memmap=False):
    """
    Read IRIS level 2 SJI FITS from an OBS into an IRISMapCube instance.

    Parameters
    ----------
    filenames: `list` of `str` or `str`
        Filename or filenames to be read.  They must all be associated with the same
        OBS number.

    memmap : `bool`
        Default value is `False`.
        If the user wants to use it, he has to set `True`

    Returns
    -------
    result: `irispy.sji.IRISMapCube` or `irispy.sji.IRISMapCubeSequence`

    """
    list_of_cubes = []
    if type(filenames) is str:
        filenames = [filenames]
    for filename in filenames:
        # Open a fits file
        hdulist = fits.open(filename, memmap=memmap, do_not_scale_image_data=memmap)
        hdulist.verify('fix')
        # Derive WCS, data and mask for NDCube from fits file.
        wcs = WCS(hdulist[0].header)
        data = hdulist[0].data
        data_nan_masked = hdulist[0].data
        if memmap:
            data_nan_masked[data == BAD_PIXEL_VALUE_UNSCALED] = 0
            mask = None
            scaled = False
            unit = iris_tools.DN_UNIT["SJI_UNSCALED"]
            uncertainty = None
        elif not memmap:
            data_nan_masked[data == BAD_PIXEL_VALUE_SCALED] = np.nan
            mask = data_nan_masked == BAD_PIXEL_VALUE_SCALED
            scaled = True
            # Derive unit and readout noise from the detector
            unit = iris_tools.DN_UNIT["SJI"]
            readout_noise = iris_tools.READOUT_NOISE["SJI"]
            # Derive uncertainty of data for NDCube from fits file.
            uncertainty = u.Quantity(np.sqrt((data_nan_masked*unit).to(u.photon).value
                                             + readout_noise.to(u.photon).value**2),
                                     unit=u.photon).to(unit).value
        # Derive exposure time from detector.
        exposure_times = hdulist[1].data[:, hdulist[1].header["EXPTIMES"]]
        # Derive extra coordinates for NDCube from fits file.
        times = (Time(hdulist[0].header["STARTOBS"]) +
                 TimeDelta(hdulist[1].data[:, hdulist[1].header["TIME"]], format='sec'))
        pztx = hdulist[1].data[:, hdulist[1].header["PZTX"]] * u.arcsec
        pzty = hdulist[1].data[:, hdulist[1].header["PZTY"]] * u.arcsec
        xcenix = hdulist[1].data[:, hdulist[1].header["XCENIX"]] * u.arcsec
        ycenix = hdulist[1].data[:, hdulist[1].header["YCENIX"]] * u.arcsec
        obs_vrix = hdulist[1].data[:, hdulist[1].header["OBS_VRIX"]] * u.m/u.s
        ophaseix = hdulist[1].data[:, hdulist[1].header["OPHASEIX"]]
        slit_pos_x = hdulist[1].data[:, hdulist[1].header["SLTPX1IX"]]
        slit_pos_y = hdulist[1].data[:, hdulist[1].header["SLTPX2IX"]]
        extra_coords = [('time', 0, times), ("pztx", 0, pztx), ("pzty", 0, pzty),
                        ("xcenix", 0, xcenix), ("ycenix", 0, ycenix),
                        ("obs_vrix", 0, obs_vrix), ("ophaseix", 0, ophaseix),
                        ("exposure time", 0, exposure_times),
                        ("slit x position", 0, slit_pos_x * u.pix),
                        ("slit y position", 0, slit_pos_y * u.pix)]
        # Extraction of meta for NDCube from fits file.
        startobs = hdulist[0].header.get('STARTOBS', None)
        startobs = Time(startobs) if startobs else None
        endobs = hdulist[0].header.get('ENDOBS', None)
        endobs = Time(endobs) if endobs else None
        meta = {'TELESCOP': hdulist[0].header.get('TELESCOP', None),
                'INSTRUME': hdulist[0].header.get('INSTRUME', None),
                'DATA_LEV': hdulist[0].header.get('DATA_LEV', None),
                'TWAVE1': hdulist[0].header.get('TWAVE1', None),
                'OBSID': hdulist[0].header.get('OBSID', None),
                'STARTOBS': startobs,
                'ENDOBS': endobs,
                'SAT_ROT': hdulist[0].header['SAT_ROT'] * u.deg,
                'NBFRAMES': hdulist[0].data.shape[0],
                'OBS_DESC': hdulist[0].header.get('OBS_DESC', None),
                'FOVX': hdulist[0].header['FOVX'] * u.arcsec,
                'FOVY': hdulist[0].header['FOVY'] * u.arcsec,
                'XCEN': hdulist[0].header['XCEN'] * u.arcsec,
                'YCEN': hdulist[0].header['YCEN'] * u.arcsec}
        list_of_cubes.append(IRISMapCube(data_nan_masked, wcs, uncertainty=uncertainty,
                                         unit=unit, meta=meta, mask=mask,
                                         extra_coords=extra_coords, scaled=scaled))
        hdulist.close()
    if len(filenames) == 1:
        return list_of_cubes[0]
    else:
        # In Sequence, all cubes must have the same Observation Identification.
        if np.any([cube.meta["OBSID"] != list_of_cubes[0].meta["OBSID"]
                   for cube in list_of_cubes]):
            raise ValueError("Inputed files must have the same Observation Identification")
        # In Sequence, all cubes must have the same passband.
        if np.any([cube.meta["TWAVE1"] != list_of_cubes[0].meta["TWAVE1"]
                   for cube in list_of_cubes]):
            raise ValueError("Inputed files must have the same passband")
        return IRISMapCubeSequence(list_of_cubes, meta=meta, common_axis=0)


class SJIMap(GenericMap):
    def __init__(self, data, header, **kwargs):
        raise ImportError("This class has been replaced by irispy.sji.IRISMapCube.")


class SJICube(object):
    def __init__(self, input):
        raise ImportError("This class has been replaced by irispy.sji.IRISMapCube."
                          "To create an irispy.sji.IRISMapCube from a level 2 SJI FITS file,"
                          "use irispy.sji.read_iris_sji_level2_fits.")


def SJI_fits_to_cube(filelist, start=0, stop=None, skip=None):
    raise ImportError("This function has been replaced by irispy.sji.read_iris_sji_level2_fits.")
