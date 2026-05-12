
import argparse
import sys

from config import SimConfig, BuildingConfig, TimeConfig, TrafficConfig
from simulation import ElevatorSimulation
from simulation_optimized import ElevatorSimulationOptimized


def parse_args():
    parser = argparse.ArgumentParser(description='对比原版与优化版电梯调度算法')
    parser.add_argument('--floors', type=int, default=17, help='总楼层数')
    parser.add_argument('--elevators', type=int, default=4, help='电梯数量')
    parser.add_argument('--capacity', type=int, default=12, help='电梯容量')
    parser.add_argument('--sim-time', type=float, default=300, help='Simulation duration in seconds (default: 300)')
    parser.add_argument('--seed', type=int, default=42, help='随机种子')
    return parser.parse_args()


def main():
    args = parse_args()

    building_config = BuildingConfig(
        n_floors=args.floors,
        n_elevators=args.elevators,
        capacity=args.capacity
    )

    time_config = TimeConfig()

    traffic_config = TrafficConfig()

    sim_config = SimConfig(
        building=building_config,
        time=time_config,
        traffic=traffic_config,
        sim_end=args.sim_time,
        seed=args.seed
    )

    print("=" * 70)
    print("电梯调度算法对比测试")
    print("=" * 70)
    print()

    # 运行原版
    print("\n" + "=" * 70)
    print("【原版】基于SCAN的调度算法")
    print("=" * 70)
    sim_original = ElevatorSimulation(sim_config)
    stats_original = sim_original.run()
    stats_original.print_summary(args.sim_time)

    # 运行优化版
    print("\n" + "=" * 70)
    print("【优化版】智能协作调度算法")
    print("=" * 70)
    sim_optimized = ElevatorSimulationOptimized(sim_config)
    stats_optimized = sim_optimized.run()
    stats_optimized.print_summary(args.sim_time)

    # 对比分析
    print("\n" + "=" * 70)
    print("对比分析总结")
    print("=" * 70)
    
    # 关键指标对比
    print(f"\n平均等待时间:")
    print(f"  原版: {stats_original.get_avg_wait_time():.1f}秒")
    print(f"  优化版: {stats_optimized.get_avg_wait_time():.1f}秒")
    if stats_original.get_avg_wait_time() &gt; 0:
        improvement = (stats_original.get_avg_wait_time() - stats_optimized.get_avg_wait_time()) / stats_original.get_avg_wait_time() * 100
        print(f"  改善: {improvement:+.1f}%")
    
    print(f"\n长等待(&gt;2min)比例:")
    print(f"  原版: {stats_original.get_long_wait_ratio():.1%}")
    print(f"  优化版: {stats_optimized.get_long_wait_ratio():.1%}")
    
    print(f"\n系统吞吐量:")
    print(f"  原版: {stats_original.get_throughput(args.sim_time):.4f}人/秒")
    print(f"  优化版: {stats_optimized.get_throughput(args.sim_time):.4f}人/秒")
    
    # 电梯利用率对比
    print(f"\n电梯利用率对比:")
    util_original = stats_original.get_elevator_utilization(args.sim_time)
    util_optimized = stats_optimized.get_elevator_utilization(args.sim_time)
    for eid in [1, 2, 3, 4]:
        print(f"  电梯{eid}: 原版{util_original.get(eid, 0):.1%} -&gt; 优化版{util_optimized.get(eid, 0):.1%}")
    
    # 负载不平衡度（仅优化版）
    print(f"\n【优化版】同组负载不平衡度:")
    imbalance = stats_optimized.get_group_load_imbalance(args.sim_time)
    print(f"  奇数组: {imbalance['odd']:.1%}")
    print(f"  偶数组: {imbalance['even']:.1%}")
    
    print(f"\n【优化版】优化特性统计:")
    print(f"  任务重分配次数: {stats_optimized.reassign_count}")
    print(f"  批量停靠比例: {stats_optimized.get_batch_stop_ratio():.1%}")
    
    print("\n" + "=" * 70)
    print("测试完成！")
    print("=" * 70)

    return 0


if __name__ == '__main__':
    sys.exit(main())
