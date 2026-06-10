import simpy
import numpy as np
from datetime import datetime

# 导入项目模块
from config import SimConfig
from models import HallCall, Direction, ElevatorState, ElevatorSnapshot, PassengerState, Passenger
from statistics import Statistics

class ElevatorBase:
    """基础电梯类"""
    def __init__(self, elevator_id, config, env, call_store, statistics, served_floors):
        self.elevator_id = elevator_id
        self.config = config
        self.env = env
        self.call_store = call_store
        self.statistics = statistics
        self.served_floors = served_floors
        
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

    def assign_call(self, call):
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

    def _move_to_floor(self, target):
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

    def get_snapshot(self):
        return ElevatorSnapshot(
            id=self.elevator_id,
            position=self.position,
            direction=self.direction,
            n_passengers=len(self.passengers),
            state=self.state,
            car_calls=frozenset(self.car_calls),
            hall_calls=frozenset(self.hall_calls.keys())
        )

class PassengerGeneratorSimple:
    """简化的乘客生成器"""
    def __init__(self, env, config, dispatcher, statistics, rng_seed):
        self.env = env
        self.config = config
        self.dispatcher = dispatcher
        self.statistics = statistics
        self.rng = np.random.default_rng(rng_seed)

    def run(self):
        passenger_id = 0
        while True:
            current_time = self.env.now
            lam = self.config.get_lambda(current_time)
            interval = self.rng.exponential(1.0 / lam) if lam > 0 else float('inf')
            yield self.env.timeout(interval)

            origin = self.rng.integers(1, self.config.building.n_floors + 1)
            destination = self.rng.integers(1, self.config.building.n_floors + 1)
            while destination == origin:
                destination = self.rng.integers(1, self.config.building.n_floors + 1)

            passenger = Passenger(
                id=passenger_id,
                origin=origin,
                destination=destination,
                request_time=self.env.now,
                state=PassengerState.ARRIVED
            )
            passenger_id += 1

            self.statistics.record_arrival(passenger)
            direction = Direction.UP if destination > origin else Direction.DOWN
            
            call = HallCall(
                floor=origin,
                direction=direction,
                time=self.env.now,
                passengers=[passenger]
            )
            
            self.dispatcher.dispatch(call)

class DispatcherSimple:
    """简化的调度器"""
    def __init__(self, elevators):
        self.elevators = elevators

    def dispatch(self, call):
        available = [e for e in self.elevators if call.floor in e.served_floors]
        if not available:
            return None
        
        best_e = None
        best_score = float('inf')
        
        for e in available:
            score = abs(e.position - call.floor)
            if score < best_score:
                best_score = score
                best_e = e
        
        if best_e:
            best_e.assign_call(call)
            return best_e.elevator_id
        return None

def run_simulation(strategy, seed, sim_time=300):
    """运行单次仿真"""
    config = SimConfig.default()
    config.sim_end = sim_time
    config.seed = seed
    
    env = simpy.Environment()
    stats = Statistics()
    
    # 定义不同策略的楼层分配
    if strategy == 'odd_even':
        # 奇偶分组
        floor_groups = [
            {1,3,5,7,9,11,13,15,17},
            {1,3,5,7,9,11,13,15,17},
            {1,2,4,6,8,10,12,14,16},
            {1,2,4,6,8,10,12,14,16}
        ]
    elif strategy == 'long_chain':
        # 长链分组
        floor_groups = [
            {1,2,3,4,5,6,7,8,9},
            {1,7,8,9,10,11,12,13,14,15},
            {1,11,12,13,14,15,16,17},
            {1,2,3,4,5,13,14,15,16,17}
        ]
    elif strategy == 'no_group':
        # 不分组
        all_floors = set(range(1, 18))
        floor_groups = [all_floors, all_floors, all_floors, all_floors]
    else:
        raise ValueError(f"Unknown strategy: {strategy}")
    
    call_stores = [simpy.Store(env) for _ in range(4)]
    elevators = []
    
    for i in range(4):
        elevator = ElevatorBase(
            elevator_id=i+1,
            config=config,
            env=env,
            call_store=call_stores[i],
            statistics=stats,
            served_floors=floor_groups[i]
        )
        elevators.append(elevator)
        env.process(elevator.run())
    
    dispatcher = DispatcherSimple(elevators)
    generator = PassengerGeneratorSimple(env, config, dispatcher, stats, seed)
    env.process(generator.run())
    
    env.run(until=sim_time)
    
    return stats

def run_multiple_simulations(strategy, n_runs=30, sim_time=300):
    """运行多次仿真并收集统计"""
    results = {
        'avg_wait_time': [],
        'max_wait_time': [],
        'avg_riding_time': [],
        'throughput': [],
        'utilization': []
    }
    
    for i in range(n_runs):
        stats = run_simulation(strategy, i*100 + 42, sim_time)
        
        if stats.total_arrived > 0:
            avg_wait = sum(p.wait_time for p in stats.completed_passengers) / len(stats.completed_passengers) if stats.completed_passengers else 0
            max_wait = max(p.wait_time for p in stats.completed_passengers) if stats.completed_passengers else 0
            avg_riding = sum(p.riding_time for p in stats.completed_passengers) / len(stats.completed_passengers) if stats.completed_passengers else 0
            throughput = len(stats.completed_passengers) / sim_time
            utilization = sum(stats.elevator_utilization.values()) / 4
            
            results['avg_wait_time'].append(avg_wait)
            results['max_wait_time'].append(max_wait)
            results['avg_riding_time'].append(avg_riding)
            results['throughput'].append(throughput)
            results['utilization'].append(utilization)
    
    return results

def main():
    print("=" * 80)
    print("电梯分组策略对比仿真实验")
    print("=" * 80)
    print(f"实验时间: {datetime.now()}")
    print(f"仿真时长: 300秒/次")
    print(f"实验次数: 15次/策略")
    print("策略对比: 奇偶分组 vs 长链结构 vs 不分组")
    print("=" * 80)
    
    strategies = ['odd_even', 'long_chain', 'no_group']
    strategy_names = ['奇偶分组', '长链结构', '不分组']
    all_results = {}
    
    for strategy, name in zip(strategies, strategy_names):
        print(f"\n正在运行 [{name}] 策略...")
        results = run_multiple_simulations(strategy, n_runs=15)
        all_results[strategy] = results
        print(f"  完成 {len(results['avg_wait_time'])} 次仿真")
    
    print("\n" + "=" * 80)
    print("仿真结果统计")
    print("=" * 80)
    
    # 生成报告
    report_lines = []
    report_lines.append("电梯分组策略对比仿真报告")
    report_lines.append("=" * 80)
    report_lines.append(f"生成时间: {datetime.now()}")
    report_lines.append(f"仿真参数: 300秒/次, 30次/策略")
    report_lines.append("=" * 80)
    
    for strategy, name in zip(strategies, strategy_names):
        results = all_results[strategy]
        
        avg_wait = np.mean(results['avg_wait_time'])
        std_wait = np.std(results['avg_wait_time'])
        max_wait = np.mean(results['max_wait_time'])
        avg_riding = np.mean(results['avg_riding_time'])
        throughput = np.mean(results['throughput'])
        utilization = np.mean(results['utilization'])
        
        report_lines.append(f"\n【{name}】")
        report_lines.append(f"├─ 平均等待时间: {avg_wait:.2f} ± {std_wait:.2f} 秒")
        report_lines.append(f"├─ 最大等待时间: {max_wait:.2f} 秒")
        report_lines.append(f"├─ 平均乘车时间: {avg_riding:.2f} 秒")
        report_lines.append(f"├─ 系统吞吐量: {throughput:.4f} 人/秒")
        report_lines.append(f"└─ 电梯利用率: {utilization*100:.1f}%")
    
    # 对比分析
    report_lines.append("\n" + "=" * 80)
    report_lines.append("策略对比分析")
    report_lines.append("=" * 80)
    
    odd_even = all_results['odd_even']
    long_chain = all_results['long_chain']
    no_group = all_results['no_group']
    
    wait_improve_chain = (np.mean(odd_even['avg_wait_time']) - np.mean(long_chain['avg_wait_time'])) / np.mean(odd_even['avg_wait_time']) * 100
    wait_improve_nogroup = (np.mean(odd_even['avg_wait_time']) - np.mean(no_group['avg_wait_time'])) / np.mean(odd_even['avg_wait_time']) * 100
    
    throughput_improve_chain = (np.mean(long_chain['throughput']) - np.mean(odd_even['throughput'])) / np.mean(odd_even['throughput']) * 100
    throughput_improve_nogroup = (np.mean(no_group['throughput']) - np.mean(odd_even['throughput'])) / np.mean(odd_even['throughput']) * 100
    
    report_lines.append(f"\n等待时间改进对比（以奇偶分组为基准）:")
    report_lines.append(f"  ├─ 长链结构: 改进 {wait_improve_chain:.1f}%")
    report_lines.append(f"  └─ 不分组: 改进 {wait_improve_nogroup:.1f}%")
    
    report_lines.append(f"\n吞吐量改进对比（以奇偶分组为基准）:")
    report_lines.append(f"  ├─ 长链结构: 改进 {throughput_improve_chain:.1f}%")
    report_lines.append(f"  └─ 不分组: 改进 {throughput_improve_nogroup:.1f}%")
    
    report_lines.append("\n" + "=" * 80)
    report_lines.append("结论")
    report_lines.append("=" * 80)
    
    if np.mean(long_chain['avg_wait_time']) < np.mean(no_group['avg_wait_time']) and np.mean(long_chain['throughput']) > np.mean(no_group['throughput']):
        report_lines.append("✅ 长链结构在等待时间和吞吐量方面均优于不分组策略")
    elif np.mean(long_chain['avg_wait_time']) < np.mean(no_group['avg_wait_time']):
        report_lines.append("✅ 长链结构等待时间更短")
    else:
        report_lines.append("⚠️ 仿真结果与理论预测有差异")
    
    report_lines.append("\n📊 效率排序:")
    wait_times = [
        ('奇偶分组', np.mean(odd_even['avg_wait_time'])),
        ('长链结构', np.mean(long_chain['avg_wait_time'])),
        ('不分组', np.mean(no_group['avg_wait_time']))
    ]
    wait_times.sort(key=lambda x: x[1])
    
    for i, (name, val) in enumerate(wait_times, 1):
        report_lines.append(f"  {i}. {name}: {val:.2f}秒")
    
    # 打印报告
    print("\n".join(report_lines))
    
    # 保存报告
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_filename = f'elevator_strategy_comparison_report_{timestamp}.txt'
    with open(report_filename, 'w', encoding='utf-8') as f:
        f.write("\n".join(report_lines))
    print(f"\n报告已保存为: {report_filename}")

if __name__ == '__main__':
    main()
