import simpy
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
from config import SimConfig, BuildingConfig, TimeConfig, TrafficConfig
from models import Passenger, HallCall, Direction, ElevatorState, PassengerState
from typing import List, Optional

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

class QuickElevator:
    """快速电梯类"""
    def __init__(self, elevator_id: int, served_floors: set, config: SimConfig, 
                 env: simpy.Environment, call_store: simpy.Store, statistics: 'QuickStats'):
        self.elevator_id = elevator_id
        self.served_floors = served_floors
        self.config = config
        self.env = env
        self.call_store = call_store
        self.statistics = statistics
        
        self.position = 1.0
        self.direction = Direction.IDLE
        self.state = ElevatorState.IDLE
        self.passengers = []
        self.car_calls = set()
        self.hall_calls = {}
        self.capacity = config.building.capacity
    
    @property
    def is_full(self):
        return len(self.passengers) >= self.capacity
    
    def assign_call(self, call: HallCall):
        if call.floor in self.served_floors:
            self.hall_calls[call.floor] = call
            call.assign_to(self.elevator_id)
            self.call_store.put(call)
    
    def _get_next_stop(self):
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
    
    def _should_stop_at(self, floor):
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
    
    def _set_direction_to_target(self, target):
        if target is None:
            self.direction = Direction.IDLE
        elif target > round(self.position):
            self.direction = Direction.UP
        elif target < round(self.position):
            self.direction = Direction.DOWN
        else:
            self.direction = Direction.IDLE
    
    def _handle_door_open(self, floor):
        self.state = ElevatorState.DOOR_OPEN
        yield self.env.timeout(0.5)
        
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
        
        yield self.env.timeout(0.3)
        self.state = ElevatorState.IDLE
    
    def _move_to_floor(self, target):
        while round(self.position) != target:
            if self.direction == Direction.UP:
                self.position += 1
                yield self.env.timeout(0.1)
            elif self.direction == Direction.DOWN:
                self.position -= 1
                yield self.env.timeout(0.1)
    
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

class QuickDispatcher:
    def __init__(self, config: SimConfig, elevators: List[QuickElevator]):
        self.config = config
        self.elevators = elevators
    
    def dispatch(self, passenger: Passenger) -> Optional[int]:
        available = [e for e in self.elevators if passenger.origin in e.served_floors]
        if not available:
            return None
        
        idle = [e for e in available if e.is_full == False]
        if idle:
            best = min(idle, key=lambda e: abs(e.position - passenger.origin))
            call = HallCall(
                floor=passenger.origin,
                direction=passenger.direction,
                time=passenger.request_time,
                passengers=[passenger]
            )
            passenger.state = PassengerState.WAITING
            best.assign_call(call)
            return best.elevator_id
        
        best = min(available, key=lambda e: abs(e.position - passenger.origin))
        call = HallCall(
            floor=passenger.origin,
            direction=passenger.direction,
            time=passenger.request_time,
            passengers=[passenger]
        )
        passenger.state = PassengerState.WAITING
        best.assign_call(call)
        return best.elevator_id

class QuickStats:
    def __init__(self):
        self.completed_passengers = []
        self.arrived_passengers = []
    
    def record_arrival(self, passenger: Passenger):
        self.arrived_passengers.append(passenger)
    
    def record_alighting(self, passenger: Passenger):
        passenger.state = PassengerState.DONE
        self.completed_passengers.append(passenger)

class QuickPassengerGenerator:
    def __init__(self, env: simpy.Environment, config: SimConfig, 
                 dispatcher: QuickDispatcher, statistics: QuickStats, rng: np.random.Generator):
        self.env = env
        self.config = config
        self.dispatcher = dispatcher
        self.statistics = statistics
        self.rng = rng
        self.passenger_id = 0
    
    def run(self):
        while True:
            lam = 0.15
            interval = self.rng.exponential(1.0 / lam) if lam > 0 else float('inf')
            yield self.env.timeout(interval)
            
            origin = self.rng.integers(1, self.config.building.n_floors + 1)
            destination = self.rng.integers(1, self.config.building.n_floors + 1)
            while destination == origin:
                destination = self.rng.integers(1, self.config.building.n_floors + 1)
            
            passenger = Passenger(
                id=self.passenger_id,
                origin=origin,
                destination=destination,
                request_time=self.env.now,
                state=PassengerState.ARRIVED
            )
            self.passenger_id += 1
            
            self.statistics.record_arrival(passenger)
            self.dispatcher.dispatch(passenger)

def create_floor_groups(strategy: str):
    if strategy == 'odd_even':
        return [
            {1,3,5,7,9,11,13,15,17},
            {1,3,5,7,9,11,13,15,17},
            {1,2,4,6,8,10,12,14,16},
            {1,2,4,6,8,10,12,14,16}
        ]
    elif strategy == 'long_chain':
        return [
            {1,2,3,4,5,6,7,8,9},
            {1,7,8,9,10,11,12,13,14,15},
            {1,11,12,13,14,15,16,17},
            {1,2,3,4,5,13,14,15,16,17}
        ]
    elif strategy == 'no_group':
        all_floors = set(range(1, 18))
        return [all_floors, all_floors, all_floors, all_floors]

def run_quick_simulation(strategy: str, seed: int, sim_time: int = 300):
    building_config = BuildingConfig(n_floors=17, n_elevators=4, capacity=12)
    time_config = TimeConfig()
    traffic_config = TrafficConfig(lambda_morning=0.50, lambda_noon=0.66)
    config = SimConfig(
        building=building_config,
        time=time_config,
        traffic=traffic_config,
        sim_end=sim_time,
        seed=seed
    )
    
    rng = np.random.default_rng(seed)
    env = simpy.Environment()
    stats = QuickStats()
    
    floor_groups = create_floor_groups(strategy)
    call_stores = [simpy.Store(env) for _ in range(4)]
    
    elevators = []
    for i in range(4):
        elevator = QuickElevator(
            elevator_id=i+1,
            served_floors=floor_groups[i],
            config=config,
            env=env,
            call_store=call_stores[i],
            statistics=stats
        )
        elevators.append(elevator)
        env.process(elevator.run())
    
    dispatcher = QuickDispatcher(config=config, elevators=elevators)
    generator = QuickPassengerGenerator(env, config, dispatcher, stats, rng)
    env.process(generator.run())
    
    env.run(until=sim_time)
    
    wait_times = []
    for p in stats.completed_passengers:
        if p.wait_time is not None:
            wait_times.append(p.wait_time)
    
    avg_wait = np.mean(wait_times) if wait_times else 0
    throughput = len(wait_times) / sim_time if wait_times else 0
    
    return {
        'avg_wait': avg_wait,
        'throughput': throughput,
        'total_passengers': len(wait_times)
    }

def main():
    print("=" * 80)
    print("电梯分组策略 - 快速SimPy仿真预览 (10次/策略)")
    print("=" * 80)
    print(f"开始时间: {datetime.now()}")
    print("=" * 80)
    
    strategies = ['odd_even', 'long_chain', 'no_group']
    labels = ['奇偶分组', '长链结构', '不分组']
    all_results = {}
    
    for strategy, label in zip(strategies, labels):
        print(f"\n运行 {label}...")
        wait_results = []
        throughput_results = []
        passenger_results = []
        
        for i in range(10):
            res = run_quick_simulation(strategy, i * 100 + 42, 300)
            wait_results.append(res['avg_wait'])
            throughput_results.append(res['throughput'])
            passenger_results.append(res['total_passengers'])
        
        all_results[strategy] = {
            'avg_wait': wait_results,
            'throughput': throughput_results,
            'total_passengers': passenger_results
        }
        
        print(f"  平均等待: {np.mean(wait_results):.2f}s, 吞吐量: {np.mean(throughput_results):.4f}")
    
    print("\n" + "=" * 80)
    print("快速预览结果")
    print("=" * 80)
    
    for strategy, label in zip(strategies, labels):
        avg_wait = np.mean(all_results[strategy]['avg_wait'])
        avg_throughput = np.mean(all_results[strategy]['throughput'])
        print(f"{label}: 等待={avg_wait:.2f}s, 吞吐量={avg_throughput:.4f}")
    
    print("\n" + "=" * 80)
    print("完整SimPy仿真 (80次/策略) 正在后台运行...")
    print("预计需要20-30分钟完成")
    print("=" * 80)

if __name__ == '__main__':
    main()
