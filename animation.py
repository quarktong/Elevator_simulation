import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.patches import Rectangle, FancyBboxPatch, Circle
from matplotlib.collections import PatchCollection
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

from models import Passenger, PassengerState, ElevatorSnapshot, Direction, ElevatorState
from config import SimConfig

@dataclass
class PassengerSnapshot:
    passenger_id: int
    floor: int
    state: PassengerState
    time: float
    elevator_id: Optional[int] = None

@dataclass
class AnimationFrame:
    time: float
    elevator_snapshots: List[ElevatorSnapshot]
    passenger_snapshots: List[PassengerSnapshot]

class AnimationRecorder:
    def __init__(self, config: SimConfig):
        self.config = config
        self.frames: List[AnimationFrame] = []
        self._current_passenger_states: Dict[int, PassengerSnapshot] = {}
        self._passenger_id_to_info: Dict[int, Tuple[int, int, Optional[int]]] = {}

    def record_elevator_snapshots(self, snapshots: List[ElevatorSnapshot], current_time: float):
        passenger_snapshots = []
        for pid, p_info in self._passenger_id_to_info.items():
            origin, destination, elev_id = p_info
            state = PassengerState.ARRIVED
            if pid in self._current_passenger_states:
                state = self._current_passenger_states[pid].state
            floor = origin
            if state == PassengerState.RIDING:
                floor = destination
            passenger_snapshots.append(PassengerSnapshot(
                passenger_id=pid,
                floor=floor,
                state=state,
                time=current_time,
                elevator_id=elev_id
            ))

        frame = AnimationFrame(
            time=current_time,
            elevator_snapshots=snapshots,
            passenger_snapshots=passenger_snapshots
        )
        self.frames.append(frame)

    def register_passenger(self, passenger: Passenger, elevator_id: Optional[int] = None):
        self._passenger_id_to_info[passenger.id] = (passenger.origin, passenger.destination, elevator_id)

    def update_passenger_state(self, passenger_id: int, state: PassengerState, current_time: float, elevator_id: Optional[int] = None):
        if passenger_id in self._passenger_id_to_info:
            origin, destination, _ = self._passenger_id_to_info[passenger_id]
            if elevator_id is not None:
                self._passenger_id_to_info[passenger_id] = (origin, destination, elevator_id)
            else:
                _, _, existing_elevator = self._passenger_id_to_info[passenger_id]
                elevator_id = existing_elevator
            floor = origin
            if state == PassengerState.RIDING:
                floor = destination
            self._current_passenger_states[passenger_id] = PassengerSnapshot(
                passenger_id=passenger_id,
                floor=floor,
                state=state,
                time=current_time,
                elevator_id=elevator_id
            )

    def get_frame_count(self) -> int:
        return len(self.frames)

    def get_times(self) -> List[float]:
        return [f.time for f in self.frames]

class ElevatorAnimator:
    COLORS = {
        'elevator_odd': '#3498db',
        'elevator_even': '#2ecc71',
        'elevator_idle': '#95a5a6',
        'passenger_waiting': '#e74c3c',
        'passenger_riding': '#f39c12',
        'passenger_done': '#27ae60',
        'floor': '#ecf0f1',
        'wall': '#34495e',
    }

    def __init__(self, config: SimConfig, recorder: AnimationRecorder):
        self.config = config
        self.recorder = recorder
        self.n_floors = config.building.n_floors
        self.n_elevators = config.building.n_elevators

    def create_animation(self, interval: int = 100, output_file: Optional[str] = None) -> animation.FuncAnimation:
        fig, ax = plt.subplots(figsize=(16, 10))

        elevator_width = 2.0
        elevator_spacing = 2.5
        total_width = self.n_elevators * elevator_spacing
        ax.set_xlim(-1, total_width + 1)
        ax.set_ylim(0, self.n_floors + 1)
        ax.set_xlabel('Elevator', fontsize=12)
        ax.set_ylabel('Floor', fontsize=12)
        ax.set_title('Elevator Simulation Animation', fontsize=14)
        ax.set_yticks(range(1, self.n_floors + 1))
        ax.grid(True, alpha=0.3)

        for floor in range(1, self.n_floors + 1):
            floor_type = 'odd' if floor % 2 == 1 else 'even'
            color = '#ddd' if floor_type == 'odd' else '#f8f8f8'
            ax.axhspan(floor - 0.5, floor + 0.5, color=color, alpha=0.3)

        elevator_patches = []
        for i in range(self.n_elevators):
            x_pos = i * elevator_spacing + elevator_spacing / 2 - elevator_width / 2
            rect = FancyBboxPatch(
                (i * elevator_spacing + 0.25, 1), elevator_width, 1,
                boxstyle="round,pad=0.02,rounding_size=0.2",
                facecolor=self.COLORS['elevator_idle'],
                edgecolor='black',
                linewidth=1.5,
                alpha=0.8
            )
            ax.add_patch(rect)
            elevator_patches.append(rect)

            ax.text(i * elevator_spacing + elevator_spacing / 2, 0.3, f'E{i+1}', ha='center', va='center', fontsize=10, fontweight='bold')

        passenger_patches: Dict[int, Circle] = {}
        direction_texts = []
        for i in range(self.n_elevators):
            direction_texts.append(ax.text(i * elevator_spacing + elevator_spacing / 2, self.n_floors + 0.5, '', ha='center', va='bottom', fontsize=12))

        info_text = ax.text(0.02, 0.98, '', transform=ax.transAxes,
                            verticalalignment='top', fontsize=10,
                            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

        def update(frame_idx):
            if frame_idx >= len(self.recorder.frames):
                return elevator_patches + list(passenger_patches.values()) + direction_texts + [info_text]

            frame = self.recorder.frames[frame_idx]

            for i, elev_patch in enumerate(elevator_patches):
                if i < len(frame.elevator_snapshots):
                    snapshot = frame.elevator_snapshots[i]
                    position = snapshot.position

                    if snapshot.state == ElevatorState.MOVING:
                        color = self.COLORS['elevator_odd'] if i < 2 else self.COLORS['elevator_even']
                    elif snapshot.state == ElevatorState.DOOR_OPEN:
                        color = '#9b59b6'
                    else:
                        color = self.COLORS['elevator_idle']

                    elev_patch.set_facecolor(color)

                    elev_patch.set_y(position - 0.5)

                    if snapshot.state == ElevatorState.MOVING:
                        if snapshot.direction == Direction.UP:
                            direction_texts[i].set_text('↑')
                            direction_texts[i].set_color('#27ae60')
                        elif snapshot.direction == Direction.DOWN:
                            direction_texts[i].set_text('↓')
                            direction_texts[i].set_color('#e74c3c')
                        else:
                            direction_texts[i].set_text('')
                    elif snapshot.state == ElevatorState.DOOR_OPEN:
                        direction_texts[i].set_text('◐')
                        direction_texts[i].set_color('#9b59b6')
                    else:
                        direction_texts[i].set_text('')

                    passenger_count = snapshot.n_passengers
                    if passenger_count > 0:
                        elev_patch.set_label(f'{passenger_count}p')
                    else:
                        elev_patch.set_label('')
                else:
                    elev_patch.set_y(0.5)

            current_pids = set()
            for p_snap in frame.passenger_snapshots:
                current_pids.add(p_snap.passenger_id)

                if p_snap.state == PassengerState.DONE or p_snap.state == PassengerState.ABANDONED:
                    if p_snap.passenger_id in passenger_patches:
                        passenger_patches[p_snap.passenger_id].remove()
                        del passenger_patches[p_snap.passenger_id]
                    continue

                x_pos = self._get_passenger_x(p_snap)
                y_pos = p_snap.floor

                if p_snap.passenger_id in passenger_patches:
                    passenger_patches[p_snap.passenger_id].center = (x_pos, y_pos)
                else:
                    if p_snap.state == PassengerState.WAITING:
                        color = self.COLORS['passenger_waiting']
                    elif p_snap.state == PassengerState.RIDING:
                        color = self.COLORS['passenger_riding']
                    else:
                        color = '#95a5a6'

                    circle = Circle((x_pos, y_pos), 0.2, facecolor=color,
                                   edgecolor='black', linewidth=0.5, alpha=0.8)
                    ax.add_patch(circle)
                    passenger_patches[p_snap.passenger_id] = circle

            for pid in list(passenger_patches.keys()):
                if pid not in current_pids:
                    passenger_patches[pid].remove()
                    del passenger_patches[pid]

            waiting_count = sum(1 for p in frame.passenger_snapshots if p.state == PassengerState.WAITING)
            riding_count = sum(1 for p in frame.passenger_snapshots if p.state == PassengerState.RIDING)
            done_count = sum(1 for p in frame.passenger_snapshots if p.state in [PassengerState.DONE, PassengerState.ABANDONED])

            info_text.set_text(f'Time: {frame.time:.1f}s\n'
                              f'Waiting: {waiting_count}\n'
                              f'Riding: {riding_count}\n'
                              f'Completed: {done_count}')

            return elevator_patches + list(passenger_patches.values()) + direction_texts + [info_text]

        anim = animation.FuncAnimation(fig, update, frames=len(self.recorder.frames),
                                        interval=interval, blit=True)

        if output_file:
            if output_file.endswith('.gif'):
                anim.save(output_file, writer='pillow', fps=10)
            elif output_file.endswith('.mp4'):
                anim.save(output_file, writer='ffmpeg', fps=10)
            else:
                anim.save(output_file + '.gif', writer='pillow', fps=10)

        return anim

    def _get_passenger_x(self, p_snap: PassengerSnapshot) -> float:
        elevator_spacing = 2.5

        if p_snap.elevator_id is not None:
            base_x = p_snap.elevator_id * elevator_spacing + elevator_spacing / 2
            hash_id = hash(p_snap.passenger_id)
            offset = (hash_id % 3 - 1) * 0.2
            return base_x + offset

        is_odd_group = p_snap.floor % 2 == 1 if p_snap.floor != 1 else True
        if is_odd_group:
            base_x = elevator_spacing / 2
        else:
            base_x = 3 * elevator_spacing / 2

        hash_id = hash(p_snap.passenger_id)
        offset = (hash_id % 5 - 2) * 0.15

        return base_x + offset

def run_simulation_with_animation(config: SimConfig, sim_end: Optional[float] = None) -> Tuple[AnimationRecorder, List]:
    import simpy
    from elevator import Elevator
    from dispatcher import Dispatcher
    from passenger_generator import PassengerGenerator
    from statistics import Statistics

    if sim_end is not None:
        config.sim_end = sim_end

    env = simpy.Environment()
    recorder = AnimationRecorder(config)
    stats = Statistics()

    call_stores = [simpy.Store(env) for _ in range(config.building.n_elevators)]
    elevators = []

    for i in range(config.building.n_elevators):
        is_odd_group = i < 2
        elevator = Elevator(
            elevator_id=i + 1,
            is_odd_group=is_odd_group,
            config=config,
            env=env,
            call_store=call_stores[i],
            statistics=stats
        )
        elevators.append(elevator)
        env.process(elevator.run())

    dispatcher = Dispatcher(config=config, elevators=elevators)

    generator = PassengerGeneratorWithAnimation(
        env=env,
        config=config,
        dispatcher=dispatcher,
        statistics=stats,
        recorder=recorder
    )
    env.process(generator.run())

    env.process(_monitor_process_with_animation(env, elevators, recorder))

    env.run(until=config.sim_end)

    return recorder, []

class PassengerGeneratorWithAnimation:
    def __init__(self, env, config, dispatcher, statistics, recorder):
        self.env = env
        self.config = config
        self.dispatcher = dispatcher
        self.statistics = statistics
        self.recorder = recorder
        self.rng = np.random.default_rng(config.seed)

    def run(self):
        passenger_id = 0
        while True:
            current_time = self.env.now
            period = self.config.get_period(current_time)
            lam = self.config.get_lambda(current_time)

            interval = self.rng.exponential(1.0 / lam) if lam > 0 else float('inf')
            yield self.env.timeout(interval)

            passenger = self._generate_passenger(period)
            if passenger is None:
                continue

            passenger_id += 1
            passenger.id = passenger_id

            self.statistics.record_arrival(passenger)
            self.recorder.register_passenger(passenger)
            self.recorder.update_passenger_state(passenger_id, PassengerState.ARRIVED, self.env.now)

            elevator_id = self.dispatcher.dispatch(passenger)
            if elevator_id is not None:
                self.recorder.update_passenger_state(passenger_id, PassengerState.WAITING, self.env.now, elevator_id)
            else:
                self._handle_no_elevator_available(passenger)
                self.recorder.update_passenger_state(passenger_id, PassengerState.ABANDONED, self.env.now)

    def _generate_passenger(self, period):
        from models import Passenger, PassengerState
        origin, destination = self._sample_origin_destination(period)
        if origin is None or destination is None:
            return None

        from models import Direction
        passenger = Passenger(
            id=0,
            origin=origin,
            destination=destination,
            request_time=self.env.now,
            state=PassengerState.ARRIVED
        )
        return passenger

    def _sample_origin_destination(self, period):
        from config import TimePeriod
        current_time = self.env.now
        use_prob = self.rng.random()

        if period == TimePeriod.MORNING_PEAK:
            return self._sample_morning_peak(use_prob)
        elif period == TimePeriod.NOON_PEAK:
            return self._sample_noon_peak()
        else:
            return self._sample_off_peak()

    def _sample_morning_peak(self, use_prob: float):
        if use_prob > 0.27:
            return None, None

        if use_prob <= 0:
            floor_range = (1, 4)
        elif use_prob <= 0.10 * 2 / 17:
            floor_range = (5, 6)
        elif use_prob <= (0.10 * 2 + 0.30 * 4) / 17:
            floor_range = (7, 10)
        else:
            floor_range = (11, 17)

        origin = self.rng.integers(floor_range[0], floor_range[1] + 1)
        destination = 1
        return origin, destination

    def _sample_noon_peak(self):
        origin = 1
        high_floors = list(range(10, 18))
        if self.rng.random() < 0.3:
            high_floors = list(range(5, 10))
        destination = self.rng.choice(high_floors)
        return origin, destination

    def _sample_off_peak(self):
        origin = self.rng.integers(1, self.config.building.n_floors + 1)
        destination = self.rng.integers(1, self.config.building.n_floors + 1)
        while destination == origin:
            destination = self.rng.integers(1, self.config.building.n_floors + 1)
        return origin, destination

    def _handle_no_elevator_available(self, passenger):
        from models import PassengerState
        passenger.state = PassengerState.ABANDONED
        self.statistics.record_abandoned(passenger)

def _monitor_process_with_animation(env, elevators, recorder):
    while True:
        yield env.timeout(1.0)
        snapshots = [e.get_snapshot() for e in elevators]
        recorder.record_elevator_snapshots(snapshots, env.now)

if __name__ == '__main__':
    from config import SimConfig

    print("运行电梯仿真并生成动画...")
    config = SimConfig.default()
    config.sim_end = 300

    recorder, _ = run_simulation_with_animation(config, sim_end=300)

    print(f"仿真完成，共 {recorder.get_frame_count()} 帧")

    animator = ElevatorAnimator(config, recorder)

    print("正在生成动画...")
    anim = animator.create_animation(interval=100, output_file='elevator_animation.gif')

    print("动画已保存为 elevator_animation.gif")
    plt.show()