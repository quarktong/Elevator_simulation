from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List

class PassengerState(Enum):
    ARRIVED = "ARRIVED"
    WAITING = "WAITING"
    BOARDING = "BOARDING"
    RIDING = "RIDING"
    ALIGHTING = "ALIGHTING"
    DONE = "DONE"
    ABANDONED = "ABANDONED"

class Direction(Enum):
    UP = 1
    DOWN = -1
    IDLE = 0

class ElevatorState(Enum):
    IDLE = "IDLE"
    MOVING = "MOVING"
    DOOR_OPEN = "DOOR_OPEN"

@dataclass
class Passenger:
    id: int
    origin: int
    destination: int
    request_time: float
    state: PassengerState = PassengerState.ARRIVED
    board_time: Optional[float] = None
    alight_time: Optional[float] = None
    is_odd_group: bool = False

    @property
    def wait_time(self) -> Optional[float]:
        if self.board_time is not None:
            return self.board_time - self.request_time
        return None

    @property
    def trip_time(self) -> Optional[float]:
        if self.board_time is not None and self.alight_time is not None:
            return self.alight_time - self.board_time
        return None

    @property
    def total_time(self) -> Optional[float]:
        if self.alight_time is not None:
            return self.alight_time - self.request_time
        return None

    @property
    def direction(self) -> Direction:
        return Direction.DOWN if self.origin > self.destination else Direction.UP

@dataclass
class HallCall:
    floor: int
    direction: Direction
    time: float
    assigned_elevator: Optional[int] = None
    passengers: List[Passenger] = field(default_factory=list)
    completed: bool = False

    def assign_to(self, elevator_id: int):
        self.assigned_elevator = elevator_id

    def is_assigned(self) -> bool:
        return self.assigned_elevator is not None

@dataclass
class ElevatorSnapshot:
    id: int
    position: float
    direction: Direction
    n_passengers: int
    state: ElevatorState
    car_calls: frozenset = field(default_factory=frozenset)
    hall_calls: frozenset = field(default_factory=frozenset)

@dataclass
class CarCall:
    floor: int
    time: float
    passenger_id: int
