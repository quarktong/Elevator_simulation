import simpy
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
from config import SimConfig
from models import HallCall, Direction, ElevatorState, ElevatorSnapshot, PassengerState, Passenger
from statistics import Statistics

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

class ElevatorSimple:
    """简化的电梯类 - 提高仿真速度"""
    def __init__(self, elevator_id, config, env, served_floors):
        self.elevator_id = elevator_id
        self.config = config
        self.env = env
        self.served_floors = served_floors
        
        self.position = 1.0
        self.direction = Direction.IDLE
        self.passengers = []
        self.car_calls = set()
        self.hall_calls = {}
        self.capacity = config.building.capacity
        self.moving_time = 0
        self.idle_time = 0

    def assign_call(self, call, time):
        if call.floor in self.served_floors:
            self.hall_calls[call.floor] = (call, time)
            call.assign_to(self.elevator_id)

    def get_next_stop(self):
        all_calls = set(self.car_calls)
        for call, _ in self.hall_calls.values():
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

    def run_simulation(self, env, end_time):
        wait_times = []
        board_times = []
        total_passengers = 0
        
        call_queue = []
        
        while env.now < end_time:
            next_stop = self.get_next_stop()
            
            if next_stop is None:
                idle_start = env.now
                if call_queue:
                    next_call, call_time = call_queue.pop(0)
                    self.assign_call(next_call, call_time)
                    next_stop = self.get_next_stop()
                else:
                    try:
                        yield env.timeout(1)
                        self.idle_time += env.now - idle_start
                        continue
                    except:
                        break
            
            current = round(self.position)
            target = next_stop
            move_start = env.now
            
            if target > current:
                self.direction = Direction.UP
                steps = target - current
                self.position = target
                yield env.timeout(steps * 2.31)
            elif target < current:
                self.direction = Direction.DOWN
                steps = current - target
                self.position = target
                yield env.timeout(steps * 2.31)
            
            self.moving_time += env.now - move_start
            
            if target in self.car_calls:
                passengers_to_alight = [p for p in self.passengers if p.destination == target]
                for p in passengers_to_alight:
                    if hasattr(p, 'board_time'):
                        board_times.append(env.now - p.board_time)
                self.passengers = [p for p in self.passengers if p.destination != target]
                self.car_calls.discard(target)
            
            if target in self.hall_calls:
                call, req_time = self.hall_calls[target]
                if not call.completed and len(self.passengers) < self.capacity:
                    for p in call.passengers[:]:
                        if len(self.passengers) < self.capacity:
                            p.board_time = env.now
                            wait_times.append(env.now - req_time)
                            self.passengers.append(p)
                            self.car_calls.add(p.destination)
                            total_passengers += 1
                    call.passengers = []
                    call.completed = True
                    del self.hall_calls[target]
            
            yield env.timeout(10.8)
            
            next_stop = self.get_next_stop()
            if next_stop is not None:
                if next_stop > round(self.position):
                    self.direction = Direction.UP
                elif next_stop < round(self.position):
                    self.direction = Direction.DOWN
                else:
                    self.direction = Direction.IDLE
            else:
                self.direction = Direction.IDLE
        
        return wait_times, board_times, total_passengers, self.moving_time, self.idle_time

def run_single_simulation(strategy, seed, sim_time=300):
    """运行单次快速仿真"""
    config = SimConfig.default()
    config.sim_end = sim_time
    config.seed = seed
    
    rng = np.random.default_rng(seed)
    
    if strategy == 'odd_even':
        floor_groups = [
            {1,3,5,7,9,11,13,15,17},
            {1,3,5,7,9,11,13,15,17},
            {1,2,4,6,8,10,12,14,16},
            {1,2,4,6,8,10,12,14,16}
        ]
    elif strategy == 'long_chain':
        floor_groups = [
            {1,2,3,4,5,6,7,8,9},
            {1,7,8,9,10,11,12,13,14,15},
            {1,11,12,13,14,15,16,17},
            {1,2,3,4,5,13,14,15,16,17}
        ]
    elif strategy == 'no_group':
        all_floors = set(range(1, 18))
        floor_groups = [all_floors, all_floors, all_floors, all_floors]
    else:
        raise ValueError(f"Unknown strategy: {strategy}")
    
    elevators = [ElevatorSimple(i+1, config, None, floor_groups[i]) for i in range(4)]
    
    env = simpy.Environment()
    passenger_id = 0
    total_passengers = 0
    current_time = 0.0
    all_wait_times = []
    all_board_times = []
    total_moving_time = [0, 0, 0, 0]
    total_idle_time = [0, 0, 0, 0]
    
    elev_procs = []
    for i in range(4):
        elevator = elevators[i]
        elevator.env = env
        elev_proc = env.process(elevator.run_simulation(env, sim_time))
        elev_procs.append(elev_proc)
    
    while current_time < sim_time:
        lam = config.get_lambda(current_time)
        interval = rng.exponential(1.0 / lam) if lam > 0 else float('inf')
        current_time += interval
        if current_time >= sim_time:
            break
        
        origin = rng.integers(1, 18)
        destination = rng.integers(1, 18)
        while destination == origin:
            destination = rng.integers(1, 18)
        
        passenger = Passenger(
            id=passenger_id,
            origin=origin,
            destination=destination,
            request_time=current_time,
            state=PassengerState.ARRIVED
        )
        passenger_id += 1
        
        direction = Direction.UP if destination > origin else Direction.DOWN
        call = HallCall(
            floor=origin,
            direction=direction,
            time=current_time,
            passengers=[passenger]
        )
        
        available_elevators = []
        for e in elevators:
            if origin in e.served_floors:
                available_elevators.append(e)
        
        if available_elevators:
            best_e = None
            best_score = float('inf')
            for e in available_elevators:
                score = abs(e.position - origin)
                if score < best_score:
                    best_score = score
                    best_e = e
            if best_e:
                best_e.assign_call(call, current_time)
                total_passengers += 1
    
    env.run(until=sim_time)
    
    for i, elev_proc in enumerate(elev_procs):
        result = elev_proc.value
        if result:
            waits, boards, count, moving, idle = result
            all_wait_times.extend(waits)
            all_board_times.extend(boards)
            total_moving_time[i] = moving
            total_idle_time[i] = idle
    
    avg_wait = np.mean(all_wait_times) if all_wait_times else 0
    max_wait = np.max(all_wait_times) if all_wait_times else 0
    avg_board = np.mean(all_board_times) if all_board_times else 0
    throughput = len(all_wait_times) / sim_time if all_wait_times else 0
    avg_utilization = np.mean([m / sim_time for m in total_moving_time]) if sim_time > 0 else 0
    
    return {
        'avg_wait': avg_wait,
        'max_wait': max_wait,
        'avg_board': avg_board,
        'throughput': throughput,
        'utilization': avg_utilization,
        'wait_times': all_wait_times
    }

def run_multiple_simulations(strategy, n_runs=50, sim_time=300):
    """运行多次仿真"""
    results = {
        'avg_wait': [],
        'max_wait': [],
        'avg_board': [],
        'throughput': [],
        'utilization': [],
        'all_wait_times': []
    }
    
    for i in range(n_runs):
        res = run_single_simulation(strategy, i * 100 + 42, sim_time)
        results['avg_wait'].append(res['avg_wait'])
        results['max_wait'].append(res['max_wait'])
        results['avg_board'].append(res['avg_board'])
        results['throughput'].append(res['throughput'])
        results['utilization'].append(res['utilization'])
        results['all_wait_times'].extend(res['wait_times'])
    
    return results

def plot_results(results_dict, strategy_names, output_prefix):
    """生成结果图表"""
    fig = plt.figure(figsize=(16, 12))
    
    # 1. 平均等待时间对比
    ax1 = plt.subplot(2, 3, 1)
    avg_waits = [np.mean(results_dict[s]['avg_wait']) for s in strategy_names]
    std_waits = [np.std(results_dict[s]['avg_wait']) for s in strategy_names]
    bars = ax1.bar(range(3), avg_waits, yerr=std_waits, capsize=10, 
                   color=['#FF9999', '#66B2FF', '#99FF99'])
    ax1.set_xticks(range(3))
    ax1.set_xticklabels(['奇偶分组', '长链结构', '不分组'], fontsize=12)
    ax1.set_ylabel('平均等待时间 (秒)', fontsize=12)
    ax1.set_title('平均等待时间对比', fontsize=14, fontweight='bold')
    ax1.grid(axis='y', alpha=0.3)
    
    for i, bar in enumerate(bars):
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height + 1,
                f'{height:.1f}s', ha='center', fontsize=10)
    
    # 2. 吞吐量对比
    ax2 = plt.subplot(2, 3, 2)
    throughputs = [np.mean(results_dict[s]['throughput']) for s in strategy_names]
    std_throughput = [np.std(results_dict[s]['throughput']) for s in strategy_names]
    bars = ax2.bar(range(3), throughputs, yerr=std_throughput, capsize=10,
                   color=['#FF9999', '#66B2FF', '#99FF99'])
    ax2.set_xticks(range(3))
    ax2.set_xticklabels(['奇偶分组', '长链结构', '不分组'], fontsize=12)
    ax2.set_ylabel('吞吐量 (人/秒)', fontsize=12)
    ax2.set_title('系统吞吐量对比', fontsize=14, fontweight='bold')
    ax2.grid(axis='y', alpha=0.3)
    
    for i, bar in enumerate(bars):
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height + 0.001,
                f'{height:.3f}', ha='center', fontsize=10)
    
    # 3. 最大等待时间对比
    ax3 = plt.subplot(2, 3, 3)
    max_waits = [np.mean(results_dict[s]['max_wait']) for s in strategy_names]
    std_max = [np.std(results_dict[s]['max_wait']) for s in strategy_names]
    bars = ax3.bar(range(3), max_waits, yerr=std_max, capsize=10,
                   color=['#FF9999', '#66B2FF', '#99FF99'])
    ax3.set_xticks(range(3))
    ax3.set_xticklabels(['奇偶分组', '长链结构', '不分组'], fontsize=12)
    ax3.set_ylabel('最大等待时间 (秒)', fontsize=12)
    ax3.set_title('最大等待时间对比', fontsize=14, fontweight='bold')
    ax3.grid(axis='y', alpha=0.3)
    
    for i, bar in enumerate(bars):
        height = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width()/2., height + 2,
                f'{height:.1f}s', ha='center', fontsize=10)
    
    # 4. 等待时间分布
    ax4 = plt.subplot(2, 3, 4)
    colors = ['#FF9999', '#66B2FF', '#99FF99']
    for i, s in enumerate(strategy_names):
        wait_times = np.array(results_dict[s]['all_wait_times'])
        ax4.hist(wait_times, bins=30, alpha=0.6, color=colors[i], 
                 label=['奇偶分组', '长链结构', '不分组'][i], density=True)
    ax4.set_xlabel('等待时间 (秒)', fontsize=12)
    ax4.set_ylabel('频率', fontsize=12)
    ax4.set_title('等待时间分布', fontsize=14, fontweight='bold')
    ax4.legend(fontsize=10)
    ax4.grid(axis='y', alpha=0.3)
    
    # 5. 电梯利用率对比
    ax5 = plt.subplot(2, 3, 5)
    utilizations = [np.mean(results_dict[s]['utilization']) * 100 for s in strategy_names]
    std_util = [np.std(results_dict[s]['utilization']) * 100 for s in strategy_names]
    bars = ax5.bar(range(3), utilizations, yerr=std_util, capsize=10,
                   color=['#FF9999', '#66B2FF', '#99FF99'])
    ax5.set_xticks(range(3))
    ax5.set_xticklabels(['奇偶分组', '长链结构', '不分组'], fontsize=12)
    ax5.set_ylabel('利用率 (%)', fontsize=12)
    ax5.set_title('电梯利用率对比', fontsize=14, fontweight='bold')
    ax5.set_ylim(0, 100)
    ax5.grid(axis='y', alpha=0.3)
    
    for i, bar in enumerate(bars):
        height = bar.get_height()
        ax5.text(bar.get_x() + bar.get_width()/2., height + 1,
                f'{height:.1f}%', ha='center', fontsize=10)
    
    # 6. 效率改进幅度雷达图
    ax6 = plt.subplot(2, 3, 6, polar=True)
    
    base_wait = np.mean(results_dict['odd_even']['avg_wait'])
    wait_improve = [(base_wait - np.mean(results_dict[s]['avg_wait']))/base_wait * 100 
                   for s in strategy_names]
    
    base_throughput = np.mean(results_dict['odd_even']['throughput'])
    throughput_improve = [(np.mean(results_dict[s]['throughput']) - base_throughput)/base_throughput * 100 
                        for s in strategy_names]
    
    base_max = np.mean(results_dict['odd_even']['max_wait'])
    max_improve = [(base_max - np.mean(results_dict[s]['max_wait']))/base_max * 100 
                  for s in strategy_names]
    
    labels = ['等待时间', '吞吐量', '最大等待', '利用率']
    values = np.array([
        [wait_improve[0], throughput_improve[0], max_improve[0], 0],
        [wait_improve[1], throughput_improve[1], max_improve[1], 
         (np.mean(results_dict['long_chain']['utilization']) - np.mean(results_dict['odd_even']['utilization'])) * 100],
        [wait_improve[2], throughput_improve[2], max_improve[2], 
         (np.mean(results_dict['no_group']['utilization']) - np.mean(results_dict['odd_even']['utilization'])) * 100]
    ])
    
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    angles += angles[:1]
    
    for i in range(3):
        vals = values[i].tolist()
        vals += vals[:1]
        ax6.plot(angles, vals, 'o-', linewidth=2, 
                label=['奇偶分组', '长链结构', '不分组'][i],
                color=['#FF9999', '#66B2FF', '#99FF99'][i])
        ax6.fill(angles, vals, alpha=0.25, 
                color=['#FF9999', '#66B2FF', '#99FF99'][i])
    
    ax6.set_xticks(angles[:-1])
    ax6.set_xticklabels(labels, fontsize=11)
    ax6.set_title('效率改进幅度 (%)', fontsize=14, fontweight='bold', pad=20)
    ax6.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0), fontsize=10)
    ax6.grid(True)
    
    plt.tight_layout()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    chart_file = f'{output_prefix}_comparison_chart_{timestamp}.png'
    plt.savefig(chart_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    return chart_file

def main():
    print("=" * 80)
    print("电梯分组策略对比仿真实验 - 增强版")
    print("=" * 80)
    print(f"实验时间: {datetime.now()}")
    print(f"仿真时长: 300秒/次")
    print(f"实验次数: 50次/策略")
    print("策略对比: 奇偶分组 vs 长链结构 vs 不分组")
    print("=" * 80)
    
    strategies = ['odd_even', 'long_chain', 'no_group']
    strategy_display = ['奇偶分组', '长链结构', '不分组']
    all_results = {}
    
    for strategy, display in zip(strategies, strategy_display):
        print(f"\n正在运行 [{display}] 策略...")
        results = run_multiple_simulations(strategy, n_runs=50)
        all_results[strategy] = results
        print(f"  完成 50 次仿真")
        print(f"  平均等待: {np.mean(results['avg_wait']):.2f} ± {np.std(results['avg_wait']):.2f}秒")
        print(f"  平均吞吐量: {np.mean(results['throughput']):.4f} ± {np.std(results['throughput']):.4f}人/秒")
    
    print("\n" + "=" * 80)
    print("生成结果图表...")
    chart_file = plot_results(all_results, strategies, 'elevator_strategy')
    print(f"图表已保存: {chart_file}")
    
    print("\n" + "=" * 80)
    print("仿真结果统计")
    print("=" * 80)
    
    report_lines = []
    report_lines.append("电梯分组策略对比仿真报告")
    report_lines.append("=" * 80)
    report_lines.append(f"生成时间: {datetime.now()}")
    report_lines.append(f"仿真参数: 300秒/次, 50次/策略")
    report_lines.append("=" * 80)
    
    for strategy, display in zip(strategies, strategy_display):
        results = all_results[strategy]
        
        avg_wait = np.mean(results['avg_wait'])
        std_wait = np.std(results['avg_wait'])
        max_wait = np.mean(results['max_wait'])
        avg_board = np.mean(results['avg_board'])
        throughput = np.mean(results['throughput'])
        utilization = np.mean(results['utilization']) * 100
        
        report_lines.append(f"\n【{display}】")
        report_lines.append(f"  ├─ 平均等待时间: {avg_wait:.2f} ± {std_wait:.2f}秒")
        report_lines.append(f"  ├─ 最大等待时间: {max_wait:.2f}秒")
        report_lines.append(f"  ├─ 平均乘车时间: {avg_board:.2f}秒")
        report_lines.append(f"  ├─ 系统吞吐量: {throughput:.4f} ± {np.std(results['throughput']):.4f}人/秒")
        report_lines.append(f"  └─ 电梯利用率: {utilization:.1f} ± {np.std(results['utilization'])*100:.1f}%")
    
    report_lines.append("\n" + "=" * 80)
    report_lines.append("策略对比分析")
    report_lines.append("=" * 80)
    
    base_wait = np.mean(all_results['odd_even']['avg_wait'])
    base_throughput = np.mean(all_results['odd_even']['throughput'])
    
    wait_improve_chain = ((base_wait - np.mean(all_results['long_chain']['avg_wait'])) / base_wait) * 100
    wait_improve_nogroup = ((base_wait - np.mean(all_results['no_group']['avg_wait'])) / base_wait) * 100
    
    throughput_improve_chain = ((np.mean(all_results['long_chain']['throughput']) - base_throughput) / base_throughput) * 100
    throughput_improve_nogroup = ((np.mean(all_results['no_group']['throughput']) - base_throughput) / base_throughput) * 100
    
    report_lines.append(f"\n等待时间改进对比 (以奇偶分组为基准):")
    report_lines.append(f"  ├─ 长链结构: ▼ {wait_improve_chain:.1f}%")
    report_lines.append(f"  └─ 不分组: ▼ {wait_improve_nogroup:.1f}%")
    
    report_lines.append(f"\n吞吐量改进对比 (以奇偶分组为基准):")
    report_lines.append(f"  ├─ 长链结构: ▲ {throughput_improve_chain:.1f}%")
    report_lines.append(f"  └─ 不分组: ▲ {throughput_improve_nogroup:.1f}%")
    
    report_lines.append("\n" + "=" * 80)
    report_lines.append("结论")
    report_lines.append("=" * 80)
    
    if np.mean(all_results['long_chain']['avg_wait']) < np.mean(all_results['no_group']['avg_wait']):
        report_lines.append("✅ 长链结构在等待时间上优于不分组策略")
    else:
        report_lines.append("⚠️ 不分组策略在等待时间上略优")
    
    if np.mean(all_results['long_chain']['throughput']) > np.mean(all_results['no_group']['throughput']):
        report_lines.append("✅ 长链结构在吞吐量上优于不分组策略")
    else:
        report_lines.append("⚠️ 不分组策略在吞吐量上略优")
    
    report_lines.append("\n📊 效率排序:")
    wait_times = [
        ('奇偶分组', np.mean(all_results['odd_even']['avg_wait'])),
        ('长链结构', np.mean(all_results['long_chain']['avg_wait'])),
        ('不分组', np.mean(all_results['no_group']['avg_wait']))
    ]
    wait_times.sort(key=lambda x: x[1])
    
    for i, (name, val) in enumerate(wait_times, 1):
        report_lines.append(f"  {i}. {name}: {val:.2f}秒")
    
    print("\n".join(report_lines))
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_file = f'elevator_strategy_comparison_report_{timestamp}.txt'
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(report_lines))
    print(f"\n报告已保存: {report_file}")
    
    print(f"\n图表已保存: {chart_file}")
    print("\n" + "=" * 80)
    print("实验完成!")
    print("=" * 80)

if __name__ == '__main__':
    main()
