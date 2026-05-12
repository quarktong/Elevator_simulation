import simpy
from typing import Optional, List, Dict
from dataclasses import dataclass, field

from config import SimConfig, TimePeriod
from models import Passenger, HallCall, CarCall, Direction, ElevatorState, ElevatorSnapshot, PassengerState

@dataclass
class Elevator:
    elevator_id: int
    is_odd_group: bool
    config: SimConfig
    env: simpy.Environment
    call_store: simpy.Store
    statistics: 'Statistics'

    position: float = 1.0
    direction: Direction = Direction.IDLE
    state: ElevatorState = ElevatorState.IDLE
    passengers: List[Passenger] = field(default_factory=list)
    car_calls: set = field(default_factory=set)
    hall_calls: Dict[int, HallCall] = field(default_factory=dict)

    def __post_init__(self):
        self.served_floors = self.config.building.get_service_floors(self.is_odd_group)
        self.capacity = self.config.building.capacity

    @property
    def is_full(self) -> bool:
        return len(self.passengers) >= self.capacity

    @property
    def is_idle(self) -> bool:
        return self.state == ElevatorState.IDLE

    def add_car_call(self, floor: int, passenger: Passenger):
        self.car_calls.add(floor)
        passenger.state = PassengerState.BOARDING

    def assign_call(self, call: HallCall):
        self.hall_calls[call.floor] = call
        call.assign_to(self.elevator_id)
        self.call_store.put(call)

    def release_call(self, floor: int):
        if floor in self.hall_calls:
            del self.hall_calls[floor]

    def _get_next_stop(self) -> Optional[int]:
        all_calls = set(self.car_calls)
        for call in self.hall_calls.values():
            if not call.completed:
                all_calls.add(call.floor)

        if not all_calls:
            return None

        current = round(self.position)

        if self.direction == Direction.UP:
            candidates = [f for f in all_calls if f >= current and f in self.served_floors]
            if candidates:
                return min(candidates)
            candidates = [f for f in all_calls if f < current and f in self.served_floors]
            if candidates:
                return max(candidates)
        elif self.direction == Direction.DOWN:
            candidates = [f for f in all_calls if f <= current and f in self.served_floors]
            if candidates:
                return max(candidates)
            candidates = [f for f in all_calls if f > current and f in self.served_floors]
            if candidates:
                return min(candidates)
        else:
            if current in all_calls:
                return current
            closer_up = min([f for f in all_calls if f >= current], default=None)
            closer_down = max([f for f in all_calls if f <= current], default=None)
            if closer_up is None:
                return closer_down
            if closer_down is None:
                return closer_up
            return closer_up if abs(closer_up - current) < abs(closer_down - current) else closer_down

        return None

    def _should_stop_at(self, floor: int) -> bool:
        if floor not in self.served_floors:
            return False

        if floor in self.car_calls:
            return True

        if floor in self.hall_calls:
            call = self.hall_calls[floor]
            if not call.completed:
                if self.is_full:
                    return False
                if self.direction == Direction.IDLE:
                    return True
                return call.direction == self.direction

        return False

    def _set_direction_to_target(self, target: Optional[int]):
        if target is None:
            self.direction = Direction.IDLE
        elif target > round(self.position):
            self.direction = Direction.UP
        elif target < round(self.position):
            self.direction = Direction.DOWN
        else:
            self.direction = Direction.IDLE

    def _handle_door_open(self, floor: int):
        self.state = ElevatorState.DOOR_OPEN
        open_time = self.config.time.get_open_time(floor)
        yield self.env.timeout(open_time)

        for p in self.passengers[:]:
            if p.destination == floor:
                p.alight_time = self.env.now
                p.state = PassengerState.ALIGHTING
                self.passengers.remove(p)
                self.car_calls.discard(floor)
                self.statistics.record_alighting(p)

        passengers_to_board = []
        for call_floor, call in list(self.hall_calls.items()):
            if call_floor == floor and not call.completed:
                if not self.is_full:
                    for p in call.passengers[:]:
                        if p.origin == floor and len(self.passengers) < self.capacity:
                            passengers_to_board.append((p, call))

        for p, call in passengers_to_board:
            p.board_time = self.env.now
            p.state = PassengerState.RIDING
            self.passengers.append(p)
            self.car_calls.add(p.destination)
            call.passengers.remove(p)
            if not call.passengers:
                call.completed = True
                del self.hall_calls[call_floor]

        yield self.env.timeout(self.config.time.t_close)
        self.state = ElevatorState.IDLE

    def _move_to_floor(self, target: int):
        while round(self.position) != target:
            if self.direction == Direction.UP:
                self.position += 1
                yield self.env.timeout(self.config.time.t_travel)
            elif self.direction == Direction.DOWN:
                self.position -= 1
                yield self.env.timeout(self.config.time.t_travel)

    def run(self):
        while True:
            next_stop = self._get_next_stop()

            if next_stop is None:
                self.state = ElevatorState.IDLE
                self.direction = Direction.IDLE
                yield self.call_store.get()
                continue

            self._set_direction_to_target(next_stop)
            self.state = ElevatorState.MOVING

            yield from self._move_to_floor(next_stop)

            if self._should_stop_at(round(self.position)):
                yield from self._handle_door_open(round(self.position))

            next_stop = self._get_next_stop()
            if next_stop is not None:
                self._set_direction_to_target(next_stop)
            else:
                self.direction = Direction.IDLE

    def get_snapshot(self) -> ElevatorSnapshot:
        return ElevatorSnapshot(
            id=self.elevator_id,
            position=self.position,
            direction=self.direction,
            n_passengers=len(self.passengers),
            state=self.state,
            car_calls=frozenset(self.car_calls),
            hall_calls=frozenset(self.hall_calls.keys())
        )
