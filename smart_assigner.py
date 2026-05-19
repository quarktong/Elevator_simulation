from typing import Dict, List, Optional, Tuple
from enum import Enum
from models import HallCall, Direction, ElevatorState, ElevatorSnapshot
from config import SimConfig
from task_warehouse import TaskWarehouse

ELEVATOR_GROUPS = {'odd': [1, 2], 'even': [3, 4]}

class TriggerType(Enum):
    NEW_CALL = "new_call"
    ELEVATOR_STATE_CHANGE = "elevator_state_change"
    PERIODIC = "periodic"

class SmartAssigner:
    def __init__(self, config: SimConfig, task_warehouse: TaskWarehouse):
        self.config = config
        self.task_warehouse = task_warehouse
        self.weights = {'waiting_time': 0.3, 'distance': 0.25, 'load_balance': 0.2, 
                        'direction_consistency': 0.15, 'prediction_value': 0.1}
        self.reassign_count = 0
        self.prediction_hits = 0
        self.periodic_interval = 5.0
        self.last_periodic_time = 0.0

    def set_weights(self, period: str):
        if period in ["morning_peak", "noon_peak"]:
            self.weights = {'waiting_time': 0.35, 'distance': 0.2, 'load_balance': 0.25, 
                            'direction_consistency': 0.15, 'prediction_value': 0.05}
        else:
            self.weights = {'waiting_time': 0.25, 'distance': 0.3, 'load_balance': 0.15, 
                            'direction_consistency': 0.2, 'prediction_value': 0.1}

    def compute_score(self, call: HallCall, elevator_id: int, 
                     elevator_snapshot: ElevatorSnapshot, 
                     current_time: float, period: str) -> float:
        wait_time = current_time - call.request_time
        wait_time_factor = min(wait_time / self.config.max_wait_time, 1.0)
        distance = abs(elevator_snapshot.floor - call.floor)
        distance_factor = 1.0 - (distance / self.config.building.n_floors)
        load_factor = 1.0 - (elevator_snapshot.passenger_count / self.config.building.elevator_capacity)
        
        direction_factor = 0.0
        if elevator_snapshot.state == ElevatorState.IDLE:
            direction_factor = 0.5
        elif (elevator_snapshot.direction == call.direction):
            direction_factor = 1.0
        
        prediction_factor = min(self.task_warehouse.get_prediction(period, call.floor, call.direction.value) / 10.0, 1.0)
        
        return (self.weights['waiting_time'] * wait_time_factor +
                self.weights['distance'] * distance_factor +
                self.weights['load_balance'] * load_factor +
                self.weights['direction_consistency'] * direction_factor +
                self.weights['prediction_value'] * prediction_factor)

    def determine_elevator_group(self, call: HallCall) -> List[int]:
        return [1, 2] if (call.floor % 2 == 1 or call.floor == 1) else [3, 4]

    def check_collaboration_state(self, elevators: Dict[int, ElevatorSnapshot]) -> Dict[str, List[int]]:
        state_info = {'separated': [], 'following': [], 'converging': []}
        for _, elevator_ids in ELEVATOR_GROUPS.items():
            if len(elevator_ids) < 2 or elevator_ids[0] not in elevators or elevator_ids[1] not in elevators:
                continue
            e1, e2 = elevators[elevator_ids[0]], elevators[elevator_ids[1]]
            distance = abs(e1.floor - e2.floor)
            same_direction = e1.direction == e2.direction
            key = 'separated' if (distance > 4 and not same_direction) or (distance <= 4 and not same_direction) else \
                  'converging' if distance > 4 else 'following'
            state_info[key].extend(elevator_ids)
        return state_info

    def assign(self, elevators: Dict[int, ElevatorSnapshot], 
              current_time: float, trigger_type: TriggerType,
              period: str = "normal") -> List[Tuple[HallCall, int]]:
        self.set_weights(period)
        assignments = []
        for call in self.task_warehouse.get_waiting_calls():
            best_elevator, best_score = None, -1.0
            for elevator_id in self.determine_elevator_group(call):
                if elevator_id not in elevators:
                    continue
                score = self.compute_score(call, elevator_id, elevators[elevator_id], current_time, period)
                if score > best_score:
                    best_score, best_elevator = score, elevator_id
            if best_elevator is not None and best_score > 0.1:
                self.task_warehouse.assign_to_elevator(call, best_elevator)
                assignments.append((call, best_elevator))
        if trigger_type == TriggerType.PERIODIC:
            assignments.extend(self.periodic_reassign(elevators, current_time))
        return assignments

    def periodic_reassign(self, elevators: Dict[int, ElevatorSnapshot], 
                         current_time: float) -> List[Tuple[HallCall, int]]:
        if current_time - self.last_periodic_time < self.periodic_interval:
            return []
        self.last_periodic_time = current_time
        reassignments = []
        for _, elevator_ids in ELEVATOR_GROUPS.items():
            loads = {eid: len(self.task_warehouse.get_elevator_tasks(eid)) 
                    for eid in elevator_ids if eid in elevators}
            if len(loads) >= 2:
                max_eid = max(loads.items(), key=lambda x: x[1])[0]
                min_eid = min(loads.items(), key=lambda x: x[1])[0]
                if loads[max_eid] - loads[min_eid] >= 2:
                    tasks = self.task_warehouse.get_elevator_tasks(max_eid)
                    if tasks:
                        self.task_warehouse.reassign_task(tasks[-1], max_eid, min_eid)
                        reassignments.append((tasks[-1], min_eid))
                        self.reassign_count += 1
        return reassignments

    def get_statistics(self) -> Dict:
        return {'reassign_count': self.reassign_count, 'prediction_hits': self.prediction_hits}
