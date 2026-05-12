import simpy
import numpy as np
from typing import Optional

from config import SimConfig, TimePeriod
from models import Passenger, PassengerState
from dispatcher import Dispatcher

class PassengerGenerator:
    def __init__(self, env: simpy.Environment, config: SimConfig, dispatcher: Dispatcher, statistics: 'Statistics'):
        self.env = env
        self.config = config
        self.dispatcher = dispatcher
        self.statistics = statistics
        self.rng = np.random.default_rng(config.seed)

    def run(self):
        passenger_id = 0
        while True:
            current_time = self.env.now
            period = self.config.get_period(current_time)
            lam = self.config.get_lambda(current_time)

            interval = self.rng.exponential(1.0 / lam) if lam > 0 else float('inf')
            yield self.env.timeout(interval)

            passenger = self._generate_passenger(period)
            if passenger is None:
                continue

            passenger_id += 1
            passenger.id = passenger_id

            self.statistics.record_arrival(passenger)

            if self.dispatcher.dispatch(passenger):
                pass
            else:
                self._handle_no_elevator_available(passenger)

    def _generate_passenger(self, period: TimePeriod) -> Optional[Passenger]:
        origin, destination = self._sample_origin_destination(period)
        if origin is None or destination is None:
            return None

        passenger = Passenger(
            id=0,
            origin=origin,
            destination=destination,
            request_time=self.env.now,
            state=PassengerState.ARRIVED
        )

        return passenger

    def _sample_origin_destination(self, period: TimePeriod):
        current_time = self.env.now
        use_prob = self.rng.random()

        if period == TimePeriod.MORNING_PEAK:
            return self._sample_morning_peak(use_prob)
        elif period == TimePeriod.NOON_PEAK:
            return self._sample_noon_peak()
        else:
            return self._sample_off_peak()

    def _sample_morning_peak(self, use_prob: float) -> tuple:
        if use_prob > 0.27:
            return None, None

        if use_prob <= 0:
            floor_range = (1, 4)
        elif use_prob <= 0.10 * 2 / 17:
            floor_range = (5, 6)
        elif use_prob <= (0.10 * 2 + 0.30 * 4) / 17:
            floor_range = (7, 10)
        else:
            floor_range = (11, 17)

        origin = self.rng.integers(floor_range[0], floor_range[1] + 1)
        destination = 1
        return origin, destination

    def _sample_noon_peak(self) -> tuple:
        origin = 1
        high_floors = list(range(10, 18))
        if self.rng.random() < 0.3:
            high_floors = list(range(5, 10))
        destination = self.rng.choice(high_floors)
        return origin, destination

    def _sample_off_peak(self) -> tuple:
        origin = self.rng.integers(1, self.config.building.n_floors + 1)
        destination = self.rng.integers(1, self.config.building.n_floors + 1)
        while destination == origin:
            destination = self.rng.integers(1, self.config.building.n_floors + 1)
        return origin, destination

    def _handle_no_elevator_available(self, passenger: Passenger):
        passenger.state = PassengerState.ABANDONED
        self.statistics.record_abandoned(passenger)
