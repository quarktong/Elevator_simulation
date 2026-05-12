
import simpy
from typing import Optional, List, Dict
from dataclasses import dataclass, field

from config import SimConfig, TimePeriod
from models import Passenger, HallCall, CarCall, Direction, ElevatorState, ElevatorSnapshot, PassengerState


@dataclass
class ElevatorOptimized:
    """
    优化版电梯：在原版SCAN基础上增加以下特性
    
    - 批量停靠优化
    - 顺路性判断
    - ETA预估
    - 任务仓库集成
    """
    elevator_id: int
    is_odd_group: bool
    config: SimConfig
    env: simpy.Environment
    call_store: simpy.Store
    statistics: 'StatisticsOptimized'
    task_warehouse: 'TaskWarehouse' = None

    position: float = 1.0
    direction: Direction = Direction.IDLE
    state: ElevatorState = ElevatorState.IDLE
    passengers: List[Passenger] = field(default_factory=list)
    car_calls: set = field(default_factory=set)
    hall_calls: Dict[int, HallCall] = field(default_factory=dict)
    
    # 优化特性统计
    batch_stop_count: int = 0
    eta_used_count: int = 0

    def __post_init__(self):
        self.served_floors = self.config.building.get_service_floors(self.is_odd_group)
        self.capacity = self.config.building.capacity

    @property
    def is_full(self) -&gt; bool:
        return len(self.passengers) &gt;= self.capacity

    @property
    def is_idle(self) -&gt; bool:
        return self.state == ElevatorState.IDLE

    def add_car_call(self, floor: int, passenger: Passenger):
        self.car_calls.add(floor)
        passenger.state = PassengerState.BOARDING

    def assign_call(self, call: HallCall):
        self.hall_calls[call.floor] = call
        call.assign_to(self.elevator_id)
        self.call_store.put(call)
        
        # 同步到任务仓库
        if self.task_warehouse:
            self.task_warehouse.assign_to_elevator(call, self.elevator_id)

    def release_call(self, floor: int):
        if floor in self.hall_calls:
            call = self.hall_calls[floor]
            del self.hall_calls[floor]
            
            # 同步到任务仓库
            if self.task_warehouse:
                self.task_warehouse.complete_task(call, self.elevator_id, self.env.now)

    def estimate_eta(self, target_floor: int) -&gt; float:
        """
        预估到达目标楼层的时间
        
        Args:
            target_floor: 目标楼层
            
        Returns:
            预计到达时间（秒）
        """
        current_floor = round(self.position)
        if current_floor == target_floor:
            return 0.0
        
        # 基础运行时间
        distance = abs(target_floor - current_floor)
        eta = distance * self.config.time.t_travel
        
        # 预估停靠时间
        # 简化计算：假设每层停靠约5秒
        estimated_stops = min(distance, 3)
        eta += estimated_stops * 5.0
        
        self.eta_used_count += 1
        return eta

    def check_on_route(self, call_floor: int) -&gt; bool:
        """
        判断呼叫是否在当前运行路径上
        
        Args:
            call_floor: 呼叫楼层
            
        Returns:
            是否顺路
        """
        if self.direction == Direction.IDLE:
            return True
        
        current = round(self.position)
        
        if self.direction == Direction.UP:
            return call_floor &gt;= current
        else:
            return call_floor &lt;= current

    def _get_next_stop(self) -&gt; Optional[int]:
        all_calls = set(self.car_calls)
        for call in self.hall_calls.values():
            if not call.completed:
                all_calls.add(call.floor)

        if not all_calls:
            return None

        current = round(self.position)

        if self.direction == Direction.UP:
            candidates = [f for f in all_calls if f &gt;= current and f in self.served_floors]
            if candidates:
                return min(candidates)
            candidates = [f for f in all_calls if f &lt; current and f in self.served_floors]
            if candidates:
                return max(candidates)
        elif self.direction == Direction.DOWN:
            candidates = [f for f in all_calls if f &lt;= current and f in self.served_floors]
            if candidates:
                return max(candidates)
            candidates = [f for f in all_calls if f &gt; current and f in self.served_floors]
            if candidates:
                return min(candidates)
        else:
            if current in all_calls:
                return current
            closer_up = min([f for f in all_calls if f &gt;= current], default=None)
            closer_down = max([f for f in all_calls if f &lt;= current], default=None)
            if closer_up is None:
                return closer_down
            if closer_down is None:
                return closer_up
            return closer_up if abs(closer_up - current) &lt; abs(closer_down - current) else closer_down

        return None

    def _should_stop_at(self, floor: int) -&gt; bool:
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

    def _set_direction_to_target(self, target: Optional[int]):
        if target is None:
            self.direction = Direction.IDLE
        elif target &gt; round(self.position):
            self.direction = Direction.UP
        elif target &lt; round(self.position):
            self.direction = Direction.DOWN
        else:
            self.direction = Direction.IDLE

    def _handle_door_open(self, floor: int):
        """
        开门处理：批量停靠优化
        
        当有多个上下车乘客时，一次性处理
        """
        self.state = ElevatorState.DOOR_OPEN
        open_time = self.config.time.get_open_time(floor)
        yield self.env.timeout(open_time)

        # 批量下车
        alighting_passengers = [p for p in self.passengers if p.destination == floor]
        for p in alighting_passengers:
            p.alight_time = self.env.now
            p.state = PassengerState.ALIGHTING
            self.passengers.remove(p)
            self.car_calls.discard(floor)
            self.statistics.record_alighting(p)
        
        if alighting_passengers:
            self.batch_stop_count += 1

        # 批量上车
        passengers_to_board = []
        for call_floor, call in list(self.hall_calls.items()):
            if call_floor == floor and not call.completed:
                if not self.is_full:
                    for p in call.passengers[:]:
                        if p.origin == floor and len(self.passengers) &lt; self.capacity:
                            passengers_to_board.append((p, call))

        for p, call in passengers_to_board:
            p.board_time = self.env.now
            p.state = PassengerState.RIDING
            self.passengers.append(p)
            self.car_calls.add(p.destination)
            call.passengers.remove(p)
            if not call.passengers:
                call.completed = True
                self.release_call(call_floor)

        yield self.env.timeout(self.config.time.t_close)
        self.state = ElevatorState.IDLE

    def _move_to_floor(self, target: int):
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

    def get_snapshot(self) -&gt; ElevatorSnapshot:
        return ElevatorSnapshot(
            id=self.elevator_id,
            position=self.position,
            direction=self.direction,
            n_passengers=len(self.passengers),
            state=self.state,
            car_calls=frozenset(self.car_calls),
            hall_calls=frozenset(self.hall_calls.keys())
        )
