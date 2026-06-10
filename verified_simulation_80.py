import simpy
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
from config import SimConfig, BuildingConfig, TimeConfig, TrafficConfig
from models import Passenger, HallCall, Direction, ElevatorState, PassengerState
from typing import List, Optional

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

class FullElevator:
    """完整电梯类"""
    def __init__(self, elevator_id: int, served_floors: set, config: SimConfig, 
                 env: simpy.Environment, call_store: simpy.Store, statistics: 'FullStatistics'):
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

class FullDispatcher:
    """完整调度器"""
    def __init__(self, config: SimConfig, elevators: List[FullElevator]):
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

class FullStatistics:
    """完整统计类"""
    def __init__(self):
        self.completed_passengers = []
        self.arrived_passengers = []
        self.elevator_utilization = {}
    
    def record_arrival(self, passenger: Passenger):
        self.arrived_passengers.append(passenger)
    
    def record_alighting(self, passenger: Passenger):
        passenger.state = PassengerState.DONE
        self.completed_passengers.append(passenger)
    
    @property
    def total_arrived(self):
        return len(self.arrived_passengers)
    
    @property
    def total_completed(self):
        return len(self.completed_passengers)

class FullPassengerGenerator:
    """完整乘客生成器"""
    def __init__(self, env: simpy.Environment, config: SimConfig, 
                 dispatcher: FullDispatcher, statistics: FullStatistics, rng: np.random.Generator):
        self.env = env
        self.config = config
        self.dispatcher = dispatcher
        self.statistics = statistics
        self.rng = rng
        self.passenger_id = 0
    
    def run(self):
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
    """创建不同策略的楼层分配"""
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
    else:
        raise ValueError(f"Unknown strategy: {strategy}")

def run_full_simulation(strategy: str, seed: int, sim_time: int = 300):
    """运行完整仿真"""
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
    stats = FullStatistics()
    
    floor_groups = create_floor_groups(strategy)
    call_stores = [simpy.Store(env) for _ in range(4)]
    
    elevators = []
    for i in range(4):
        elevator = FullElevator(
            elevator_id=i+1,
            served_floors=floor_groups[i],
            config=config,
            env=env,
            call_store=call_stores[i],
            statistics=stats
        )
        elevators.append(elevator)
        env.process(elevator.run())
    
    dispatcher = FullDispatcher(config=config, elevators=elevators)
    generator = FullPassengerGenerator(env, config, dispatcher, stats, rng)
    env.process(generator.run())
    
    env.run(until=sim_time)
    
    wait_times = []
    board_times = []
    
    for p in stats.completed_passengers:
        if p.wait_time is not None:
            wait_times.append(p.wait_time)
        if p.trip_time is not None:
            board_times.append(p.trip_time)
    
    avg_wait = np.mean(wait_times) if wait_times else 0
    max_wait = np.max(wait_times) if wait_times else 0
    avg_board = np.mean(board_times) if board_times else 0
    throughput = len(wait_times) / sim_time if wait_times else 0
    
    return {
        'avg_wait': avg_wait,
        'max_wait': max_wait,
        'avg_board': avg_board,
        'throughput': throughput,
        'wait_times': wait_times,
        'total_passengers': len(wait_times)
    }

def run_batch_simulations(strategy: str, n_runs: int = 80, sim_time: int = 300):
    """运行批量仿真"""
    print(f"开始运行 {strategy} 策略，共 {n_runs} 次仿真...")
    
    results = {
        'avg_wait': [],
        'max_wait': [],
        'avg_board': [],
        'throughput': [],
        'all_wait_times': [],
        'total_passengers': []
    }
    
    for i in range(n_runs):
        res = run_full_simulation(strategy, i * 100 + 42, sim_time)
        results['avg_wait'].append(res['avg_wait'])
        results['max_wait'].append(res['max_wait'])
        results['avg_board'].append(res['avg_board'])
        results['throughput'].append(res['throughput'])
        results['all_wait_times'].extend(res['wait_times'])
        results['total_passengers'].append(res['total_passengers'])
        
        if (i + 1) % 20 == 0:
            print(f"  已完成 {i+1}/{n_runs} 次")
    
    return results

def plot_comprehensive_results(results_dict, output_prefix):
    """生成综合结果图表"""
    fig = plt.figure(figsize=(18, 14))
    
    strategies = ['odd_even', 'long_chain', 'no_group']
    labels = ['奇偶分组', '长链结构', '不分组']
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1']
    
    ax1 = plt.subplot(2, 3, 1)
    avg_waits = [np.mean(results_dict[s]['avg_wait']) for s in strategies]
    std_waits = [np.std(results_dict[s]['avg_wait']) for s in strategies]
    bars = ax1.bar(range(3), avg_waits, yerr=std_waits, capsize=10, color=colors)
    ax1.set_xticks(range(3))
    ax1.set_xticklabels(labels, fontsize=12)
    ax1.set_ylabel('平均等待时间 (秒)', fontsize=12)
    ax1.set_title('平均等待时间对比', fontsize=13, fontweight='bold')
    ax1.grid(axis='y', alpha=0.3)
    
    for i, bar in enumerate(bars):
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                f'{height:.1f}s', ha='center', fontsize=11, fontweight='bold')
    
    ax2 = plt.subplot(2, 3, 2)
    throughputs = [np.mean(results_dict[s]['throughput']) for s in strategies]
    std_throughput = [np.std(results_dict[s]['throughput']) for s in strategies]
    bars = ax2.bar(range(3), throughputs, yerr=std_throughput, capsize=10, color=colors)
    ax2.set_xticks(range(3))
    ax2.set_xticklabels(labels, fontsize=12)
    ax2.set_ylabel('吞吐量 (人/秒)', fontsize=12)
    ax2.set_title('系统吞吐量对比', fontsize=13, fontweight='bold')
    ax2.grid(axis='y', alpha=0.3)
    
    for i, bar in enumerate(bars):
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height + 0.002,
                f'{height:.4f}', ha='center', fontsize=11, fontweight='bold')
    
    ax3 = plt.subplot(2, 3, 3)
    box_data = [results_dict[s]['avg_wait'] for s in strategies]
    bp = ax3.boxplot(box_data, labels=labels, patch_artist=True)
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax3.set_ylabel('平均等待时间 (秒)', fontsize=12)
    ax3.set_title('等待时间分布', fontsize=13, fontweight='bold')
    ax3.grid(axis='y', alpha=0.3)
    
    ax4 = plt.subplot(2, 3, 4)
    base_wait = np.mean(results_dict['odd_even']['avg_wait'])
    base_throughput = np.mean(results_dict['odd_even']['throughput'])
    
    wait_improve = [(base_wait - np.mean(results_dict[s]['avg_wait']))/base_wait * 100 
                   for s in strategies]
    throughput_improve = [(np.mean(results_dict[s]['throughput']) - base_throughput)/base_throughput * 100 
                        for s in strategies]
    
    x = np.arange(3)
    width = 0.35
    bars1 = ax4.bar(x - width/2, wait_improve, width, label='等待时间改进', color='#FF9999')
    bars2 = ax4.bar(x + width/2, throughput_improve, width, label='吞吐量改进', color='#99FF99')
    ax4.set_xticks(x)
    ax4.set_xticklabels(labels, fontsize=12)
    ax4.set_ylabel('改进幅度 (%)', fontsize=12)
    ax4.set_title('相对于奇偶分组的改进', fontsize=13, fontweight='bold')
    ax4.legend(fontsize=10)
    ax4.grid(axis='y', alpha=0.3)
    ax4.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    
    ax5 = plt.subplot(2, 3, 5)
    totals = [np.mean(results_dict[s]['total_passengers']) for s in strategies]
    std_totals = [np.std(results_dict[s]['total_passengers']) for s in strategies]
    bars = ax5.bar(range(3), totals, yerr=std_totals, capsize=10, color=colors)
    ax5.set_xticks(range(3))
    ax5.set_xticklabels(labels, fontsize=12)
    ax5.set_ylabel('完成乘客数', fontsize=12)
    ax5.set_title('每次仿真完成乘客数', fontsize=13, fontweight='bold')
    ax5.grid(axis='y', alpha=0.3)
    
    ax6 = plt.subplot(2, 3, 6, polar=True)
    categories = ['等待时间', '吞吐量', '乘客数', '稳定性']
    wait_scores = [100 - (np.mean(results_dict[s]['avg_wait']) / max([np.mean(results_dict[x]['avg_wait']) for x in strategies])) * 100 
                  for s in strategies]
    throughput_scores = [(np.mean(results_dict[s]['throughput']) / max([np.mean(results_dict[x]['throughput']) for x in strategies])) * 100 
                        for s in strategies]
    passenger_scores = [(np.mean(results_dict[s]['total_passengers']) / max([np.mean(results_dict[x]['total_passengers']) for x in strategies])) * 100 
                       for s in strategies]
    stability_scores = [100 - np.std(results_dict[s]['avg_wait']) for s in strategies]
    
    values = np.array([[wait_scores[i], throughput_scores[i], passenger_scores[i], stability_scores[i]] 
                      for i in range(3)])
    
    angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
    angles += angles[:1]
    
    for i in range(3):
        vals = values[i].tolist()
        vals += vals[:1]
        ax6.plot(angles, vals, 'o-', linewidth=2, label=labels[i], color=colors[i])
        ax6.fill(angles, vals, alpha=0.25, color=colors[i])
    
    ax6.set_xticks(angles[:-1])
    ax6.set_xticklabels(categories, fontsize=11)
    ax6.set_title('综合效率对比', fontsize=13, fontweight='bold', pad=20)
    ax6.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0), fontsize=10)
    ax6.grid(True)
    
    plt.tight_layout()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    chart_file = f'{output_prefix}_verified80_{timestamp}.png'
    plt.savefig(chart_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    return chart_file

def main():
    print("=" * 80)
    print("电梯分组策略 - 真实SimPy仿真验证 (80次/策略)")
    print("=" * 80)
    print(f"实验时间: {datetime.now()}")
    print(f"仿真时长: 300秒/次")
    print(f"实验次数: 80次/策略 (共240次)")
    print(f"仿真引擎: SimPy (真实事件驱动)")
    print("=" * 80)
    
    strategies = ['odd_even', 'long_chain', 'no_group']
    all_results = {}
    
    for strategy in strategies:
        results = run_batch_simulations(strategy, n_runs=80, sim_time=300)
        all_results[strategy] = results
    
    print("\n" + "=" * 80)
    print("生成结果图表...")
    chart_file = plot_comprehensive_results(all_results, 'elevator_verified80')
    print(f"图表已保存: {chart_file}")
    
    print("\n" + "=" * 80)
    print("仿真结果统计 (80次仿真平均)")
    print("=" * 80)
    
    labels = ['奇偶分组', '长链结构', '不分组']
    
    for strategy, label in zip(strategies, labels):
        results = all_results[strategy]
        avg_wait = np.mean(results['avg_wait'])
        std_wait = np.std(results['avg_wait'])
        avg_throughput = np.mean(results['throughput'])
        std_throughput = np.std(results['throughput'])
        avg_passengers = np.mean(results['total_passengers'])
        
        print(f"\n【{label}】")
        print(f"  平均等待时间: {avg_wait:.2f} ± {std_wait:.2f} 秒")
        print(f"  平均吞吐量: {avg_throughput:.4f} ± {std_throughput:.4f} 人/秒")
        print(f"  平均完成乘客: {avg_passengers:.1f} 人/次")
    
    print("\n" + "=" * 80)
    print("效率改进分析 (以奇偶分组为基准)")
    print("=" * 80)
    
    base_wait = np.mean(all_results['odd_even']['avg_wait'])
    base_throughput = np.mean(all_results['odd_even']['throughput'])
    
    for strategy, label in zip(strategies[1:], labels[1:]):
        wait_improve = (base_wait - np.mean(all_results[strategy]['avg_wait'])) / base_wait * 100
        throughput_improve = (np.mean(all_results[strategy]['throughput']) - base_throughput) / base_throughput * 100
        
        print(f"\n{label}:")
        print(f"  等待时间改进: {wait_improve:+.1f}%")
        print(f"  吞吐量改进: {throughput_improve:+.1f}%")
    
    print("\n" + "=" * 80)
    print("结论")
    print("=" * 80)
    
    wait_results = [(labels[i], np.mean(all_results[s]['avg_wait'])) for i, s in enumerate(strategies)]
    wait_results.sort(key=lambda x: x[1])
    
    throughput_results = [(labels[i], np.mean(all_results[s]['throughput'])) for i, s in enumerate(strategies)]
    throughput_results.sort(key=lambda x: x[1], reverse=True)
    
    print("\n等待时间排序 (从小到大):")
    for i, (name, val) in enumerate(wait_results, 1):
        print(f"  {i}. {name}: {val:.2f}秒")
    
    print("\n吞吐量排序 (从大到小):")
    for i, (name, val) in enumerate(throughput_results, 1):
        print(f"  {i}. {name}: {val:.4f}人/秒")
    
    print("\n" + "=" * 80)
    print("实验完成!")
    print("=" * 80)

if __name__ == '__main__':
    main()
