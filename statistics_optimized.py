
from dataclasses import dataclass, field
from typing import List, Dict
import numpy as np

from models import Passenger, PassengerState, ElevatorSnapshot


@dataclass
class StatisticsOptimized:
    """
    优化版统计模块：增加以下指标
    
    - 同组负载不平衡度
    - 任务重分配次�?    - 批量停靠比例
    - 预测命中次数
    """
    arrivals: List[Passenger] = field(default_factory=list)
    completed: List[Passenger] = field(default_factory=list)
    abandoned: List[Passenger] = field(default_factory=list)
    boarding_times: List[float] = field(default_factory=list)
    alighting_times: List[float] = field(default_factory=list)
    elevator_snapshots: List[List[ElevatorSnapshot]] = field(default_factory=list)
    
    # 优化特性统�?    reassign_count: int = 0
    batch_stop_count: int = 0
    total_stop_count: int = 0
    prediction_hits: int = 0
    eta_used_count: int = 0

    def record_arrival(self, passenger: Passenger):
        self.arrivals.append(passenger)

    def record_boarding(self, passenger: Passenger):
        self.boarding_times.append(passenger.board_time)

    def record_alighting(self, passenger: Passenger):
        self.alighting_times.append(passenger.alight_time)
        if passenger.alight_time is not None:
            passenger.state = PassengerState.DONE
            self.completed.append(passenger)

    def record_abandoned(self, passenger: Passenger):
        self.abandoned.append(passenger)

    def record_snapshot(self, snapshots: List[ElevatorSnapshot]):
        self.elevator_snapshots.append(snapshots)
    
    def record_reassign(self):
        self.reassign_count += 1
    
    def record_batch_stop(self):
        self.batch_stop_count += 1
    
    def record_stop(self):
        self.total_stop_count += 1
    
    def record_prediction_hit(self):
        self.prediction_hits += 1
    
    def record_eta_use(self):
        self.eta_used_count += 1

    @property
    def total_passengers(self) -> int:
        return len(self.arrivals)

    @property
    def completed_passengers(self) -> int:
        return len(self.completed)

    @property
    def abandoned_passengers(self) -> int:
        return len(self.abandoned)

    def get_avg_wait_time(self) -> float:
        if not self.completed:
            return 0.0
        wait_times = [p.wait_time for p in self.completed if p.wait_time is not None]
        return np.mean(wait_times) if wait_times else 0.0

    def get_max_wait_time(self) -> float:
        if not self.completed:
            return 0.0
        wait_times = [p.wait_time for p in self.completed if p.wait_time is not None]
        return np.max(wait_times) if wait_times else 0.0

    def get_avg_trip_time(self) -> float:
        if not self.completed:
            return 0.0
        trip_times = [p.trip_time for p in self.completed if p.trip_time is not None]
        return np.mean(trip_times) if trip_times else 0.0

    def get_avg_total_time(self) -> float:
        if not self.completed:
            return 0.0
        total_times = [p.total_time for p in self.completed if p.total_time is not None]
        return np.mean(total_times) if total_times else 0.0

    def get_long_wait_ratio(self, threshold: float = 120) -> float:
        if not self.completed:
            return 0.0
        long_waits = [p for p in self.completed if p.wait_time and p.wait_time > threshold]
        return len(long_waits) / len(self.completed)

    def get_abandon_rate(self) -> float:
        total = len(self.completed) + len(self.abandoned)
        if total == 0:
            return 0.0
        return len(self.abandoned) / total

    def get_throughput(self, simulation_time: float) -> float:
        if simulation_time == 0:
            return 0.0
        return len(self.completed) / simulation_time

    def get_elevator_utilization(self, simulation_time: float) -> Dict[int, float]:
        if not self.elevator_snapshots or simulation_time == 0:
            return {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}

        utilizations = {}
        for elevator_id in [1, 2, 3, 4]:
            moving_count = 0
            total_count = 0
            for snapshot_list in self.elevator_snapshots:
                for snapshot in snapshot_list:
                    if snapshot.id == elevator_id:
                        if snapshot.state.value == "MOVING":
                            moving_count += 1
                        total_count += 1
                        break
            utilizations[elevator_id] = moving_count / total_count if total_count > 0 else 0.0

        return utilizations
    
    def get_group_load_imbalance(self, simulation_time: float) -> Dict[str, float]:
        """
        计算同组电梯负载不平衡度
        
        Returns:
            奇数组和偶数组的负载不平衡度
        """
        util = self.get_elevator_utilization(simulation_time)
        
        result = {}
        
        # 奇数�?(1, 2)
        odd_loads = [util.get(1, 0.0), util.get(2, 0.0)]
        result['odd'] = abs(odd_loads[0] - odd_loads[1])
        
        # 偶数�?(3, 4)
        even_loads = [util.get(3, 0.0), util.get(4, 0.0)]
        result['even'] = abs(even_loads[0] - even_loads[1])
        
        return result
    
    def get_batch_stop_ratio(self) -> float:
        """计算批量停靠比例"""
        if self.total_stop_count == 0:
            return 0.0
        return self.batch_stop_count / self.total_stop_count

    def print_summary(self, simulation_time: float):
        print("\n" + "=" * 60)
        print("【优化版】电梯仿真统计结�?)
        print("=" * 60)
        print(f"仿真时间: {simulation_time:.1f} �?)
        print("-" * 60)
        print(f"总乘客数: {self.total_passengers}")
        print(f"完成乘客: {self.completed_passengers}")
        print(f"放弃乘客: {self.abandoned_passengers}")
        print("-" * 60)
        print(f"平均等待时间: {self.get_avg_wait_time():.1f} �?)
        print(f"最大等待时�? {self.get_max_wait_time():.1f} �?)
        print(f"平均行程时间: {self.get_avg_trip_time():.1f} �?)
        print(f"平均总时�? {self.get_avg_total_time():.1f} �?)
        print("-" * 60)
        print(f"长等�?>2min)比例: {self.get_long_wait_ratio():.1%}")
        print(f"放弃�? {self.get_abandon_rate():.1%}")
        print(f"吞吐�? {self.get_throughput(simulation_time):.4f} �?�?)
        print("-" * 60)

        util = self.get_elevator_utilization(simulation_time)
        for eid, u in util.items():
            print(f"电梯{eid}利用�? {u:.1%}")
        
        print("-" * 60)
        
        # 新增指标
        imbalance = self.get_group_load_imbalance(simulation_time)
        print(f"奇数组负载不平衡�? {imbalance['odd']:.1%}")
        print(f"偶数组负载不平衡�? {imbalance['even']:.1%}")
        print(f"任务重分配次�? {self.reassign_count}")
        print(f"批量停靠比例: {self.get_batch_stop_ratio():.1%}")
        print(f"ETA使用次数: {self.eta_used_count}")
        print("=" * 60)
