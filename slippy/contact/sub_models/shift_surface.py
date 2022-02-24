from ._TransientSubModelABC import _TransientSubModelABC  # noqa: E402
from collections.abc import Sequence

__all__ = ['UpdateShiftRollingSurface']


class UpdateShiftRollingSurface(_TransientSubModelABC):
    """
    Shifts a RollingSurface at a set speed
    """

    def __init__(self, name: str, surface_to_roll: int, speed_x: float = 0.0, speed_y: float = 0.0,
                 interpolation_mode='linear'):
        super().__init__(name, set("time_step"), set(), (speed_x, speed_y),
                         (f'{name}_shift_speed_x', f'{name}_shift_speed_y'), interpolation_mode)
        if surface_to_roll not in {1, 2}:
            raise ValueError(f"Surface to roll should be either 1 or 2, got {surface_to_roll}")
        self._surface_to_roll = surface_to_roll

    def _solve(self, current_state: dict, **kwargs) -> dict:

        distance_x = kwargs[f'{self.name}_shift_speed_x'] * current_state['time_step']
        distance_y = kwargs[f'{self.name}_shift_speed_y'] * current_state['time_step']

        if self._surface_to_roll == 1:
            self.model.surface_1.shift(distance_y, distance_x)
        return current_state
