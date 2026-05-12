from typing import List, Optional, Dict
from dataclasses import dataclass

from config import SimConfig
from models import Passenger, HallCall, Direction, ElevatorState

@dataclass
class Dispatcher:
    config: SimConfig
    elevators: List['Elevator']

    def dispatch(self, passenger: Passenger) -> Optional[int]:
        group = self._select_group(passenger)
        if not group:
            return None

        best_elevator = self._select_best_elevator(group, passenger)
        if best_elevator is None:
            return None

        call = HallCall(
            floor=passenger.origin,
            direction=passenger.direction,
            time=passenger.request_time,
            passengers=[passenger]
        )

        passenger.state = passenger.state.WAITING
        best_elevator.assign_call(call)
        return best_elevator.elevator_id

    def _select_group(self, passenger: Passenger) -> List['Elevator']:
        is_odd = passenger.destination % 2 == 1 if passenger.origin == 1 else passenger.origin % 2 == 1
        passenger.is_odd_group = is_odd
        return [e for e in self.elevators if e.is_odd_group == is_odd]

    def _select_best_elevator(self, group: List['Elevator'], passenger: Passenger) -> Optional['Elevator']:
        idle_elevators = [e for e in group if e.is_idle]
        if idle_elevators:
            return min(idle_elevators, key=lambda e: abs(e.position - passenger.origin))

        same_direction = [e for e in group if e.direction == passenger.direction]
        if same_direction:
            return min(same_direction, key=lambda e: self._calc_cost(e, passenger))

        return min(group, key=lambda e: self._calc_cost(e, passenger))

    def _calc_cost(self, elevator: 'Elevator', passenger: Passenger) -> float:
        distance = abs(elevator.position - passenger.origin)

        if elevator.direction == Direction.IDLE:
            return distance

        if elevator.direction == passenger.direction:
            if (passenger.direction == Direction.UP and passenger.origin >= round(elevator.position)) or \
               (passenger.direction == Direction.DOWN and passenger.origin <= round(elevator.position)):
                return distance
            else:
                return (self.config.building.n_floors - elevator.position) + \
                       (self.config.building.n_floors - passenger.origin)

        return distance + self.config.building.n_floors

    def release_elevator_call(self, elevator_id: int, floor: int):
        for e in self.elevators:
            if e.elevator_id == elevator_id:
                e.release_call(floor)
                break
