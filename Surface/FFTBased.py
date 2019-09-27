"""
Classes for generating pseudo-random surfaces based on description of FFT:
    ===========================================================================
    ===========================================================================
    Each class inherits functionallity from the Surface but changes the 
    __init__ and descretise functions
    ===========================================================================
    ===========================================================================
    DiscFreqSurface:
        Generate a surface conating only specific frequency componenets
    ProbFreqSurface:
        Generate a surface containing normally distributed amptitudes with a
        specified function for the varience of the distribution based on the 
        frequency
    DtmnFreqSurface:
        Generate a surface containing frequency components with amptitude 
        specifed by a function of the frequency
        
    ===========================================================================
    ===========================================================================

#TODO:
        doc strings
"""

from .Surface_class import _AnalyticalSurface
import numpy as np
import typing
from numbers import Number

__all__ = ["DiscFreqSurface", "ProbFreqSurface", "HurstFractalSurface"]  # , "DtmnFreqSurface"]


class DiscFreqSurface(_AnalyticalSurface):
    r""" Object for reading, manipulating and plotting surfaces
    
    The Surface class contains methods for setting properties, 
    examining measures of roughness and descriptions of surfaces, plotting,
    fixing and editing surfaces.
    
    Parameters
    ----------
    frequencies, amptitudes=[1], phases_rads=[0], 
                 dimentions=2

                 
    Other Parameters
    ----------------
    
    grid_spacing extent
    
    
    Attributes
    ----------
    profile : array
        The height infromation of the surface
        
    shape : tuple
        The numbeer of points in each direction of the profile
        
    size : int
        The total number of points in the profile
    
    grid_spacing: float
        The distance between adjacent points in the profile
        
    extent : list
        The size of the profile in the same units as the grid spacing is set in
        
    dimentions : int {1, 2}
        The number of dimentions of the surface
    
    surface_type : str {'Experimental', 'Analytical', 'Random'}
        A description of the surface type    
    
    acf, psd, fft : array or None
        The acf, psd and fft of the surface set by the get_acf get_psd and
        get_fft methods
    
    Methods
    -------
    
    descretise
    show
    subtract_polynomial
    roughness
    get_mat_vr
    get_height_of_mat_vr
    find_summits
    get_summit_curvatures
    low_pass_filter
    read_from_file
    fill_holes
    resample
    get_fft
    get_acf
    get_psd
    
    See Also
    --------
    ProbFreqSurface
    HurstFractalSurface
    
    Notes
    -----
    Roughness functions are aliased from the functions provided in the surface 
    module
    
    Examples
    --------
    
    
    """
    """
    Generates a surface containg discrete frequncy components
    
    Usage:
    
    DiscFreqSurface(frequencies, amptitudes=[1], phases_rads=[0], dimentions=2)
    
    Generates a surface with the specified frequencies, amptitudes and phases 
    any kwargs that can be passed to surface can also be passed to this
    
    mySurf=DiscFreqSurface(10, 0.1) 
    mySurf.extent=[0.5,0.5]
    mySurf.descretise(0.001)
    
    Generates and descretises a 2D surface with a frequency of 10 rads/unit
    of global size, descretised on a grid with a grid_spacing of 0.001
    """
    is_descrete = False
    surface_type = 'discreteFreq'

    def __init__(self, frequencies, amptitudes: tuple = (1,), phases_rads: tuple = (0,), rotation: Number = 0,
                 shift: typing.Optional[tuple] = None,
                 generate: bool = False, grid_spacing: float = None,
                 extent: tuple = None, shape: tuple = None):

        if type(frequencies) is list or type(frequencies) is np.ndarray:
            self.frequencies = frequencies
        else:
            raise ValueError('Frequencies, amptitudes and phases must be equal'
                             'length lists or np.arrays')
        is_complex = [type(amp) is complex for amp in amptitudes]
        if any(is_complex):
            if not len(frequencies) == len(amptitudes):
                raise ValueError('Frequencies, amptitudes and phases must be'
                                 ' equal length lists or np.arrays')
            else:
                self.amptitudes = amptitudes
        else:
            if not len(frequencies) == len(amptitudes) == len(phases_rads):
                raise ValueError('Frequencies, amptitudes and phases must be'
                                 ' equal length lists or np.arrays')
            else:
                cplx_amps = []
                for idx in range(len(amptitudes)):
                    cplx_amps.append(amptitudes[idx] *
                                     np.exp(1j * phases_rads[idx]))
                self.amptitudes = cplx_amps

        super().__init__(generate=generate, rotation=rotation, shift=shift,
                         grid_spacing=grid_spacing, extent=extent, shape=shape)

    def _height(self, x_mesh, y_mesh):
        profile = np.zeros_like(x_mesh)
        for idx in range(len(self.frequencies)):
            profile += np.real(self.amptitudes[idx] *
                               np.exp(-1j * self.frequencies[idx] * x_mesh * 2 * np.pi) +
                               self.amptitudes[idx] *
                               np.exp(-1j * self.frequencies[idx] * y_mesh * 2 * np.pi))
        return profile

    def __repr__(self):
        string = self._repr_helper()
        return f'DiscFreqSurface({self.frequencies}, {self.amptitudes}{string})'


class ProbFreqSurface(_AnalyticalSurface):
    """
    ProbFreqSurface(H, qr, qs)
    
    Generates a surface with all possible frequencies in the fft represented 
    with amptitudes described by the probability distrribution given as input.
    Defaults to the parameters used in the contact mechanics challenge
    
    This class only works for square 2D domains
    
    For more infromation on the definations of the input parameters refer to 
    XXXXXX contact mechanics challenge paper
    
    """

    is_descrete = False
    surface_type = 'continuousFreq'

    def __init__(self, h=2, qr=0.05, qs=10,
                 generate: bool = False, grid_spacing: float = None,
                 extent: tuple = None, shape: tuple = None):
        self.h = h
        self.qs = qs
        self.qr = qr
        super().__init__(grid_spacing=grid_spacing, extent=extent, shape=shape, generate=generate)

    def rotate(self, radians: Number):
        raise NotImplementedError("Probabalistic frequency surface cannot be rotated")

    def shift(self, shift: tuple = None):
        if shift is None:
            return
        raise NotImplementedError("Probabalistic frequency surface cannot be shifted")

    def _height(self, x_mesh, y_mesh):
        grid_spacing, extent, shape = check_coords_are_simple(x_mesh, y_mesh)

        qny = np.pi / grid_spacing

        u = np.linspace(0, qny, shape[0])
        u_mesh, v_mesh = np.meshgrid(u, u)
        freqs = np.abs(u_mesh + v_mesh)
        varience = np.zeros(freqs.shape)
        varience[np.logical_and((1 / freqs) > (1 / self.qr), (2 * np.pi / freqs) <= (extent[0]))] = 1
        varience[np.logical_and((1 / freqs) >= (1 / self.qs), (1 / freqs) < (1 / self.qr))] = \
            (freqs[np.logical_and(1 / freqs >= 1 / self.qs, 1 / freqs < 1 / self.qr)] / self.qr) ** (-2 * (1 + self.h))

        fou_trans = np.reshape(np.array([np.random.normal() * var ** 0.5 for var in varience.flatten()]), freqs.shape)
        return np.real(np.fft.ifft2(fou_trans))

    def __repr__(self):
        string = self._repr_helper()
        return f'ProbFreqSurface(h={self.h}, qr={self.qr}, qs={self.qs}{string})'


class HurstFractalSurface(_AnalyticalSurface):
    """
    HurstFractalSurface(q0,q0 amptitude,cut off frequency,Hurst parameter)
    
    generates a hurst fratal surface with frequency components from q0 to 
    cut off frequency in even steps of q0.
    
    amptitudes are given by:
        q0 amptitude**2 *((h**2+k**2)/2)^(1-Hurst parameter)
    where h,k = -N...N 
    where N=cut off frequency/ q0
    phases are randomly generated on construction of the surface object,
    repeted calls to the descretise function will descretise on the same surface
    but repeted calls to this class will generate diferent realisations
    
    Example:
        #create the surface object with the specified fractal prameters
        my_surface=HurstFractalSurface(1,0.1,1000,2)
        #descrtise the surface over a grid 1 unit by 1 unit with a grid_spacing of 0.01
        heights=my_surface.descretise('grid', [[0,1],[0,1]], [0.01,0.01])
        #interpolate over a previously made grid
        heights=my_surface.descretise('interp', X, Y, **kwargs) ** kwargs for remaking interpolator and interpolator options
        #generate new points (e.g. for a custom grid)
        my_surface.descretise('points', X, Y)
        
        A new efficient numerical method for contact mechanics of rough surfaces
        C.Putignano L.Afferrante G.Carbone G.Demelio
    """
    is_descrete = False
    surface_type = "hurstFractal"

    def __init__(self, q0, q0_amp, q_cut_off, hurst, generate: bool = False, grid_spacing: float = None,
                 extent: tuple = None, shape: tuple = None):
        self.input_params = (q0, q0_amp, q_cut_off, hurst)
        n = int(round(q_cut_off / q0))
        h, k = range(-1 * n, n + 1), range(-1 * n, n + 1)
        h_mesh, k_mesh = np.meshgrid(h, k)
        h_mesh[n, n] = 1
        mm2 = q0_amp ** 2 * ((h_mesh ** 2 + k_mesh ** 2) / 2) ** (1 - hurst)
        mm2[n, n] = 0
        pha = 2 * np.pi * np.random.rand(mm2.shape[0], mm2.shape[1])

        mean_mags2 = np.zeros((2 * n + 1, 2 * n + 1))
        phases = np.zeros_like(mean_mags2)

        mean_mags2[:][n:] = mm2[:][n:]
        mean_mags2[:][0:n + 1] = np.flipud(mm2[:][n:])
        self.mean_mags = np.sqrt(mean_mags2).flatten()

        phases[:][n:] = pha[:][n:]
        phases[:][0:n + 1] = np.pi * 2 - np.fliplr(np.flipud(pha[:][n:]))
        phases[n, 0:n] = np.pi * 2 - np.flip(phases[n, n + 1:])
        # next line added
        phases = 2 * np.pi * np.random.rand(phases.shape[0], phases.shape[1])
        self.phases = phases.flatten()
        self.mags = self.mean_mags * np.cos(self.phases) + 1j * self.mean_mags * np.sin(self.phases)
        k_mesh = np.transpose(h_mesh)
        self.qkh = np.transpose(np.array([q0 * h_mesh.flatten(), q0 * k_mesh.flatten()]))
        super().__init__(grid_spacing=grid_spacing, extent=extent, shape=shape, generate=generate)

    def _height(self, x_mesh, y_mesh):
        input_shape = x_mesh.shape

        coords = np.array([x_mesh.flatten(), y_mesh.flatten()])

        z = np.zeros_like(x_mesh.flatten())
        for idx in range(len(self.qkh)):
            z += np.real(self.mags[idx] * np.exp(-1j * np.dot(self.qkh[idx], coords) * 2 * np.pi))

        return np.reshape(z, input_shape)

    def __repr__(self):
        string = self._repr_helper()
        input_param_string = ', '.join(self.input_params)
        return f'HurstFractalSurface({input_param_string}{string})'

    def rotate(self, radians: Number):
        raise NotImplementedError("Hurst fractal surface cannot be rotated")

    def shift(self, shift: tuple = None):
        if shift is None:
            return
        raise NotImplementedError("Hurst fractal surface cannot be shifted")


def check_coords_are_simple(x_mesh, y_mesh):
    """
    Checks that the coordinates are of the type np.meshgrid(np.arrange(0, end, step), np.arrange(0, end, step))

    Parameters
    ----------
    x_mesh: np.ndarray
    y_mesh: np.ndarray

    Returns
    -------
    grid_spacing, extent, shape
    """
    x_mesh_check, y_mesh_check = np.meshgrid(x_mesh[0, :], x_mesh[0, :])

    difference = np.diff(x_mesh[0, :])
    if not np.allclose(difference, difference[0]):
        raise ValueError('x and y points must be evenly spaced and sorted')

    if not x_mesh[0, 0] == 0:
        raise ValueError('x and y points must start at 0')

    if not x_mesh_check == x_mesh and y_mesh_check == y_mesh:
        raise ValueError("For descretising a Probabistic frequency surface the x and y coordinates should form"
                         " an evenly spaced grid aligned with the axes")

    extent = (x_mesh[0, -1], x_mesh[0, -1])
    grid_spacing = difference[0]
    shape = [ex / grid_spacing + 1 for ex in extent]
    return grid_spacing, extent, shape
