from collections import deque
from typing import Dict, List, Optional, Tuple
from models import HallCall, Passenger

class TaskWarehouse:
    def __init__(self):
        self.wait_queue: List[Tuple[float, HallCall]] = []
        self.assigned_tasks: Dict[int, List[HallCall]] = {}
        self.completed_history: deque = deque(maxlen=1000)
        self.historical_data: Dict[str, Dict] = {}

    def add_call(self, call: HallCall, current_time: float, priority: float = 1.0):
        self.wait_queue.append((priority, call))
        self.wait_queue.sort(key=lambda x: x[0], reverse=True)

    def get_waiting_calls(self) -> List[HallCall]:
        return [call for (pri, call) in self.wait_queue]

    def assign_to_elevator(self, call: HallCall, elevator_id: int):
        self.wait_queue = [(pri, c) for (pri, c) in self.wait_queue if c != call]
        if elevator_id not in self.assigned_tasks:
            self.assigned_tasks[elevator_id] = []
        self.assigned_tasks[elevator_id].append(call)

    def unassign_from_elevator(self, call: HallCall, elevator_id: int):
        if elevator_id in self.assigned_tasks:
            self.assigned_tasks[elevator_id] = [c for c in self.assigned_tasks[elevator_id] if c != call]

    def complete_task(self, call: HallCall, elevator_id: int, completion_time: float):
        self.unassign_from_elevator(call, elevator_id)
        self.completed_history.append({
            'call': call,
            'elevator_id': elevator_id,
            'completion_time': completion_time
        })

    def get_elevator_tasks(self, elevator_id: int) -> List[HallCall]:
        return self.assigned_tasks.get(elevator_id, [])

    def reassign_task(self, call: HallCall, from_elevator_id: int, to_elevator_id: int):
        self.unassign_from_elevator(call, from_elevator_id)
        self.assign_to_elevator(call, to_elevator_id)

    def record_historical_data(self, period: str, floor: int, direction: str, count: int):
        key = f"{period}_{floor}_{direction}"
        if key not in self.historical_data:
            self.historical_data[key] = {'total': 0, 'count': 0}
        self.historical_data[key]['total'] += count
        self.historical_data[key]['count'] += 1

    def get_prediction(self, period: str, floor: int, direction: str) -> float:
        key = f"{period}_{floor}_{direction}"
        if key in self.historical_data:
            data = self.historical_data[key]
            return data['total'] / data['count'] if data['count'] > 0 else 0.0
        return 0.0
