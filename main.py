import argparse
import sys

from config import SimConfig, BuildingConfig, TimeConfig, TrafficConfig
from simulation import ElevatorSimulation

def parse_args():
    parser = argparse.ArgumentParser(description='宿舍楼电梯仿真系统')
    parser.add_argument('--floors', type=int, default=17, help='总楼层数')
    parser.add_argument('--elevators', type=int, default=4, help='电梯数量')
    parser.add_argument('--capacity', type=int, default=12, help='电梯容量')
    parser.add_argument('--sim-time', type=float, default=300, help='Simulation duration in seconds (default: 300 for quick test)')
    parser.add_argument('--seed', type=int, default=42, help='随机种子')
    parser.add_argument('--morning-lambda', type=float, default=0.50, help='早高峰到达率')
    parser.add_argument('--noon-lambda', type=float, default=0.66, help='午间高峰到达率')
    parser.add_argument('--animate', action='store_true', help='生成动画')
    parser.add_argument('--output', type=str, default='elevator_animation.gif', help='动画输出文件')
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

    print(f"电梯仿真系统配置:")
    print(f"  楼层数: {args.floors}")
    print(f"  电梯数: {args.elevators}")
    print(f"  电梯容量: {args.capacity}")
    print(f"  仿真时长: {args.sim_time}秒")
    print(f"  随机种子: {args.seed}")
    print()

    if args.animate:
        from animation import run_simulation_with_animation, ElevatorAnimator
        import matplotlib.pyplot as plt

        print("正在运行仿真并生成动画...")
        recorder, _ = run_simulation_with_animation(sim_config, sim_end=args.sim_time)

        print(f"仿真完成，共 {recorder.get_frame_count()} 帧")
        print("正在生成动画...")

        animator = ElevatorAnimator(sim_config, recorder)
        anim = animator.create_animation(interval=100, output_file=args.output)

        print(f"动画已保存为 {args.output}")
        plt.show()
    else:
        sim = ElevatorSimulation(sim_config)
        stats = sim.run()
        stats.print_summary(args.sim_time)

    return 0

if __name__ == '__main__':
    sys.exit(main())
