
import argparse
import sys

from config import SimConfig, BuildingConfig, TimeConfig, TrafficConfig
from simulation_optimized import ElevatorSimulationOptimized


def parse_args():
    parser = argparse.ArgumentParser(description='【优化版】宿舍楼电梯仿真系统')
    parser.add_argument('--floors', type=int, default=17, help='总楼层数')
    parser.add_argument('--elevators', type=int, default=4, help='电梯数量')
    parser.add_argument('--capacity', type=int, default=12, help='电梯容量')
    parser.add_argument('--sim-time', type=float, default=300, help='Simulation duration in seconds (default: 300 for quick test)')
    parser.add_argument('--seed', type=int, default=42, help='随机种子')
    parser.add_argument('--morning-lambda', type=float, default=0.50, help='早高峰到达率')
    parser.add_argument('--noon-lambda', type=float, default=0.66, help='午间高峰到达率')
    return parser.parse_args()


def main():
    args = parse_args()

    building_config = BuildingConfig(
        n_floors=args.floors,
        n_elevators=args.elevators,
        capacity=args.capacity
    )

    time_config = TimeConfig()

    traffic_config = TrafficConfig(
        lambda_morning=args.morning_lambda,
        lambda_noon=args.noon_lambda
    )

    sim_config = SimConfig(
        building=building_config,
        time=time_config,
        traffic=traffic_config,
        sim_end=args.sim_time,
        seed=args.seed
    )

    print(f"【优化版】电梯仿真系统配置:")
    print(f"  楼层数: {args.floors}")
    print(f"  电梯数: {args.elevators}")
    print(f"  电梯容量: {args.capacity}")
    print(f"  仿真时长: {args.sim_time}秒")
    print(f"  随机种子: {args.seed}")
    print()
    print(f"优化特性:")
    print(f"  - 任务仓库管理")
    print(f"  - 智能多因素分配器")
    print(f"  - 双电梯深度协作")
    print(f"  - 批量停靠优化")
    print(f"  - ETA预估")
    print()

    sim = ElevatorSimulationOptimized(sim_config)
    stats = sim.run()
    stats.print_summary(args.sim_time)

    return 0


if __name__ == '__main__':
    sys.exit(main())
