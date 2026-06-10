import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
from config import SimConfig, BuildingConfig, TimeConfig, TrafficConfig
from models import Passenger, HallCall, Direction, ElevatorState
from typing import List, Optional

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

# 先定义我们需要的电梯和调度类
class SimpleElevator:
    """简化电梯类"""
    def __init__(self, elevator_id: int, served_floors: set, config: SimConfig):
        self.elevator_id = elevator_id
        self.served_floors = served_floors
        self.config = config
        self.position = 1.0
        self.direction = Direction.IDLE
        self.passengers = []
        self.car_calls = set()
        self.hall_calls = dict()
        self.capacity = config.building.capacity
        self.moving_time = 0
        self.idle_time = 0

    @property
    def is_idle(self):
        return len(self.passengers) == 0 and not self.hall_calls

    def can_serve(self, floor: int) -> bool:
        return floor in self.served_floors

    def assign_call(self, call: HallCall):
        self.hall_calls[call.floor] = call

    def release_call(self, floor: int):
        if floor in self.hall_calls:
            del self.hall_calls[floor]

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

def simulate_single_run(strategy: str, seed: int, sim_time: int = 300):
    """运行单次仿真"""
    rng = np.random.default_rng(seed)
    
    # 配置
    building_config = BuildingConfig(n_floors=17, n_elevators=4, capacity=12)
    time_config = TimeConfig()
    traffic_config = TrafficConfig(lambda_morning=0.5, lambda_noon=0.66)
    config = SimConfig(building=building_config, time=time_config, traffic=traffic_config, sim_end=sim_time, seed=seed)
    
    # 创建电梯
    floor_groups = create_floor_groups(strategy)
    elevators = [SimpleElevator(i+1, floor_groups[i], config) for i in range(4)]
    
    # 统计
    wait_times = []
    board_times = []
    completed_passengers = []
    passengers = []
    current_time = 0.0
    
    # 事件队列中的乘客
    pending_calls = []
    
    while current_time < sim_time:
        # 生成乘客
        lam = 0.15  # 到达率
        interval = rng.exponential(1.0 / lam) if lam > 0 else float('inf')
        next_arrival = current_time + interval
        
        # 找到下一个事件：要么是乘客到达，要么是电梯完成
        # 简化：我们就先处理乘客生成，再处理电梯
        if next_arrival < sim_time:
            current_time = next_arrival
            origin = rng.integers(1, 18)
            destination = rng.integers(1, 18)
            while destination == origin:
                destination = rng.integers(1, 18)
            
            passenger = {
                'id': len(passengers),
                'origin': origin,
                'destination': destination,
                'request_time': current_time,
                'board_time': None,
                'alight_time': None
            }
            passengers.append(passenger)
            pending_calls.append(passenger)
        
        # 处理电梯 - 简化版本
        # 对每台电梯，简单地移动到最近的呼叫
        time_advance = 0.1
        for elev in elevators:
            if elev.hall_calls or elev.passengers:
                # 找目标层
                target = None
                if elev.passengers:
                    # 先处理已在电梯里的乘客
                    dests = [p['destination'] for p in elev.passengers]
                    if dests:
                        # SCAN算法
                        if elev.direction == Direction.UP:
                            above = [d for d in dests if d >= round(elev.position)]
                            target = min(above) if above else max(dests)
                        elif elev.direction == Direction.DOWN:
                            below = [d for d in dests if d <= round(elev.position)]
                            target = max(below) if below else min(dests)
                        else:
                            target = min(dests, key=lambda d: abs(d - round(elev.position)))
                elif elev.hall_calls:
                    # 处理呼梯
                    floors = list(elev.hall_calls.keys())
                    target = min(floors, key=lambda f: abs(f - round(elev.position)))
                
                if target is not None:
                    # 移动到目标
                    distance = abs(target - round(elev.position))
                    if distance > 0:
                        move_time = distance * 2.31
                        elev.moving_time += min(move_time, time_advance)
                        if elev.moving_time >= move_time:
                            elev.position = target
                            elev.moving_time -= move_time
                        else:
                            elev.position += np.sign(target - elev.position) * min(time_advance/2.31, distance)
                    else:
                        # 在这一层，处理上下客
                        # 下客
                        remaining = []
                        for p in elev.passengers:
                            if p['destination'] == target:
                                p['alight_time'] = current_time
                                if p['board_time'] is not None:
                                    board_times.append(current_time - p['board_time'])
                                completed_passengers.append(p)
                            else:
                                remaining.append(p)
                        elev.passengers = remaining
                        
                        # 上客
                        to_board = [p for p in pending_calls 
                                  if p['origin'] == target and p['board_time'] is None
                                  and target in elev.served_floors]
                        for p in to_board[:12-len(elev.passengers)]:
                            p['board_time'] = current_time
                            wait_times.append(current_time - p['request_time'])
                            elev.passengers.append(p)
                            elev.car_calls.add(p['destination'])
                        # 更新pending_calls
                        pending_calls = [p for p in pending_calls if p['board_time'] is None and p not in elev.passengers]
                        
                        # 更新方向
                        if elev.passengers:
                            next_dest = min([p['destination'] for p in elev.passengers], 
                                          key=lambda d: abs(d - target))
                            elev.direction = Direction.UP if next_dest > target else Direction.DOWN
                        else:
                            elev.direction = Direction.IDLE
            else:
                elev.idle_time += time_advance
        
        # 分配呼梯给电梯
        for p in pending_calls:
            if p['board_time'] is None:
                # 找能服务该层的电梯
                candidates = [e for e in elevators if e.can_serve(p['origin'])]
                if candidates:
                    # 简单选距离最近的
                    best_elev = min(candidates, key=lambda e: abs(e.position - p['origin']))
                    if best_elev.can_serve(p['origin']):
                        # 检查是否已经分配过
                        already = any(p in call.passengers for call in best_elev.hall_calls.values())
                        if not already:
                            call = HallCall(
                                floor=p['origin'],
                                direction=Direction.UP if p['destination'] > p['origin'] else Direction.DOWN,
                                time=p['request_time'],
                                passengers=[p]
                            )
                            best_elev.assign_call(call)
        
        current_time += time_advance
    
    # 计算统计
    avg_wait = np.mean(wait_times) if wait_times else 0
    max_wait = np.max(wait_times) if wait_times else 0
    avg_board = np.mean(board_times) if board_times else 0
    throughput = len(wait_times) / sim_time if wait_times else 0
    total_time = sum(e.moving_time + e.idle_time for e in elevators) / 4
    avg_utilization = sum(e.moving_time / sim_time for e in elevators) / 4
    
    return {
        'avg_wait': avg_wait,
        'max_wait': max_wait,
        'avg_board': avg_board,
        'throughput': throughput,
        'utilization': avg_utilization,
        'wait_times': wait_times
    }

def run_multiple_simulations(strategy: str, n_runs: int = 20, sim_time: int = 300):
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
        res = simulate_single_run(strategy, i * 100 + 42, sim_time)
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
        ax1.text(bar.get_x() + bar.get_width()/2., height + 0.5,
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
        ax2.text(bar.get_x() + bar.get_width()/2., height + 0.002,
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
        ax3.text(bar.get_x() + bar.get_width()/2., height + 1,
                f'{height:.1f}s', ha='center', fontsize=10)
    
    # 4. 等待时间分布
    ax4 = plt.subplot(2, 3, 4)
    colors = ['#FF9999', '#66B2FF', '#99FF99']
    labels = ['奇偶分组', '长链结构', '不分组']
    for i, s in enumerate(strategy_names):
        wait_times = np.array(results_dict[s]['all_wait_times'])
        if len(wait_times) > 0:
            ax4.hist(wait_times, bins=30, alpha=0.6, color=colors[i], 
                    label=labels[i], density=True)
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
    
    radar_labels = ['等待时间', '吞吐量', '最大等待', '利用率']
    values = np.array([
        [wait_improve[0], throughput_improve[0], max_improve[0], 0],
        [wait_improve[1], throughput_improve[1], max_improve[1], 
         (np.mean(results_dict['long_chain']['utilization']) - np.mean(results_dict['odd_even']['utilization'])) * 100],
        [wait_improve[2], throughput_improve[2], max_improve[2], 
         (np.mean(results_dict['no_group']['utilization']) - np.mean(results_dict['odd_even']['utilization'])) * 100]
    ])
    
    angles = np.linspace(0, 2 * np.pi, len(radar_labels), endpoint=False).tolist()
    angles += angles[:1]
    
    for i in range(3):
        vals = values[i].tolist()
        vals += vals[:1]
        ax6.plot(angles, vals, 'o-', linewidth=2, 
                label=labels[i],
                color=['#FF9999', '#66B2FF', '#99FF99'][i])
        ax6.fill(angles, vals, alpha=0.25, 
                color=['#FF9999', '#66B2FF', '#99FF99'][i])
    
    ax6.set_xticks(angles[:-1])
    ax6.set_xticklabels(radar_labels, fontsize=11)
    ax6.set_title('效率改进幅度 (vs 奇偶分组)', fontsize=14, fontweight='bold', pad=20)
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
    print("电梯分组策略对比仿真实验 (正确版本)")
    print("=" * 80)
    print(f"实验时间: {datetime.now()}")
    print(f"仿真时长: 300秒/次")
    print(f"实验次数: 20次/策略")
    print("策略对比: 奇偶分组 vs 长链结构 vs 不分组")
    print("=" * 80)
    
    strategies = ['odd_even', 'long_chain', 'no_group']
    all_results = {}
    
    for strategy in strategies:
        print(f"\n正在运行 [{strategy}] 策略...")
        results = run_multiple_simulations(strategy, n_runs=20)
        all_results[strategy] = results
        print(f"  完成 20 次仿真")
        print(f"  平均等待: {np.mean(results['avg_wait']):.1f} ± {np.std(results['avg_wait']):.1f}秒")
        print(f"  平均吞吐量: {np.mean(results['throughput']):.4f} ± {np.std(results['throughput']):.4f}人/秒")
    
    print("\n" + "=" * 80)
    print("生成结果图表...")
    chart_file = plot_results(all_results, strategies, 'elevator_strategy')
    print(f"图表已保存: {chart_file}")
    
    print("\n" + "=" * 80)
    print("仿真结果统计")
    print("=" * 80)
    
    strategy_names = ['奇偶分组', '长链结构', '不分组']
    report_lines = []
    report_lines.append("电梯分组策略对比仿真报告")
    report_lines.append("=" * 80)
    report_lines.append(f"生成时间: {datetime.now()}")
    report_lines.append(f"仿真参数: 300秒/次, 20次/策略")
    report_lines.append("=" * 80)
    
    for strategy, display in zip(strategies, strategy_names):
        results = all_results[strategy]
        avg_wait = np.mean(results['avg_wait'])
        std_wait = np.std(results['avg_wait'])
        max_wait = np.mean(results['max_wait'])
        avg_board = np.mean(results['avg_board'])
        throughput = np.mean(results['throughput'])
        utilization = np.mean(results['utilization']) * 100
        
        report_lines.append(f"\n【{display}】")
        report_lines.append(f"  ├─ 平均等待时间: {avg_wait:.1f} ± {std_wait:.1f}秒")
        report_lines.append(f"  ├─ 最大等待时间: {max_wait:.1f}秒")
        report_lines.append(f"  ├─ 平均乘车时间: {avg_board:.1f}秒")
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
    wait_results = [
        ('奇偶分组', np.mean(all_results['odd_even']['avg_wait'])),
        ('长链结构', np.mean(all_results['long_chain']['avg_wait'])),
        ('不分组', np.mean(all_results['no_group']['avg_wait']))
    ]
    wait_results.sort(key=lambda x: x[1])
    
    for i, (name, val) in enumerate(wait_results, 1):
        report_lines.append(f"  {i}. {name}: {val:.1f}秒")
    
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
