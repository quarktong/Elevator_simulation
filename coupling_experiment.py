import simpy
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
from config import SimConfig, BuildingConfig, TimeConfig, TrafficConfig
from models import Passenger, HallCall, Direction, ElevatorState, PassengerState
from typing import List, Optional, Dict, Tuple
import itertools

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

print("=" * 80)
print("电梯分组策略 × 调度算法 全组合实验")
print("=" * 80)
print(f"开始时间: {datetime.now()}")
print("组合数: 3×3 = 9种")
print("每种组合: 30次仿真")
print("总仿真数: 270次")
print("预计时间: 30-40分钟")
print("=" * 80)

# ==================== 电梯类定义 ====================

class ElevatorBase:
    """电梯基类"""
    def __init__(self, elevator_id: int, served_floors: set, config: SimConfig, 
                 env: simpy.Environment, call_store: simpy.Store, statistics: 'Stats'):
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
        yield self.env.timeout(0.3)
        
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
        
        yield self.env.timeout(0.2)
        self.state = ElevatorState.IDLE
    
    def _move_to_floor(self, target):
        while round(self.position) != target:
            if self.direction == Direction.UP:
                self.position += 1
                yield self.env.timeout(0.08)
            elif self.direction == Direction.DOWN:
                self.position -= 1
                yield self.env.timeout(0.08)
    
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

class Stats:
    def __init__(self):
        self.completed_passengers = []
        self.arrived_passengers = []
    
    def record_arrival(self, passenger: Passenger):
        self.arrived_passengers.append(passenger)
    
    def record_alighting(self, passenger: Passenger):
        passenger.state = PassengerState.DONE
        self.completed_passengers.append(passenger)

class PassengerGenerator:
    def __init__(self, env: simpy.Environment, config: SimConfig, 
                 dispatcher: 'Dispatcher', statistics: Stats, rng: np.random.Generator):
        self.env = env
        self.config = config
        self.dispatcher = dispatcher
        self.statistics = statistics
        self.rng = rng
        self.passenger_id = 0
    
    def run(self):
        while True:
            lam = 0.12
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

# ==================== 调度器定义 ====================

class DispatcherSimple:
    """简单调度器：就近分配"""
    def __init__(self, config: SimConfig, elevators: List[ElevatorBase]):
        self.config = config
        self.elevators = elevators
    
    def dispatch(self, passenger: Passenger) -> Optional[int]:
        available = [e for e in self.elevators if passenger.origin in e.served_floors]
        if not available:
            return None
        
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

class DispatcherSCAN:
    """SCAN调度器：考虑方向和距离"""
    def __init__(self, config: SimConfig, elevators: List[ElevatorBase]):
        self.config = config
        self.elevators = elevators
    
    def dispatch(self, passenger: Passenger) -> Optional[int]:
        available = [e for e in self.elevators if passenger.origin in e.served_floors]
        if not available:
            return None
        
        idle = [e for e in available if e.is_full == False and len(e.passengers) == 0]
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
        
        same_direction = [e for e in available if e.direction == passenger.direction and not e.is_full]
        if same_direction:
            best = min(same_direction, key=lambda e: self._calc_cost(e, passenger))
            call = HallCall(
                floor=passenger.origin,
                direction=passenger.direction,
                time=passenger.request_time,
                passengers=[passenger]
            )
            passenger.state = PassengerState.WAITING
            best.assign_call(call)
            return best.elevator_id
        
        best = min(available, key=lambda e: self._calc_cost(e, passenger))
        call = HallCall(
            floor=passenger.origin,
            direction=passenger.direction,
            time=passenger.request_time,
            passengers=[passenger]
        )
        passenger.state = PassengerState.WAITING
        best.assign_call(call)
        return best.elevator_id
    
    def _calc_cost(self, elevator: ElevatorBase, passenger: Passenger) -> float:
        distance = abs(elevator.position - passenger.origin)
        if elevator.direction == passenger.direction:
            if (passenger.direction == Direction.UP and passenger.origin >= round(elevator.position)) or \
               (passenger.direction == Direction.DOWN and passenger.origin <= round(elevator.position)):
                return distance
        return distance + 10

class DispatcherSmart:
    """智能调度器：多因素评分"""
    def __init__(self, config: SimConfig, elevators: List[ElevatorBase]):
        self.config = config
        self.elevators = elevators
    
    def dispatch(self, passenger: Passenger) -> Optional[int]:
        available = [e for e in self.elevators if passenger.origin in e.served_floors]
        if not available:
            return None
        
        scores = {}
        for e in available:
            score = self._calc_score(e, passenger)
            scores[e] = score
        
        best = min(scores, key=scores.get)
        call = HallCall(
            floor=passenger.origin,
            direction=passenger.direction,
            time=passenger.request_time,
            passengers=[passenger]
        )
        passenger.state = PassengerState.WAITING
        best.assign_call(call)
        return best.elevator_id
    
    def _calc_score(self, elevator: ElevatorBase, passenger: Passenger) -> float:
        distance = abs(elevator.position - passenger.origin)
        
        eta = distance * 0.1
        
        load_factor = len(elevator.passengers) / elevator.capacity
        
        if elevator.direction == passenger.direction and elevator.direction != Direction.IDLE:
            if (passenger.direction == Direction.UP and passenger.origin >= round(elevator.position)) or \
               (passenger.direction == Direction.DOWN and passenger.origin <= round(elevator.position)):
                eta = eta * 0.5
        
        idle_bonus = 0 if len(elevator.passengers) > 0 else -2
        
        return eta + load_factor * 5 + idle_bonus

# ==================== 分组策略定义 ====================

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

def get_dispatcher(strategy: str, config: SimConfig, elevators: List[ElevatorBase]):
    if strategy == 'simple':
        return DispatcherSimple(config, elevators)
    elif strategy == 'scan':
        return DispatcherSCAN(config, elevators)
    elif strategy == 'smart':
        return DispatcherSmart(config, elevators)

# ==================== 仿真运行 ====================

def run_simulation(group_strategy: str, dispatch_strategy: str, seed: int, sim_time: int = 300):
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
    stats = Stats()
    
    floor_groups = create_floor_groups(group_strategy)
    call_stores = [simpy.Store(env) for _ in range(4)]
    
    elevators = []
    for i in range(4):
        elevator = ElevatorBase(
            elevator_id=i+1,
            served_floors=floor_groups[i],
            config=config,
            env=env,
            call_store=call_stores[i],
            statistics=stats
        )
        elevators.append(elevator)
        env.process(elevator.run())
    
    dispatcher = get_dispatcher(dispatch_strategy, config, elevators)
    generator = PassengerGenerator(env, config, dispatcher, stats, rng)
    env.process(generator.run())
    
    env.run(until=sim_time)
    
    wait_times = []
    for p in stats.completed_passengers:
        if p.wait_time is not None:
            wait_times.append(p.wait_time)
    
    avg_wait = np.mean(wait_times) if wait_times else 0
    max_wait = np.max(wait_times) if wait_times else 0
    throughput = len(wait_times) / sim_time if wait_times else 0
    
    return {
        'avg_wait': avg_wait,
        'max_wait': max_wait,
        'throughput': throughput,
        'total_passengers': len(wait_times)
    }

# ==================== 主实验 ====================

group_strategies = ['odd_even', 'long_chain', 'no_group']
dispatch_strategies = ['simple', 'scan', 'smart']
group_labels = ['奇偶分组', '长链结构', '不分组']
dispatch_labels = ['简单调度', 'SCAN调度', '智能调度']

results = {}
all_results = {}

start_time = datetime.now()

for i, (gs, gl) in enumerate(zip(group_strategies, group_labels)):
    for j, (ds, dl) in enumerate(zip(dispatch_strategies, dispatch_labels)):
        combo_key = f"{gs}_{ds}"
        combo_label = f"{gl} × {dl}"
        
        print(f"\n[{i*3+j+1}/9] {combo_label}")
        
        wait_results = []
        max_wait_results = []
        throughput_results = []
        passenger_results = []
        
        for k in range(30):
            res = run_simulation(gs, ds, (i*3+j)*1000 + k*42, 300)
            wait_results.append(res['avg_wait'])
            max_wait_results.append(res['max_wait'])
            throughput_results.append(res['throughput'])
            passenger_results.append(res['total_passengers'])
            
            if (k + 1) % 10 == 0:
                print(f"  {k+1}/30 完成，当前平均等待: {np.mean(wait_results):.2f}s")
        
        results[combo_key] = {
            'label': combo_label,
            'group': gs,
            'dispatch': ds,
            'avg_wait': np.mean(wait_results),
            'std_wait': np.std(wait_results),
            'max_wait': np.mean(max_wait_results),
            'std_max_wait': np.std(max_wait_results),
            'throughput': np.mean(throughput_results),
            'std_throughput': np.std(throughput_results),
            'passengers': np.mean(passenger_results)
        }
        
        all_results[combo_key] = {
            'avg_wait': wait_results,
            'max_wait': max_wait_results,
            'throughput': throughput_results,
            'passengers': passenger_results
        }

end_time = datetime.now()
duration = (end_time - start_time).total_seconds() / 60

print("\n" + "=" * 80)
print("实验完成!")
print(f"总耗时: {duration:.1f} 分钟")
print("=" * 80)

# ==================== 结果输出 ====================

print("\n" + "=" * 80)
print("完整实验结果 (30次平均)")
print("=" * 80)

# 创建结果表格
print("\n【平均等待时间】")
print("-" * 70)
header = f"{'策略组合':<20}"
for dl in dispatch_labels:
    header += f"{dl:>15}"
print(header)
print("-" * 70)

for gl in group_labels:
    row = f"{gl:<20}"
    for ds in dispatch_strategies:
        key = f"{['odd_even', 'long_chain', 'no_group'][['奇偶分组', '长链结构', '不分组'].index(gl)]}_{ds}"
        row += f"{results[key]['avg_wait']:>14.2f}s"
    print(row)

print("\n【系统吞吐量 (人/秒)】")
print("-" * 70)
header = f"{'策略组合':<20}"
for dl in dispatch_labels:
    header += f"{dl:>15}"
print(header)
print("-" * 70)

for gl in group_labels:
    row = f"{gl:<20}"
    for ds in dispatch_strategies:
        key = f"{['odd_even', 'long_chain', 'no_group'][['奇偶分组', '长链结构', '不分组'].index(gl)]}_{ds}"
        row += f"{results[key]['throughput']:>15.4f}"
    print(row)

# 找出最优组合
best_combo = min(results, key=lambda k: results[k]['avg_wait'])
print(f"\n✅ 最优组合: {results[best_combo]['label']}")
print(f"   平均等待时间: {results[best_combo]['avg_wait']:.2f}秒")
print(f"   系统吞吐量: {results[best_combo]['throughput']:.4f}人/秒")

# 与基准对比
baseline_key = 'odd_even_simple'
baseline_wait = results[baseline_key]['avg_wait']
print(f"\n【相对于基准(奇偶分组×简单调度)的改进】")
print("-" * 70)

for key, data in results.items():
    wait_improve = (baseline_wait - data['avg_wait']) / baseline_wait * 100
    throughput_improve = (data['throughput'] - results[baseline_key]['throughput']) / results[baseline_key]['throughput'] * 100
    print(f"{data['label']:<25} 等待时间: {wait_improve:>+6.1f}%  吞吐量: {throughput_improve:>+6.1f}%")

# ==================== 图表生成 ====================

fig = plt.figure(figsize=(18, 14))

# 1. 热力图 - 平均等待时间
ax1 = plt.subplot(2, 3, 1)
wait_matrix = np.zeros((3, 3))
for i, gs in enumerate(group_strategies):
    for j, ds in enumerate(dispatch_strategies):
        key = f"{gs}_{ds}"
        wait_matrix[i, j] = results[key]['avg_wait']

im1 = ax1.imshow(wait_matrix, cmap='RdYlGn_r', aspect='auto')
ax1.set_xticks(range(3))
ax1.set_xticklabels(['简单调度', 'SCAN调度', '智能调度'], fontsize=10)
ax1.set_yticks(range(3))
ax1.set_yticklabels(['奇偶分组', '长链结构', '不分组'], fontsize=10)
for i in range(3):
    for j in range(3):
        ax1.text(j, i, f'{wait_matrix[i, j]:.1f}s', ha='center', va='center', 
                fontsize=11, fontweight='bold', 
                color='white' if wait_matrix[i, j] > 40 else 'black')
ax1.set_title('平均等待时间热力图\n(秒，越绿越好)', fontsize=12, fontweight='bold')
plt.colorbar(im1, ax=ax1)

# 2. 热力图 - 吞吐量
ax2 = plt.subplot(2, 3, 2)
throughput_matrix = np.zeros((3, 3))
for i, gs in enumerate(group_strategies):
    for j, ds in enumerate(dispatch_strategies):
        key = f"{gs}_{ds}"
        throughput_matrix[i, j] = results[key]['throughput']

im2 = ax2.imshow(throughput_matrix, cmap='RdYlGn', aspect='auto')
ax2.set_xticks(range(3))
ax2.set_xticklabels(['简单调度', 'SCAN调度', '智能调度'], fontsize=10)
ax2.set_yticks(range(3))
ax2.set_yticklabels(['奇偶分组', '长链结构', '不分组'], fontsize=10)
for i in range(3):
    for j in range(3):
        ax2.text(j, i, f'{throughput_matrix[i, j]:.3f}', ha='center', va='center', 
                fontsize=10, fontweight='bold',
                color='white' if throughput_matrix[i, j] < 0.03 else 'black')
ax2.set_title('系统吞吐量热力图\n(人/秒，越绿越好)', fontsize=12, fontweight='bold')
plt.colorbar(im2, ax=ax2)

# 3. 柱状图 - 各组合对比
ax3 = plt.subplot(2, 3, 3)
labels = [results[key]['label'] for key in results]
waits = [results[key]['avg_wait'] for key in results]
colors = plt.cm.viridis(np.linspace(0, 1, len(labels)))
bars = ax3.barh(range(len(labels)), waits, color=colors)
ax3.set_yticks(range(len(labels)))
ax3.set_yticklabels(labels, fontsize=9)
ax3.set_xlabel('平均等待时间 (秒)', fontsize=11)
ax3.set_title('所有组合等待时间对比', fontsize=12, fontweight='bold')
ax3.invert_yaxis()
for i, bar in enumerate(bars):
    ax3.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2, 
            f'{waits[i]:.1f}s', va='center', fontsize=9)

# 4. 3D柱状图
ax4 = plt.subplot(2, 3, 4, projection='3d')
x = np.arange(3)
y = np.arange(3)
xpos, ypos = np.meshgrid(x, y)
xpos = xpos.ravel()
ypos = ypos.ravel()
zpos = np.zeros(9)

dx = dy = 0.25 * np.ones(9)
dz_wait = wait_matrix.ravel()
dz_throughput = throughput_matrix.ravel()

ax4.bar3d(xpos, ypos, zpos, dx, dy, dz_wait, color='steelblue', alpha=0.8)
ax4.set_xlabel('调度算法')
ax4.set_ylabel('分组策略')
ax4.set_zlabel('等待时间(秒)')
ax4.set_title('3D等待时间分布', fontsize=11, fontweight='bold')
ax4.set_xticks([0, 1, 2])
ax4.set_xticklabels(['简单', 'SCAN', '智能'])
ax4.set_yticks([0, 1, 2])
ax4.set_yticklabels(['奇偶', '长链', '不分组'])

# 5. 效率提升对比
ax5 = plt.subplot(2, 3, 5)
improvements = []
labels_short = []
for key in results:
    if key != baseline_key:
        wait_imp = (baseline_wait - results[key]['avg_wait']) / baseline_wait * 100
        improvements.append(wait_imp)
        labels_short.append(results[key]['label'].split('×')[1].strip())

colors = ['green' if x > 0 else 'red' for x in improvements]
bars = ax5.bar(range(len(improvements)), improvements, color=colors, alpha=0.7)
ax5.set_xticks(range(len(improvements)))
ax5.set_xticklabels(labels_short, rotation=45, ha='right', fontsize=9)
ax5.set_ylabel('等待时间改进 (%)', fontsize=11)
ax5.set_title('相对于基准(奇偶×简单)的改进', fontsize=12, fontweight='bold')
ax5.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
for i, bar in enumerate(bars):
    height = bar.get_height()
    ax5.text(bar.get_x() + bar.get_width()/2., height + (1 if height > 0 else -5),
            f'{height:+.1f}%', ha='center', fontsize=9)

# 6. 耦合效应分析
ax6 = plt.subplot(2, 3, 6)
coupling_data = {
    '简单调度': [],
    'SCAN调度': [],
    '智能调度': []
}
for ds, dl in zip(dispatch_strategies, dispatch_labels):
    for gs in group_strategies:
        key = f"{gs}_{ds}"
        coupling_data[dl].append(results[key]['avg_wait'])

x = np.arange(3)
width = 0.25
for i, (label, values) in enumerate(coupling_data.items()):
    ax6.bar(x + i*width, values, width, label=label, alpha=0.8)

ax6.set_xticks(x + width)
ax6.set_xticklabels(['奇偶分组', '长链结构', '不分组'])
ax6.set_ylabel('平均等待时间 (秒)', fontsize=11)
ax6.set_title('调度算法×分组策略耦合效应', fontsize=12, fontweight='bold')
ax6.legend(fontsize=10)
ax6.grid(axis='y', alpha=0.3)

plt.tight_layout()
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
chart_file = f'coupling_experiment_results_{timestamp}.png'
plt.savefig(chart_file, dpi=300, bbox_inches='tight')
plt.close()

print(f"\n✅ 图表已保存: {chart_file}")

# ==================== 保存详细结果 ====================

report_file = f'coupling_experiment_report_{timestamp}.txt'
with open(report_file, 'w', encoding='utf-8') as f:
    f.write("电梯分组策略 × 调度算法 全组合实验报告\n")
    f.write("=" * 80 + "\n")
    f.write(f"实验时间: {datetime.now()}\n")
    f.write(f"总耗时: {duration:.1f} 分钟\n")
    f.write(f"每种组合: 30次仿真\n")
    f.write(f"仿真时长: 300秒/次\n")
    f.write("=" * 80 + "\n\n")
    
    f.write("【完整结果表格】\n")
    f.write("-" * 80 + "\n")
    f.write(f"{'策略组合':<25} {'平均等待':>12} {'最大等待':>12} {'吞吐量':>12} {'乘客数':>10}\n")
    f.write("-" * 80 + "\n")
    
    for key, data in sorted(results.items(), key=lambda x: x[1]['avg_wait']):
        f.write(f"{data['label']:<25} {data['avg_wait']:>11.2f}s {data['max_wait']:>11.2f}s "
                f"{data['throughput']:>11.4f} {data['passengers']:>10.1f}\n")
    
    f.write("\n" + "=" * 80 + "\n")
    f.write("【最优组合分析】\n")
    f.write("-" * 80 + "\n")
    best_key = min(results, key=lambda k: results[k]['avg_wait'])
    best = results[best_key]
    f.write(f"最优组合: {best['label']}\n")
    f.write(f"平均等待时间: {best['avg_wait']:.2f} ± {best['std_wait']:.2f} 秒\n")
    f.write(f"系统吞吐量: {best['throughput']:.4f} ± {best['std_throughput']:.4f} 人/秒\n")
    f.write(f"\n相对于基准改进:\n")
    f.write(f"  等待时间减少: {(baseline_wait - best['avg_wait'])/baseline_wait*100:.1f}%\n")
    f.write(f"  吞吐量提升: {(best['throughput'] - results[baseline_key]['throughput'])/results[baseline_key]['throughput']*100:.1f}%\n")
    
    f.write("\n" + "=" * 80 + "\n")
    f.write("【耦合效应分析】\n")
    f.write("-" * 80 + "\n")
    
    for ds, dl in zip(dispatch_strategies, dispatch_labels):
        f.write(f"\n{dl}:\n")
        for gs, gl in zip(group_strategies, group_labels):
            key = f"{gs}_{ds}"
            imp = (baseline_wait - results[key]['avg_wait'])/baseline_wait*100
            f.write(f"  {gl}: {results[key]['avg_wait']:.2f}s ({imp:+.1f}%)\n")

print(f"✅ 报告已保存: {report_file}")

print("\n" + "=" * 80)
print("实验完成!")
print("=" * 80)
