from dataclasses import dataclass
from enum import Enum
from typing import Optional

class TimePeriod(Enum):
    MORNING_PEAK = "morning"    # 早高峰 07:40-08:00
    NOON_PEAK = "noon"          # 午间返程 12:05-12:20
    OFF_PEAK = "off_peak"       # 非高峰

@dataclass
class BuildingConfig:
    n_floors: int = 17
    n_total: int = 1790
    n_elevators: int = 4
    capacity: int = 12
    odd_floors: frozenset = frozenset({1, 3, 5, 7, 9, 11, 13, 15, 17})
    even_floors: frozenset = frozenset({1, 2, 4, 6, 8, 10, 12, 14, 16})

    def get_service_floors(self, is_odd_group: bool) -> frozenset:
        return self.odd_floors if is_odd_group else self.even_floors

    def is_valid_floor(self, floor: int) -> bool:
        return 1 <= floor <= self.n_floors

@dataclass
class TimeConfig:
    t_travel: float = 2.31
    t_open_1: float = 10.0
    t_open: float = 6.8
    t_close: float = 4.0
    t_board: float = 1.0
    t_alight: float = 0.8

    def get_open_time(self, floor: int) -> float:
        return self.t_open_1 if floor == 1 else self.t_open

    def get_stop_time(self, floor: int, n_board: int, n_alight: int) -> float:
        return self.get_open_time(floor) + n_board * self.t_board + n_alight * self.t_alight + self.t_close

@dataclass
class TrafficConfig:
    lambda_morning: float = 0.50
    lambda_noon: float = 0.66
    lambda_off_peak: float = 0.05

    t_morning_start: float = 0
    t_morning_end: float = 1200
    t_noon_start: float = 2000
    t_noon_end: float = 2900

    use_prob_5_6: float = 0.10
    use_prob_7_10: float = 0.30
    use_prob_11_17: float = 0.50
    use_prob_return_5_9: float = 0.30
    use_prob_return_10_17: float = 1.0

    t_max_wait: float = 300

    def get_period(self, sim_time: float) -> TimePeriod:
        if self.t_morning_start <= sim_time < self.t_morning_end:
            return TimePeriod.MORNING_PEAK
        elif self.t_noon_start <= sim_time < self.t_noon_end:
            return TimePeriod.NOON_PEAK
        else:
            return TimePeriod.OFF_PEAK

    def get_lambda(self, period: TimePeriod) -> float:
        if period == TimePeriod.MORNING_PEAK:
            return self.lambda_morning
        elif period == TimePeriod.NOON_PEAK:
            return self.lambda_noon
        else:
            return self.lambda_off_peak

    def get_use_prob(self, floor: int, period: TimePeriod) -> float:
        if period == TimePeriod.MORNING_PEAK:
            if floor <= 4:
                return 0.0
            elif 5 <= floor <= 6:
                return self.use_prob_5_6
            elif 7 <= floor <= 10:
                return self.use_prob_7_10
            else:
                return self.use_prob_11_17
        elif period == TimePeriod.NOON_PEAK:
            if floor == 1:
                return 1.0
            elif 5 <= floor <= 9:
                return self.use_prob_return_5_9
            elif 10 <= floor <= 17:
                return self.use_prob_return_10_17
            else:
                return 0.0
        else:
            return 0.05

@dataclass
class SimConfig:
    building: BuildingConfig
    time: TimeConfig
    traffic: TrafficConfig
    sim_start: float = 0
    sim_end: float = 3600
    seed: Optional[int] = 42

    @classmethod
    def default(cls) -> 'SimConfig':
        return cls(
            building=BuildingConfig(),
            time=TimeConfig(),
            traffic=TrafficConfig()
        )

    def get_period(self, sim_time: float) -> TimePeriod:
        return self.traffic.get_period(sim_time)

    def get_lambda(self, sim_time: float) -> float:
        return self.traffic.get_lambda(self.get_period(sim_time))

    def get_use_prob(self, floor: int, sim_time: float) -> float:
        return self.traffic.get_use_prob(floor, self.get_period(sim_time))
