import numpy as np
import slippy
from itertools import product
from collections import defaultdict
from slippy.core import _SubModelABC, plan_multi_convolve, _IMMaterial
from typing import Sequence, Union

__all__ = ['SubsurfaceStress']


class SubsurfaceStress(_SubModelABC):
    """A sub model for subsurface stresses in influence matrix based materials

    Parameters
    ----------
    z: np.array[float], optional (None)
        The depths of interest in the material, defaults to half the span with the same spacing as the surface
        grid spacing
    surface: int or Sequence[int], optional ((1,2))
        The surfaces for which the stress components are to be calculated
    name: str, optional ('sub_surface_stress')
        The name of the sub model, used for debugging
    load_components: str, optional 'z'
        The components of the surface loads to include in the calculation, eg 'xz' indicates the normal loads ('z') and
        tangential tractions in the x direction will be superimposed. The sub model will require the loads in each of
        these directions to be in the current state when the model is run.
    stress_components: str or Sequence[str], optional ('all', )
        The components of stress to be found. Valid entries are: Cauchy stress tensor components: 'xx', 'yy', 'zz',
        'xy', 'yz', 'xz'. Principal stresses: '1', '2', '3'. Or von misses stress: 'vm'. The model will provide
        the requested components in the state dictionary. Requesting any of the principal stresses or the von mises
        stress will compute the full tensor, however the the tensor components will not be added to the state dict
        unless they are also requested. 'all' will compute all Cauchy stress tensor components, but no other components.
    keep_kernels: bool, optional (True)
         If True the kernels will be cached for faster computation, if False they are deleted and re computed every time
         the sub model is called, this will add time to computations, but reduce memory requirements.
    cuda_convolutions: bool, optional (False)
        If True the computations will be carried out on the GPU (if cupy can be imported), This may result in faster
        computations depending on hardware but kernels and results must be stored on GPU memory.

    Notes
    -----
    Memory requirements for this sub model are large, if stress components are not required for further computations
    it may be faster to compute them after the model has run.

    This model will add values to the state dict: surface_a_y for each surface (a) and stress component (y) (all lower
    case).

    Each value added to the dict will have shape: (len(z), loads.shape) where loads.shape is the shape of the loads
    array.

    This sub model requires the relevent sub surface stress function to be implemented and working for the material.

    Examples
    --------
    The sub model:
    >>>SubsurfaceStress(surface=1, stress_components='svm')
    Will find the Von Mises stress on the master surface in the model (surface 1), this will add the key 'surface_1_svm'
    to the state dict.
    """

    def __init__(self, z: np.array = None, surface: Union[int, Sequence[int]] = (1, 2),
                 name: str = 'sub_surface_stress', periodic_axes: Sequence[bool] = (False, False),
                 load_components: str = 'z', stress_components: Union[str, Sequence[str]] = ('all',),
                 keep_kernels: bool = True, cuda_convolutions: bool = False):
        if isinstance(surface, int):
            surface = (surface,)
        if isinstance(stress_components, str):
            stress_components = (stress_components,)
        for lc in load_components:
            if lc not in 'xz':
                raise ValueError(f"Unrecognised load direction: {lc}, valid directions are: x, z")
        requires = set('loads_' + c for c in load_components)
        valid_stresses = ('xx', 'yy', 'zz', 'xy', 'yz', 'xz', '1', '2', '3', 'vm')
        for sc in stress_components:
            if sc not in valid_stresses:
                raise ValueError(f"Unrecognised stress component: {sc}, valid components are: {valid_stresses}")
        provides = set('surface_' + str(s) + '_' + sc for s, sc in product(surface, stress_components))
        super().__init__(name, requires, provides)
        self.surfaces = surface
        self.load_components = load_components
        self.stress_components = stress_components
        self.keep_kernels = keep_kernels
        self.cuda_convolutions = cuda_convolutions
        self._kernel_cache = {s: {a: dict() for a in stress_components} for s in surface}
        self._cache_span = (0, 0)
        self.z = z
        calc_all = any(s in stress_components for s in ('1', '2', '3', 'vm'))
        self.comps_to_find = ('xx', 'yy', 'zz', 'xy', 'yz', 'xz') if calc_all else stress_components
        self.periodic_axes = periodic_axes

    def solve(self, current_state: dict) -> dict:
        if self.cuda_convolutions:
            xp = slippy.xp
        else:
            xp = np
        example_loads = current_state['loads_' + self.load_components[0]]
        span = example_loads.shape
        out_put_shape = (len(self.z),) + span

        def default_factory():
            return xp.zeros(out_put_shape)

        for surface_num in self.surfaces:
            surface = self.model.__getattribute__('surface_' + str(surface_num))
            material = surface.material
            grid_spacing = [surface.grid_spacing, ] * 2
            assert (isinstance(material, _IMMaterial)), 'Sub surface stress only valid for influence matrix based ' \
                                                        'materials'
            intermediate_results = defaultdict(default_factory)
            for l_comp in self.load_components:
                if self.keep_kernels and span == self._cache_span:
                    conv_funcs = self._kernel_cache[surface_num][l_comp]
                else:
                    args = (span, grid_spacing, self.comps_to_find, self.z, self.cuda_convolutions)
                    if l_comp == 'z':
                        im_comps = material.sss_influence_matrices_normal(*args)
                    elif l_comp == 'x':
                        im_comps = material.sss_influence_matrices_tangential_x(*args)
                    elif l_comp == 'y':
                        im_comps = material.sss_influence_matrices_tangential_y(*args)
                    else:
                        raise ValueError(f"Unrecognised load component requested: {l_comp}")
                    conv_funcs = {key: plan_multi_convolve(example_loads, value, None, self.periodic_axes) for
                                  key, value in im_comps.items()}
                    if self.keep_kernels:
                        self._cache_span = span
                        self._kernel_cache[surface_num][l_comp] = conv_funcs

                for key, conv_func in conv_funcs.items():
                    loads = current_state['loads_' + l_comp]
                    intermediate_results[key] += conv_func(loads)
            # find other stress components
            if 'vm' in self.stress_components:
                intermediate_results['vm'] = xp.sqrt(((intermediate_results['xx'] - intermediate_results['yy']) ** 2 +
                                                      (intermediate_results['yy'] - intermediate_results['zz']) ** 2 +
                                                      (intermediate_results['zz'] - intermediate_results['xx']) ** 2 +
                                                      6 * (intermediate_results['xy'] ** 2 +
                                                           intermediate_results['yz'] ** 2 +
                                                           intermediate_results['xz'] ** 2)) / 2)
            if '1' in self.stress_components or '2' in self.stress_components or '3' in self.stress_components:
                b = intermediate_results['xx'] + intermediate_results['yy'] + intermediate_results['zz']
                c = (intermediate_results['xx'] * intermediate_results['yy'] +
                     intermediate_results['yy'] * intermediate_results['zz'] +
                     intermediate_results['xx'] * intermediate_results['zz'] -
                     intermediate_results['xy'] ** 2 - intermediate_results['xz'] ** 2 - intermediate_results[
                         'yz'] ** 2)
                d = (intermediate_results['xx'] * intermediate_results['yy'] * intermediate_results['zz'] +
                     2 * intermediate_results['xy'] * intermediate_results['xz'] * intermediate_results['yz'] -
                     intermediate_results['xx'] * intermediate_results['yz'] ** 2 -
                     intermediate_results['yy'] * intermediate_results['xz'] ** 2 -
                     intermediate_results['zz'] * intermediate_results['xy'] ** 2)

                p = c - (b ** 2) / 3
                q = ((2 / 27) * b ** 3 - (1 / 3) * b * c + d)
                del c
                del d
                for key in intermediate_results:
                    if key not in self.stress_components:
                        del intermediate_results[key]
                principals = xp.zeros((3,) + out_put_shape)
                for i in range(3):
                    principals[i] = 2 * xp.sqrt((-1 / 3) * p) * xp.cos(
                        1 / 3 * xp.arccos(3 * q / (2 * p) * xp.sqrt(-3 / p)) - 2 * xp.pi * i / 3) - b / 3
                    #                ^ real roots from cubic equation for depressed cubic                          ^
                    #                                                                               change of variable
                intermediate_results['1'] = xp.max(principals, 0)
                intermediate_results['3'] = xp.min(principals, 0)
                intermediate_results['2'] = b - intermediate_results['1'] - intermediate_results['3']

            for key in self.stress_components:
                current_state['surface_' + str(surface_num) + '_' + key] = intermediate_results[key]
        return current_state
